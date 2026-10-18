"""Exercise the actual app over HTTP, with isolated data and restart checks."""
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
from urllib.parse import urlencode
import urllib.request

APP_PATH = Path(__file__).with_name("app.py")
spec = importlib.util.spec_from_file_location("notes_app_test_target", APP_PATH)
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)


class NotesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database = Path(self.temp.name) / "notes.db"
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

    def request(self, path="/api/notes", method="GET", data=None, raw=None, headers=None):
        req = urllib.request.Request(self.base + path, method=method,
            data=json.dumps(data).encode() if data is not None else raw,
            headers={"Content-Type": "application/json", **(headers or {})})
        try:
            response = urllib.request.urlopen(req, timeout=5)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            body = response.read().decode()
            if response.headers.get("Content-Type", "").startswith("application/json"):
                body = json.loads(body)
            return response.status, body

    def create(self, title="Buy milk", body="Need to buy groceries"):
        status, note = self.request(method="POST", data={"title": title, "body": body})
        self.assertEqual(status, 201)
        return note

    def test_health_and_assets(self):
        self.assertEqual(self.request("/health"), (200, {"status": "ok"}))
        for path, text in [("/", "<form"), ("/app.js", "textContent"), ("/style.css", "font-family")]:
            self.assertEqual(self.request(path)[0], 200)
            self.assertIn(text, self.request(path)[1])

    def test_create_and_list_objects(self):
        self.assertEqual(self.request(), (200, []))
        note = self.create("  Buy milk  ")
        self.assertEqual(note, {"id": 1, "title": "Buy milk", "body": "Need to buy groceries"})
        self.assertEqual(self.request(), (200, [note]))

    def test_matching_and_nonmatching_search(self):
        self.create()
        self.create("Read book", "A different note")
        self.assertEqual(self.request("/api/notes/search?q=MILK")[1][0]["title"], "Buy milk")
        self.assertEqual(self.request("/api/notes/search?q=does-not-exist"), (200, []))

    def test_search_decodes_spaces_unicode_and_symbols(self):
        title = "Café & milk 100%"
        self.create(title)
        for query in ["Café & milk", "100%", "", "MILK"]:
            self.assertEqual(self.request("/api/notes/search?" + urlencode({"q": query}))[1][0]["title"], title)

    def test_delete_and_confirm_absence(self):
        note = self.create()
        self.assertEqual(self.request(f'/api/notes/{note["id"]}', "DELETE"), (200, {"deleted": True, "id": 1}))
        self.assertEqual(self.request(), (200, []))
        self.assertEqual(self.request("/api/notes/1", "DELETE")[0], 404)

    def test_restart_persists_title_and_body(self):
        note = self.create()
        self.stop_server()
        self.start_server()
        self.assertEqual(self.request(), (200, [note]))

    def test_full_process_restart_persists_note(self):
        database = Path(self.temp.name) / "process-notes.db"
        saved_base = self.base
        def start():
            proc = subprocess.Popen([sys.executable, str(APP_PATH), "--port", "0", "--database", str(database)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            line = proc.stdout.readline().strip()
            if not line.startswith("Notes App: http://127.0.0.1:"):
                proc.terminate(); proc.wait(timeout=5); proc.stdout.close()
                self.fail(line)
            self.base = line.split(" ", 2)[2]
            return proc
        def stop(proc):
            proc.terminate(); proc.wait(timeout=5); proc.stdout.close()
        first = start()
        try:
            note = self.create("Remember this", "Persist across process restarts")
        finally:
            stop(first)
        second = start()
        try:
            self.assertEqual(self.request(), (200, [note]))
        finally:
            stop(second)
            self.base = saved_base

    def test_invalid_input_returns_json_errors(self):
        for data in [{}, {"title": "", "body": "x"}, {"title": 9, "body": "x"}, {"title": "x", "body": None}, {"title": "x" * 301, "body": "x"}, []]:
            with self.subTest(data=data):
                status, result = self.request(method="POST", data=data)
                self.assertEqual(status, 400)
                self.assertIn("error", result)
        self.assertEqual(self.request(method="POST", raw=b"not-json")[0], 400)
        self.assertEqual(self.request(), (200, []))

    def test_concurrent_creates(self):
        with ThreadPoolExecutor(max_workers=6) as pool:
            statuses = list(pool.map(lambda i: self.request(method="POST", data={"title": f"Note {i}", "body": "Saved"})[0], range(12)))
        self.assertEqual(statuses, [201] * 12)
        self.assertEqual(len(self.request()[1]), 12)

    def test_untrusted_text_is_stored_as_data(self):
        title = "<img src=x onerror=alert(1)>'); DROP TABLE notes;--"
        note = self.create(title, "<script>alert(1)</script>")
        self.assertEqual(self.request(), (200, [note]))
        self.create("Still works")

    def test_cross_origin_create_rejected(self):
        self.assertEqual(self.request(method="POST", data={"title": "Unexpected", "body": ""}, headers={"Origin": "https://untrusted.example"})[0], 403)
        self.assertEqual(self.request(), (200, []))

    def test_unknown_routes(self):
        for path in ["/api/notes/nope", "/api/notes/0", "/unknown"]:
            self.assertEqual(self.request(path, "DELETE")[0], 404)


if __name__ == "__main__":
    unittest.main()
