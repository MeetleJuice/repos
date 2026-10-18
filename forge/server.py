"""Loopback-only web interface. Session token + origin checks protect local mutations."""
import argparse
import io
import json
import os
from pathlib import Path
import secrets
import webbrowser
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
import zipfile

from .core import Workbench, ACTIVE
from .models import connection_info
from .routing import uses_cloud, validate_config
from . import __version__
from .storage import data_home, import_legacy, workspace_lock
from .runner import runtime_diagnostics
from .updates import UpdateManager, atomic_json

ROOT = Path(__file__).resolve().parents[1]


def load_dotenv(path):
    if path.exists():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() in {"OLLAMA_URL", "GROQ_API_KEY", "OPENROUTER_API_KEY", "GEMINI_API_KEY"}:
                os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def make_server(port=8765, workbench=None):
    bench = workbench or Workbench(data_home(ROOT) / "projects")
    token = secrets.token_urlsafe(32)
    updater = UpdateManager(bench.root.parent, ROOT, bench)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass  # Avoid logging project content or headers.

        def send_bytes(self, status, content, content_type="application/json", filename=None):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            if filename:
                self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.end_headers()
            self.wfile.write(content)

        def json(self, value, status=200):
            self.send_bytes(status, json.dumps(value).encode())

        def check_request(self):
            expected = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
            if self.headers.get("Host") not in expected:
                raise PermissionError("Unrecognized local host.")
            origin = self.headers.get("Origin")
            if origin and origin not in {"http://" + h for h in expected}:
                raise PermissionError("Cross-origin requests are forbidden.")

        def do_GET(self):
            self.dispatch(False)

        def do_POST(self):
            self.dispatch(True)

        def dispatch(self, post):
            try:
                self.check_request()
                path = urlsplit(self.path).path
                if path.startswith("/api/"):
                    if not secrets.compare_digest(self.headers.get("X-Foundry-Token", ""), token):
                        raise PermissionError("Session expired. Refresh this page.")
                    if post:
                        if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                            raise ValueError("JSON request required.")
                        length = int(self.headers.get("Content-Length", "0"))
                        if not 0 < length <= 150000:
                            raise ValueError("Request body too large or empty.")
                        body = json.loads(self.rfile.read(length))
                        if not isinstance(body, dict):
                            raise ValueError("Request body must be a JSON object.")
                    else:
                        body = {}
                    if post and path == "/api/updates/check":
                        self.api(path, post, body)
                    elif post:
                        with bench.lock:
                            if getattr(bench, 'maintenance', False):
                                raise ValueError('An update is being installed. Wait for the restart before making changes.')
                            self.api(path, post, body)
                    else:
                        self.api(path, post, body)
                elif post:
                    self.json({"error": "Not found."}, 404)
                elif path == "/health":
                    self.json({"status": "ok", "version": __version__, "boot": os.getenv("FOUNDRY_BOOT_NONCE", "")})
                elif path == "/":
                    html = (ROOT / "forge" / "static" / "index.html").read_text(encoding="utf-8").replace("__TOKEN__", token)
                    self.send_bytes(200, html.encode(), "text/html; charset=utf-8")
                elif path in {"/app.js", "/planning.js", "/updates.js", "/style.css"}:
                    self.send_bytes(200, (ROOT / "forge" / "static" / path[1:]).read_bytes(), "text/javascript" if path.endswith(".js") else "text/css")
                else:
                    self.json({"error": "Not found."}, 404)
            except PermissionError as exc:
                self.json({"error": str(exc)}, 403)
            except (ValueError, KeyError, TypeError) as exc:
                self.json({"error": str(exc)}, 400)
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception:
                self.json({"error": "Internal error. Check the workbench terminal and local project data."}, 500)

        def api(self, path, post, body):
            if path == "/api/updates" and not post:
                self.json(updater.status())
                return
            if path == "/api/updates/check" and post:
                self.json(updater.check(__version__))
                return
            if path == "/api/updates/install" and post:
                self.json(updater.install(__version__, self.server.shutdown), 202)
                return
            if path == "/api/insights" and not post:
                self.json(bench.insights())
                return
            if path == "/api/info" and not post:
                states = bench.list_projects()
                calls = [c for state in states for c in state.get("model_calls", [])]
                self.json({"version": __version__, "data_folder": str(bench.root.parent), "projects": len(states),
                           "model_calls": len(calls), "model_seconds": round(sum(c["seconds"] for c in calls), 1),
                           "warnings": bench.warnings, "inference_policy": "One model request at a time; fallback requires explicit configuration and cloud consent."})
                return
            if path == "/api/backup" and not post:
                self.send_bytes(200, bench.backup(), "application/zip", "Idea-Foundry-workspace-backup.zip")
                return
            if path == "/api/projects":
                if post:
                    self.cloud_consent(body.get("planner", {}), body.get("coder", {}), body)
                    self.json(bench.create(body["idea"], body["planner"], body["coder"], body.get("starter"), body.get("cloud_consent") is True), 201)
                else:
                    self.json(bench.list_projects())
                return
            if path == "/api/connections" and not post:
                runtime = runtime_diagnostics()
                self.json({"providers": connection_info(), "docker_installed": runtime["installed"], "docker": runtime})
                return
            pieces = path.strip("/").split("/")
            if len(pieces) not in {3, 4} or pieces[:2] != ["api", "projects"]:
                self.json({"error": "Not found."}, 404)
                return
            ident = pieces[2]
            state = bench.load(ident)
            if len(pieces) == 3 and not post:
                self.json(state)
                return
            action = pieces[-1]
            if action in {"files", "download"} and not post:
                if state["status"] in ACTIVE:
                    raise ValueError("Wait for the running job to stop before inspecting or exporting a stable project.")
                if action == "files":
                    self.json(bench.files(ident))
                else:
                    stream = io.BytesIO()
                    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
                        for name, content in bench.files(ident).items():
                            archive.writestr("generated-app/" + name, content)
                        archive.writestr("generated-app/BUILD-REPORT.json", json.dumps({"generator_version": __version__, "starter": state.get("starter"), "starter_version": state.get("starter_version"), "milestones": state.get("milestones", []), "status": state["status"], "checks": state["checks"], "preflight": state.get("preflight"), "plan_review": state.get("plan_review"), "planning_stats": state.get("planning_stats"), "models": {"planner": state["planner"], "coder": state["coder"]}}, indent=2))
                    self.send_bytes(200, stream.getvalue(), "application/zip", "generated-app.zip")
            elif post and action == "review":
                self.json(bench.review_proposal(ident, body["plan"]))
            elif post and action == "approve":
                self.json(bench.approve(ident, body["plan"]))
            elif post and action == "stop":
                self.json(bench.stop(ident))
            elif post and action == "restore":
                self.json(bench.restore(ident, body["snapshot"]))
            elif not post and action == "diff":
                self.json(bench.diff(ident))
            elif post and action == "models":
                self.json(bench.configure_models(ident, body["planner"], body["coder"]))
            elif post and action == "change":
                self.cloud_consent(state["planner"], state["coder"], body)
                self.json(bench.fork(ident, body["request"], body.get("cloud_consent") is True), 201)
            elif post and action in {"plan", "build"}:
                self.cloud_consent(state["planner"], state["coder"], body)
                bench.start(ident, action, body)
                self.json(bench.load(ident), 202)
            else:
                self.json({"error": "Not found."}, 404)

        @staticmethod
        def cloud_consent(planner, coder, body):
            planner, coder = validate_config(planner), validate_config(coder)
            if any(uses_cloud(c) for c in (planner, coder)) and body.get("cloud_consent") is not True:
                raise ValueError("Confirm that you allow sending this project's content to the selected cloud providers. API usage may cost money.")

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    server.workbench = bench
    server.updater = updater
    return server


def main():
    parser = argparse.ArgumentParser(description="Idea Foundry — local idea-to-app workbench")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--data-dir", help="Workspace folder; overrides FOUNDRY_HOME and the default location")
    parser.add_argument("--open", action="store_true", help="Open the workbench in your default browser")
    args = parser.parse_args()
    home = data_home(ROOT, args.data_dir)
    try:
        with workspace_lock(home):
            migration_warnings = []
            imported = import_legacy(ROOT, home, migration_warnings)
            load_dotenv(home / ".env")
            load_dotenv(ROOT / ".env")
            launch_root = os.getenv("FOUNDRY_LAUNCH_ROOT")
            if launch_root:
                load_dotenv(Path(launch_root) / ".env")
            bench = Workbench(home / "projects")
            bench.warnings.extend(migration_warnings)
            server = make_server(args.port, bench)
            print(f"Idea Foundry {__version__} is running locally on port {server.server_port}.\nOpen http://127.0.0.1:{server.server_port}\nYour workspace: {home}", flush=True)
            ready_file = os.getenv("FOUNDRY_READY_FILE")
            if ready_file:
                atomic_json(Path(ready_file), {"port": server.server_port})
            if imported:
                print(f"Copied {len(imported)} legacy projects; originals were preserved.", flush=True)
            if args.open:
                threading.Timer(0.5, lambda: webbrowser.open(f"http://127.0.0.1:{server.server_port}")).start()
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
            finally:
                jobs = list(server.workbench.jobs.values())
                for _, cancel in jobs:
                    cancel.set()
                # Keep the workspace lock until workers stop writing to it.
                for thread, _ in jobs:
                    thread.join()
                server.server_close()
            if server.updater.restart:
                raise SystemExit(75)
    except (ValueError, OSError) as exc:
        parser.exit(1, f"Idea Foundry could not start: {exc}\n")


if __name__ == "__main__":
    main()
