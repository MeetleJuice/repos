"""Persistent projects and a deliberately bounded plan/build/check/repair state machine."""
from datetime import datetime, timezone
import copy
import difflib
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import threading
import time
import uuid
import zipfile

from .models import ModelClient
from .prompts import PLAN, CODE
from .inspection import inspect_files
from .runner import verify, require_runtime

OWNED = {"readme.md", "project.md", "tasks.md", "checks.json", "run.bat", "run.sh", "launch.py"}
ACTIVE = {"planning", "building", "checking", "repairing", "queued"}


def validate_plan(plan):
    for name in ("title", "summary"):
        if not isinstance(plan.get(name), str) or not plan[name].strip() or len(plan[name]) > 6000:
            raise ValueError(f"Proposal needs a nonempty {name} (up to 6000 characters).")
    for name in ("features", "out_of_scope", "risks"):
        if not isinstance(plan.get(name), list) or len(plan[name]) > 20 or not all(isinstance(x, str) and len(x) < 3000 for x in plan[name]):
            raise ValueError(f"Proposal needs a list of {name}.")
    if not plan["features"]:
        raise ValueError("The proposal must list at least one feature.")
    def coverage(items, label):
        covered = set()
        for item in items:
            indexes = item.get("feature_indexes")
            if not isinstance(indexes, list) or not all(type(i) is int and 0 <= i < len(plan["features"]) for i in indexes):
                raise ValueError(f"Each {label} needs feature_indexes listing the feature numbers it covers (starting at 0).")
            covered.update(indexes)
        missing = set(range(len(plan["features"]))) - covered
        if missing:
            raise ValueError(f"Every feature needs {label} coverage. Missing feature indexes: {sorted(missing)}.")
    tasks = plan.get("tasks")
    if not isinstance(tasks, list) or not 1 <= len(tasks) <= 8:
        raise ValueError("Proposal must contain 1–8 ordered tasks.")
    for task in tasks:
        if not isinstance(task, dict) or not all(isinstance(task.get(k), str) and 0 < len(task[k]) <= 6000 for k in ("title", "instructions")):
            raise ValueError("Each task needs a title and instructions.")
    coverage(tasks, "task")
    checks = plan.get("checks")
    if not isinstance(checks, list) or not 1 <= len(checks) <= 15:
        raise ValueError("Proposal must contain 1–15 behavioral HTTP checks.")
    behavior = False
    for check in checks:
        if not isinstance(check, dict):
            raise ValueError("Each check must be an object.")
        path = check.get("path", "")
        if not isinstance(path, str) or not path.startswith("/") or path.startswith("//") or any(c in path for c in "\r\n\\#") or len(path) > 1000:
            raise ValueError("Checks must use local URL paths.")
        if check.get("method") not in {"GET", "POST", "PUT", "DELETE", "PATCH"}:
            raise ValueError("Unsupported HTTP check method.")
        if not isinstance(check.get("name"), str) or not check["name"]:
            raise ValueError("Every check needs a name.")
        if type(check.get("status")) is not int or not 100 <= check["status"] <= 599:
            raise ValueError("Every check needs an expected HTTP status.")
        has_contains = isinstance(check.get("contains"), str) and bool(check["contains"])
        has_json = isinstance(check.get("json_contains"), (dict, list)) and bool(check["json_contains"])
        has_equals = "json_equals" in check
        if not (has_contains or has_json or has_equals):
            raise ValueError("Every check needs contains, nonempty json_contains, or json_equals.")
        if "contains" in check and not has_contains or "json_contains" in check and not has_json:
            raise ValueError("Invalid response assertion.")
        if path.split("?")[0] not in {"/", "/health"}:
            behavior = True
    if not behavior:
        raise ValueError("Add a check of actual app behavior beyond / and /health.")
    coverage(checks, "acceptance check")
    if len(json.dumps(plan)) > 30000:
        raise ValueError("Proposal too large. Narrow the scope.")
    return plan


def preflight(files, complete=True):
    return inspect_files(files, complete=complete)


def safe_file(root, name):
    if not isinstance(name, str) or len(name) > 160 or "\\" in name or ":" in name:
        raise ValueError("Invalid generated filename.")
    parts = PurePosixPath(name).parts
    if not parts or PurePosixPath(name).is_absolute() or any(p.startswith(".") or p.endswith((" ", ".")) for p in parts):
        raise ValueError("Hidden files, absolute paths and parent paths are forbidden.")
    reserved = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
    if any(p.split(".")[0].upper() in reserved or not re.fullmatch(r"[A-Za-z0-9_. -]+", p) for p in parts):
        raise ValueError("Filename is not portable to Windows.")
    if Path(name).suffix.lower() not in {".py", ".html", ".css", ".js", ".json", ".txt", ".md"}:
        raise ValueError("Only source and text files are supported.")
    target = root.joinpath(*parts)
    if any(p.is_symlink() for p in [target, *target.parents]) or not target.resolve().is_relative_to(root.resolve()):
        raise ValueError("File escapes the project directory.")
    return target


class Workbench:
    def __init__(self, root, client_factory=ModelClient, verifier=verify):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.client_factory, self.verifier = client_factory, verifier
        self.lock = threading.RLock()
        self.inference_lock = threading.Lock()
        self.jobs = {}
        self.warnings = []
        for path in self.root.glob("*/state.json"):
            try:
                state = self.load(path.parent.name)
            except (ValueError, OSError):
                self.warnings.append(f"Could not read project {path.parent.name}. Its files were preserved. Restore from a workspace backup.")
                continue
            if not (path.parent / "source").exists():
                recoverable = sorted(path.parent.glob(".source-before-*"), key=lambda p: p.stat().st_mtime, reverse=True)
                if recoverable:
                    os.replace(recoverable[0], path.parent / "source")
                    self.warnings.append(f"Recovered project {state['title']} after an interrupted file update. Original source was restored.")
            if state.get("status") in ACTIVE:
                state["status"] = "interrupted"
                state["events"].append({"time": self.now(), "message": "Workbench restarted. Resume to continue from the last saved task."})
                self.save(state)

    @staticmethod
    def now():
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def directory(self, ident):
        if not re.fullmatch(r"[a-f0-9]{32}", ident):
            raise ValueError("Invalid project ID.")
        return self.root / ident

    def load(self, ident):
        with self.lock:
            try:
                state = json.loads((self.directory(ident) / "state.json").read_text(encoding="utf-8"))
                if not isinstance(state, dict) or state.get("id") != ident or not all(isinstance(state.get(k), str) for k in ("status", "created", "title")) or not isinstance(state.get("events"), list):
                    raise ValueError("Project metadata is invalid. Original files were preserved.")
                return state
            except FileNotFoundError:
                raise ValueError("Project not found.") from None
            except json.JSONDecodeError:
                raise ValueError("Project metadata is damaged. Original files were preserved; restore from a backup.") from None

    def save(self, state):
        with self.lock:
            path = self.directory(state["id"])
            path.mkdir(exist_ok=True)
            state["schema_version"] = 2
            state["updated"] = self.now()
            temporary = path / ("state-" + uuid.uuid4().hex + ".tmp")
            temporary.write_text(json.dumps(state, indent=2), encoding="utf-8")
            os.replace(temporary, path / "state.json")

    def event(self, state, message):
        state["events"].append({"time": self.now(), "message": message})
        state["events"] = state["events"][-300:]
        self.save(state)

    def list_projects(self):
        with self.lock:
            states = []
            for path in self.root.glob("*/state.json"):
                try:
                    states.append(self.load(path.parent.name))
                except (ValueError, OSError):
                    continue
        return sorted(states, key=lambda p: p["created"], reverse=True)

    def call_model(self, state, role, system, prompt, cancel):
        """One inference at a time avoids loading competing local models."""
        previous = state["status"]
        if not self.inference_lock.acquire(blocking=False):
            state["status"] = "queued"
            self.event(state, "Waiting for the other model request to finish. You can stop this queued job.")
            while not self.inference_lock.acquire(timeout=0.2):
                if cancel.is_set():
                    raise InterruptedError("Stopped while waiting for a model.")
        started = time.monotonic()
        record = {"role": role, **state[role], "time": self.now(), "success": False}
        try:
            if cancel.is_set():
                raise InterruptedError("Stopped before model inference.")
            state["status"] = previous
            self.save(state)
            result = self.client(state, role).complete(system, prompt)
            record["success"] = True
            return result
        finally:
            record["seconds"] = round(time.monotonic() - started, 2)
            state.setdefault("model_calls", []).append(record)
            state["model_calls"] = state["model_calls"][-100:]
            try:
                self.save(state)
            finally:
                self.inference_lock.release()

    def configure_models(self, ident, planner, coder):
        with self.lock:
            state = self.load(ident)
            if state["status"] in ACTIVE:
                raise ValueError("Wait for or stop the running job before changing models.")
            for config in (planner, coder):
                ModelClient(config["provider"], config["model"])
                if config["provider"] == "ollama" and "embed" in config["model"].lower():
                    raise ValueError("Embedding models cannot plan or write apps. Choose a chat/coding model.")
            state.update(planner=planner, coder=coder)
            self.event(state, "Model choices updated. Project files and approved requirements were kept.")
            return state

    def fork(self, ident, request):
        with self.lock:
            parent = self.load(ident)
            if parent["status"] in ACTIVE or not parent["approved"]:
                raise ValueError("Finish or stop an approved project before requesting a change.")
            if not isinstance(request, str) or not 10 <= len(request.strip()) <= 6000:
                raise ValueError("Describe the change in 10–6000 characters.")
            state = copy.deepcopy(parent)
            state.update(id=uuid.uuid4().hex, parent_id=ident, parent_title=parent["title"],
                         change_request=request.strip(), baseline_plan=copy.deepcopy(parent["plan"]),
                         frozen_tests={name: hashlib.sha256(text.encode()).hexdigest() for name, text in self.context_files(ident).items() if Path(name).name.startswith("test_") and name.endswith(".py")},
                         title=parent["title"] + " · change", created=self.now(), status="draft", approved=False,
                         plan=None, next_task=0, events=[], snapshots=[], checks=None, preflight=None, model_calls=[], milestones=[], repair_count=0)
            target = self.directory(state["id"]) / "source"
            target.mkdir(parents=True)
            for name, content in self.files(ident).items():
                path = target / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
            state["baseline_frozen_tests"] = copy.deepcopy(state["frozen_tests"])
            self.save(state)
            self.start(state["id"], "plan", {})
            return self.load(state["id"])

    @staticmethod
    def revision_plan(state, plan):
        plan = copy.deepcopy(plan)
        baseline = state.get("baseline_plan")
        if baseline:
            if plan.get("features", [])[:len(baseline["features"])] != baseline["features"]:
                raise ValueError("A change must preserve the original features in their original order, then append new features.")
            for check in baseline["checks"]:
                original = {**check, "feature_indexes": check.get("feature_indexes", [])}
                if original not in plan.get("checks", []):
                    plan.setdefault("checks", []).append(original)
        return validate_plan(plan)

    def backup(self):
        with self.lock:
            if any(thread.is_alive() for thread, _ in self.jobs.values()):
                raise ValueError("Wait for or stop all jobs before backing up a consistent workspace.")
            stream = io.BytesIO()
            total = 0
            with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(self.root.rglob("*")):
                    relative = path.relative_to(self.root)
                    if not path.is_file() or any(p.is_symlink() for p in [path, *path.parents]) or any(p.startswith(".") for p in relative.parts) or "__pycache__" in relative.parts or path.suffix in {".pyc", ".tmp"}:
                        continue
                    total += path.stat().st_size
                    if total > 100_000_000:
                        raise ValueError("Workspace exceeds the 100 MB browser-backup limit. Copy the data folder using your file manager.")
                    archive.write(path, "projects/" + relative.as_posix())
                archive.writestr("BACKUP-README.txt", "Idea Foundry workspace backup. Stop Foundry, extract projects/ into your data folder, then restart. Back up the current folder before restoring. API keys and .env files are intentionally excluded.\n")
            return stream.getvalue()

    def diff(self, ident):
        state = self.load(ident)
        if state["status"] in ACTIVE:
            raise ValueError("Wait until the job stops before reviewing changes.")
        current = self.files(ident)
        before = {}
        if state["snapshots"]:
            root = self.directory(ident) / "snapshots" / state["snapshots"][-1]["id"]
            for name in current:
                path = root / name
                if path.is_file() and not any(p.is_symlink() for p in [path, *path.parents]):
                    before[name] = path.read_text(encoding="utf-8")
        result = []
        for name, content in current.items():
            if before.get(name) != content:
                lines = difflib.unified_diff(before.get(name, "").splitlines(), content.splitlines(), fromfile="before/" + name, tofile="after/" + name, lineterm="")
                result.append({"name": name, "kind": "modified" if name in before else "added", "diff": "\n".join(lines)[:20000]})
        return result

    def create(self, idea, planner, coder):
        if not isinstance(idea, str) or not 10 <= len(idea.strip()) <= 12000:
            raise ValueError("Describe your idea in 10–12000 characters.")
        for config in (planner, coder):
            self.client_factory(config["provider"], config["model"])
        ident = uuid.uuid4().hex
        state = {"id": ident, "idea": idea.strip(), "title": "New project", "created": self.now(),
                 "status": "draft", "planner": planner, "coder": coder, "plan": None,
                 "approved": False, "next_task": 0, "events": [], "checks": None,
                 "snapshots": [], "repair_count": 0}
        (self.directory(ident) / "source").mkdir(parents=True)
        self.save(state)
        self.start(ident, "plan", {})
        return self.load(ident)

    def client(self, state, role):
        config = state[role]
        return self.client_factory(config["provider"], config["model"])

    def start(self, ident, action, options):
        with self.lock:
            state = self.load(ident)
            existing = self.jobs.get(ident)
            if existing and existing[0].is_alive():
                raise ValueError("A job is already running for this project.")
            if action not in {"plan", "build"}:
                raise ValueError("Unknown job action.")
            if action == "build" and not state["approved"]:
                raise ValueError("Approve the proposal first.")
            if action == "plan" and state["approved"]:
                raise ValueError("An approved proposal is frozen. Create another project for a new scope.")
            mode = options.get("runtime", "docker")
            execute = options.get("execute", False) is True
            if mode not in {"docker", "local"}:
                raise ValueError("Unknown execution runtime.")
            if execute and options.get("consent") is not True:
                raise ValueError("Explicit execution consent is required.")
            if state["status"] == "verified" and not state.get("frozen_tests"):
                state["frozen_tests"] = {name: hashlib.sha256(text.encode()).hexdigest() for name, text in self.context_files(ident).items() if Path(name).name.startswith("test_") and name.endswith(".py")}
            attempts = options.get("repairs", 2)
            if type(attempts) is not int or not 0 <= attempts <= 3:
                raise ValueError("Repair limit must be between 0 and 3.")
            state["status"] = "planning" if action == "plan" else "building"
            state["error"] = None
            self.save(state)
            cancel = threading.Event()
            thread = threading.Thread(target=self._job, args=(state, action, options, cancel), daemon=True)
            self.jobs[ident] = (thread, cancel)
            thread.start()

    def stop(self, ident):
        with self.lock:
            job = self.jobs.get(ident)
            if job:
                job[1].set()
        return {"message": "Stop requested. An in-flight model request can take up to five minutes to finish; its output will be discarded."}

    def approve(self, ident, plan):
        with self.lock:
            state = self.load(ident)
            if state["status"] in ACTIVE or state["approved"]:
                raise ValueError("Cannot change this proposal while a job runs or after approval.")
            state["plan"] = self.revision_plan(state, plan)
            plan = state["plan"]
            state["title"] = plan["title"]
            state["approved"], state["status"] = True, "approved"
            self.documents(state)
            self.event(state, "Proposal approved. Requirements and acceptance checks frozen.")
            return state

    def documents(self, state):
        source = self.directory(state["id"]) / "source"
        plan = state["plan"]
        (source / "PROJECT.md").write_text("# " + plan["title"] + "\n\n" + plan["summary"] + "\n\n## Approved requirements\n\n" + json.dumps(plan, indent=2), encoding="utf-8")
        (source / "TASKS.md").write_text("# Build tasks\n\n" + "\n".join(f'{i+1}. {t["title"]}\n   {t["instructions"]}' for i, t in enumerate(plan["tasks"])), encoding="utf-8")
        (source / "CHECKS.json").write_text(json.dumps(plan["checks"], indent=2), encoding="utf-8")
        (source / "README.md").write_text(f'# {plan["title"]}\n\n{plan["summary"]}\n\nRequires Python 3.11+. No third-party packages.\n\nRun `python app.py --host 127.0.0.1 --port 8080`, then open http://127.0.0.1:8080.\nOn Windows you can double-click run.bat.\n\nAI-generated code: review it before running. See PROJECT.md for the agreed scope and CHECKS.json for acceptance checks.\nPassing checks is evidence of the tested behaviors, not a guarantee of all requirements.\n', encoding="utf-8")
        (source / "launch.py").write_text(Path(__file__).with_name("launch_template.py").read_text(encoding="utf-8"), encoding="utf-8")
        (source / "run.bat").write_text('@echo off\r\ncd /d "%~dp0"\r\nwhere py >nul 2>&1\r\nif %errorlevel% equ 0 (\r\n    py -3 launch.py\r\n) else (\r\n    python launch.py\r\n)\r\npause\r\n', encoding="utf-8")
        (source / "run.sh").write_text('#!/bin/sh\ncd "$(dirname "$0")" || exit 1\nexec python3 launch.py\n', encoding="utf-8")
        with (source / "README.md").open("a", encoding="utf-8") as readme:
            readme.write("\nThe launch scripts wait for the app to become ready and open your browser. If port 8080 is busy, the launcher chooses another free port and prints the address. Keep its terminal open.\n")

    def files(self, ident):
        root = self.directory(ident) / "source"
        files = {}
        for path in sorted(root.rglob("*")):
            relative = path.relative_to(root)
            if not path.is_file() or any(p.startswith(".") or p == "__pycache__" for p in relative.parts):
                continue
            if path.suffix.lower() not in {".py", ".html", ".css", ".js", ".json", ".txt", ".md", ".bat", ".sh"}:
                continue
            if any(p.is_symlink() for p in [path, *path.parents]):
                continue
            if path.stat().st_size > 1_000_000:
                raise ValueError("A project file exceeds the 1 MB inspection limit.")
            files[relative.as_posix()] = path.read_text(encoding="utf-8")
        return files

    def context_files(self, ident):
        return {name: content for name, content in self.files(ident).items() if name.lower() not in OWNED}

    def checkpoint(self, state, label):
        number = uuid.uuid4().hex
        target = self.directory(state["id"]) / "snapshots" / number
        shutil.copytree(self.directory(state["id"]) / "source", target)
        state["snapshots"].append({"id": number, "label": label, "next_task": state["next_task"], "frozen_tests": copy.deepcopy(state.get("frozen_tests", {}))})
        self.save(state)

    def _swap_source(self, ident, prepared):
        root = self.directory(ident) / "source"
        previous = root.with_name(".source-before-" + uuid.uuid4().hex)
        os.replace(root, previous)
        try:
            os.replace(prepared, root)
        except BaseException:
            os.replace(previous, root)
            raise
        shutil.rmtree(previous)

    def restore(self, ident, snapshot):
        with self.lock:
            state = self.load(ident)
            if state["status"] in ACTIVE:
                raise ValueError("Stop the current job before restoring.")
            match = next((s for s in state["snapshots"] if s["id"] == snapshot), None)
            if not match:
                raise ValueError("Checkpoint not found.")
            source = self.directory(ident) / "source"
            self.checkpoint(state, "Backup before manual restore")
            staging = source.with_name(".restore-" + uuid.uuid4().hex)
            try:
                shutil.copytree(self.directory(ident) / "snapshots" / snapshot, staging)
                self._swap_source(ident, staging)
            finally:
                if staging.exists():
                    shutil.rmtree(staging)
            state.update(next_task=match["next_task"], status="approved", checks=None, preflight=None, frozen_tests=copy.deepcopy(match.get("frozen_tests", state.get("baseline_frozen_tests", state.get("frozen_tests", {}) if state.get("baseline_plan") else {}))))
            self.event(state, "Restored checkpoint: " + match["label"])
            return state

    def apply(self, state, response, repair=False):
        files = response.get("files")
        if not isinstance(files, dict) or not 1 <= len(files) <= 24:
            raise ValueError("Model must return 1–24 complete source files.")
        root = self.directory(state["id"]) / "source"
        current = self.files(state["id"])
        targets, normalized = [], set()
        for name, content in files.items():
            target = safe_file(root, name)
            lower = name.lower()
            if lower in normalized or any(n.lower() == lower and n != name for n in current):
                raise ValueError("Case-colliding filenames are not portable to Windows.")
            normalized.add(lower)
            if lower in OWNED:
                raise ValueError("Model attempted to modify frozen documentation or acceptance checks.")
            if not isinstance(content, str) or len(content) > 40000:
                raise ValueError("Generated file is too large or not text.")
            if name in state.get("frozen_tests", {}) and hashlib.sha256(content.encode()).hexdigest() != state["frozen_tests"][name]:
                raise ValueError("Existing app tests are trusted regression tests and cannot be rewritten. Add new tests in another file.")
            targets.append((target, content))
        if sum(len(v) for v in (current | files).values()) > 70000:
            raise ValueError("Project exceeded the small-model context budget. Narrow the scope.")
        if sum(len(v) for k, v in (current | files).items() if k.lower() not in OWNED) > 36000:
            raise ValueError("Source exceeded the local-model context budget. Narrow the scope or split the app.")
        # All names and contents are validated before any file is written.
        if any(path.is_symlink() for path in root.rglob("*")):
            raise ValueError("Remove symbolic links from this project before model file updates.")
        self.checkpoint(state, "Before " + ("repair" if repair else f'task {state["next_task"] + 1}'))
        staging = root.with_name(".source-update-" + uuid.uuid4().hex)
        try:
            shutil.copytree(root, staging)
            for target, content in targets:
                prepared = staging / target.relative_to(root)
                prepared.parent.mkdir(parents=True, exist_ok=True)
                prepared.write_text(content, encoding="utf-8")
            self._swap_source(state["id"], staging)
        finally:
            if staging.exists():
                shutil.rmtree(staging)
        self.event(state, str(response.get("summary", "Source files updated."))[:2000])

    def _inspect_and_repair(self, state, cancel, remaining, complete=True):
        for attempt in range(remaining + 1):
            if cancel.is_set():
                raise InterruptedError("Stopped before static inspection.")
            state["preflight"] = preflight(self.context_files(state["id"]), complete=complete)
            current = self.context_files(state["id"])
            trusted_issues = []
            for name, expected in state.get("frozen_tests", {}).items():
                if name not in current or hashlib.sha256(current[name].encode()).hexdigest() != expected:
                    trusted_issues.append("Trusted regression test was changed or removed: " + name + ". Restore its checkpoint before continuing.")
            state["preflight"]["issues"].extend(trusted_issues)
            state["preflight"]["passed"] = not state["preflight"]["issues"]
            self.save(state)
            if trusted_issues:
                state["status"] = "needs_attention"
                self.event(state, "\n".join(trusted_issues))
                return None
            if state["preflight"]["passed"]:
                return remaining
            issues = "\n".join(state["preflight"]["issues"])
            if remaining == 0:
                state["status"] = "needs_attention"
                self.event(state, "Static inspection found incomplete code. No code was executed.\n" + issues)
                return None
            state["status"] = "repairing"
            self.event(state, f"Static repair {attempt+1}: correcting syntax/structure or adding missing tests without executing code.\n" + issues)
            response = self.call_model(state, "coder", CODE, json.dumps({"proposal": state["plan"], "files": self.context_files(state["id"]), "failure": issues, "frozen_tests": list(state.get("frozen_tests", {})), "instruction": "Repair source syntax/structure. Add missing behavioral unittest files. Approved checks and frozen_tests are immutable. Repair unverified test files when necessary: import the real app and make actual HTTP requests. Implement every approved feature."}), cancel)
            if cancel.is_set():
                raise InterruptedError("Stopped. Static repair output discarded.")
            self.apply(state, response, repair=True)
            state["repair_count"] += 1
            remaining -= 1

    def _job(self, state, action, options, cancel):
        try:
            if action == "plan":
                self.event(state, "Planning with " + state["planner"]["provider"] + "/" + state["planner"]["model"])
                revision = options.get("revision", "")
                if not isinstance(revision, str) or len(revision) > 6000:
                    raise ValueError("Revision must be under 6000 characters.")
                request = {"idea": state["idea"], "revision": revision, "previous_proposal": state["plan"],
                           "existing_project": state.get("baseline_plan"), "change_request": state.get("change_request"),
                           "instruction": "For changes, preserve original features in order, append new ones, and plan only work needed for the change. Original checks and existing tests must still pass."}
                for attempt in range(2):
                    plan = self.call_model(state, "planner", PLAN, json.dumps(request), cancel)
                    if cancel.is_set():
                        raise InterruptedError("Stopped. Model output discarded.")
                    try:
                        plan = self.revision_plan(state, plan)
                        break
                    except ValueError as exc:
                        if attempt:
                            raise
                        request.update(previous_proposal=plan, validation_error=str(exc))
                        self.event(state, "Proposal incomplete; asking the planner to correct task/check coverage: " + str(exc))
                state.update(plan=plan, title=plan["title"], status="proposed")
                self.event(state, "Proposal ready. Review the scope, tasks, and behavioral checks before approval.")
                return
            if state.get("baseline_plan") and "baseline_frozen_tests" not in state:
                state["baseline_frozen_tests"] = copy.deepcopy(state.get("frozen_tests", {}))
            if options.get("execute"):
                require_runtime(options.get("runtime", "docker"))
            state["checks"] = None
            state["preflight"] = None
            remaining_repairs = options.get("repairs", 2)
            for index in range(state["next_task"], len(state["plan"]["tasks"])):
                if cancel.is_set():
                    raise InterruptedError("Build stopped. You can resume from the next unfinished task.")
                task = state["plan"]["tasks"][index]
                self.event(state, f'Task {index+1}: {task["title"]}')
                response = self.call_model(state, "coder", CODE, json.dumps({"proposal": state["plan"], "current_task": task, "is_final_task": index == len(state["plan"]["tasks"]) - 1, "files": self.context_files(state["id"]), "frozen_tests": list(state.get("frozen_tests", {}))}), cancel)
                if cancel.is_set():
                    raise InterruptedError("Stopped. Model output discarded.")
                self.apply(state, response)
                remaining_repairs = self._inspect_and_repair(state, cancel, remaining_repairs, complete=False)
                if remaining_repairs is None:
                    return
                state["status"] = "building"
                state.setdefault("milestones", []).append({"task": index + 1, "title": task["title"], "syntax_passed": True, "behavior_verified": False, "time": self.now()})
                state["next_task"] = index + 1
                self.save(state)
            # Repairs here are text-only model calls. No generated code is run.
            remaining_repairs = self._inspect_and_repair(state, cancel, remaining_repairs)
            if remaining_repairs is None:
                return
            if not options.get("execute"):
                state["status"] = "generated"
                self.event(state, "Source and test files generated; static syntax/structure checks passed. The app has NOT run or been verified. Approve execution for behavioral checks.")
                return
            runtime_repairs = remaining_repairs
            for attempt in range(runtime_repairs + 1):
                if cancel.is_set():
                    raise InterruptedError("Verification stopped.")
                state["status"] = "checking"
                self.event(state, "Running generated tests and frozen HTTP acceptance checks.")
                result = self.verifier(self.directory(state["id"]) / "source", options.get("runtime", "docker"), cancel)
                state["checks"] = result
                self.save(state)
                if cancel.is_set():
                    raise InterruptedError("Verification stopped.")
                if result["passed"]:
                    state["frozen_tests"] = {name: hashlib.sha256(text.encode()).hexdigest() for name, text in self.context_files(state["id"]).items() if Path(name).name.startswith("test_") and name.endswith(".py")}
                    state["status"] = "verified"
                    self.event(state, "Tests and HTTP acceptance checks passed. Download and try the app; review remaining requirements yourself.")
                    return
                if result.get("failure_kind") == "environment":
                    state["status"] = "needs_attention"
                    self.event(state, "Execution environment failed. Fix the Docker/runtime error below before retrying; application code was not sent for repair.")
                    return
                if attempt == runtime_repairs:
                    state["status"] = "needs_attention"
                    self.event(state, "Checks failed. Repair limit reached; inspect the output and files.")
                    return
                state["status"] = "repairing"
                self.event(state, f'Repair attempt {attempt+1}; approved checks and trusted regression tests remain frozen. New unverified tests may be corrected.')
                response = self.call_model(state, "coder", CODE, json.dumps({"proposal": state["plan"], "files": self.context_files(state["id"]), "failure": result["log"][-12000:], "diagnosis": result.get("diagnosis"), "frozen_tests": list(state.get("frozen_tests", {})), "instruction": "Repair the application and, if faulty, unverified test files. Never edit frozen_tests or approved checks. Test the actual imported app, send HTTP requests with timeouts, and preserve every approved feature."}), cancel)
                if cancel.is_set():
                    raise InterruptedError("Stopped. Repair output discarded.")
                self.apply(state, response, repair=True)
                state["repair_count"] += 1
        except InterruptedError as exc:
            state["status"] = "stopped"
            self.event(state, str(exc))
        except Exception as exc:
            state["status"], state["error"] = "error", str(exc)[:2000]
            self.event(state, "Stopped with error: " + state["error"])
