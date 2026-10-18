"""A failing local planner must not strand a reviewed standard starter."""
import copy
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from forge.core import Workbench
from forge.schemas import PLAN_SCHEMA
from tests.test_evidence import game_plan, CONFIG
from tests.test_workbench import ScriptedModels, await_job
from tests.fixtures import PLAN


class StarterRecoveryTests(unittest.TestCase):
    def test_standard_creation_uses_no_model_and_no_code(self):
        with tempfile.TemporaryDirectory() as temp:
            models = ScriptedModels([])
            bench = Workbench(Path(temp), models, verifier=lambda *_: self.fail('Must not execute'))
            state = bench.create('Use the reviewed standard Neon Dodge.', CONFIG, CONFIG, 'arcade', use_reviewed_plan=True)
            self.assertEqual(state['status'], 'proposed')
            self.assertEqual(state['plan'], game_plan())
            self.assertEqual(state['planning_stats']['attempts'], 0)
            self.assertEqual(models.calls, [])
            self.assertFalse(state['approved'])
            self.assertEqual(bench.files(state['id']), {})
            self.assertNotIn(state['id'], bench.jobs)

    def test_failed_browser_fields_recovers_same_project_without_retry(self):
        with tempfile.TemporaryDirectory() as temp:
            invalid = game_plan()
            invalid.pop('app_kind')
            invalid.pop('manual_checks')
            invalid['checks'] = invalid['checks'][:1]
            models = ScriptedModels([invalid, invalid])
            bench = Workbench(Path(temp), models)
            state = bench.create('Build Neon Dodge with localStorage.', CONFIG, CONFIG, 'arcade')
            state = await_job(bench, state['id'])
            self.assertEqual(state['status'], 'error')
            self.assertIsNone(state['plan'])
            self.assertIn('app_kind', state['error'])
            self.assertIn('manual_checks', models.calls[-1]['validation_error'])
            count = len(models.calls)
            original_idea = state['idea']
            state = bench.load_starter_plan(state['id'])
            self.assertEqual(state['status'], 'proposed')
            self.assertEqual(state['idea'], original_idea)
            self.assertIsNone(state['error'])
            self.assertIsNone(state['failed_candidate'])
            self.assertEqual(state['proposal_source']['kind'], 'reviewed_starter')
            self.assertEqual(len(models.calls), count)
            self.assertEqual(bench.files(state['id']), {})
            state = bench.approve(state['id'], state['plan'])
            self.assertIn('game.js', bench.files(state['id']))
            self.assertIsNone(state['checks'])
            with self.assertRaisesRegex(ValueError, 'unapproved'):
                bench.load_starter_plan(state['id'])

    def test_cannot_replace_change_project_or_wrong_starter(self):
        with tempfile.TemporaryDirectory() as temp:
            models = ScriptedModels([PLAN])
            bench = Workbench(Path(temp), models)
            state = bench.create('Build a basic task tracker.', CONFIG, CONFIG, 'web')
            state = await_job(bench, state['id'])
            with self.assertRaisesRegex(ValueError, 'Neon Dodge'):
                bench.load_starter_plan(state['id'])
            with self.assertRaisesRegex(ValueError, 'Neon Dodge'):
                bench.create('Use an unsupported standard plan.', CONFIG, CONFIG, 'web', use_reviewed_plan=True)
            state['starter'] = 'arcade'
            state['baseline_plan'] = PLAN
            bench.save(state)
            with self.assertRaisesRegex(ValueError, 'original project'):
                bench.load_starter_plan(state['id'])

    def test_busy_project_and_maintenance_are_protected(self):
        with tempfile.TemporaryDirectory() as temp:
            bench = Workbench(Path(temp), ScriptedModels([]))
            state = bench.create('Use the reviewed standard Neon Dodge.', CONFIG, CONFIG, 'arcade', use_reviewed_plan=True)
            state['status'] = 'planning'
            bench.save(state)
            with self.assertRaisesRegex(ValueError, 'idle'):
                bench.load_starter_plan(state['id'])
            bench.maintenance = True
            with self.assertRaisesRegex(ValueError, 'update'):
                bench.load_starter_plan(state['id'])

    def test_valid_custom_planning_stays_on_model_path(self):
        with tempfile.TemporaryDirectory() as temp:
            plan = game_plan()
            plan['title'] = 'My custom arcade'
            models = ScriptedModels([plan])
            bench = Workbench(Path(temp), models)
            state = bench.create('Customize the arcade game colors.', CONFIG, CONFIG, 'arcade')
            state = await_job(bench, state['id'])
            self.assertEqual(state['plan']['title'], 'My custom arcade')
            self.assertEqual(len(models.calls), 1)
            self.assertNotIn('proposal_source', state)
            self.assertEqual(models.calls[0]['required_plan_fields']['app_kind'], 'browser')

    def test_native_schema_requires_app_kind_without_breaking_legacy_validation(self):
        self.assertIn('app_kind', PLAN_SCHEMA['required'])
        from forge.contracts import validate_structure
        self.assertEqual(validate_structure(copy.deepcopy(PLAN)), PLAN)


if __name__ == '__main__':
    unittest.main()
