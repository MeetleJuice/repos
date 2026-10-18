"""Direct manual-failure repairs and exact edits must preserve approved evidence."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from forge.context import browser_feedback
from forge.edits import expand_response
from forge.evidence import validate_evidence
import tests.test_evidence as evidence
from tests.test_evidence import game_plan
from tests.test_workbench import await_job


class ExactEditTests(unittest.TestCase):
    def test_sequential_edits_and_new_files(self):
        result = expand_response({'files': {'new.js': 'new'}, 'edits': [
            {'file': 'game.js', 'search': 'before', 'replace': 'middle'},
            {'file': 'game.js', 'search': 'middle', 'replace': 'after'}]}, {'game.js': 'before'})
        self.assertEqual(result, {'new.js': 'new', 'game.js': 'after'})

    def test_rejects_ambiguous_missing_unchanged_or_malformed_edits(self):
        current = {'game.js': 'one one'}
        for edit in [None, {}, {'file': 'game.js', 'search': 'one', 'replace': 'two'},
                     {'file': 'game.js', 'search': 'absent', 'replace': 'two'},
                     {'file': 'game.js', 'search': '', 'replace': 'two'},
                     {'file': 'missing.js', 'search': 'one', 'replace': 'two'},
                     {'file': 'game.js', 'search': 'one one', 'replace': 'one one'},
                     {'file': [], 'search': 'one', 'replace': 'two'}]:
            with self.subTest(edit=edit), self.assertRaises(ValueError):
                expand_response({'edits': [edit]}, current)
        with self.assertRaises(ValueError):
            expand_response({'edits':[{'file':'overlap.js','search':'aa','replace':'b'}]}, {'overlap.js':'aaa'})
        with self.assertRaises(ValueError):
            expand_response({'files': {'game.js': 'other'}, 'edits': [{'file': 'game.js','search': 'one one','replace': 'two'}]},current)

    def test_atomic_rejection_and_frozen_checks(self):
        with tempfile.TemporaryDirectory() as temp:
            bench, ident, _ = evidence.EvidenceTests().make_game(Path(temp))
            state = bench.load(ident); before = bench.files(ident)
            for name in ['CHECKS.json', 'MANUAL-CHECKS.md', 'test_foundation.py', '../escape.js']:
                text = before.get(name, 'old')
                response = {'files': {'new.js': 'never written'}, 'edits': [{'file':name,'search':text,'replace':text+'\nchanged'}]}
                with self.subTest(name=name), self.assertRaises(ValueError):
                    bench.apply(state, response)
                self.assertEqual(bench.files(ident), before)
            with self.assertRaises(ValueError):
                bench.apply(state, {'edits':[{'file':'game.js','search':'missing unique text','replace':'x'}]})
            self.assertEqual(bench.files(ident),before)


class ManualRepairTests(unittest.TestCase):
    def prepare(self, root):
        bench, ident, models = evidence.EvidenceTests().make_game(root)
        bench.start(ident, 'build', {'execute':True,'consent':True,'runtime':'local','repairs':0})
        state=await_job(bench,ident)
        self.assertEqual(state['status'],'review_required',state.get('error'))
        return bench,ident,models

    def test_direct_repair_runs_checks_without_replanning_or_changing_frozen_tests(self):
        with tempfile.TemporaryDirectory() as temp:
            bench,ident,models=self.prepare(Path(temp))
            state=bench.record_manual(ident,[True,False,True,True],['','Pausing does not freeze the canvas.','',''])
            before=bench.files(ident); plan=copy.deepcopy(state['plan']); frozen=copy.deepcopy(state['frozen_tests'])
            # Controlled response exercises orchestration; it is not a claim of model quality.
            models.responses.append({'edits':[{'file':'game.js','search':'"use strict";','replace':'"use strict";\n// targeted repair fixture'}]})
            calls=len(models.calls)
            bench.start(ident,'repair',{'execute':True,'consent':True,'runtime':'local','repairs':1})
            state=await_job(bench,ident)
            self.assertEqual(state['status'],'review_required',state.get('error'))
            self.assertEqual(len(models.calls),calls+1)
            self.assertEqual(models.calls[-1]['manual_evidence']['failures'][0]['observed'],'Pausing does not freeze the canvas.')
            self.assertEqual(state['plan'],plan);self.assertEqual(state['frozen_tests'],frozen)
            self.assertEqual(state['manual_results'],{})
            self.assertTrue(state['checks']['passed'])
            self.assertEqual(len(state['repair_history']),1)
            for name in ['CHECKS.json','MANUAL-CHECKS.md','test_app.py','test_foundation.py']:
                self.assertEqual(bench.files(ident)[name],before[name])
            self.assertTrue(any(s['label']=='Before repair' for s in state['snapshots']))

    def test_repair_rejects_stale_missing_notes_and_zero_budget(self):
        with tempfile.TemporaryDirectory() as temp:
            bench,ident,models=self.prepare(Path(temp));calls=len(models.calls)
            with self.assertRaisesRegex(ValueError,'Save failed'):
                bench.start(ident,'repair',{'repairs':1})
            bench.record_manual(ident,[True,False,True,True])
            with self.assertRaisesRegex(ValueError,'Describe what'):
                bench.start(ident,'repair',{'repairs':1})
            bench.record_manual(ident,[True,False,True,True],['','Actual failure','',''])
            for execute in ['true','false',1,{}]:
                with self.subTest(execute=execute),self.assertRaisesRegex(ValueError,'JSON boolean'):
                    bench.start(ident,'repair',{'execute':execute,'runtime':'local','repairs':1})
            with self.assertRaisesRegex(ValueError,'execution consent'):
                bench.start(ident,'repair',{'execute':True,'runtime':'local','repairs':1})
            with self.assertRaisesRegex(ValueError,'at least one'):
                bench.start(ident,'repair',{'repairs':0})
            path=bench.directory(ident)/'source/game.js';path.write_text(path.read_text()+'\n// changed')
            with self.assertRaisesRegex(ValueError,'Source changed'):
                bench.start(ident,'repair',{'repairs':1})
            self.assertEqual(len(models.calls),calls)

    def test_files_only_repair_never_executes_and_retains_failure_history(self):
        with tempfile.TemporaryDirectory() as temp:
            bench,ident,models=self.prepare(Path(temp))
            bench.record_manual(ident,[False,True,True,True],['Keyboard movement fails.','','',''])
            models.responses.append({'edits':[{'file':'game.js','search':'"use strict";','replace':'"use strict";\n// patch'}]})
            bench.verifier=lambda *args:self.fail('Execution was not authorized')
            bench.start(ident,'repair',{'execute':False,'repairs':1})
            state=await_job(bench,ident)
            self.assertEqual(state['status'],'generated',state.get('error'))
            self.assertIsNone(state['checks']);self.assertIsNone(state['verification_fingerprint'])
            self.assertFalse(state['repair_history'][0]['execution_requested'])
            self.assertEqual(state['repair_history'][0]['evidence']['failures'][0]['observed'],'Keyboard movement fails.')

    def test_unchanged_repair_stops_without_execution_and_preserves_report(self):
        with tempfile.TemporaryDirectory() as temp:
            bench,ident,models=self.prepare(Path(temp))
            bench.record_manual(ident,[False,True,True,True],['Keyboard movement fails.','','',''])
            models.responses.append({'files':{'game.js':bench.files(ident)['game.js']}})
            bench.verifier=lambda *args:self.fail('Unchanged source must not run again')
            bench.start(ident,'repair',{'execute':True,'consent':True,'runtime':'local','repairs':1})
            state=await_job(bench,ident)
            self.assertEqual(state['status'],'needs_attention')
            self.assertTrue(any('unchanged source' in event['message'] for event in state['events']))
            self.assertEqual(state['manual_results']['notes'][0],'Keyboard movement fails.')
            self.assertEqual(state['repair_history'][0]['evidence']['failures'][0]['observed'],'Keyboard movement fails.')

    def test_bad_exact_edit_recovers_once_using_complete_files(self):
        with tempfile.TemporaryDirectory() as temp:
            bench,ident,models=self.prepare(Path(temp))
            bench.record_manual(ident,[False,True,True,True],['Keyboard movement fails.','','',''])
            before=bench.files(ident);calls=len(models.calls)
            models.responses.extend([{'edits':[{'file':'game.js','search':'missing line','replace':'fixed'}]},
                                     {'files':{'game.js':before['game.js']+'\n// complete-file recovery fixture'}}])
            bench.start(ident,'repair',{'execute':False,'repairs':1})
            state=await_job(bench,ident)
            self.assertEqual(state['status'],'generated',state.get('error'))
            self.assertEqual(len(models.calls),calls+2)
            self.assertEqual(models.calls[-1]['response_mode'],'complete_files')
            self.assertEqual(models.calls[-1]['files']['game.js'],before['game.js'])
            self.assertEqual(bench.files(ident)['game.js'],before['game.js']+'\n// complete-file recovery fixture')
            self.assertEqual(state['manual_results'],{})
            self.assertIsNone(state['checks'])

    def test_failed_correction_keeps_saved_observations_on_unchanged_source(self):
        with tempfile.TemporaryDirectory() as temp:
            bench,ident,models=self.prepare(Path(temp))
            previous=bench.record_manual(ident,[False,True,True,True],['Keyboard movement fails.','','',''])
            before=bench.files(ident);calls=len(models.calls)
            models.responses.extend([{'edits':[{'file':'game.js','search':'missing line','replace':'fixed'}]},{}])
            bench.start(ident,'repair',{'execute':False,'repairs':1})
            state=await_job(bench,ident)
            self.assertEqual(state['status'],'error')
            self.assertEqual(len(models.calls),calls+2)
            self.assertEqual(bench.files(ident),before)
            self.assertEqual(state['manual_results'],previous['manual_results'])
            self.assertEqual(state['verification_fingerprint'],previous['verification_fingerprint'])
            self.assertEqual(state['checks'],previous['checks'])
            self.assertEqual(len(state['snapshots']),len(previous['snapshots']))
            # Reproduce the user's next step: server-only re-verification cannot erase the failed gameplay result.
            calls=len(models.calls)
            bench.start(ident,'build',{'execute':True,'consent':True,'runtime':'local','repairs':0})
            state=await_job(bench,ident)
            self.assertEqual(state['status'],'needs_attention')
            self.assertTrue(state['checks']['passed'])
            self.assertEqual(state['manual_results'],previous['manual_results'])
            self.assertEqual(len(models.calls),calls)

    def test_runtime_unavailable_does_not_request_code(self):
        with tempfile.TemporaryDirectory() as temp:
            bench,ident,models=self.prepare(Path(temp))
            bench.record_manual(ident,[False,True,True,True],['Keyboard movement fails.','','',''])
            calls=len(models.calls)
            with patch('forge.core.require_runtime',side_effect=ValueError('Docker unavailable')):
                bench.start(ident,'repair',{'execute':True,'consent':True,'runtime':'docker','repairs':1})
                state=await_job(bench,ident)
            self.assertEqual(len(models.calls),calls)
            self.assertEqual(state['manual_results']['notes'][0],'Keyboard movement fails.')

    def test_source_change_during_runtime_preparation_prevents_repair(self):
        with tempfile.TemporaryDirectory() as temp:
            bench,ident,models=self.prepare(Path(temp))
            bench.record_manual(ident,[False,True,True,True],['Keyboard movement fails.','','',''])
            calls=len(models.calls)
            def change_source(mode):
                path=bench.directory(ident)/'source/game.js'
                path.write_text(path.read_text()+'\n// external edit during runtime setup')
            with patch('forge.core.require_runtime',side_effect=change_source):
                bench.start(ident,'repair',{'execute':True,'consent':True,'runtime':'local','repairs':1})
                state=await_job(bench,ident)
            self.assertIn('Source changed while preparing',state['error'])
            self.assertEqual(len(models.calls),calls)
            self.assertEqual(state['manual_results']['notes'][0],'Keyboard movement fails.')

    def test_notes_validation(self):
        with tempfile.TemporaryDirectory() as temp:
            bench,ident,_=self.prepare(Path(temp))
            for notes in [[],[1]*4,['x'*2001]*4]:
                with self.subTest(notes=type(notes[0]) if notes else None),self.assertRaisesRegex(ValueError,'2000'):
                    bench.record_manual(ident,[False,True,True,True],notes)


class ClockContractTests(unittest.TestCase):
    def check(self, **fields):
        return {'name':'Replay','feature_indexes':[1],'clock':True,
                'steps':[{'action':'advance_time','ms':1000},{'action':'expect_text_exact','selector':'#state','value':'Playing'}],**fields}

    def test_clock_and_random_bounds(self):
        for fields in [{'clock':1},{'clock':False},{'random_seed':True},{'random_seed':-1},
                       {'random_values':[]},{'random_values':[True]},{'random_values':[float('nan')]},
                       {'random_values':[1]},{'random_values':[0.2],'random_seed':1},
                       {'steps':[{'action':'advance_time','ms':10001},{'action':'expect_visible','selector':'#game'}]}]:
            plan=game_plan();plan['browser_checks']=[self.check(**fields)]
            with self.subTest(fields=fields),self.assertRaises(ValueError):validate_evidence(plan)
        plan=game_plan();plan['browser_checks']=[self.check(random_seed=42),self.check(random_values=[0,0.5])]
        validate_evidence(plan)

    def test_clock_dependency_blocks_before_model_requests(self):
        from forge.runner import require_browser_runtime
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'BROWSER-CHECKS.json').write_text(json.dumps([self.check()]))
            with patch('forge.browser_runner.diagnostics',return_value={'available':True,'clock_supported':False}):
                with self.assertRaisesRegex(ValueError,'No model request'):
                    require_browser_runtime(root,'local')

    def test_replay_budget(self):
        plan=game_plan();plan['browser_checks']=[self.check(steps=[{'action':'advance_time','ms':10000}]*4+[{'action':'expect_visible','selector':'#game'}])]
        with self.assertRaisesRegex(ValueError,'30 seconds'):validate_evidence(plan)


class FeedbackBudgetTests(unittest.TestCase):
    def test_browser_feedback_bounds_and_marks_omissions(self):
        detail={'check':'Visible state','step_number':20,'step':{'action':'expect_text_exact','value':'v'*2000},
                'completed_steps':[{'action':'fill','value':'v'*2000}]*19,
                'random_values':[0.25]*256,'error':'e'*4000}
        report=browser_feedback(detail)
        self.assertLess(len(json.dumps(report)),5000)
        self.assertEqual(report['completed_steps_omitted'],15)
        self.assertEqual(report['random_values_omitted'],224)
        self.assertEqual(report['step_number'],20)


class RecoverySchemaTests(unittest.TestCase):
    def test_native_recovery_requires_complete_nonempty_files(self):
        from forge.models import ModelClient
        from forge.prompts import CODE
        from forge.schemas import COMPLETE_CODE_SCHEMA
        with patch('forge.models.request_json',return_value={'message':{'content':'{"files":{"game.js":"updated"}}'}}) as request:
            response=ModelClient('ollama','fixture').complete(CODE,json.dumps({'response_mode':'complete_files'}))
        self.assertEqual(response,{'files':{'game.js':'updated'}})
        payload=request.call_args.args[1]
        self.assertEqual(payload['format'],COMPLETE_CODE_SCHEMA)
        self.assertEqual(payload['format']['properties']['files']['minProperties'],1)
        self.assertIn('Do not return edits',payload['messages'][0]['content'])
