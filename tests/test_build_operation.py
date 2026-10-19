"""Ownership/resume, model observations, and selection regressions; no live keys."""
import copy
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from forge.build_contract import generation_contract
from forge.cloud import CloudSetup
from forge.core import Workbench
from forge.model_status import ModelStatus
from forge.models import ModelError
from tests.fixtures import PLAN, APP, TEST
from tests.test_cloud import CHAIN, state_for
from tests.test_workbench import ScriptedModels, await_job


class BuildOperationTests(unittest.TestCase):
    def test_resume_sixth_task_after_owned_file_rejection_keeps_checks(self):
        fixture=json.loads((Path(__file__).parent/'fixture_data/build-ownership-v1.json').read_text())
        plan=copy.deepcopy(PLAN);plan['tasks']=[copy.deepcopy(plan['tasks'][0]) for _ in range(6)]
        plan['tasks'][-1]['instructions']='Implement app documentation and create README.md and MANUAL-CHECKS.md.'
        models=ScriptedModels([plan,{'files':{'README.md':'replace contract','app.py':APP}},
            {'files':{'app.py':APP,'test_app.py':TEST,'APP-GUIDE.md':'# App guide\nLocal browser app'}}])
        with tempfile.TemporaryDirectory() as d:
            bench=Workbench(Path(d)/'projects',models)
            state=await_job(bench,bench.create('Build task tracker',CHAIN,CHAIN,cloud_consent=True)['id'])
            bench.approve(state['id'],state['plan'])
            state=bench.load(state['id']);state['next_task']=fixture['completed_tasks'];bench.save(state)
            before={n:v for n,v in bench.files(state['id']).items() if n.lower() in {'readme.md','checks.json','manual-checks.md'}}
            bench.start(state['id'],'build',{'execute':False,'cloud_consent':True,'repairs':0})
            state=await_job(bench,state['id'])
            self.assertEqual(state['status'],'generated',state.get('error'))
            self.assertEqual(state['next_task'],6)
            after=bench.files(state['id'])
            self.assertTrue(all(after[n]==v for n,v in before.items()))
            self.assertIn('APP-GUIDE.md',after)
            self.assertIn('file_ownership',models.calls[-2])
            self.assertEqual([r['provider'] for r in state['model_calls'][-2:]],['gemini','groq'])
            self.assertEqual(models.calls[-1]['response_mode'],'complete_files')
            self.assertFalse(state.get('checks'))

    def test_owned_file_rejection_remains_atomic_and_names_file(self):
        models=ScriptedModels([PLAN])
        with tempfile.TemporaryDirectory() as d:
            bench=Workbench(Path(d)/'projects',models)
            state=await_job(bench,bench.create('Build task tracker',{'provider':'ollama','model':'fixture'},{'provider':'ollama','model':'fixture'})['id'])
            bench.approve(state['id'],state['plan']);state=bench.load(state['id']);before=bench.files(state['id'])
            with self.assertRaisesRegex(ValueError,'CHECKS.json'):
                bench.apply(state,{'files':{'extra.js':'const neverWritten=1;','CHECKS.json':'[]'}})
            self.assertEqual(bench.files(state['id']),before)

    def test_ownership_payload_keeps_original_task_and_scope(self):
        payload={'current_task':{'instructions':'Create README.md'},'proposal':{'features':['Keep this']}}
        enriched=generation_contract(payload)
        self.assertEqual(enriched['current_task'],payload['current_task'])
        self.assertEqual(enriched['proposal'],payload['proposal'])
        self.assertNotIn('file_ownership',payload)
        self.assertIn('checks.json',enriched['file_ownership']['controller_owned'])

    def test_live_working_snapshot_and_finally_clears_on_failure(self):
        entered=threading.Event();release=threading.Event()
        class Client:
            def complete(self,system,prompt):
                entered.set();release.wait(5);raise ModelError('No access','model')
        with tempfile.TemporaryDirectory() as d:
            bench=Workbench(Path(d)/'projects',lambda *_:Client());state=state_for(bench)
            errors=[]
            def invoke():
                try:bench.call_model(state,'coder','fixture','{}',threading.Event())
                except ModelError as e:errors.append(e)
            worker=threading.Thread(target=invoke);worker.start();self.assertTrue(entered.wait(3))
            snap=bench.model_status.snapshot({},{});self.assertEqual(next(i for i in snap['items'] if i['id']=='gemini')['state'],'working')
            release.set();worker.join(5);self.assertFalse(worker.is_alive());self.assertTrue(errors)
            self.assertIsNone(bench.model_status.active)

    def test_recent_hard_failures_skipped_across_jobs_but_transports_can_retry(self):
        status=ModelStatus();status.finish('gemini','bad','model');self.assertTrue(status.avoid('gemini','bad'))
        status.finish('groq','slow','transport');self.assertFalse(status.avoid('groq','slow'))
        with patch('forge.model_status.time.time',return_value=10**12):self.assertFalse(status.avoid('gemini','bad'))
        status.reset();self.assertFalse(status.avoid('gemini','bad'))

    def test_status_has_all_clouds_local_embeddings_and_no_secret_echo(self):
        with patch.dict(os.environ,{'GEMINI_API_KEY':'fixture-secret'},clear=True):
            status=ModelStatus();status.finish('gemini','good','responded')
            snap=status.snapshot({}, {'connected':True,'models':['qwen3.5:9b','nomic-embed-text:latest','fixture-secret']})
            self.assertEqual(len(snap['items']),9)
            self.assertEqual(snap['items'][-1]['state'],'embedding')
            self.assertNotIn('fixture-secret',json.dumps(snap))
            self.assertEqual(next(i for i in snap['items'] if i['id']=='gemini')['state'],'responded')

    def test_selection_prefers_newer_coding_family_over_old_small_coder(self):
        self.assertLess(CloudSetup.rank('qwen/qwen3-coder-flash','coder'),CloudSetup.rank('qwen/qwen-2.5-coder-32b-instruct','coder'))
        self.assertLess(CloudSetup.rank('openai/gpt-oss-120b','coder'),CloudSetup.rank('deepseek-ai/deepseek-coder-6.7b-instruct','coder'))

    def test_automatic_selection_avoids_observed_hard_failure(self):
        with tempfile.TemporaryDirectory() as d,patch.object(CloudSetup,'check',return_value={}):
            setup=CloudSetup(d);setup.checked={'gemini':{'status':'catalogue_available','models':['gemini-3-flash','gemini-2.5-flash']}}
            routes=setup.automatic(avoid=lambda p,m:m=='gemini-3-flash')
            self.assertEqual(routes['planner']['model'],'gemini-2.5-flash')

    def test_cancelled_response_clears_working_without_acceptance(self):
        cancel=threading.Event()
        class Client:
            def complete(self,system,prompt):cancel.set();return PLAN
        with tempfile.TemporaryDirectory() as d:
            bench=Workbench(Path(d)/'projects',lambda *_:Client());state=state_for(bench)
            with self.assertRaises(InterruptedError):bench.call_model(state,'coder','fixture','{}',cancel)
            self.assertIsNone(bench.model_status.active)
            self.assertFalse(state['model_calls'][-1]['success'])

    def test_transient_failure_does_not_hide_missing_account_configuration(self):
        with patch.dict(os.environ,{'CLOUDFLARE_API_TOKEN':'fixture'},clear=True):
            status=ModelStatus()
            snap=status.snapshot({}, {})
            row=next(i for i in snap['items'] if i['id']=='cloudflare')
            self.assertEqual(row['state'],'missing_configuration')
