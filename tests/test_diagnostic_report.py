"""Diagnostic exports contain evidence, never implicit source/credential bundles."""
from __future__ import annotations

import hashlib
import importlib
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import zipfile


class Recorder:
    def snapshot(self, limit=5000):
        return {'records': [
            {'id': 'h1', 'kind': 'model_attempt', 'project_id': 'a' * 32,
             'data': {'provider': 'ollama', 'model': 'coder',
                      'success': False, 'category': 'transport', 'seconds': 1.2}},
            {'id': 'd2', 'kind': 'resource_sample', 'data': {'cpu_percent': None}},
        ], 'integrity': {'valid': True}, 'retention': {'pruned_records': 1}}

    def health(self):
        return {'available': True, 'database_check': 'ok'}


class Bench:
    def __init__(self, root):
        self.root = root / 'projects'
        self.root.mkdir()
        self.lock = threading.RLock()
        self.diagnostics = Recorder()
        self.warnings = []
        self.jobs = {}
        self.state = {'id': 'a' * 32, 'status': 'needs_attention', 'title': 'Sample',
                      'created': '2026-10-21T10:00:00+00:00', 'updated': '2026-10-21T11:00:00+00:00',
                      'approved': True, 'idea': 'PRIVATE ORIGINAL IDEA', 'next_task': 1,
                      'planner': {'provider': 'ollama', 'model': 'planner'},
                      'coder': {'provider': 'ollama', 'model': 'coder'},
                      'plan': {'tasks': [{'id': 'task-1', 'title': 'Create API', 'files': ['app.py']}],
                               'checks': [{'name': 'create', 'method': 'POST', 'path': '/api/records',
                                           'body': {'title': 'PRIVATE SAMPLE CONTENT'}, 'status': 201}]},
                      'checks': {'passed': True, 'log': 'Ran 2 tests; PRIVATE KEY Bearer secret-token',
                                 'phases': [{'phase': 'tests', 'tests_run': 2, 'passed': True}]},
                      'manual_results': {'notes': ['PRIVATE MANUAL NOTES']},
                      'verification_fingerprint': 'old-source'}
        directory = self.root / self.state['id']
        directory.mkdir()
        (directory / 'state.json').write_text(json.dumps(self.state), encoding='utf-8')
        self.records = [
            {'id': 'h1', 'kind': 'model_attempt', 'time': '2026-10-21T11:00:00Z',
             'run_id': 'run1', 'origin': 'controller',
             'data': {'provider': 'ollama', 'model': 'coder', 'success': False,
                      'category': 'transport', 'prompt': 'PRIVATE MODEL PROMPT'}},
            {'id': 'h2', 'kind': 'journal', 'origin': 'model_report',
             'data': {'message': 'PRIVATE MODEL SOURCE BODY'}},
        ]
        (directory / 'workflow-history.jsonl').write_text(
            ''.join(json.dumps(record) + '\n' for record in self.records), encoding='utf-8')

    def load(self, ident):
        if ident != self.state['id']:
            raise ValueError('Project not found')
        return self.state

    def evidence(self, ident):
        return {'recorded_status': 'verified', 'effective_status': 'needs_attention',
                'automated_evidence_current': False, 'manual_acceptance_current': False,
                'issues': ['Implementation changed since automated verification.']}

    def history(self, ident):
        return {'records': self.records, 'coverage': {'complete_since_tracking_started': True}}


class DiagnosticReportTests(unittest.TestCase):
    def test_check_prose_and_query_samples_are_not_exported(self):
        with tempfile.TemporaryDirectory() as temp:
            bench = Bench(Path(temp))
            marker = 'private_unprefixed_check_sample_4913'
            check = bench.state['plan']['checks'][0]
            check.update(name=marker, path='/api/records?search=' + marker)
            path = bench.root / bench.state['id'] / 'state.json'
            path.write_text(json.dumps(bench.state))
            report = self.collect(bench)
            self.assertNotIn(marker, json.dumps(report))
            metadata = report['evidence']['projects'][0]['acceptance_check_metadata'][0]
            self.assertEqual(metadata['index'], 0)
            self.assertEqual(metadata['path'], '/api/records')
            self.assertTrue(metadata['path_query_omitted'])

    def module(self):
        spec = importlib.util.find_spec('forge.diagnostic_report')
        self.assertIsNotNone(spec, 'Master Diag must provide a bounded, privacy-safe report collector')
        return importlib.import_module('forge.diagnostic_report')

    def collect(self, bench):
        module = self.module()
        with patch.object(module, '_ollama_probe', return_value={'status': 'unavailable', 'failure': 'connection'}), \
             patch.object(module, '_git_info', return_value={'commit': None, 'available': False}), \
             patch.object(module, 'resource_snapshot', return_value={'cpu_percent': None, 'available': False}):
            return module.collect_report(bench, bench.root.parent, project_id=bench.state['id'])

    def test_export_is_useful_redacted_and_manifest_verifiable(self):
        with tempfile.TemporaryDirectory() as temp:
            bench = Bench(Path(temp))
            report = self.collect(bench)
            self.assertEqual(report['schema'], 1)
            self.assertTrue(report['findings'])
            self.assertFalse(report['evidence']['projects'][0]['verification']['automated_evidence_current'])
            encoded = json.dumps(report)
            for secret in ('PRIVATE ORIGINAL IDEA', 'PRIVATE MODEL PROMPT', 'PRIVATE MODEL SOURCE BODY',
                           'PRIVATE MANUAL NOTES', 'PRIVATE SAMPLE CONTENT', 'secret-token'):
                self.assertNotIn(secret, encoded)
            raw = self.module().export_report(report)
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                self.assertIn('START_HERE.md', archive.namelist())
                self.assertIn('summary.json', archive.namelist())
                self.assertIn('completeness.json', archive.namelist())
                manifest = json.loads(archive.read('manifest.json'))
                for entry in manifest['files']:
                    content = archive.read(entry['path'])
                    self.assertEqual(entry['sha256'], hashlib.sha256(content).hexdigest())
                    self.assertEqual(entry['bytes'], len(content))
                self.assertEqual(set(archive.namelist()), {item['path'] for item in manifest['files']} | {'manifest.json'})

    def test_missing_collectors_yield_honest_partial_report(self):
        with tempfile.TemporaryDirectory() as temp:
            bench = Bench(Path(temp))
            with patch.object(bench.diagnostics, 'snapshot', side_effect=OSError('recorder unavailable')):
                report = self.collect(bench)
            self.assertFalse(report['completeness']['complete'])
            self.assertTrue(any(item['classification'] == 'missing_evidence' for item in report['findings']))
            self.assertTrue(self.module().export_report(report).startswith(b'PK'))

    def test_findings_reference_actual_event_ids_and_dash_gaps_not_invented(self):
        with tempfile.TemporaryDirectory() as temp:
            report = self.collect(Bench(Path(temp)))
            failure = next(item for item in report['findings'] if item['code'] == 'model_failures')
            self.assertIn('h1', failure['event_ids'])
            dashboard = report['evidence']['dashboard']
            self.assertEqual(dashboard['matched_history_events'], 1)
            self.assertEqual(dashboard['unmatched_history_events'], 0)
            self.assertFalse(dashboard['client_rendering_verified'])

    def test_selected_missing_or_corrupt_state_does_not_destroy_report(self):
        with tempfile.TemporaryDirectory() as temp:
            bench = Bench(Path(temp))
            module = self.module()
            with patch.object(module, '_ollama_probe', return_value={'status': 'unavailable'}), \
                 patch.object(module, '_git_info', return_value={'commit': None}), \
                 patch.object(module, 'resource_snapshot', return_value={}):
                report = module.collect_report(bench, Path(temp), project_id='b' * 32)
            self.assertFalse(report['completeness']['complete'])
            self.assertTrue(any(item['code'] == 'project_unavailable' for item in report['findings']))

    def test_loopback_probe_refuses_remote_or_authenticated_urls(self):
        module = self.module()
        for url in ('https://example.com', 'http://example.com', 'http://user:password@127.0.0.1:11434',
                    'http://127.0.0.1:11434/?token=secret'):
            with patch.dict('os.environ', {'OLLAMA_URL': url}), patch.object(module.urllib.request, 'build_opener') as opener:
                result = module._ollama_probe()
            self.assertEqual(result['status'], 'configuration_error')
            opener.assert_not_called()

    def test_export_preserves_more_than_256_event_records_and_declares_retention(self):
        with tempfile.TemporaryDirectory() as temp:
            bench = Bench(Path(temp))
            rows = [{'id': str(index), 'kind': 'model_attempt', 'data': {'provider': 'ollama', 'seconds': 1}}
                    for index in range(300)]
            with patch.object(bench.diagnostics, 'snapshot', return_value={
                'records': rows, 'integrity': {'passed': True},
                'retention': {'retired_records': 7, 'export_omitted_records': 13}}):
                report = self.collect(bench)
            self.assertEqual(len(report['evidence']['recorder']['records']), 300)
            self.assertFalse(report['completeness']['complete'])
            self.assertTrue(any('retired' in item for item in report['completeness']['omissions']))
            with zipfile.ZipFile(io.BytesIO(self.module().export_report(report))) as archive:
                exported = json.loads(archive.read('evidence/recorder.json'))
            self.assertEqual(len(exported['records']), 300)

    def test_independent_launcher_failures_survive_without_server_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            bench = Bench(Path(temp))
            directory = Path(temp) / 'diagnostics'
            directory.mkdir()
            (directory / 'launcher.jsonl.1').write_text(json.dumps({
                'id': 'launch1', 'kind': 'previous_session_unfinished', 'origin': 'independent_supervisor',
                'data': {'reason': 'no_clean_supervisor_end_record'}}) + '\n', encoding='utf-8')
            (directory / 'launcher.jsonl').write_text(json.dumps({
                'id': 'launch2', 'kind': 'application_exception', 'origin': 'independent_supervisor',
                'data': {'exception_type': 'ModuleNotFoundError', 'location': 'run.py', 'line': 5,
                         'error': 'unprefixed-invented-credential'}}) + '\n', encoding='utf-8')
            (directory / 'launcher-session.json').write_text(json.dumps({'status': 'running', 'pid': 123}), encoding='utf-8')
            (directory / 'instance.json').write_text(json.dumps({'boot': 'private-boot-token', 'port': 8765}), encoding='utf-8')
            report = self.collect(bench)
            self.assertEqual(len(report['evidence']['launcher']['records']), 2)
            failure = next(item for item in report['findings'] if item['code'] == 'launcher_failures')
            self.assertEqual(failure['event_ids'], ['launch2'])
            warning = next(item for item in report['findings'] if item['code'] == 'unfinished_supervisor_session')
            self.assertEqual(warning['classification'], 'warning')
            self.assertNotIn('private-boot-token', json.dumps(report))
            self.assertNotIn('unprefixed-invented-credential', json.dumps(report))

    def test_packaged_identity_exit_code_and_unknown_secret_prose(self):
        with tempfile.TemporaryDirectory() as temp:
            bench = Bench(Path(temp))
            bench.state['error'] = 'urlopen() got an unexpected keyword argument method; hidden-value-no-prefix'
            bench.state['title'] = 'hidden-value-no-prefix'
            bench.state['checks']['exit_code'] = 1
            bench.state['checks']['log'] = 'hidden-value-no-prefix'
            bench.state['preflight'] = {'passed': False, 'issues': ['hidden-value-no-prefix']}
            bench.state['plan']['tasks'][0]['title'] = 'hidden-value-no-prefix'
            (bench.root / bench.state['id'] / 'state.json').write_text(json.dumps(bench.state), encoding='utf-8')
            forge = Path(temp) / 'forge'
            forge.mkdir()
            (forge / 'build-info.json').write_text(json.dumps({'schema': 1, 'version': '0.31.0',
                'source_commit': 'a' * 40, 'tracked_modified_files': 0, 'source_tree_sha256': 'b' * 64,
                'source_file_count': 300}), encoding='utf-8')
            report = self.collect(bench)
            self.assertEqual(report['evidence']['application']['packaged_identity']['source_commit'], 'a' * 40)
            detail = report['evidence']['projects'][0]
            self.assertEqual(detail['test_evidence']['exit_code'], 1)
            self.assertIn('urllib_urlopen_method_keyword', detail['error_symptom_tags'])
            self.assertNotIn('hidden-value-no-prefix', json.dumps(report))

    def test_readonly_update_pointer_checks_and_history_duplicates(self):
        with tempfile.TemporaryDirectory() as temp:
            bench = Bench(Path(temp))
            updates = Path(temp) / 'updates'
            updates.mkdir()
            (updates / 'current.json').write_text('{"version":"0.99.0"}', encoding='utf-8')
            before = (updates / 'current.json').read_bytes()
            records = [bench.records[0], {**bench.records[0], 'time': '2026-10-20T11:00:00Z'}]
            (bench.root / bench.state['id'] / 'workflow-history.jsonl').write_text(
                ''.join(json.dumps(item) + '\n' for item in records), encoding='utf-8')
            report = self.collect(bench)
            codes = {item['code'] for item in report['findings']}
            self.assertTrue({'update_pointer_invalid', 'duplicate_history_events', 'nonmonotonic_history_time'} <= codes)
            self.assertEqual(before, (updates / 'current.json').read_bytes())
            self.assertFalse(report['evidence']['workspace']['generated_databases_inspected'])


if __name__ == '__main__':
    unittest.main()
