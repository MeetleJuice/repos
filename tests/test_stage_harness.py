"""Stage harness regressions; synthetic controller inputs, not live model outcomes."""
import copy
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from forge.outline_planning import create_outline
from forge.feature_acceptance import compile_feature

IDEA='Build Tiny Wins, a small local accomplishment journal. Use the selected SQLite foundation and its existing API. One responsive browser page lets me add a win with a title and optional note, then view saved wins. Entries survive page reloads and server restarts. Include meaningful create, read, and restart-persistence checks, plus a manual browser checklist. No accounts, external services, extra packages, search, editing, or deletion.'


def scope():
    return {'title':'Records','summary':'Save a titled record','features':['Create a record'],
            'out_of_scope':[],'risks':[],'app_kind':'server','task_contract_version':1,'context_policy':'focused_v1'}


class StageHarnessTests(unittest.TestCase):
    def test_frozen_diagnostic_and_prior_sets_are_unchanged(self):
        import hashlib
        from forge.planning_diagnostics import latest_planning_run
        root=Path(__file__).parent/'fixture_data'
        previous=json.loads((root/'frozen-regressions-v22.json').read_text())
        current=json.loads((root/'frozen-regressions-v23.json').read_text())
        self.assertEqual(current['sets'][:-1],previous['sets'])
        for row in current['sets']:self.assertEqual(hashlib.sha256((root/row['file']).read_bytes()).hexdigest(),row['sha256'])
        fixture=json.loads((root/'stage-harness-v1.json').read_text())
        result=latest_planning_run(fixture['observed_records'])
        for key,value in fixture['expected_latest_run'].items():self.assertEqual(result[key],value)
        self.assertEqual(result['stages']['acceptance_feature']['accepted'],1)
    def packets(self):
        from tests.test_evidence_planning import sqlite_plan
        from tests.test_guided_planning import outline_replies,feature_batches
        from tests.test_feature_acceptance import feature_replies
        from tests.test_diag_revision import wire
        plan=sqlite_plan();outline,acceptance=outline_replies({k:v for k,v in plan.items() if k!='tasks'})
        packets=[wire(p) for p in feature_replies(acceptance,2)]
        # The model need not repeat controller-known contracts in the new policy.
        for packet in packets:packet.pop('api_contracts',None)
        return plan,outline,packets,feature_batches(plan['tasks'])

    def test_scope_context_defers_builder_details_but_keeps_original_requirements(self):
        request={'idea':'Keep Café 🐜 exactly','planning_context_policy':'stage_v1',
                 'builder_profile':{'irrelevant_route_description':'BULKY_ROUTE_DATA'*1000},
                 'starter_source':{'app.py':'SOURCE_NOT_NEEDED_FOR_SCOPE'},
                 'existing_project':{'features':['Keep existing behavior']}}
        calls=[]
        class StopAfterScope(Exception):pass
        def generate(system,payload,validate):
            calls.append(payload)
            if len(calls)>1:raise StopAfterScope()
            validate(scope());return scope()
        with self.assertRaises(StopAfterScope):create_outline(request,generate,lambda _:None,{},threading.Event())
        packet=json.dumps(calls[0],ensure_ascii=False)
        self.assertFalse('BULKY_ROUTE_DATA' in packet)
        self.assertIn(request['idea'],packet)
        self.assertIn('Keep existing behavior',packet)

    def test_registered_starter_contracts_do_not_need_model_redeclaration(self):
        from forge.scaffolds import CATALOG
        from forge.contracts import starter_contracts
        request={'starter':CATALOG['sqlite'],'acceptance_policy':'evidence_v1',
                 'acceptance_planning_policy':'feature_v3','planning_context_policy':'stage_v1'}
        candidate={'checks':[{'name':'Create record','method':'POST','path':'/api/records','status':201,
                             'body':{'title':'A real sample','note':'Saved'},
                             'json_contains':{'id':1,'title':'A real sample','note':'Saved'}}]}
        result=compile_feature(scope(),{'checks':[]},candidate,0,request)
        self.assertEqual(result['api_contracts'],starter_contracts('sqlite'))
        self.assertEqual(result['checks'][0]['json_contains'],candidate['checks'][0]['json_contains'])

    def test_unknown_contract_wrong_shape_and_missing_body_still_fail(self):
        from forge.scaffolds import CATALOG
        from forge.guided import StageValidationError
        request={'starter':CATALOG['sqlite'],'acceptance_policy':'evidence_v1','acceptance_planning_policy':'feature_v3'}
        base={'name':'Create','method':'POST','path':'/api/records','status':201,
              'body':{'title':'Saved sample'},'json_contains':{'id':1,'title':'Saved sample'}}
        for change,code in [({'path':'/api/unknown'},'missing_api_contract'),
                            ({'json_contains':[{'title':'Saved sample'}]},'response_shape'),
                            ({'body':{}},'mutation_example')]:
            with self.subTest(code=code),self.assertRaises(StageValidationError) as caught:
                compile_feature(scope(),{'checks':[]},{'checks':[{**base,**change}]},0,request)
            self.assertIn(code,[f.code for f in caught.exception.review.findings])

    def test_memory_resume_and_tamper_detection_are_bound_to_exact_prefix(self):
        from forge.scaffolds import CATALOG
        plan,outline,packets,_=self.packets();saved=[];calls=[];cancel=threading.Event()
        request={'idea':'Keep Café 🐜 exactly','starter':CATALOG['sqlite'],'acceptance_policy':'evidence_v1',
                 'acceptance_planning_policy':'feature_v3','planning_context_policy':'stage_v1'}
        def generate(system,payload,validate):
            calls.append(payload);reply=packets[payload['target_feature_index']];validate(reply);return copy.deepcopy(reply)
        def stop(draft):saved.append(draft);cancel.set()
        with self.assertRaises(InterruptedError):create_outline(request,generate,stop,{'scope':outline},cancel)
        original=copy.deepcopy(saved[-1]);memory=original['acceptance_draft']['planning_memory']
        self.assertEqual(memory['accepted_features'],1)
        self.assertEqual(memory['declared_mutations'][0]['check_index'],0)
        cancel.clear();calls.clear()
        for kind in ('changed_sample','removed_contract'):
            changed=copy.deepcopy(original)
            if kind=='changed_sample':changed['acceptance_draft']['fields']['checks'][0]['body']['title']='DRIFT'
            else:changed['acceptance_draft']['fields']['api_contracts'].pop()
            with self.subTest(kind=kind),self.assertRaisesRegex(ValueError,'planning memory'):
                create_outline(request,generate,lambda _:None,changed,cancel)
        self.assertEqual(calls,[])
        result=create_outline(request,generate,saved.append,original,cancel)
        self.assertEqual([p['target_feature_index'] for p in calls],[1])
        self.assertEqual(result['checks'],plan['checks'])
        self.assertEqual(calls[0]['planning_memory']['accepted_prefix_sha256'],memory['accepted_prefix_sha256'])

    def test_real_native_adapter_completes_v3_plan_at_16k_and_preserves_checks(self):
        from forge.core import Workbench
        from tests.test_workbench import await_job
        plan,outline,packets,batches=self.packets();replies=[outline,*packets,*batches];transports=[]
        def transport(url,payload,*args,**kwargs):
            transports.append(payload)
            return {'done':True,'done_reason':'stop','model':payload['model'],
                    'message':{'content':json.dumps(replies.pop(0))},'eval_count':100,'prompt_eval_count':500}
        with tempfile.TemporaryDirectory() as folder,patch('forge.models.request_json',side_effect=transport):
            bench=Workbench(Path(folder)/'projects')
            bench.installed_ollama_models=['qwen2.5-coder:7b','qwen3.5:9b','deepseek-r1:7b','qwen2.5:7b','qwen3:8b','granite4.2:8b']
            planner={'provider':'ollama','model':'qwen2.5-coder:7b','options':{'num_ctx':16384,'num_predict':8192}}
            coder={'provider':'ollama','model':'qwen2.5-coder:7b','options':{'num_ctx':16384,'num_predict':4096}}
            state=await_job(bench,bench.create(IDEA+' Preserve Café 🐜.',
                planner,coder,starter='sqlite',plan_mode='granular',acceptance_wire_version=3)['id'])
            self.assertEqual(state['status'],'proposed',state.get('error'))
            self.assertEqual(state['plan']['checks'],plan['checks'])
            self.assertEqual(len(transports),5)
            for call in state['model_calls']:
                self.assertLessEqual(call['input_estimate_tokens']+call['requested_max_output_tokens'],16384)
                self.assertGreaterEqual(call['reserved_text_output_tokens'],8192)
                self.assertEqual(call['planning_context_policy'],'stage_v1')
                self.assertEqual(call['schema_version'],3)
            self.assertFalse(state['approved']);self.assertEqual(bench.context_files(state['id']),{})
            self.assertEqual(state['planning_progress']['memory']['accepted_features'],2)
            self.assertEqual(state['guided_draft']['acceptance_draft']['planning_memory']['check_count'],3)
            from forge.diagnostic_report import _planning_metadata, _safe_history
            metadata=_planning_metadata(state,_safe_history(bench.directory(state['id']))['records'])
            self.assertEqual(metadata['memory']['known_contracts'],5)
            self.assertEqual(metadata['memory']['accepted_prefix_sha256'],state['guided_draft']['acceptance_draft']['planning_memory']['accepted_prefix_sha256'])
            self.assertNotIn('Café',json.dumps(metadata,ensure_ascii=False))
            # Stage-local content recovery must not erase a configuration failure.
            from forge.outline_planning import SCOPE_PROMPT
            state['job_model_rejections']={'ollama/qwen2.5-coder:7b':'configuration'}
            state['planner']['fallbacks']=[{'provider':'ollama','model':'qwen3.5:9b','options':{'num_ctx':16384,'num_predict':8192}}]
            replies.append(outline)
            bench.call_model(state,'planner',SCOPE_PROMPT,json.dumps({'planning_stage':'scope',
                'planning_context_policy':'stage_v1','request':{'idea':'A different scope'}}),threading.Event())
            self.assertNotEqual(transports[-1]['model'],'qwen2.5-coder:7b',state['events'][-6:])

    def test_rejected_primary_can_handle_the_next_different_feature(self):
        from forge.core import Workbench
        from tests.test_workbench import ScriptedModels,await_job
        plan,outline,packets,batches=self.packets()
        invalid=copy.deepcopy(packets[0]);invalid['checks'][1]['assertion']['expected']=[{'title':'Wrong array'}]
        models=ScriptedModels([outline,invalid,invalid,*packets,*batches])
        with tempfile.TemporaryDirectory() as folder:
            bench=Workbench(Path(folder)/'projects',models)
            planner={'provider':'ollama','model':'primary','fallbacks':[{'provider':'ollama','model':'backup'}]}
            coder={'provider':'ollama','model':'primary'}
            state=await_job(bench,bench.create('A useful SQLite wins tracker',planner,coder,starter='sqlite',
                plan_mode='granular',acceptance_wire_version=3)['id'])
            self.assertEqual(state['status'],'proposed',state.get('error'))
            self.assertEqual([c['model'] for c in state['model_calls'][:5]],['primary','primary','primary','backup','primary'])
            self.assertEqual(models.calls[2]['contract_feedback'][1]['known_contracts'][0]['response_kind'],'object')
            self.assertEqual(state['plan']['checks'],plan['checks'])

    def test_stricter_planning_probe_rejects_a_read_only_reply(self):
        from forge.planner_probe import run_probe
        from tests.test_workbench import ScriptedModels
        reply={'checks':[{'name':'Read','method':'GET','path':'/api/records','status':200,
                         'assertion':{'kind':'json_subset','expected':{'records':[{'title':'Diagnostic sample'}]}}}]}
        with tempfile.TemporaryDirectory() as folder:
            client=ScriptedModels([reply]);result=run_probe(client,'ollama','fixture',{},Path(folder)/'caps.json',version=2)
            self.assertEqual(result['status'],'failed')
            self.assertIn('probe_mutation_required',result['review_codes'])
            self.assertEqual(result['probe_version'],2)

    def test_static_interface_tool_never_imports_source_and_discloses_bounds(self):
        from forge.stage_context import interface_index
        source='raise RuntimeError("DO NOT EXECUTE")\nclass Store: pass\ndef create_server(host,port): pass\n'
        files={f'module{i:02}.py':source for i in range(35)}
        result=interface_index(files)
        self.assertEqual(len(result['files']),32)
        self.assertEqual(result['files_omitted'],3)
        self.assertEqual(result['files'][0]['symbols'],['Store','create_server'])
        self.assertNotIn('DO NOT EXECUTE',json.dumps(result))
        self.assertEqual(interface_index({'bad.py':'def incomplete('})['files'][0]['parse_status'],'unavailable')

    def test_new_guard_cases_keep_semantic_validation_enabled(self):
        from forge.stage_context import guard_probes
        result=guard_probes()
        self.assertEqual(result['status'],'passed')
        self.assertEqual(result['case_count'],4)
        self.assertEqual([row['code'] for row in result['cases']],['known_registry','unknown_contract','wrong_wrapper','missing_sample'])
        self.assertFalse(result['executed']);self.assertFalse(result['inference_tested'])

    def test_budget_refusal_keeps_numeric_evidence_and_sends_no_transport(self):
        from forge.core import Workbench
        from tests.test_workbench import await_job
        from forge.diagnostic_report import _safe_history
        with tempfile.TemporaryDirectory() as folder,patch('forge.models.request_json') as transport:
            bench=Workbench(Path(folder)/'projects')
            config={'provider':'ollama','model':'qwen2.5-coder:7b','options':{'num_ctx':16384,'num_predict':8192}}
            state=await_job(bench,bench.create('Build a notes application. '+'Café '*2000,config,config,
                starter='sqlite',plan_mode='granular',acceptance_wire_version=3)['id'])
            self.assertEqual(state['status'],'error');transport.assert_not_called()
            record=state['model_calls'][-1]
            self.assertGreater(record['required_context_tokens'],record['effective_context_tokens'])
            self.assertGreater(record['context_shortfall_tokens'],0)
            self.assertEqual(record['schema_version'],3)
            self.assertIs(record['transport_attempted'],False)
            history=_safe_history(bench.directory(state['id']))
            exported=next(r['data'] for r in history['records'] if r['kind']=='model_attempt')
            self.assertEqual(exported['required_context_tokens'],record['required_context_tokens'])
            self.assertNotIn('Café',json.dumps(history,ensure_ascii=False))

    def test_browser_capability_is_explicit_and_does_not_grant_execution(self):
        from forge.scaffolds import CATALOG
        from forge.guided import StageValidationError
        request={'starter':CATALOG['sqlite'],'acceptance_policy':'evidence_v1','acceptance_planning_policy':'feature_v3'}
        candidate={'checks':[{'name':'Create','method':'POST','path':'/api/records','status':201,
                             'body':{'title':'Sample'},'json_contains':{'title':'Sample'}}],
                   'browser_checks':[{'name':'Form exists','steps':[{'action':'expect_visible','selector':'#title'}]}]}
        with self.assertRaises(StageValidationError) as caught:compile_feature(scope(),{'checks':[]},candidate,0,request)
        self.assertEqual(caught.exception.review.findings[0].code,'browser_not_requested')
        allowed=compile_feature(scope(),{'checks':[]},candidate,0,{**request,'browser_automation_requested':True})
        self.assertEqual(allowed['browser_checks'][0]['feature_indexes'],[0])
        self.assertNotIn('execute',allowed)

    def test_explicit_policy_upgrade_retains_the_old_unapproved_draft(self):
        from forge.core import Workbench
        from tests.test_workbench import ScriptedModels,await_job
        plan,outline,packets,batches=self.packets()
        # v2 still requires its model's own API declaration.
        first=copy.deepcopy(packets[0]);first['api_contracts']=copy.deepcopy(plan['api_contracts'])
        models=ScriptedModels([outline,first,InterruptedError('Stop before the next feature')])
        with tempfile.TemporaryDirectory() as folder:
            bench=Workbench(Path(folder)/'projects',models);config={'provider':'ollama','model':'fixture'}
            state=await_job(bench,bench.create(IDEA,config,config,starter='sqlite',plan_mode='granular',acceptance_wire_version=2)['id'])
            previous=copy.deepcopy(state['guided_draft'])
            self.assertEqual(previous['acceptance_draft']['next_feature'],1)
            models.responses.extend([outline,*packets,*batches])
            bench.start(state['id'],'plan',{'plan_mode':'granular','acceptance_wire_version':3})
            state=await_job(bench,state['id'])
            self.assertEqual(state['status'],'proposed',state.get('error'))
            self.assertEqual(state['previous_guided_draft'],previous)
            self.assertFalse(state['approved'])
            self.assertEqual(state['plan']['checks'],plan['checks'])
