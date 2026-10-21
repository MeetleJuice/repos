"""Production-journal regressions: preserve scope, checks, routes and output floors."""
import copy
import json
from pathlib import Path
import tempfile
import threading
import unittest
import hashlib
from unittest.mock import patch
from forge.core import Workbench
from forge.models import ModelError
from forge.tasks import task_packet
from forge.prompts import CODE
from tests.test_cloud import state_for
from tests.test_task_contracts import structured_plan
from tests.test_workbench import ScriptedModels,await_job
from tests.fixtures import APP,TEST
from forge.capabilities import CapabilityRegistry
from forge.routing import validate_options
from forge.build_contract import builder_profile,focused_handoff
from forge.guided import validate_batch,TASKS_PROMPT
from forge.models import ModelClient,request_schema
from forge.model_inventory import refresh_local_limits,limit_rows
from tests.test_guided_planning import responses


class CapacityDeliveryTests(unittest.TestCase):
    def test_uploaded_diagnostic_fixture_is_frozen_and_labels_mock_source(self):
        path=Path(__file__).parent/'fixture_data/watchlist-delivery-v1.json'
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),'114bb832f61d4b4b0484321b4a390396803c67177b9757784787276dd45babf4')
        data=json.loads(path.read_text());self.assertEqual(data['logged_request_lines'],33)
        self.assertIn('not captured provider replies',data['provenance'])
    def test_profile_keeps_saved_routes_and_rejects_a_wide_guided_batch(self):
        route={'provider':'ollama','model':'coder','options':{'num_ctx':16384,'num_predict':4096}}
        before=copy.deepcopy(route);profile=builder_profile(route,CapabilityRegistry())
        self.assertEqual(route,before);self.assertEqual(profile['max_editable_files'],2)
        self.assertEqual(profile['max_feature_indexes'],1)
        self.assertEqual(profile['smallest_output_ceiling'],4096)
        outline,batch,_=responses();wide=copy.deepcopy(batch)
        wide['tasks'][0]['files']=['app.py','db.py','test_app.py']
        with self.assertRaisesRegex(ValueError,'too broad'):validate_batch(wide,outline,[],[0,1],4,profile)
        validate_batch(batch,outline,[],[0,1],4,profile)

    def test_scoped_native_schema_prevents_writes_to_unapproved_files(self):
        plan=structured_plan();packet=task_packet(plan,0,0)
        payload={'task_packet':packet,'files':{'app.py':APP}}
        with patch('forge.models.request_json',return_value={'message':{'content':json.dumps({'files':{'app.py':APP}})},'done':True}) as wire:
            ModelClient('ollama','fixture').complete(CODE,json.dumps(payload))
        schema=wire.call_args.args[1]['format'];files=schema['properties']['files']
        self.assertFalse(files['additionalProperties'])
        self.assertEqual(set(files['properties']),set(packet['files']))
        self.assertEqual(schema['properties']['edits']['items']['properties']['file']['enum'],packet['files'])
        from forge.schemas import CODE_SCHEMA
        self.assertNotIn('enum',CODE_SCHEMA['properties']['edits']['items']['properties']['file'])
        self.assertEqual(payload['task_packet'],packet)

    def test_guided_readiness_rejects_unimportable_tests_and_missing_producer_dependency(self):
        outline,batch,_=responses()
        profile=builder_profile({'provider':'ollama','model':'fixture'},CapabilityRegistry())
        nested=copy.deepcopy(batch);nested['tasks'][1]['files']=['tests/test_movies.py']
        with self.assertRaisesRegex(ValueError,'would not be collected'):
            validate_batch(nested,outline,[],[0,1],4,profile)
        ready=copy.deepcopy(profile);ready['available_files']=['tests/__init__.py']
        validate_batch(nested,outline,[],[0,1],4,ready)
        missing=copy.deepcopy(batch);missing['tasks'][1]['interfaces']=[{'file':'app.py','symbol':'create_server','contract':'Existing server factory'}]
        missing['tasks'][1]['depends_on']=[]
        with self.assertRaisesRegex(ValueError,'must depend on earlier'):
            validate_batch(missing,outline,[],[0,1],4,profile)

    def test_batch_schema_and_budget_use_this_stage_without_lowering_floor(self):
        profile=builder_profile({'provider':'ollama','model':'fixture'},CapabilityRegistry())
        payload={'planning_stage':'tasks','max_new_tasks':2,'builder_profile':profile}
        schema=request_schema(TASKS_PROMPT,json.dumps(payload))
        self.assertEqual(schema['properties']['tasks']['items']['properties']['files']['maxItems'],2)
        self.assertEqual(schema['properties']['tasks']['items']['properties']['feature_indexes']['maxItems'],1)
        budget=CapabilityRegistry().reserve('gemini','gemini-3.8-flash',dict(validate_options({})),TASKS_PROMPT,json.dumps(payload))
        self.assertEqual(budget.text_output_tokens,8192)

    def test_unknown_output_is_not_a_claimed_published_limit_or_minimum(self):
        registry=CapabilityRegistry();registry.discover_models('groq',[{'id':'fixture','context_window':32768}])
        row=registry.describe('groq','fixture')
        self.assertEqual(row['model_context_limit'],32768)
        self.assertIsNone(row['model_output_limit']);self.assertTrue(row['estimated'])
        self.assertIsNone(row['minimum_output_tokens'])

    def test_local_metadata_caps_context_and_never_retains_private_modelfile(self):
        with tempfile.TemporaryDirectory() as temp:
            registry=CapabilityRegistry(Path(temp)/'caps.json')
            response={'model_info':{'qwen.context_length':8192},'modelfile':'PRIVATE LOCAL PATH','template':'PRIVATE TEMPLATE'}
            with patch('forge.models.request_json',return_value=response) as wire:
                refresh_local_limits(registry,['coder','nomic-embed-text:latest'])
                self.assertEqual(wire.call_count,2)
                refresh_local_limits(registry,['coder','nomic-embed-text:latest'])
                self.assertEqual(wire.call_count,2)
                self.assertTrue(all(call.args[0].endswith('/api/show') for call in wire.call_args_list))
            saved=registry.path.read_text();self.assertNotIn('PRIVATE',saved)
            cap=registry.get('ollama','coder',{'num_ctx':32768,'num_predict':8192})
            self.assertEqual(cap.max_context_tokens,8192);self.assertEqual(cap.max_output_tokens,8191)
            rows=limit_rows(registry,{'ollama':{'models':['coder','nomic-embed-text:latest']}},{},{})
            self.assertFalse(rows[-1]['generation_eligible'])

    def test_handoff_preserves_original_task_and_never_enriches_legacy_payload(self):
        legacy={'files':{},'note':'项目'};self.assertEqual(focused_handoff(legacy,{}),legacy)
        packet=task_packet(structured_plan(),0,0);payload={'task_packet':packet,'current_task':{'instructions':'Keep exactly this'}}
        enriched=focused_handoff(payload,{'app.py':APP,'test_foundation.py':'frozen'})
        self.assertEqual(enriched['task_packet'],packet)
        self.assertEqual(enriched['current_task'],payload['current_task'])
        self.assertIn('test_foundation.py',enriched['builder_handoff']['read_only_files'])

    def test_all_prior_rejections_have_a_nonempty_exhaustion_explanation(self):
        with tempfile.TemporaryDirectory() as temp:
            bench=Workbench(Path(temp)/'projects',ScriptedModels([]));state=state_for(bench)
            state['coder']={'provider':'ollama','model':'first','fallbacks':[{'provider':'ollama','model':'second'}]}
            state['job_model_rejections']={'ollama/first':'response_rejected','ollama/second':'transport'}
            with self.assertRaisesRegex(ModelError,'ollama/first.*response_rejected.*ollama/second.*transport'):
                bench.call_model(state,'coder',CODE,'{}',threading.Event())

    def test_account_quota_skips_same_provider_alternate_without_a_second_transport(self):
        called=[]
        class Client:
            def __init__(self,provider,model):self.provider=provider;self.model=model
            def complete(self,*_):
                called.append((self.provider,self.model))
                if self.provider=='requesty':raise ModelError('Account has no credit','quota',http_status=402)
                return {'files':{'app.py':'value=1\n'}}
        with tempfile.TemporaryDirectory() as temp:
            bench=Workbench(Path(temp)/'projects',Client);state=state_for(bench)
            state['coder']={'provider':'requesty','model':'first','fallbacks':[{'provider':'requesty','model':'second'},{'provider':'ollama','model':'local'}]}
            bench.call_model(state,'coder',CODE,'{}',threading.Event())
            self.assertEqual(called,[('requesty','first'),('ollama','local')])

    def test_scoped_syntax_rejection_gets_one_same_model_exact_edit_correction(self):
        first=APP.splitlines()[0]
        models=ScriptedModels([structured_plan(),{'files':{'app.py':'def broken(:\n'}},
            {'edits':[{'file':'app.py','search':first,'replace':first+'\n# focused correction'}]}])
        with tempfile.TemporaryDirectory() as temp:
            bench=Workbench(Path(temp)/'projects',models)
            config={'provider':'ollama','model':'coder','fallbacks':[{'provider':'ollama','model':'backup'}]}
            state=await_job(bench,bench.create('Build a small task tracker',config,config)['id'])
            bench.approve(state['id'],state['plan']);state=bench.load(state['id'])
            bench.apply(state,{'files':{'app.py':APP,'test_app.py':TEST}})
            before=bench.files(state['id']);frozen=copy.deepcopy(state['plan'])
            payload={'proposal':state['plan'],'current_task':state['plan']['tasks'][0],
                     'task_packet':task_packet(state['plan'],0,0),'files':bench.context_files(state['id'])}
            bench.generate_and_apply(state,payload,threading.Event())
            self.assertEqual([r['model'] for r in state['model_calls'] if r['role']=='coder'],['coder','coder'])
            self.assertEqual(state['plan'],frozen)
            self.assertIn('# focused correction',bench.files(state['id'])['app.py'])
            self.assertEqual(before['CHECKS.json'],bench.files(state['id'])['CHECKS.json'])
            self.assertEqual(models.calls[-1]['response_mode'],'focused_changes')
            self.assertEqual(models.calls[-1]['task_packet'],payload['task_packet'])


if __name__=='__main__':unittest.main()
