"""Source-bound recovery evidence; scripted replies are not live-model results."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
import threading
from unittest.mock import patch

from forge.core import Workbench
from forge.diagnostic_report import collect_report, export_report
from tests.fixtures import PLAN, APP, BROKEN, TEST
from tests.test_workbench import ScriptedModels, await_job


class RunDiagnosticsTests(unittest.TestCase):
    def test_frozen_loop_scenarios_append_without_changing_previous_sets(self):
        import hashlib
        from forge.run_diagnostics import loop_guards
        root = Path(__file__).parent/'fixture_data'
        previous = json.loads((root/'frozen-regressions-v20.json').read_text())
        current = json.loads((root/'frozen-regressions-v21.json').read_text())
        self.assertEqual(current['sets'][:-1], previous['sets'])
        for row in current['sets']:
            self.assertEqual(hashlib.sha256((root/row['file']).read_bytes()).hexdigest(), row['sha256'])
        fixture = json.loads((root/'run-loop-evidence-v1.json').read_text())
        self.assertEqual([r['code'] for r in loop_guards()['cases']], [r['code'] for r in fixture['cases']])
        self.assertEqual([r['observed_validation'] for r in loop_guards()['cases']], [r['expected'] for r in fixture['cases']])

    def event(self, kind, run='build-1', **data):
        return {'id': kind, 'kind': kind, 'run_id': run, 'data': data}

    def test_fixed_loop_guards_keep_static_prefix_and_behavior_separate(self):
        from forge.run_diagnostics import loop_guards
        result = loop_guards()
        self.assertEqual(result['status'], 'passed', result)
        self.assertEqual(result['case_count'], 6)
        self.assertFalse(result['executed'])
        self.assertFalse(result['inference_tested'])

    def test_report_size_pruning_keeps_repair_links_within_exported_history(self):
        with tempfile.TemporaryDirectory() as folder:
            bench, state, _ = self.build(folder)
            with patch('forge.diagnostic_report._ollama_probe', return_value={'status': 'unavailable'}), \
                 patch('forge.diagnostic_report.MAX_REPORT_BYTES', 35000):
                report = collect_report(bench, Path(__file__).resolve().parents[1], project_id=state['id'])
            self.assertTrue(report['completeness']['omissions'])
            project = next(row for row in report['evidence']['projects'] if row['project_id']==state['id'])
            ids = {r['id'] for r in project.get('history', {}).get('records', [])}
            latest = report['summary']['selected_execution'] or {}
            for repair in latest.get('repairs', []):
                if repair.get('validation_event_id'):
                    self.assertIn(repair['validation_event_id'], ids)
            self.assertEqual(latest, project.get('execution') or {})

    def test_readiness_checks_approval_dependencies_and_snapshot_without_mutation(self):
        from forge.run_diagnostics import task_readiness
        from forge.execution import seal_checkpoint
        state = {'plan': copy.deepcopy(PLAN), 'next_task': 0, 'approved': True}
        files = {'app.py': APP}; seal_checkpoint(state, files)
        before = copy.deepcopy(state)
        self.assertTrue(task_readiness(state, 0, files)['passed'])
        self.assertEqual(state, before)
        self.assertIn('checkpoint_mismatch', task_readiness(state, 0, {'app.py': APP+'\n'})['review_codes'])
        state['approved'] = False
        self.assertIn('approval_required', task_readiness(state, 0, files)['review_codes'])
        from tests.test_task_contracts import structured_plan
        state = {'plan': structured_plan(), 'next_task': 0, 'approved': True}
        self.assertIn('task_contract_not_ready', task_readiness(state, 1, files)['review_codes'])

    def test_latest_run_separates_planning_and_orphaned_newer_build(self):
        from forge.run_diagnostics import latest_execution
        records = [self.event('job_started', action='build'), self.event('job_finished', action='build', status='verified', model_attempts=0),
                   self.event('job_started', run='plan-2', action='plan'),
                   self.event('repair_started', run='build-3', repair_id='unfinished', stage='static_repair')]
        result = latest_execution(records, {'prefix_omitted': True})
        self.assertEqual(result['run_id'], 'build-3')
        self.assertFalse(result['coverage']['run_start_retained'])
        self.assertFalse(result['coverage']['run_end_retained'])
        self.assertTrue(result['coverage']['history_gaps'])
        self.assertEqual(result['repairs'][0]['validation'], 'interrupted_or_in_progress')
        self.assertIsNone(result['status'])

    def test_unknown_usage_and_timing_stay_unknown_with_partial_reporting(self):
        from forge.run_diagnostics import latest_execution
        records = [self.event('job_started', action='build'),
                   self.event('model_attempt', provider='ollama', model='fixture', success=True),
                   self.event('model_attempt', provider='ollama', model='fixture', success=False, prompt_tokens=7, seconds=1.25),
                   self.event('job_finished', action='build', status='error', model_attempts=3)]
        result = latest_execution(records)
        model = result['model_results'][0]
        self.assertEqual(model['seconds'], 1.25)
        self.assertEqual(model['unknown_timings'], 1)
        self.assertIsNone(model['completion_tokens'])
        self.assertEqual(model['prompt_tokens_requests'], 1)
        self.assertEqual(model['transport_unknown'], 2)
        self.assertFalse(result['coverage']['attempt_details_complete'])
        self.assertEqual(result['unattributed_attempts'], 2)

    def test_failed_and_cancelled_repairs_cannot_be_promoted_by_later_pass(self):
        from forge.run_diagnostics import latest_execution
        for status, expected in [('failed', 'repair_failed'), ('cancelled', 'interrupted')]:
            rows = [self.event('job_started', action='repair'),
                    self.event('repair_finished', repair_id='r', status=status, after_source_sha256='same'),
                    self.event('verification_finished', passed=True, source_sha256='same')]
            self.assertEqual(latest_execution(rows)['repairs'][0]['validation'], expected)

    def test_unfinished_requests_are_linked_without_inventing_transport_failure(self):
        from forge.run_diagnostics import latest_execution
        rows = [self.event('job_started', action='build'),
                self.event('model_request_started', attempt_id='done', provider='ollama', model='first'),
                self.event('model_attempt', attempt_id='done', provider='ollama', model='first', success=False),
                self.event('model_request_started', attempt_id='pending', provider='ollama', model='second', timeout_seconds=120),
                self.event('model_request_started', provider='ollama', model='legacy')]
        result = latest_execution(rows)
        self.assertEqual(result['started_requests'], 3)
        self.assertEqual(result['requests_without_identity'], 1)
        self.assertEqual([r['attempt_id'] for r in result['pending_requests']], ['pending'])
        self.assertIsNone(result['status'])

    def test_malformed_optional_values_do_not_create_success_or_zero_usage(self):
        from forge.run_diagnostics import latest_execution
        rows = [self.event('job_started', action='build'), self.event('repair_finished', repair_id={}),
                self.event('model_attempt', provider=[], model='fixture'),
                self.event('model_attempt', provider='ollama', model='fixture', seconds=float('nan'), completion_tokens=True)]
        result = latest_execution(rows)
        self.assertEqual(result['repairs'], [])
        self.assertIsNone(result['model_results'][0]['seconds'])
        self.assertIsNone(result['model_results'][0]['completion_tokens'])

    def test_handoff_v2_preserves_authoritative_unicode_and_scoped_source(self):
        from forge.build_contract import focused_handoff
        from forge.tasks import task_packet
        from tests.test_task_contracts import structured_plan
        plan = structured_plan(); packet = task_packet(plan, 0, 0)
        payload = {'task_packet': packet, 'current_task': plan['tasks'][0], 'files': {'app.py': 'Café 🐜'}}
        before = copy.deepcopy(payload); result = focused_handoff(payload, {'app.py': 'Café 🐜', 'index.html': 'PRIVATE'})
        self.assertEqual(payload, before)
        for key in payload: self.assertEqual(result[key], payload[key])
        handoff = result['builder_handoff']
        self.assertEqual(handoff['schema'], 2)
        self.assertTrue({'goal', 'context', 'constraints', 'done_when'} <= handoff.keys())
        self.assertIn('index.html', handoff['read_only_files'])
        legacy = {'files': {'app.py': 'Café 🐜'}}
        self.assertEqual(focused_handoff(legacy, legacy['files']), legacy)

    def test_failed_repair_is_recorded_and_thread_context_is_restored(self):
        from forge.models import ModelError
        with tempfile.TemporaryDirectory() as folder:
            bench = Workbench(Path(folder)/'projects', ScriptedModels([PLAN]))
            config = {'provider': 'ollama', 'model': 'fixture'}
            state = await_job(bench, bench.create('PRIVATE IDEA', config, config)['id'])
            before = bench.context_files(state['id'])
            with patch.object(bench, '_generate_and_apply', side_effect=ModelError('PRIVATE ERROR', 'quota')):
                with self.assertRaises(ModelError):
                    bench.generate_and_apply(state, {}, threading.Event(), repair=True, repair_stage='static_repair')
            end = next(r['data'] for r in bench.history(state['id'])['records'] if r['kind']=='repair_finished')
            self.assertEqual(end['failure_class'], 'quota')
            self.assertEqual(end['status'], 'failed')
            self.assertFalse(end['source_changed'])
            self.assertEqual(bench.execution_context.value, {})
            self.assertEqual(bench.context_files(state['id']), before)
            self.assertNotIn('PRIVATE ERROR', json.dumps(end))

    def test_test_audit_does_not_create_history_in_a_legacy_project(self):
        from forge.system_tests import SystemTests
        with tempfile.TemporaryDirectory() as folder:
            models = ScriptedModels([PLAN]); bench = Workbench(Path(folder)/'projects', models)
            config = {'provider': 'ollama', 'model': 'fixture'}
            state = await_job(bench, bench.create('PRIVATE IDEA', config, config)['id'])
            directory = bench.directory(state['id'])
            (directory/'workflow-history.jsonl').unlink()
            before = {str(p.relative_to(directory)): p.read_bytes() for p in directory.rglob('*') if p.is_file()}
            runner = SystemTests(bench, lambda: {}, lambda: {'connected': True})
            runner.start([], project_id=state['id']); runner.worker.join(5)
            self.assertFalse(runner.worker.is_alive())
            self.assertEqual(next(r for r in runner.status()['rows'] if r['code']=='project_execution')['status'], 'skipped')
            self.assertEqual({str(p.relative_to(directory)): p.read_bytes() for p in directory.rglob('*') if p.is_file()}, before)
            self.assertEqual(len(models.calls), 1)

    def test_unchanged_static_repair_does_not_spend_the_remaining_budget(self):
        with tempfile.TemporaryDirectory() as folder:
            models = ScriptedModels([PLAN, *[{'files': {'app.py': APP}} for _ in range(4)]])
            bench = Workbench(Path(folder)/'projects', models)
            config = {'provider': 'ollama', 'model': 'fixture'}
            state = await_job(bench, bench.create('Task tracker', config, config)['id'])
            bench.approve(state['id'], state['plan'])
            bench.start(state['id'], 'build', {'execute': False, 'repairs': 3})
            result = await_job(bench, state['id'])
            self.assertEqual(result['status'], 'needs_attention')
            self.assertEqual(len(models.calls), 3, 'One unchanged static repair must stop before spending two more calls.')
            self.assertEqual(result['repair_count'], 1)

    def build(self, folder):
        models = ScriptedModels([PLAN, {'files': {'app.py': BROKEN, 'test_app.py': TEST}},
                                 {'files': {'app.py': APP}}])
        bench = Workbench(Path(folder)/'projects', models)
        config = {'provider': 'ollama', 'model': 'fixture'}
        state = await_job(bench, bench.create('PRIVATE IDEA', config, config)['id'])
        bench.approve(state['id'], state['plan'])
        bench.start(state['id'], 'build', {'execute': True, 'consent': True, 'runtime': 'local', 'repairs': 1})
        state = await_job(bench, state['id'])
        self.assertEqual(state['status'], 'verified', state.get('error'))
        return bench, state, models

    def test_repair_is_attributed_and_checked_against_the_same_source(self):
        with tempfile.TemporaryDirectory() as folder:
            bench, state, _ = self.build(folder)
            records = bench.history(state['id'])['records']
            starts = [row for row in records if row['kind'] == 'repair_started']
            self.assertEqual(len(starts), 1, 'The real repair must have a correlated start record.')
            repair = next(row['data'] for row in records if row['kind'] == 'repair_finished')
            self.assertEqual(repair['repair_id'], starts[0]['data']['repair_id'])
            self.assertEqual(repair['stage'], 'behavioral_repair')
            self.assertEqual(repair['status'], 'candidate_saved')
            self.assertTrue(repair['source_changed'])
            self.assertFalse(repair['behavior_verified'])
            attempt = next(row['data'] for row in records if row['kind'] == 'model_attempt'
                           and row['data'].get('repair_id') == repair['repair_id'])
            self.assertEqual(attempt['execution_stage'], 'behavioral_repair')
            request = next(row['data'] for row in records if row['kind'] == 'model_request_started'
                           and row['data'].get('attempt_id') == attempt['attempt_id'])
            self.assertEqual(request['repair_id'], repair['repair_id'])
            checked = next(row['data'] for row in reversed(records) if row['kind'] == 'verification_finished')
            self.assertEqual(checked['source_sha256'], repair['after_source_sha256'])
            self.assertTrue(checked['passed'])

    def test_diag_exports_selected_execution_without_prompt_or_code(self):
        with tempfile.TemporaryDirectory() as folder:
            bench, state, models = self.build(folder)
            before = (bench.directory(state['id'])/'state.json').read_bytes()
            with patch('forge.diagnostic_report._ollama_probe', return_value={'status': 'unavailable'}):
                report = collect_report(bench, Path(__file__).resolve().parents[1], project_id=state['id'])
            latest = report['summary'].get('selected_execution')
            self.assertIsNotNone(latest, 'Diag must explain the selected build, separate from planning/history.')
            self.assertEqual(latest['repairs'][0]['validation'], 'behavioral_pass')
            self.assertEqual(latest['status'], 'verified')
            self.assertTrue(latest['coverage']['run_start_retained'])
            self.assertEqual(latest['attempts'], 2)
            self.assertEqual((bench.directory(state['id'])/'state.json').read_bytes(), before)
            self.assertEqual(len(models.calls), 3)
            from forge.system_tests import SystemTests
            runner = SystemTests(bench, lambda: {}, lambda: {'connected': True})
            runner.start([], project_id=state['id']); runner.worker.join(5)
            self.assertFalse(runner.worker.is_alive())
            row = next(r for r in runner.status()['rows'] if r['code']=='project_execution')
            self.assertEqual(row['status'], 'passed')
            self.assertEqual(row['recorded_status'], 'verified')
            self.assertFalse(row['executed'])
            import io
            import zipfile
            with zipfile.ZipFile(io.BytesIO(export_report(report))) as archive:
                exported = b''.join(archive.read(name) for name in archive.namelist())
                self.assertNotIn(b'PRIVATE IDEA', exported)
                self.assertNotIn(APP.encode(), exported)
