"""Update integrity, archive safety, preservation, and real supervisor recovery."""
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import urllib.request
import zipfile

from bootstrap import home_for, rollback, selected_program
from forge import __version__
from forge.core import Workbench
from forge.updates import UpdateManager, validate_manifest, extract_release, REPOSITORY, atomic_json, fetch_bytes

ROOT = Path(__file__).resolve().parents[1]


def manifest_for(content, version='0.8.2'):
    return {'schema': 1, 'version': version, 'data_schema': 2, 'python': [3, 11],
            'url': f'https://raw.githubusercontent.com/{REPOSITORY}/main/releases/Idea-Foundry-{version}.zip',
            'sha256': hashlib.sha256(content).hexdigest(), 'notes': 'Test release'}


def archive_for(extra=None):
    stream = io.BytesIO()
    files = {'run.py': '# launcher', 'bootstrap.py': '# supervisor', 'forge/server.py': '# server', 'forge/__init__.py': '__version__ = "0.8.2"\n'}
    files.update(extra or {})
    with zipfile.ZipFile(stream, 'w') as archive:
        for name, content in files.items():
            archive.writestr('Idea-Foundry/' + name, content)
    return stream.getvalue()


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)
        self.bench = Workbench(self.home / 'projects')
        self.content = archive_for()
        self.manifest = manifest_for(self.content)
        self.manager = UpdateManager(self.home, ROOT, self.bench, lambda url, limit: json.dumps(self.manifest).encode() if url.endswith('.json') else self.content)

    def tearDown(self):
        self.temp.cleanup()

    def test_check_distinguishes_new_current_and_older(self):
        self.assertEqual(self.manager.check('0.5.0')['status'], 'available')
        self.assertEqual(self.manager.check('0.8.2')['status'], 'current')
        self.assertEqual(self.manager.check('0.9.0')['status'], 'current')

    def test_failed_check_clears_previously_available_release(self):
        self.manager.check('0.5.0')
        self.manager.downloader = lambda *a: b'not json'
        self.assertEqual(self.manager.check('0.5.0')['status'], 'error')
        self.assertIsNone(self.manager.release)

    def test_downloads_cannot_use_other_hosts_or_repository_paths(self):
        for url in ['http://localhost/archive.zip', 'https://example.com/a', f'https://raw.githubusercontent.com/{REPOSITORY}/main/releases/../x']:
            with self.subTest(url=url), self.assertRaises(ValueError):
                fetch_bytes(url, 10)
        bad = dict(self.manifest, url='https://example.com/archive.zip')
        with self.assertRaises(ValueError):
            validate_manifest(bad)

    def test_bad_checksum_never_writes_files(self):
        target = self.home / 'install'
        bad = dict(self.manifest, sha256='0' * 64)
        with self.assertRaisesRegex(ValueError, 'checksum'):
            extract_release(self.content, target, bad)
        self.assertFalse(target.exists())

    def test_archive_paths_duplicates_secrets_and_missing_files_are_rejected(self):
        for name in ['../escape.py', 'data/projects/x.txt', '.env', 'forge/../../escape.py', 'APP.py', 'a\\b.py']:
            extra = {name: 'bad'}
            if name == 'APP.py':
                extra['app.py'] = 'collision'
            content = archive_for(extra)
            target = self.home / 'invalid'
            with self.subTest(name=name), self.assertRaises(ValueError):
                extract_release(content, target, manifest_for(content))
            self.assertFalse(target.exists())
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as archive:
            archive.writestr('Idea-Foundry/README.md', 'incomplete')
        with self.assertRaisesRegex(ValueError, 'missing'):
            extract_release(stream.getvalue(), self.home / 'missing', manifest_for(stream.getvalue()))

    def test_symlink_archive_entry_is_rejected(self):
        stream = io.BytesIO(self.content)
        with zipfile.ZipFile(stream, 'a') as archive:
            info = zipfile.ZipInfo('Idea-Foundry/link.py')
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(info, 'outside')
        content = stream.getvalue()
        with self.assertRaisesRegex(ValueError, 'Links'):
            extract_release(content, self.home / 'bad', manifest_for(content))

    def test_data_schema_python_and_version_mismatches_are_rejected(self):
        for change in [{'data_schema': 99}, {'version': '../bad'}, {'python': [99, 0]}, {'sha256': 'oops'}]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_manifest(dict(self.manifest, **change))
        content = archive_for({'forge/__init__.py': '__version__ = "0.4.0"'})
        with self.assertRaisesRegex(ValueError, 'version'):
            extract_release(content, self.home / 'bad', manifest_for(content))

    def test_prepare_preserves_program_projects_keys_and_records_backup(self):
        self.manager.check('0.5.0')
        project = self.home / 'projects' / 'keep.txt'
        project.write_text('user work')
        key = self.home / '.env'
        key.write_text('GROQ_API_KEY=test-only-placeholder')
        backup = self.manager.prepare(b'backup fixture')
        self.assertEqual(backup.read_bytes(), b'backup fixture')
        self.assertEqual(project.read_text(), 'user work')
        self.assertEqual(key.read_text(), 'GROQ_API_KEY=test-only-placeholder')
        self.assertEqual(json.loads((self.home / 'updates/current.json').read_text()), {'version': '0.8.2'})
        self.assertTrue((self.home / 'updates/versions/0.8.2/run.py').is_file())
        self.assertEqual(selected_program(ROOT, self.home), self.home / 'updates/versions/0.8.2')
        self.assertTrue(rollback(self.home, 'failed startup'))
        self.assertEqual(selected_program(ROOT, self.home), ROOT)
        self.assertEqual(project.read_text(), 'user work')
        self.assertEqual(backup.read_bytes(), b'backup fixture')

    def test_existing_version_is_never_overwritten(self):
        self.manager.check('0.5.0')
        self.manager.prepare(b'backup')
        with self.assertRaisesRegex(ValueError, 'already exists'):
            self.manager.prepare(b'other')

    def test_install_requires_supervisor_and_idle_jobs(self):
        self.manager.check('0.5.0')
        with patch.dict(os.environ, {'FOUNDRY_SUPERVISED': '0'}), self.assertRaisesRegex(ValueError, 'Start Foundry'):
            self.manager.install('0.5.0', lambda: None)
        event = threading.Event()
        worker = threading.Thread(target=lambda: event.wait(5))
        worker.start()
        self.bench.jobs['test'] = worker, event
        try:
            with patch.dict(os.environ, {'FOUNDRY_SUPERVISED': '1'}), self.assertRaisesRegex(ValueError, 'running jobs'):
                self.manager.install('0.5.0', lambda: None)
            self.assertFalse(self.bench.maintenance)
        finally:
            event.set()
            worker.join()

    def test_install_failure_releases_maintenance_and_keeps_active_pointer(self):
        self.manager.check('0.5.0')
        self.manager.downloader = lambda *a: b'wrong checksum'
        with patch.dict(os.environ, {'FOUNDRY_SUPERVISED': '1'}):
            self.manager.install('0.5.0', lambda: self.fail('Must not restart'))
            deadline = time.monotonic() + 5
            while self.manager.status()['status'] == 'installing' and time.monotonic() < deadline:
                time.sleep(.02)
        self.assertEqual(self.manager.status()['status'], 'error')
        self.assertFalse(self.bench.maintenance)
        self.assertFalse((self.home / 'updates/current.json').exists())

    def test_launcher_honors_both_override_formats(self):
        self.assertEqual(home_for(ROOT, ['--data-dir', str(self.home)]), self.home)
        self.assertEqual(home_for(ROOT, ['--data-dir=' + str(self.home)]), self.home)


class SupervisorTests(unittest.TestCase):
    """Start actual application servers through the real stable launcher."""
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)
        self.process = None
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            self.port = sock.getsockname()[1]

    def tearDown(self):
        if self.process and self.process.poll() is None:
            if os.name == 'nt':
                subprocess.run(['taskkill', '/PID', str(self.process.pid), '/T', '/F'], capture_output=True, timeout=10)
            else:
                os.killpg(self.process.pid, signal.SIGINT)
                try:
                    self.process.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    os.killpg(self.process.pid, signal.SIGKILL)
            self.process.wait(timeout=10)
        self.temp.cleanup()

    def prepare_version(self, broken=False):
        target = self.home / 'updates/versions/0.8.2'
        target.mkdir(parents=True)
        shutil.copytree(ROOT / 'forge', target / 'forge', ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copyfile(ROOT / 'run.py', target / 'run.py')
        shutil.copyfile(ROOT / 'bootstrap.py', target / 'bootstrap.py')
        (target / 'forge/__init__.py').write_text('__version__ = "0.8.2"\n')
        if broken:
            (target / 'run.py').write_text('raise SystemExit(2)\n')
        atomic_json(self.home / 'updates/current.json', {'version': '0.8.2'})
        atomic_json(self.home / 'updates/pending.json', {'version': '0.8.2', 'previous': None, 'backup': 'preserved-backup.zip'})

    def start_and_wait(self, version):
        flags = {'start_new_session': True} if os.name != 'nt' else {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP}
        self.process = subprocess.Popen([sys.executable, str(ROOT / 'run.py'), '--data-dir', str(self.home), '--port', str(self.port)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **flags)
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{self.port}/health', timeout=1) as response:
                    if json.load(response)['version'] == version and (self.home / 'updates/last-result.json').exists():
                        return
            except (OSError, ValueError):
                pass
            if self.process.poll() is not None:
                self.fail('Supervisor exited before application became healthy')
            time.sleep(.1)
        self.fail('Application did not pass startup health check')

    def test_successful_new_version_starts_and_preserves_user_data(self):
        self.prepare_version()
        (self.home / '.env').write_text('GROQ_API_KEY=test-local-placeholder')
        (self.home / 'projects').mkdir()
        (self.home / 'projects/user-file.txt').write_text('preserve this')
        self.start_and_wait('0.8.2')
        report = json.loads((self.home / 'updates/last-result.json').read_text())
        self.assertEqual(report['status'], 'updated')
        self.assertFalse((self.home / 'updates/pending.json').exists())
        self.assertEqual((self.home / 'projects/user-file.txt').read_text(), 'preserve this')
        self.assertEqual((self.home / '.env').read_text(), 'GROQ_API_KEY=test-local-placeholder')

    def test_bad_release_rolls_back_and_starts_original_program(self):
        self.prepare_version(broken=True)
        self.start_and_wait(__version__)
        self.assertEqual(json.loads((self.home / 'updates/last-result.json').read_text())['status'], 'rolled_back')
        self.assertFalse((self.home / 'updates/current.json').exists())


class UpdateHTTPTests(unittest.TestCase):
    def test_authenticated_install_backs_up_then_stops_server(self):
        from forge.server import make_server
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            bench = Workbench(home / 'projects')
            (home / 'projects/keep.txt').write_text('important user work')
            (home / '.env').write_text('EXCLUDED=placeholder')
            server = make_server(0, bench)
            content = archive_for()
            manifest = manifest_for(content)
            server.updater.downloader = lambda url, limit: json.dumps(manifest).encode() if url.endswith('.json') else content
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            base = f'http://127.0.0.1:{server.server_port}'
            try:
                with urllib.request.urlopen(base) as response:
                    html = response.read().decode()
                token = html.split('name="foundry-token" content="')[1].split('"')[0]
                def post(path):
                    req = urllib.request.Request(base + path, data=b'{}', headers={'Content-Type': 'application/json', 'X-Foundry-Token': token})
                    with urllib.request.urlopen(req, timeout=5) as response:
                        return json.load(response)
                self.assertEqual(post('/api/updates/check')['status'], 'available')
                with patch.dict(os.environ, {'FOUNDRY_SUPERVISED': '1'}):
                    post('/api/updates/install')
                    worker.join(5)
                self.assertFalse(worker.is_alive())
                self.assertTrue(server.updater.restart)
                backup = next((home / 'updates/backups').glob('*.zip'))
                with zipfile.ZipFile(backup) as archive:
                    self.assertEqual(archive.read('projects/keep.txt'), b'important user work')
                    self.assertFalse(any('.env' in name for name in archive.namelist()))
                self.assertEqual((home / 'projects/keep.txt').read_text(), 'important user work')
            finally:
                server.shutdown()
                server.server_close()


class UpdateTransactionTests(unittest.TestCase):
    def test_pointer_write_failure_cleans_new_version_but_keeps_backup(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            bench = Workbench(home / 'projects')
            content = archive_for()
            manager = UpdateManager(home, ROOT, bench, lambda *args: content)
            manager.release = manifest_for(content)
            real_atomic = atomic_json
            def fail_pointer(path, value):
                if Path(path).name == 'current.json':
                    raise OSError('simulated full disk')
                return real_atomic(path, value)
            with patch('forge.updates.atomic_json', side_effect=fail_pointer), self.assertRaises(OSError):
                manager.prepare(b'backup')
            self.assertFalse((home / 'updates/current.json').exists())
            self.assertFalse((home / 'updates/pending.json').exists())
            self.assertFalse((home / 'updates/versions/0.8.2').exists())
            self.assertEqual(next((home / 'updates/backups').glob('*.zip')).read_bytes(), b'backup')
