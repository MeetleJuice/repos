"""Observed late-review failure shapes; synthetic replies, never live quality claims."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import threading
import unittest

from forge.contracts import review_plan
from forge.core import Workbench
from forge.guided import StageValidationError, run_guided
from forge.outline_planning import assemble
from tests.test_guided_planning import responses, outline_replies, feature_batches
from tests.test_workbench import ScriptedModels, await_job


def boundary_fixture():
    outline, batch, _ = responses()
    scope, valid = outline_replies(outline)
    valid['checks'][1].update(name='Retrieve saved task after restart', restart_before=True)
    invalid = copy.deepcopy(valid)
    invalid['checks'][0]['restart_before'] = True
    invalid['checks'][1].pop('restart_before')
    return scope, invalid, valid, batch


class AcceptanceBoundaryTests(unittest.TestCase):
    def test_frozen_observed_failure_shapes_and_corrected_restart(self):
        root=Path(__file__).parent/'fixture_data'
        for entry in json.loads((root/'frozen-regressions-v17.json').read_text())['sets']:
            self.assertEqual(hashlib.sha256((root/entry['file']).read_bytes()).hexdigest(), entry['sha256'])
        fixture=json.loads((root/'acceptance-boundary-v1.json').read_text())
        with self.assertRaises(StageValidationError) as raised:
            assemble(fixture['scope'], fixture['invalid'], {})
        self.assertEqual({(f.code,f.path) for f in raised.exception.review.findings},
                         {('restart_evidence','/checks/3'),('false_restart','/checks/4/name')})
        result=assemble(fixture['scope'], fixture['valid'], {})
        self.assertEqual(result['checks'], fixture['valid']['checks'])

    def test_restart_findings_are_rejected_before_task_generation(self):
        scope, invalid, _, _ = boundary_fixture()
        with self.assertRaises(StageValidationError) as raised:
            assemble(scope, invalid, {})
        self.assertEqual({f.code for f in raised.exception.review.findings}, {'restart_evidence', 'false_restart'})

    def test_real_controller_corrects_acceptance_before_any_feature_call(self):
        scope, invalid, valid, batch = boundary_fixture()
        models = ScriptedModels([scope, invalid, valid, *feature_batches(batch['tasks'])])
        with tempfile.TemporaryDirectory() as temp:
            bench = Workbench(Path(temp)/'projects', models)
            config = {'provider':'ollama', 'model':'fixture'}
            state = await_job(bench, bench.create('A persistent local task tracker', config, config,
                                                 plan_mode='guided')['id'])
            self.assertEqual(state['status'], 'proposed', state.get('error'))
            self.assertEqual([call['planning_stage'] for call in models.calls],
                             ['scope', 'acceptance', 'acceptance', 'feature_tasks', 'feature_tasks'])
            self.assertEqual(state['plan']['checks'], valid['checks'])
            self.assertFalse(state['approved'])
            self.assertEqual(bench.files(state['id']), {})
            self.assertEqual(state['model_calls'][1]['failure_class'], 'schema_error')
            self.assertEqual(set(state['model_calls'][1]['review_codes']), {'restart_evidence','false_restart'})

    def test_old_invalid_checkpoint_keeps_scope_but_rebuilds_dependent_tasks(self):
        scope, invalid, valid, batch = boundary_fixture()
        request = {'idea':'Tracker', 'task_planning_policy':'compiled_v1', 'outline_planning_policy':'split_v1'}
        saved = {'schema':2, 'task_planning_policy':'compiled_v1',
                 'request_sha256':hashlib.sha256(json.dumps(request,sort_keys=True).encode()).hexdigest(),
                 'scope':scope, 'outline':{**scope, **invalid}, 'tasks':batch['tasks'], 'next_feature':2}
        original = copy.deepcopy(saved)
        replies = iter([valid, *feature_batches(batch['tasks'])]); stages = []; checkpoints = []
        def generate(system, payload, validate):
            stages.append(payload['planning_stage']); reply=copy.deepcopy(next(replies)); validate(reply); return reply
        result=run_guided(request, generate, checkpoints.append, threading.Event(), saved)
        self.assertEqual(stages, ['acceptance','feature_tasks','feature_tasks'])
        self.assertEqual(checkpoints[0]['scope'], scope)
        self.assertIsNone(checkpoints[0]['outline'])
        self.assertEqual(checkpoints[0]['tasks'], [])
        self.assertEqual(saved, original)
        self.assertEqual(result['checks'], valid['checks'])
        self.assertTrue(review_plan(result).passed)

    def test_repeated_invalid_acceptance_stops_before_tasks(self):
        scope, invalid, _, _ = boundary_fixture()
        models=ScriptedModels([scope, invalid, invalid])
        with tempfile.TemporaryDirectory() as temp:
            bench=Workbench(Path(temp)/'projects', models)
            config={'provider':'ollama','model':'fixture'}
            state=await_job(bench,bench.create('Persistent task tracker',config,config,plan_mode='guided')['id'])
            self.assertEqual(state['status'],'error')
            self.assertFalse(any(call['planning_stage']=='feature_tasks' for call in models.calls))
            self.assertEqual(state['guided_draft']['scope'],scope)
            self.assertIsNone(state['guided_draft']['outline'])
            self.assertFalse(state['approved'])

    def test_shared_outline_reviewer_catches_starter_contract_mismatch(self):
        from forge.scaffolds import CATALOG
        from tests.test_planning import good_notes
        outline={k:v for k,v in good_notes().items() if k!='tasks'}
        outline.update(task_contract_version=1, context_policy='focused_v1', app_kind='server')
        scope,acceptance=outline_replies(outline)
        acceptance.pop('api_contracts')
        acceptance['checks'][1]['json_contains']=['wrong row shape']
        with self.assertRaises(StageValidationError) as raised:
            assemble(scope,acceptance,{'starter':CATALOG['notes']})
        self.assertIn('response_shape',{f.code for f in raised.exception.review.findings})

    def test_valid_outline_resume_does_not_rewrite_acceptance(self):
        scope, _, valid, batch = boundary_fixture()
        request={'idea':'Tracker','task_planning_policy':'compiled_v1','outline_planning_policy':'split_v1'}
        drafts=[];cancel=threading.Event();replies=iter([scope,valid]);stages=[]
        def generate(system,payload,validate):
            stages.append(payload['planning_stage']);reply=copy.deepcopy(next(replies));validate(reply);return reply
        def checkpoint(draft):
            drafts.append(draft)
            if draft.get('outline') is not None:cancel.set()
        with self.assertRaises(InterruptedError):run_guided(request,generate,checkpoint,cancel)
        cancel.clear();stages.clear();replies=iter(feature_batches(batch['tasks']))
        result=run_guided(request,generate,drafts.append,cancel,drafts[-1])
        self.assertEqual(stages,['feature_tasks','feature_tasks'])
        self.assertEqual(result['checks'],valid['checks'])
