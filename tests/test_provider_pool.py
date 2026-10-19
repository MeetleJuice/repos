"""Seven-provider contracts and bounded recovery using controlled responses only."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from forge.providers import PROVIDERS, CLOUD_ORDER, KEYS, key_for, endpoint
from forge.credentials import CredentialStore, parse_dotenv
from forge.cloud import CloudSetup
from forge.models import ModelClient, ModelError
from forge.core import Workbench
from forge.routing import validate_config
from forge.prompts import PLAN as PLAN_SYSTEM, CODE
from forge.contracts import validate_structure
from forge.history import redact
from tests.fixtures import PLAN
from tests.test_cloud import state_for
from tests.test_workbench import ScriptedModels

ENV = {key:'fixture-'+key.lower() for key in KEYS}
ENV['CLOUDFLARE_ACCOUNT_ID']='a'*32
MODELS={'gemini':'gemini-2.5-flash','groq':'llama-3.3-70b-versatile','cloudflare':'@cf/meta/llama-3.1-8b-instruct',
        'openrouter':'openrouter/free','nvidia':'meta/llama-3.3-70b-instruct','requesty':'openai/gpt-4.1-mini','huggingface':'openai/gpt-oss-120b'}


def catalogue(url, payload=None, headers=None, timeout=10):
    if url.endswith('/whoami-v2'):return {'name':'fixture-user'}
    if url.endswith('/key'):return {'data':{}}
    if 'googleapis' in url:return {'models':[{'name':'models/'+MODELS['gemini'],'supportedGenerationMethods':['generateContent'],'outputTokenLimit':65536,'inputTokenLimit':1048576}]}
    if 'cloudflare' in url:return {'success':True,'result':[{'name':MODELS['cloudflare'],'task':{'name':'Text Generation'}}]}
    provider = next(p for p in CLOUD_ORDER if p in url)
    return {'data':[{'id':MODELS[provider]}]}


class ProviderPoolTests(unittest.TestCase):
    def test_all_keys_and_account_import_without_echo_or_shell_execution(self):
        text='\n'.join(['GOOGLE_API_KEY=fixture-gemini','GROQ_KEY=fixture-groq','CF_API_TOKEN=fixture-cloudflare',
                        'CF_ACCOUNT_ID='+'a'*32,'OPENROUTER_KEY=fixture-openrouter','NVIDIA_NIM_API_KEY=fixture-nvidia',
                        'REQUESTY_KEY=fixture-requesty','HF_TOKEN=fixture-hf','PATH=must-not-load','X=$(execute)'])
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{},clear=True):
            store=CredentialStore(Path(d));status=store.import_text(text)
            self.assertEqual(len(status['keys']),7);self.assertTrue(all(status['keys'].values()))
            self.assertTrue(status['configuration']['CLOUDFLARE_ACCOUNT_ID'])
            self.assertNotIn('fixture-',json.dumps(status));self.assertNotIn('PATH',parse_dotenv(text))
            self.assertEqual(key_for('huggingface'),'fixture-hf')
            self.assertEqual(key_for('cloudflare'),'fixture-cloudflare')
            self.assertTrue(endpoint('cloudflare').endswith('/'+'a'*32+'/ai/v1'))

    def test_cloudflare_missing_account_is_explicit_and_does_not_hide_other_tiers(self):
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{k:v for k,v in ENV.items() if k!='CLOUDFLARE_ACCOUNT_ID'},clear=True),patch('forge.cloud.request_json',side_effect=catalogue):
            checked=CloudSetup(d).check()
            self.assertEqual(checked['cloudflare']['status'],'missing_configuration')
            self.assertIn('CLOUDFLARE_ACCOUNT_ID',checked['cloudflare']['detail'])
            self.assertEqual(checked['nvidia']['status'],'catalogue_available')

    def test_cloudflare_account_cannot_inject_endpoint_path(self):
        with patch.dict(os.environ,{'CLOUDFLARE_ACCOUNT_ID':'../invalid'},clear=True):
            with self.assertRaises(ValueError):endpoint('cloudflare')

    def test_seven_advertised_catalogues_build_ordered_route_and_persist_settings(self):
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,ENV,clear=True),patch('forge.cloud.request_json',side_effect=catalogue):
            cloud=CloudSetup(d);checked=cloud.check()
            self.assertTrue(all(c['status']=='catalogue_available' for c in checked.values()),checked)
            order=list(reversed(CLOUD_ORDER));choices={p:MODELS[p] for p in CLOUD_ORDER}
            profile=cloud.select(choices,local_model='qwen2.5-coder:7b',order=order,timeouts={'nvidia':30},structured={'requesty':False})
            chain=[profile['coder'],*profile['coder']['fallbacks']]
            self.assertEqual([c['provider'] for c in chain],order+['ollama'])
            validate_config(profile['coder'])
            nvidia=next(c for c in chain if c['provider']=='nvidia');self.assertEqual(nvidia['options']['timeout_seconds'],30)
            self.assertFalse(next(c for c in chain if c['provider']=='requesty')['options']['structured_outputs'])
            saved=CloudSetup(d);self.assertEqual(saved.order,order);self.assertEqual(saved.timeouts['nvidia'],30)
            self.assertFalse(any(v in cloud.path.read_text() for v in ENV.values()))
            with self.assertRaises(ValueError):validate_config({**profile['coder'],'fallbacks':[{'provider':'ollama','model':'extra'+str(i)} for i in range(16)]})

    def test_invalid_orders_and_timeouts_are_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            cloud=CloudSetup(d);cloud.checked={'groq':{'status':'catalogue_available','models':['fixture']}}
            for kwargs in [{'order':['groq']*7},{'timeouts':{'groq':True}},{'timeouts':{'groq':1}},{'structured':{'groq':'yes'}}]:
                with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):cloud.select({'groq':'fixture'},**kwargs)

    def test_new_cloud_adapters_use_bearer_json_limits_and_explicit_timeout(self):
        for provider in ('cloudflare','nvidia','requesty','huggingface'):
            with self.subTest(provider=provider),patch.dict(os.environ,ENV,clear=True):
                result={'choices':[{'finish_reason':'stop','message':{'content':'{"files":{"app.py":"source"}}'}}]}
                with patch('forge.models.request_json',return_value=result) as request:
                    client=ModelClient(provider,MODELS[provider],{'timeout_seconds':15,'num_predict':4096})
                    self.assertIn('files',client.complete(CODE,'{}'))
                    url,payload,headers=request.call_args.args
                    self.assertTrue(url.endswith('/chat/completions'));self.assertEqual(payload['max_tokens'],4096)
                    self.assertEqual(headers['Authorization'],'Bearer '+key_for(provider))
                    self.assertEqual(request.call_args.kwargs['timeout'],15)
                    self.assertEqual(payload['response_format'],{'type':'json_object'})
                    if provider=='cloudflare':self.assertEqual(payload['options'],{'rejectIfBusy':True})

    def test_json_format_can_be_disabled_without_disabling_json_parsing(self):
        with patch.dict(os.environ,ENV),patch('forge.models.request_json',return_value={'choices':[{'message':{'content':'{}'}}]}) as request:
            client=ModelClient('nvidia',MODELS['nvidia'],{'structured_outputs':False})
            client.complete(CODE,'{}');self.assertNotIn('response_format',request.call_args.args[1])

    def test_new_missing_configuration_falls_through_without_transport(self):
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{k:v for k,v in ENV.items() if k!='CLOUDFLARE_ACCOUNT_ID'},clear=True):
            bench=Workbench(Path(d)/'projects');state=state_for(bench)
            state['coder']={'provider':'cloudflare','model':MODELS['cloudflare'],'fallbacks':[{'provider':'nvidia','model':MODELS['nvidia']}]}
            with patch('forge.models.request_json',return_value={'choices':[{'message':{'content':'{}'}}]}) as request:
                self.assertEqual(bench.call_model(state,'coder',CODE,'{}',threading.Event()),{})
            self.assertEqual(request.call_count,1)
            self.assertEqual(state['model_calls'][0]['error_category'],'configuration')
            self.assertEqual(state['model_calls'][0]['failure_class'],'configuration')
            self.assertFalse(state['model_calls'][0]['transport_attempted'])
            self.assertEqual(state['model_calls'][1]['provider'],'nvidia')

    def test_every_tier_is_tried_once_after_transport_failures(self):
        with tempfile.TemporaryDirectory() as d:
            models=ScriptedModels([ModelError('Unavailable','transport')]*6+[PLAN])
            bench=Workbench(Path(d)/'projects',models);state=state_for(bench)
            configs=[{'provider':p,'model':MODELS[p]} for p in CLOUD_ORDER]
            state['coder']={**configs[0],'fallbacks':configs[1:]}
            self.assertEqual(bench.call_model(state,'coder','fixture','{}',threading.Event()),PLAN)
            self.assertEqual([c['provider'] for c in state['model_calls']],list(CLOUD_ORDER))

    def test_invalid_json_fails_over_with_parse_classification(self):
        with tempfile.TemporaryDirectory() as d:
            models=ScriptedModels([ModelError('Invalid JSON','format'),PLAN]);bench=Workbench(Path(d)/'projects',models);state=state_for(bench)
            state['coder']={'provider':'requesty','model':MODELS['requesty'],'fallbacks':[{'provider':'huggingface','model':MODELS['huggingface']}]}
            self.assertEqual(bench.call_model(state,'coder','fixture','{}',threading.Event()),PLAN)
            self.assertEqual(state['model_calls'][0]['failure_class'],'parse_error')

    def test_compact_revision_keeps_request_and_full_schema_with_8192_reservation(self):
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,ENV),patch('forge.models.request_json',return_value={'choices':[{'finish_reason':'stop','message':{'content':json.dumps(PLAN)}}]}) as request:
            bench=Workbench(Path(d)/'projects');state=state_for(bench);state['planner']={'provider':'openrouter','model':'openrouter/free'}
            previous={**PLAN,'tasks':PLAN['tasks']*6,'features':PLAN['features']*5}
            prompt=json.dumps({'idea':'Tiny Colony','previous_proposal':previous,'revision':'Preserve all behavior and checks'})
            result=bench.call_model(state,'planner',PLAN_SYSTEM,prompt,threading.Event());validate_structure(result)
            payload=request.call_args.args[1]
            self.assertEqual(payload['messages'][1]['content'],prompt)
            self.assertEqual(payload['max_tokens'],8192)
            self.assertIn('SCHEMA-COMPLETE',payload['messages'][-1]['content'])
            self.assertEqual(state['model_calls'][0]['recovery_path'],'budget_compaction')
            self.assertGreater(state['model_calls'][0]['estimated_required_output_tokens'],8192)

    def test_compact_truncation_still_stops_after_three_attempts(self):
        response={'choices':[{'finish_reason':'length','message':{'content':'{"title":'}}]}
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,ENV),patch('forge.models.request_json',return_value=response) as request:
            bench=Workbench(Path(d)/'projects');state=state_for(bench);state['planner']={'provider':'openrouter','model':'openrouter/free'}
            prompt=json.dumps({'previous_proposal':{**PLAN,'tasks':PLAN['tasks']*6,'features':PLAN['features']*5}})
            with self.assertRaises(ModelError) as error:bench.call_model(state,'planner',PLAN_SYSTEM,prompt,threading.Event())
            self.assertEqual(error.exception.category,'truncated_output');self.assertEqual(request.call_count,3)
            self.assertEqual([r['recovery_path'] for r in state['model_calls']],['budget_compaction','continuation','shortening'])

    def test_compaction_cannot_lower_explicit_floor(self):
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,ENV),patch('forge.models.request_json') as request:
            bench=Workbench(Path(d)/'projects');state=state_for(bench);state['planner']={'provider':'openrouter','model':'openrouter/free','options':{'num_ctx':32768,'num_predict':16384}}
            with self.assertRaises(ModelError):bench.call_model(state,'planner',PLAN_SYSTEM,'{}',threading.Event())
            request.assert_not_called()

    def test_every_new_key_alias_is_redacted_from_history_metadata(self):
        from forge.providers import SECRET_NAMES
        values={name:'secret-'+name.lower() for name in SECRET_NAMES}
        with patch.dict(os.environ,values,clear=True):
            output=json.dumps(redact({'message':' '.join(values.values())}))
        self.assertFalse(any(value in output for value in values.values()))

    def test_real_http_failover_tracks_error_and_timeout_across_new_providers(self):
        calls=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                payload=json.loads(self.rfile.read(int(self.headers['Content-Length'])));calls.append((self.path,payload,self.headers.get('Authorization')))
                status=503 if self.path.startswith('/requesty') else 200
                content=json.dumps({'choices':[{'finish_reason':'stop','message':{'content':'{}'}}]}).encode()
                self.send_response(status);self.send_header('Content-Length',str(len(content)));self.end_headers();self.wfile.write(content)
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            bases={p:('http://127.0.0.1:'+str(server.server_port)+'/'+p,PROVIDERS[p][1]) for p in ('requesty','nvidia')}
            with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,ENV),patch.dict(PROVIDERS,bases):
                bench=Workbench(Path(d)/'projects');state=state_for(bench)
                state['coder']={'provider':'requesty','model':MODELS['requesty'],'options':{'timeout_seconds':15},'fallbacks':[{'provider':'nvidia','model':MODELS['nvidia'],'options':{'timeout_seconds':30}}]}
                self.assertEqual(bench.call_model(state,'coder',CODE,'{}',threading.Event()),{})
                self.assertEqual([c['timeout_seconds'] for c in state['model_calls']],[15,30])
                self.assertEqual([c[0] for c in calls],['/requesty/chat/completions','/nvidia/chat/completions'])
        finally:server.shutdown();server.server_close()

    def test_socket_timeout_is_classified_and_next_provider_runs_without_waiting(self):
        import urllib.request
        calls=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                content=b'{"choices":[{"message":{"content":"{}"},"finish_reason":"stop"}]}'
                self.rfile.read(int(self.headers['Content-Length']))
                self.send_response(200);self.send_header('Content-Length',str(len(content)));self.end_headers();self.wfile.write(content)
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
        real=urllib.request.urlopen
        def open_url(request,timeout):
            calls.append((request.full_url,timeout))
            if '/requesty/' in request.full_url:raise TimeoutError('controlled socket timeout')
            return real(request,timeout=timeout)
        try:
            bases={p:('http://127.0.0.1:'+str(server.server_port)+'/'+p,PROVIDERS[p][1]) for p in ('requesty','huggingface')}
            with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,ENV),patch.dict(PROVIDERS,bases),patch('forge.models.urllib.request.urlopen',side_effect=open_url):
                bench=Workbench(Path(d)/'projects');state=state_for(bench)
                state['coder']={'provider':'requesty','model':MODELS['requesty'],'options':{'timeout_seconds':15},'fallbacks':[{'provider':'huggingface','model':MODELS['huggingface'],'options':{'timeout_seconds':30}}]}
                self.assertEqual(bench.call_model(state,'coder',CODE,'{}',threading.Event()),{})
                self.assertEqual(state['model_calls'][0]['error_category'],'transport')
                self.assertEqual([t for _,t in calls],[15,30])
                self.assertEqual(state['model_calls'][1]['provider'],'huggingface')
        finally:server.shutdown();server.server_close()

    def test_catalogue_limit_updates_from_parallel_checks_are_not_lost(self):
        def with_limits(url,**kwargs):
            data=catalogue(url,**kwargs)
            if url.endswith('/models'):
                for entry in data.get('data',[]):entry.update(max_output_tokens=16384,context_length=131072)
            return data
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,ENV),patch('forge.cloud.request_json',side_effect=with_limits):
            CloudSetup(d).check()
            saved=json.loads((Path(d)/'model-capabilities-v1.json').read_text())['models']
            for provider in ('gemini','groq','openrouter','nvidia','requesty','huggingface'):
                self.assertIn(provider+'/'+MODELS[provider],saved)

    def test_capability_cache_write_failure_does_not_hide_catalogue(self):
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,ENV),patch('forge.cloud.request_json',side_effect=catalogue),patch('forge.capabilities.atomic_text',side_effect=PermissionError('fixture')):
            checked=CloudSetup(d)._check_provider('gemini')
            self.assertEqual(checked['status'],'catalogue_available')
            self.assertIn('could not be saved',checked['detail'])

    def test_frozen_tiny_colony_revision_is_complete_and_source_request_is_preserved(self):
        from forge.contracts import require_consistent
        path=Path(__file__).parent/'fixture_data/planner-compaction-v1.json'
        manifest=json.loads(path.with_name('frozen-regressions-v5.json').read_text())
        expected_hash=next(item['sha256'] for item in manifest['sets'] if item['file']==path.name)
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),expected_hash)
        fixture=json.loads(path.read_text());prompt=json.dumps(fixture['request'])
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,ENV),patch('forge.models.request_json',return_value=fixture['response']) as request:
            bench=Workbench(Path(d)/'projects');state=state_for(bench);state['approved']=False
            state['planner']={'provider':fixture['provider'],'model':fixture['model']}
            result=bench.call_model(state,'planner',PLAN_SYSTEM,prompt,threading.Event())
            self.assertTrue(require_consistent(result,'web').passed)
            self.assertEqual(result['features'],fixture['expected_features'])
            self.assertEqual(len(result['manual_checks']),9)
            self.assertEqual(request.call_args.args[1]['messages'][1]['content'],prompt)
            self.assertEqual(state['model_calls'][0]['requested_max_output_tokens'],8192)
            self.assertEqual(state['model_calls'][0]['recovery_path'],'budget_compaction')
            self.assertEqual(bench.files(state['id']),{})

    def test_aggregator_reported_model_is_kept_separate_from_requested_route(self):
        response={'model':'resolved/model-v1','provider':'upstream-fixture','choices':[{'message':{'content':'{}'}}]}
        with patch.dict(os.environ,ENV),patch('forge.models.request_json',return_value=response):
            client=ModelClient('requesty',MODELS['requesty']);client.complete(CODE,'{}')
            self.assertEqual(client.model,MODELS['requesty'])
            self.assertEqual(client.last_metadata['response_model'],'resolved/model-v1')
            self.assertEqual(client.last_metadata['response_provider'],'upstream-fixture')

    def test_reported_model_cannot_echo_a_known_key_into_metadata(self):
        response={'model':ENV['NVIDIA_API_KEY'],'choices':[{'message':{'content':'{}'}}]}
        with patch.dict(os.environ,ENV),patch('forge.models.request_json',return_value=response):
            client=ModelClient('nvidia',MODELS['nvidia']);client.complete(CODE,'{}')
            self.assertNotIn('response_model',client.last_metadata)
