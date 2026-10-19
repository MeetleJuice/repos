"""Independent acceptance, generated-test, and launch phases in disposable copies."""
from __future__ import annotations

import argparse
from html.parser import HTMLParser
import importlib.util
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import unittest
from typing import Any
import urllib.error
import urllib.request
from urllib.parse import urljoin, urlsplit

MARKER = "FOUNDRY_PHASE_REPORT "


def subset(actual, expected):
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(k in actual and subset(actual[k], v) for k, v in expected.items())
    if isinstance(expected, list):
        return isinstance(actual, list) and all(any(subset(item, wanted) for item in actual) for wanted in expected)
    if isinstance(actual, bool) or isinstance(expected, bool):
        return actual is expected
    return actual == expected


class Assets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.paths = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        path = attrs.get("src") if tag in {"script", "img"} else attrs.get("href") if tag == "link" and "stylesheet" in attrs.get("rel", "") else None
        if path and not path.startswith(("data:", "#")):
            self.paths.append(path)


def fetch(base, check):
    body = json.dumps(check["body"]).encode() if "body" in check else None
    req = urllib.request.Request(base + check["path"], data=body, method=check["method"], headers={"Content-Type": "application/json"})
    try:
        response = urllib.request.urlopen(req, timeout=5)
    except urllib.error.HTTPError as exc:
        response = exc
    with response:
        data = response.read(1_000_001)
        assert len(data) <= 1_000_000, "Response exceeded the 1 MB limit."
        text = data.decode("utf-8")
        assert response.code == check["status"], f'{check["name"]}: expected HTTP {check["status"]}, got {response.code}: {text[:1000]}'
        if check.get("empty_body"):
            assert not data, f'{check["name"]}: expected an empty response body.'
        if "contains" in check:
            assert check["contains"] in text, f'{check["name"]}: response missing {check["contains"]!r}'
        if "json_contains" in check:
            assert subset(json.loads(text), check["json_contains"]), f'{check["name"]}: unexpected JSON: {text[:1000]}'
        if "json_equals" in check:
            assert json.dumps(json.loads(text), sort_keys=True) == json.dumps(check["json_equals"], sort_keys=True), f'{check["name"]}: JSON response did not exactly match {check["json_equals"]!r}: {text[:1000]}'
        return text


def acceptance(root):
    spec = importlib.util.spec_from_file_location("foundry_generated_app", root / "app.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    server = module.create_server("127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = "http://127.0.0.1:" + str(server.server_address[1])
    checks = [
        {"name": "Health endpoint", "method": "GET", "path": "/health", "status": 200, "json_contains": {"status": "ok"}},
        {"name": "HTML interface", "method": "GET", "path": "/", "status": 200, "contains": "<"},
        *json.loads((root / "CHECKS.json").read_text(encoding="utf-8")),
    ]
    assets = set()
    restarts = 0
    process = None
    factory_running = True
    try:
        for check in checks:
            if check.get("restart_before"):
                if factory_running:
                    server.shutdown()
                    server.server_close()
                    thread.join(3)
                    assert not thread.is_alive(), "Previous server did not stop before persistence check."
                    factory_running = False
                if process is not None:
                    stop_app_process(process)
                    process = None
                process, base = start_app_process()
                restarts += 1
                print("RESTART: Previous server closed; independent app process started against the same data directory.", flush=True)
            try:
                text = fetch(base, check)
            except Exception as exc:
                if check.get("restart_before"):
                    raise AssertionError("Restart persistence check failed: " + str(exc)) from exc
                raise
            print("PASS:", check["name"], flush=True)
            if check["path"] == "/" and check["method"] == "GET":
                parser = Assets()
                parser.feed(text)
                assets.update(parser.paths)
        for asset in sorted(assets):
            url = urljoin(base + "/", asset)
            parsed = urlsplit(url)
            assert parsed.scheme == "http" and parsed.netloc == urlsplit(base).netloc, "External runtime assets are unsupported: " + asset
            path = parsed.path + ("?" + parsed.query if parsed.query else "")
            fetch(base, {"name": "Referenced asset " + asset, "method": "GET", "path": path, "status": 200})
            print("PASS: Referenced asset", asset, flush=True)
    finally:
        if process is not None:
            stop_app_process(process)
        if factory_running:
            server.shutdown()
            server.server_close()
            thread.join(3)
    return {"http_checks": len(checks), "asset_checks": len(assets), "server_restarts": restarts, "process_restarts": restarts}


def generated_tests(root):
    app_path = str(root / "app.py")
    calls = [0]
    def profile(frame, event, _arg):
        if event == "call" and frame.f_code.co_filename == app_path and frame.f_code.co_flags & 0x02:
            calls[0] += 1
    suite = unittest.defaultTestLoader.discover(str(root), pattern="test_*.py")
    sys.setprofile(profile)
    threading.setprofile(profile)
    try:
        result = unittest.TextTestRunner(verbosity=2).run(suite)
    finally:
        sys.setprofile(None)
        threading.setprofile(None)
    assert result.testsRun > 0 and result.wasSuccessful() and not result.skipped and not result.expectedFailures, "Generated tests must execute at least one test, with no failures, skips, or expected failures."
    assert calls[0] > 0, "Generated tests did not exercise app.py. Import and call the real application instead of testing a duplicate or a trivial assertion."
    return {"tests_run": result.testsRun, "app_calls": calls[0]}


def stop_app_process(proc: subprocess.Popen[bytes]) -> None:
    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=3)


def start_app_process() -> tuple[subprocess.Popen[bytes], str]:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    proc = subprocess.Popen([sys.executable, "-B", "app.py", "--host", "127.0.0.1", "--port", str(port)])
    base = f"http://127.0.0.1:{port}"
    try:
        deadline = time.monotonic() + 8
        while True:
            assert proc.poll() is None, "app.py exited before its launch command became ready."
            try:
                fetch(base, {"name": "Python launch command", "path": "/health", "method": "GET", "status": 200, "json_contains": {"status": "ok"}})
                return proc, base
            except (urllib.error.URLError, TimeoutError):
                assert time.monotonic() < deadline, "app.py launch command did not become ready within eight seconds."
                time.sleep(0.1)
    except BaseException:
        stop_app_process(proc)
        raise


def launch(_root):
    proc, _base = start_app_process()
    try:
        print("PASS: Python launch command", flush=True)
        return {"http_checks": 1}
    finally:
        stop_app_process(proc)


class PhaseInfrastructureError(RuntimeError):
    """The verifier workspace failed, rather than the application under test."""


def phase(name, source):
    previous = Path.cwd()
    previous_path = sys.path[:]
    try:
        workspace = tempfile.TemporaryDirectory(prefix="foundry-" + name + "-")
    except OSError as exc:
        raise PhaseInfrastructureError("Verifier workspace could not be created: " + str(exc)) from exc
    try:
        root = Path(workspace.name).resolve()
        try:
            shutil.copytree(source, root, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__", "*.db", "*.sqlite*"))
        except OSError as exc:
            raise PhaseInfrastructureError("Verifier workspace could not be prepared: " + str(exc)) from exc
        os.chdir(root)
        sys.path.insert(0, str(root))
        return {"phase": name, "passed": True, **{"acceptance": acceptance, "tests": generated_tests, "launch": launch}[name](root)}
    finally:
        # Windows cannot remove the process's current directory. Restore even when
        # application code or generated tests raise or change cwd/sys.path themselves.
        try:
            os.chdir(previous)
        except OSError as exc:
            raise PhaseInfrastructureError("Verifier could not restore its working directory: " + str(exc)) from exc
        finally:
            sys.path[:] = previous_path
            try:
                workspace.cleanup()
            except OSError as exc:
                raise PhaseInfrastructureError("Verifier workspace cleanup failed after testing: " + str(exc)) from exc


def _run_prepared_phase(name: str, source: Path, timeout: float) -> dict[str, Any]:
    print("PHASE:", name, flush=True)
    with tempfile.TemporaryFile() as output:
        proc = subprocess.Popen([sys.executable, "-B", str(Path(__file__).resolve()), str(source), "--phase", name, "--prepared"], stdout=output, stderr=subprocess.STDOUT)
        deadline = time.monotonic() + timeout
        reason = None
        while proc.poll() is None:
            if time.monotonic() >= deadline:
                reason = name + " phase exceeded its time limit."
            elif os.fstat(output.fileno()).st_size > 2_000_000:
                reason = name + " phase exceeded its output limit."
            if reason:
                if os.name == "nt":
                    subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, timeout=10)
                else:
                    proc.kill()
                break
            time.sleep(0.05)
        proc.wait(timeout=10)
        output.seek(0)
        log = output.read(2_000_000).decode("utf-8", errors="replace")
    print(log[-24000:], flush=True)
    if reason:
        return {"phase": name, "passed": False, "error": reason, "timed_out": "time limit" in reason}
    try:
        last = log.strip().splitlines()[-1]
        report = json.loads(last.removeprefix(MARKER)) if last.startswith(MARKER) else {}
        if report.get("phase") == name and ((proc.returncode == 0 and report.get("passed") is True) or (proc.returncode != 0 and report.get("passed") is False)):
            return report
    except (ValueError, IndexError, AttributeError):
        pass
    return {"phase": name, "passed": False, "error": log[-16000:] or "Phase produced no completion report; a zero exit code alone is insufficient."}


def prepared_phase(name: str, root: Path) -> dict[str, Any]:
    """Execute app objects only in a worker; its supervisor owns the workspace."""
    os.chdir(root)
    sys.path.insert(0, str(root))
    return {"phase": name, "passed": True, **{"acceptance": acceptance, "tests": generated_tests, "launch": launch}[name](root)}


def run_phase(name: str, source: Path, timeout: float) -> dict[str, Any]:
    workspace = None
    report = {"phase": name, "passed": False}
    try:
        workspace = tempfile.TemporaryDirectory(prefix="foundry-" + name + "-")
        root = Path(workspace.name).resolve()
        shutil.copytree(source, root, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__", "*.db", "*.sqlite*"))
        # _run_prepared_phase waits for worker exit before returning. SQLite,
        # imported module globals and generated tests cannot retain parent handles.
        report = _run_prepared_phase(name, root, timeout)
    except OSError as exc:
        report = {"phase": name, "passed": False, "failure_kind": "environment",
                  "error": "Verifier workspace could not be prepared: " + str(exc)}
    finally:
        if workspace is not None:
            for attempt in range(3):
                try:
                    workspace.cleanup()
                    report["workspace_cleanup"] = "passed"
                    break
                except OSError as exc:
                    if attempt < 2:
                        time.sleep(0.05 * (attempt + 1))
                    else:
                        report.update(behavior_passed=report.get("passed") is True,
                                      passed=False, failure_kind="environment", workspace_cleanup="failed",
                                      error="Verifier workspace cleanup failed after worker exit: " + str(exc))
    return report


def diagnose(report):
    text = report.get("error", "").lower()
    if report.get("failure_kind") == "environment":
        return "Foundry could not prepare or clean up its verification workspace. This is a verifier/environment failure; no application code repair was requested. " + report.get("error", "")[:1500]
    if "restart persistence check failed" in text:
        return "Expected saved data could not be retrieved after an independent app-process restart. Persist data to SQLite/JSON in a stable project path; do not rely on module globals or erase the database at startup."
    if "message_from_bytes" in text or "unexpected keyword argument 'headers'" in text or "unexpected keyword argument 'method'" in text:
        return "An HTTP API is used incorrectly. Read Content-Type with self.headers.get_content_type(). Build urllib.request.Request with headers/method, then call urlopen(request, timeout=3)."
    if "no such table" in text:
        return "The database table is missing. Initialize the schema in create_server before handling requests."
    if "filenotfounderror" in text or any("referenced asset" in line and ("assertionerror" in line or "expected http" in line) for line in text.splitlines()):
        return "A referenced page or asset is missing or not served. Check HTML, CSS, JavaScript paths and routes."
    if report.get("phase") == "tests" and report.get("timed_out"):
        return "Generated tests timed out. Send real HTTP requests with timeouts; do not wait on server.handle_request without a client."
    if "did not exercise app.py" in text:
        return "The tests did not execute the real application. Import app.py and test its behavior."
    if "unexpected json" in text or "json response did not exactly match" in text:
        return "An API returned the wrong JSON structure or values. Match the approved response fields and the objects expected by the browser interface."
    if report.get("phase") == "tests":
        return "Generated tests failed. Inspect the traceback and repair the app or unverified tests while preserving the approved acceptance checks."
    if report.get("phase") == "launch":
        return "The app did not start correctly from its command line. Check --host, --port, imports, and startup output."
    return "The app failed an approved behavioral check. Inspect the last failing request and traceback."


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--phase", choices=["acceptance", "tests", "launch"])
    parser.add_argument("--milestone", action="store_true")
    parser.add_argument("--prepared", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--test-timeout", type=float, default=30)
    args = parser.parse_args()
    source = args.source.resolve()
    if args.phase:
        try:
            report = prepared_phase(args.phase, source) if args.prepared else phase(args.phase, source)
        except PhaseInfrastructureError as exc:
            traceback.print_exc()
            print(MARKER + json.dumps({"phase": args.phase, "passed": False, "failure_kind": "environment", "error": str(exc)}), flush=True)
            return 1
        except Exception:
            traceback.print_exc()
            return 1
        print(MARKER + json.dumps(report), flush=True)
        return 0
    results = []
    phases = [("acceptance", 40)] if args.milestone else [("acceptance", 40), ("tests", max(0.1, min(args.test_timeout, 300))), ("launch", 15)]
    for name, timeout in phases:
        result = run_phase(name, source, timeout)
        results.append(result)
        if not result["passed"]:
            print(json.dumps({"result": "failed", "phases": results, "diagnosis": diagnose(result), "failure_kind": result.get("failure_kind", "application")}), flush=True)
            return 1
    if args.milestone:
        print(json.dumps({"result": "milestone_passed", "http_checks": results[0]["http_checks"], "phases": results}), flush=True)
        return 0
    print(json.dumps({"result": "passed", "tests_run": results[1]["tests_run"], "app_calls": results[1]["app_calls"], "asset_checks": results[0]["asset_checks"], "http_checks": results[0]["http_checks"] + results[2]["http_checks"], "phases": results}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
