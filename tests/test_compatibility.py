"""Legacy metadata/backup parity and actual 0.5 launcher → 0.6 startup."""
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request
import zipfile

from forge import __version__
from forge.core import Workbench
from forge.models import ModelError
from forge.scaffolds import starter_files
from forge.updates import atomic_json
from tests.fixtures import PLAN, APP, TEST
from tests.test_workbench import ScriptedModels, await_job

ROOT = Path(__file__).resolve().parents[1]
CONFIG = {'provider': 'ollama', 'model': 'test'}


def legacy_state():
    return {'id': 'a' * 32, 'title': 'Legacy app', 'idea': 'Build a local app', 'created': '2026-10-18T00:00:00+00:00',
            'updated': '2026-10-18T00:00:00+00:00', 'schema_version': 2, 'status': 'generated',
            'planner': CONFIG, 'coder': CONFIG, 'approved': True, 'plan': copy.deepcopy(PLAN), 'next_task': 1,
            'events': [], 'snapshots': [], 'repair_count': 0, 'checks': None}


def write_legacy(home):
    state = legacy_state()
    project = home / 'projects' / state['id']
    source = project / 'source'
    source.mkdir(parents=True)
    (project / 'state.json').write_text(json.dumps(state))
    for name, content in {'app.py': APP, 'test_app.py': TEST, 'CHECKS.json': json.dumps(PLAN['checks'])}.items():
        (source / name).write_text(content)
    return project


class LegacyParityTests(unittest.TestCase):
    def test_loading_and_backing_up_old_state_does_not_rewrite_source_or_metadata(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            project = write_legacy(home)
            before = {str(p.relative_to(project)): p.read_bytes() for p in project.rglob('*') if p.is_file()}
            bench = Workbench(home / 'projects')
            self.assertEqual(bench.load('a' * 32)['status'], 'generated')
            with zipfile.ZipFile(io.BytesIO(bench.backup())) as archive:
                for relative, data in before.items():
                    self.assertEqual(archive.read('projects/' + 'a' * 32 + '/' + relative), data)
            after = {str(p.relative_to(project)): p.read_bytes() for p in project.rglob('*') if p.is_file()}
            self.assertEqual(before, after)

    def test_already_approved_legacy_checks_are_not_revalidated_or_rewritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            project = write_legacy(home)
            state = json.loads((project / 'state.json').read_text())
            # The old, approved proposal is inconsistent. New reviews must not alter it.
            state['plan']['checks'][0]['json_contains'] = [{'title': 'Buy milk'}]
            (project / 'state.json').write_text(json.dumps(state))
            (project / 'source/CHECKS.json').write_text(json.dumps(state['plan']['checks']))
            bench = Workbench(home / 'projects', ScriptedModels([]))
            bench.start(state['id'], 'build', {'execute': False, 'repairs': 0})
            result = await_job(bench, state['id'])
            self.assertEqual(result['status'], 'generated', result.get('error'))
            self.assertEqual(result['plan'], state['plan'])
            self.assertEqual(json.loads(bench.files(state['id'])['CHECKS.json']), state['plan']['checks'])
            self.assertIsNone(result['checks'])

    def test_builder_service_failure_uses_one_configured_fallback_and_keeps_source_only_mode(self):
        with tempfile.TemporaryDirectory() as temporary:
            models = ScriptedModels([PLAN, ModelError('Unavailable', 'transport'), {'files': {'app.py': APP, 'test_app.py': TEST}}])
            coder = {**CONFIG, 'fallback': {'provider': 'ollama', 'model': 'backup-coder'}}
            bench = Workbench(temporary, models, verifier=lambda *a: self.fail('No execution consent'))
            state = bench.create('Build a task tracker', CONFIG, coder)
            state = await_job(bench, state['id'])
            bench.approve(state['id'], state['plan'])
            bench.start(state['id'], 'build', {'execute': False, 'repairs': 0})
            state = await_job(bench, state['id'])
            self.assertEqual(state['status'], 'generated', state.get('error'))
            self.assertEqual(len(models.calls), 3)
            self.assertEqual(state['model_calls'][-1]['model'], 'backup-coder')
            self.assertTrue(state['model_calls'][-1]['fallback'])
            self.assertEqual(bench.files(state['id'])['app.py'], APP)

    def test_revision_review_preserves_the_same_baseline_rules_as_approval(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            project = write_legacy(home)
            state = json.loads((project / 'state.json').read_text())
            state.update(approved=False, baseline_plan=copy.deepcopy(PLAN))
            (project / 'state.json').write_text(json.dumps(state))
            bench = Workbench(home / 'projects')
            bad = copy.deepcopy(PLAN)
            bad['features'].reverse()
            result = bench.review_proposal(state['id'], bad)
            self.assertFalse(result['passed'])
            self.assertIn('preserve the original features', result['findings'][0]['message'])
            self.assertFalse(bench.review_proposal(state['id'], [])['passed'])


class OldLauncherTests(unittest.TestCase):
    def test_published_05_supervisor_starts_new_server_with_unchanged_projects_and_keys(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            old = root / 'old/Idea-Foundry'
            (old / 'forge').mkdir(parents=True)
            # Exact launcher bytes extracted from the published 0.5 archive, inert in fixtures.
            for source, target in [('bootstrap-v05.txt', 'bootstrap.py'), ('run-v05.txt', 'run.py'), ('version-v05.txt', 'forge/__init__.py')]:
                (old / target).write_bytes((ROOT / 'tests/fixture_data' / source).read_bytes())
            home = root / 'home'
            project = write_legacy(home)
            before = (project / 'state.json').read_bytes()
            (home / '.env').write_text('GROQ_API_KEY=local-test-placeholder')
            version = home / 'updates/versions' / __version__
            version.mkdir(parents=True)
            shutil.copytree(ROOT / 'forge', version / 'forge', ignore=shutil.ignore_patterns('__pycache__'))
            shutil.copyfile(ROOT / 'run.py', version / 'run.py')
            atomic_json(home / 'updates/current.json', {'version': __version__})
            atomic_json(home / 'updates/pending.json', {'version': __version__, 'previous': None, 'backup': 'old-workspace-backup.zip'})
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0)); port = sock.getsockname()[1]
            flags = {'start_new_session': True} if os.name != 'nt' else {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP}
            proc = subprocess.Popen([sys.executable, str(old / 'run.py'), '--data-dir', str(home), '--port', str(port)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **flags)
            try:
                deadline = time.monotonic() + 15
                while time.monotonic() < deadline:
                    try:
                        with urllib.request.urlopen(f'http://127.0.0.1:{port}/health', timeout=1) as response:
                            ready = json.load(response)
                        if ready['version'] == __version__ and (home / 'updates/last-result.json').exists():
                            break
                    except (OSError, ValueError):
                        pass
                    if proc.poll() is not None:
                        self.fail('Old supervisor exited before starting the new version')
                    time.sleep(.1)
                else:
                    self.fail('New server did not become healthy under the 0.5 supervisor')
                self.assertEqual(json.loads((home / 'updates/last-result.json').read_text())['status'], 'updated')
                with urllib.request.urlopen(f'http://127.0.0.1:{port}/') as response:
                    html = response.read().decode()
                token = html.split('name="foundry-token" content="')[1].split('"')[0]
                request = urllib.request.Request(f'http://127.0.0.1:{port}/api/projects', headers={'X-Foundry-Token': token})
                with urllib.request.urlopen(request) as response:
                    projects = json.load(response)
                self.assertEqual(projects[0]['id'], 'a' * 32)
                self.assertEqual((project / 'state.json').read_bytes(), before)
                self.assertEqual((home / '.env').read_text(), 'GROQ_API_KEY=local-test-placeholder')
            finally:
                if proc.poll() is None:
                    if os.name == 'nt':
                        subprocess.run(['taskkill', '/PID', str(proc.pid), '/T', '/F'], capture_output=True, timeout=10)
                    else:
                        os.killpg(proc.pid, signal.SIGINT)
                    proc.wait(timeout=10)
