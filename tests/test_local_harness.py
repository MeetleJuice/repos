"""Local runtime/controller regressions; no real keys, models or GPUs."""
import json
from pathlib import Path
import unittest
import copy
import hashlib
import io
import os
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from forge.routing import uses_cloud, validate_config
from forge.capabilities import CapabilityRegistry
from forge.cloud import CloudSetup
from forge.core import Workbench
from forge.models import ModelClient, ModelError, connection_info
from forge.providers import endpoint
from forge.streaming import stream_chat
from forge.execution import begin_task, candidate_saved, finish_gate
from forge.model_status import ModelStatus
from forge.credentials import CredentialStore
from forge.history import redact
from tests.test_cloud import state_for
from tests.test_task_contracts import structured_plan
from tests.test_workbench import ScriptedModels
from tests.fixtures import PLAN

FIXTURE=Path(__file__).parent/'fixture_data/local-harness-v1.json'


class LocalHarnessTests(unittest.TestCase):
    def setUp(self):self.fixture=json.loads(FIXTURE.read_text())

    def test_local_runtime_route_does_not_require_cloud_consent(self):
        config=validate_config(self.fixture['runtime'])
        self.assertFalse(uses_cloud(config))
        self.assertTrue(uses_cloud({**config,'fallback':{'provider':'gemini','model':'fixture'}}))

    def test_local_runtime_reserves_real_input_and_planner_output_room(self):
        config=self.fixture['runtime'];registry=CapabilityRegistry()
        budget=registry.reserve('local',config['model'],config['options'],'Plan','{}')
        self.assertGreaterEqual(budget.text_output_tokens,8192)
        with self.assertRaises(ValueError):
            registry.reserve('local',config['model'],{**config['options'],'num_ctx':8192},'Plan','{}')

    def test_fixture_is_frozen(self):
        self.assertEqual(hashlib.sha256(FIXTURE.read_bytes()).hexdigest(),'05390e0eac52362487e72791d4ddadd59c972826561c0023c0a2d24662702d96')

    def test_endpoint_rejects_remote_userinfo_and_query(self):
        for url in ['https://127.0.0.1:1234/v1','http://example.com/v1','http://127.0.0.1.evil/v1','http://key@localhost/v1','http://localhost/v1?token=x','http://127.0.0.1:99999/v1']:
            with self.subTest(url=url),patch.dict(os.environ,{'LOCAL_API_URL':url}),self.assertRaises(ValueError):endpoint('local')

    def test_runtime_key_is_private_imported_and_redacted(self):
        with tempfile.TemporaryDirectory() as temp,patch.dict(os.environ,{},clear=True):
            store=CredentialStore(temp)
            result=store.import_text('LOCAL_API_URL=http://127.0.0.1:8080/v1\nLOCAL_API_KEY=fixture-private-runtime')
            self.assertNotIn('fixture-private-runtime',json.dumps(result))
            self.assertEqual(endpoint('local'),'http://127.0.0.1:8080/v1')
            self.assertEqual(redact('fixture-private-runtime'),'[redacted]')

    def test_explicit_runtime_profiles_persist_without_cloud(self):
        with tempfile.TemporaryDirectory() as temp,patch('forge.cloud.request_json') as request:
            setup=CloudSetup(temp);setup.timeouts['groq']=30
            routes=setup.local_runtime('fixture-coder','fixture-coder',['fixture-coder'])
            request.assert_not_called()
            self.assertEqual(CloudSetup(temp).saved_profiles(),routes)
            self.assertEqual(CloudSetup(temp).timeouts['groq'],30)
            self.assertFalse(any(uses_cloud(config) for config in routes.values()))
            with self.assertRaises(ValueError):setup.local_runtime('missing','fixture-coder',['fixture-coder'])
            self.assertEqual(CloudSetup(temp).saved_profiles(),routes)

    def test_real_loopback_discovery_and_inference(self):
        fixture=self.fixture;requests=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def send(self,value):
                data=json.dumps(value).encode();self.send_response(200);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
            def do_GET(self):self.send(fixture['catalogue'] if self.path=='/v1/models' else {'models':[]})
            def do_POST(self):
                body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                requests.append((self.path,body,self.headers.get('Authorization'),self.headers.get('User-Agent')))
                self.send(fixture['completion'])
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            base='http://127.0.0.1:'+str(server.server_port)
            with patch.dict(os.environ,{'LOCAL_API_URL':base+'/v1','LOCAL_API_KEY':'local-fixture','OLLAMA_URL':base},clear=True):
                self.assertEqual(connection_info()['local']['models'],['fixture-coder','fixture-embedding'])
                client=ModelClient('local','fixture-coder')
                self.assertEqual(client.complete('Return JSON','{}'),{'ok':True})
                path,payload,key,agent=requests[-1]
                self.assertEqual(path,'/v1/chat/completions');self.assertEqual(payload['max_tokens'],8192)
                self.assertEqual(key,'Bearer local-fixture');self.assertTrue(agent.startswith('IdeaFoundry/'))
                self.assertEqual(client.last_metadata['finish_reason'],'stop')
        finally:server.shutdown();server.server_close();thread.join()

    def test_local_redirect_is_not_followed(self):
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):self.send_response(302);self.send_header('Location','http://example.com/v1/chat/completions');self.end_headers()
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with patch.dict(os.environ,{'LOCAL_API_URL':'http://127.0.0.1:'+str(server.server_port)+'/v1'}):
                with self.assertRaisesRegex(ModelError,'redirects are refused'):ModelClient('local','fixture').complete('JSON','{}')
        finally:server.shutdown();server.server_close();thread.join()

    def stream(self,body,provider='local',cancel=None,progress=None):
        opener=type('Opener',(),{'open':lambda *args,**kwargs:io.BytesIO(body)})()
        with patch('forge.streaming.urllib.request.build_opener',return_value=opener):
            return stream_chat('http://127.0.0.1/v1/chat/completions',{}, {},30,provider,cancel or threading.Event(),progress or (lambda text:None))

    def test_sse_and_ndjson_streams_preserve_content_and_finish_reason(self):
        fragments=[]
        body=b'data: {"choices":[{"delta":{"content":"{\\\"ok\\\":true}"},"finish_reason":null}]}\n\ndata: {"choices":[{"delta":{},"finish_reason":"stop"}],"usage":{"completion_tokens":4}}\n\ndata: [DONE]\n'
        result=self.stream(body,progress=fragments.append)
        self.assertEqual(result['choices'][0]['message']['content'],'{"ok":true}')
        self.assertEqual(fragments,['{"ok":true}']);self.assertEqual(result['usage']['completion_tokens'],4)
        result=self.stream(b'{"message":{"content":"{}"},"done":false}\n{"done":true,"done_reason":"length","eval_count":2}\n','ollama')
        self.assertEqual(result['done_reason'],'length');self.assertEqual(result['message']['content'],'{}')

    def test_stream_cancel_missing_terminator_and_size_fail_closed(self):
        cancel=threading.Event()
        with self.assertRaises(InterruptedError):self.stream(b'{"message":{"content":"partial"}}\n{"done":true}\n','ollama',cancel,lambda text:cancel.set())
        with self.assertRaisesRegex(ModelError,'completion marker'):self.stream(b'data: {"choices":[{"delta":{"content":"{}"}}]}\n')
        with self.assertRaisesRegex(ModelError,'2 MB'):self.stream(b'x'*2_000_001)

    def test_finish_gate_checks_source_scope_and_plan_before_advancement(self):
        plan=structured_plan();files={'app.py':'original'}
        state={'plan':copy.deepcopy(plan),'approved':True,'next_task':0}
        begin_task(state,0,files);files={'app.py':'updated'};candidate_saved(state,files)
        gate=finish_gate(state,0,files)
        self.assertTrue(gate['passed']);self.assertFalse(gate['behavior_verified'])
        self.assertEqual(gate['criteria'],plan['tasks'][0]['done_when'])
        state['plan']['tasks'][0]['outcome']='Changed after approval'
        with self.assertRaisesRegex(ValueError,'Approved plan differs'):finish_gate(state,0,files)
        state['plan']=copy.deepcopy(plan)
        files['outside.js']='wrong scope';candidate_saved(state,files)
        with self.assertRaisesRegex(ValueError,'outside'):finish_gate(state,0,files)

    def test_repeated_calls_stop_before_fourth_invocation_but_new_input_is_allowed(self):
        with tempfile.TemporaryDirectory() as temp:
            models=ScriptedModels([PLAN]*4);bench=Workbench(Path(temp)/'projects',models);state=state_for(bench)
            state['coder']=self.fixture['runtime'];state['job_cloud_consent']=False;state['job_max_model_calls']=64
            for _ in range(3):bench.call_model(state,'coder','JSON','{}',threading.Event())
            with self.assertRaisesRegex(ModelError,'identical request'):bench.call_model(state,'coder','JSON','{}',threading.Event())
            self.assertEqual(len(models.calls),3);self.assertEqual(state['model_calls'][-1]['failure_class'],'loop_detected')
            bench.call_model(state,'coder','JSON','{"new_evidence":true}',threading.Event())
            self.assertEqual(len(models.calls),4)

    def test_progress_is_bounded_redacted_and_cleared(self):
        status=ModelStatus();status.start('local','fixture','coder','a'*32)
        with patch.dict(os.environ,{'LOCAL_API_KEY':'fixture-private'}):
            status.progress('x'*3000+'fixture-private')
            snapshot=status.snapshot({}, {'compatible':{'connected':True,'models':['fixture']}})
            self.assertLessEqual(len(status.active['preview']),2000)
            self.assertNotIn('fixture-private',json.dumps(snapshot))
            self.assertEqual(snapshot['items'][-1]['state'],'working')
            self.assertEqual(status.snapshot({}, {})['items'][-1]['state'],'working')
            status.finish('local','fixture','responded');self.assertIsNone(status.snapshot({}, {})['stream'])

    def test_cancel_real_http_stream_discards_partial_completion(self):
        entered=threading.Event()
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                self.rfile.read(int(self.headers['Content-Length']))
                self.send_response(200);self.send_header('Content-Type','text/event-stream');self.end_headers()
                entered.set()
                self.wfile.write(b'data: {"choices":[{"delta":{"content":"partial"},"finish_reason":null}]}\n\n');self.wfile.flush()
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            cancel=threading.Event()
            with patch.dict(os.environ,{'LOCAL_API_URL':'http://127.0.0.1:'+str(server.server_port)+'/v1'}):
                client=ModelClient('local','fixture');client.cancel_event=cancel;client.stream_progress=lambda text:cancel.set()
                with self.assertRaises(InterruptedError):client.complete('Return JSON','{}')
                self.assertTrue(entered.is_set());self.assertIsNone(client.last_metadata['finish_reason'])
        finally:server.shutdown();server.server_close();thread.join()

    def test_update_ready_event_is_explicit_and_never_installs(self):
        from forge.updates import UpdateManager
        from tests.test_updates import archive_for,manifest_for
        with tempfile.TemporaryDirectory() as temp:
            manager=UpdateManager(temp,temp,None,lambda url,limit:json.dumps(manifest_for(archive_for())).encode())
            result=manager.check('0.24.0')
            self.assertEqual(result['completion_event']['type'],'update_ready')
            self.assertTrue(result['completion_event']['requires_user_action'])
            self.assertIn('Press the Update button',result['completion_event']['message'])
            self.assertFalse(manager.restart)
