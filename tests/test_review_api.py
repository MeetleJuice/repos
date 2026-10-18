"""Authenticated review/approval parity, with no inference or project writes on review."""
import json
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.request
import urllib.error

from forge.core import Workbench
from forge.server import make_server
from tests.test_workbench import ScriptedModels, await_job
from tests.test_planning import good_notes, DATA, CONFIG


class ReviewAPITests(unittest.TestCase):
    def test_review_approval_and_session_boundaries(self):
        with tempfile.TemporaryDirectory() as temporary:
            models = ScriptedModels([good_notes()])
            bench = Workbench(Path(temporary) / 'projects', models)
            state = bench.create('Build a local notes app', CONFIG, CONFIG, 'notes')
            state = await_job(bench, state['id'])
            server = make_server(0, bench)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            base = f'http://127.0.0.1:{server.server_port}'
            try:
                with urllib.request.urlopen(base) as response:
                    token = response.read().decode().split('name="foundry-token" content="')[1].split('"')[0]
                prefix = '/api/projects/' + state['id']
                def post(action, plan, auth=True, origin=None):
                    headers = {'Content-Type': 'application/json'}
                    if auth: headers['X-Foundry-Token'] = token
                    if origin: headers['Origin'] = origin
                    request = urllib.request.Request(base + prefix + '/' + action, data=json.dumps({'plan': plan}).encode(), headers=headers)
                    with urllib.request.urlopen(request, timeout=5) as response:
                        return json.load(response)
                before = (bench.directory(state['id']) / 'state.json').read_bytes()
                bad = json.loads((DATA / 'notes-plan-2.json').read_text())
                self.assertFalse(post('review', bad)['passed'])
                self.assertTrue(post('review', good_notes())['passed'])
                self.assertFalse(post('review', [])['passed'])
                self.assertEqual((bench.directory(state['id']) / 'state.json').read_bytes(), before)
                with self.assertRaises(urllib.error.HTTPError) as error:
                    post('approve', bad)
                self.assertEqual(error.exception.code, 400)
                for auth, origin in [(False, None), (True, 'https://untrusted.invalid')]:
                    with self.assertRaises(urllib.error.HTTPError) as error:
                        post('review', good_notes(), auth, origin)
                    self.assertEqual(error.exception.code, 403)
                result = post('approve', good_notes())
                self.assertTrue(result['approved'])
                self.assertIsNone(result['checks'])
                self.assertEqual(len(models.calls), 1)
            finally:
                server.shutdown(); server.server_close()
