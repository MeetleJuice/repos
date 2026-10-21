"""Cross-system diagnostic evidence, security boundaries and local-only ideas."""
import json
import io
import hashlib
from pathlib import Path
import re
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import zipfile
from unittest.mock import Mock, patch

from forge.core import Workbench
from forge.server import make_server
from forge.ideas import generate_idea
from forge.models import ModelError
from forge.lifecycle import record_exception
from forge.diagnostic_report import collect_report, export_report
from tests.fixtures import PLAN, APP
from tests.test_workbench import ScriptedModels, await_job


class MasterDiagTests(unittest.TestCase):
    def test_syntax_failure_records_location_without_source_or_exception_text(self):
        from bootstrap import record_launcher_exception
        with tempfile.TemporaryDirectory() as temp:
            bench = Workbench(Path(temp) / 'projects')
            marker = 'private-unprefixed-expression-8371'
            try:
                compile('if ' + marker, '/private/source/broken_import.py', 'exec')
            except SyntaxError as exc:
                record_exception(bench.diagnostics, 'application_start_failed', exc)
                record_launcher_exception(Path(temp), exc)
            snapshot = bench.diagnostics.snapshot()
            frames = snapshot['records'][-1]['data']['frames']
            self.assertEqual(frames[-1]['file'], 'broken_import.py')
            self.assertEqual(frames[-1]['line'], 1)
            launch = (Path(temp) / 'diagnostics/launcher.jsonl').read_text()
            self.assertNotIn(marker, launch + json.dumps(snapshot))
            self.assertEqual(json.loads(launch)['data']['location'], 'broken_import.py')
            with patch('forge.diagnostic_report.ollama_health', return_value={'status': 'unavailable'}), patch('forge.diagnostic_report.resource_snapshot', return_value={}):
                report = collect_report(bench, Path(__file__).resolve().parents[1])
            exported = next(r for r in report['evidence']['recorder']['records'] if r['kind'] == 'application_start_failed')
            self.assertEqual(exported['data']['frames'][-1]['file'], 'broken_import.py')
            finding = next(f for f in report['findings'] if f['code'] == 'operational_failures')
            self.assertIn(exported['id'], finding['event_ids'])

    def test_corrupt_project_metadata_is_observed_without_changing_it(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / 'projects' / ('a' * 32)
            source.mkdir(parents=True)
            state = source / 'state.json'
            state.write_text('not json')
            bench = Workbench(source.parent)
            self.assertEqual(state.read_text(), 'not json')
            event = next(r for r in bench.diagnostics.snapshot()['records'] if r['kind'] == 'project_state_unreadable')
            self.assertEqual(event['project_id'], 'a' * 32)
            self.assertEqual(len(bench.warnings), 1)

    def test_local_idea_request_never_creates_a_project_or_calls_cloud(self):
        with tempfile.TemporaryDirectory() as temp:
            models = ScriptedModels([{'idea': 'Build a local book tracker with title entry, saved records, search and a small manual checklist.'}])
            bench = Workbench(Path(temp) / 'projects', models)
            factory = Mock(return_value=models)
            bench.client_factory = factory
            profiles = [{'provider': 'gemini', 'model': 'cloud', 'fallbacks': [
                {'provider': 'ollama', 'model': 'installed-coder', 'options': {'num_ctx': 8192, 'num_predict': 4096}}]}]
            with patch('forge.ideas.local_models', return_value=['installed-coder']):
                result = generate_idea(bench, profiles)
            self.assertEqual(result['provider'], 'ollama')
            self.assertEqual(result['model'], 'installed-coder')
            factory.assert_called_once_with('ollama', 'installed-coder')
            self.assertEqual(bench.list_projects(), [])
            self.assertEqual(len(models.calls), 1)
            self.assertFalse(bench.idea_busy)
            self.assertFalse(bench.inference_lock.locked())
            self.assertEqual(models.options['num_predict'], 1024)
            self.assertIsNone(bench.model_status.active)

    def test_idea_malformed_response_and_offline_runtime_release_inference(self):
        for response in ({'idea': 'bad'}, ModelError('fixture runtime unavailable', 'transport')):
            with self.subTest(response=type(response).__name__), tempfile.TemporaryDirectory() as temp:
                bench = Workbench(Path(temp) / 'projects', ScriptedModels([response]))
                with patch('forge.ideas.local_models', return_value=['installed-coder']), self.assertRaises(ModelError):
                    generate_idea(bench, [{'provider': 'ollama', 'model': 'installed-coder'}])
                self.assertFalse(bench.idea_busy)
                self.assertFalse(bench.inference_lock.locked())
                self.assertEqual(bench.list_projects(), [])
                failed = [r for r in bench.diagnostics.snapshot()['records'] if r['kind'] == 'idea_request_failed']
                self.assertEqual(len(failed), 1)
                self.assertIsNone(bench.model_status.active)

    def test_idea_refuses_active_build_before_any_model_or_catalogue_request(self):
        with tempfile.TemporaryDirectory() as temp:
            bench = Workbench(Path(temp) / 'projects', ScriptedModels([]))
            done = threading.Event()
            thread = threading.Thread(target=done.wait)
            thread.start()
            bench.jobs['fixture'] = thread, done
            try:
                with patch('forge.ideas.local_models') as catalogue, self.assertRaisesRegex(ValueError, 'running job'):
                    generate_idea(bench, [])
                catalogue.assert_not_called()
            finally:
                done.set()
                thread.join()

    def test_failed_source_write_retains_task_and_old_files_with_correlated_event(self):
        with tempfile.TemporaryDirectory() as temp:
            bench = Workbench(Path(temp) / 'projects', ScriptedModels([PLAN]))
            cfg = {'provider': 'ollama', 'model': 'fixture'}
            state = await_job(bench, bench.create('A small tracker', cfg, cfg)['id'])
            bench.approve(state['id'], state['plan'])
            state = bench.load(state['id'])
            before = bench.files(state['id'])
            original = Path.write_text
            def fail_source_write(path, *args, **kwargs):
                if '.source-update-' in str(path) and path.name == 'app.py':
                    raise PermissionError(13, 'fixture denied')
                return original(path, *args, **kwargs)
            with patch.object(Path, 'write_text', fail_source_write), self.assertRaises(PermissionError):
                bench.apply(state, {'files': {'app.py': APP}})
            self.assertEqual(before, bench.files(state['id']))
            event = next(r for r in bench.diagnostics.snapshot()['records'] if r['kind'] == 'file_operation_failed')
            self.assertEqual(event['project_id'], state['id'])
            self.assertEqual(event['data']['task'], 1)
            self.assertEqual(event['data']['operation'], 'replace_source')
            self.assertEqual(bench.load(state['id'])['next_task'], 0)

    def test_restart_keeps_interrupted_evidence_and_never_marks_it_complete(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'projects'
            bench = Workbench(root, ScriptedModels([PLAN]))
            cfg = {'provider': 'ollama', 'model': 'fixture'}
            state = await_job(bench, bench.create('A small tracker', cfg, cfg)['id'])
            state.update(status='building', active_run_id='interrupted-fixture')
            bench.trace(state, 'job_started', {'action': 'build'})
            bench.save(state)
            resumed = Workbench(root)
            self.assertEqual(resumed.load(state['id'])['status'], 'interrupted')
            event = next(r for r in resumed.diagnostics.snapshot()['records'] if r['kind'] == 'job_interrupted')
            self.assertEqual(event['run_id'], 'interrupted-fixture')

    def test_diag_zip_excludes_unknown_private_prose_and_survives_recorder_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            bench = Workbench(Path(temp) / 'projects', ScriptedModels([PLAN]))
            cfg = {'provider': 'ollama', 'model': 'fixture'}
            state = await_job(bench, bench.create('A small tracker', cfg, cfg)['id'])
            markers = ['PRIVATE_UNPREFIXED_NOTE_6191', 'PRIVATE_UNPREFIXED_MODEL_7923']
            bench.trace(state, 'manual_observations', {'notes': [markers[0]], 'results': [False]}, 'user')
            bench.event(state, markers[1], origin='model_report')
            with patch('forge.diagnostic_report.ollama_health', return_value={'status': 'unavailable'}), patch('forge.diagnostic_report.resource_snapshot', return_value={}):
                report = collect_report(bench, Path(__file__).resolve().parents[1], project_id=state['id'])
                bundle = export_report(report)
                with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
                    content = b''.join(archive.read(name) for name in archive.namelist()).decode()
                for marker in markers:
                    self.assertNotIn(marker, content)
                with patch.object(bench.diagnostics, 'snapshot', side_effect=OSError('fixture unavailable')):
                    partial = collect_report(bench, Path(__file__).resolve().parents[1], project_id=state['id'])
                self.assertFalse(partial['completeness']['complete'])
                self.assertTrue(export_report(partial).startswith(b'PK'))

    def test_controller_events_have_identical_persistent_diagnostic_ids(self):
        with tempfile.TemporaryDirectory() as temp:
            bench = Workbench(Path(temp) / 'projects', ScriptedModels([PLAN]))
            cfg = {'provider': 'ollama', 'model': 'fixture'}
            state = await_job(bench, bench.create('A small tracker', cfg, cfg)['id'])
            self.assertTrue(hasattr(bench, 'diagnostics'), 'No independent flight recorder')
            history = bench.history(state['id'])['records']
            records = bench.diagnostics.snapshot()['records']
            mirrored = {r['id']: r for r in records if r.get('project_id') == state['id']}
            for event in history:
                if event['kind'] == 'history_started':
                    continue
                self.assertIn(event['id'], mirrored)
                self.assertEqual(mirrored[event['id']]['kind'], event['kind'])
                self.assertEqual(mirrored[event['id']]['run_id'], event['run_id'])
            self.assertFalse(bench.diagnostics.directory.is_relative_to(bench.root))

    def test_diag_endpoint_is_session_protected_and_does_not_generate(self):
        with tempfile.TemporaryDirectory() as temp:
            models = ScriptedModels([])
            bench = Workbench(Path(temp) / 'projects', models)
            server = make_server(0, bench)
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            base = 'http://127.0.0.1:' + str(server.server_port)
            try:
                with urllib.request.urlopen(base) as response:
                    token = re.search(r'name="foundry-token" content="([^"]+)"', response.read().decode())[1]
                def request(token_value):
                    return urllib.request.Request(base + '/api/diagnostics', data=b'{}',
                        headers={'Content-Type': 'application/json', 'X-Foundry-Token': token_value})
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    urllib.request.urlopen(request('wrong'))
                self.assertEqual(caught.exception.code, 403)
                caught.exception.close()
                with patch('forge.diagnostic_report.ollama_health', return_value={'available': False, 'models': [], 'error': 'fixture offline'}):
                    with urllib.request.urlopen(request(token), timeout=15) as response:
                        report = json.load(response)
                self.assertEqual(report['schema'], 1)
                self.assertTrue(report['findings'])
                self.assertEqual(models.calls, [])
                self.assertEqual(bench.list_projects(), [])
                export_request = urllib.request.Request(base + '/api/diagnostics/export',
                    data=json.dumps({'report_id': report['id']}).encode(),
                    headers={'Content-Type': 'application/json', 'X-Foundry-Token': token})
                with patch('forge.server.collect_report', side_effect=AssertionError('Export must reuse displayed snapshot')):
                    with urllib.request.urlopen(export_request) as response:
                        bundle = response.read()
                with zipfile.ZipFile(io.BytesIO(bundle)) as archive:
                    manifest = json.loads(archive.read('manifest.json'))
                    self.assertEqual(manifest['report_id'], report['id'])
                    for entry in manifest['files']:
                        content = archive.read(entry['path'])
                        self.assertEqual(len(content), entry['bytes'])
                        self.assertEqual(hashlib.sha256(content).hexdigest(), entry['sha256'])
            finally:
                server.shutdown()
                server.server_close()
                worker.join(5)


if __name__ == '__main__':
    unittest.main()
