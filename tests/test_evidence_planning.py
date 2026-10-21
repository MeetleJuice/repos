"""Real exported-plan regression, not a live-model quality benchmark."""
import copy
import hashlib
import json
from pathlib import Path
import unittest
import tempfile
import subprocess
import sys
import threading
from unittest.mock import patch
from forge.contracts import review_plan
from forge.guided import validate_batch
from forge.scaffolds import starter_files
from forge.core import Workbench
from tests.test_workbench import ScriptedModels,await_job
from tests.test_task_contracts import structured_plan


def proof_plan():
    plan=structured_plan();plan['acceptance_policy']='evidence_v1';plan['app_kind']='server'
    plan['api_contracts']=[{'method':'POST','path':'/api/tasks','status':201,'response_kind':'object','required_fields':['title']},
                           {'method':'GET','path':'/api/tasks','status':200,'response_kind':'array','required_fields':['title']}]
    plan['checks'][1].pop('contains');plan['checks'][1]['json_contains']=[{'title':'Buy milk'}]
    plan['tasks'][0]['check_indexes']=[0,1]
    return plan


def sqlite_plan():
    plan={'title':'Tiny Wins — evidence-ready draft','summary':'Reuse tested SQLite storage; build the browser interface.',
        'features':['Create and list records with SQLite persistence','Use a responsive accomplishment interface'],
        'out_of_scope':['Accounts'],'risks':['Manual UI checks still require actual observations.'],
        'app_kind':'server','context_policy':'focused_v1','task_contract_version':1,'acceptance_policy':'evidence_v1',
        'checks':[
            {'name':'Create a concrete record','method':'POST','path':'/api/records','body':{'title':'Saved proof','note':'Persists'},'status':201,'json_contains':{'id':1,'title':'Saved proof'},'feature_indexes':[0]},
            {'name':'Read the created record','method':'GET','path':'/api/records','status':200,'json_contains':{'records':[{'id':1,'title':'Saved proof'}]},'feature_indexes':[0]},
            {'name':'Read it after restart','method':'GET','path':'/api/records','status':200,'restart_before':True,'json_contains':{'records':[{'title':'Saved proof','note':'Persists'}]},'feature_indexes':[0]}],
        'api_contracts':[{'method':'POST','path':'/api/records','status':201,'response_kind':'object','required_fields':['id','title','note','created_at']},
                         {'method':'GET','path':'/api/records','status':200,'response_kind':'object','required_fields':['records','today_count']}],
        'manual_checks':[{'name':'Browser interaction','steps':['Add a win, filter, reload and delete it.'],'expected':'The record persists and the list updates.','feature_indexes':[1]}],
        'tasks':[{'title':'Reuse and check reviewed storage','instructions':'Inspect existing app.py and storage.py. Preserve the reviewed API and factory; cite current source if already implemented.',
            'outcome':'The reviewed API creates and returns saved records.','files':['app.py','storage.py'],'depends_on':[],
            'done_when':['Factory initializes storage; POST returns id; GET reads records across restart.'],'feature_indexes':[0],'check_indexes':[2]},
            {'title':'Build the browser interface','instructions':'Implement a usable form, record list, Today filter and confirmed delete using the existing API; responsive dark gold styling.',
            'outcome':'The browser can create, read, filter and delete records.','files':['index.html','style.css'],'depends_on':[0],
            'done_when':['A usable interface calls the existing API safely.'],'feature_indexes':[1]}]}
    return plan


class EvidencePlanningTests(unittest.TestCase):
    def test_exported_failure_fixture_is_frozen(self):
        path=Path(__file__).parent/'fixture_data/tiny-wins-evidence-v1.json'
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),'c02e038ac538cd5546d8b494339e54ae14d5e152bfaf9b91c26e37f5a77ecb1d')
    def test_uploaded_tiny_wins_is_rejected_only_under_new_policy(self):
        fixture=json.loads((Path(__file__).parent/'fixture_data/tiny-wins-evidence-v1.json').read_text())
        original=fixture['approved_plan'];before=copy.deepcopy(original)
        self.assertTrue(review_plan(original,'web').passed)
        result=review_plan({**original,'acceptance_policy':'evidence_v1'},'web')
        self.assertFalse(result.passed)
        codes={finding.code for finding in result.findings}
        self.assertTrue({'vacuous_assertion','mutation_example','persistence_evidence','missing_api_contract','missing_milestone'}<=codes)
        self.assertEqual(original,before)

    def test_meaningful_plan_and_exact_empty_results_remain_valid(self):
        plan=proof_plan();self.assertTrue(review_plan(plan).passed)
        plan['checks'].append({'name':'Exact empty result','method':'GET','path':'/api/tasks?empty=true','status':200,'json_equals':[],'feature_indexes':[1]})
        plan['tasks'][0]['check_indexes'].append(2)
        self.assertTrue(review_plan(plan).passed)

    def test_restart_requires_created_data_not_only_health_or_empty_lists(self):
        plan=proof_plan();plan['checks'][1]['restart_before']=True
        self.assertTrue(review_plan(plan).passed)
        plan['checks'][1]['json_contains']=[{'title':'NEVER CREATED'}]
        self.assertIn('persistence_evidence',{f.code for f in review_plan(plan).findings})

    def test_legacy_checks_and_delivery_browser_app_are_unchanged(self):
        plan=proof_plan();plan.pop('acceptance_policy');plan.pop('api_contracts');plan['checks'][1]['json_contains']=[]
        # The original structure validator still rejects empty root subsets.
        self.assertFalse(review_plan(plan).passed)
        plan['checks'][1]['json_contains']={'items':[]}
        self.assertTrue(review_plan(plan).passed)

    def test_ready_milestone_is_required_in_the_current_batch(self):
        plan=sqlite_plan();outline={k:v for k,v in plan.items() if k!='tasks'}
        validate_batch({'tasks':plan['tasks']},outline,[],[0,1],4)
        bad=copy.deepcopy(plan['tasks']);bad[0].pop('check_indexes')
        with self.assertRaisesRegex(ValueError,'check_indexes'):validate_batch({'tasks':bad},outline,[],[0,1],4)

    def test_checkpoint_cannot_run_future_feature_checks(self):
        plan=proof_plan();task=plan['tasks'][0]
        plan['tasks']=[{**task,'feature_indexes':[0],'files':['app.py'],'check_indexes':[1]},
                       {**task,'feature_indexes':[1],'files':['test_app.py'],'depends_on':[0],'check_indexes':[1]}]
        self.assertIn('premature_milestone',{f.code for f in review_plan(plan).findings})

    def test_browser_delivery_checks_are_not_fabricated_gameplay_milestones(self):
        plan=structured_plan();plan.update(app_kind='browser',acceptance_policy='evidence_v1',features=['Play the browser game'])
        plan['tasks'][0]['feature_indexes']=[0]
        plan['checks']=[{'name':'Deliver page','method':'GET','path':'/','status':200,'contains':'<canvas','feature_indexes':[]}]
        plan['manual_checks']=[{'name':'Play the game','steps':['Start, move and restart.'],'expected':'Controls and restart work.','feature_indexes':[0]}]
        self.assertTrue(review_plan(plan).passed)

    def test_proof_mode_survives_editor_removal_and_preserves_legacy(self):
        plan=sqlite_plan();outline={k:v for k,v in plan.items() if k!='tasks'}
        outline.pop('acceptance_policy')
        with tempfile.TemporaryDirectory() as folder:
            bench=Workbench(Path(folder)/'projects',ScriptedModels([outline,{'tasks':plan['tasks']}]))
            config={'provider':'ollama','model':'fixture'}
            state=await_job(bench,bench.create('A small accomplishment tracker',config,config,'sqlite',plan_mode='proof')['id'])
            self.assertEqual(state['status'],'proposed',state.get('error'))
            self.assertEqual(state['plan']['acceptance_policy'],'evidence_v1')
            removed=copy.deepcopy(state['plan']);removed.pop('acceptance_policy')
            removed['checks'][0].pop('body')
            with self.assertRaises(ValueError):bench.approve(state['id'],removed)
            self.assertFalse(bench.load(state['id'])['approved'])
            self.assertEqual(bench.context_files(state['id']),{})
            bench.approve(state['id'],state['plan'])
            with self.assertRaisesRegex(ValueError,'requires its approved checkpoints'):
                bench.start(state['id'],'build',{'execute':True,'consent':True,'runtime':'local','milestones':False})

    def test_sqlite_foundation_runs_in_a_disposable_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            for name,text in starter_files('sqlite').items():(Path(folder)/name).write_text(text)
            result=subprocess.run([sys.executable,'-m','unittest','discover','-v'],cwd=folder,capture_output=True,text=True,timeout=20)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn('Ran 2 tests',result.stderr)

    def test_failed_milestone_repair_cannot_write_future_files_or_advance(self):
        from tests.fixtures import APP,TEST
        plan=structured_plan();plan['tasks'][0]['check_indexes']=[0]
        bad={'files':{'future_feature.py':'should_never_be_written=True\n'}}
        with tempfile.TemporaryDirectory() as folder:
            bench=Workbench(Path(folder)/'projects',ScriptedModels([plan,bad,bad]))
            config={'provider':'ollama','model':'fixture'}
            state=await_job(bench,bench.create('A small task tracker',config,config)['id'])
            bench.approve(state['id'],state['plan']);state=bench.load(state['id'])
            bench.apply(state,{'files':{'app.py':APP,'test_app.py':TEST}})
            state['next_task']=1;state['milestones']=[{'task':1}]
            bench.milestone_verifier=lambda *args:{'passed':False,'failure_kind':'application','log':'Create response was wrong.'}
            with patch.object(bench,'_inspect_and_repair',side_effect=lambda state,cancel,remaining,**kwargs:remaining):
                with self.assertRaisesRegex(ValueError,'Task scope violation'):
                    bench._verify_milestone(state,state['plan']['tasks'][0],0,{'runtime':'local'},threading.Event(),1)
            self.assertNotIn('future_feature.py',bench.files(state['id']))
            self.assertEqual(state['next_task'],0)

    def test_successful_milestone_repair_seals_the_restored_cursor(self):
        from tests.fixtures import APP,TEST
        from forge.execution import resume_problem
        plan=structured_plan();plan['tasks'][0]['check_indexes']=[0]
        with tempfile.TemporaryDirectory() as folder:
            bench=Workbench(Path(folder)/'projects',ScriptedModels([plan,{'files':{'app.py':APP+'\n# scoped repair\n'}}]))
            config={'provider':'ollama','model':'fixture'}
            state=await_job(bench,bench.create('A small task tracker',config,config)['id'])
            bench.approve(state['id'],state['plan']);state=bench.load(state['id'])
            bench.apply(state,{'files':{'app.py':APP,'test_app.py':TEST}})
            state['next_task']=1;state['milestones']=[{'task':1}]
            results=iter([{'passed':False,'failure_kind':'application','log':'Incorrect response.'},{'passed':True}])
            bench.milestone_verifier=lambda *args:next(results)
            with patch.object(bench,'_inspect_and_repair',side_effect=lambda state,cancel,remaining,**kwargs:remaining):
                self.assertEqual(bench._verify_milestone(state,state['plan']['tasks'][0],0,{'runtime':'local'},threading.Event(),1),0)
            self.assertEqual(state['next_task'],1)
            self.assertEqual(resume_problem(state,bench.context_files(state['id'])),'')


    def test_verifier_exception_cannot_skip_the_unverified_task(self):
        from tests.fixtures import APP,TEST
        plan=structured_plan();plan['tasks'][0]['check_indexes']=[0]
        with tempfile.TemporaryDirectory() as folder:
            bench=Workbench(Path(folder)/'projects',ScriptedModels([plan]));config={'provider':'ollama','model':'fixture'}
            state=await_job(bench,bench.create('A small task tracker',config,config)['id'])
            bench.approve(state['id'],state['plan']);state=bench.load(state['id'])
            bench.apply(state,{'files':{'app.py':APP,'test_app.py':TEST}})
            state['next_task']=1;state['milestones']=[{'task':1}]
            bench.milestone_verifier=lambda *args:(_ for _ in ()).throw(RuntimeError('Verification worker unavailable'))
            with self.assertRaisesRegex(RuntimeError,'worker unavailable'):
                bench._verify_milestone(state,state['plan']['tasks'][0],0,{'runtime':'local'},threading.Event(),0)
            self.assertEqual(state['next_task'],0)


if __name__=='__main__':unittest.main()
