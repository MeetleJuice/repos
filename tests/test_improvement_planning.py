"""Regression: an approved feature list is not proof the copied source implements it."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from forge.context import planning_context
from forge.core import Workbench
from tests.test_evidence import CONFIG
from tests.test_workbench import ScriptedModels, await_job

ROOT = Path(__file__).resolve().parents[1]
BASE = json.loads((ROOT / 'tests/fixture_data/shield-repeated-plan.json').read_text())
REPAIR = json.loads((ROOT / 'docs/proposals/Neon-Dodge-Shield-Repair.json').read_text())


class ImprovementPlanningTests(unittest.TestCase):
    def test_source_context_is_relevant_bounded_and_explicit(self):
        source = {'app.py': 'def health(): pass\n' * 1000, 'game.js': 'let shield = null;\n' * 1000, 'test_app.py': '# shield\n' * 1000}
        result = planning_context(source, 'Repair shield creation in game.js')
        self.assertEqual(result['excerpts'][0]['file'], 'game.js')
        self.assertIn('shield = null', result['excerpts'][0]['content'])
        self.assertEqual(result['source_characters'], 8000)
        self.assertTrue(result['excerpts'][0]['truncated'])
        self.assertIn('not proof', result['meaning'])
        self.assertLessEqual(len(json.dumps(result['source_map'])), 2600)

    def test_same_repair_tasks_rejected_even_with_whitespace_changes(self):
        plan = copy.deepcopy(BASE)
        plan['tasks'][0]['instructions'] = '  ' + plan['tasks'][0]['instructions'].upper() + '\n'
        with self.assertRaisesRegex(ValueError, 'repeats the previous build tasks'):
            Workbench.revision_plan({'baseline_plan': BASE, 'change_request': 'Fix broken shield'}, plan)
        candidate = Workbench.revision_plan({'baseline_plan': BASE, 'change_request': 'Fix broken shield'}, REPAIR)
        self.assertEqual(candidate['manual_checks'][:8], BASE['manual_checks'])

    def make_parent(self, root, models):
        bench = Workbench(root, models)
        state = bench.create('Use the standard reviewed Neon Dodge.', CONFIG, CONFIG, 'arcade', use_reviewed_plan=True)
        state['plan'] = copy.deepcopy(BASE)
        bench.save(state)
        bench.approve(state['id'], state['plan'])
        state = bench.load(state['id'])
        bench.apply(state, {'files': {'game.js': 'let shield = null; // pickup implementation is missing'}})
        return bench, state['id']

    def test_recycled_plan_recovers_with_real_source_in_feedback(self):
        with tempfile.TemporaryDirectory() as temp:
            models = ScriptedModels([BASE, REPAIR])
            bench, ident = self.make_parent(Path(temp), models)
            before = bench.files(ident)
            child = bench.fork(ident, 'Fix game.js: shield stays null and no pickups are created.')
            child = await_job(bench, child['id'])
            self.assertEqual(child['status'], 'proposed', child.get('error'))
            self.assertEqual(child['planning_stats']['attempts'], 2)
            context = models.calls[0]['implementation_context']
            self.assertIn('shield = null', context['excerpts'][0]['content'])
            self.assertEqual(context['excerpts'][0]['file'], 'game.js')
            self.assertIn('repeats the previous build tasks', models.calls[1]['validation_error'])
            self.assertEqual(bench.files(ident), before)

    def test_save_imported_plan_is_visible_persistent_and_has_no_source_side_effects(self):
        with tempfile.TemporaryDirectory() as temp:
            models = ScriptedModels([REPAIR])
            bench, ident = self.make_parent(Path(temp), models)
            child = await_job(bench, bench.fork(ident, 'Fix missing shield creation in game.js')['id'])
            source = bench.files(child['id'])
            calls = len(models.calls)
            edited = copy.deepcopy(REPAIR); edited['title'] = 'Reviewed shield repair'
            saved = bench.save_proposal(child['id'], edited)
            self.assertEqual(saved['title'], 'Reviewed shield repair')
            self.assertEqual(len(saved['plan']['tasks']), 2)
            self.assertFalse(saved['approved'])
            self.assertEqual(bench.files(child['id']), source)
            self.assertEqual(len(models.calls), calls)
            self.assertEqual(bench.load(child['id'])['plan'], saved['plan'])
            with self.assertRaisesRegex(ValueError, 'repeats'):
                bench.save_proposal(child['id'], BASE)
            bad = copy.deepcopy(REPAIR); bad['features'] = ['Drop baseline']
            with self.assertRaisesRegex(ValueError, 'preserve'):
                bench.save_proposal(child['id'], bad)
            bench.approve(child['id'], saved['plan'])
            with self.assertRaisesRegex(ValueError, 'unapproved'):
                bench.save_proposal(child['id'], edited)


if __name__ == '__main__':
    unittest.main()
