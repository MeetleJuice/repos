"""Controller reliability regressions; no live providers or repair-quality claims."""
import json
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from forge import harness
from forge.core import Workbench
from forge.models import ModelError
from forge.prompts import CODE
from tests.fixtures import APP, TEST, PLAN
from tests.test_cloud import state_for


class CompletionProcessTests(unittest.TestCase):
    def test_nested_tests_must_be_discoverable(self):
        from forge.inspection import inspect_files
        files = {'app.py':APP, 'tests/test_app.py':TEST}
        report = inspect_files(files)
        self.assertFalse(report['passed'])
        self.assertTrue(any('discovery' in issue for issue in report['issues']))
        files['tests/__init__.py'] = ''
        self.assertTrue(inspect_files(files)['passed'])

    def test_frozen_completion_fixture(self):
        path = Path(__file__).parent/'fixture_data/completion-process-v1.json'
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), '211c250505291c37288837021c0712b261ed5eb63bce34a05b3a1597d95a1312')
        manifest = json.loads(path.with_name('frozen-regressions-v3.json').read_text())
        self.assertEqual(manifest['sets'][-1]['sha256'], hashlib.sha256(path.read_bytes()).hexdigest())

    def test_worker_exits_before_database_workspace_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            # Deliberately retain an open native SQLite connection in app globals.
            # On Windows this file cannot be deleted until the worker exits.
            root.joinpath('CHECKS.json').write_text(json.dumps(PLAN['checks']))
            root.joinpath('app.py').write_text(APP + '\nleaked_connection = sqlite3.connect("leaked.db")\n')
            report = harness.run_phase('acceptance', root, 15)
            self.assertTrue(report['passed'], report)
            self.assertEqual(report['workspace_cleanup'], 'passed')
            self.assertNotIn('app', sys.modules)

    def test_full_real_verification_reaches_tests_and_launch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            root.joinpath('CHECKS.json').write_text(json.dumps(PLAN['checks']))
            root.joinpath('app.py').write_text(APP)
            root.joinpath('test_app.py').write_text(TEST)
            result = subprocess.run([sys.executable, '-B', str(Path(harness.__file__).resolve()), str(root)], capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = json.loads(result.stdout.strip().splitlines()[-1])
            self.assertEqual(report['result'], 'passed')
            self.assertEqual([p['phase'] for p in report['phases']], ['acceptance', 'tests', 'launch'])
            self.assertGreater(report['tests_run'], 0)
            self.assertTrue(all(p['workspace_cleanup'] == 'passed' for p in report['phases']))
            self.assertFalse(root.joinpath('tasks.db').exists())

    def test_persistent_cleanup_failure_keeps_behavior_evidence(self):
        real = tempfile.TemporaryDirectory
        calls = []
        class BusyDirectory(real):
            def cleanup(self):
                calls.append(1)
                super().cleanup()
                raise PermissionError('simulated Windows locked handle')
        with tempfile.TemporaryDirectory() as directory, patch.object(harness.tempfile, 'TemporaryDirectory', BusyDirectory), patch.object(harness, '_run_prepared_phase', return_value={'phase':'acceptance','passed':True,'http_checks':11}):
            report = harness.run_phase('acceptance', Path(directory), 3)
        self.assertEqual(len(calls), 3)
        self.assertFalse(report['passed'])
        self.assertTrue(report['behavior_passed'])
        self.assertEqual(report['http_checks'], 11)
        self.assertEqual(report['failure_kind'], 'environment')

    def test_transient_cleanup_retries_without_rerunning_app(self):
        real = tempfile.TemporaryDirectory
        calls = []
        class OnceBusy(real):
            def cleanup(self):
                calls.append(1)
                if len(calls) == 1: raise PermissionError('transient lock')
                super().cleanup()
        with tempfile.TemporaryDirectory() as directory, patch.object(harness.tempfile, 'TemporaryDirectory', OnceBusy), patch.object(harness, '_run_prepared_phase', return_value={'phase':'acceptance','passed':True}) as worker:
            report = harness.run_phase('acceptance', Path(directory), 3)
        self.assertTrue(report['passed'])
        self.assertEqual(worker.call_count, 1)
        self.assertEqual(len(calls), 2)

    def route(self, responses):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'GEMINI_API_KEY':'fixture'}):
            bench = Workbench(Path(directory)/'projects')
            state = state_for(bench)
            state['coder'] = {'provider':'gemini','model':'gemini-3.8-flash','options':{'num_predict':8192},'fallbacks':[{'provider':'openrouter','model':'openrouter/free'}]}
            calls = []
            def request(url, payload, headers, timeout):
                calls.append((url,payload))
                text, reason = responses.pop(0)
                return {'candidates':[{'finishReason':reason,'content':{'parts':[{'text':text}]}}], 'usageMetadata':{'candidatesTokenCount':123,'thoughtsTokenCount':32}}
            with patch('forge.models.request_json', side_effect=request):
                try: result = bench.call_model(state, 'coder', CODE, json.dumps({'task':'Implement health check','files':{}}), threading.Event())
                except ModelError as exc: result = exc
            return result, state, calls

    def test_builder_continuation_reserves_reasoning_and_keeps_complete_json(self):
        fixture = json.loads((Path(__file__).parent/'fixture_data/completion-process-v1.json').read_text())
        expected = {'files':fixture['expected_files'], 'summary':'Complete app'}
        result, state, calls = self.route([(r['text'],r['finish_reason']) for r in fixture['builder_responses']])
        self.assertEqual(result, expected)
        self.assertEqual([r['recovery_path'] for r in state['model_calls']], ['initial','continuation'])
        self.assertEqual(state['model_calls'][0]['failure_class'], 'truncated_output')
        config = calls[0][1]['generationConfig']
        self.assertEqual(config['maxOutputTokens'], 9216)
        self.assertEqual(config['thinkingConfig'], {'thinkingBudget':1024})

    def test_builder_bad_suffix_gets_one_fresh_short_response(self):
        expected = {'files':{'app.py':APP}}
        result, state, calls = self.route([('{"files":','MAX_TOKENS'),('invalid','STOP'),(json.dumps(expected),'STOP')])
        self.assertEqual(result, expected)
        self.assertEqual([r['recovery_path'] for r in state['model_calls']], ['initial','continuation','shortening'])
        self.assertIn('exact edits', calls[-1][1]['contents'][-1]['parts'][0]['text'])

    def test_builder_exhaustion_never_downgrades_output_capacity(self):
        result, state, calls = self.route([('{','MAX_TOKENS')]*3)
        self.assertIsInstance(result, ModelError)
        self.assertEqual(result.category, 'truncated_output')
        self.assertEqual(len(calls), 3)
        self.assertTrue(all(r['provider'] == 'gemini' for r in state['model_calls']))

    def test_truncated_builder_completes_real_approved_project(self):
        from tests.test_workbench import await_job
        expected = {'files':{'app.py':APP, 'test_app.py':TEST}}
        text = json.dumps(expected); split = len(text)//2
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'GEMINI_API_KEY':'fixture'}):
            bench = Workbench(Path(directory)/'projects')
            config = {'provider':'gemini','model':'gemini-3.8-flash','options':{'num_predict':8192}}
            responses = [(json.dumps(PLAN),'STOP'), (text[:split],'MAX_TOKENS'), (text[split:],'STOP')]
            def request(url, payload, headers, timeout):
                # The partial response has not replaced any source file.
                if len(responses) == 1:
                    self.assertNotIn('app.py', bench.files(state['id']))
                content, reason = responses.pop(0)
                return {'candidates':[{'finishReason':reason,'content':{'parts':[{'text':content}]}}]}
            with patch('forge.models.request_json', side_effect=request):
                state = bench.create('Build a task tracker',config,config,cloud_consent=True)
                state = await_job(bench,state['id'])
                self.assertEqual(state['status'],'proposed',state.get('error'))
                bench.approve(state['id'],state['plan'])
                approved = bench.files(state['id'])['CHECKS.json']
                bench.start(state['id'],'build',{'execute':True,'consent':True,'runtime':'local','repairs':0,'cloud_consent':True})
                state = await_job(bench,state['id'])
            self.assertEqual(state['status'],'verified',state.get('error'))
            self.assertEqual(state['repair_count'],0)
            self.assertEqual(state['next_task'],1)
            self.assertEqual(bench.files(state['id'])['CHECKS.json'],approved)
            self.assertTrue(all(p['workspace_cleanup']=='passed' for p in state['checks']['phases']))
            self.assertEqual([r['recovery_path'] for r in state['model_calls']],['initial','initial','continuation'])
