"""Versioned updates from this repository. No in-place edits or project migrations.

HTTPS and a release SHA256 protect transport/integrity. This is not TUF signing;
repository ownership remains the trust boundary. Downloads never execute hooks.
"""
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import sys
import tempfile
import threading
import time
import urllib.request
import uuid
import zipfile

REPOSITORY = "MeetleJuice/repos"
MANIFEST_URL = f"https://raw.githubusercontent.com/{REPOSITORY}/main/releases/latest.json"
MAX_ARCHIVE = 20_000_000
MAX_EXPANDED = 80_000_000


def version_tuple(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{1,3}\.\d{1,3}\.\d{1,3}", value):
        raise ValueError("Release version must be major.minor.patch.")
    return tuple(map(int, value.split('.')))


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '-' + uuid.uuid4().hex + '.tmp')
    temporary.write_text(json.dumps(value, indent=2), encoding='utf-8')
    os.replace(temporary, path)


class ReleaseRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        prefix = f"https://raw.githubusercontent.com/{REPOSITORY}/main/releases/"
        if not newurl.startswith(prefix) or ".." in newurl:
            raise ValueError("Release redirect left the configured repository.")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_bytes(url, limit):
    # Fixed repository URLs only. Forbid redirects to arbitrary code hosts.
    prefix = f"https://raw.githubusercontent.com/{REPOSITORY}/main/releases/"
    if not url.startswith(prefix) or '?' in url or '#' in url or '..' in url:
        raise ValueError("Update URL is outside the configured release repository.")
    request = urllib.request.Request(url, headers={'User-Agent': 'Idea-Foundry-Updater', 'Cache-Control': 'no-cache'})
    with urllib.request.build_opener(ReleaseRedirectHandler()).open(request, timeout=20) as response:
        if not response.url.startswith(prefix):
            raise ValueError("Release download redirected outside the configured repository.")
        content = response.read(limit + 1)
    if len(content) > limit:
        raise ValueError("Release download exceeds its size limit.")
    return content


def validate_manifest(manifest):
    if not isinstance(manifest, dict):
        raise ValueError('Invalid release manifest.')
    version_tuple(manifest.get('version'))
    if manifest.get('schema') != 1 or manifest.get('data_schema') != 2:
        raise ValueError('This release needs a different updater/data format. Install it manually.')
    if not isinstance(manifest.get('sha256'), str) or not re.fullmatch('[a-f0-9]{64}', manifest['sha256']):
        raise ValueError('Release checksum is missing or invalid.')
    expected = f"https://raw.githubusercontent.com/{REPOSITORY}/main/releases/Idea-Foundry-{manifest['version']}.zip"
    if manifest.get('url') != expected:
        raise ValueError('Release archive must use the versioned file in the configured repository.')
    minimum = manifest.get('python', [3, 11])
    if not isinstance(minimum, list) or len(minimum) != 2 or any(type(n) is not int or not 0 <= n <= 99 for n in minimum):
        raise ValueError('Invalid Python requirement in release manifest.')
    if sys.version_info[:2] < tuple(minimum):
        raise ValueError(f"This release requires Python {minimum[0]}.{minimum[1]} or newer.")
    if not isinstance(manifest.get('notes', ''), str) or len(manifest.get('notes', '')) > 12000:
        raise ValueError('Invalid release notes.')
    return manifest


def extract_release(content, destination, manifest):
    """Validate the entire archive before writing any members."""
    validate_manifest(manifest)
    if len(content) > MAX_ARCHIVE or hashlib.sha256(content).hexdigest() != manifest['sha256']:
        raise ValueError('Release checksum did not match. Nothing was installed.')
    entries, seen, total = [], set(), 0
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        for info in archive.infolist():
            parts = PurePosixPath(info.filename).parts
            if info.is_dir():
                continue
            if not parts or parts[0] != 'Idea-Foundry' or len(parts) < 2 or '\\' in info.filename:
                raise ValueError('Invalid release archive layout.')
            relative = PurePosixPath(*parts[1:])
            if any(p in {'', '.', '..'} or ':' in p or p.endswith((' ', '.')) for p in parts) or info.filename.startswith('/'):
                raise ValueError('Unsafe archive path.')
            reserved = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
            if any(p.split('.')[0].upper() in reserved or not re.fullmatch(r"[A-Za-z0-9_. -]+", p) for p in relative.parts):
                raise ValueError('Archive filename is not portable to Windows.')
            mode = info.external_attr >> 16
            if stat.S_IFMT(mode) not in {0, stat.S_IFREG} or info.flag_bits & 1:
                raise ValueError('Links and encrypted archive entries are forbidden.')
            key = str(relative).lower()
            if key in seen or any(p in {'.env', '.git', 'data', 'artifacts', 'releases', '__pycache__'} for p in relative.parts):
                raise ValueError('Duplicate or private/runtime paths in release archive.')
            seen.add(key)
            total += info.file_size
            if total > MAX_EXPANDED or info.file_size > 2_000_000 or len(seen) > 2000:
                raise ValueError('Expanded release exceeds its size limit.')
            entries.append((info, relative))
        required = {'run.py', 'bootstrap.py', 'forge/server.py', 'forge/__init__.py'}
        if not required.issubset(seen):
            raise ValueError('Release is missing required application files.')
        init = archive.read('Idea-Foundry/forge/__init__.py').decode('utf-8')
        if not re.search(r"__version__\s*=\s*['\"]" + re.escape(manifest['version']) + r"['\"]", init):
            raise ValueError('Archive version does not match release metadata.')
        for info, relative in entries:
            target = Path(destination).joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(info))


class UpdateManager:
    def __init__(self, home, program_root, bench, downloader=fetch_bytes):
        self.home = Path(home)
        self.root = Path(program_root)
        self.bench = bench
        self.downloader = downloader
        self.directory = self.home / 'updates'
        self.lock = threading.RLock()
        self.release = None
        self.state = {'status': 'idle', 'message': 'Check for a newer release from GitHub.', 'repository': REPOSITORY}
        self.restart = False

    def record(self, kind, data):
        try:
            self.bench.diagnostics.record(kind, data)
        except Exception:
            pass

    def status(self):
        with self.lock:
            result = dict(self.state)
            result['supervised'] = os.environ.get('FOUNDRY_SUPERVISED') == '1'
            result['release'] = self.release
            path = self.directory / 'last-result.json'
            if path.is_file():
                try:
                    result['last_result'] = json.loads(path.read_text(encoding='utf-8'))
                except (ValueError, OSError):
                    pass
            return result

    def check(self, current):
        with self.lock:
            if self.state['status'] in {'checking', 'installing', 'restarting'}:
                raise ValueError('An update operation is already running.')
            self.state.update(status='checking', message='Checking the release repository…')
        self.record('update_check_started', {'current_version': current})
        try:
            release = validate_manifest(json.loads(self.downloader(MANIFEST_URL, 30000)))
            available = version_tuple(release['version']) > version_tuple(current)
            with self.lock:
                self.release = release
                self.state.update(status='available' if available else 'current', message=f"Version {release['version']} is available." if available else 'You have the latest published version.')
                self.state['completion_event'] = {'type':'update_ready','version':release['version'],
                    'requires_user_action':True,'message':'Version '+release['version']+' is ready. Press the Update button in the app to apply changes.'} if available else None
            if available:print(self.state['completion_event']['message'],flush=True)
            self.record('update_check_finished', {'current_version': current, 'release_version': release['version'],
                'available': available, 'success': True})
        except Exception as exc:
            with self.lock:
                self.release = None
                self.state['completion_event'] = None
                self.state.update(status='error', message=f'Could not check for updates: {exc}. Your current installation is unchanged.')
            self.record('update_check_finished', {'current_version': current, 'success': False,
                'exception_type': type(exc).__name__})
        return self.status()

    def prepare(self, backup):
        release = dict(self.release)
        self.record('update_download_started', {'version': release['version']})
        content = self.downloader(release['url'], MAX_ARCHIVE)
        versions = self.directory / 'versions'
        versions.mkdir(parents=True, exist_ok=True)
        target = versions / release['version']
        if target.exists():
            raise ValueError('That release directory already exists. Keep it for recovery and install manually.')
        # Validate before saving backup or changing the active-version pointer.
        with tempfile.TemporaryDirectory(prefix='.stage-', dir=versions) as temp:
            staged = Path(temp) / 'program'
            extract_release(content, staged, release)
            self.record('update_download_verified', {'version': release['version'], 'bytes': len(content),
                'sha256': hashlib.sha256(content).hexdigest()})
            backup_path = self.directory / 'backups' / (time.strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:6] + '.zip')
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            backup_path.write_bytes(backup)
            pointer = self.directory / 'current.json'
            previous = json.loads(pointer.read_text(encoding='utf-8')) if pointer.exists() else None
            os.replace(staged, target)
            try:
                atomic_json(self.directory / 'pending.json', {'version': release['version'], 'previous': previous, 'backup': str(backup_path)})
                atomic_json(pointer, {'version': release['version']})
            except Exception:
                # atomic_json leaves the prior pointer intact if its write fails.
                (self.directory / 'pending.json').unlink(missing_ok=True)
                shutil.rmtree(target)
                raise
        self.record('update_prepared', {'version': release['version'], 'backup_saved': backup_path.is_file(),
            'previous_version': (previous or {}).get('version'), 'pending_health_check': True})
        return backup_path

    def install(self, current, shutdown):
        with self.lock, self.bench.lock:
            if os.environ.get('FOUNDRY_SUPERVISED') != '1':
                raise ValueError('Start Foundry with Start-Foundry.bat or python run.py to enable managed restarts.')
            if not self.release or self.state['status'] != 'available' or version_tuple(self.release['version']) <= version_tuple(current):
                raise ValueError('Check for a newer release first.')
            if any(t.is_alive() for t, _ in self.bench.jobs.values()):
                raise ValueError('Finish or stop running jobs before updating.')
            if getattr(self.bench, 'idea_busy', False):
                raise ValueError('Wait for Generate Idea to finish before updating.')
            if getattr(self.bench,'test_busy',False):raise ValueError('Wait for system tests to finish before updating.')
            self.bench.maintenance = True
            self.state.update(status='installing', message='Validating download and backing up projects. Keep this terminal open.')
            self.record('update_install_started', {'current_version': current, 'release_version': self.release['version']})

        def work():
            try:
                backup = self.bench.backup()
                backup_path = self.prepare(backup)
                with self.lock:
                    self.state.update(status='restarting', message='Update installed. Restarting; this page will reconnect.', backup=str(backup_path))
                    self.restart = True
                self.record('update_restart_requested', {'version': self.release['version']})
                shutdown()
            except Exception as exc:
                with self.lock:
                    self.state.update(status='error', message=f'Update stopped: {exc}. Your projects were preserved.')
                self.bench.maintenance = False
                self.record('update_install_failed', {'exception_type': type(exc).__name__, 'projects_preserved': True})
        threading.Thread(target=work, daemon=True).start()
        return self.status()
