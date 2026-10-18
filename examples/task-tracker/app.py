"""Task Tracker: local, standard-library-only app. No database writes on import."""
import argparse
from contextlib import closing, contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import sqlite3
from urllib.parse import parse_qs, urlsplit

ASSETS = Path(__file__).resolve().parent


def create_server(host="127.0.0.1", port=8080, database=None):
    database = Path(database or "tasks.db").resolve()
    @contextmanager
    def connection():
        with closing(sqlite3.connect(database, timeout=10)) as db:
            with db:
                yield db

    with connection() as db:
        db.execute("CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY, title TEXT NOT NULL, completed BOOLEAN NOT NULL DEFAULT 0)")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def reply(self, value, status=200, content_type="application/json; charset=utf-8"):
            body = value if isinstance(value, bytes) else json.dumps(value).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers()
            self.wfile.write(body)

        def data(self, optional=False):
            length = int(self.headers.get("Content-Length", "0"))
            if length == 0 and optional:
                return {}
            if not 0 < length <= 8192:
                raise ValueError("Request must contain at most 8192 bytes.")
            text = self.rfile.read(length).decode("utf-8")
            kind = self.headers.get("Content-Type", "").split(";")[0]
            if kind == "application/json":
                data = json.loads(text)
            elif kind == "application/x-www-form-urlencoded":
                data = {key: values[0] for key, values in parse_qs(text).items()}
            else:
                raise ValueError("Send JSON or form data.")
            if not isinstance(data, dict):
                raise ValueError("Request must be an object.")
            return data

        def do_GET(self):
            self.handle_request("GET")

        def do_POST(self):
            self.handle_request("POST")

        def do_PUT(self):
            self.handle_request("PUT")

        def do_DELETE(self):
            self.handle_request("DELETE")

        def handle_request(self, method):
            try:
                hosts = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
                origin = self.headers.get("Origin")
                if self.headers.get("Host") not in hosts or origin and origin not in {"http://" + h for h in hosts}:
                    return self.reply({"error": "Only local, same-origin requests are allowed."}, 403)
                path = urlsplit(self.path).path
                if method == "GET" and path == "/health":
                    return self.reply({"status": "ok"})
                assets = {"/": ("index.html", "text/html; charset=utf-8"), "/app.js": ("app.js", "text/javascript; charset=utf-8"), "/style.css": ("style.css", "text/css; charset=utf-8")}
                if method == "GET" and path in assets:
                    name, kind = assets[path]
                    return self.reply((ASSETS / name).read_bytes(), content_type=kind)
                if path == "/api/tasks" and method == "GET":
                    with connection() as db:
                        rows = db.execute("SELECT id, title, completed FROM tasks ORDER BY id").fetchall()
                    return self.reply([{"id": row[0], "title": row[1], "completed": bool(row[2])} for row in rows])
                if path == "/api/tasks" and method == "POST":
                    data = self.data()
                    title = data.get("title")
                    if not isinstance(title, str) or not 1 <= len(title.strip()) <= 300:
                        raise ValueError("Enter a task title between 1 and 300 characters.")
                    title = title.strip()
                    with connection() as db:
                        ident = db.execute("INSERT INTO tasks (title, completed) VALUES (?, 0)", (title,)).lastrowid
                    return self.reply({"id": ident, "title": title, "completed": False}, 201)
                match = re.fullmatch(r"/api/tasks/([1-9][0-9]*)", path)
                if match and method in {"PUT", "DELETE"}:
                    ident = int(match.group(1))
                    completed = self.data(optional=True).get("completed", True) if method == "PUT" else None
                    if method == "PUT" and type(completed) is not bool:
                        raise ValueError("completed must be true or false.")
                    with connection() as db:
                        row = db.execute("SELECT title FROM tasks WHERE id = ?", (ident,)).fetchone()
                        if row is None:
                            return self.reply({"error": "Task not found."}, 404)
                        if method == "PUT":
                            db.execute("UPDATE tasks SET completed = ? WHERE id = ?", (completed, ident))
                        else:
                            db.execute("DELETE FROM tasks WHERE id = ?", (ident,))
                    if method == "PUT":
                        return self.reply({"id": ident, "title": row[0], "completed": completed})
                    return self.reply({"id": ident, "deleted": True})
                return self.reply({"error": "Not found."}, 404)
            except (ValueError, UnicodeError, OverflowError) as exc:
                self.reply({"error": str(exc)}, 400)
            except sqlite3.Error:
                self.reply({"error": "Database unavailable. Check disk permissions and retry."}, 500)
            except (BrokenPipeError, ConnectionResetError):
                pass

    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    return server


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="A small local task tracker")
    parser.add_argument("--host", default="127.0.0.1", choices=["127.0.0.1", "localhost"])
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--database", default="tasks.db")
    args = parser.parse_args()
    server = create_server(args.host, args.port, args.database)
    print(f"Task Tracker: http://127.0.0.1:{server.server_port} — keep this window open. Ctrl+C stops the app.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
