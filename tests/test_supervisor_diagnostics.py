"""Independent launcher evidence survives failures before application imports."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import signal
import socket
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

import bootstrap


class SupervisorDiagnosticsTests(unittest.TestCase):
    def test_interrupt_after_instance_publication_removes_owned_marker(self):
        from forge import server
        with tempfile.TemporaryDirectory() as temporary:
            home=Path(temporary);fake=Mock(server_port=12345)
            with patch.object(sys,'argv',['foundry','--data-dir',str(home)]), \
                 patch.object(server,'make_server',return_value=fake), \
                 patch('desktop_launcher.install_shortcut',return_value={'status':'not_supported'}), \
                 patch.object(server.ResourceSampler,'start',side_effect=KeyboardInterrupt()), \
                 patch.dict(os.environ,{'FOUNDRY_BOOT_NONCE':'fixture-owned-instance'}):
                with self.assertRaises(KeyboardInterrupt):server.main()
            self.assertFalse((home/'diagnostics/instance.json').exists())

    def test_independent_events_are_bounded_and_do_not_record_error_text(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            for index in range(50):
                bootstrap.record_launch(home, 'child_exit', returncode=index,
                                        exception_type='ValueError', message='Bearer should-never-appear')
            path = home / 'diagnostics' / 'launcher.jsonl'
            records = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual(len(records), 50)
            self.assertNotIn('should-never-appear', path.read_text())
            self.assertEqual(records[-1]['data']['returncode'], 49)
            self.assertEqual(records[-1]['origin'], 'independent_supervisor')
            self.assertEqual(len({item['id'] for item in records}), 50)
            with patch.object(bootstrap, 'MAX_LAUNCH_LOG_BYTES', 1024):
                bootstrap.record_launch(home, 'child_exit', returncode=1)
            self.assertTrue(path.with_suffix('.jsonl.1').is_file())

    def test_broken_app_records_exit_and_preserves_root(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'program'
            root.mkdir()
            (root / 'run.py').write_text('raise SystemExit(7)\n')
            home = Path(temporary) / 'home'
            code = bootstrap.supervise(root, ['--data-dir', str(home)])
            self.assertEqual(code, 7)
            records = [json.loads(line) for line in (home / 'diagnostics/launcher.jsonl').read_text().splitlines()]
            exits = [item for item in records if item['kind'] == 'child_exit']
            self.assertEqual(exits[-1]['data']['returncode'], 7)
            self.assertFalse(exits[-1]['data']['healthy'])
            self.assertTrue((root / 'run.py').exists())

    def test_supervisor_import_has_no_application_import(self):
        result = subprocess.run([sys.executable, '-c',
            "import bootstrap,sys; assert not any(k=='forge' or k.startswith('forge.') for k in sys.modules)"],
            cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_unfinished_previous_session_is_evidence_not_crash_claim(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            path = home / 'diagnostics'
            path.mkdir()
            (path / 'launcher-session.json').write_text(json.dumps({'status':'running', 'pid':-1}))
            root = home / 'program'
            root.mkdir()
            (root / 'run.py').write_text('raise SystemExit(2)\n')
            bootstrap.supervise(root, ['--data-dir', str(home)])
            records = [json.loads(line) for line in (path / 'launcher.jsonl').read_text().splitlines()]
            self.assertIn('previous_session_unfinished', [item['kind'] for item in records])

    def test_startup_timeout_is_recorded_without_marking_child_healthy(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'program'
            root.mkdir()
            (root / 'run.py').write_text('import time\ntime.sleep(60)\n')
            home = Path(temporary) / 'home'
            with patch.object(bootstrap, 'STARTUP_HEALTH_SECONDS', .1):
                code = bootstrap.supervise(root, ['--data-dir', str(home)])
            self.assertNotEqual(code, 0)
            records = [json.loads(line) for line in (home / 'diagnostics/launcher.jsonl').read_text().splitlines()]
            self.assertIn('startup_health_timeout', [item['kind'] for item in records])
            self.assertNotIn('child_healthy', [item['kind'] for item in records])

    def test_run_wrapper_captures_pre_import_failure_without_exception_message(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temporary:
            program = Path(temporary) / 'program'
            program.mkdir()
            for name in ('run.py', 'bootstrap.py'):
                (program / name).write_bytes((root / name).read_bytes())
            home = Path(temporary) / 'home'
            result = subprocess.run([sys.executable, str(program / 'run.py'), '--server', '--data-dir', str(home)],
                                    cwd=program, capture_output=True, text=True, timeout=10)
            self.assertNotEqual(result.returncode, 0)
            records = [json.loads(line) for line in (home / 'diagnostics/launcher.jsonl').read_text().splitlines()]
            capture = records[-1]
            self.assertEqual(capture['kind'], 'application_exception')
            self.assertEqual(capture['data']['exception_type'], 'ModuleNotFoundError')
            self.assertEqual(capture['data']['location'], 'run.py')
            self.assertNotIn('No module named', json.dumps(capture))

    def test_real_launcher_health_duplicate_open_and_clean_stop(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0))
                port = sock.getsockname()[1]
            arguments = ['--data-dir', str(home), '--port', str(port)]
            flags = {'start_new_session': True} if os.name != 'nt' else {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP}
            process = subprocess.Popen([sys.executable, str(root / 'run.py'), *arguments],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **flags)
            try:
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    path = home / 'diagnostics/launcher.jsonl'
                    if bootstrap.instance_url(home) and path.is_file() and 'child_healthy' in path.read_text():
                        break
                    if process.poll() is not None:
                        self.fail('Launcher exited before publishing a health-verified instance')
                    time.sleep(.05)
                else:
                    self.fail('No health-verified instance was published')
                with patch('bootstrap.webbrowser.open') as opened, \
                     patch('bootstrap.subprocess.Popen', side_effect=AssertionError('No second process allowed')):
                    self.assertEqual(bootstrap.supervise(root, [*arguments, '--open']), 0)
                    opened.assert_called_once_with(f'http://127.0.0.1:{port}')
            finally:
                if process.poll() is None:
                    if os.name == 'nt':
                        process.send_signal(signal.CTRL_BREAK_EVENT)
                    else:
                        os.killpg(process.pid, signal.SIGINT)
                    try:
                        process.wait(timeout=12)
                    except subprocess.TimeoutExpired:
                        if os.name == 'nt':
                            subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True, timeout=10)
                        else:
                            os.killpg(process.pid, signal.SIGKILL)
                        process.wait(timeout=5)
            self.assertEqual(process.returncode, 0)
            records = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertIn('supervisor_stopped', [item['kind'] for item in records])
            self.assertFalse((home / 'diagnostics/instance.json').exists())

    def test_windows_console_interrupt_waits_before_forced_termination(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            child = Mock(pid=123)
            child.poll.side_effect = [KeyboardInterrupt(), None]
            child.wait.return_value = 0
            # Replace only this module's os reference. Mutating os.name globally
            # would change pathlib behavior on the Linux test host.
            windows_os = SimpleNamespace(name='nt', environ=os.environ)
            with patch('bootstrap.os', windows_os), \
                 patch('bootstrap.selected_program', return_value=home), \
                 patch('bootstrap.read_json', return_value=None), \
                 patch('bootstrap.record_launch'), \
                 patch('bootstrap.subprocess.Popen', return_value=child):
                self.assertEqual(bootstrap._supervise_programs(home, home, []), 0)
            child.wait.assert_called_once_with(timeout=8)
            child.terminate.assert_not_called()
            child.kill.assert_not_called()

    def test_invalid_installed_pointer_uses_original_without_rewriting_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / 'home'
            root = Path(temporary) / 'program'
            root.mkdir()
            (root / 'run.py').write_text('raise SystemExit(7)\n')
            pointer = home / 'updates/current.json'
            pointer.parent.mkdir(parents=True)
            original = json.dumps({'version': '../invalid'})
            pointer.write_text(original)
            self.assertEqual(bootstrap.supervise(root, ['--data-dir', str(home)]), 7)
            self.assertEqual(pointer.read_text(), original)
            records = [json.loads(line) for line in (home / 'diagnostics/launcher.jsonl').read_text().splitlines()]
            self.assertIn('selected_program_fallback', [item['kind'] for item in records])

    def test_installed_version_starts_when_original_download_was_moved(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / 'home'
            candidate = home / 'updates/versions/0.31.0'
            candidate.mkdir(parents=True)
            (candidate / 'run.py').write_text('# installed program\n')
            (home / 'updates/current.json').write_text(json.dumps({'version':'0.31.0'}))
            self.assertEqual(bootstrap.selected_program(Path(temporary) / 'missing-download', home), candidate)


if __name__ == '__main__':
    unittest.main()
