"""Diagnostic (8) derived regressions. No captured response bodies or live quality claim."""
import copy
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from forge.contracts import review_plan
from tests.fixtures import PLAN


def wire(candidate):
    result=copy.deepcopy(candidate)
    for check in result['checks']:
        for field,kind in (('contains','text'),('json_contains','json_subset'),('json_equals','json_exact'),('empty_body','empty')):
            if field in check:
                value=check.pop(field)
                check['assertion']={'kind':kind,'expected':None if kind=='empty' else value}
    return result


class DiagnosticRevisionTests(unittest.TestCase):
    def test_frozen_observed_ledger_and_labeled_synthetic_wire_cases(self):
        import hashlib
        from forge.planning_diagnostics import latest_planning_run
        from forge.assertions import compile_assertion,AssertionErrorDetail
        root=Path(__file__).parent/'fixture_data'
        previous=json.loads((root/'frozen-regressions-v21.json').read_text())
        current=json.loads((root/'frozen-regressions-v22.json').read_text())
        self.assertEqual(current['sets'][:-1],previous['sets'])
        for row in current['sets']:self.assertEqual(hashlib.sha256((root/row['file']).read_bytes()).hexdigest(),row['sha256'])
        fixture=json.loads((root/'diag-planner-wire-v2.json').read_text())
        result=latest_planning_run(fixture['records'])
        for key,value in fixture['expected_observation'].items():
            self.assertEqual(result['stages']['acceptance_feature']['accepted'] if key=='acceptance_accepted' else result[key],value)
        signature=fixture['legacy_message_signature']
        encoded=json.dumps(signature['known_source_literal']).encode()
        self.assertEqual(hashlib.sha256(encoded).hexdigest(),signature['sha256'])
        self.assertEqual(len(encoded),signature['bytes'])
        for case in fixture['synthetic_wire_cases']:
            if 'expected_code' in case:
                with self.assertRaises(AssertionErrorDetail) as caught:compile_assertion(case['assertion'],'/checks/0/assertion')
                self.assertEqual(caught.exception.code,case['expected_code'])
            else:self.assertEqual(compile_assertion(case['assertion'],'/'),{case['expected_field']:case['expected_value']})

    def test_missing_assertion_has_a_specific_rule_and_check_path(self):
        plan = copy.deepcopy(PLAN)
        plan['checks'][1].pop('contains')
        result = review_plan(plan)
        self.assertFalse(result.passed)
        self.assertEqual([(f.code, f.path) for f in result.findings], [('assertion_required', '/checks/1')])

    def test_candidate_shape_distinguishes_present_but_empty_assertions(self):
        from forge.planning_diagnostics import candidate_shape
        result = candidate_shape({'checks': [{'json_contains': {}, 'empty_body': False}]})
        check = result['check_structure'][0]
        self.assertTrue(check['has_assertion'])
        self.assertIs(check.get('assertion_valid'), False)
        self.assertEqual(check.get('invalid_assertion_fields'), ['json_contains', 'empty_body'])

    def test_wire_compiles_exact_values_without_mutating_input(self):
        from forge.assertions import compile_wire
        for kind,value,field in [('text','Café 🐜','contains'),('json_subset',{'title':'Café 🐜'},'json_contains'),
                                 ('json_exact',[],'json_equals'),('json_exact',None,'json_equals'),('empty',None,'empty_body')]:
            candidate={'checks':[{'assertion':{'kind':kind,'expected':value}}]};before=copy.deepcopy(candidate)
            result=compile_wire(candidate)
            self.assertEqual(result,{'checks':[{field:True if kind=='empty' else value}]})
            self.assertEqual(candidate,before)
        for assertion in ({'kind':'text','expected':''},{'kind':'json_subset','expected':{}},
                          {'kind':'empty','expected':False},{'kind':'invented','expected':7},None):
            with self.subTest(assertion=assertion),self.assertRaises(ValueError):
                compile_wire({'checks':[{'assertion':assertion}]})
        with self.assertRaisesRegex(ValueError,'mix legacy'):
            compile_wire({'checks':[{'assertion':{'kind':'text','expected':'ok'},'contains':'ok'}]})

    def test_v2_native_schema_has_no_mixed_properties_anyof(self):
        from forge.feature_acceptance import WIRE_PROMPT,WIRE_SCHEMA
        from forge.models import request_schema
        self.assertEqual(request_schema(WIRE_PROMPT,'{}'),WIRE_SCHEMA)
        def inspect(value):
            if isinstance(value,dict):
                self.assertFalse('properties' in value and 'anyOf' in value)
                for child in value.values():inspect(child)
            elif isinstance(value,list):
                for child in value:inspect(child)
        inspect(WIRE_SCHEMA)
        check=WIRE_SCHEMA['properties']['checks']['items']
        self.assertIn('assertion',check['required'])
        self.assertNotIn('json_contains',check['properties'])

    def test_real_ollama_http_adapter_sends_v2_schema_and_explicit_reservation(self):
        import os
        from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
        from forge.models import ModelClient
        from forge.planner_probe import run_probe
        from forge.feature_acceptance import WIRE_SCHEMA
        reply={'checks':[{'name':'Create record','method':'POST','path':'/api/records','status':201,
                         'body':{'title':'Diagnostic sample'},'assertion':{'kind':'json_subset','expected':{'id':1,'title':'Diagnostic sample'}}}],
               'api_contracts':[{'method':'POST','path':'/api/records','status':201,'response_kind':'object','required_fields':['id','title']}]}
        requests=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                requests.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
                data=json.dumps({'done':True,'done_reason':'stop','model':'fixture','message':{'content':json.dumps(reply)},'eval_count':123,'prompt_eval_count':456}).encode()
                self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(data)
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,{'OLLAMA_URL':'http://127.0.0.1:'+str(server.server_port),'NO_PROXY':'127.0.0.1','no_proxy':'127.0.0.1'}):
                client=ModelClient('ollama','fixture')
                result=run_probe(client,'ollama','fixture',{'options':{'num_ctx':32768,'num_predict':8192}},Path(folder)/'caps.json')
                self.assertEqual(result['status'],'passed',result)
                self.assertEqual(requests[0]['format'],WIRE_SCHEMA)
                self.assertEqual(requests[0]['options']['num_ctx'],32768)
                self.assertGreaterEqual(requests[0]['options']['num_predict'],8192)
                self.assertEqual(result['requested_max_output_tokens'],requests[0]['options']['num_predict'])
                self.assertEqual(result['observed_output_tokens'],123)
                self.assertEqual(result['finish_reason'],'stop')
                self.assertEqual(client.last_metadata['schema_sha256'],result['schema_sha256'])
                self.assertNotIn('PRIVATE',requests[0]['messages'][1]['content'])
                with patch('forge.models.request_json') as transport,self.assertRaisesRegex(Exception,'does not fit'):
                    run_probe(client,'ollama','fixture',{'options':{'num_ctx':4096}},Path(folder)/'caps.json')
                transport.assert_not_called()
        finally:server.shutdown();server.server_close()

    def test_v2_round_trip_preserves_full_approval_checks_and_resumes_prefix(self):
        from forge.outline_planning import create_outline
        from tests.test_guided_planning import outline_replies
        from tests.test_feature_acceptance import feature_replies
        from tests.test_evidence_planning import sqlite_plan
        plan=sqlite_plan();scope,acceptance=outline_replies({k:v for k,v in plan.items() if k!='tasks'})
        packets=[wire(p) for p in feature_replies(acceptance,2)];calls=[];saved=[];cancel=threading.Event()
        request={'idea':'Keep this exact idea Café 🐜','acceptance_planning_policy':'feature_v2','acceptance_policy':'evidence_v1'}
        def generate(system,payload,validate):
            calls.append(payload);reply=packets[payload['target_feature_index']];validate(reply);return copy.deepcopy(reply)
        def checkpoint(draft):saved.append(draft);cancel.set()
        with self.assertRaises(InterruptedError):create_outline(request,generate,checkpoint,{'scope':scope},cancel)
        self.assertEqual(saved[-1]['acceptance_draft']['policy'],'feature_v2')
        self.assertEqual(saved[-1]['acceptance_draft']['next_feature'],1)
        cancel.clear();calls.clear()
        result=create_outline(request,generate,saved.append,saved[-1],cancel)
        self.assertEqual([p['target_feature_index'] for p in calls],[1])
        self.assertEqual(result['checks'],plan['checks'])
        self.assertEqual(calls[0]['request']['idea'],request['idea'])

    def test_real_workbench_v2_correction_uses_current_feature_fields(self):
        from forge.core import Workbench
        from tests.test_workbench import ScriptedModels,await_job
        from tests.test_guided_planning import outline_replies,feature_batches
        from tests.test_feature_acceptance import feature_replies
        from tests.test_evidence_planning import sqlite_plan
        plan=sqlite_plan();scope,acceptance=outline_replies({k:v for k,v in plan.items() if k!='tasks'})
        packets=[wire(p) for p in feature_replies(acceptance,2)]
        invalid=copy.deepcopy(packets[0]);invalid['checks'][0]['assertion']={'kind':'json_subset','expected':{}}
        models=ScriptedModels([scope,invalid,*packets,*feature_batches(plan['tasks'])])
        with tempfile.TemporaryDirectory() as folder:
            bench=Workbench(Path(folder)/'projects',models);config={'provider':'ollama','model':'fixture'}
            state=await_job(bench,bench.create('A useful SQLite wins tracker',config,config,starter='sqlite',plan_mode='granular',acceptance_wire_version=2)['id'])
            self.assertEqual(state['status'],'proposed',state.get('error'))
            self.assertEqual(state['plan']['checks'],plan['checks'])
            self.assertFalse(state['approved'])
            self.assertEqual(state['model_calls'][1]['review_codes'],['assertion_value'])
            correction=models.calls[2]
            self.assertEqual(correction['target_feature'],scope['features'][0])
            self.assertTrue(correction['wire_examples'])
            self.assertEqual(correction['earlier_acceptance'],{'checks':[]})


class DiagnosticSessionTests(unittest.TestCase):
    def make(self,folder,replies=(),collector=None):
        from forge.core import Workbench
        from forge.system_tests import SystemTests
        from forge.diagnostic_session import DiagnosticSession
        from tests.test_workbench import ScriptedModels
        models=ScriptedModels(list(replies));bench=Workbench(Path(folder)/'projects',models)
        runner=SystemTests(bench,lambda:{},lambda:{'connected':True})
        def collect(*args,**kwargs):
            return {'schema':1,'id':'fixture-report','created_at':'2026-10-22T12:00:00Z','summary':{},'findings':[],
                    'evidence':{'system_tests':copy.deepcopy(kwargs['test_snapshot'])},
                    'completeness':{'complete':True,'omissions':[]}}
        session=DiagnosticSession(bench,Path(folder),runner,collector=collector or collect)
        return bench,models,runner,session

    def finish(self,session):
        session.worker.join(8)
        self.assertFalse(session.worker.is_alive())
        result=session.status()
        self.assertTrue(result['download_ready'],result)
        return result

    def test_quick_session_owns_tests_and_same_report_export_survives_restart(self):
        import io,zipfile
        from forge.diagnostic_session import DiagnosticSession
        with tempfile.TemporaryDirectory() as folder:
            bench,models,runner,session=self.make(folder)
            started=session.start(None,[]);result=self.finish(session)
            self.assertEqual(result['status'],'finished')
            self.assertEqual(models.calls,[])
            owned=session.report['evidence']['system_tests']['id']
            runner.start([]);runner.worker.join(5)
            self.assertNotEqual(runner.status()['id'],owned)
            with zipfile.ZipFile(io.BytesIO(session.export(started['id']))) as z:
                self.assertEqual(json.loads(z.read('evidence/system_tests.json'))['id'],owned)
                self.assertEqual(json.loads(z.read('evidence/diagnostic_session.json'))['id'],started['id'])
            restored=DiagnosticSession(bench,Path(folder),runner)
            self.assertTrue(restored.status()['download_ready'])
            self.assertEqual(restored.report,session.report)
            self.assertEqual(restored.export(started['id']),session.export(started['id']))
            with self.assertRaises(ValueError):session.export('stale-session')

    def test_busy_workbench_collects_without_running_or_attaching_other_tests(self):
        with tempfile.TemporaryDirectory() as folder:
            bench,models,runner,session=self.make(folder)
            bench.test_busy=True
            runner.report={'id':'unrelated','rows':[{'code':'other','status':'passed'}]}
            session.start(None,[]);result=self.finish(session)
            self.assertEqual(result['status'],'partial')
            self.assertEqual(result['checks_skipped_reason'],'workbench_busy')
            self.assertEqual(session.report['evidence']['system_tests']['rows'],[])
            self.assertFalse(session.report['completeness']['complete'])
            self.assertEqual(models.calls,[])

    def test_stop_waits_for_owned_test_then_exports_partial_and_rejects_overlap(self):
        with tempfile.TemporaryDirectory() as folder:
            _,models,runner,session=self.make(folder)
            entered=threading.Event();release=threading.Event()
            runner.local=lambda:(entered.set(),release.wait(5),{'connected':True})[-1]
            session.start(None,[]);self.assertTrue(entered.wait(3))
            with self.assertRaises(ValueError):session.start(None,[])
            self.assertFalse(session.status()['download_ready'])
            session.stop();release.set();result=self.finish(session)
            self.assertEqual(result['status'],'stopped')
            self.assertEqual(session.report['evidence']['system_tests']['status'],'stopped')
            self.assertEqual(models.calls,[])

    def test_fixed_planning_probe_is_explicit_and_does_not_use_project_data(self):
        reply={'checks':[{'name':'Create record','method':'POST','path':'/api/records','status':201,
                         'body':{'title':'Diagnostic sample'},'assertion':{'kind':'json_subset','expected':{'id':1,'title':'Diagnostic sample'}}}],
               'api_contracts':[{'method':'POST','path':'/api/records','status':201,'response_kind':'object','required_fields':['id','title','note','created_at']}]}
        with tempfile.TemporaryDirectory() as folder:
            bench,models,runner,session=self.make(folder,[reply])
            session.start(None,[{'provider':'ollama','model':'fixture'},{'provider':'groq','model':'never-call-cloud'}],'planning')
            self.finish(session)
            row=next(r for r in runner.status()['rows'] if r['code']=='planner_stage_probe')
            self.assertEqual(row['status'],'passed',row)
            self.assertEqual(row['schema_version'],3)
            self.assertEqual(len(row['schema_sha256']),64)
            self.assertEqual(models.calls[0]['acceptance_planning_policy'],'feature_v3')
            self.assertFalse(runner.status()['project_content_sent'])
            self.assertEqual(bench.list_projects(),[])
            self.assertEqual(len(models.calls),1)

    def test_cloud_probe_requires_consent_before_session_start(self):
        with tempfile.TemporaryDirectory() as folder:
            _,models,_,session=self.make(folder)
            with self.assertRaisesRegex(ValueError,'Explicitly'):
                session.start(None,[{'provider':'groq','model':'fixture'}],'cloud')
            self.assertEqual(models.calls,[])
            self.assertIsNone(session.worker)

    def test_failed_planning_probe_records_precise_assertion_evidence(self):
        reply={'checks':[{'name':'Create','path':'/api/records','method':'POST','status':201,
                         'assertion':{'kind':'json_subset','expected':{}}}]}
        with tempfile.TemporaryDirectory() as folder:
            _,_,runner,session=self.make(folder,[reply])
            session.start(None,[{'provider':'ollama','model':'fixture'}],'planning');self.finish(session)
            row=next(r for r in runner.status()['rows'] if r['code']=='planner_stage_probe')
            self.assertEqual(row['failure_class'],'schema_error')
            self.assertEqual(row['review_findings'],[{'code':'assertion_value','path':'/checks/0/assertion'}])
            self.assertFalse(row['candidate_shape']['check_structure'][0]['assertion_valid'])
            self.assertEqual(row['candidate_shape']['check_structure'][0]['invalid_assertion_fields'],['assertion'])
            self.assertEqual(session.status()['checks']['rows'],runner.status()['rows'])

    def test_stop_does_not_cancel_a_new_independent_test_during_collection(self):
        collecting=threading.Event();collected=threading.Event();second=threading.Event();release=threading.Event()
        def collector(*args,**kwargs):
            collecting.set();collected.wait(5)
            return {'id':'report','summary':{},'findings':[],'evidence':{'system_tests':kwargs['test_snapshot']},
                    'completeness':{'complete':True,'omissions':[]}}
        with tempfile.TemporaryDirectory() as folder:
            _,_,runner,session=self.make(folder,collector=collector)
            session.start(None,[]);self.assertTrue(collecting.wait(3))
            owned=session.state['test_report_id']
            runner.local=lambda:(second.set(),release.wait(5),{'connected':True})[-1]
            runner.start([]);self.assertTrue(second.wait(3))
            try:
                session.stop()
                self.assertFalse(runner.cancel.is_set())
                collected.set();self.finish(session)
                self.assertEqual(session.report['evidence']['system_tests']['id'],owned)
                self.assertNotEqual(owned,runner.status()['id'])
            finally:collected.set();release.set();runner.worker.join(5)
