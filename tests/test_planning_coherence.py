"""Uploaded proposal contradictions; fixtures are not live model benchmarks."""
import copy
import json
from pathlib import Path
import unittest
import tempfile
import hashlib
from forge.contracts import review_plan
from forge.task_planning import compile_tasks, schedule
from tests.test_evidence_planning import sqlite_plan


def uploaded_plan():
    return json.loads((Path(__file__).parent/'fixture_data/planning-coherence-v1.json').read_text())['plan']


class PlanningCoherenceTests(unittest.TestCase):
    def test_frozen_uploaded_case_appends_without_rewriting_previous_sets(self):
        root=Path(__file__).parent/'fixture_data'
        previous=json.loads((root/'frozen-regressions-v19.json').read_text())
        current=json.loads((root/'frozen-regressions-v20.json').read_text())
        self.assertEqual(current['sets'][:-1],previous['sets'])
        for row in current['sets']:self.assertEqual(hashlib.sha256((root/row['file']).read_bytes()).hexdigest(),row['sha256'])

    def test_feature_task_packet_uses_real_checks_and_excludes_rejected_plan(self):
        import threading
        from forge.task_planning import run_compiled
        from tests.test_guided_planning import feature_batches
        plan=sqlite_plan();outline={key:value for key,value in plan.items() if key!='tasks'}
        batches=iter(feature_batches(plan['tasks']));calls=[]
        request={'idea':'Café 🐜','revision':'Keep this exact revision','existing_project':{'frozen':'ORIGINAL BASELINE'},
            'previous_proposal':{'tasks':['OBSOLETE REJECTED DRAFT']}}
        def generate(system,payload,validate):
            reply=outline if payload['planning_stage']=='outline' else next(batches)
            calls.append(payload);validate(reply);return copy.deepcopy(reply)
        result=run_compiled(request,generate,lambda draft:None,threading.Event())
        packets=[p for p in calls if p['planning_stage']=='feature_tasks']
        self.assertNotIn('OBSOLETE REJECTED DRAFT',json.dumps(packets))
        for packet in packets:
            self.assertEqual(packet['request']['idea'],request['idea'])
            self.assertEqual(packet['request']['existing_project'],request['existing_project'])
            self.assertEqual(packet['context_manifest']['omitted_fields'][0]['field'],'previous_proposal')
        self.assertEqual(packets[0]['target_acceptance']['checks'],plan['checks'])
        self.assertEqual(result['checks'],plan['checks'])

    def test_invalid_saved_outline_discards_its_invalid_acceptance_prefix_but_keeps_scope(self):
        import threading
        from forge.task_planning import run_compiled
        from tests.test_guided_planning import feature_batches,outline_replies
        from tests.test_feature_acceptance import feature_replies
        plan=sqlite_plan();scope,acceptance=outline_replies({key:value for key,value in plan.items() if key!='tasks'})
        bad=copy.deepcopy(acceptance);bad['checks'][2].pop('restart_before')
        request={'acceptance_policy':'evidence_v1','acceptance_planning_policy':'feature_v1','outline_planning_policy':'split_v1'}
        saved={'schema':2,'task_planning_policy':'compiled_v1',
            'request_sha256':hashlib.sha256(json.dumps(request,sort_keys=True).encode()).hexdigest(),
            'scope':scope,'outline':{**scope,**bad,'acceptance_policy':'evidence_v1'},'tasks':[],'next_feature':0,
            'acceptance_draft':{'policy':'feature_v1','next_feature':2,'fields':bad}}
        replies=iter([*feature_replies(acceptance,2),*feature_batches(plan['tasks'])]);calls=[]
        def generate(system,payload,validate):
            calls.append(payload['planning_stage']);reply=next(replies);validate(reply);return copy.deepcopy(reply)
        result=run_compiled(request,generate,lambda draft:None,threading.Event(),saved)
        self.assertEqual(calls,['acceptance_feature','acceptance_feature','feature_tasks','feature_tasks'])
        self.assertEqual(result['checks'],plan['checks'])

    def test_probe_cases_exercise_real_reviewer_without_execution(self):
        from forge.coherence import guard_probes
        result=guard_probes()
        self.assertEqual(result['status'],'passed',result)
        self.assertEqual(result['case_count'],8)
        self.assertFalse(result['executed'])

    def test_uploaded_browser_plan_cannot_pass_full_reviewer(self):
        plan=uploaded_plan();before=copy.deepcopy(plan)
        review=review_plan(plan)
        self.assertFalse(review.passed,'The uploaded contradictory plan must not be approvable.')
        codes={finding.code for finding in review.findings}
        self.assertTrue({'task_endpoint_mismatch','duplicate_task','missing_persistence_scenario',
            'duplicate_create_id','missing_ui_task','missing_api_contract','missing_milestone'}<=codes,codes)
        self.assertEqual(plan,before)

    def test_browser_api_checks_are_scheduled_like_server_checks(self):
        plan=sqlite_plan();plan['app_kind']='browser'
        outline={key:value for key,value in plan.items() if key!='tasks'}
        tasks=schedule(outline,plan['tasks'])
        self.assertEqual(tasks[0].get('check_indexes'),[0,1,2])
        self.assertTrue(review_plan({**outline,'tasks':tasks}).passed)

    def test_wrong_endpoint_is_rejected_before_saving_a_task_batch(self):
        plan=sqlite_plan();outline={key:value for key,value in plan.items() if key!='tasks'}
        candidate={'tasks':[{key:copy.deepcopy(value) for key,value in uploaded_plan()['tasks'][0].items()
            if key not in {'feature_indexes','depends_on','check_indexes'}}]}
        with self.assertRaisesRegex(ValueError,'endpoint|API'):
            compile_tasks(candidate,outline,[],0,3,None)

    def test_parameterized_routes_and_literal_inline_browser_intent_remain_valid(self):
        from forge.coherence import matches
        self.assertTrue(matches('DELETE','/api/records/123',{'method':'DELETE','path':'/api/records/{id}'}))
        self.assertFalse(matches('GET','/api/records/123',{'method':'DELETE','path':'/api/records/{id}'}))
        plan=sqlite_plan();plan['app_kind']='browser'
        plan['tasks'][1]['files']=['app.py'];plan['tasks'][1]['instructions']='Serve the HTML form inline from the Python handler.'
        self.assertTrue(review_plan(plan).passed)

    def test_distinct_interface_contracts_are_not_identical_work(self):
        from forge.coherence import task_digest
        task=copy.deepcopy(uploaded_plan()['tasks'][0]);other=copy.deepcopy(task)
        other['interfaces'][0]['contract']='Returns an isolated server with a caller-supplied database path.'
        self.assertNotEqual(task_digest(task),task_digest(other))

    def test_server_label_cannot_hide_explicit_interactive_manual_requirements(self):
        plan=uploaded_plan();plan['app_kind']='server'
        self.assertIn('missing_ui_task',{finding.code for finding in review_plan(plan).findings})

    def test_deleted_seed_cannot_prove_persistence_after_restart(self):
        plan=sqlite_plan();plan['checks'].insert(2,{'name':'Delete saved record','method':'DELETE',
            'path':'/api/records/1','status':204,'empty_body':True,'feature_indexes':[0]})
        plan['api_contracts'].append({'method':'DELETE','path':'/api/records/{id}','status':204,'response_kind':'empty','required_fields':[]})
        plan['tasks'][0]['check_indexes']=[3]
        self.assertIn('persistence_seed_state',{f.code for f in review_plan(plan).findings})

    def test_ordering_uses_two_live_seeds_and_order_sensitive_assertions(self):
        from tests.test_evidence_planning import proof_plan
        from forge.harness import subset
        plan=proof_plan();plan['features'][1]+=' newest first'
        plan['checks'].insert(1,{'name':'Create second record','method':'POST','path':'/api/tasks','status':201,
            'body':{'title':'Newer record'},'json_contains':{'title':'Newer record'},'feature_indexes':[0]})
        plan['checks'][2].pop('json_contains');plan['checks'][2]['json_equals']=[{'title':'Newer record'},{'title':'Buy milk'}]
        plan['tasks'][0]['check_indexes']=[2]
        self.assertTrue(review_plan(plan).passed,review_plan(plan).findings)
        exact=plan['checks'][2].pop('json_equals');plan['checks'][2]['json_contains']=exact
        self.assertTrue(subset(list(reversed(exact)),exact),'Existing subset semantics are deliberately unordered.')
        self.assertIn('ordering_scenario',{f.code for f in review_plan(plan).findings})

    def test_current_review_blocks_old_green_proposal_without_mutating_approval(self):
        from forge.core import Workbench
        from tests.test_workbench import ScriptedModels,await_job
        from tests.fixtures import PLAN
        with tempfile.TemporaryDirectory() as folder:
            models=ScriptedModels([PLAN]);bench=Workbench(Path(folder)/'projects',models);cfg={'provider':'ollama','model':'fixture'}
            state=await_job(bench,bench.create('A local tracker',cfg,cfg)['id'])
            state.update(plan=uploaded_plan(),plan_review={'passed':True},evidence_planning=True);bench.save(state)
            original=bench.load(state['id']);shown=bench.present(state['id'])
            self.assertFalse(shown['current_plan_review']['passed']);self.assertTrue(shown['plan_review']['passed'])
            with self.assertRaises(ValueError):bench.approve(state['id'],state['plan'])
            self.assertEqual(bench.load(state['id']),original)
            state['approved']=True;bench.save(state)
            self.assertNotIn('current_plan_review',bench.present(state['id']))
            self.assertEqual(bench.load(state['id'])['plan'],state['plan'])
            self.assertEqual(len(models.calls),1)

    def test_test_button_and_diag_report_codes_without_source_or_model_calls(self):
        from forge.core import Workbench
        from forge.system_tests import SystemTests,read_tests
        from forge.diagnostic_report import _planning_metadata
        from tests.test_workbench import ScriptedModels,await_job
        from tests.fixtures import PLAN
        with tempfile.TemporaryDirectory() as folder:
            models=ScriptedModels([PLAN]);bench=Workbench(Path(folder)/'projects',models);cfg={'provider':'ollama','model':'fixture'}
            state=await_job(bench,bench.create('PRIVATE ORIGINAL IDEA',cfg,cfg)['id'])
            state.update(plan=uploaded_plan(),plan_review={'passed':True});bench.save(state);original=bench.load(state['id'])
            runner=SystemTests(bench,lambda:{},lambda:{'connected':True});runner.start([],project_id=state['id']);runner.worker.join(5)
            self.assertFalse(runner.worker.is_alive());report=read_tests(runner.path)
            guards=next(row for row in report['rows'] if row['code']=='planning_guards')
            self.assertEqual(guards['status'],'passed');self.assertEqual(guards['case_count'],8)
            audit=next(row for row in report['rows'] if row['code']=='project_plan')
            self.assertEqual(audit['status'],'failed');self.assertIn('task_endpoint_mismatch',audit['review_codes'])
            metadata=_planning_metadata(state)
            self.assertTrue(metadata['stored_review_passed']);self.assertFalse(metadata['current_review']['passed'])
            self.assertGreater(len(metadata['current_review']['duplicate_task_groups']),0)
            self.assertNotIn('Learned to use SQLite',json.dumps(metadata));self.assertNotIn('PRIVATE ORIGINAL IDEA',runner.path.read_text())
            self.assertEqual(bench.load(state['id']),original);self.assertEqual(len(models.calls),1)

    def test_latest_run_excludes_old_failures_and_preserves_missing_timings(self):
        from forge.planning_diagnostics import latest_planning_run
        rows=[{'kind':'model_attempt','run_id':'old','data':{'seconds':900,'success':False}},
            {'kind':'job_started','run_id':'new','data':{'action':'plan'}},
            {'kind':'model_attempt','run_id':'new','data':{'planning_stage':'feature_tasks','success':True}},
            {'kind':'job_finished','run_id':'new','data':{'status':'proposed','model_attempts':1,'seconds':20}}]
        result=latest_planning_run(rows)
        self.assertEqual(result['recorded_attempts'],1);self.assertFalse(result['history_may_be_partial'])
        self.assertIsNone(result['stages']['feature_tasks']['seconds'])
        self.assertEqual(result['stages']['feature_tasks']['unknown_timings'],1)
