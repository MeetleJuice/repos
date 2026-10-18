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


def verify(project, mode, cancel, timeout=120):
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
            return _execute(staging / "source", mode, cancel, timeout, staging / "harness.py")
    return _execute(project, mode, cancel, timeout)


def _execute(project, mode, cancel, timeout, harness=None):
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
               IMAGE, "python", "-B", "/harness.py", "/source"]
    elif mode == "local":
        cmd = [sys.executable, "-I", "-B", str(harness), str(project)]
    else:
        raise ValueError("Choose Docker or trusted local execution.")
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
    reported = False
    if proc.returncode == 0 and not stopped:
        try:
            report = json.loads(log.strip().splitlines()[-1])
            checks = json.loads((project / "CHECKS.json").read_text(encoding="utf-8"))
            reported = (report.get("result") == "passed" and type(report.get("tests_run")) is int
                        and report["tests_run"] > 0 and report.get("http_checks") == len(checks) + 3)
        except (ValueError, KeyError, IndexError, AttributeError, OSError):
            pass
        if not reported:
            log += "\nVerification did not produce a complete test and HTTP-check report. A zero exit code alone is insufficient.\n"
    return {"passed": proc.returncode == 0 and not stopped and reported, "exit_code": proc.returncode,
            "log": ((stopped + "\n") if stopped else "") + log[-24000:], "runtime": mode}
