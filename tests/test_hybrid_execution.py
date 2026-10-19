"""Frozen hybrid routing and source-supported progress; no live keys/inference."""
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from forge.cloud import CloudSetup
from forge.circuit import TransportCircuit
from forge.core import Workbench
from forge.models import ModelClient,ModelError
from forge.prompts import CODE
from forge.tasks import existing_task_evidence,task_packet
from tests.test_task_contracts import structured_plan
from tests.test_workbench import ScriptedModels,await_job
from tests.test_automatic_routing import ENV,catalogue
from tests.test_cloud import state_for
from tests.fixtures import PLAN,APP,TEST


def supported():
    return {'already_satisfied':{'reason':'The existing app already defines the requested server factory.',
        'evidence':[{'file':'app.py','contains':APP[0:80]}]}}


class HybridExecutionTests(unittest.TestCase):
    def test_frozen_fixture_set(self):
        root=Path(__file__).parent/'fixture_data'
        for entry in json.loads((root/'frozen-regressions-v12.json').read_text())['sets']:
            self.assertEqual(hashlib.sha256((root/entry['file']).read_bytes()).hexdigest(),entry['sha256'])

    def test_explicit_modes_and_coder_selection_persist(self):
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,ENV,clear=True),patch('forge.cloud.request_json',side_effect=catalogue):
            setup=CloudSetup(d);local=['qwen3.5:9b','qwen2.5-coder:7b','qwen3-embedding:0.6b']
            hybrid=setup.automatic(local,mode='hybrid')
            self.assertEqual(hybrid['coder']['provider'],'ollama');self.assertEqual(hybrid['coder']['model'],'qwen2.5-coder:7b')
            self.assertEqual(hybrid['planner']['fallbacks'][0]['provider'],'ollama')
            self.assertEqual(CloudSetup(d).mode,'hybrid')
            cloud=setup.automatic(local,mode='cloud_first');self.assertEqual(cloud['coder']['fallbacks'][-1]['provider'],'ollama')
            first=setup.automatic(local,mode='local_first');self.assertEqual(first['planner']['provider'],'ollama')
            with patch.object(setup,'check') as check:
                only=setup.automatic(local,mode='local_only');check.assert_not_called()
            for config in only.values():
                entries=[config,*config.get('fallbacks',[])]
                self.assertEqual(len(entries),2)
                self.assertTrue(all(c['provider']=='ollama' for c in entries))
                self.assertEqual(len({c['model'] for c in entries}),2)
            self.assertEqual(CloudSetup(d).automatic_routes,only)
            with self.assertRaises(ValueError):setup.automatic(local,mode={})

    def test_source_claim_requires_real_scoped_excerpts_not_behavior_claims(self):
        packet=task_packet(structured_plan(),0,0)
        result=existing_task_evidence(supported(),{'app.py':APP},packet)
        self.assertFalse(result['behavior_verified']);self.assertEqual(result['kind'],'existing_source_supported')
        for bad in [{'already_satisfied':{'reason':'already done','evidence':[]}},
                    {'already_satisfied':{'reason':'Existing behavior is fully implemented here.','evidence':[{'file':'app.py','contains':'x'*40}]}},
                    {**supported(),'files':{'outside.py':'bad'}}]:
            with self.subTest(bad=bad),self.assertRaises(ValueError):existing_task_evidence(bad,{'app.py':APP},packet)
        with self.assertRaises(ValueError):existing_task_evidence(supported(),{'app.py':APP},{'structured':False})

    def test_failed_edit_then_evidence_only_response_finishes_without_code_changes(self):
        plan=structured_plan();second=copy.deepcopy(plan['tasks'][0]);second['depends_on']=[0];second['title']='Confirm existing server factory';plan['tasks'].append(second)
        models=ScriptedModels([plan,{'files':{'app.py':APP,'test_app.py':TEST}},
            {'edits':[{'file':'app.py','search':'not present','replace':'bad'}]},supported()])
        with tempfile.TemporaryDirectory() as d:
            bench=Workbench(Path(d)/'projects',models);config={'provider':'ollama','model':'fixture'}
            state=await_job(bench,bench.create('Build a task tracker',config,config)['id']);bench.approve(state['id'],state['plan'])
            bench.start(state['id'],'build',{'execute':False,'repairs':0});state=await_job(bench,state['id'])
            self.assertEqual(state['status'],'generated',state.get('error'));self.assertEqual(state['next_task'],2)
            receipt=state['task_receipts'][-1];self.assertFalse(receipt['source_changed']);self.assertFalse(receipt['behavior_verified'])
            self.assertEqual(receipt['disposition'],'existing_source_supported');self.assertEqual(receipt['before_sha256'],receipt['after_sha256'])
            self.assertEqual(bench.files(state['id'])['app.py'],APP);self.assertFalse(state.get('checks'))
            self.assertEqual(models.calls[-1]['response_mode'],'complete_files')

    def test_transport_circuit_expiry_success_and_reset(self):
        circuit=TransportCircuit()
        with patch('forge.circuit.time.monotonic',return_value=100):
            circuit.failure('groq');self.assertEqual(circuit.remaining('groq'),0)
            circuit.failure('groq');self.assertEqual(circuit.remaining('groq'),120)
        with patch('forge.circuit.time.monotonic',return_value=221):self.assertEqual(circuit.remaining('groq'),0)
        circuit.success('groq');self.assertNotIn('groq',circuit.blocked)
        circuit.failure('groq');circuit.reset();self.assertFalse(circuit.failures)

    def test_repeated_transport_failures_skipped_without_sleep_or_changing_route(self):
        calls=[]
        class Client:
            def __init__(self,provider):self.provider=provider
            def complete(self,*_):
                calls.append(self.provider)
                if self.provider=='gemini':raise ModelError('fixture unavailable','provider')
                return copy.deepcopy(PLAN)
        with tempfile.TemporaryDirectory() as d:
            bench=Workbench(Path(d)/'projects',lambda p,m:Client(p));state=state_for(bench)
            before=copy.deepcopy(state['planner']) if 'planner' in state else None
            for _ in range(3):bench.call_model(state,'planner','fixture','{}',threading.Event())
            self.assertEqual(calls.count('gemini'),2);self.assertEqual(calls.count('groq'),3)
            self.assertEqual(state['planner'],before)

    def test_all_cooldown_exhaustion_explains_no_requests(self):
        models=ScriptedModels([])
        with tempfile.TemporaryDirectory() as d:
            bench=Workbench(Path(d)/'projects',models);state=state_for(bench)
            for provider in ('gemini','groq','openrouter'):
                bench.transport_circuit.failure(provider);bench.transport_circuit.failure(provider)
            with self.assertRaisesRegex(ModelError,'cooldown.*no request sent'):
                bench.call_model(state,'planner','fixture','{}',threading.Event())
            self.assertFalse(models.calls)

    def test_http_status_is_retained_without_provider_body(self):
        import io
        import urllib.error
        from forge.models import request_json
        error=urllib.error.HTTPError('https://example.invalid',503,'fixture',{},io.BytesIO(b'private-response-body'))
        with patch('forge.models.urllib.request.urlopen',side_effect=error):
            with self.assertRaises(ModelError) as failure:request_json('https://example.invalid')
        self.assertEqual(failure.exception.http_status,503)
        self.assertNotIn('private-response-body',str(failure.exception))

    def test_local_timing_and_recovery_schema(self):
        body={'message':{'content':json.dumps(supported())},'done_reason':'stop','load_duration':1000000000,'eval_duration':2000000000,'eval_count':40}
        with patch('forge.models.request_json',return_value=body) as request:
            client=ModelClient('ollama','fixture');self.assertEqual(client.complete(CODE,'{"response_mode":"complete_files"}'),supported())
        self.assertEqual(client.last_metadata['ollama_load_seconds'],1)
        self.assertEqual(client.last_metadata['ollama_tokens_per_second'],20)
        self.assertIn('already_satisfied',request.call_args.args[1]['format']['properties'])
        body['eval_count']=10**400
        with patch('forge.models.request_json',return_value=body):
            client.complete(CODE,'{}')
        self.assertNotIn('ollama_tokens_per_second',client.last_metadata)
