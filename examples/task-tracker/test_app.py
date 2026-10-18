"""Behavioral tests against real HTTP requests and a temporary SQLite database."""
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

spec = importlib.util.spec_from_file_location("task_tracker_test_target", Path(__file__).with_name("app.py"))
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)


class TrackerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database = Path(self.temp.name) / "tasks.db"
        self.start_server()

    def start_server(self):
        self.server = app.create_server("127.0.0.1", 0, self.database)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(3)

    def tearDown(self):
        self.stop_server()
        self.temp.cleanup()

    def request(self, path="/api/tasks", method="GET", data=None, raw=None, headers=None):
        body = json.dumps(data).encode() if data is not None else raw
        req = urllib.request.Request(self.base + path, method=method, data=body,
            headers={"Content-Type": "application/json", **(headers or {})})
        try:
            response = urllib.request.urlopen(req, timeout=10)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            content = response.read().decode()
            if response.headers.get("Content-Type", "").startswith("application/json"):
                content = json.loads(content)
            return response.status, content

    def test_health_and_browser_assets(self):
        self.assertEqual(self.request("/health"), (200, {"status": "ok"}))
        for path, expected in [("/", "Task Tracker"), ("/app.js", "textContent"), ("/style.css", "font-family")]:
            with self.subTest(path=path):
                status, body = self.request(path)
                self.assertEqual(status, 200)
                self.assertIn(expected, body)

    def test_create_and_list(self):
        self.assertEqual(self.request(), (200, []))
        status, task = self.request(method="POST", data={"title": "  Buy milk  "})
        self.assertEqual(status, 201)
        self.assertEqual(task, {"id": 1, "title": "Buy milk", "completed": False})
        self.assertEqual(self.request(), (200, [task]))

    def test_complete_and_reopen(self):
        self.request(method="POST", data={"title": "Read a book"})
        status, task = self.request("/api/tasks/1", "PUT")
        self.assertEqual(status, 200)
        self.assertTrue(task["completed"])
        self.assertTrue(self.request()[1][0]["completed"])
        status, task = self.request("/api/tasks/1", "PUT", {"completed": False})
        self.assertEqual(status, 200)
        self.assertFalse(task["completed"])

    def test_delete(self):
        self.request(method="POST", data={"title": "Remove me"})
        self.assertEqual(self.request("/api/tasks/1", "DELETE"), (200, {"id": 1, "deleted": True}))
        self.assertEqual(self.request(), (200, []))
        self.assertEqual(self.request("/api/tasks/1", "DELETE")[0], 404)

    def test_persistence_after_server_restart(self):
        self.request(method="POST", data={"title": "Keep me"})
        self.request("/api/tasks/1", "PUT", {"completed": True})
        self.stop_server()
        self.start_server()
        self.assertEqual(self.request(), (200, [{"id": 1, "title": "Keep me", "completed": True}]))

    def test_bad_input_returns_400_without_creating_tasks(self):
        for data in [{}, {"title": " "}, {"title": 1}, {"title": "x" * 301}, [], None]:
            with self.subTest(data=data):
                self.assertEqual(self.request(method="POST", data=data, raw=b"invalid" if data is None else None)[0], 400)
        self.request(method="POST", data={"title": "Valid"})
        self.assertEqual(self.request("/api/tasks/1", "PUT", {"completed": "false"})[0], 400)
        self.assertEqual(len(self.request()[1]), 1)

    def test_form_encoded_submission(self):
        status, task = self.request(method="POST", raw=b"title=Buy+tea", headers={"Content-Type": "application/x-www-form-urlencoded"})
        self.assertEqual(status, 201)
        self.assertEqual(task["title"], "Buy tea")

    def test_unknown_and_invalid_routes(self):
        for path in ["/api/tasks/nope", "/api/tasks/0", "/api/tasks/999", "/unknown"]:
            with self.subTest(path=path):
                self.assertEqual(self.request(path, "PUT")[0], 404)

    def test_concurrent_creates_use_independent_connections(self):
        with ThreadPoolExecutor(max_workers=6) as pool:
            statuses = list(pool.map(lambda i: self.request(method="POST", data={"title": f"Task {i}"})[0], range(12)))
        self.assertEqual(statuses, [201] * 12)
        rows = self.request()[1]
        self.assertEqual(len(rows), 12)
        self.assertEqual(len({t["id"] for t in rows}), 12)

    def test_sql_and_html_are_stored_as_text(self):
        title = "<img src=x onerror=alert(1)>'); DROP TABLE tasks;--"
        self.assertEqual(self.request(method="POST", data={"title": title})[0], 201)
        self.assertEqual(self.request()[1][0]["title"], title)
        self.assertEqual(self.request(method="POST", data={"title": "Still works"})[0], 201)

    def test_cross_origin_writes_are_rejected(self):
        status, _ = self.request(method="POST", data={"title": "Unwanted"}, headers={"Origin": "https://untrusted.example"})
        self.assertEqual(status, 403)
        self.assertEqual(self.request(), (200, []))


if __name__ == "__main__":
    unittest.main()
