"""Acceptance corrections may fix unapproved checks, never frozen baseline evidence."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from forge.core import Workbench
from forge.models import request_schema
from forge.outline_planning import ACCEPTANCE_PROMPT, ACCEPTANCE_SCHEMA
from tests.test_guided_planning import feature_batches
from tests.test_workbench import await_job


def boundary_fixture():
    fixture=json.loads((Path(__file__).parent/'fixture_data/acceptance-guidance-v1.json').read_text())
    return fixture['scope'],fixture['invalid'],fixture['corrected'],fixture['task_batch']


class AcceptanceGuidanceTests(unittest.TestCase):
    def test_frozen_fixture_and_prior_sets_remain_unchanged(self):
        root=Path(__file__).parent/'fixture_data'
        old=json.loads((root/'frozen-regressions-v17.json').read_text())
        current=json.loads((root/'frozen-regressions-v18.json').read_text())
        self.assertEqual(current['sets'][:-1],old['sets'])
        for row in current['sets']:
            self.assertEqual(hashlib.sha256((root/row['file']).read_bytes()).hexdigest(),row['sha256'])
    def test_diag_distinguishes_retained_proposal_from_approved_plan(self):
        from forge.diagnostic_report import _planning_metadata
        scope,_,valid,_=boundary_fixture();plan={**scope,**valid}
        data=_planning_metadata({'plan':plan,'approved':False})
        self.assertFalse(data['approved_plan']['object'])
        self.assertTrue(data['retained_proposal']['object'])
        self.assertFalse(data['proposal_approved'])
        self.assertTrue(_planning_metadata({'plan':plan,'approved':True})['approved_plan']['object'])

    def test_diag_records_missing_coverage_without_manual_text(self):
        from forge.planning_diagnostics import candidate_shape
        scope,_,valid,_=boundary_fixture()
        candidate={**scope,**valid,'features':[*scope['features'],'Browser UI'],
                   'manual_checks':[{'name':'PRIVATE NAME','steps':['PRIVATE STEP'],'expected':'PRIVATE EXPECTED','feature_indexes':[1]}]}
        data=candidate_shape(candidate)
        self.assertEqual(data['uncovered_feature_indexes'],[2])
        self.assertEqual(data['manual_check_structure'],[{'index':0,'feature_indexes':[1]}])
        self.assertNotIn('PRIVATE',json.dumps(data))

    def test_instruction_following_correction_can_change_invalid_draft_checks(self):
        scope,invalid,valid,batch=boundary_fixture()
        class Models:
            def __init__(self):self.calls=[];self.tasks=iter(feature_batches(batch['tasks']))
            def __call__(self,*args):return self
            def complete(self,system,prompt):
                payload=json.loads(prompt);self.calls.append(payload)
                if payload['planning_stage']=='scope':return copy.deepcopy(scope)
                if payload['planning_stage']=='acceptance':
                    instruction=payload.get('correction_instruction','').lower()
                    return copy.deepcopy(valid if 'unapproved acceptance' in instruction and 'may change' in instruction else invalid)
                return next(self.tasks)
        models=Models()
        with tempfile.TemporaryDirectory() as temp:
            bench=Workbench(Path(temp)/'projects',models);config={'provider':'ollama','model':'fixture'}
            state=await_job(bench,bench.create('Persistent local tracker',config,config,plan_mode='guided')['id'])
            self.assertEqual(state['status'],'proposed',state.get('error'))
            self.assertEqual([p['planning_stage'] for p in models.calls],['scope','acceptance','acceptance','feature_tasks','feature_tasks'])
            self.assertEqual(state['plan']['checks'],valid['checks'])
            self.assertFalse(state['approved'])
            self.assertEqual(bench.files(state['id']),{})

    def test_native_acceptance_schema_constrains_references_to_saved_scope(self):
        scope,_,_,_=boundary_fixture();original=copy.deepcopy(ACCEPTANCE_SCHEMA)
        schema=request_schema(ACCEPTANCE_PROMPT,json.dumps({'planning_stage':'acceptance','scope':scope}))
        for field in ('checks','manual_checks','browser_checks'):
            self.assertEqual(schema['properties'][field]['items']['properties']['feature_indexes']['items']['enum'],[0,1])
        self.assertEqual(ACCEPTANCE_SCHEMA,original)

    def test_acceptance_request_contains_concrete_examples_and_fixed_coverage(self):
        from forge.outline_planning import create_outline
        import threading
        scope,_,valid,_=boundary_fixture();captured=[]
        def generate(system,payload,validate):captured.append(payload);validate(valid);return valid
        create_outline({'idea':'Tracker'},generate,lambda draft:None,{'scope':scope},threading.Event())
        payload=captured[0]
        self.assertIn('acceptance_examples',payload)
        self.assertEqual([row['index'] for row in payload['coverage_required']],[0,1])
        example=payload['acceptance_examples']['persistence_sequence']
        self.assertEqual([c['method'] for c in example],['POST','GET','DELETE'])
        self.assertTrue(example[1]['restart_before'])
        self.assertNotIn('restart_before',example[0])
