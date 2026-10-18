"""Execute only fixed verification commands, with an explicit user-selected runtime."""
import os
import json
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid

IMAGE = "python:3.12-slim"


def docker_ready():
    if not shutil.which("docker"):
        return False
    try:
        return subprocess.run(["docker", "info"], capture_output=True, timeout=8).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def runtime_diagnostics():
    installed = bool(shutil.which("docker"))
    running = docker_ready() if installed else False
    image = False
    if running:
        try:
            image = subprocess.run(["docker", "image", "inspect", IMAGE], capture_output=True, timeout=8).returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            pass
    return {"installed": installed, "running": running, "image_ready": image}


def require_runtime(mode):
    if mode == "local":
        return
    status = runtime_diagnostics()
    if not status["running"]:
        raise ValueError("Docker is not running. Start Docker Desktop, or explicitly select trusted local execution. No model request was made for this run.")
    if not status["image_ready"]:
        raise ValueError("Docker needs its Python image. Run: docker pull python:3.12-slim. Then retry. No model request was made for this run.")
def require_browser_runtime(project, mode):
    path = Path(project) / "BROWSER-CHECKS.json"
    if not path.exists() or not json.loads(path.read_text(encoding="utf-8")):
        return
    if mode != "local":
        raise ValueError("This proposal requires optional Chromium checks, currently supported only with explicitly approved trusted local execution. Docker verification cannot silently skip them. Revise the unapproved proposal to manual checks if browser automation is unavailable.")
    from .browser_runner import diagnostics
    status = diagnostics()
    if not status["available"]:
        raise ValueError(status["detail"] + ". No model request was made for this run.")


def verify(project, mode, cancel, timeout=120, test_timeout=30):
    require_browser_runtime(project, mode)
    if mode == "docker":
        # The source checkout may use private (0600/0700) permissions. Prepare a
        # readable disposable mount without relaxing permissions on user files.
        with tempfile.TemporaryDirectory(prefix=".verify-", dir=Path(project).parent) as temp:
            staging = Path(temp)
            shutil.copytree(project, staging / "source")
            shutil.copyfile(Path(__file__).with_name("harness.py"), staging / "harness.py")
            staging.chmod(0o755)
            for path in staging.rglob("*"):
                path.chmod(0o755 if path.is_dir() else 0o644)
            return _execute(staging / "source", mode, cancel, timeout, staging / "harness.py", test_timeout)
    result = _execute(project, mode, cancel, timeout, test_timeout=test_timeout)
    path = Path(project) / "BROWSER-CHECKS.json"
    if result["passed"] and path.exists() and json.loads(path.read_text(encoding="utf-8")):
        result = _verify_browser(project, mode, cancel, result)
    return result


def _execute(project, mode, cancel, timeout, harness=None, test_timeout=30, milestone=False):
    project = Path(project).resolve()
    harness = (harness or Path(__file__).with_name("harness.py")).resolve()
    name = "foundry-" + uuid.uuid4().hex
    if mode == "docker":
        if not docker_ready():
            raise ValueError("Docker Desktop is not running. Start it and pull python:3.12-slim, or explicitly choose trusted local execution.")
        cmd = ["docker", "run", "--rm", "--name", name, "--pull=never", "--network=none",
               "--memory=512m", "--cpus=1", "--pids-limit=64", "--read-only", "--cap-drop=ALL",
               "--security-opt=no-new-privileges", "--user=65534:65534", "--tmpfs", "/tmp:rw,size=128m,mode=1777",
               "--mount", f"type=bind,source={project},target=/source,readonly",
               "--mount", f"type=bind,source={harness},target=/harness.py,readonly",
               IMAGE, "python", "-B", "/harness.py", "/source", "--test-timeout", str(test_timeout)]
    elif mode == "local":
        cmd = [sys.executable, "-I", "-B", str(harness), str(project), "--test-timeout", str(test_timeout)]
    else:
        raise ValueError("Choose Docker or trusted local execution.")
    if milestone:
        cmd.append("--milestone")
    # Do not pass the workbench's API keys or broad environment through to generated programs.
    environment = {k: v for k, v in os.environ.items() if k.upper() in {
        "PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "HOME", "USERPROFILE",
        "DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_CONFIG", "PROGRAMFILES", "COMSPEC",
    }}
    flags = {"start_new_session": True} if os.name != "nt" else {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    stopped = None
    with tempfile.TemporaryFile() as output:
        proc = subprocess.Popen(cmd, stdout=output, stderr=subprocess.STDOUT, cwd=project, env=environment, **flags)
        deadline = time.monotonic() + timeout
        try:
            while proc.poll() is None:
                if cancel.is_set():
                    stopped = "Stopped by user."
                elif time.monotonic() > deadline:
                    stopped = "Verification exceeded its time limit."
                elif os.fstat(output.fileno()).st_size > 2_000_000:
                    stopped = "Verification exceeded the output limit."
                if stopped:
                    break
                time.sleep(0.1)
        finally:
            if proc.poll() is None or os.name != "nt":
                if os.name == "nt":
                    subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, timeout=10)
                else:
                    try:
                        os.killpg(proc.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
            proc.wait(timeout=10)
            if mode == "docker":
                subprocess.run(["docker", "rm", "-f", name], capture_output=True, timeout=15)
        output.seek(0)
        log = output.read(2_000_000).decode("utf-8", errors="replace")
    reported, report = False, {}
    try:
        report = json.loads(log.strip().splitlines()[-1])
        if not isinstance(report, dict):
            report = {}
    except (ValueError, IndexError):
        pass
    if proc.returncode == 0 and not stopped:
        try:
            checks = json.loads((project / "CHECKS.json").read_text(encoding="utf-8"))
            reported = (report.get("result") == "passed" and type(report.get("tests_run")) is int
                        and report["tests_run"] > 0 and report.get("http_checks") == len(checks) + 3
                        and type(report.get("app_calls")) is int and report["app_calls"] > 0
                        and [p.get("phase") for p in report.get("phases", []) if p.get("passed")] == ["acceptance", "tests", "launch"])
            if milestone:
                reported = (report.get("result") == "milestone_passed" and report.get("http_checks") == len(checks) + 2
                            and [p.get("phase") for p in report.get("phases", []) if p.get("passed")] == ["acceptance"])
        except (ValueError, KeyError, IndexError, AttributeError, OSError):
            pass
        if not reported:
            log += "\nVerification did not produce a complete test and HTTP-check report. A zero exit code alone is insufficient.\n"
    passed = proc.returncode == 0 and not stopped and reported
    return {"passed": passed, "exit_code": proc.returncode,
            "diagnosis": report.get("diagnosis") or ("Verification stopped before completion." if stopped else None),
            "phases": report.get("phases", []),
            "failure_kind": None if passed else "environment" if mode == "docker" and proc.returncode in {125, 126, 127} else "application",
            "log": ((stopped + "\n") if stopped else "") + log[-24000:], "runtime": mode}


def verify_milestone(project, mode, cancel, checks):
    """Run only an approved ordered prefix in a disposable copy, without changing CHECKS.json."""
    project = Path(project).resolve()
    with tempfile.TemporaryDirectory(prefix=".milestone-", dir=project.parent) as temp:
        root = Path(temp)
        source = root / "source"
        shutil.copytree(project, source)
        (source / "CHECKS.json").write_text(json.dumps(checks), encoding="utf-8")
        harness = root / "harness.py"
        shutil.copyfile(Path(__file__).with_name("harness.py"), harness)
        if mode == "docker":
            root.chmod(0o755)
            for path in root.rglob("*"):
                path.chmod(0o755 if path.is_dir() else 0o644)
        return _execute(source, mode, cancel, 60, harness, milestone=True)


def _verify_browser(project, mode, cancel, result):
    harness = Path(__file__).with_name("browser_runner.py").resolve()
    environment = {k: v for k, v in os.environ.items() if k.upper() in {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "HOME", "USERPROFILE", "LOCALAPPDATA", "PROGRAMFILES", "COMSPEC", "PLAYWRIGHT_BROWSERS_PATH"}}
    flags = {"start_new_session": True} if os.name != "nt" else {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    stopped = None
    with tempfile.TemporaryFile() as output:
        proc = subprocess.Popen([sys.executable, "-B", str(harness), str(Path(project).resolve())], stdout=output, stderr=subprocess.STDOUT, env=environment, **flags)
        deadline = time.monotonic() + 90
        try:
            while proc.poll() is None:
                if cancel.is_set(): stopped = "Browser verification stopped by user."
                elif time.monotonic() > deadline: stopped = "Browser verification exceeded its time limit."
                elif os.fstat(output.fileno()).st_size > 2_000_000: stopped = "Browser verification exceeded its output limit."
                if stopped: break
                time.sleep(0.1)
        finally:
            if os.name == "nt" and proc.poll() is None:
                subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, timeout=10)
            elif os.name != "nt":
                try: os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError: pass
            proc.wait(timeout=10)
        output.seek(0)
        log = output.read(2_000_000).decode("utf-8", errors="replace")
    try:
        report = json.loads(log.strip().splitlines()[-1])
        assert isinstance(report, dict)
    except (ValueError, IndexError, AssertionError):
        report = {"phase": "browser", "passed": False, "error": "Browser process produced no valid report."}
    expected = len(json.loads((Path(project) / "BROWSER-CHECKS.json").read_text(encoding="utf-8")))
    passed = not stopped and proc.returncode == 0 and report.get("phase") == "browser" and report.get("passed") is True and report.get("browser_checks") == expected and type(report.get("assertions")) is int and report["assertions"] >= expected
    report["passed"] = bool(passed)
    result["phases"].append(report)
    result["failure_kind"] = None if passed else report.get("failure_kind", "application")
    result.update(passed=bool(passed), exit_code=proc.returncode, diagnosis=None if passed else stopped or report.get("error") or "Browser assertions failed.")
    result["log"] += "\nBrowser verification:\n" + (stopped or "") + log[-16000:]
    return result
