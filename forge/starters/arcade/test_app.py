"""Server and delivery tests; these do not claim to test JavaScript gameplay."""
import json
import threading
import unittest
import urllib.error
import urllib.request
from app import create_server


class ArcadeServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = create_server('127.0.0.1', 0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = 'http://127.0.0.1:' + str(cls.server.server_address[1])

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(3)

    def test_health(self):
        with urllib.request.urlopen(self.base + '/health', timeout=3) as response:
            self.assertEqual(json.load(response), {'status': 'ok'})

    def test_assets(self):
        for path, expected in [('/', b'<canvas'), ('/game.js', b'requestAnimationFrame'), ('/style.css', b'color-scheme')]:
            with self.subTest(path=path), urllib.request.urlopen(self.base + path, timeout=3) as response:
                self.assertIn(expected, response.read())

    def test_private_files_are_not_served(self):
        for path in ['/app.py', '/CHECKS.json', '/../app.py', '/test_app.py', '/.env', '/unknown']:
            with self.subTest(path=path), self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(self.base + path, timeout=3)
            self.assertEqual(caught.exception.code, 404)
            caught.exception.close()
