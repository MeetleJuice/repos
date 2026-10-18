"""Regression cases from the real browser-game planning failure."""
import copy
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from forge.contracts import review_plan, validate_structure
from forge.core import Workbench
from forge.context import fingerprint
from forge.runner import require_browser_runtime, verify
from forge.scaffolds import starter_files
from tests.fixtures import PLAN, APP, TEST
from tests.test_workbench import ScriptedModels, await_job

DATA = Path(__file__).resolve().parents[1] / 'forge' / 'starters' / 'arcade'
CONFIG = {'provider': 'ollama', 'model': 'fixture'}


def game_plan():
    return json.loads((DATA / 'proposal.json').read_text())


class EvidenceTests(unittest.TestCase):
    def test_browser_only_app_does_not_need_fake_api(self):
        plan = game_plan()
        plan['checks'] = plan['checks'][:1]
        self.assertTrue(review_plan(plan).passed)
        self.assertEqual(validate_structure(plan), plan)

    def test_uncovered_feature_cannot_hide_behind_page(self):
        plan = game_plan()
        plan['manual_checks'] = []
        self.assertFalse(review_plan(plan).passed)

    def test_static_asset_cannot_masquerade_as_server_behavior(self):
        plan = game_plan()
        plan['app_kind'] = 'server'
        self.assertFalse(review_plan(plan).passed)

    def test_tampered_manual_document_cannot_get_verified(self):
        with tempfile.TemporaryDirectory() as temp:
            bench, ident, _ = self.make_game(Path(temp))
            state = bench.load(ident)
            (bench.directory(ident) / 'source' / 'MANUAL-CHECKS.md').write_text('All good!')
            self.assertIsNone(bench._inspect_and_repair(state, threading.Event(), 0))
            self.assertEqual(state['status'], 'needs_attention')
            self.assertIn('manual checklist', state['events'][-1]['message'])

    def test_server_still_needs_behavior(self):
        plan = game_plan()
        plan['app_kind'] = 'server'
        plan['checks'] = plan['checks'][:1]
        self.assertFalse(review_plan(plan).passed)

    def test_invalid_manual_checks_rejected(self):
        for field, value in [('steps', []), ('steps', ['']), ('expected', ''), ('feature_indexes', [99]), ('feature_indexes', [True])]:
            with self.subTest(field=field, value=value):
                plan = game_plan()
                plan['manual_checks'][0][field] = value
                self.assertFalse(review_plan(plan).passed)

    def test_browser_steps_are_declarative_and_bounded(self):
        for steps in [[{'action': 'evaluate', 'value': 'fetch("https://example.com")'}], [{'action': 'wait', 'ms': 100000}], [{'action': 'click', 'selector': '#start'}], [{'action': 'expect_visible', 'selector': '#start', 'url': 'http://evil'}]]:
            plan = game_plan()
            plan['browser_checks'] = [{'name': 'Bad automation', 'steps': steps, 'feature_indexes': [1]}]
            self.assertFalse(review_plan(plan).passed)

    def test_real_browser_plan_valid(self):
        plan = game_plan()
        plan['browser_checks'] = [{'name': 'Start and render', 'feature_indexes': [1, 2], 'steps': [{'action': 'click', 'selector': '#start'}, {'action': 'expect_text', 'selector': '#state', 'value': 'Playing'}, {'action': 'expect_canvas_changes', 'selector': '#game', 'ms': 300}]}]
        self.assertTrue(review_plan(plan).passed)

    def test_get_before_create_caught(self):
        plan = copy.deepcopy(PLAN)
        plan['checks'] = [plan['checks'][1], plan['checks'][0]]
        plan['checks'][0].pop('contains')
        plan['checks'][0]['json_contains'] = [{'title': 'Buy milk'}]
        review = review_plan(plan)
        self.assertIn('read_before_create', [f.code for f in review.findings])

    def test_browser_dependency_not_silently_skipped(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'BROWSER-CHECKS.json').write_text('[{}]')
            with self.assertRaisesRegex(ValueError, 'cannot silently skip'):
                require_browser_runtime(root, 'docker')
            with patch('forge.browser_runner.diagnostics', return_value={'available': False, 'detail': 'Install optional Chromium'}):
                with self.assertRaisesRegex(ValueError, 'Chromium'):
                    require_browser_runtime(root, 'local')

    def make_game(self, root):
        plan = game_plan()
        responses = [plan, {'files': {'game.js': starter_files('arcade')['game.js']}}, {'files': {'test_app.py': starter_files('arcade')['test_app.py']}}]
        models = ScriptedModels(responses)
        bench = Workbench(root, models)
        state = bench.create('Build Neon Dodge with localStorage and manual gameplay checks.', CONFIG, CONFIG, 'arcade')
        state = await_job(bench, state['id'])
        self.assertEqual(state['status'], 'proposed', state.get('error'))
        bench.approve(state['id'], state['plan'])
        return bench, state['id'], models

    def test_game_full_pipeline_manual_acceptance_and_invalidation(self):
        with tempfile.TemporaryDirectory() as temp:
            bench, ident, models = self.make_game(Path(temp))
            with self.assertRaisesRegex(ValueError, 'automated'):
                bench.record_manual(ident, [True] * 4)
            bench.start(ident, 'build', {'execute': True, 'consent': True, 'runtime': 'local', 'repairs': 0})
            state = await_job(bench, ident)
            self.assertEqual(state['status'], 'review_required', state.get('error') or state.get('checks'))
            self.assertEqual(state.get('manual_results'), {})
            self.assertTrue(state['checks']['passed'])
            self.assertIn('not automated', bench.files(ident)['MANUAL-CHECKS.md'])
            state = bench.record_manual(ident, [True, False, True, True])
            self.assertEqual(state['status'], 'needs_attention')
            state = bench.record_manual(ident, [True] * 4)
            self.assertEqual(state['status'], 'verified')
            self.assertEqual(state['manual_results']['evidence'], 'User-reported observations, not automated tests.')
            files = bench.context_files(ident)
            path = bench.directory(ident) / 'source' / 'game.js'
            path.write_text(files['game.js'] + '\n// external edit')
            with self.assertRaisesRegex(ValueError, 'Source changed'):
                bench.record_manual(ident, [True] * 4)
            self.assertEqual(len(models.calls), 3)

    def test_approved_browser_checks_are_protected(self):
        with tempfile.TemporaryDirectory() as temp:
            bench, ident, _ = self.make_game(Path(temp))
            state = bench.load(ident)
            with self.assertRaisesRegex(ValueError, 'frozen'):
                bench.apply(state, {'files': {'BROWSER-CHECKS.json': '[]'}})
            with self.assertRaisesRegex(ValueError, 'frozen'):
                bench.apply(state, {'files': {'MANUAL-CHECKS.md': 'All passed'}})

    def test_manual_validation_and_baseline_preservation(self):
        plan = game_plan()
        candidate = copy.deepcopy(plan)
        candidate['manual_checks'] = []
        revision = Workbench.revision_plan({'baseline_plan': plan}, candidate)
        self.assertEqual(revision['manual_checks'], plan['manual_checks'])

    def test_format_recovery_rejects_without_partial_write(self):
        with tempfile.TemporaryDirectory() as temp:
            models = ScriptedModels([PLAN, {'files': {'app.py': APP, 'CHECKS.json': '[]'}}, {'files': {'app.py': APP, 'test_app.py': TEST}}])
            bench = Workbench(Path(temp), models)
            state = bench.create('Build a simple task tracker.', CONFIG, CONFIG)
            state = await_job(bench, state['id'])
            state = bench.approve(state['id'], state['plan'])
            source = bench.directory(state['id']) / 'source'
            bench.generate_and_apply(state, {'files': {}}, threading.Event())
            self.assertEqual(json.loads((source / 'CHECKS.json').read_text()), PLAN['checks'])
            self.assertEqual(state['generation_stats']['rejected_responses'], 1)
            self.assertIn('response_validation_error', models.calls[-1])

    def test_malformed_json_gets_one_focused_correction(self):
        from forge.models import ModelError
        with tempfile.TemporaryDirectory() as temp:
            models = ScriptedModels([PLAN, ModelError('Invalid JSON', 'format'), {'files': {'app.py': APP, 'test_app.py': TEST}}])
            bench = Workbench(Path(temp), models)
            state = bench.create('Build a simple task tracker.', CONFIG, CONFIG)
            state = await_job(bench, state['id'])
            state = bench.approve(state['id'], state['plan'])
            bench.generate_and_apply(state, {}, threading.Event())
            self.assertEqual(state['generation_stats']['rejected_responses'], 1)
            self.assertEqual(models.calls[-1]['response_validation_error'], 'Invalid JSON')
            self.assertEqual(state['model_calls'][-2]['error_category'], 'format')

    def test_auth_failure_is_not_retried_as_format_correction(self):
        from forge.models import ModelError
        with tempfile.TemporaryDirectory() as temp:
            models = ScriptedModels([PLAN, ModelError('Unauthorized', 'auth')])
            bench = Workbench(Path(temp), models)
            state = bench.create('Build a simple task tracker.', CONFIG, CONFIG)
            state = await_job(bench, state['id'])
            state = bench.approve(state['id'], state['plan'])
            with self.assertRaises(ModelError):
                bench.generate_and_apply(state, {}, threading.Event())
            self.assertEqual(len(models.calls), 2)

    def test_repeated_bad_response_stops_after_one_correction(self):
        with tempfile.TemporaryDirectory() as temp:
            models = ScriptedModels([PLAN, {'files': {}}, {'files': {}}])
            bench = Workbench(Path(temp), models)
            state = bench.create('Build a simple task tracker.', CONFIG, CONFIG)
            state = await_job(bench, state['id'])
            state = bench.approve(state['id'], state['plan'])
            with self.assertRaises(ValueError):
                bench.generate_and_apply(state, {}, threading.Event())
            self.assertEqual(len(models.calls), 3)
            self.assertFalse((bench.directory(state['id']) / 'source' / 'app.py').exists())

    def test_actual_uploaded_neon_proposal_exposes_order_bug(self):
        original = json.loads((DATA.parents[2] / 'tests' / 'fixture_data' / 'neon-plan-v06.json').read_text())
        self.assertIn('read_before_create', [f.code for f in review_plan(original).findings])

    def test_manual_results_reject_incomplete_and_non_boolean_values(self):
        with tempfile.TemporaryDirectory() as temp:
            bench, ident, _ = self.make_game(Path(temp))
            state = bench.load(ident)
            state.update(checks={'passed': True}, verification_fingerprint=fingerprint(bench.context_files(ident)))
            bench.save(state)
            for results in [[], [True], ['yes'] * 4, [1] * 4, None]:
                with self.subTest(results=results), self.assertRaisesRegex(ValueError, 'explicit pass/fail'):
                    bench.record_manual(ident, results)

    def test_restore_clears_manual_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            bench, ident, _ = self.make_game(Path(temp))
            state = bench.load(ident)
            state.update(manual_results={'results': [True] * 4}, verification_fingerprint='stale', checks={'passed': True}, status='verified')
            bench.save(state)
            restored = bench.restore(ident, state['snapshots'][0]['id'])
            self.assertEqual(restored['manual_results'], {})
            self.assertIsNone(restored['verification_fingerprint'])

    def test_invalid_revision_labels_previous_proposal(self):
        with tempfile.TemporaryDirectory() as temp:
            invalid = game_plan()
            invalid['manual_checks'] = []
            invalid['checks'] = invalid['checks'][:1]
            models = ScriptedModels([PLAN, invalid, invalid])
            bench = Workbench(Path(temp), models)
            state = bench.create('Build a small app with useful behavior.', CONFIG, CONFIG)
            state = await_job(bench, state['id'])
            bench.start(state['id'], 'plan', {'revision': 'Make a browser game with manual gameplay checks.'})
            state = await_job(bench, state['id'])
            self.assertEqual(state['status'], 'error')
            self.assertTrue(state['plan_is_previous'])
            self.assertEqual(state['plan'], PLAN)
            self.assertEqual(state['failed_candidate'], invalid)
            self.assertIn('browser game', state['last_revision'])

    def test_arcade_starter_static_and_server_checks(self):
        from forge.inspection import inspect_files
        self.assertTrue(inspect_files(starter_files('arcade'))['passed'])


if __name__ == '__main__':
    unittest.main()
