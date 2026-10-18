"""Persistent projects and a deliberately bounded plan/build/check/repair state machine."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import threading
import uuid

from .models import ModelClient
from .prompts import PLAN, CODE
from .runner import verify

OWNED = {"readme.md", "project.md", "tasks.md", "checks.json", "run.bat", "run.sh"}
ACTIVE = {"planning", "building", "checking", "repairing"}


def validate_plan(plan):
    for name in ("title", "summary"):
        if not isinstance(plan.get(name), str) or not plan[name].strip() or len(plan[name]) > 6000:
            raise ValueError(f"Proposal needs a nonempty {name} (up to 6000 characters).")
    for name in ("features", "out_of_scope", "risks"):
        if not isinstance(plan.get(name), list) or len(plan[name]) > 20 or not all(isinstance(x, str) and len(x) < 3000 for x in plan[name]):
            raise ValueError(f"Proposal needs a list of {name}.")
    tasks = plan.get("tasks")
    if not isinstance(tasks, list) or not 1 <= len(tasks) <= 8:
        raise ValueError("Proposal must contain 1–8 ordered tasks.")
    for task in tasks:
        if not isinstance(task, dict) or not all(isinstance(task.get(k), str) and 0 < len(task[k]) <= 6000 for k in ("title", "instructions")):
            raise ValueError("Each task needs a title and instructions.")
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
        has_json = isinstance(check.get("json_contains"), dict) and bool(check["json_contains"])
        if not (has_contains or has_json):
            raise ValueError("Every check must assert a nonempty contains or json_contains value.")
        if "contains" in check and not has_contains or "json_contains" in check and not has_json:
            raise ValueError("Invalid response assertion.")
        if path.split("?")[0] not in {"/", "/health"}:
            behavior = True
    if not behavior:
        raise ValueError("Add a check of actual app behavior beyond / and /health.")
    if len(json.dumps(plan)) > 30000:
        raise ValueError("Proposal too large. Narrow the scope.")
    return plan


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
        self.jobs = {}
        for path in self.root.glob("*/state.json"):
            state = json.loads(path.read_text(encoding="utf-8"))
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
                return json.loads((self.directory(ident) / "state.json").read_text(encoding="utf-8"))
            except FileNotFoundError:
                raise ValueError("Project not found.") from None

    def save(self, state):
        with self.lock:
            path = self.directory(state["id"])
            path.mkdir(exist_ok=True)
            temporary = path / "state.tmp"
            temporary.write_text(json.dumps(state, indent=2), encoding="utf-8")
            os.replace(temporary, path / "state.json")

    def event(self, state, message):
        state["events"].append({"time": self.now(), "message": message})
        state["events"] = state["events"][-300:]
        self.save(state)

    def list_projects(self):
        with self.lock:
            states = [json.loads(p.read_text(encoding="utf-8")) for p in self.root.glob("*/state.json")]
        return sorted(states, key=lambda p: p["created"], reverse=True)

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
            state["plan"] = validate_plan(plan)
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
        (source / "run.bat").write_text('@echo off\r\ncd /d "%~dp0"\r\npython app.py --host 127.0.0.1 --port 8080\r\npause\r\n', encoding="utf-8")
        (source / "run.sh").write_text('#!/bin/sh\ncd "$(dirname "$0")"\nexec python3 app.py --host 127.0.0.1 --port 8080\n', encoding="utf-8")

    def files(self, ident):
        root = self.directory(ident) / "source"
        return {str(p.relative_to(root)).replace(os.sep, "/"): p.read_text(encoding="utf-8") for p in sorted(root.rglob("*")) if p.is_file() and not p.is_symlink() and "__pycache__" not in p.parts}

    def context_files(self, ident):
        return {name: content for name, content in self.files(ident).items() if name.lower() not in OWNED}

    def checkpoint(self, state, label):
        number = uuid.uuid4().hex
        target = self.directory(state["id"]) / "snapshots" / number
        shutil.copytree(self.directory(state["id"]) / "source", target)
        state["snapshots"].append({"id": number, "label": label, "next_task": state["next_task"]})
        self.save(state)

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
            shutil.rmtree(source)
            shutil.copytree(self.directory(ident) / "snapshots" / snapshot, source)
            state.update(next_task=match["next_task"], status="approved", checks=None)
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
            if lower in OWNED or repair and (target.name.startswith("test_") or target.name.endswith("_test.py")):
                raise ValueError("Model attempted to modify frozen documentation, acceptance checks, or repair-time tests.")
            if not isinstance(content, str) or len(content) > 40000:
                raise ValueError("Generated file is too large or not text.")
            targets.append((target, content))
        if sum(len(v) for v in (current | files).values()) > 70000:
            raise ValueError("Project exceeded the small-model context budget. Narrow the scope.")
        if sum(len(v) for k, v in (current | files).items() if k.lower() not in OWNED) > 36000:
            raise ValueError("Source exceeded the local-model context budget. Narrow the scope or split the app.")
        # All names and contents are validated before any file is written.
        self.checkpoint(state, "Before " + ("repair" if repair else f'task {state["next_task"] + 1}'))
        for target, content in targets:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        self.event(state, str(response.get("summary", "Source files updated."))[:2000])

    def _job(self, state, action, options, cancel):
        try:
            if action == "plan":
                self.event(state, "Planning with " + state["planner"]["provider"] + "/" + state["planner"]["model"])
                revision = options.get("revision", "")
                if not isinstance(revision, str) or len(revision) > 6000:
                    raise ValueError("Revision must be under 6000 characters.")
                plan = self.client(state, "planner").complete(PLAN, json.dumps({"idea": state["idea"], "revision": revision, "previous_proposal": state["plan"]}))
                if cancel.is_set():
                    raise InterruptedError("Stopped. Model output discarded.")
                state.update(plan=validate_plan(plan), title=plan["title"], status="proposed")
                self.event(state, "Proposal ready. Review the scope, tasks, and behavioral checks before approval.")
                return
            state["checks"] = None
            for index in range(state["next_task"], len(state["plan"]["tasks"])):
                if cancel.is_set():
                    raise InterruptedError("Build stopped. You can resume from the next unfinished task.")
                task = state["plan"]["tasks"][index]
                self.event(state, f'Task {index+1}: {task["title"]}')
                response = self.client(state, "coder").complete(CODE, json.dumps({"proposal": state["plan"], "current_task": task, "files": self.context_files(state["id"])}))
                if cancel.is_set():
                    raise InterruptedError("Stopped. Model output discarded.")
                self.apply(state, response)
                state["next_task"] = index + 1
                self.save(state)
            if not options.get("execute"):
                state["status"] = "generated"
                self.event(state, "Code generated. Not executed or verified. Approve execution to run checks and repairs.")
                return
            for attempt in range(options.get("repairs", 2) + 1):
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
                    state["status"] = "verified"
                    self.event(state, "Tests and HTTP acceptance checks passed. Download and try the app; review remaining requirements yourself.")
                    return
                if attempt == options.get("repairs", 2):
                    state["status"] = "needs_attention"
                    self.event(state, "Checks failed. Repair limit reached; inspect the output and files.")
                    return
                state["status"] = "repairing"
                self.event(state, f'Repair attempt {attempt+1}; approved checks and generated test files remain frozen.')
                response = self.client(state, "coder").complete(CODE, json.dumps({"proposal": state["plan"], "files": self.context_files(state["id"]), "failure": result["log"][-12000:], "instruction": "Fix application source only. Do not edit test files or weaken approved checks."}))
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
