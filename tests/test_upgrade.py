"""0.5 regressions: starter preservation, actual milestone checks, bounded repairs."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import threading
import unittest

from forge.core import Workbench, preflight, validate_plan
from forge.context import source_map, failure_feedback
from forge.runner import verify, verify_milestone
from forge.scaffolds import starter_files
from tests.fixtures import PLAN, APP, BROKEN, TEST
from tests.test_workbench import ScriptedModels, await_job

ROOT = Path(__file__).resolve().parents[1]
CONFIG = {'provider': 'ollama', 'model': 'test'}


class UpgradeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def project(self, plan, replies, starter=None):
        models = ScriptedModels([plan, *replies])
        bench = Workbench(self.root / 'projects', models)
        state = bench.create('Build a task tracker with saved tasks', CONFIG, CONFIG, starter)
        state = await_job(bench, state['id'])
        bench.approve(state['id'], state['plan'])
        return bench, bench.load(state['id']), models

    def two_task_plan(self, indexes=(0,)):
        plan = copy.deepcopy(PLAN)
        plan['tasks'] = [
            {'title': 'Create tasks', 'instructions': 'Server and create API', 'feature_indexes': [0], 'check_indexes': list(indexes)},
            {'title': 'Finish listing and tests', 'instructions': 'Complete browser and tests', 'feature_indexes': [1]},
        ]
        return plan

    def test_newest_uploaded_static_pass_is_now_rejected_without_running(self):
        data = ROOT / 'tests/fixture_data'
        result = preflight({'app.py': (data / 'notes-repaired-static-app.txt').read_text(), 'test_app.py': (data / 'notes-repaired-static-tests.txt').read_text()})
        self.assertFalse(result['passed'])
        self.assertFalse(result['executed'])
        self.assertIn('message_from_bytes', ' '.join(result['issues']))
        self.assertIn('urlopen does not accept', ' '.join(result['issues']))

    def test_starter_is_installed_only_at_approval_without_execution(self):
        models = ScriptedModels([PLAN])
        bench = Workbench(self.root, models, verifier=lambda *a: self.fail('No consent'))
        state = bench.create('Build a task tracker', CONFIG, CONFIG, 'web')
        state = await_job(bench, state['id'])
        self.assertEqual(bench.context_files(state['id']), {})
        state = bench.approve(state['id'], state['plan'])
        self.assertEqual(bench.files(state['id'])['app.py'], starter_files('web')['app.py'])
        foundation = bench.files(state['id'])['test_foundation.py']
        self.assertEqual(state['frozen_tests']['test_foundation.py'], hashlib.sha256(foundation.encode()).hexdigest())
        with self.assertRaisesRegex(ValueError, 'trusted regression'):
            bench.apply(state, {'files': {'test_foundation.py': foundation + '\n# changed'}})
        self.assertIn('Architecture and execution contract', bench.files(state['id'])['PROJECT.md'])
        self.assertIsNone(state['checks'])

    def test_legacy_projects_are_not_seeded_or_rewritten(self):
        bench, state, _ = self.project(PLAN, [])
        self.assertFalse(bench.context_files(state['id']))
        self.assertNotIn('starter_version', state)
        with self.assertRaises(ValueError):
            bench.create('Unsupported project', CONFIG, CONFIG, 'unknown-template')

    def test_milestone_prefix_runs_real_http_and_preserves_frozen_checks(self):
        bench, state, models = self.project(self.two_task_plan(), [{'files': {'app.py': APP}}, {'files': {'app.py': APP, 'test_app.py': TEST}}])
        bench.start(state['id'], 'build', {'execute': True, 'consent': True, 'runtime': 'local', 'repairs': 0})
        state = await_job(bench, state['id'])
        self.assertEqual(state['status'], 'verified', state.get('error'))
        self.assertTrue(state['milestones'][0]['behavior_verified'])
        self.assertEqual(state['milestones'][0]['checks'], 1)
        self.assertEqual(state['milestones'][0]['result']['phases'][0]['http_checks'], 3)
        self.assertEqual(json.loads(bench.files(state['id'])['CHECKS.json']), PLAN['checks'])
        self.assertIn('source_map', models.calls[1])

    def test_milestone_failure_is_repaired_before_next_task(self):
        bench, state, models = self.project(self.two_task_plan((0, 1)), [
            {'files': {'app.py': BROKEN}}, {'files': {'app.py': APP}}, {'files': {'app.py': APP, 'test_app.py': TEST}},
        ])
        bench.start(state['id'], 'build', {'execute': True, 'consent': True, 'runtime': 'local', 'repairs': 1})
        state = await_job(bench, state['id'])
        self.assertEqual(state['status'], 'verified', state.get('error'))
        self.assertEqual(state['repair_count'], 1)
        self.assertTrue(state['milestones'][0]['behavior_verified'])
        self.assertEqual(models.calls[2]['feedback']['phase'], 'acceptance')
        self.assertEqual(models.calls[3]['current_task']['title'], 'Finish listing and tests')

    def test_failed_milestone_does_not_advance_saved_progress(self):
        bench, state, models = self.project(self.two_task_plan((0, 1)), [{'files': {'app.py': BROKEN}}])
        bench.start(state['id'], 'build', {'execute': True, 'consent': True, 'runtime': 'local', 'repairs': 0})
        state = await_job(bench, state['id'])
        self.assertEqual(state['status'], 'needs_attention')
        self.assertEqual(state['next_task'], 0)
        self.assertEqual(len(models.calls), 2)
        self.assertFalse(state['checks']['passed'])

    def test_no_milestone_execution_without_consent(self):
        bench, state, _ = self.project(self.two_task_plan(), [{'files': {'app.py': APP}}, {'files': {'app.py': APP, 'test_app.py': TEST}}])
        bench.milestone_verifier = lambda *a: self.fail('Must not execute')
        bench.verifier = lambda *a: self.fail('Must not execute')
        bench.start(state['id'], 'build', {'execute': False, 'repairs': 0})
        state = await_job(bench, state['id'])
        self.assertEqual(state['status'], 'generated')
        self.assertFalse(state['milestones'][0]['behavior_verified'])

    def test_static_repairs_after_runtime_failure_share_the_cap(self):
        bench, state, _ = self.project(PLAN, [
            {'files': {'app.py': BROKEN, 'test_app.py': TEST}},
            {'files': {'app.py': APP + '\nimport cgi\n'}},
            {'files': {'app.py': APP}},
        ])
        bench.start(state['id'], 'build', {'execute': True, 'consent': True, 'runtime': 'local', 'repairs': 2})
        state = await_job(bench, state['id'])
        self.assertEqual(state['status'], 'verified', state.get('error'))
        self.assertEqual(state['repair_count'], 2)

    def test_unchanged_repair_stops_without_repeating_verification(self):
        bench, state, _ = self.project(PLAN, [{'files': {'app.py': APP, 'test_app.py': TEST}}, {'files': {'app.py': APP}}])
        calls = []
        def failed(*args):
            calls.append(1)
            return {'passed': False, 'log': 'AssertionError: missing feature', 'diagnosis': 'Missing feature', 'phases': [{'phase': 'acceptance', 'passed': False}]}
        bench.verifier = failed
        bench.start(state['id'], 'build', {'execute': True, 'consent': True, 'runtime': 'local', 'repairs': 3})
        state = await_job(bench, state['id'])
        self.assertEqual(state['status'], 'needs_attention')
        self.assertEqual(len(calls), 1)
        self.assertIn('unchanged source', state['events'][-1]['message'])

    def test_invalid_milestone_indexes_rejected_at_approval(self):
        for indexes in [[99], [True], '0']:
            plan = self.two_task_plan()
            plan['tasks'][0]['check_indexes'] = indexes
            with self.subTest(indexes=indexes), self.assertRaises(ValueError):
                validate_plan(plan)

    def test_source_map_and_feedback_keep_symbols_and_concrete_failure(self):
        mapping = source_map({'app.py': APP, 'test_app.py': TEST})
        self.assertIn('create_server', mapping[0]['symbols'])
        self.assertNotIn(APP, json.dumps(mapping))
        result = failure_feedback({'diagnosis': 'HTTP failure', 'phases': [{'phase': 'acceptance', 'passed': False, 'error': 'File "app.py", line 30\nAttributeError: bad API'}]})
        self.assertEqual(result['phase'], 'acceptance')
        self.assertIn('app.py', result['referenced_files'])
        self.assertIn('AttributeError', result['traceback_tail'])

    def test_reviewed_notes_starter_passes_real_verifier(self):
        source = self.root / 'source'
        source.mkdir()
        for name, content in starter_files('notes').items():
            (source / name).write_text(content, encoding='utf-8')
        checks = json.loads((ROOT / 'examples/notes-proposal.json').read_text())['checks']
        (source / 'CHECKS.json').write_text(json.dumps(checks))
        result = verify(source, 'local', threading.Event())
        self.assertTrue(result['passed'], result['log'])
        self.assertEqual(result['phases'][1]['tests_run'], 13)

    def test_model_insights_describe_project_results_not_rankings(self):
        bench, state, _ = self.project(PLAN, [])
        result = bench.insights()
        self.assertEqual(result['models'][0]['projects'], 1)
        self.assertEqual(result['models'][0]['verified'], 0)
        self.assertIn('not a controlled model ranking', result['explanation'])


class PreservationTests(unittest.TestCase):
    def test_external_acceptance_check_changes_stop_without_spending_repairs(self):
        with tempfile.TemporaryDirectory() as temporary:
            model = ScriptedModels([PLAN, {'files': {'app.py': APP, 'test_app.py': TEST}}])
            bench = Workbench(temporary, model)
            state = bench.create('Build a task tracker', CONFIG, CONFIG)
            state = await_job(bench, state['id'])
            bench.approve(state['id'], state['plan'])
            (bench.directory(state['id']) / 'source/CHECKS.json').write_text('[]')
            bench.start(state['id'], 'build', {'repairs': 3})
            state = await_job(bench, state['id'])
            self.assertEqual(state['status'], 'needs_attention')
            self.assertEqual(state['repair_count'], 0)
            self.assertIn('Approved acceptance checks', ' '.join(state['preflight']['issues']))
            self.assertEqual(len(model.calls), 1)

    def test_starter_checkpoint_restoration_keeps_owned_documents(self):
        with tempfile.TemporaryDirectory() as temporary:
            model = ScriptedModels([PLAN])
            bench = Workbench(temporary, model)
            state = bench.create('Build a task tracker', CONFIG, CONFIG, 'web')
            state = await_job(bench, state['id'])
            state = bench.approve(state['id'], state['plan'])
            restored = bench.restore(state['id'], state['snapshots'][0]['id'])
            self.assertEqual(json.loads(bench.files(state['id'])['CHECKS.json']), PLAN['checks'])
            self.assertEqual(restored['next_task'], 0)
