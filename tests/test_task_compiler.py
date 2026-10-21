"""Controller planning regressions; synthetic replies, never live-model evidence."""
import copy
import threading
import unittest
import json
import hashlib
import tempfile
from pathlib import Path
from unittest.mock import patch

from forge.guided import run_guided
from tests.test_guided_planning import responses
from forge.task_planning import compile_tasks, schedule, FEATURE_PROMPT, FEATURE_SCHEMA, validate_compilable_outline
from forge.contracts import require_consistent
from tests.test_evidence_planning import sqlite_plan


class TaskCompilerTests(unittest.TestCase):
    def test_frozen_compiler_fixture_and_prior_sets_are_unchanged(self):
        root = Path(__file__).parent/'fixture_data'
        for item in json.loads((root/'frozen-regressions-v15.json').read_text())['sets']:
            self.assertEqual(hashlib.sha256((root/item['file']).read_bytes()).hexdigest(), item['sha256'])
        fixture = json.loads((root/'task-compiler-v1.json').read_text())
        replies = iter([fixture['outline'], *fixture['semantic_replies']])
        def generate(system, payload, validate):
            reply = copy.deepcopy(next(replies)); validate(reply); return reply
        plan = run_guided({'idea':'Fixture Tiny Wins', 'task_planning_policy':'compiled_v1'},
                          generate, lambda draft: None, threading.Event())
        require_consistent(plan, 'sqlite')
        self.assertEqual(plan['checks'], fixture['outline']['checks'])
        self.assertEqual([task['feature_indexes'] for task in plan['tasks']], fixture['expected_feature_indexes'])
        self.assertEqual([task['depends_on'] for task in plan['tasks']], fixture['expected_dependencies'])
        self.assertEqual([task.get('check_indexes', []) for task in plan['tasks']], fixture['expected_check_indexes'])

    def test_checkpoint_schedule_preserves_checks_and_never_schedules_future_work(self):
        plan = sqlite_plan(); original = copy.deepcopy(plan)
        tasks = schedule(plan, plan['tasks'])
        self.assertEqual(tasks[0]['check_indexes'], list(range(len(plan['checks']))))
        self.assertNotIn('check_indexes', tasks[1])
        require_consistent({**plan, 'tasks': tasks}, 'sqlite')
        self.assertEqual(plan, original)
        first = schedule(plan, [plan['tasks'][0]])
        self.assertEqual(first[0]['check_indexes'], list(range(len(plan['checks']))))

    def test_misplaced_model_indexes_are_rejected_not_silently_relabelled(self):
        outline, batch, _ = responses()
        with self.assertRaisesRegex(ValueError, 'controller-owned'):
            compile_tasks({'tasks': [batch['tasks'][0]]}, outline, [], 0, 3, None)

    def test_wide_and_protected_tasks_still_fail_before_approval(self):
        outline, batch, _ = responses()
        item = {k: v for k, v in batch['tasks'][0].items() if k not in {'feature_indexes', 'depends_on', 'check_indexes'}}
        for files in (['a.py','b.py','c.py'], ['test_foundation.py']):
            with self.subTest(files=files), self.assertRaises(ValueError):
                compile_tasks({'tasks': [{**item, 'files': files}]}, outline, [], 0, 3,
                    {'max_editable_files': 2, 'max_feature_indexes': 1, 'protected_existing_files': ['test_foundation.py']})

    def test_unschedulable_outline_fails_before_task_calls(self):
        plan = sqlite_plan(); outline = {k:v for k,v in plan.items() if k != 'tasks'}
        outline['checks'][0]['feature_indexes'] = [0,1]
        with self.assertRaisesRegex(ValueError, 'No early business prefix'):
            validate_compilable_outline(outline)

    def test_same_feature_multiple_tasks_have_last_producer_checkpoint(self):
        plan = sqlite_plan()
        tasks = [copy.deepcopy(plan['tasks'][0]), copy.deepcopy(plan['tasks'][0]), copy.deepcopy(plan['tasks'][1])]
        tasks[1]['instructions'] = 'Add focused SQLite restart regression tests after the storage API is implemented.'
        tasks[1]['outcome'] = 'The existing storage API has independent persistence tests.'
        tasks[1]['done_when'] = ['A restart test reads the record created before server shutdown.']
        tasks[1]['depends_on'] = [0]; tasks[2]['depends_on'] = [1]
        scheduled = schedule(plan, tasks)
        self.assertNotIn('check_indexes', scheduled[0])
        self.assertEqual(scheduled[1]['check_indexes'], list(range(len(plan['checks']))))
        require_consistent({**plan, 'tasks': scheduled}, 'sqlite')

    def test_native_schema_removes_bookkeeping_and_obeys_builder_file_cap(self):
        from forge.models import ModelClient
        payload = {'planning_stage':'feature_tasks', 'builder_profile': {'max_editable_files':1, 'max_feature_indexes':1}}
        with patch('forge.models.request_json', return_value={'message':{'content':'{"tasks":[]}'}, 'done':True}) as wire:
            ModelClient('ollama','fixture').complete(FEATURE_PROMPT, json.dumps(payload))
        item = wire.call_args.args[1]['format']['properties']['tasks']['items']
        self.assertEqual(item['properties']['files']['maxItems'], 1)
        self.assertFalse(item['additionalProperties'])
        self.assertNotIn('feature_indexes', item['properties'])
        self.assertEqual(FEATURE_SCHEMA['properties']['tasks']['items']['properties']['files']['maxItems'], 3)

    def test_stage_stops_after_six_rejected_calls_and_retains_diagnostics(self):
        from forge.core import Workbench
        from forge.guided import stage_review
        from forge.models import ModelError
        from tests.test_cloud import state_for
        from tests.test_workbench import ScriptedModels
        def reject(candidate): raise ValueError('Task is too broad for the configured builder profile')
        with tempfile.TemporaryDirectory() as temp:
            models = ScriptedModels([{'tasks': []}]*8)
            bench = Workbench(Path(temp)/'projects', models); state = state_for(bench)
            state['planner'] = {'provider':'ollama','model':'fixture-0',
                'fallbacks':[{'provider':'ollama','model':'fixture-'+str(i)} for i in range(1,5)]}
            payload = {'task_planning_policy':'compiled_v1','planning_stage':'feature_tasks','target_feature_indexes':[0]}
            with self.assertRaises(ModelError) as caught:
                bench.call_model(state,'planner',FEATURE_PROMPT,json.dumps(payload),threading.Event(),
                    review_candidate=lambda value: stage_review(reject,value))
            self.assertEqual(caught.exception.category, 'planning_stage_budget')
            self.assertEqual(len(models.calls), 6)
            self.assertEqual(state['model_calls'][-1]['review_codes'], ['task_width'])
            self.assertEqual(state['model_calls'][-1]['planning_stage'], 'feature_tasks')

    def test_provider_failures_do_not_consume_semantic_rejection_allowance(self):
        from forge.core import Workbench
        from forge.contracts import Review
        from forge.models import ModelError
        from tests.test_cloud import state_for
        from tests.test_workbench import ScriptedModels
        with tempfile.TemporaryDirectory() as temp:
            models = ScriptedModels([ModelError('Fixture unavailable', 'transport') for _ in range(7)]+[{'tasks':[]}])
            bench = Workbench(Path(temp)/'projects', models); state = state_for(bench)
            state['planner'] = {'provider':'ollama','model':'fixture-0',
                'fallbacks':[{'provider':'ollama','model':'fixture-'+str(i)} for i in range(1,8)]}
            payload = {'task_planning_policy':'compiled_v1','planning_stage':'feature_tasks'}
            result = bench.call_model(state,'planner',FEATURE_PROMPT,json.dumps(payload),threading.Event(),
                review_candidate=lambda value: (value, Review(())))
            self.assertEqual(result, {'tasks':[]})
            self.assertEqual(len(models.calls), 8)

    def test_one_feature_requests_and_controller_owned_references(self):
        outline, batch, _ = responses()
        calls = []
        drafts = []

        def generate(system, payload, validate):
            calls.append(copy.deepcopy(payload))
            if payload['planning_stage'] == 'outline':
                return copy.deepcopy(outline)
            target = payload['target_feature_indexes'][0]
            task = copy.deepcopy(batch['tasks'][target])
            for name in ('depends_on', 'feature_indexes', 'check_indexes'):
                task.pop(name, None)
            value = {'tasks': [task]}
            validate(value)
            return value

        result = run_guided({'idea': 'Task tracker', 'task_planning_policy': 'compiled_v1'},
                            generate, drafts.append, threading.Event())
        self.assertEqual([p['target_feature_indexes'] for p in calls[1:]], [[0], [1]])
        self.assertEqual(result['tasks'][0]['depends_on'], [])
        self.assertEqual(result['tasks'][1]['depends_on'], [0])
        self.assertEqual([t['feature_indexes'] for t in result['tasks']], [[0], [1]])
        self.assertEqual(drafts[-1]['task_planning_policy'], 'compiled_v1')

    def test_resume_preserves_accepted_feature_without_replanning(self):
        outline, batch, _ = responses()
        cancel = threading.Event()
        drafts = []
        calls = []

        def generate(system, payload, validate):
            calls.append(payload['planning_stage'])
            if payload['planning_stage'] == 'outline': return copy.deepcopy(outline)
            task = copy.deepcopy(batch['tasks'][payload['target_feature_indexes'][0]])
            for key in ('depends_on', 'feature_indexes', 'check_indexes'): task.pop(key, None)
            return {'tasks': [task]}

        def checkpoint(draft):
            drafts.append(draft)
            if draft['next_feature'] == 1: cancel.set()

        request = {'idea': 'Task tracker', 'task_planning_policy': 'compiled_v1'}
        with self.assertRaises(InterruptedError):
            run_guided(request, generate, checkpoint, cancel)
        cancel.clear(); calls.clear()
        result = run_guided(request, generate, drafts.append, cancel, drafts[-1])
        self.assertEqual(calls, ['feature_tasks'])
        self.assertEqual(result['tasks'][0], drafts[1]['tasks'][0])

