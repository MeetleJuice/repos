"""Real SQLite evidence/persistence tests; no providers, keys or GPU required."""
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from forge.diagnostics import FlightRecorder, ResourceSampler, redact, resource_snapshot, sanitize_event_data


class DiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_restart_preserves_identity_correlation_and_evidence(self):
        first = FlightRecorder(self.home / 'diagnostics')
        ident = first.record('model_attempt', {'success': False, 'category': 'transport', 'completion_tokens': 0}, project_id='project', run_id='run', event_id='workflow-id')
        self.assertEqual(ident, 'workflow-id')
        first.close()
        second = FlightRecorder(self.home / 'diagnostics')
        snapshot = second.snapshot()
        self.assertTrue(snapshot['integrity']['passed'])
        self.assertEqual(snapshot['records'][0]['id'], 'workflow-id')
        self.assertEqual(snapshot['records'][0]['project_id'], 'project')
        self.assertEqual(snapshot['records'][0]['run_id'], 'run')
        self.assertEqual(snapshot['records'][0]['data']['completion_tokens'], 0)

    def test_count_rotation_is_honest_and_chain_stays_valid(self):
        recorder = FlightRecorder(self.home, max_records=3)
        for index in range(8):
            recorder.record('stage', {'index': index})
        snapshot = recorder.snapshot(limit=2)
        self.assertTrue(snapshot['integrity']['passed'])
        self.assertEqual([r['data']['index'] for r in snapshot['records']], [6, 7])
        self.assertEqual(snapshot['retention']['retired_records'], 5)
        self.assertEqual(snapshot['retention']['export_omitted_records'], 1)
        self.assertEqual(snapshot['retention']['available_records'], 3)

    def test_age_and_byte_retention_do_not_invent_full_history(self):
        recorder = FlightRecorder(self.home, max_bytes=1800)
        recorder.record('old', {'value': 'old'}, time_utc='2000-01-01T00:00:00+00:00')
        for _ in range(6):
            recorder.record('new', {'value': 'x' * 500})
        result = recorder.snapshot()
        self.assertTrue(result['integrity']['passed'])
        self.assertGreater(result['retention']['retired_records'], 0)
        self.assertNotIn('old', [event['kind'] for event in result['records']])
        self.assertLessEqual(sum(len(json.dumps(event['data'])) for event in result['records']), 1800)

    def test_threads_and_independent_instances_share_transactions(self):
        one, two = FlightRecorder(self.home), FlightRecorder(self.home)
        threads = [threading.Thread(target=lambda rec=one if i % 2 else two: [rec.record('parallel', {'iteration': n}) for n in range(15)]) for i in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        result = one.snapshot()
        self.assertEqual(len(result['records']), 60)
        self.assertEqual(one.dropped + two.dropped, 0)
        self.assertTrue(result['integrity']['passed'])

    def test_separate_processes_share_durable_recorder(self):
        FlightRecorder(self.home)
        program = "from pathlib import Path; import sys; from forge.diagnostics import FlightRecorder; r=FlightRecorder(Path(sys.argv[1])); [r.record('process_event', {'iteration':n}) for n in range(10)]; raise SystemExit(bool(r.dropped))"
        children = [subprocess.Popen([sys.executable, '-c', program, str(self.home)], stdout=subprocess.PIPE, stderr=subprocess.PIPE) for _ in range(2)]
        for child in children:
            _, stderr = child.communicate(timeout=15)
            self.assertEqual(child.returncode, 0, stderr.decode(errors='replace'))
        snapshot = FlightRecorder(self.home).snapshot()
        self.assertTrue(snapshot['integrity']['passed'])
        self.assertEqual(len(snapshot['records']), 20)

    def test_tampering_and_deleted_tail_are_detected(self):
        recorder = FlightRecorder(self.home)
        recorder.record('start', {'status': 'running'})
        recorder.record('finish', {'status': 'verified'})
        connection = sqlite3.connect(recorder.path)
        connection.execute("UPDATE events SET body=replace(body,'running','stopped') WHERE sequence=1")
        connection.execute('DELETE FROM events WHERE sequence=2')
        connection.commit()
        connection.close()
        result = recorder.snapshot()
        self.assertFalse(result['integrity']['passed'])
        self.assertIn('hash_chain_mismatch', [issue['error'] for issue in result['integrity']['issues']])
        self.assertIn('head_mismatch', [issue['error'] for issue in result['integrity']['issues']])

    def test_record_file_failure_does_not_crash_caller(self):
        (self.home / 'blocked').write_text('ordinary file')
        recorder = FlightRecorder(self.home / 'blocked')
        self.assertIsNone(recorder.record('failed_write', {'operation': 'source swap'}))
        self.assertEqual(recorder.dropped, 1)
        self.assertIsNotNone(recorder.health()['last_error'])
        result = recorder.snapshot()
        self.assertFalse(result['integrity']['passed'])
        self.assertEqual(result['records'], [])

    def test_corrupt_database_produces_honest_partial_report(self):
        self.home.joinpath('flight-recorder.sqlite3').write_bytes(b'not sqlite')
        recorder = FlightRecorder(self.home)
        self.assertIsNone(recorder.record('work'))
        self.assertFalse(recorder.snapshot()['integrity']['passed'])
        self.assertIsNotNone(recorder.last_error)

    def test_redaction_before_storage_and_again_on_read(self):
        secret = 'private-key-used-for-test-only'
        with patch.dict(os.environ, {'GROQ_API_KEY': secret}):
            recorder = FlightRecorder(self.home)
            recorder.record('failure', {'message': 'Bearer unknown-long-token ' + secret + ' C:\\Users\\guard\\Desktop\\app.py /home/alice/project/app.py email@example.net', 'authorization': 'anything', 'api_key': 'undiscovered-legacy-secret', 'token': 'bare-token-value', 'accessToken': 'camel-token-value', 'privateKey': 'camel-private-key', 'source': 'private code', 'partial_content': 'partial response', 'prompt': 'private idea', 'completion_tokens': 42})
        raw = recorder.path.read_bytes()
        snapshot = json.dumps(recorder.snapshot())
        for forbidden in (secret, 'unknown-long-token', 'undiscovered-legacy-secret', 'bare-token-value', 'camel-token-value', 'camel-private-key', 'private code', 'partial response', 'private idea', 'guard', 'alice', 'email@example.net'):
            self.assertNotIn(forbidden.encode(), raw)
            self.assertNotIn(forbidden, snapshot)
        self.assertEqual(recorder.snapshot()['records'][0]['data']['completion_tokens'], 42)

    def test_old_key_patterns_pem_and_quoted_assignments_are_redacted(self):
        text = 'gsk_abcdefghijklmnop hf_abcdefghijklmnop sk-or-v1-abcdefghijklmnop -----BEGIN RSA PRIVATE KEY-----\nsecret material\n-----END RSA PRIVATE KEY----- {"password": "legacy-password-value", "GROQ_API_KEY": "legacy-arbitrary-value"}'
        cleaned = redact({'message': text})['message']
        for forbidden in ('gsk_abcdefghijklmnop', 'hf_abcdefghijklmnop', 'sk-or-v1-abcdefghijklmnop', 'secret material', 'legacy-password-value', 'legacy-arbitrary-value'):
            self.assertNotIn(forbidden, cleaned)

    def test_oversized_event_data_is_omitted_with_explicit_reason(self):
        recorder = FlightRecorder(self.home)
        recorder.record('large', {'counters': {f'counter_{index}_' + 'x' * 180: index for index in range(256)}})
        result = recorder.snapshot()['records'][0]
        self.assertIn('omitted', result['data'])
        self.assertGreater(result['data']['original_bytes'], 32768)

    def test_arbitrary_free_text_and_model_reports_are_never_stored(self):
        recorder = FlightRecorder(self.home)
        private = 'unprefixed-and-unknown-legacy-password-that-cannot-be-pattern-matched'
        recorder.record('journal', {'message': 'A model returned: ' + private})
        recorder.record('journal', {'message': 'private source: def do_business(): ' + private}, origin='model_report')
        recorder.record('manual_observations', {'results': [False], 'notes': [private]})
        recorder.record('proposal_review', {'passed': False, 'findings': [{'code': 'missing_milestone', 'message': private, 'path': '/tasks/0'}]})
        recorder.record('code_response_rejected', {'provider': 'ollama', 'model': 'qwen2.5-coder:7b', 'reason': private, 'unexpected_string': private})
        rows = recorder.snapshot()['records']
        self.assertNotIn(private, json.dumps(rows))
        self.assertNotIn(private.encode(), recorder.path.read_bytes())
        self.assertTrue(rows[0]['data']['content_omitted'])
        self.assertEqual(rows[3]['data']['findings'][0]['code'], 'missing_milestone')
        self.assertEqual(rows[4]['data']['provider'], 'ollama')

    def test_event_projection_is_idempotent_for_already_omitted_evidence(self):
        for kind, origin, data in [('journal', 'model_report', {'message': 'private'}), ('proposal_review', 'controller', {'findings': [{'code': 'invalid', 'message': 'private'}]}), ('manual_observations', 'user', {'notes': ['private'], 'results': [False]})]:
            once = sanitize_event_data(kind, data, origin)
            self.assertEqual(sanitize_event_data(kind, once, origin), once)

    @unittest.skipUnless(hasattr(os, 'symlink'), 'symlinks unavailable')
    def test_symlink_destination_is_not_written(self):
        outside = self.home / 'outside'
        outside.mkdir()
        linked = self.home / 'linked'
        try:
            linked.symlink_to(outside, target_is_directory=True)
        except OSError:
            self.skipTest('platform does not permit symlink creation')
        recorder = FlightRecorder(linked)
        self.assertIsNone(recorder.record('event'))
        self.assertEqual(list(outside.iterdir()), [])

    def test_gpu_absence_is_unknown_not_zero_or_hardware_claim(self):
        with patch('forge.diagnostics.shutil.which', return_value=None):
            result = resource_snapshot(self.home)
        self.assertIsNone(result['gpu'])
        self.assertIn('nvidia-smi unavailable; GPU/VRAM unknown.', result['limitations'])
        self.assertGreater(result['disk_free_bytes'], 0)

    def test_sampler_records_real_measurement_and_stops(self):
        recorder = FlightRecorder(self.home)
        ready = threading.Event()
        sample = {'ram_total_bytes': 100, 'ram_available_bytes': 1, 'disk_free_bytes': 100, 'cpu_counters': None}
        def probe(_):
            ready.set()
            return dict(sample)
        with patch('forge.diagnostics.resource_snapshot', side_effect=probe):
            sampler = ResourceSampler(recorder, self.home)
            sampler.start()
            self.assertTrue(ready.wait(2))
            sampler.stop()
        self.assertFalse(sampler.thread.is_alive())
        kinds = [event['kind'] for event in recorder.snapshot()['records']]
        self.assertIn('hardware_sample', kinds)
        self.assertIn('resource_pressure', kinds)


if __name__ == '__main__':
    unittest.main()
