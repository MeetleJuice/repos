"""Release-level regressions for project changes, storage, recovery and concurrency."""
import copy
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import subprocess
import sys
import socket
import signal
import unittest
from unittest.mock import patch
import zipfile

from forge.core import Workbench
from forge.models import ModelClient
from forge.runner import require_runtime
from forge.storage import data_home, import_legacy, workspace_lock
from tests.fixtures import APP, PLAN, TEST
from tests.test_workbench import ScriptedModels, await_job

CONFIG = {"provider": "ollama", "model": "test"}


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def built_project(self, responses=()):
        models = ScriptedModels([PLAN, {"files": {"app.py": APP, "test_app.py": TEST}}, *responses])
        bench = Workbench(self.root / "projects", models)
        state = bench.create("Build a task tracker", CONFIG, CONFIG)
        state = await_job(bench, state["id"])
        bench.approve(state["id"], state["plan"])
        bench.start(state["id"], "build", {})
        state = await_job(bench, state["id"])
        self.assertEqual(state["status"], "generated", state.get("error"))
        return bench, state, models

    def test_change_preserves_parent_tests_and_acceptance_checks(self):
        change = copy.deepcopy(PLAN)
        change["features"].append("Show a Search heading")
        change["tasks"][0]["feature_indexes"] = [0, 1, 2]
        # Intentionally omit original checks; the backend must put them back.
        change["checks"] = [{"name": "Search heading", "method": "GET", "path": "/", "status": 200, "contains": "Search", "feature_indexes": [0, 1, 2]}]
        changed_app = APP.replace("<h1>Pocket Tasks</h1>", "<h1>Pocket Tasks Search</h1>")
        bench, parent, models = self.built_project([change, {"files": {"app.py": changed_app}}])
        original = bench.files(parent["id"])
        child = bench.fork(parent["id"], "Add a Search heading to the app")
        child = await_job(bench, child["id"])
        self.assertEqual(child["status"], "proposed", child.get("error"))
        for check in PLAN["checks"]:
            self.assertIn(check, child["plan"]["checks"])
        self.assertEqual(child["parent_id"], parent["id"])
        bench.approve(child["id"], child["plan"])
        bench.start(child["id"], "build", {"execute": True, "consent": True, "runtime": "local", "repairs": 0})
        child = await_job(bench, child["id"])
        self.assertEqual(child["status"], "verified", child.get("error"))
        self.assertEqual(bench.files(parent["id"]), original)
        self.assertEqual(bench.files(child["id"])["test_app.py"], TEST)
        self.assertEqual(child["repair_count"], 0)
        self.assertIn("frozen_tests", models.calls[-1])

    def test_change_cannot_rewrite_existing_tests_or_drop_features(self):
        bench, parent, _ = self.built_project([PLAN])
        child = bench.fork(parent["id"], "Make a useful interface improvement")
        child = await_job(bench, child["id"])
        with self.assertRaisesRegex(ValueError, "Existing app tests"):
            bench.apply(child, {"files": {"test_app.py": TEST + "\n# change\n"}})
        bad = copy.deepcopy(PLAN)
        bad["features"] = ["Replace everything"]
        with self.assertRaisesRegex(ValueError, "preserve the original features"):
            bench.approve(child["id"], bad)

    def test_model_switch_preserves_source_and_requirements(self):
        bench, state, _ = self.built_project()
        source = bench.files(state["id"])
        new = {"provider": "groq", "model": "user-chosen-model"}
        result = bench.configure_models(state["id"], CONFIG, new)
        self.assertEqual(result["coder"], new)
        self.assertEqual(result["plan"], state["plan"])
        self.assertEqual(bench.files(state["id"]), source)
        with self.assertRaisesRegex(ValueError, "Embedding"):
            bench.configure_models(state["id"], CONFIG, {"provider": "ollama", "model": "nomic-embed-text"})

    def test_backup_has_projects_but_no_env_or_caches(self):
        bench, state, _ = self.built_project()
        source = bench.directory(state["id"]) / "source"
        (source / ".env").write_text("DO_NOT_EXPORT=placeholder")
        (source / "__pycache__").mkdir()
        (source / "__pycache__" / "x.pyc").write_bytes(b"cache")
        self.assertNotIn(".env", bench.files(state["id"]))
        with zipfile.ZipFile(io.BytesIO(bench.backup())) as archive:
            names = archive.namelist()
            self.assertIn(f'projects/{state["id"]}/state.json', names)
            self.assertIn(f'projects/{state["id"]}/source/app.py', names)
            self.assertFalse(any(".env" in n or "__pycache__" in n for n in names))

    def test_corrupt_project_does_not_block_other_projects(self):
        bench, state, _ = self.built_project()
        damaged = bench.root / ("a" * 32)
        damaged.mkdir()
        (damaged / "state.json").write_text("[]")
        restarted = Workbench(bench.root)
        self.assertEqual([p["id"] for p in restarted.list_projects()], [state["id"]])
        self.assertTrue(restarted.warnings)
        self.assertEqual((damaged / "state.json").read_text(), "[]")

    def test_legacy_import_copies_without_overwriting_or_removing(self):
        bench, state, _ = self.built_project()
        program = self.root / "program"
        legacy = program / "data" / "projects"
        import shutil
        shutil.copytree(bench.root, legacy)
        home = self.root / "user-home"
        self.assertEqual(import_legacy(program, home), [state["id"]])
        target = home / "projects" / state["id"] / "source" / "app.py"
        target.write_text("User work must survive")
        self.assertEqual(import_legacy(program, home), [])
        self.assertEqual(target.read_text(), "User work must survive")
        self.assertEqual((legacy / state["id"] / "source" / "app.py").read_text(), APP)

    def test_workspace_lock_and_explicit_data_path(self):
        self.assertEqual(data_home(self.root, str(self.root / "custom")), self.root / "custom")
        with workspace_lock(self.root):
            with self.assertRaisesRegex(ValueError, "Another Idea Foundry"):
                with workspace_lock(self.root):
                    self.fail("The second process must not use the same workspace")
        with workspace_lock(self.root):
            pass

    def test_corrupt_legacy_project_is_preserved_without_blocking_import(self):
        program = self.root / "program"
        legacy = program / "data" / "projects" / ("f" * 32)
        legacy.mkdir(parents=True)
        (legacy / "state.json").write_text("broken metadata")
        warnings = []
        self.assertEqual(import_legacy(program, self.root / "new-home", warnings), [])
        self.assertTrue(warnings)
        self.assertEqual((legacy / "state.json").read_text(), "broken metadata")

    def test_docker_blocker_does_not_trigger_model_calls(self):
        bench, state, models = self.built_project()
        before = len(models.calls)
        with patch("forge.runner.runtime_diagnostics", return_value={"installed": True, "running": True, "image_ready": False}):
            bench.start(state["id"], "build", {"execute": True, "consent": True, "runtime": "docker"})
            state = await_job(bench, state["id"])
        self.assertEqual(state["status"], "error")
        self.assertIn("docker pull", state["error"])
        self.assertEqual(len(models.calls), before)

    def test_environment_failure_does_not_request_code_repair(self):
        bench, state, models = self.built_project()
        before = len(models.calls)
        bench.verifier = lambda *a: {"passed": False, "failure_kind": "environment", "log": "Docker mount failed", "runtime": "local", "exit_code": 125}
        bench.start(state["id"], "build", {"execute": True, "consent": True, "runtime": "local"})
        state = await_job(bench, state["id"])
        self.assertEqual(state["status"], "needs_attention")
        self.assertEqual(len(models.calls), before)

    def test_diff_and_model_timing_are_real_records(self):
        bench, state, _ = self.built_project()
        changes = bench.diff(state["id"])
        self.assertTrue(any(c["name"] == "app.py" and "+def create_server" in c["diff"] for c in changes))
        self.assertEqual(len(state["model_calls"]), 2)
        self.assertTrue(all(c["seconds"] >= 0 and c["success"] for c in state["model_calls"]))
        self.assertTrue(state["milestones"][0]["syntax_passed"])
        self.assertFalse(state["milestones"][0]["behavior_verified"])

    def test_failed_source_swap_preserves_previous_app(self):
        bench, state, _ = self.built_project()
        original = bench.files(state["id"])
        replace = os.replace
        def fail_install(source, destination):
            if Path(source).name.startswith(".source-update-"):
                raise OSError("Simulated failed installation")
            return replace(source, destination)
        with patch("forge.core.os.replace", side_effect=fail_install), self.assertRaises(OSError):
            bench.apply(state, {"files": {"app.py": APP + "\n# changed\n"}})
        self.assertEqual(bench.files(state["id"]), original)

    def test_restart_recovers_interrupted_source_swap(self):
        bench, state, _ = self.built_project()
        root = bench.directory(state["id"])
        os.replace(root / "source", root / ".source-before-interrupted")
        restarted = Workbench(bench.root)
        self.assertEqual(restarted.files(state["id"])["app.py"], APP)
        self.assertTrue(any("Recovered" in warning for warning in restarted.warnings))

    def test_downloaded_app_launcher_uses_a_free_port(self):
        bench, state, _ = self.built_project()
        source = bench.directory(state["id"]) / "source"
        with socket.socket() as occupied:
            occupied.bind(("127.0.0.1", 0))
            occupied.listen()
            port = occupied.getsockname()[1]
            flags = {"start_new_session": True} if os.name != "nt" else {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
            proc = subprocess.Popen([sys.executable, "launch.py", "--no-browser", "--port", str(port)], cwd=source,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, **flags)
            try:
                line = proc.stdout.readline()
                self.assertTrue(line.startswith("APP_READY http://127.0.0.1:"), line)
                url = line.split()[1]
                self.assertNotEqual(int(url.rsplit(":", 1)[1]), port)
                import urllib.request
                with urllib.request.urlopen(url + "/health", timeout=5) as response:
                    self.assertEqual(json.load(response), {"status": "ok"})
            finally:
                if os.name == "nt":
                    proc.send_signal(signal.CTRL_BREAK_EVENT)
                else:
                    proc.send_signal(signal.SIGINT)
                try:
                    proc.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)
                proc.stdout.close()

    def test_queued_job_can_stop_without_second_inference(self):
        entered, release = threading.Event(), threading.Event()
        class BlockingModel:
            calls = 0
            def __call__(self, *args):
                return self
            def complete(self, *args):
                self.calls += 1
                entered.set()
                release.wait(5)
                return copy.deepcopy(PLAN)
        model = BlockingModel()
        bench = Workbench(self.root / "projects", model)
        first = bench.create("Build the first tracker", CONFIG, CONFIG)
        self.assertTrue(entered.wait(3))
        second = bench.create("Build the second tracker", CONFIG, CONFIG)
        try:
            deadline = time.monotonic() + 3
            while bench.load(second["id"])["status"] != "queued" and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertEqual(bench.load(second["id"])["status"], "queued")
            bench.stop(second["id"])
            self.assertEqual(await_job(bench, second["id"])["status"], "stopped")
            self.assertEqual(model.calls, 1)
            with self.assertRaisesRegex(ValueError, "stop all jobs"):
                bench.backup()
        finally:
            release.set()
            await_job(bench, first["id"])


if __name__ == "__main__":
    unittest.main()
