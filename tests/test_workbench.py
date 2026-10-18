import copy
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request
import zipfile

from forge.core import Workbench, validate_plan, safe_file, ACTIVE, preflight
from forge.models import ModelClient, extract_json
from forge.runner import verify
from forge.server import make_server
from tests.fixtures import PLAN, APP, BROKEN, TEST


class ScriptedModels:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, provider, model):
        return self

    def complete(self, system, prompt):
        self.calls.append(json.loads(prompt))
        if not self.responses:
            raise ValueError("No scripted response left.")
        value = self.responses.pop(0)
        if isinstance(value, Exception):
            raise value
        return copy.deepcopy(value)


def await_job(bench, ident):
    bench.jobs[ident][0].join(20)
    if bench.jobs[ident][0].is_alive():
        raise AssertionError("Job did not complete.")
    return bench.load(ident)


class WorkbenchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def create(self, responses):
        model = ScriptedModels([PLAN, *responses])
        bench = Workbench(self.root, model)
        config = {"provider": "ollama", "model": "test"}
        p = bench.create("Make a task tracker", config, config)
        p = await_job(bench, p["id"])
        self.assertEqual(p["status"], "proposed")
        bench.approve(p["id"], p["plan"])
        return bench, p["id"], model

    def test_real_checks_detect_and_repair_behavior(self):
        bench, ident, models = self.create([
            {"summary": "Initial code", "files": {"app.py": BROKEN, "test_app.py": TEST}},
            {"summary": "Repair listing", "files": {"app.py": APP}},
        ])
        bench.start(ident, "build", {"execute": True, "consent": True, "runtime": "local", "repairs": 1})
        state = await_job(bench, ident)
        self.assertEqual(state["status"], "verified", state.get("error"))
        self.assertEqual(state["repair_count"], 1)
        self.assertIn("Retrieve saved task", models.calls[-1]["failure"])
        self.assertIn('"tests_run": 1', state["checks"]["log"])
        self.assertIn('"http_checks": 5', state["checks"]["log"])
        self.assertEqual(bench.files(ident)["test_app.py"], TEST)
        self.assertFalse((bench.directory(ident) / "source" / "tasks.db").exists())
        self.assertNotIn("CHECKS.json", models.calls[-1]["files"])
        snapshot = state["snapshots"][-1]["id"]
        restored = bench.restore(ident, snapshot)
        self.assertEqual(restored["status"], "approved")
        self.assertIsNone(restored["checks"])
        self.assertEqual(bench.files(ident)["app.py"], BROKEN)

    def test_generation_does_not_execute(self):
        bench, ident, _ = self.create([{"files": {"app.py": APP, "test_app.py": TEST}}])
        bench.verifier = lambda *a: self.fail("Must not execute without consent")
        bench.start(ident, "build", {"execute": False})
        state = await_job(bench, ident)
        self.assertEqual(state["status"], "generated")
        self.assertIsNone(state["checks"])
        with self.assertRaises(ValueError):
            bench.start(ident, "build", {"execute": True})

    def test_repair_budget_exhaustion_is_not_success(self):
        bench, ident, _ = self.create([{"files": {"app.py": BROKEN, "test_app.py": TEST}}])
        bench.start(ident, "build", {"execute": True, "consent": True, "runtime": "local", "repairs": 0})
        state = await_job(bench, ident)
        self.assertEqual(state["status"], "needs_attention")
        self.assertFalse(state["checks"]["passed"])

    def test_zero_tests_is_not_success(self):
        bench, ident, _ = self.create([{"files": {"app.py": APP}}])
        bench.start(ident, "build", {"execute": True, "consent": True, "runtime": "local", "repairs": 0})
        state = await_job(bench, ident)
        self.assertEqual(state["status"], "needs_attention")
        self.assertIsNone(state["checks"])
        self.assertIn("Missing unittest", " ".join(state["preflight"]["issues"]))

    def test_early_zero_exit_is_not_success(self):
        early_exit = APP + '\nif __name__ == "foundry_generated_app":\n    import sys\n    sys.exit(0)\n'
        bench, ident, _ = self.create([{"files": {"app.py": early_exit, "test_app.py": TEST}}])
        bench.start(ident, "build", {"execute": True, "consent": True, "runtime": "local", "repairs": 0})
        state = await_job(bench, ident)
        self.assertEqual(state["status"], "needs_attention")
        self.assertIn("zero exit code alone", state["checks"]["log"])

    def test_resume_after_model_failure(self):
        bench, ident, models = self.create([ValueError("Model offline"), {"files": {"app.py": APP, "test_app.py": TEST}}])
        bench.start(ident, "build", {})
        self.assertEqual(await_job(bench, ident)["status"], "error")
        self.assertEqual(bench.load(ident)["next_task"], 0)
        bench.start(ident, "build", {})
        self.assertEqual(await_job(bench, ident)["status"], "generated")

    def test_files_are_validated_before_writes(self):
        bench, ident, _ = self.create([])
        state = bench.load(ident)
        with self.assertRaises(ValueError):
            bench.apply(state, {"files": {"app.py": APP, "../escape.py": "bad"}})
        self.assertNotIn("app.py", bench.files(ident))
        bench.apply(state, {"files": {"test_app.py": TEST}})
        with self.assertRaises(ValueError):
            bench.apply(state, {"files": {"CHECKS.json": "[]"}})
        with self.assertRaises(ValueError):
            bench.apply(state, {"files": {"test_app.py": "pass"}}, repair=True)
        for name in ["../x.py", "/x.py", ".env", "C:/x.py", "a\\x.py", "CON.py", "x./a.py"]:
            with self.subTest(name=name), self.assertRaises(ValueError):
                safe_file(self.root, name)

    def test_static_repair_adds_missing_tests_without_execution(self):
        bench, ident, _ = self.create([
            {"files": {"app.py": "def create_server(:\n"}},
            {"files": {"app.py": APP, "test_app.py": TEST}},
        ])
        bench.verifier = lambda *a: self.fail("Static repair must not execute code")
        bench.start(ident, "build", {"execute": False, "repairs": 1})
        state = await_job(bench, ident)
        self.assertEqual(state["status"], "generated", state.get("error"))
        self.assertTrue(state["preflight"]["passed"])
        self.assertEqual(state["repair_count"], 1)
        self.assertIsNone(state["checks"])
        self.assertIn("test_app.py", bench.files(ident))

    def test_static_and_runtime_repairs_share_one_budget(self):
        bench, ident, models = self.create([
            {"files": {"app.py": BROKEN}},
            {"files": {"test_app.py": TEST}},
        ])
        bench.start(ident, "build", {"execute": True, "consent": True, "runtime": "local", "repairs": 1})
        state = await_job(bench, ident)
        self.assertEqual(state["status"], "needs_attention")
        self.assertEqual(state["repair_count"], 1)
        self.assertFalse(state["checks"]["passed"])
        self.assertEqual(len(models.calls), 3)

    def test_incomplete_plan_is_rejected_and_planner_retries(self):
        invalid = copy.deepcopy(PLAN)
        invalid["tasks"][0]["feature_indexes"] = [0]
        with self.assertRaisesRegex(ValueError, "Missing feature indexes"):
            validate_plan(invalid)
        models = ScriptedModels([invalid, PLAN])
        bench = Workbench(self.root, models)
        cfg = {"provider": "ollama", "model": "test"}
        state = bench.create("Make a task tracker", cfg, cfg)
        state = await_job(bench, state["id"])
        self.assertEqual(state["status"], "proposed")
        self.assertIn("validation_error", models.calls[1])
        self.assertEqual(len(models.calls), 2)

    def test_missing_test_methods_and_syntax_are_detected(self):
        result = preflight({"app.py": "def create_server(:\n", "test_app.py": "import unittest\n"})
        self.assertFalse(result["passed"])
        self.assertTrue(any("syntax error" in issue for issue in result["issues"]))
        self.assertTrue(any("test_ methods" in issue for issue in result["issues"]))

    def test_approval_is_required_and_frozen(self):
        bench, ident, _ = self.create([])
        with self.assertRaises(ValueError):
            bench.approve(ident, PLAN)
        with self.assertRaises(ValueError):
            bench.start(ident, "plan", {})
        plan = copy.deepcopy(PLAN)
        plan["checks"] = [{"name": "Only health", "method": "GET", "path": "/health", "status": 200, "contains": "ok"}]
        with self.assertRaises(ValueError):
            validate_plan(plan)

    def test_restart_marks_unfinished_job_interrupted(self):
        bench, ident, _ = self.create([])
        state = bench.load(ident)
        state["status"] = "building"
        bench.save(state)
        new = Workbench(self.root)
        self.assertEqual(new.load(ident)["status"], "interrupted")

    def test_timeout_and_cancellation(self):
        source = self.root / "source"
        source.mkdir()
        (source / "app.py").write_text(APP)
        (source / "test_app.py").write_text("import time\ntime.sleep(30)\n")
        (source / "CHECKS.json").write_text(json.dumps(PLAN["checks"]))
        result = verify(source, "local", threading.Event(), timeout=0.3)
        self.assertFalse(result["passed"])
        self.assertIn("time limit", result["log"])
        cancel = threading.Event(); cancel.set()
        result = verify(source, "local", cancel)
        self.assertFalse(result["passed"])
        self.assertIn("Stopped by user", result["log"])


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.models = ScriptedModels([PLAN, {"files": {"app.py": APP, "test_app.py": TEST}}])
        self.bench = Workbench(self.temp.name, self.models)
        self.server = make_server(0, self.bench)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        with urllib.request.urlopen(self.base) as response:
            html = response.read().decode()
            self.token = html.split('name="foundry-token" content="')[1].split('"')[0]

    def tearDown(self):
        for thread, cancel in self.bench.jobs.values():
            cancel.set(); thread.join(5)
        self.server.shutdown(); self.server.server_close(); self.temp.cleanup()

    def call(self, path, body=None, token=True, origin=None):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["X-Foundry-Token"] = self.token
        if origin:
            headers["Origin"] = origin
        req = urllib.request.Request(self.base + path, headers=headers, data=None if body is None else json.dumps(body).encode())
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.read()

    def test_full_api_proposal_approval_build_export(self):
        cfg = {"provider": "ollama", "model": "test"}
        p = json.loads(self.call("/api/projects", {"idea": "Create a task tracker", "planner": cfg, "coder": cfg}))
        p = await_job(self.bench, p["id"])
        prefix = "/api/projects/" + p["id"]
        self.call(prefix + "/approve", {"plan": p["plan"]})
        self.call(prefix + "/build", {"execute": True, "consent": True, "runtime": "local", "repairs": 0})
        p = await_job(self.bench, p["id"])
        self.assertEqual(p["status"], "verified")
        with zipfile.ZipFile(io.BytesIO(self.call(prefix + "/download"))) as archive:
            self.assertIn("generated-app/app.py", archive.namelist())
            self.assertIn("generated-app/PROJECT.md", archive.namelist())
            report = json.loads(archive.read("generated-app/BUILD-REPORT.json"))
            self.assertTrue(report["checks"]["passed"])
            self.assertFalse(any(".env" in n or ".git" in n for n in archive.namelist()))

    def test_api_requires_session_and_same_origin(self):
        with self.assertRaises(urllib.error.HTTPError) as exc:
            self.call("/api/projects", token=False)
        self.assertEqual(exc.exception.code, 403)
        with self.assertRaises(urllib.error.HTTPError) as exc:
            self.call("/api/projects", origin="https://untrusted.example")
        self.assertEqual(exc.exception.code, 403)

    def test_cloud_requires_explicit_consent(self):
        cfg = {"provider": "groq", "model": "test"}
        with self.assertRaises(urllib.error.HTTPError) as exc:
            self.call("/api/projects", {"idea": "Make a task tracker", "planner": cfg, "coder": cfg})
        self.assertEqual(exc.exception.code, 400)
        self.assertEqual(len(self.bench.list_projects()), 0)


class ProviderTests(unittest.TestCase):
    def test_ollama_protocol_through_real_http(self):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        seen = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_): pass
            def do_POST(self):
                seen.append((self.path, json.loads(self.rfile.read(int(self.headers["Content-Length"])))))
                body = json.dumps({"message": {"content": json.dumps(PLAN)}}).encode()
                self.send_response(200);self.send_header("Content-Length", str(len(body)));self.end_headers();self.wfile.write(body)
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with patch.dict(os.environ, {"OLLAMA_URL": f"http://127.0.0.1:{server.server_port}"}):
                plan = ModelClient("ollama", "qwen-test").complete("JSON", "Task tracker")
            self.assertEqual(plan, PLAN)
            self.assertEqual(seen[0][0], "/api/chat")
            self.assertEqual(seen[0][1]["format"], "json")
            self.assertFalse(seen[0][1]["stream"])
        finally:
            server.shutdown();server.server_close()

    def test_cloud_adapters_and_secret_presence(self):
        for provider, variable in [("groq", "GROQ_API_KEY"), ("openrouter", "OPENROUTER_API_KEY"), ("gemini", "GEMINI_API_KEY")]:
            with self.subTest(provider=provider), patch.dict(os.environ, {variable: "test-placeholder"}), patch("forge.models.request_json") as call:
                call.return_value = {"choices": [{"message": {"content": json.dumps(PLAN)}}]}
                self.assertEqual(ModelClient(provider, "test-model").complete("system", "prompt"), PLAN)
                self.assertTrue(call.call_args.args[0].startswith("https://"))
                self.assertEqual(call.call_args.args[2]["Authorization"], "Bearer test-placeholder")
        with patch.dict(os.environ, {}, clear=True), self.assertRaisesRegex(ValueError, "GROQ_API_KEY"):
            ModelClient("groq", "test").complete("system", "prompt")

    def test_structured_output_errors(self):
        self.assertEqual(extract_json('```json\n{"files":{}}\n```'), {"files": {}})
        self.assertEqual(extract_json('<think>thinking</think>{"ok":true}'), {"ok": True})
        for content in ["not json", "[]", "```python\nprint('hi')\n```"]:
            with self.assertRaises(ValueError):
                extract_json(content)


if __name__ == "__main__":
    unittest.main()
