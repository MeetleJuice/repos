"""Local model failures must not suppress healthy Ollama alternatives."""
import copy
import json
import os
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from forge.core import Workbench
from forge.models import ModelError
from tests.fixtures import PLAN, APP, TEST
from tests.test_cloud import state_for
from tests.test_workbench import ScriptedModels,await_job
from forge.cloud import CloudSetup,local_failover_route


class LocalFailoverTests(unittest.TestCase):
    def test_planner_summary_counts_actual_calls_inside_local_route(self):
        invalid=copy.deepcopy(PLAN);del invalid['tasks'][0]['instructions']
        with tempfile.TemporaryDirectory() as temp:
            models=ScriptedModels([invalid,invalid,PLAN]);bench=Workbench(Path(temp)/'projects',models)
            config={'provider':'ollama','model':'first','fallback':{'provider':'ollama','model':'second'}}
            state=await_job(bench,bench.create('Build a small local task tracker',config,config)['id'])
            self.assertEqual(state['status'],'proposed',state.get('error'))
            self.assertEqual(len(state['model_calls']),3)
            self.assertEqual(state['planning_stats']['attempts'],3)

    def test_real_ollama_http_errors_advance_model_ids(self):
        requested=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*_):pass
            def do_POST(self):
                payload=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                requested.append(payload['model']);success=payload['model']=='third'
                body=json.dumps({'message':{'content':json.dumps(PLAN)},'done':True} if success else {'error':'fixture model failed'}).encode()
                self.send_response(200 if success else 500);self.send_header('Content-Type','application/json')
                self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            with tempfile.TemporaryDirectory() as temp,patch.dict(os.environ,{'OLLAMA_URL':'http://127.0.0.1:'+str(server.server_port)}):
                bench=Workbench(Path(temp)/'projects');state=state_for(bench)
                state['planner']={'provider':'ollama','model':'first','fallbacks':[{'provider':'ollama','model':model} for model in ['second','third']]}
                self.assertEqual(bench.call_model(state,'planner','Plan','{}',threading.Event()),PLAN)
                self.assertEqual(requested,['first','second','third'])
                self.assertEqual([row.get('http_status') for row in state['model_calls']],[500,500,None])
        finally:server.shutdown();server.server_close()

    def test_backups_are_detected_unique_bounded_and_preserve_explicit_settings(self):
        config={'provider':'ollama','model':'primary','options':{'num_ctx':16384,'num_predict':8192},'fallback':{'provider':'ollama','model':'explicit','options':{'num_ctx':32768,'num_predict':8192}}}
        before=copy.deepcopy(config)
        installed=['qwen3-embedding:0.6b','qwen2.5vl:3b','../bad','primary','explicit']+['model'+str(i) for i in range(20)]
        result=local_failover_route(config,installed,'coder');entries=[result,*result['fallbacks']]
        self.assertEqual(config,before);self.assertEqual(len(entries),6)
        self.assertEqual(entries[1],config['fallback']);self.assertEqual(len({entry['model'] for entry in entries}),6)
        self.assertTrue(all(entry['provider']=='ollama' for entry in entries))
        self.assertFalse(any('embed' in entry['model'] or 'vl:' in entry['model'] or '../' in entry['model'] for entry in entries))
        cloud={'provider':'gemini','model':'chosen','fallback':config}
        self.assertEqual(local_failover_route(cloud,installed,'planner'),cloud)

    def test_explicit_legacy_local_backup_is_used_for_rejected_code(self):
        with tempfile.TemporaryDirectory() as temp:
            models=ScriptedModels([PLAN,{'files':{}},{'files':{'app.py':APP,'test_app.py':TEST}}])
            bench=Workbench(Path(temp)/'projects',models)
            config={'provider':'ollama','model':'first','fallback':{'provider':'ollama','model':'second'}}
            state=await_job(bench,bench.create('Build a small local task tracker',config,config)['id'])
            bench.approve(state['id'],state['plan']);bench.start(state['id'],'build',{'execute':False,'repairs':0})
            state=await_job(bench,state['id']);self.assertEqual(state['status'],'generated',state.get('error'))
            self.assertEqual([row['model'] for row in state['model_calls'] if row['role']=='coder'],['first','second'])

    def test_failed_model_is_not_restarted_on_next_task_in_same_job(self):
        with tempfile.TemporaryDirectory() as temp:
            models=ScriptedModels([ModelError('Timeout','transport'),PLAN,PLAN]);bench=Workbench(Path(temp)/'projects',models)
            state=state_for(bench);state['planner']={'provider':'ollama','model':'first','fallbacks':[{'provider':'ollama','model':'second'}]}
            for _ in range(2):self.assertEqual(bench.call_model(state,'planner','Plan','{}',threading.Event()),PLAN)
            self.assertEqual([row['model'] for row in state['model_calls']],['first','second','second'])

    def test_two_local_transport_failures_do_not_skip_third_model(self):
        calls=[];models=ScriptedModels([ModelError('Timeout one','transport'),ModelError('Timeout two','transport'),PLAN])
        def factory(provider,model):calls.append((provider,model));return models
        with tempfile.TemporaryDirectory() as temp:
            bench=Workbench(Path(temp)/'projects',factory);state=state_for(bench)
            state['planner']={'provider':'ollama','model':'first','fallbacks':[{'provider':'ollama','model':name} for name in ['second','third']]}
            self.assertEqual(bench.call_model(state,'planner','Plan','{}',threading.Event()),PLAN)
            self.assertEqual([model for _,model in calls],['first','second','third'])

    def test_detected_models_supply_backups_without_replacing_saved_primary(self):
        calls=[];models=ScriptedModels([ModelError('Primary unavailable','transport'),PLAN])
        def factory(provider,model):calls.append((provider,model));return models
        with tempfile.TemporaryDirectory() as temp:
            bench=Workbench(Path(temp)/'projects',factory)
            bench.installed_ollama_models=['qwen3.5:9b','granite4.2:8b','qwen2.5-coder:7b','qwen3-embedding:0.6b','qwen2.5vl:3b']
            config={'provider':'ollama','model':'qwen3.5:9b'}
            state=await_job(bench,bench.create('Build a small local task tracker',config,config)['id'])
            self.assertEqual(state['status'],'proposed',state.get('error'))
            self.assertEqual(state['planner']['model'],'qwen3.5:9b')
            self.assertNotIn('fallbacks',state['planner'])
            self.assertEqual(len(state['model_calls']),2)
            self.assertNotEqual(state['model_calls'][0]['model'],state['model_calls'][1]['model'])
            self.assertTrue(all(provider=='ollama' for provider,_ in calls))
            self.assertEqual(state['run_model_routes']['planner']['model'],'qwen3.5:9b')

    def test_rejected_code_can_advance_beyond_two_local_models(self):
        models=ScriptedModels([PLAN,{'files':{}},{'files':{}},{'files':{'app.py':APP,'test_app.py':TEST}}]);calls=[]
        def factory(provider,model):calls.append((provider,model));return models
        with tempfile.TemporaryDirectory() as temp:
            bench=Workbench(Path(temp)/'projects',factory)
            config={'provider':'ollama','model':'first','fallbacks':[{'provider':'ollama','model':name} for name in ['second','third']]}
            state=await_job(bench,bench.create('Build a small local task tracker',config,config)['id'])
            bench.approve(state['id'],state['plan']);before=copy.deepcopy(state['plan'])
            bench.start(state['id'],'build',{'execute':False,'repairs':0});state=await_job(bench,state['id'])
            self.assertEqual(state['status'],'generated',state.get('error'))
            self.assertEqual(state['plan'],before)
            self.assertEqual([row['model'] for row in state['model_calls'] if row['role']=='coder'],['first','second','third'])
            self.assertEqual(bench.files(state['id'])['app.py'],APP)
