"""Synthetic replies reproduce observed outline failure classes, not model quality."""
import copy
import hashlib
import threading
import unittest
import json
from pathlib import Path
import tempfile
from unittest.mock import patch
from forge.guided import run_guided
from forge.planning_diagnostics import classify_finding
from tests.test_guided_planning import responses, feature_batches


class OutlineStageTests(unittest.TestCase):
    def test_frozen_failure_classifications_and_acceptance_assembly(self):
        from forge.outline_planning import assemble
        root=Path(__file__).parent/'fixture_data'
        for item in json.loads((root/'frozen-regressions-v16.json').read_text())['sets']:
            self.assertEqual(hashlib.sha256((root/item['file']).read_bytes()).hexdigest(),item['sha256'])
        fixture=json.loads((root/'outline-stages-v1.json').read_text())
        for case in fixture['cases']:
            self.assertEqual(classify_finding('guided_contract','/',case['message']),(case['code'],case['path']))
            self.assertEqual(hashlib.sha256(json.dumps(case['message'],ensure_ascii=False,separators=(',',':')).encode()).hexdigest(),case['message_sha256'])
        plan=assemble(fixture['scope'],fixture['acceptance'],{'acceptance_policy':'evidence_v1'})
        self.assertEqual(plan['checks'],fixture['acceptance']['checks'])

    def test_scope_resume_does_not_replay_accepted_scope(self):
        from tests.test_guided_planning import outline_replies
        outline,batch,expected=responses();scope,acceptance=outline_replies(outline)
        cancel=threading.Event();drafts=[]
        def checkpoint(draft):drafts.append(draft);cancel.set()
        request={'idea':'Tracker','task_planning_policy':'compiled_v1','outline_planning_policy':'split_v1'}
        with self.assertRaises(InterruptedError):
            run_guided(request,lambda system,payload,validate:scope,checkpoint,cancel)
        self.assertIsNone(drafts[-1]['outline']);self.assertEqual(drafts[-1]['scope'],scope)
        cancel.clear();replies=iter([acceptance,*feature_batches(batch['tasks'])]);stages=[]
        def generate(system,payload,validate):
            stages.append(payload['planning_stage']);reply=copy.deepcopy(next(replies));validate(reply);return reply
        self.assertEqual(run_guided(request,generate,drafts.append,cancel,drafts[-1]),expected)
        self.assertEqual(stages,['acceptance','feature_tasks','feature_tasks'])

    def test_acceptance_schema_is_sent_to_native_local_wire(self):
        from forge.models import ModelClient
        from forge.outline_planning import ACCEPTANCE_PROMPT,SCOPE_PROMPT
        for system,required in ((SCOPE_PROMPT,'features'),(ACCEPTANCE_PROMPT,'checks')):
            with patch('forge.models.request_json',return_value={'message':{'content':'{}'},'done':True}) as wire:
                ModelClient('ollama','fixture').complete(system,'{}')
                schema=wire.call_args.args[1]['format'];self.assertIn(required,schema['properties'])
                self.assertNotIn('tasks',schema['properties'])
                self.assertGreaterEqual(wire.call_args.args[1]['options']['num_predict'],8192)

    def test_acceptance_validation_preserves_multiple_failure_codes(self):
        from forge.guided import stage_review,validate_outline
        from tests.test_evidence_planning import sqlite_plan
        plan=sqlite_plan();outline={k:v for k,v in plan.items() if k!='tasks'}
        outline['checks'][0].pop('body');outline['checks'][1]['json_contains']={'records':[]}
        _,review=stage_review(validate_outline,outline)
        self.assertIn('mutation_example',[f.code for f in review.findings])
        self.assertIn('vacuous_assertion',[f.code for f in review.findings])

    def test_scope_and_acceptance_are_separate_checkpointed_calls(self):
        outline,batch,expected=responses()
        acceptance_keys={'checks','manual_checks','browser_checks','api_contracts'}
        scope={k:v for k,v in outline.items() if k not in acceptance_keys}
        acceptance={k:v for k,v in outline.items() if k in acceptance_keys}
        replies=iter([scope,acceptance,*feature_batches(batch['tasks'])]);stages=[];drafts=[]
        def generate(system,payload,validate):
            stages.append(payload['planning_stage']);reply=copy.deepcopy(next(replies));validate(reply);return reply
        result=run_guided({'idea':'Task tracker','task_planning_policy':'compiled_v1','outline_planning_policy':'split_v1'},
                          generate,drafts.append,threading.Event())
        self.assertEqual(stages,['scope','acceptance','feature_tasks','feature_tasks'])
        self.assertEqual(result,expected)
        self.assertIsNone(drafts[0]['outline'])
        self.assertEqual(drafts[0]['scope'],scope)

    def test_observed_rejections_have_specific_codes_and_paths(self):
        cases=[('Outline checks must be an array of objects.','check_structure','/checks'),
            ('Every feature needs acceptance check coverage. Missing feature indexes: [6, 8].','acceptance_coverage','/features'),
            ('Every check needs contains, nonempty json_contains, or json_equals.','assertion_required','/checks'),
            ('/checks/0: Supply concrete nonempty JSON request example data; for a deliberately bodyless endpoint explain request_body_optional_reason (20–500 characters).','mutation_example','/checks/0'),
            ('/checks/2: Restart checks must GET a concrete value created by an earlier successful request to this collection. Health or empty data does not prove persistence.','persistence_evidence','/checks/2')]
        for message,code,path in cases:
            with self.subTest(code=code):self.assertEqual(classify_finding('guided_contract','/',message),(code,path))
