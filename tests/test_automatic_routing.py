"""Controlled reproductions; no live cloud calls or quality claims."""
import copy
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from forge.cloud import CloudSetup
from forge.core import Workbench
from forge.models import ModelError, ModelClient, output_contract
from forge.prompts import PLAN as PROMPT
from forge.routing import validate_config
from tests.fixtures import PLAN
from tests.test_cloud import CHAIN, state_for
from tests.test_provider_pool import ENV, catalogue
from tests.test_workbench import ScriptedModels, await_job


class AutomaticRoutingTests(unittest.TestCase):
    def test_frozen_josh_reproduction_advances_after_one_correction(self):
        fixture=json.loads((Path(__file__).parent/'fixture_data/planner-semantic-routing-v1.json').read_text())
        self.assertEqual(fixture['expected']['openrouter_requests'],2)
        replies=[ModelError('Model access denied',step['category']) if 'category' in step else copy.deepcopy(PLAN if step['response']=='tests.fixtures.PLAN' else step['response']) for step in fixture['sequence']]
        models=ScriptedModels(replies)
        config={'provider':'gemini','model':'unavailable','fallbacks':[
            {'provider':'openrouter','model':'free'},{'provider':'nvidia','model':'instruct'}]}
        with tempfile.TemporaryDirectory() as d:
            bench=Workbench(Path(d)/'projects',models)
            state=await_job(bench,bench.create('Build Josh dashboard',config,config,cloud_consent=True)['id'])
            self.assertEqual(state['status'],'proposed',state.get('error'))
            records=state['model_calls']
            self.assertEqual([r['provider'] for r in records],['gemini','openrouter','openrouter','nvidia'])
            self.assertEqual([r.get('failure_class') for r in records[:3]],['provider_unavailable','schema_error','schema_error'])
            self.assertEqual(records[2]['recovery_path'],'schema_correction')
            self.assertEqual(records[1]['error_category'],'schema_error')
            self.assertTrue(records[-1]['proposal_valid'])
            self.assertFalse(state['approved']);self.assertEqual(bench.context_files(state['id']),{})
            self.assertIn('validation_error',models.calls[2])

    def test_exhausted_invalid_pool_is_not_restarted(self):
        models=ScriptedModels([{}]*6)
        with tempfile.TemporaryDirectory() as d:
            bench=Workbench(Path(d)/'projects',models)
            state=await_job(bench,bench.create('Build task tracker',CHAIN,CHAIN,cloud_consent=True)['id'])
            self.assertEqual(state['status'],'error');self.assertEqual(len(models.calls),6)
            self.assertTrue(all(r['failure_class']=='schema_error' for r in state['model_calls']))
            self.assertFalse(state['approved'])

    def test_correction_can_succeed_without_advancing(self):
        models=ScriptedModels([{},PLAN])
        with tempfile.TemporaryDirectory() as d:
            bench=Workbench(Path(d)/'projects',models)
            state=await_job(bench,bench.create('Build task tracker',CHAIN,CHAIN,cloud_consent=True)['id'])
            self.assertEqual(state['status'],'proposed');self.assertEqual(len(models.calls),2)
            self.assertEqual([r['provider'] for r in state['model_calls']],['gemini','gemini'])

    def test_automatic_catalogues_rank_role_models_and_persist_without_secrets(self):
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,ENV,clear=True),patch('forge.cloud.request_json',side_effect=catalogue):
            setup=CloudSetup(d)
            routes=setup.automatic(['qwen2.5-coder:7b','qwen3-embedding:0.6b'])
            for role,config in routes.items():
                validate_config(config)
                chain=[config,*config.get('fallbacks',[])]
                self.assertLessEqual(len(chain),16)
                self.assertEqual(chain[-1]['model'],'qwen2.5-coder:7b')
                self.assertEqual(CloudSetup(d).profile(role),config)
            self.assertFalse(any(secret in setup.path.read_text() for secret in ENV.values()))
            self.assertLess(setup.rank('Qwen/Qwen3-Coder:free','coder'),setup.rank('openrouter/free','coder'))

    def test_alternate_models_and_role_specific_ranking(self):
        with tempfile.TemporaryDirectory() as d,patch.object(CloudSetup,'check',return_value={}):
            setup=CloudSetup(d)
            setup.checked={'requesty':{'status':'catalogue_available','models':['qwen-coder','gemini-flash']}}
            routes=setup.automatic()
            self.assertEqual(routes['coder']['model'],'qwen-coder')
            self.assertEqual(routes['planner']['model'],'gemini-flash')
            self.assertEqual(routes['coder']['fallbacks'][0]['model'],'gemini-flash')

    def test_automatic_local_only_and_no_available_service(self):
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{},clear=True):
            setup=CloudSetup(d)
            with self.assertRaisesRegex(ValueError,'No eligible'):setup.automatic()
            routes=setup.automatic(['qwen2.5-coder:7b'])
            self.assertEqual(routes['planner']['provider'],'ollama')
            self.assertNotIn('fallbacks',routes['planner'])

    def test_request_parameter_retry_does_not_disable_json_validation(self):
        models=ScriptedModels([ModelError('Bad request','request'),ModelError('Invalid JSON','format'),PLAN])
        with tempfile.TemporaryDirectory() as d:
            bench=Workbench(Path(d)/'projects',models);state=state_for(bench)
            self.assertEqual(bench.call_model(state,'coder','code','{}',threading.Event()),PLAN)
            self.assertEqual([r['provider'] for r in state['model_calls']],['gemini','gemini','groq'])
            self.assertEqual(state['model_calls'][1]['recovery_path'],'json_compatibility')
            self.assertEqual(state['model_calls'][1]['failure_class'],'parse_error')

    def test_job_rejected_model_is_not_retried_on_next_coding_task(self):
        models=ScriptedModels([ModelError('Missing model','model'),PLAN,PLAN])
        with tempfile.TemporaryDirectory() as d:
            bench=Workbench(Path(d)/'projects',models);state=state_for(bench)
            for _ in range(2):bench.call_model(state,'coder','code','{}',threading.Event())
            self.assertEqual([r['provider'] for r in state['model_calls']],['gemini','groq','groq'])

    def test_planner_attempt_budget_prevents_unbounded_retry(self):
        models=ScriptedModels([PLAN])
        with tempfile.TemporaryDirectory() as d:
            bench=Workbench(Path(d)/'projects',models);state=state_for(bench);state['job_inference_attempts']=24
            with self.assertRaisesRegex(ModelError,'24-attempt'):bench.call_model(state,'planner',PROMPT,'{}',threading.Event())
            self.assertFalse(models.calls)

    def test_authoritative_contract_is_sent_and_not_a_wrapper(self):
        with patch('forge.models.request_json',return_value={'message':{'content':json.dumps(PLAN)}}) as request:
            client=ModelClient('ollama','fixture');client.complete(PROMPT,'{}')
            system=request.call_args.args[1]['messages'][0]['content']
            self.assertEqual(system,output_contract(PROMPT))
            self.assertIn('AUTHORITATIVE ROOT OUTPUT CONTRACT',system)
            self.assertIn('manual_checks',system)
