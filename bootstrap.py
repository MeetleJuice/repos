"""Stable launcher supervising versioned Foundry servers and failed-start rollback.

Uses only the standard library and does not import the installed application.
The original downloaded folder always remains a fallback.
"""
import json
import os
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime, timezone
import re
import signal
import subprocess
import sys
import time
import traceback
import urllib.request
import uuid
import webbrowser

MAX_LAUNCH_LOG_BYTES = 1_000_000
STARTUP_HEALTH_SECONDS = 25
_EVENT_FIELDS = {'pid', 'returncode', 'healthy', 'version', 'seconds', 'phase', 'exception_type',
                 'location', 'line', 'launch_id', 'reason', 'event_count'}


class SupervisorBusy(Exception):
    """Separate lock contention from an application's ValueError."""


def record_launch(home, kind, **data):
    """Independent, bounded metadata evidence. Never accepts exception messages or streams."""
    try:
        directory = Path(home) / 'diagnostics'
        directory.mkdir(parents=True, exist_ok=True)
        if directory.is_symlink():
            return
        path = directory / 'launcher.jsonl'
        if path.is_symlink() or path.with_suffix('.jsonl.1').is_symlink():
            return
        clean = {}
        for key, value in data.items():
            if key not in _EVENT_FIELDS:
                continue
            if isinstance(value, (bool, int, float)) or value is None:
                clean[key] = value
            elif isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_.:/ -]{0,160}', value):
                clean[key] = value
        record = {'schema': 1, 'id': uuid.uuid4().hex, 'time': datetime.now(timezone.utc).isoformat(),
                  'origin': 'independent_supervisor', 'kind': kind, 'data': clean}
        line = (json.dumps(record, separators=(',', ':')) + '\n').encode('utf-8')
        if path.exists() and path.stat().st_size + len(line) > MAX_LAUNCH_LOG_BYTES:
            os.replace(path, path.with_suffix('.jsonl.1'))
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(fd, 'ab') as stream:
            stream.write(line)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError:
        # Evidence loss must not prevent recovery or starting the application.
        pass


def record_launcher_exception(home, exc, phase='application_import_or_main'):
    """A second process can still retain its exit event if this helper is unavailable."""
    frames = traceback.extract_tb(exc.__traceback__)
    frame = frames[-1] if frames else None
    syntax_file = exc.filename if isinstance(exc, SyntaxError) else None
    syntax_line = exc.lineno if isinstance(exc, SyntaxError) else None
    record_launch(home, 'application_exception', phase=phase,
                  exception_type=type(exc).__name__,
                  location=Path(syntax_file).name if syntax_file else Path(frame.filename).name if frame else None,
                  line=syntax_line if syntax_line is not None else frame.lineno if frame else None)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_):
        return None


def instance_url(home):
    """Accept only a locally published endpoint whose health response matches its boot."""
    info = read_json(Path(home) / 'diagnostics' / 'instance.json')
    if not info or not isinstance(info.get('port'), int) or not 0 < info['port'] < 65536:
        return None
    nonce = info.get('boot')
    if not isinstance(nonce, str) or not nonce or len(nonce) > 128:
        return None
    url = f"http://127.0.0.1:{info['port']}"
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
        with opener.open(url + '/health', timeout=1) as response:
            content = response.read(4097)
            if len(content) > 4096:
                return None
            health = json.loads(content)
        return url if health.get('status') == 'ok' and health.get('boot') == nonce else None
    except (OSError, ValueError, TypeError):
        return None


@contextmanager
def supervisor_lock(home):
    Path(home).mkdir(parents=True, exist_ok=True)
    with (Path(home) / '.supervisor.lock').open('a+b') as handle:
        handle.seek(0)
        if not handle.read(1):
            handle.write(b'0')
            handle.flush()
        handle.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise SupervisorBusy('Another Foundry launcher is starting or running.') from None
        try:
            yield
        finally:
            if os.name == 'nt':
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def home_for(root, arguments):
    override = None
    for index, argument in enumerate(arguments):
        if argument == '--data-dir' and index + 1 < len(arguments):
            override = arguments[index + 1]
        elif argument.startswith('--data-dir='):
            override = argument.split('=', 1)[1]
    if override or os.getenv('FOUNDRY_HOME'):
        return Path(override or os.environ['FOUNDRY_HOME']).expanduser().resolve()
    if os.name == 'nt':
        return Path(os.getenv('LOCALAPPDATA', Path.home() / 'AppData' / 'Local')) / 'IdeaFoundry'
    return Path(root) / 'data'


def read_json(path):
    try:
        result = json.loads(Path(path).read_text(encoding='utf-8'))
        return result if isinstance(result, dict) else None
    except (OSError, ValueError):
        return None


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '-' + uuid.uuid4().hex + '.tmp')
    try:
        with temporary.open('x', encoding='utf-8') as stream:
            stream.write(json.dumps(value, indent=2))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def selected_program(root, home):
    pointer = read_json(home / 'updates' / 'current.json')
    if pointer:
        import re
        version = pointer.get('version', '')
        if not isinstance(version, str) or not re.fullmatch(r'\d{1,3}\.\d{1,3}\.\d{1,3}', version):
            raise ValueError('Invalid installed-version pointer. Original program is intact.')
        candidate = home / 'updates' / 'versions' / version
        if not (candidate / 'run.py').is_file() or candidate.is_symlink():
            raise ValueError('Installed version is missing. Original program is intact.')
        # A newer manually downloaded launcher must not be downgraded by an old pointer.
        import re as regex
        try:
            text = (Path(root) / 'forge' / '__init__.py').read_text(encoding='utf-8')
        except OSError:
            # A valid installed version can still start if the user moved the
            # original download. Recovery to that absent folder is unavailable.
            text = ''
        match = regex.search(r"__version__\s*=\s*['\"](\d+\.\d+\.\d+)['\"]", text)
        if match and tuple(map(int, match[1].split('.'))) > tuple(map(int, version.split('.'))):
            return Path(root)
        return candidate
    return Path(root)


def rollback(home, reason):
    updates = home / 'updates'
    pending = read_json(updates / 'pending.json')
    if not pending:
        return False
    previous = pending.get('previous')
    pointer = updates / 'current.json'
    if previous:
        write_json(pointer, previous)
    else:
        pointer.unlink(missing_ok=True)
    write_json(updates / 'last-result.json', {'status': 'rolled_back', 'time': time.time(), 'message': reason, 'backup': pending.get('backup')})
    (updates / 'pending.json').unlink(missing_ok=True)
    record_launch(home, 'update_rolled_back', reason='startup_health_check_failed')
    return True


def supervise(root, arguments):
    root = Path(root).resolve()
    home = home_for(root, arguments)
    existing = instance_url(home)
    if existing:
        record_launch(home, 'existing_instance_reused')
        if '--open' in arguments:
            webbrowser.open(existing)
        return 0
    try:
        with supervisor_lock(home):
            return _supervise_locked(root, home, arguments)
    except SupervisorBusy:
        # A simultaneous second double-click never launches a second server.
        for _ in range(20):
            existing = instance_url(home)
            if existing:
                if '--open' in arguments:
                    webbrowser.open(existing)
                record_launch(home, 'existing_instance_reused')
                return 0
            time.sleep(.2)
        record_launch(home, 'duplicate_launcher_blocked')
        print('Foundry is already starting or running. Wait a moment and use its browser window.', file=sys.stderr)
        return 1
    except OSError as exc:
        record_launcher_exception(home, exc, 'supervisor_startup')
        print('Foundry launcher could not start. The original program and project data were preserved.', file=sys.stderr)
        return 1


def _supervise_locked(root, home, arguments):
    session_path = home / 'diagnostics' / 'launcher-session.json'
    previous = read_json(session_path)
    if previous and previous.get('status') == 'running':
        record_launch(home, 'previous_session_unfinished', reason='no_clean_supervisor_end_record')
    launch_id = uuid.uuid4().hex
    write_json(session_path, {'status': 'running', 'pid': os.getpid(), 'launch_id': launch_id})
    record_launch(home, 'supervisor_started', pid=os.getpid(), launch_id=launch_id)
    try:
        result = _supervise_programs(root, home, arguments)
    except BaseException as exc:
        record_launcher_exception(home, exc, 'supervisor')
        raise
    else:
        write_json(session_path, {'status': 'stopped', 'pid': os.getpid(), 'returncode': result, 'launch_id': launch_id})
        record_launch(home, 'supervisor_stopped', returncode=result, launch_id=launch_id)
        return result


def _supervise_programs(root, home, arguments):
    # Managed children inherit the original stable data location and settings fallback.
    env = dict(os.environ, FOUNDRY_HOME=str(home), FOUNDRY_LAUNCH_ROOT=str(root), FOUNDRY_SUPERVISED='1')
    while True:
        try:
            program = selected_program(root, home)
        except ValueError as exc:
            if rollback(home, str(exc)):
                continue
            record_launcher_exception(home, exc, 'selected_program')
            if (root / 'run.py').is_file():
                # Do not erase the broken pointer or versions. The original
                # reviewed download is still a useful non-destructive fallback.
                record_launch(home, 'selected_program_fallback', reason='invalid_installed_pointer')
                print('The installed-version pointer could not be used. Starting the original program; diagnostic evidence was preserved.', file=sys.stderr)
                program = root
            else:
                print('The installed program and original fallback are unavailable. Keep the workspace and reinstall the program folder.', file=sys.stderr)
                return 1
        pending = read_json(home / 'updates' / 'pending.json')
        nonce = uuid.uuid4().hex
        env['FOUNDRY_BOOT_NONCE'] = nonce
        ready = home / 'updates' / ('ready-' + nonce + '.json')
        env['FOUNDRY_READY_FILE'] = str(ready)
        child = subprocess.Popen([sys.executable, str(program / 'run.py'), '--server', *arguments], cwd=program, env=env)
        record_launch(home, 'child_started', pid=child.pid, phase='startup')
        healthy = False
        started = time.monotonic()
        deadline = time.monotonic() + STARTUP_HEALTH_SECONDS
        try:
            while child.poll() is None:
                if not healthy:
                    report = read_json(ready)
                    if report:
                        try:
                            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
                            with opener.open(f"http://127.0.0.1:{int(report['port'])}/health", timeout=1) as response:
                                health = json.load(response)
                            healthy = health.get('boot') == nonce and health.get('status') == 'ok' and (not pending or health.get('version') == pending['version'])
                        except (OSError, ValueError, KeyError):
                            pass
                    if healthy:
                        record_launch(home, 'child_healthy', pid=child.pid, version=health.get('version'), seconds=round(time.monotonic()-started, 3))
                        if pending:
                            write_json(home / 'updates' / 'last-result.json', {'status': 'updated', 'time': time.time(), 'message': 'Update started successfully.', 'version': pending['version'], 'backup': pending.get('backup')})
                            (home / 'updates' / 'pending.json').unlink(missing_ok=True)
                    elif time.monotonic() > deadline:
                        record_launch(home, 'startup_health_timeout', pid=child.pid, seconds=round(time.monotonic()-started, 3))
                        child.terminate()
                        try:
                            child.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            child.kill()
                        break
                time.sleep(0.2)
            code = child.wait()
        except KeyboardInterrupt:
            record_launch(home, 'user_stop_requested', pid=child.pid)
            # Console Ctrl+C also reaches the child. POSIX tests may signal only us.
            if child.poll() is None:
                if os.name != 'nt':
                    child.send_signal(signal.SIGINT)
                # Windows console Ctrl+C reaches both processes. Give the
                # server's finally block time to stop workers and persist state
                # before resorting to TerminateProcess.
            try:
                child.wait(timeout=8)
            except subprocess.TimeoutExpired:
                record_launch(home, 'shutdown_grace_expired', pid=child.pid)
                child.terminate()
                try:
                    child.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
            return 0
        finally:
            ready.unlink(missing_ok=True)
        record_launch(home, 'child_exit', pid=child.pid, returncode=code, healthy=healthy,
                      seconds=round(time.monotonic()-started, 3))
        if pending and not healthy:
            rollback(home, 'New version failed its startup check. Previous program restored; project data was unchanged.')
            arguments = [a for a in arguments if a != '--open']
            continue
        if code != 75:
            return code if healthy or code else 1
        arguments = [a for a in arguments if a != '--open']


if __name__ == '__main__':
    settings = read_json(Path(__file__).resolve().parent / 'settings.json')
    if not settings or not isinstance(settings.get('fallback_root'), str) or not isinstance(settings.get('home'), str):
        raise SystemExit('The stable launcher settings are missing. Start the original Start-Foundry.bat.')
    raise SystemExit(supervise(Path(settings['fallback_root']), ['--data-dir', settings['home'], *sys.argv[1:]]))
