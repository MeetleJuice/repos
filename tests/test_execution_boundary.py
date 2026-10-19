"""Frozen log-derived failures; controlled providers, never live model claims."""
import hashlib
import copy
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from forge.build_contract import generation_contract, execution_directive, remove_unchanged_owned_echoes
from forge.models import ModelClient
from forge.prompts import CODE
from forge.cloud import CloudSetup
from forge.http_io import read_bounded, ResponseTooLarge, MAX_RESPONSE_BYTES
from forge.core import Workbench
from tests.fixtures import PLAN, APP, TEST
from tests.test_workbench import ScriptedModels, await_job


class ExecutionBoundaryTests(unittest.TestCase):
    def test_frozen_contract_preserves_requirements_and_counts_full_snapshot(self):
        fixture=json.loads((Path(__file__).parent/'fixture_data/execution-boundary-v1.json').read_text())
        self.assertEqual(len(fixture['gates']),5)
        root=Path(__file__).parent/'fixture_data'
        for item in json.loads((root/'frozen-regressions-v10.json').read_text())['sets']:
            self.assertEqual(hashlib.sha256((root/item['file']).read_bytes()).hexdigest(),item['sha256'])
        payload={'current_task':{'instructions':'Create README.md and implement café UI.'},'proposal':copy.deepcopy(PLAN),'files':{'app.py':'x'}}
        original=copy.deepcopy(payload)
        result=generation_contract(payload,{'app.py':'x'*100,'README.md':'r'*200})
        self.assertEqual(payload,original)
        self.assertTrue(all(result[k]==v for k,v in original.items()))
        self.assertIn('APP-GUIDE.md',result['execution_brief']['effective_instructions'])
        self.assertEqual(result['file_budget']['source_used'],100)
        self.assertEqual(result['file_budget']['total_used'],300)
        self.assertEqual(result['file_budget']['total_remaining'],69700)
        self.assertIn('No README.md',execution_directive(result))
        self.assertEqual(execution_directive({}),'')

    def test_only_exact_unchanged_owned_echo_removed_without_mutation(self):
        response={'files':{'README.md':'original','CHECKS.json':'modified','app.py':APP}}
        original=copy.deepcopy(response)
        result,ignored=remove_unchanged_owned_echoes(response,{'README.md':'original','CHECKS.json':'[]'})
        self.assertEqual(ignored,['README.md']);self.assertEqual(response,original)
        self.assertEqual(result['files']['CHECKS.json'],'modified')
        self.assertIn('app.py',result['files'])
        self.assertEqual(remove_unchanged_owned_echoes({'files':{'readme.md':'original'}},{'README.md':'original'})[1],[])

    def test_unchanged_echo_build_finishes_and_changed_guard_remains_atomic(self):
        models=ScriptedModels([PLAN])
        with tempfile.TemporaryDirectory() as d:
            bench=Workbench(Path(d)/'projects',models)
            config={'provider':'ollama','model':'fixture'}
            state=await_job(bench,bench.create('Build a task tracker',config,config)['id'])
            bench.approve(state['id'],state['plan']);before=bench.files(state['id'])
            models.responses.append({'files':{'README.md':before['README.md'],'app.py':APP,'test_app.py':TEST}})
            bench.start(state['id'],'build',{'execute':False,'repairs':0})
            state=await_job(bench,state['id'])
            self.assertEqual(state['status'],'generated',state.get('error'))
            self.assertEqual(state['generation_stats']['unchanged_owned_echoes'],1)
            self.assertEqual(bench.files(state['id'])['README.md'],before['README.md'])
            snapshot=bench.files(state['id'])
            with self.assertRaisesRegex(ValueError,'README.md'):
                bench.apply(state,{'files':{'README.md':'changed','extra.js':'bad'}})
            self.assertEqual(bench.files(state['id']),snapshot)

    def test_wire_keeps_original_payload_and_final_execution_boundary(self):
        payload=generation_contract({'current_task':{'instructions':'Create README.md'},'files':{}})
        captured=[]
        def wire(url,body,headers=None,timeout=300):
            captured.append(body)
            return {'message':{'content':json.dumps({'files':{'app.py':APP}})},'done_reason':'stop'}
        with patch('forge.models.request_json',side_effect=wire):
            ModelClient('ollama','fixture').complete(CODE,json.dumps(payload))
        messages=captured[0]['messages']
        self.assertEqual(json.loads(messages[1]['content']),payload)
        self.assertIn('FINAL EXECUTION BOUNDARY',messages[-1]['content'])
        self.assertIn('APP-GUIDE.md',messages[-1]['content'])

    def test_stream_elapsed_budget_stops_between_reads(self):
        class Slow:
            calls=0
            def read1(self,n):self.calls+=1;return b'x'
        response=Slow()
        with patch('forge.http_io.time.monotonic',side_effect=[0,1,2,11]):
            with self.assertRaisesRegex(TimeoutError,'elapsed'):read_bounded(response,10)
        self.assertEqual(response.calls,2)

    def test_stream_size_and_regular_body(self):
        with patch('forge.http_io.time.monotonic',return_value=0):
            self.assertEqual(read_bounded(io.BytesIO(b'{}'),10),b'{}')
            with self.assertRaises(ResponseTooLarge):read_bounded(io.BytesIO(b'x'*(MAX_RESPONSE_BYTES+1)),10)

    def test_automatic_catalogue_excludes_batch_not_normal_chat(self):
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'GROQ_API_KEY':'fixture'},clear=True),patch('forge.cloud.request_json',return_value={'data':[{'id':'qwen/chat:batch'},{'id':'qwen/chat'}]}):
            result=CloudSetup(d)._check_provider('groq')
            self.assertEqual(result['models'],['qwen/chat'])
