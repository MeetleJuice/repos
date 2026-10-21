"""Tiny Wins diagnostic-derived regressions; replies are controlled fixtures."""
import copy
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from forge.core import Workbench
from forge.models import ModelError
from forge.tasks import task_packet
from tests.fixtures import APP,TEST
from tests.test_workbench import ScriptedModels,await_job
from tests.test_task_contracts import structured_plan


class TaskResponseRecoveryTests(unittest.TestCase):
    def setup_case(self,temp,replies):
        models=ScriptedModels([structured_plan(),*replies]);bench=Workbench(Path(temp)/'projects',models)
        config={'provider':'ollama','model':'coder','fallbacks':[{'provider':'ollama','model':'backup'}]}
        state=await_job(bench,bench.create('Build a task tracker',config,config)['id'])
        bench.approve(state['id'],state['plan']);state=bench.load(state['id'])
        bench.apply(state,{'files':{'app.py':APP,'test_app.py':TEST}})
        payload={'proposal':state['plan'],'current_task':state['plan']['tasks'][0],
                 'task_packet':task_packet(state['plan'],0,0),'files':bench.context_files(state['id'])}
        return bench,models,state,payload

    def test_bad_source_does_not_ban_model_from_changed_context(self):
        bad={'files':{'app.py':'def broken(:\n'}}
        with tempfile.TemporaryDirectory() as temp:
            bench,models,state,payload=self.setup_case(temp,[bad,bad,{'files':{'app.py':APP+'\n# backup saved\n'}},{'files':{'app.py':APP+'\n# new context saved\n'}}])
            frozen=copy.deepcopy(state['plan']);checks=bench.files(state['id'])['CHECKS.json']
            bench.generate_and_apply(state,payload,threading.Event())
            payload['files']=bench.context_files(state['id'])
            bench.generate_and_apply(state,payload,threading.Event(),repair=True)
            self.assertEqual([r['model'] for r in state['model_calls'] if r['role']=='coder'],['coder','coder','backup','coder'])
            self.assertEqual(state['plan'],frozen);self.assertEqual(bench.files(state['id'])['CHECKS.json'],checks)
            self.assertNotIn('ollama/coder',state.get('job_model_rejections',{}))

    def test_bad_exact_edit_gets_scoped_same_model_complete_file_correction(self):
        bad={'edits':[{'file':'app.py','search':'THIS TEXT NEVER EXISTED','replace':'replacement'}]}
        with tempfile.TemporaryDirectory() as temp:
            bench,models,state,payload=self.setup_case(temp,[bad,{'files':{'app.py':APP+'\n# corrected exact edit\n'}}])
            bench.generate_and_apply(state,payload,threading.Event())
            self.assertEqual([r['model'] for r in state['model_calls'] if r['role']=='coder'],['coder','coder'])
            self.assertEqual(models.calls[-1]['response_mode'],'complete_files')
            self.assertEqual(models.calls[-1]['task_packet'],payload['task_packet'])

    def test_malformed_json_exclusion_is_also_response_scoped(self):
        with tempfile.TemporaryDirectory() as temp:
            bench,models,state,payload=self.setup_case(temp,[ModelError('Bad JSON','parse_error'),{'files':{'app.py':APP+'\n# backup\n'}},{'files':{'app.py':APP+'\n# next context\n'}}])
            bench.generate_and_apply(state,payload,threading.Event())
            payload['files']=bench.context_files(state['id'])
            bench.generate_and_apply(state,payload,threading.Event())
            self.assertEqual([r['model'] for r in state['model_calls'] if r['role']=='coder'],['coder','backup','coder'])

    def test_failed_truncation_continuation_still_gets_same_model_shortening(self):
        cut=ModelError('Cut output','truncated_output');cut.partial_content='{"files":'
        with tempfile.TemporaryDirectory() as temp:
            bench,models,state,payload=self.setup_case(temp,[cut,ModelError('Incomplete suffix','parse_error'),{'files':{'app.py':APP+'\n# shortened\n'}}])
            from forge.prompts import CODE
            import json
            bench.call_model(state,'coder',CODE,json.dumps(payload),threading.Event(),response_rejections=set())
            self.assertEqual([r['model'] for r in state['model_calls'] if r['role']=='coder'],['coder','coder','coder'])
            self.assertEqual([r['recovery_path'] for r in state['model_calls'] if r['role']=='coder'],['initial','continuation','shortening'])

    def test_empty_repair_gets_actionable_correction_without_advancing_task(self):
        with tempfile.TemporaryDirectory() as temp:
            bench,models,state,payload=self.setup_case(temp,[{'files':{'app.py':APP}},{'files':{'app.py':APP+'\n# repaired candidate\n'}}])
            cursor=state['next_task'];bench.generate_and_apply(state,payload,threading.Event(),repair=True)
            self.assertEqual([r['model'] for r in state['model_calls'] if r['role']=='coder'],['coder','coder'])
            self.assertEqual(state['next_task'],cursor)
            self.assertIn('Task produced no source changes',models.calls[-1]['response_validation_error'])

    def test_static_repair_supplies_a_scoped_defect_contract(self):
        with tempfile.TemporaryDirectory() as temp:
            bench,models,state,payload=self.setup_case(temp,[{'files':{'test_app.py':TEST+'\n# corrected request construction\n'}}])
            state['pending_task']={'cursor':0}
            issue='test_app.py: urlopen does not accept headers= or method=.'
            with patch('forge.core.preflight',side_effect=[{'passed':False,'issues':[issue]},{'passed':True,'issues':[]}]):
                self.assertEqual(bench._inspect_and_repair(state,threading.Event(),1),0)
            brief=models.calls[-1]['repair_brief']
            self.assertEqual(brief['reported_defects'],[issue])
            self.assertEqual(brief['editable_files'],payload['task_packet']['files'])
            self.assertIn('urllib.request.Request',brief['http_test_rule'])
            self.assertIn('never filenames',brief['response_rule'])


if __name__=='__main__':unittest.main()
