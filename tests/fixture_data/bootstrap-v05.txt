"""Stable launcher supervising versioned Foundry servers and failed-start rollback.

Uses only the standard library and does not import the installed application.
The original downloaded folder always remains a fallback.
"""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import urllib.request
import uuid


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
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2), encoding='utf-8')
    os.replace(temporary, path)


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
        text = (Path(root) / 'forge' / '__init__.py').read_text(encoding='utf-8')
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
    return True


def supervise(root, arguments):
    root = Path(root).resolve()
    home = home_for(root, arguments)
    # Managed children inherit the original stable data location and settings fallback.
    env = dict(os.environ, FOUNDRY_HOME=str(home), FOUNDRY_LAUNCH_ROOT=str(root), FOUNDRY_SUPERVISED='1')
    while True:
        try:
            program = selected_program(root, home)
        except ValueError as exc:
            if rollback(home, str(exc)):
                continue
            print(exc, file=sys.stderr)
            return 1
        pending = read_json(home / 'updates' / 'pending.json')
        nonce = uuid.uuid4().hex
        env['FOUNDRY_BOOT_NONCE'] = nonce
        ready = home / 'updates' / ('ready-' + nonce + '.json')
        env['FOUNDRY_READY_FILE'] = str(ready)
        child = subprocess.Popen([sys.executable, str(program / 'run.py'), '--server', *arguments], cwd=program, env=env)
        healthy = not bool(pending)
        deadline = time.monotonic() + 25
        try:
            while child.poll() is None:
                if not healthy:
                    report = read_json(ready)
                    if report:
                        try:
                            with urllib.request.urlopen(f"http://127.0.0.1:{report['port']}/health", timeout=1) as response:
                                health = json.load(response)
                            healthy = health.get('boot') == nonce and health.get('version') == pending['version'] and health.get('status') == 'ok'
                        except (OSError, ValueError, KeyError):
                            pass
                    if healthy:
                        write_json(home / 'updates' / 'last-result.json', {'status': 'updated', 'time': time.time(), 'message': 'Update started successfully.', 'version': pending['version'], 'backup': pending.get('backup')})
                        (home / 'updates' / 'pending.json').unlink(missing_ok=True)
                    elif time.monotonic() > deadline:
                        child.terminate()
                        try:
                            child.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            child.kill()
                        break
                time.sleep(0.2)
            code = child.wait()
        except KeyboardInterrupt:
            # Console Ctrl+C also reaches the child. POSIX tests may signal only us.
            if child.poll() is None:
                if os.name != 'nt':
                    child.send_signal(signal.SIGINT)
                else:
                    child.terminate()
            try:
                child.wait(timeout=8)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
            return 0
        finally:
            ready.unlink(missing_ok=True)
        if pending and not healthy:
            rollback(home, 'New version failed its startup check. Previous program restored; project data was unchanged.')
            arguments = [a for a in arguments if a != '--open']
            continue
        if code != 75:
            return code
        arguments = [a for a in arguments if a != '--open']
