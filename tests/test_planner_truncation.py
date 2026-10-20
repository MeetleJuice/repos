"""Frozen HTTP-200/incomplete-JSON regression. No live model calls."""
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from forge.capabilities import CapabilityRegistry
from forge.core import Workbench
from forge.models import ModelClient, ModelError
from forge.prompts import PLAN as SYSTEM
from forge.contracts import validate_structure, review_plan
from tests.test_cloud import state_for

FIXTURE=Path(__file__).parent/'fixture_data/planner-truncation-v1.json'


def native(response):
    choice=response['choices'][0];usage=response['usage']
    return {'candidates':[{'finishReason':'MAX_TOKENS' if choice['finish_reason']=='length' else 'STOP',
                          'content':{'parts':[{'text':choice['message']['content']}]}}],
            'usageMetadata':{'promptTokenCount':usage['prompt_tokens'],'candidatesTokenCount':usage['completion_tokens'],'thoughtsTokenCount':32}}


class PlannerTruncationTests(unittest.TestCase):
    def setUp(self):self.fixture=json.loads(FIXTURE.read_text())

    def test_manual_ollama_planner_floor_reaches_inference_without_changing_builder_cap(self):
        options={'num_ctx':32768,'num_predict':4096,'structured_outputs':True,'timeout_seconds':120}
        registry=CapabilityRegistry()
        budget=registry.reserve('ollama','qwen2.5:7b',options,SYSTEM,'{}')
        self.assertGreaterEqual(budget.text_output_tokens,8192)
        self.assertEqual(registry.reserve_builder('ollama','qwen2.5-coder:7b',options,'Code','{}').text_output_tokens,4096)
        response={'message':{'content':json.dumps(self.fixture['expected_plan'])},'done_reason':'stop','eval_count':100}
        with tempfile.TemporaryDirectory() as directory:
            bench=Workbench(Path(directory)/'projects');state=state_for(bench)
            state['planner']={'provider':'ollama','model':'qwen2.5:7b','options':options}
            with patch('forge.models.request_json',return_value=response) as request:
                result=bench.call_model(state,'planner',SYSTEM,'{}',threading.Event())
            self.assertEqual(result,self.fixture['expected_plan'])
            sent=request.call_args.args[1]['options']['num_predict']
            self.assertGreaterEqual(sent,8192)
            self.assertEqual(state['model_calls'][-1]['requested_max_output_tokens'],sent)
            self.assertGreaterEqual(state['model_calls'][-1]['max_output_ceiling'],sent)
            self.assertEqual(state['planner']['options'],options)

    def test_manual_ollama_planner_still_rejects_insufficient_context(self):
        registry=CapabilityRegistry()
        with self.assertRaisesRegex(ValueError,'context'):
            registry.reserve('ollama','qwen2.5:7b',{'num_ctx':8192,'num_predict':4096},SYSTEM,'{}',compact=True)
        with tempfile.TemporaryDirectory() as directory:
            bench=Workbench(Path(directory)/'projects');state=state_for(bench)
            state['planner']={'provider':'ollama','model':'qwen2.5:7b','options':{'num_ctx':8192,'num_predict':4096}}
            with patch('forge.models.request_json') as request, self.assertRaises(ModelError):
                bench.call_model(state,'planner',SYSTEM,'{}',threading.Event())
            request.assert_not_called()
            self.assertIs(state['model_calls'][-1]['transport_attempted'],False)
            self.assertTrue(any('context is 8192' in event['message'] for event in state['events']))

    def run_route(self,responses,cancel=None,larger_fallback=False):
        with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,{'GEMINI_API_KEY':'fixture','OPENROUTER_API_KEY':'fixture'}):
            bench=Workbench(Path(directory)/"projects");state=state_for(bench)
            state['planner']={'provider':'gemini','model':'gemini-3.8-flash','options':{'num_ctx':16384,'num_predict':4096,'structured_outputs':True},
                              'fallbacks':[{'provider':'openrouter','model':'openrouter/free'}]}
            if larger_fallback:
                state['planner']['fallbacks'][0]['model']='larger:free'
                registry=CapabilityRegistry(Path(directory)/'model-capabilities-v1.json')
                registry.discover_openrouter([{'id':'larger:free','context_length':131072,'top_provider':{'max_completion_tokens':65536}}])
            calls=[]
            def request(url,payload,headers,timeout):
                calls.append((url,payload))
                if 'openrouter' in url: return self.fixture['gemini_shortening'] if larger_fallback else self.fixture['openrouter_smaller']
                return native(responses.pop(0))
            with patch('forge.models.request_json',side_effect=request):
                try:
                    result=bench.call_model(state,'planner',SYSTEM,json.dumps({'idea':'Build a reading list'}),cancel or threading.Event())
                except ModelError as exc:result=exc
            return result,state,calls

    def test_fixture_is_frozen_and_capabilities_are_versioned(self):
        self.assertEqual(hashlib.sha256(FIXTURE.read_bytes()).hexdigest(), '7f3cca7529ee88bbd18265881983835819cb84797cbfb146fc7f3b35cbe66aed')
        manifest=json.loads(FIXTURE.with_name('frozen-regressions-v2.json').read_text())
        for entry in manifest['sets']:
            self.assertEqual(hashlib.sha256(FIXTURE.with_name(entry['file']).read_bytes()).hexdigest(),entry['sha256'])
        registry=CapabilityRegistry()
        cap=registry.get('gemini','gemini-3.8-flash')
        self.assertEqual(cap.max_output_tokens,65536)
        self.assertTrue(cap.supports_thinking_budget)
        free=registry.get('openrouter','openrouter/free')
        self.assertEqual(free.max_output_tokens,8192);self.assertTrue(free.estimated)

    def test_cut_json_continues_on_same_model_without_smaller_fallback(self):
        result,state,calls=self.run_route([self.fixture['gemini_initial'],self.fixture['gemini_continuation']])
        self.assertEqual(result,self.fixture['expected_plan'])
        validate_structure(result);self.assertTrue(review_plan(result).passed)
        self.assertEqual(len(calls),2);self.assertTrue(all('googleapis.com' in url for url,_ in calls))
        first,second=state['model_calls']
        self.assertEqual(first['failure_class'],'truncated_output');self.assertEqual(first['error_category'],'truncated_output')
        self.assertEqual(first['finish_reason'],'MAX_TOKENS')
        self.assertGreaterEqual(first['reserved_text_output_tokens'],8192)
        self.assertEqual(first['requested_max_output_tokens'],calls[0][1]['generationConfig']['maxOutputTokens'])
        self.assertEqual(first['observed_output_tokens'],4128)
        self.assertEqual(second['recovery_path'],'continuation');self.assertTrue(second['success'])
        self.assertEqual(calls[0][1]['generationConfig']['thinkingConfig'],{'thinkingBudget':1024})
        self.assertIn('Continue exactly',calls[1][1]['contents'][-1]['parts'][0]['text'])
        self.assertNotIn('partial_content',json.dumps(state))

    def test_second_truncation_shortens_without_changing_schema(self):
        result,state,calls=self.run_route([self.fixture['gemini_initial'],self.fixture['gemini_initial'],self.fixture['gemini_shortening']])
        validate_structure(result)
        self.assertEqual([r['recovery_path'] for r in state['model_calls']],['initial','continuation','shortening'])
        self.assertIn('SCHEMA-COMPLETE',calls[-1][1]['contents'][-1]['parts'][0]['text'])
        self.assertEqual(result,self.fixture['expected_plan'])

    def test_exhaustion_stays_truncation_and_skips_lower_ceiling(self):
        result,state,calls=self.run_route([self.fixture['gemini_initial']]*3)
        self.assertIsInstance(result,ModelError);self.assertEqual(result.category,'truncated_output')
        self.assertEqual(len(calls),3)
        self.assertTrue(any('smaller than' in e['message'] for e in state['events']))
        self.assertTrue(all(r['provider']=='gemini' for r in state['model_calls']))

    def test_bad_continuation_json_gets_shortening_not_outage_failover(self):
        bad=copy.deepcopy(self.fixture['gemini_continuation']);bad['choices'][0]['message']['content']='wrong suffix'
        result,state,calls=self.run_route([self.fixture['gemini_initial'],bad,self.fixture['gemini_shortening']])
        self.assertEqual(result,self.fixture['expected_plan'])
        self.assertEqual(state['model_calls'][1]['failure_class'],'parse_error')
        self.assertEqual(state['model_calls'][2]['recovery_path'],'shortening')

    def test_published_openrouter_cap_is_persisted(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'model-capabilities-v1.json';registry=CapabilityRegistry(path)
            registry.discover_openrouter([{'id':'published:free','context_length':131072,'top_provider':{'max_completion_tokens':32768}}, {'id':'unknown:free'}])
            cap=CapabilityRegistry(path).get('openrouter','published:free')
            self.assertEqual(cap.max_output_tokens,32768);self.assertFalse(cap.estimated)
            self.assertEqual(CapabilityRegistry(path).get('openrouter','unknown:free').max_output_tokens,8192)

    def test_compatible_adapter_records_length_even_when_content_is_cut(self):
        with patch.dict(os.environ,{'OPENROUTER_API_KEY':'fixture'}),patch('forge.models.request_json',return_value=self.fixture['openrouter_smaller']):
            client=ModelClient('openrouter','openrouter/free')
            with self.assertRaises(ModelError) as error:client.complete('fixture','{}')
            self.assertEqual(error.exception.category,'truncated_output')
            self.assertEqual(client.last_metadata['finish_reason'],'length')
            self.assertEqual(client.last_metadata['observed_output_tokens'],8192)

    def test_equal_ceiling_fallback_is_allowed_after_bounded_recovery(self):
        result,state,calls=self.run_route([self.fixture['gemini_initial']]*3,larger_fallback=True)
        self.assertEqual(result,self.fixture['expected_plan'])
        self.assertEqual(len(calls),4)
        self.assertEqual(state['model_calls'][-1]['provider'],'openrouter')
        self.assertEqual(state['model_calls'][-1]['recovery_path'],'capacity_fallback')
        self.assertEqual(state['model_calls'][-1]['max_output_ceiling'],65536)

    def test_reservation_increases_with_schema_task_and_check_counts(self):
        registry=CapabilityRegistry();options={'num_predict':4096}
        small=registry.reserve('gemini','gemini-3.8-flash',options,SYSTEM,'{}')
        large=registry.reserve('gemini','gemini-3.8-flash',options,SYSTEM,json.dumps({'previous_proposal':{'features':['f']*15,'tasks':[{}]*12,'checks':[{}]*35}}))
        self.assertGreater(large.text_output_tokens,small.text_output_tokens)
        self.assertLessEqual(large.max_output_tokens,65536)
        self.assertEqual(large.max_output_tokens,large.text_output_tokens+large.thinking_budget)

    def test_stop_after_initial_truncation_prevents_recovery_request(self):
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'GEMINI_API_KEY':'fixture'}):
            bench=Workbench(Path(d)/'projects');state=state_for(bench)
            state['planner']={'provider':'gemini','model':'gemini-3.8-flash'}
            cancel=threading.Event()
            def request(*args,**kwargs):
                cancel.set()
                return native(self.fixture['gemini_initial'])
            with patch('forge.models.request_json',side_effect=request) as calls:
                with self.assertRaises(InterruptedError):bench.call_model(state,'planner',SYSTEM,'{}',cancel)
            self.assertEqual(calls.call_count,1)
            self.assertEqual(len(state['model_calls']),1)

    def test_schema_error_is_not_reported_as_provider_outage(self):
        from tests.test_workbench import await_job
        response={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'{"title":"Incomplete"}'}]}}]}
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'GEMINI_API_KEY':'fixture'}),patch('forge.models.request_json',return_value=response):
            bench=Workbench(Path(d)/'projects');config={'provider':'gemini','model':'gemini-3.8-flash'}
            state=bench.create('Build a reading list app',config,config,cloud_consent=True)
            state=await_job(bench,state['id'])
            self.assertEqual(state['status'],'error')
            self.assertEqual(state['model_calls'][-1]['failure_class'],'schema_error')
            self.assertFalse(state['model_calls'][-1]['proposal_valid'])

    def test_real_http_native_adapter_recovers_before_proposal_review(self):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        from forge.models import PROVIDERS
        from tests.test_workbench import await_job
        fixture=self.fixture;requests=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                payload=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                requests.append((self.path,payload,self.headers.get('x-goog-api-key')))
                response=native(fixture['gemini_initial'] if len(requests)==1 else fixture['gemini_continuation'])
                data=json.dumps(response).encode()
                self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
        try:
            with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'GEMINI_API_KEY':'fixture'}),patch.dict(PROVIDERS,{'gemini':('http://127.0.0.1:'+str(server.server_port)+'/v1beta/openai','GEMINI_API_KEY')}):
                bench=Workbench(Path(d)/'projects')
                config={'provider':'gemini','model':'gemini-3.8-flash','fallbacks':[{'provider':'openrouter','model':'openrouter/free'}]}
                state=bench.create('Build a small task tracker',config,config,cloud_consent=True)
                state=await_job(bench,state['id'])
                self.assertEqual(state['status'],'proposed',state.get('error'))
                self.assertFalse(state['approved'])
                self.assertEqual(bench.files(state['id']),{})
                self.assertEqual(len(requests),2)
                self.assertTrue(all(p=='/v1beta/models/gemini-3.8-flash:generateContent' and k=='fixture' for p,_,k in requests))
                self.assertEqual(state['model_calls'][0]['failure_class'],'truncated_output')
                self.assertEqual(state['model_calls'][1]['recovery_path'],'continuation')
                self.assertTrue(state['model_calls'][1]['proposal_valid'])
        finally:server.shutdown();server.server_close();worker.join(3)

    def test_legacy_outer_planner_cannot_bypass_truncation_ceiling(self):
        from tests.test_workbench import await_job
        bad=copy.deepcopy(self.fixture['gemini_continuation']);bad['choices'][0]['message']['content']='not valid JSON'
        replies=[self.fixture['gemini_initial'],bad,bad]
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'GEMINI_API_KEY':'fixture','OPENROUTER_API_KEY':'fixture'}):
            bench=Workbench(Path(d)/'projects');config={'provider':'gemini','model':'gemini-3.8-flash','fallback':{'provider':'openrouter','model':'openrouter/free'}}
            calls=[]
            def request(url,*args,**kwargs):
                calls.append(url)
                self.assertNotIn('openrouter',url)
                return native(replies.pop(0))
            with patch('forge.models.request_json',side_effect=request):
                state=bench.create('Build a small task tracker',config,config,cloud_consent=True)
                state=await_job(bench,state['id'])
            self.assertEqual(state['status'],'error')
            self.assertEqual(len(calls),3)
            self.assertTrue(any('smaller than' in event['message'] for event in state['events']))

    def test_insufficient_reservation_is_refused_without_an_api_call(self):
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'OPENROUTER_API_KEY':'fixture'}):
            home=Path(d);registry=CapabilityRegistry(home/'model-capabilities-v1.json')
            registry.discover_openrouter([{'id':'small:free','context_length':4096,'top_provider':{'max_completion_tokens':8192}}])
            self.assertEqual(CapabilityRegistry(home/'model-capabilities-v1.json').get('openrouter','small:free').max_context_tokens,4096)
            bench=Workbench(home/'projects');state=state_for(bench)
            state['planner']={'provider':'openrouter','model':'small:free'}
            with patch('forge.models.request_json') as request:
                with self.assertRaises(ModelError) as error:bench.call_model(state,'planner',SYSTEM,'{}',threading.Event())
            request.assert_not_called()
            self.assertEqual(error.exception.category,'output_budget')
            self.assertEqual(state['model_calls'][0]['failure_class'],'output_budget')
