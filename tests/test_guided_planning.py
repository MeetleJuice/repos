"""Staged planning regressions, no live inference or weakened approval checks."""
import copy
import json
from pathlib import Path
import tempfile
import threading
import unittest
import hashlib
import urllib.error
from unittest.mock import patch
from forge.core import Workbench
from forge.models import ModelError
from forge.contracts import require_consistent
from tests.fixtures import PLAN
from tests.test_workbench import ScriptedModels,await_job
from tests.test_cloud import state_for
from tests.test_task_contracts import structured_plan
from tests.fixtures import APP, TEST
from forge.guided import run_guided, validate_outline, validate_batch, stage_review, OUTLINE_PROMPT, TASKS_PROMPT, OUTLINE_SCHEMA, BATCH_SCHEMA


def responses():
    plan=structured_plan();plan['context_policy']='focused_v1';plan['app_kind']='server'
    task=plan['tasks'][0]
    plan['tasks']=[{**task,'title':'Implement app behavior','files':['app.py'],'feature_indexes':[0],
        'depends_on':[]},{**task,'title':'Cover saved task listing','files':['test_app.py'],'feature_indexes':[1],'depends_on':[0]}]
    return {name:value for name,value in plan.items() if name!='tasks'},{'tasks':plan['tasks']},plan


class GuidedPlanningTests(unittest.TestCase):
    def test_single_pass_review_also_retains_response_digest(self):
        with tempfile.TemporaryDirectory() as temp:
            models=ScriptedModels([PLAN]);bench=Workbench(Path(temp)/'projects',models)
            config={'provider':'ollama','model':'fixture'}
            state=await_job(bench,bench.create('Build a local task tracker',config,config)['id'])
            self.assertEqual(state['model_calls'][0].get('response_sha256'),hashlib.sha256(json.dumps(PLAN,sort_keys=True).encode()).hexdigest())

    def test_frozen_failure_fixture(self):
        fixture=Path(__file__).parent/'fixture_data/guided-planning-v1.json'
        self.assertEqual(hashlib.sha256(fixture.read_bytes()).hexdigest(),'615eb3f15593f060ee61439ac314df42a0b8819629ef4414cd3960a45ab9492f')

    def test_resume_keeps_outline_and_checks_but_changed_request_restarts(self):
        outline,batch,expected=responses();drafts=[];cancel=threading.Event();calls=[]
        def generate(system,payload,validate):
            calls.append(system);response=outline if system==OUTLINE_PROMPT else batch
            validate(response);return copy.deepcopy(response)
        def stop(draft):drafts.append(draft);cancel.set()
        request={'idea':'A local task tracker','revision':'Keep SQLite'}
        with self.assertRaises(InterruptedError):run_guided(request,generate,stop,cancel)
        self.assertEqual(calls,[OUTLINE_PROMPT]);self.assertEqual(drafts[-1]['tasks'],[])
        cancel.clear();calls.clear()
        self.assertEqual(run_guided(request,generate,drafts.append,cancel,drafts[-1]),expected)
        self.assertEqual(calls,[TASKS_PROMPT])
        calls.clear();run_guided({**request,'revision':'Also add a filter'},generate,drafts.append,cancel,drafts[-1])
        self.assertEqual(calls,[OUTLINE_PROMPT,TASKS_PROMPT])
        self.assertEqual(drafts[-1]['outline']['checks'],outline['checks'])

    def test_outline_is_not_approvable_and_batch_cannot_change_acceptance_or_scope(self):
        outline,batch,_=responses();validate_outline(outline)
        with self.assertRaises(ValueError):require_consistent(outline)
        for change in ({'checks':[]},{'tasks':[]},{'task_contract_version':True}):
            with self.subTest(change=change),self.assertRaises(ValueError):validate_outline({**outline,**change})
        for change in ({'checks':[]},{'tasks':[{**batch['tasks'][0],'files':['README.md']}]},
                       {'tasks':[{**batch['tasks'][0],'depends_on':[0]}]},
                       {'tasks':[{**batch['tasks'][0],'feature_indexes':[2]}]}):
            with self.subTest(change=change),self.assertRaises(ValueError):validate_batch({**batch,**change},outline,[],[0,1],4)

    def test_guided_native_schema_and_explicit_local_timeout(self):
        from forge.models import ModelClient
        for system,schema,response in ((OUTLINE_PROMPT,OUTLINE_SCHEMA,responses()[0]),(TASKS_PROMPT,BATCH_SCHEMA,responses()[1])):
            with self.subTest(system=system[:30]),patch('forge.models.request_json',return_value={'message':{'content':json.dumps(response)},'done':True}) as wire:
                client=ModelClient('ollama','fixture');client.options['timeout_seconds']=300
                self.assertEqual(client.complete(system,'{}'),response)
                self.assertEqual(wire.call_args.args[1]['format'],schema)
                self.assertGreaterEqual(wire.call_args.args[1]['options']['num_predict'],8192)
                self.assertEqual(wire.call_args.kwargs['timeout'],300)

    def test_run_local_timeout_is_applied_without_mutating_saved_route(self):
        outline,_,_=responses()
        with tempfile.TemporaryDirectory() as temp,patch('forge.models.request_json',return_value={'message':{'content':json.dumps(outline)},'done':True}) as wire:
            bench=Workbench(Path(temp)/'projects');state=state_for(bench)
            state['planner']={'provider':'ollama','model':'fixture','options':{'num_ctx':32768,'num_predict':8192,'timeout_seconds':120}}
            before=copy.deepcopy(state['planner']);state['job_local_timeout']=300
            result=bench.call_model(state,'planner',OUTLINE_PROMPT,'{}',threading.Event(),review_candidate=lambda value:stage_review(validate_outline,value))
            self.assertEqual(result,outline);self.assertEqual(state['planner'],before)
            self.assertEqual(wire.call_args.kwargs['timeout'],300)
            self.assertEqual(state['model_calls'][0]['timeout_seconds'],300)

    def test_known_timeout_and_connection_remain_distinct(self):
        from forge.models import request_json
        for error,kind in ((TimeoutError('timed out'),'timeout'),(urllib.error.URLError(TimeoutError('timed out')),'timeout'),(ConnectionRefusedError('refused'),'connection')):
            with patch('urllib.request.urlopen',side_effect=error),self.assertRaises(ModelError) as caught:
                request_json('https://fixture.invalid/models')
            self.assertEqual(caught.exception.category,'transport')
            self.assertEqual(caught.exception.transport_kind,kind)

    def test_six_batches_reserve_room_within_sixteen_task_allowance(self):
        outline,batch,_=responses();outline['features']=['Feature '+str(i) for i in range(12)]
        outline['checks'][-1]['feature_indexes']=list(range(12));limits=[]
        def generate(system,payload,validate):
            if system==OUTLINE_PROMPT:return copy.deepcopy(outline)
            maximum=payload['max_new_tasks'];limits.append(maximum)
            tasks=[{**copy.deepcopy(batch['tasks'][0]),'feature_indexes':payload['target_feature_indexes'],
                'depends_on':[payload['next_task_index']-1] if payload['next_task_index'] else []} for _ in range(maximum)]
            candidate={'tasks':tasks};validate(candidate);return candidate
        result=run_guided({'idea':'A bounded app'},generate,lambda draft:None,threading.Event())
        self.assertEqual(limits,[4,4,4,2,1,1]);self.assertEqual(len(result['tasks']),16)
        require_consistent(result)

    def test_uploaded_failure_route_keeps_both_failure_explanations(self):
        fixture=json.loads((Path(__file__).parent/'fixture_data/guided-planning-v1.json').read_text())
        invalid=copy.deepcopy(structured_plan())
        for field in fixture['failure_route'][1]['missing']:del invalid['tasks'][0][field]
        with tempfile.TemporaryDirectory() as temp:
            models=ScriptedModels([ModelError('Model timed out','transport',transport_kind='timeout'),invalid,invalid])
            bench=Workbench(Path(temp)/'projects',models);state=state_for(bench)
            state['planner']={'provider':'ollama','model':fixture['failure_route'][0]['model'],'fallbacks':[{'provider':'ollama','model':fixture['failure_route'][1]['model']}]}
            with self.assertRaises(ModelError):
                bench.call_model(state,'planner','Plan','{}',threading.Event(),review_candidate=lambda value:stage_review(require_consistent,value))
            self.assertEqual([row['error_category'] for row in state['model_calls']],['transport','schema_error','schema_error'])
            self.assertEqual(state['model_calls'][0]['transport_kind'],'timeout')
            self.assertIn('outcome',state['model_calls'][1]['review_findings'][0]['message'])
            self.assertEqual(len(state['model_calls'][1]['response_sha256']),64)

    def test_static_repair_cannot_write_a_future_tasks_file(self):
        plan=structured_plan();plan['tasks'][0]['files']=['app.py']
        response={'files':{'app.py':APP,'future.py':'value=1\n'}}
        with tempfile.TemporaryDirectory() as temp:
            models=ScriptedModels([plan,response,response]);bench=Workbench(Path(temp)/'projects',models)
            config={'provider':'ollama','model':'fixture'}
            state=await_job(bench,bench.create('Build a local task tracker',config,config)['id'])
            bench.approve(state['id'],state['plan']);state=bench.load(state['id'])
            bench.apply(state,{'files':{'app.py':APP,'test_app.py':TEST}})
            (bench.directory(state['id'])/'source/app.py').write_text('def broken(:\n')
            before=bench.files(state['id']);state['pending_task']={'cursor':0}
            with self.assertRaisesRegex(ValueError,'scope|outside|approved'):
                bench._inspect_and_repair(state,threading.Event(),1)
            self.assertEqual(bench.files(state['id']),before)
            self.assertNotIn('future.py',bench.files(state['id']))
            self.assertEqual(models.calls[-1]['task_packet']['files'],['app.py'])

    def test_new_project_can_explicitly_choose_guided_planning(self):
        outline,batch,expected=responses()
        with tempfile.TemporaryDirectory() as temp:
            models=ScriptedModels([outline,batch]);bench=Workbench(Path(temp)/'projects',models)
            config={'provider':'ollama','model':'fixture'}
            state=await_job(bench,bench.create('Build a local task tracker',config,config,plan_mode='guided',local_timeout=300)['id'])
            self.assertEqual(state['status'],'proposed',state.get('error'))
            self.assertEqual(state['plan'],expected)
            self.assertFalse(state['approved'])

    def test_stopped_guided_job_resumes_after_workbench_restart(self):
        outline,batch,expected=responses()
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'projects';models=ScriptedModels([PLAN,outline,batch]);bench=Workbench(root,models)
            config={'provider':'ollama','model':'fixture'}
            state=await_job(bench,bench.create('Build a local task tracker',config,config)['id'])
            event=bench.event
            def stop_after_outline(state,message,origin='controller'):
                event(state,message,origin)
                if message.startswith('Guided planning: 0/'):
                    bench.jobs[state['id']][1].set()
            bench.event=stop_after_outline
            bench.start(state['id'],'plan',{'plan_mode':'guided'})
            stopped=await_job(bench,state['id'])
            self.assertEqual(stopped['status'],'stopped');self.assertFalse(stopped['approved'])
            self.assertEqual(stopped['guided_draft']['next_feature'],0)
            resumed=Workbench(root,models);resumed.start(state['id'],'plan',{'plan_mode':'guided'})
            final=await_job(resumed,state['id'])
            self.assertEqual(final['plan'],expected);self.assertEqual(final['status'],'proposed')
            self.assertEqual(len(models.calls),3)

    def test_guided_cloud_route_still_requires_explicit_consent(self):
        with tempfile.TemporaryDirectory() as temp:
            models=ScriptedModels([]);bench=Workbench(Path(temp)/'projects',models)
            config={'provider':'gemini','model':'fixture'}
            with self.assertRaisesRegex(ValueError,'cloud'):
                bench.create('Build a local task tracker',config,config,plan_mode='guided')
            self.assertEqual(models.calls,[]);self.assertEqual(bench.list_projects(),[])

    def test_prompt_examples_satisfy_current_approval_contract(self):
        from forge.prompts import PLAN as prompt
        decoder=json.JSONDecoder()
        for title in ('Task tracker','Neon Dodge'):
            start=prompt.index('{"title":"'+title+'"')
            example,_=decoder.raw_decode(prompt[start:])
            self.assertEqual(example['task_contract_version'],1)
            self.assertGreaterEqual(len(example['tasks']),2)
            require_consistent(example)

    def test_guided_mode_builds_full_reviewed_proposal_from_small_calls(self):
        outline,batch,expected=responses()
        with tempfile.TemporaryDirectory() as temp:
            models=ScriptedModels([PLAN,outline,batch]);bench=Workbench(Path(temp)/'projects',models)
            config={'provider':'ollama','model':'fixture'}
            state=await_job(bench,bench.create('Build a local task tracker',config,config)['id'])
            bench.start(state['id'],'plan',{'plan_mode':'guided','local_timeout':300})
            state=await_job(bench,state['id'])
            self.assertEqual(state['status'],'proposed',state.get('error'))
            self.assertEqual(state['plan'],expected)
            self.assertFalse(state['approved']);require_consistent(state['plan'])
            self.assertEqual(len(models.calls),3)
            self.assertEqual(state['planning_stats']['mode'],'guided')

    def test_attempt_keeps_actionable_rejection_findings(self):
        with tempfile.TemporaryDirectory() as temp:
            invalid=copy.deepcopy(PLAN);del invalid['tasks'][0]['instructions']
            models=ScriptedModels([invalid]*4);bench=Workbench(Path(temp)/'projects',models);state=state_for(bench)
            state['planner']={'provider':'ollama','model':'fixture','fallbacks':[{'provider':'ollama','model':'backup'}]}
            from forge.contracts import Review,Finding
            with self.assertRaises(ModelError):
                bench.call_model(state,'planner','Plan','{}',threading.Event(),review_candidate=lambda candidate:(candidate,Review((Finding('structure','/tasks/0','Missing instructions.'),))))
            self.assertTrue(state['model_calls'][0].get('review_findings'))
            self.assertEqual(state['model_calls'][0]['review_findings'][0]['message'],'Missing instructions.')
