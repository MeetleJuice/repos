"""Regressions based on the user's real broken Notes App generation."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import threading
import unittest

from forge.core import Workbench, preflight
from forge.core import validate_plan
from forge.runner import verify
from tests.fixtures import APP, PLAN, TEST
from tests.test_workbench import ScriptedModels, await_job

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(__file__).with_name("fixture_data")


class VerificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def source(self, app=APP, tests=TEST):
        root = self.root / "source"
        root.mkdir()
        (root / "app.py").write_text(app, encoding="utf-8")
        (root / "test_app.py").write_text(tests, encoding="utf-8")
        (root / "CHECKS.json").write_text(json.dumps(PLAN["checks"]), encoding="utf-8")
        return root

    def test_exact_uploaded_failures_are_detected_without_execution(self):
        files = {"app.py": (DATA / "notes-original-app.txt").read_text(), "test_app.py": (DATA / "notes-original-tests.txt").read_text()}
        report = preflight(files)
        self.assertFalse(report["passed"])
        self.assertFalse(report["executed"])
        issues = "\n".join(report["issues"])
        self.assertIn("cgi/cgitb", issues)
        self.assertIn("import the real app.py", issues)
        self.assertIn("handle_request", issues)
        self.assertIn("reimplement", issues)

    def test_real_notes_failure_can_be_repaired_in_one_model_round(self):
        repaired = ROOT / "examples" / "notes-app"
        plan = json.loads((ROOT / "examples" / "notes-proposal.json").read_text())
        plan["tasks"] = [{"title": "Build the complete Notes App", "instructions": "Implement all features and actual app tests.", "feature_indexes": list(range(len(plan["features"])))}]
        broken = {"app.py": (DATA / "notes-original-app.txt").read_text(), "test_app.py": (DATA / "notes-original-tests.txt").read_text(), "index.html": (DATA / "notes-original-index.txt").read_text()}
        fixed = {name: (repaired / name).read_text() for name in ["app.py", "test_app.py", "index.html", "app.js", "style.css"]}
        models = ScriptedModels([plan, {"files": broken}, {"files": fixed}])
        bench = Workbench(self.root / "projects", models)
        config = {"provider": "ollama", "model": "scripted-test"}
        state = bench.create("Build a local notes app", config, config)
        state = await_job(bench, state["id"])
        bench.approve(state["id"], state["plan"])
        bench.start(state["id"], "build", {"execute": True, "consent": True, "runtime": "local", "repairs": 1})
        state = await_job(bench, state["id"])
        self.assertEqual(state["status"], "verified", state.get("error"))
        self.assertEqual(state["repair_count"], 1)
        self.assertEqual(len(models.calls), 3)
        self.assertEqual([p["phase"] for p in state["checks"]["phases"]], ["acceptance", "tests", "launch"])
        self.assertEqual(state["checks"]["phases"][1]["tests_run"], 12)
        self.assertGreater(state["checks"]["phases"][1]["app_calls"], 0)
        self.assertEqual(state["frozen_tests"]["test_app.py"], hashlib.sha256(fixed["test_app.py"].encode()).hexdigest())
        self.assertEqual(json.loads(bench.files(state["id"])["CHECKS.json"]), plan["checks"])
        with self.assertRaises(ValueError):
            bench.apply(state, {"files": {"test_app.py": TEST}}, repair=True)

    def test_faulty_unverified_tests_can_be_repaired_without_running_code(self):
        bad_test = 'import unittest\nclass Tests(unittest.TestCase):\n def test_placeholder(self):\n  self.assertTrue(True)\n'
        models = ScriptedModels([PLAN, {"files": {"app.py": APP, "test_app.py": bad_test}}, {"files": {"test_app.py": TEST}}])
        bench = Workbench(self.root / "projects", models, verifier=lambda *a: self.fail("No execution consent"))
        config = {"provider": "ollama", "model": "test"}
        state = bench.create("Build a task tracker", config, config)
        state = await_job(bench, state["id"])
        bench.approve(state["id"], state["plan"])
        bench.start(state["id"], "build", {"execute": False, "repairs": 1})
        state = await_job(bench, state["id"])
        self.assertEqual(state["status"], "generated", state.get("error"))
        self.assertEqual(state["repair_count"], 1)
        self.assertEqual(bench.files(state["id"])["test_app.py"], TEST)
        self.assertIsNone(state["checks"])

    def test_acceptance_runs_before_hanging_generated_tests(self):
        broken_app = APP.replace('db.execute("CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY, title TEXT)")', 'pass')
        hanging = TEST.replace('    def test_health(self):\n', '    def test_health(self):\n        import time\n        time.sleep(60)\n')
        result = verify(self.source(broken_app, hanging), "local", threading.Event(), timeout=10, test_timeout=0.3)
        self.assertFalse(result["passed"])
        self.assertIn("database table is missing", result["diagnosis"])
        self.assertEqual([p["phase"] for p in result["phases"]], ["acceptance"])

    def test_generated_tests_must_call_actual_app_not_just_import_it(self):
        trivial = 'import unittest\nimport app\nclass Tests(unittest.TestCase):\n def test_fake(self):\n  self.assertTrue(True)\n'
        self.assertTrue(preflight({"app.py": APP, "test_app.py": trivial})["passed"])
        result = verify(self.source(tests=trivial), "local", threading.Event())
        self.assertFalse(result["passed"])
        self.assertIn("did not execute the real application", result["diagnosis"])
        self.assertEqual(result["phases"][1]["phase"], "tests")

    def test_generated_test_timeout_is_a_specific_failure(self):
        hanging = TEST.replace('    def test_health(self):\n', '    def test_health(self):\n        import time\n        time.sleep(60)\n')
        result = verify(self.source(tests=hanging), "local", threading.Event(), timeout=10, test_timeout=0.4)
        self.assertFalse(result["passed"])
        self.assertIn("Generated tests timed out", result["diagnosis"])
        self.assertTrue(result["phases"][0]["passed"])
        self.assertTrue(result["phases"][1]["timed_out"])

    def test_referenced_missing_stylesheet_fails_acceptance(self):
        app = APP.replace("<title>Pocket Tasks</title>", '<title>Pocket Tasks</title><link rel=stylesheet href=/missing.css>')
        result = verify(self.source(app=app), "local", threading.Event())
        self.assertFalse(result["passed"])
        self.assertIn("page or asset is missing", result["diagnosis"])
        self.assertEqual(len(result["phases"]), 1)

    def test_tests_cannot_pollute_acceptance_or_launch_data(self):
        tests = TEST + '\nclass IsolationTests(unittest.TestCase):\n    def test_mutate_disposable_files(self):\n        with open("CHECKS.json", "w") as f: f.write("[]")\n        with open("app.py", "w") as f: f.write("raise RuntimeError")\n'
        root = self.source(tests=tests)
        result = verify(root, "local", threading.Event())
        self.assertTrue(result["passed"], result["log"])
        self.assertEqual((root / "app.py").read_text(), APP)
        self.assertEqual(json.loads((root / "CHECKS.json").read_text()), PLAN["checks"])
        self.assertEqual(len(result["phases"]), 3)

    def test_list_object_contract_rejects_array_rows(self):
        app = APP.replace('self.reply([{"id":row[0], "title":row[1]} for row in rows])', 'self.reply(rows)')
        root = self.source(app=app)
        plan = copy.deepcopy(PLAN)
        plan["checks"][1].pop("contains")
        plan["checks"][1]["json_contains"] = [{"id": 1, "title": "Buy milk"}]
        validate_plan(plan)
        (root / "CHECKS.json").write_text(json.dumps(plan["checks"]))
        result = verify(root, "local", threading.Event())
        self.assertFalse(result["passed"])
        self.assertIn("wrong JSON structure", result["diagnosis"])
        self.assertEqual(len(result["phases"]), 1)

    def test_exact_empty_list_assertion_is_supported(self):
        root = self.source()
        plan = copy.deepcopy(PLAN)
        plan["checks"].insert(0, {"name": "Initially empty", "method": "GET", "path": "/api/tasks", "status": 200, "json_equals": [], "feature_indexes": [1]})
        validate_plan(plan)
        (root / "CHECKS.json").write_text(json.dumps(plan["checks"]))
        result = verify(root, "local", threading.Event())
        self.assertTrue(result["passed"], result["log"])


if __name__ == "__main__":
    unittest.main()
