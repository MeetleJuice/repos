"""Foundation regression: importing and starting the actual app must remain possible."""
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.request
import app


class FoundationTests(unittest.TestCase):
    def test_server_health_and_home(self):
        previous = Path.cwd()
        with tempfile.TemporaryDirectory() as directory:
            os.chdir(directory)
            server = None
            try:
                server = app.create_server('127.0.0.1', 0)
                worker = threading.Thread(target=server.serve_forever, daemon=True)
                worker.start()
                base = 'http://127.0.0.1:' + str(server.server_address[1])
                with urllib.request.urlopen(base + '/health', timeout=3) as response:
                    self.assertEqual(json.load(response)['status'], 'ok')
                with urllib.request.urlopen(base + '/', timeout=3) as response:
                    self.assertEqual(response.status, 200)
                    self.assertIn('html', response.headers.get_content_type())
                    self.assertTrue(response.read())
            finally:
                if server:
                    server.shutdown()
                    server.server_close()
                    worker.join(3)
                os.chdir(previous)
