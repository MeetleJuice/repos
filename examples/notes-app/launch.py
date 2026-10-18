"""Generated-app launcher: choose a port, wait for readiness, then open the browser."""
import argparse
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser


def main():
    parser = argparse.ArgumentParser(description="Launch this local app")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    os.chdir(Path(__file__).resolve().parent)
    with socket.socket() as sock:
        try:
            sock.bind(("127.0.0.1", args.port))
        except OSError:
            sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    flags = {"start_new_session": True} if os.name != "nt" else {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    proc = subprocess.Popen([sys.executable, "app.py", "--host", "127.0.0.1", "--port", str(port)], **flags)
    def stop(_signal, _frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop)
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, stop)
    url = f"http://127.0.0.1:{port}"
    try:
        deadline = time.monotonic() + 20
        while True:
            if proc.poll() is not None:
                raise RuntimeError("The app stopped before it was ready. Read the error above.")
            try:
                with urllib.request.urlopen(url + "/health", timeout=1) as response:
                    body = json.loads(response.read(8192))
                    if response.status == 200 and isinstance(body, dict) and body.get("status") == "ok":
                        break
            except (urllib.error.URLError, TimeoutError, ValueError):
                pass
            if time.monotonic() > deadline:
                raise RuntimeError("The app did not become ready within 20 seconds.")
            time.sleep(0.1)
        print(f"APP_READY {url}\nKeep this window open. Press Ctrl+C to stop the app.", flush=True)
        if not args.no_browser:
            webbrowser.open(url)
        return proc.wait()
    except KeyboardInterrupt:
        return 0
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        if os.name == "nt" and proc.poll() is None:
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, timeout=10)
        elif os.name != "nt":
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
