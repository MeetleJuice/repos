"""Feature acceptance compilation; fixtures do not establish live model quality."""
import copy
import hashlib
import json
import threading
import unittest
from pathlib import Path
import tempfile
from forge.outline_planning import create_outline
from tests.test_guided_planning import responses,outline_replies


def feature_replies(acceptance, count):
    replies=[]
    for target in range(count):
        fields={}
        for key in ('checks','manual_checks','browser_checks'):
            rows=[{k:copy.deepcopy(v) for k,v in row.items() if k!='feature_indexes'}
                  for row in acceptance.get(key,[]) if row.get('feature_indexes')==[target]]
            if rows or key=='checks':fields[key]=rows
        if acceptance.get('api_contracts'):fields['api_contracts']=copy.deepcopy(acceptance['api_contracts'])
        replies.append(fields)
    return replies


class FeatureAcceptanceTests(unittest.TestCase):
    def test_frozen_five_feature_case_covers_the_previously_missing_ui_slot(self):
        root=Path(__file__).parent/'fixture_data'
        previous=json.loads((root/'frozen-regressions-v18.json').read_text())
        current=json.loads((root/'frozen-regressions-v19.json').read_text())
        self.assertEqual(current['sets'][:-1],previous['sets'])
        for row in current['sets']:self.assertEqual(hashlib.sha256((root/row['file']).read_bytes()).hexdigest(),row['sha256'])
        fixture=json.loads((root/'feature-acceptance-v1.json').read_text());calls=[]
        def generate(system,payload,validate):
            calls.append(payload);reply=fixture['packets'][payload['target_feature_index']];validate(reply);return copy.deepcopy(reply)
        result=create_outline({'idea':'Preserve this exact idea 🐜','revision':'Keep timestamps','acceptance_policy':'evidence_v1',
            'acceptance_planning_policy':'feature_v1','previous_proposal':{'rejected':'OBSOLETE DRAFT'}},generate,lambda draft:None,{'scope':fixture['scope']},threading.Event())
        self.assertEqual([p['target_feature_index'] for p in calls],list(range(5)))
        self.assertEqual([c['feature_indexes'] for c in result['checks']],fixture['expected_http_feature_indexes'])
        self.assertEqual([c['feature_indexes'] for c in result['manual_checks']],fixture['expected_manual_feature_indexes'])
        self.assertNotIn('OBSOLETE DRAFT',json.dumps(calls))

    def test_project_packet_omits_rejected_plan_but_preserves_user_and_baseline_values(self):
        from forge.feature_acceptance import packet_request
        request={'idea':'Café 🐜','revision':'Keep every feature','existing_project':{'checks':[{'value':'EXACT APPROVED'}]},
                 'previous_proposal':{'tasks':['STALE REJECTED '*1000]},'starter_source':{'app.py':'SOURCE CODE'},'change_request':'Keep data'}
        original=copy.deepcopy(request);packet,manifest=packet_request(request)
        self.assertEqual(packet['idea'],request['idea']);self.assertEqual(packet['existing_project'],request['existing_project'])
        self.assertNotIn('STALE REJECTED',json.dumps(packet));self.assertNotIn('SOURCE CODE',json.dumps(packet))
        self.assertEqual({row['field'] for row in manifest['omitted_fields']},{'previous_proposal','starter_source'})
        self.assertEqual(request,original)

    def test_empty_or_hallucinated_feature_references_cannot_advance(self):
        from forge.feature_acceptance import compile_feature
        scope,acceptance=outline_replies(responses()[0]);earlier={'checks':[]};before=copy.deepcopy(earlier)
        candidates=[{'checks':[]},{'checks':[{'name':'Health','method':'GET','path':'/health','status':200,'json_contains':{'status':'ok'}}]},
                    {'checks':[{**acceptance['checks'][0],'feature_indexes':[999]}]}]
        for candidate in candidates:
            with self.subTest(candidate=candidate),self.assertRaises(ValueError):compile_feature(scope,earlier,candidate,0,{})
        self.assertEqual(earlier,before)

    def test_manual_first_prefix_is_saved_but_never_approvable_as_a_full_plan(self):
        from forge.feature_acceptance import compile_feature
        from forge.contracts import review_plan,validate_structure
        scope,_=outline_replies(responses()[0])
        fields=compile_feature(scope,{'checks':[]},{'checks':[],'manual_checks':[{'name':'Use UI','steps':['Click Add'],'expected':'An entry appears.'}]},0,{})
        self.assertEqual(fields['manual_checks'][0]['feature_indexes'],[0])
        with self.assertRaises(ValueError):validate_structure({**scope,**fields},partial_acceptance=True)
        self.assertFalse(review_plan({**scope,**fields}).passed)

    def test_native_feature_schema_is_smaller_and_controller_owned(self):
        from forge.feature_acceptance import PROMPT,SCHEMA
        from forge.models import request_schema
        schema=request_schema(PROMPT,'{}')
        self.assertEqual(schema,SCHEMA)
        self.assertEqual(schema['properties']['checks']['maxItems'],4)
        for field in ('checks','manual_checks','browser_checks'):
            self.assertNotIn('feature_indexes',schema['properties'][field]['items']['properties'])
            self.assertFalse(schema['properties'][field]['items']['additionalProperties'])

    def test_real_granular_workbench_reaches_review_with_unchanged_sqlite_checks(self):
        from forge.core import Workbench
        from tests.test_workbench import ScriptedModels,await_job
        from tests.test_evidence_planning import sqlite_plan
        from tests.test_guided_planning import feature_batches
        plan=sqlite_plan();scope,acceptance=outline_replies({k:v for k,v in plan.items() if k!='tasks'})
        models=ScriptedModels([scope,*feature_replies(acceptance,2),*feature_batches(plan['tasks'])])
        with tempfile.TemporaryDirectory() as temp:
            bench=Workbench(Path(temp)/'projects',models);config={'provider':'ollama','model':'fixture'}
            state=await_job(bench,bench.create('A local SQLite accomplishment tracker',config,config,starter='sqlite',plan_mode='granular')['id'])
            self.assertEqual(state['status'],'proposed',state.get('error'));self.assertFalse(state['approved'])
            self.assertEqual(state['plan']['checks'],plan['checks'])
            self.assertEqual([p['planning_stage'] for p in models.calls],['scope','acceptance_feature','acceptance_feature','feature_tasks','feature_tasks'])
            self.assertEqual(state['planning_progress']['acceptance_features_planned'],2)
            models.responses.extend([scope,acceptance,*feature_batches(plan['tasks'])])
            bench.start(state['id'],'plan',{'plan_mode':'proof'})
            restored=await_job(bench,state['id'])
            self.assertEqual(restored['status'],'proposed',restored.get('error'))
            self.assertFalse(restored.get('feature_acceptance',False))
            self.assertEqual(restored['plan']['checks'],plan['checks'])

    def test_one_feature_per_request_and_controller_owned_references(self):
        scope,acceptance=outline_replies(responses()[0]);calls=[];draft={'scope':scope};saved=[]
        replies=feature_replies(acceptance,len(scope['features']))
        def generate(system,payload,validate):
            calls.append(payload)
            reply=replies[payload['target_feature_index']] if 'target_feature_index' in payload else acceptance
            validate(reply);return copy.deepcopy(reply)
        plan=create_outline({'idea':'Tracker','acceptance_planning_policy':'feature_v1'},generate,saved.append,draft,threading.Event())
        self.assertEqual([p['planning_stage'] for p in calls],['acceptance_feature','acceptance_feature'])
        self.assertEqual(plan['checks'],acceptance['checks'])
        self.assertEqual(saved[-1]['acceptance_draft']['next_feature'],2)

    def test_validated_acceptance_prefix_survives_interruption(self):
        scope,acceptance=outline_replies(responses()[0]);draft={'scope':scope};saved=[];cancel=threading.Event();calls=[]
        replies=feature_replies(acceptance,2)
        def generate(system,payload,validate):
            calls.append(payload)
            reply=replies[payload['target_feature_index']] if 'target_feature_index' in payload else acceptance
            validate(reply);return copy.deepcopy(reply)
        def stop(value):saved.append(value);cancel.set()
        with self.assertRaises(InterruptedError):create_outline({'acceptance_planning_policy':'feature_v1'},generate,stop,draft,cancel)
        cancel.clear();calls.clear()
        plan=create_outline({'acceptance_planning_policy':'feature_v1'},generate,saved.append,saved[-1],cancel)
        self.assertEqual([p['target_feature_index'] for p in calls],[1])
        self.assertEqual(plan['checks'],acceptance['checks'])
