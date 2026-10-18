"""Windows WinError 32 regression: leave a phase directory before deleting it."""
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from forge import harness
from forge.core import Workbench
from forge.runner import verify
from tests.fixtures import PLAN, APP, TEST
from tests.test_workbench import ScriptedModels, await_job

REAL_TEMP = tempfile.TemporaryDirectory


class WindowsLikeDirectory:
    """Enforce the real Windows cwd deletion rule even on a Linux test runner."""
    created = []

    def __init__(self, **kwargs):
        self.inner = REAL_TEMP(**kwargs)
        self.name = self.inner.name
        self.created.append(Path(self.name))

    def __enter__(self):
        return self.name

    def __exit__(self, *_args):
        self.cleanup()

    def cleanup(self):
        if Path.cwd().resolve().is_relative_to(Path(self.name).resolve()):
            raise PermissionError('[WinError 32] Cannot remove the current working directory')
        self.inner.cleanup()


class WorkspaceCleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp = REAL_TEMP()
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        WindowsLikeDirectory.created = []

    def tearDown(self):
        self.temp.cleanup()

    def test_every_phase_restores_cwd_before_windows_cleanup(self):
        previous, imports = Path.cwd(), sys.path[:]
        for name, target in [('acceptance', 'acceptance'), ('tests', 'generated_tests'), ('launch', 'launch')]:
            with self.subTest(phase=name), patch.object(harness.tempfile, 'TemporaryDirectory', WindowsLikeDirectory), patch.object(harness, target, return_value={'executed': True}):
                result = harness.phase(name, self.source)
                self.assertTrue(result['passed'])
                self.assertEqual(Path.cwd(), previous)
                self.assertEqual(sys.path, imports)
        self.assertTrue(WindowsLikeDirectory.created)
        self.assertTrue(all(not p.exists() for p in WindowsLikeDirectory.created))

    def test_application_failure_restores_state_and_still_fails(self):
        previous, imports = Path.cwd(), sys.path[:]
        with patch.object(harness.tempfile, 'TemporaryDirectory', WindowsLikeDirectory), patch.object(harness, 'acceptance', side_effect=AssertionError('actual app failure')):
            with self.assertRaisesRegex(AssertionError, 'actual app failure'):
                harness.phase('acceptance', self.source)
        self.assertEqual(Path.cwd(), previous)
        self.assertEqual(sys.path, imports)
        self.assertTrue(all(not p.exists() for p in WindowsLikeDirectory.created))

    def test_generated_test_cwd_and_import_changes_are_restored(self):
        previous, imports = Path.cwd(), sys.path[:]
        def action(root):
            nested = root / 'nested'; nested.mkdir(); os.chdir(nested)
            sys.path.append('temporary-generated-import-path')
            return {'tests_run': 1}
        with patch.object(harness.tempfile, 'TemporaryDirectory', WindowsLikeDirectory), patch.object(harness, 'generated_tests', side_effect=action):
            harness.phase('tests', self.source)
        self.assertEqual(Path.cwd(), previous)
        self.assertEqual(sys.path, imports)

    def test_cleanup_errors_are_explicit_environment_failures(self):
        class BusyDirectory(WindowsLikeDirectory):
            def cleanup(self):
                super().cleanup()
                raise PermissionError('[WinError 32] Another process still has a handle')
        with patch.object(harness.tempfile, 'TemporaryDirectory', BusyDirectory), patch.object(harness, 'acceptance', return_value={}):
            with self.assertRaisesRegex(harness.PhaseInfrastructureError, 'workspace cleanup failed'):
                harness.phase('acceptance', self.source)

    def test_workspace_creation_failure_is_environment_error(self):
        with patch.object(harness.tempfile, 'TemporaryDirectory', side_effect=OSError('disk unavailable')):
            with self.assertRaisesRegex(harness.PhaseInfrastructureError, 'could not be created'):
                harness.phase('acceptance', self.source)

    def test_real_phase_process_preserves_infrastructure_report(self):
        # Missing source fails before loading app code; exercise both process/report layers.
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = harness.run_phase('acceptance', self.root / 'missing', 5)
        self.assertFalse(result['passed'])
        self.assertEqual(result['failure_kind'], 'environment')
        self.assertIn('could not be prepared', result['error'])
        self.assertIn('workspace', harness.diagnose(result))
        self.assertNotIn('asset is missing', harness.diagnose(result))

    def test_successful_asset_lines_do_not_override_real_failure(self):
        diagnosis = harness.diagnose({'phase': 'acceptance', 'error': 'PASS: Referenced asset /game.js\nPermissionError: [WinError 32] cleanup failure', 'failure_kind': 'environment'})
        self.assertIn('verification workspace', diagnosis)
        self.assertNotIn('asset is missing', diagnosis)
        actual = harness.diagnose({'phase': 'acceptance', 'error': 'AssertionError: Referenced asset /missing.js: expected HTTP 200, got 404'})
        self.assertIn('asset is missing', actual)

    def test_local_runner_preserves_environment_category(self):
        from forge.runner import _execute
        script = self.root / 'infrastructure_report.py'
        report = {'result': 'failed', 'failure_kind': 'environment', 'diagnosis': 'Verifier workspace cleanup failed', 'phases': [{'phase': 'acceptance', 'passed': False, 'failure_kind': 'environment'}]}
        script.write_text('import json\nprint(' + repr(json.dumps(report)) + ')\nraise SystemExit(1)\n')
        result = _execute(self.source, 'local', threading.Event(), 5, harness=script)
        self.assertFalse(result['passed'])
        self.assertEqual(result['failure_kind'], 'environment')

    def test_main_emits_structured_cleanup_failure_and_nonzero_exit(self):
        output = io.StringIO()
        with patch.object(sys, 'argv', ['harness.py', str(self.source), '--phase', 'acceptance']), patch.object(harness, 'phase', side_effect=harness.PhaseInfrastructureError('Verifier workspace cleanup failed')), contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
            code = harness.main()
        self.assertEqual(code, 1)
        report = json.loads(output.getvalue().split(harness.MARKER)[-1])
        self.assertFalse(report['passed'])
        self.assertEqual(report['failure_kind'], 'environment')

    def test_cleanup_environment_failure_never_requests_app_repair(self):
        models = ScriptedModels([PLAN, {'files': {'app.py': APP, 'test_app.py': TEST}}])
        failure = {'passed': False, 'failure_kind': 'environment', 'diagnosis': 'Verifier workspace cleanup failed', 'log': 'WinError 32', 'phases': [{'phase': 'acceptance', 'passed': False, 'failure_kind': 'environment'}]}
        bench = Workbench(self.root / 'projects', models, verifier=lambda *_: failure)
        config = {'provider': 'ollama', 'model': 'test'}
        state = bench.create('Build a small task tracker.', config, config)
        state = await_job(bench, state['id'])
        bench.approve(state['id'], state['plan'])
        bench.start(state['id'], 'build', {'execute': True, 'consent': True, 'runtime': 'local', 'repairs': 2})
        state = await_job(bench, state['id'])
        self.assertEqual(state['status'], 'needs_attention')
        self.assertEqual(state['repair_count'], 0)
        self.assertEqual(len(models.calls), 2)
        self.assertIn('application code was not sent for repair', state['events'][-1]['message'])


if __name__ == '__main__':
    unittest.main()
