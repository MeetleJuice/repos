"""Fixed functional checks, executed in the same isolated runtime as generated code."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import threading
import socket
import subprocess
import sys
import time
import unittest
import urllib.error
import urllib.request


def subset(actual, expected):
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(k in actual and subset(actual[k], v) for k, v in expected.items())
    return actual == expected


def main():
    # Always validate a disposable copy. Do not consume or mutate a user's app data.
    root = Path(os.sys.argv[1]).resolve()
    with tempfile.TemporaryDirectory(prefix="foundry-check-") as temp:
        shutil.copytree(root, temp, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__", "*.db", "*.sqlite*"))
        os.chdir(temp)
        os.sys.path.insert(0, temp)
        suite = unittest.defaultTestLoader.discover(temp, pattern="test_*.py")
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        if result.testsRun < 1 or not result.wasSuccessful() or result.skipped or result.expectedFailures:
            raise AssertionError("Generated tests must execute at least one test, with no failures, skips, or expected failures.")
        spec = importlib.util.spec_from_file_location("foundry_generated_app", Path(temp) / "app.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        server = module.create_server("127.0.0.1", 0)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = "http://127.0.0.1:" + str(server.server_address[1])
        checks = [
            {"name": "Health endpoint", "method": "GET", "path": "/health", "status": 200, "json_contains": {"status": "ok"}},
            {"name": "HTML interface", "method": "GET", "path": "/", "status": 200, "contains": "<"},
            *json.loads((Path(temp) / "CHECKS.json").read_text(encoding="utf-8")),
        ]
        try:
            for check in checks:
                data = json.dumps(check["body"]).encode() if "body" in check else None
                req = urllib.request.Request(base + check["path"], data=data, method=check["method"], headers={"Content-Type": "application/json"})
                try:
                    response = urllib.request.urlopen(req, timeout=10)
                except urllib.error.HTTPError as exc:
                    response = exc
                with response:
                    text = response.read(1_000_000).decode("utf-8")
                    assert response.code == check["status"], f'{check["name"]}: expected HTTP {check["status"]}, got {response.code}: {text[:1000]}'
                    if "contains" in check:
                        assert check["contains"] in text, f'{check["name"]}: response missing {check["contains"]!r}'
                    if "json_contains" in check:
                        assert subset(json.loads(text), check["json_contains"]), f'{check["name"]}: unexpected JSON: {text[:1000]}'
                print("PASS:", check["name"], flush=True)
        finally:
            server.shutdown()
            server.server_close()
        # Verify the launch command too: a working factory alone does not prove
        # the downloaded app starts when invoked from the command line.
        with socket.socket() as port_socket:
            port_socket.bind(("127.0.0.1", 0))
            port = port_socket.getsockname()[1]
        proc = subprocess.Popen([sys.executable, "-B", "app.py", "--host", "127.0.0.1", "--port", str(port)])
        try:
            deadline = time.monotonic() + 8
            while True:
                if proc.poll() is not None:
                    raise AssertionError("app.py exited before its launch command became ready.")
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1) as response:
                        assert response.code == 200 and subset(json.load(response), {"status": "ok"}), "Launch command returned an invalid health response."
                    break
                except (urllib.error.URLError, TimeoutError):
                    if time.monotonic() >= deadline:
                        raise AssertionError("app.py launch command did not become ready within eight seconds.")
                    time.sleep(0.1)
            print("PASS: Python launch command", flush=True)
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=3)
        print(json.dumps({"tests_run": result.testsRun, "http_checks": len(checks) + 1, "result": "passed"}), flush=True)


if __name__ == "__main__":
    main()
