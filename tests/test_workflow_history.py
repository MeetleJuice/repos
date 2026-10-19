"""Frozen controller regressions; fixtures are not live model-quality evidence."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from forge.core import Workbench
from forge.context import fingerprint
from forge import history
from tests.fixtures import APP, TEST, PLAN
from tests.test_cloud import state_for
from tests.test_workbench import ScriptedModels, await_job


class WorkflowHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
    def tearDown(self): self.temp.cleanup()

    def built(self):
        models = ScriptedModels([PLAN, {'files':{'app.py':APP,'test_app.py':TEST},'summary':'Model says done'}])
        bench = Workbench(self.root/'projects', models)
        config = {'provider':'ollama','model':'fixture'}
        state = bench.create('Build a task tracker',config,config)
        state = await_job(bench,state['id'])
        bench.approve(state['id'],state['plan'])
        bench.start(state['id'],'build',{})
        state = await_job(bench,state['id'])
        self.assertEqual(state['status'],'generated',state.get('error'))
        return bench,state

    def verified_fixture(self):
        bench,state = self.built()
        state.update(checks={'passed':True,'phases':[]},status='verified',verification_fingerprint=fingerprint(bench.context_files(state['id'])))
        state['frozen_tests'] = {'test_app.py':hashlib.sha256(TEST.encode()).hexdigest()}
        bench.save(state)
        return bench,state

    def test_frozen_workflow_fixture(self):
        path=Path(__file__).parent/'fixture_data/workflow-audit-v1.json'
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),'901a04b683017c868144817ed4cc6d85c78b965ca6d09b2fee27187359007afe')
        manifest=json.loads(path.with_name('frozen-regressions-v4.json').read_text())
        self.assertEqual(manifest['sets'][-1]['sha256'],hashlib.sha256(path.read_bytes()).hexdigest())

    def test_attempt_totals_survive_recent_window(self):
        models=ScriptedModels([PLAN]*105)
        bench=Workbench(self.root/'projects',models);state=state_for(bench)
        state['model_totals']=history.totals_for({})
        for _ in range(105):bench.call_model(state,'coder','fixture','{}',threading.Event())
        self.assertEqual(len(state['model_calls']),100)
        self.assertEqual(state['model_totals']['requests'],105)
        attempts=[r for r in bench.history(state['id'])['records'] if r['kind']=='model_attempt']
        self.assertEqual(len(attempts),105)
        self.assertFalse(state['model_totals']['legacy_incomplete'])

    def test_legacy_history_is_imported_once_and_labeled_incomplete(self):
        bench=Workbench(self.root/'projects');state=state_for(bench)
        state['model_calls']=[{'provider':'ollama','model':'fixture','seconds':1,'time':bench.now()}]*100
        state['events']=[{'time':bench.now(),'message':'Old event'}];bench.save(state)
        first=bench.history(state['id']);second=bench.history(state['id'])
        self.assertEqual(first,second)
        self.assertEqual(len(first['records']),102)
        self.assertTrue(first['coverage']['legacy_history_incomplete'])
        self.assertTrue(history.totals_for(state)['legacy_incomplete'])

    def test_journal_retention_does_not_delete_durable_records(self):
        bench=Workbench(self.root/'projects');state=state_for(bench)
        for i in range(305):bench.event(state,str(i))
        self.assertEqual(len(state['events']),300)
        doc=bench.history(state['id'])
        self.assertEqual(sum(r['kind']=='journal' for r in doc['records']),305)
        self.assertTrue(doc['coverage']['complete_since_tracking_started'])

    def test_job_correlations_and_model_attribution(self):
        bench,state=self.built();doc=bench.history(state['id'])
        starts=[r for r in doc['records'] if r['kind']=='job_started']
        ends=[r for r in doc['records'] if r['kind']=='job_finished']
        self.assertEqual(len(starts),2);self.assertEqual({r['run_id'] for r in starts},{r['run_id'] for r in ends})
        self.assertNotIn('active_run_id',state)
        summaries=[r for r in doc['records'] if r['origin']=='model_report']
        self.assertEqual(summaries[-1]['data']['message'],'Model says done')
        self.assertTrue(any(r['kind']=='files_committed' and r['data']['changed_files'] for r in doc['records']))
        self.assertNotIn(APP,json.dumps(doc))

    def test_export_contains_snapshot_manifest_and_history(self):
        bench,state=self.verified_fixture();files,report,doc=bench.export_snapshot(state['id'])
        self.assertEqual(report['status'],'verified')
        self.assertTrue(report['evidence_status']['automated_evidence_current'])
        self.assertIn('model_calls',report);self.assertIn('journal',report)
        for entry in report['file_manifest']:
            self.assertEqual(entry['sha256'],hashlib.sha256(files[entry['file']].encode()).hexdigest())
        self.assertEqual(doc['records'][-1]['kind'],'export_prepared')
        self.assertIsNone(doc['records'][-1]['run_id'])

    def test_changed_source_cannot_inherit_verified_export_or_ui(self):
        bench,state=self.verified_fixture()
        (bench.directory(state['id'])/'source/app.py').write_text(APP+'\n# external edit\n')
        _,report,_=bench.export_snapshot(state['id'])
        self.assertEqual(report['status'],'needs_attention')
        self.assertEqual(report['recorded_status'],'verified')
        self.assertFalse(report['checks']['passed'])
        self.assertTrue(report['checks']['historical_passed'])
        self.assertFalse(report['evidence_status']['automated_evidence_current'])
        presented=bench.present(state['id'])
        self.assertEqual(presented['status'],'needs_attention');self.assertFalse(presented['checks']['passed'])
        self.assertTrue(bench.load(state['id'])['checks']['passed']) # historical evidence preserved

    def test_changed_approved_checks_cannot_inherit_verified_export(self):
        bench,state=self.verified_fixture()
        (bench.directory(state['id'])/'source/CHECKS.json').write_text('[]')
        _,report,_=bench.export_snapshot(state['id'])
        self.assertFalse(report['evidence_status']['automated_evidence_current'])
        self.assertEqual(report['status'],'needs_attention')
        self.assertTrue(any('CHECKS.json' in issue for issue in report['evidence_status']['issues']))

    def test_metadata_names_are_reserved_against_model_overwrite(self):
        bench,state=self.built()
        for name in ('BUILD-REPORT.json','RUN-HISTORY.json'):
            with self.assertRaises(ValueError):bench.apply(state,{'files':{name:'{}'}})

    def test_partial_history_is_disclosed_and_new_records_recover(self):
        bench=Workbench(self.root/'projects');state=state_for(bench);bench.event(state,'before')
        path=bench.directory(state['id'])/'workflow-history.jsonl'
        with path.open('ab') as f:f.write(b'{"schema":')
        self.assertTrue(bench.history(state['id'])['coverage']['trailing_partial_record'])
        bench.event(state,'after')
        doc=bench.history(state['id'])
        self.assertEqual(doc['coverage']['malformed_records'],1)
        self.assertFalse(doc['coverage']['complete_since_tracking_started'])
        self.assertEqual(doc['records'][-1]['data']['message'],'after')

    def test_history_limit_is_explicit_and_does_not_destroy_source(self):
        bench,state=self.built()
        with patch('forge.history.MAX_HISTORY_BYTES',1):bench.event(state,'cannot append')
        self.assertIn('16 MB',state['history_warning'])
        self.assertEqual(bench.files(state['id'])['app.py'],APP)
        self.assertFalse(bench.history(state['id'])['coverage']['complete_since_tracking_started'])

    def test_known_keys_are_redacted_in_history_and_report(self):
        bench,state=self.built()
        with patch.dict(os.environ,{'GEMINI_API_KEY':'secret-fixture-value'}):
            bench.event(state,'secret-fixture-value is not logged')
            _,report,doc=bench.export_snapshot(state['id'])
        self.assertNotIn('secret-fixture-value',json.dumps(doc))
        self.assertNotIn('secret-fixture-value',json.dumps(report))

    def test_restart_marks_incomplete_run_in_history(self):
        bench,state=self.built();state['status']='building';state['active_run_id']='interrupted-fixture';bench.save(state)
        restarted=Workbench(self.root/'projects')
        self.assertEqual(restarted.load(state['id'])['status'],'interrupted')
        self.assertNotIn('active_run_id',restarted.load(state['id']))
        self.assertTrue(any(r['kind']=='job_interrupted' and r['run_id']=='interrupted-fixture' for r in restarted.history(state['id'])['records']))

    def test_uncollected_test_module_cannot_hide_behind_passing_tests(self):
        from forge.runner import verify
        source=self.root/'generated';source.mkdir()
        (source/'app.py').write_text(APP)
        (source/'CHECKS.json').write_text(json.dumps(PLAN['checks']))
        (source/'test_app.py').write_text(TEST)
        (source/'test_uncollected.py').write_text('import app\ndef test_should_fail():\n    assert False\n')
        result=verify(source,'local',threading.Event())
        self.assertFalse(result['passed'])
        self.assertIn('test definitions were not collected',result['log'])
        self.assertEqual(result['failure_kind'],'application')

    def test_function_testcase_load_tests_is_supported(self):
        from forge.runner import verify
        source=self.root/'generated';source.mkdir()
        (source/'app.py').write_text(APP)
        (source/'CHECKS.json').write_text(json.dumps(PLAN['checks']))
        (source/'test_app.py').write_text(TEST)
        (source/'test_function.py').write_text('import unittest\nimport app\ndef test_function():\n    assert app.create_server\ndef load_tests(loader, tests, pattern):\n    return unittest.TestSuite([unittest.FunctionTestCase(test_function)])\n')
        result=verify(source,'local',threading.Event())
        self.assertTrue(result['passed'],result['log'])

    def test_current_bundle_manifest_detects_launcher_change(self):
        from forge.reporting import file_manifest
        bench,state=self.verified_fixture()
        state['verification_manifest']=file_manifest(bench.files(state['id']));bench.save(state)
        (bench.directory(state['id'])/'source/run.bat').write_text('@echo changed\n')
        _,report,_=bench.export_snapshot(state['id'])
        self.assertFalse(report['evidence_status']['automated_evidence_current'])
        self.assertTrue(report['evidence_status']['bundle_manifest_available'])
        self.assertEqual(report['status'],'needs_attention')

    def test_contract_json_comparison_preserves_boolean_number_distinction(self):
        bench,state=self.verified_fixture()
        checks=json.loads(json.dumps(state['plan']['checks']))
        checks[0]['feature_indexes'][0]=False # False must not match approved integer 0.
        (bench.directory(state['id'])/'source/CHECKS.json').write_text(json.dumps(checks))
        _,report,_=bench.export_snapshot(state['id'])
        self.assertFalse(report['evidence_status']['automated_evidence_current'])

    def test_history_endpoint_requires_session_and_zip_includes_evidence(self):
        import io,zipfile,urllib.request,urllib.error
        from forge.server import make_server
        bench,state=self.verified_fixture();server=make_server(0,bench)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        base='http://127.0.0.1:'+str(server.server_port)
        try:
            with urllib.request.urlopen(base) as response:
                token=response.read().decode().split('name="foundry-token" content="')[1].split('"')[0]
            path=base+'/api/projects/'+state['id']
            with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(path+'/history')
            self.assertEqual(error.exception.code,403)
            with urllib.request.urlopen(urllib.request.Request(path+'/download',headers={'X-Foundry-Token':token})) as response:
                content=response.read()
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                report=json.loads(archive.read('generated-app/BUILD-REPORT.json'))
                journal=json.loads(archive.read('generated-app/RUN-HISTORY.json'))
                self.assertEqual(report['status'],'verified')
                self.assertEqual(report['approved_plan'],state['plan'])
                self.assertTrue(journal['records'])
                self.assertEqual(len(archive.namelist()),len(set(archive.namelist())))
                for item in report['file_manifest']:
                    self.assertEqual(item['sha256'],hashlib.sha256(archive.read('generated-app/'+item['file'])).hexdigest())
        finally:server.shutdown();server.server_close()

    def test_preflight_budget_failure_is_not_a_transport_attempt(self):
        from forge.models import ModelError
        bench=Workbench(self.root/'projects');state=state_for(bench)
        state['coder']={'provider':'ollama','model':'fixture','options':{'num_ctx':8192,'num_predict':4096}}
        state['model_totals']=history.totals_for({})
        with patch('forge.models.request_json') as request:
            with self.assertRaises(ModelError):bench.call_model(state,'coder','fixture',json.dumps({'context':'x'*12000}),threading.Event())
        self.assertEqual(request.call_count,0)
        self.assertEqual(state['model_totals']['requests'],1)
        self.assertEqual(state['model_totals']['transport_attempts'],0)
        self.assertEqual(state['model_totals']['transport_unknown'],0)
        self.assertFalse(state['model_calls'][-1]['transport_attempted'])

    def test_missing_key_is_recorded_without_transport_or_fake_usage(self):
        from forge.models import ModelError
        bench=Workbench(self.root/'projects');state=state_for(bench)
        state['coder']={'provider':'gemini','model':'gemini-3.8-flash'}
        with patch.dict(os.environ,{},clear=True),patch('forge.models.request_json') as request:
            with self.assertRaises(ModelError):bench.call_model(state,'coder','fixture','{}',threading.Event())
        self.assertFalse(state['model_calls'][-1]['transport_attempted'])
        self.assertEqual(request.call_count,0)
        self.assertNotIn('completion_tokens',state['model_calls'][-1])

    def test_missing_tracking_start_is_not_reported_complete(self):
        bench,state=self.built();path=bench.directory(state['id'])/'workflow-history.jsonl'
        lines=path.read_bytes().splitlines(keepends=True);path.write_bytes(b''.join(lines[1:]))
        coverage=bench.history(state['id'])['coverage']
        self.assertTrue(coverage['tracking_origin_unknown'])
        self.assertFalse(coverage['complete_since_tracking_started'])

    def test_restart_recovers_attempt_durable_before_state_swap(self):
        bench=Workbench(self.root/'projects');state=state_for(bench)
        state.update(status='building',active_run_id='crash-gap',model_totals=history.totals_for({}))
        bench.save(state)
        bench.trace(state,'model_attempt',{'provider':'ollama','model':'fixture','seconds':2,'prompt_tokens':12,'completion_tokens':7,'transport_attempted':True})
        # Deliberately do not save updated state counters, reproducing the write gap.
        recovered=Workbench(self.root/'projects').load(state['id'])
        self.assertEqual(recovered['model_totals']['requests'],1)
        self.assertEqual(recovered['model_totals']['prompt_tokens'],12)
        self.assertEqual(recovered['model_totals']['transport_attempts'],1)
        self.assertEqual(recovered['status'],'interrupted')
