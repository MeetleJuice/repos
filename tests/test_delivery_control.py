"""Delivery contracts, focused source, interruption replay and local calibration."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from forge.calibration import calibrate
from forge.core import Workbench
from forge.execution import task_board, resume_problem, seal_checkpoint
from forge.focus import prepare_context, retrieve_context, interface_context
from forge.models import ModelClient
from tests.test_task_contracts import structured_plan
from tests.test_workbench import ScriptedModels,await_job
from tests.fixtures import APP,TEST


def packet():return {'structured':True,'files':['app.py','test_app.py']}


class DeliveryControlTests(unittest.TestCase):
    def test_frozen_regressions(self):
        root=Path(__file__).parent/'fixture_data'
        for entry in json.loads((root/'frozen-regressions-v13.json').read_text())['sets']:
            self.assertEqual(hashlib.sha256((root/entry['file']).read_bytes()).hexdigest(),entry['sha256'])

    def test_focused_context_complete_unicode_dependencies_and_explicit_omissions(self):
        files={'app.py':'import db\n# café 蚂蚁\n','db.py':'def query():\n    return []\n','test_db.py':'import db\n','unused.js':'x'*10000,'extra.css':'y'*5000}
        payload={'proposal':{'context_policy':'focused_v1'},'current_task':{'instructions':'Keep every original value'},'files':copy.deepcopy(files),'task_packet':packet()}
        result=prepare_context(payload,files)
        self.assertEqual(result['files']['app.py'],files['app.py']);self.assertEqual(result['files']['db.py'],files['db.py'])
        self.assertIn('test_db.py',result['files']);self.assertNotIn('unused.js',result['files'])
        self.assertEqual(result['task_context']['omitted_files'],['extra.css','unused.js'])
        self.assertEqual(payload['files'],files);self.assertEqual(result['current_task'],payload['current_task'])
        result=retrieve_context({'request_context':['unused.js']},result,files);self.assertEqual(result['files']['unused.js'],files['unused.js'])
        result=retrieve_context({'request_context':['extra.css']},result,files)
        with self.assertRaisesRegex(ValueError,'limit'):retrieve_context({'request_context':['db.py']},result,files)
        self.assertEqual(prepare_context({'files':files},files),{'files':files})

    def test_focused_packet_fits_local_budget_that_full_source_exceeds(self):
        from forge.capabilities import CapabilityRegistry
        files={'app.py':'value = 1\n','unused.js':'x'*30000}
        payload={'proposal':{'context_policy':'focused_v1'},'task_packet':packet(),'files':files}
        focused=prepare_context(payload,files);options={'num_ctx':16384,'num_predict':8192}
        registry=CapabilityRegistry()
        with self.assertRaises(ValueError):registry.reserve_builder('ollama','fixture',options,'system',json.dumps(payload))
        budget=registry.reserve_builder('ollama','fixture',options,'system',json.dumps(focused))
        self.assertLess(budget.input_estimate_tokens,8192)
        self.assertEqual(focused['task_context']['omitted_files'],['unused.js'])

    def test_invalid_context_requests_and_actual_interface_signature(self):
        files={'app.py':'def query(title, limit=10):\n    return []\n','hidden.py':'x=1\n'}
        task={'interfaces':[{'file':'app.py','symbol':'query','contract':'returns list'}]}
        result=interface_context(task,files)
        self.assertEqual(result[0]['observed_python_signature'],'query(title, limit=10)')
        context=prepare_context({'proposal':{'context_policy':'focused_v1'},'task_packet':packet()},files)
        for response in [{'request_context':['../secret.env']},{'request_context':['hidden.py'],'files':{}},{'request_context':[]}]:
            with self.assertRaises(ValueError):retrieve_context(response,context,files)

    def setup_project(self,root,models,plan=None):
        bench=Workbench(root/'projects',models);config={'provider':'ollama','model':'fixture'}
        state=await_job(bench,bench.create('Build a task tracker',config,config)['id']);bench.approve(state['id'],state['plan'])
        return bench,bench.load(state['id'])

    def test_context_round_trip_does_not_modify_unrequested_source(self):
        plan=structured_plan();plan['context_policy']='focused_v1'
        models=ScriptedModels([plan,{'request_context':['notes.py']},{'files':{'app.py':APP,'test_app.py':TEST}}])
        with tempfile.TemporaryDirectory() as d:
            bench,state=self.setup_project(Path(d),models)
            bench.apply(state,{'files':{'app.py':APP+'\n# initial source\n','notes.py':'# original café\nvalue = 1\n'}})
            bench.start(state['id'],'build',{'execute':False,'repairs':0});state=await_job(bench,state['id'])
            self.assertEqual(state['status'],'generated',state.get('error'))
            self.assertNotIn('notes.py',models.calls[-2]['files']);self.assertIn('notes.py',models.calls[-1]['files'])
            self.assertEqual(state['generation_stats']['context_retrievals'],1)
            self.assertEqual(bench.files(state['id'])['notes.py'],'# original café\nvalue = 1\n')

    def test_saved_candidate_survives_stop_and_new_workbench_without_model_replay(self):
        models=ScriptedModels([structured_plan(),{'files':{'app.py':APP,'test_app.py':TEST}}])
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);bench,state=self.setup_project(root,models)
            original=bench.apply
            def apply_and_stop(state,response,repair=False):
                original(state,response,repair=repair);bench.jobs[state['id']][1].set()
            bench.apply=apply_and_stop
            bench.start(state['id'],'build',{'execute':False,'repairs':0});state=await_job(bench,state['id'])
            self.assertEqual(state['status'],'stopped',state.get('error'));self.assertEqual(state['next_task'],0)
            self.assertEqual(state['pending_task']['phase'],'candidate_saved')
            state['status']='building';bench.save(state)  # Simulate restart with a durable candidate and an active-run marker.
            before_calls=len(models.calls)
            resumed=Workbench(root/'projects',models)
            self.assertEqual(resumed.load(state['id'])['status'],'interrupted')
            resumed.start(state['id'],'build',{'execute':False,'repairs':0});state=await_job(resumed,state['id'])
            self.assertEqual(state['status'],'generated',state.get('error'));self.assertEqual(len(models.calls),before_calls)
            self.assertEqual(state['next_task'],1);self.assertNotIn('pending_task',state)
            self.assertTrue(state['task_receipts'][0]['source_changed']);self.assertIn('test_app.py',state['task_receipts'][0]['changed_files'])

    def test_source_drift_blocks_new_calls_and_adoption_keeps_cursor_and_checks_pending(self):
        models=ScriptedModels([structured_plan(),{'files':{'app.py':APP,'test_app.py':TEST}}])
        with tempfile.TemporaryDirectory() as d:
            bench,state=self.setup_project(Path(d),models)
            bench.start(state['id'],'build',{'execute':False,'repairs':0});state=await_job(bench,state['id'])
            (bench.directory(state['id'])/'source/app.py').write_text(APP+'\n# external edit\n')
            calls=len(models.calls);bench.start(state['id'],'build',{'execute':False,'repairs':0});state=await_job(bench,state['id'])
            self.assertEqual(state['status'],'needs_attention');self.assertEqual(len(models.calls),calls)
            board=bench.workflow(state['id'])['task_board'];self.assertIn('files changed',board['resume_problem'])
            bench.adopt_resume_baseline(state['id']);state=bench.load(state['id'])
            self.assertEqual(state['next_task'],1);self.assertFalse(state.get('checks'));self.assertFalse(resume_problem(state,bench.context_files(state['id'])))
            state['plan']['summary']='tampered';bench.save(state)
            with self.assertRaisesRegex(ValueError,'plan or task position'):bench.adopt_resume_baseline(state['id'])

    def test_board_distinguishes_ready_waiting_saved_and_full_source_docs(self):
        plan=structured_plan();second=copy.deepcopy(plan['tasks'][0]);second['depends_on']=[0];plan['tasks'].append(second)
        state={'id':'a'*32,'plan':plan,'approved':True,'next_task':0,'status':'approved'}
        board=task_board(state,{'app.py':'source'})
        self.assertEqual(board['tasks'][0]['state'],'Ready to build');self.assertEqual(board['tasks'][1]['blocked_by'],[1])
        state['next_task']=1;seal_checkpoint(state,{'app.py':'source'})
        self.assertFalse(task_board(state,{'app.py':'source','README.md':'controller doc'})['resume_problem'])
        self.assertIn('checks pending',task_board(state,{'app.py':'source'})['tasks'][0]['state'])

    def test_actual_milestone_receipt_is_prefix_limited_and_becomes_historical(self):
        plan=structured_plan();plan['tasks'][0]['check_indexes']=list(range(len(plan['checks'])))
        second=copy.deepcopy(plan['tasks'][0]);second.update(title='Add app usage notes',files=['APP-GUIDE.md'],depends_on=[0],check_indexes=[])
        plan['tasks'].append(second)
        models=ScriptedModels([plan,{'files':{'app.py':APP,'test_app.py':TEST}},{'files':{'APP-GUIDE.md':'# Usage\nRun the app locally and create tasks.\n'}}])
        with tempfile.TemporaryDirectory() as d:
            bench,state=self.setup_project(Path(d),models)
            bench.start(state['id'],'build',{'execute':True,'consent':True,'runtime':'local','repairs':0,'milestones':True})
            state=await_job(bench,state['id'])
            self.assertEqual(state['status'],'verified',state.get('error'))
            evidence=state['task_receipts'][0]['milestone_evidence']
            self.assertTrue(evidence['passed']);self.assertEqual(evidence['http_prefix_count'],len(plan['checks']))
            self.assertFalse(bench.workflow(state['id'])['task_board']['tasks'][0]['milestone_current'])
            self.assertFalse(state['task_receipts'][0]['behavior_verified'])

    def test_local_calibration_fixed_cases_no_project_execution_or_route_change(self):
        results=[{'message':{'content':'{"answer":7}'}},{'message':{'content':json.dumps({'edits':[{'file':'sample.py','search':'a + b','replace':'a - b'}]})}}]
        with tempfile.TemporaryDirectory() as d,patch('forge.models.request_json',side_effect=results) as request:
            report=calibrate('fixture',Path(d)/'local-calibration-v1.json')
            self.assertTrue(report['passed']);self.assertEqual(request.call_count,2)
            self.assertTrue(all('127.0.0.1:11434' in call.args[0] for call in request.call_args_list))
            self.assertTrue(all(call.args[1]['options']['num_ctx']==4096 for call in request.call_args_list))
            self.assertTrue(all(call.args[1]['options']['num_predict']==1024 for call in request.call_args_list))
            self.assertIn('Does not prove',report['meaning'])
