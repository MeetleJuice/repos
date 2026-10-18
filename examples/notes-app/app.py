"""Local notes app. Standard library only; importing it never creates a database."""
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
    database = Path(database or "notes.db").resolve()

    @contextmanager
    def connection():
        with closing(sqlite3.connect(database, timeout=10)) as db:
            with db:
                yield db

    with connection() as db:
        db.execute("CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, body TEXT NOT NULL)")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def reply(self, data, status=200, content_type="application/json; charset=utf-8"):
            payload = data if isinstance(data, bytes) else json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self):
            self.dispatch("GET")

        def do_POST(self):
            self.dispatch("POST")

        def do_DELETE(self):
            self.dispatch("DELETE")

        def dispatch(self, method):
            try:
                hosts = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
                origin = self.headers.get("Origin")
                if self.headers.get("Host") not in hosts or origin and origin not in {"http://" + host for host in hosts}:
                    return self.reply({"error": "Only local, same-origin requests are allowed."}, 403)
                url = urlsplit(self.path)
                path = url.path
                if method == "GET" and path == "/health":
                    return self.reply({"status": "ok"})
                assets = {"/": ("index.html", "text/html; charset=utf-8"), "/app.js": ("app.js", "text/javascript; charset=utf-8"), "/style.css": ("style.css", "text/css; charset=utf-8")}
                if method == "GET" and path in assets:
                    name, kind = assets[path]
                    return self.reply((ASSETS / name).read_bytes(), content_type=kind)
                if method == "GET" and path in {"/api/notes", "/api/notes/search"}:
                    with connection() as db:
                        rows = db.execute("SELECT id, title, body FROM notes ORDER BY id DESC").fetchall()
                    notes = [{"id": row[0], "title": row[1], "body": row[2]} for row in rows]
                    if path.endswith("/search"):
                        query = parse_qs(url.query, keep_blank_values=True).get("q", [""])[0].casefold()
                        notes = [note for note in notes if query in note["title"].casefold()]
                    return self.reply(notes)
                if method == "POST" and path == "/api/notes":
                    if self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
                        raise ValueError("Send JSON with a title and body.")
                    length = int(self.headers.get("Content-Length", "0"))
                    if not 0 < length <= 100000:
                        raise ValueError("The request must contain at most 100000 bytes.")
                    data = json.loads(self.rfile.read(length))
                    if not isinstance(data, dict):
                        raise ValueError("The request must be an object.")
                    title, body = data.get("title"), data.get("body")
                    if not isinstance(title, str) or not 1 <= len(title.strip()) <= 300:
                        raise ValueError("Enter a title between 1 and 300 characters.")
                    if not isinstance(body, str) or len(body) > 20000:
                        raise ValueError("Body must be text of at most 20000 characters.")
                    title = title.strip()
                    with connection() as db:
                        ident = db.execute("INSERT INTO notes (title, body) VALUES (?, ?)", (title, body)).lastrowid
                    return self.reply({"id": ident, "title": title, "body": body}, 201)
                match = re.fullmatch(r"/api/notes/([1-9][0-9]*)", path)
                if method == "DELETE" and match:
                    ident = int(match.group(1))
                    with connection() as db:
                        count = db.execute("DELETE FROM notes WHERE id = ?", (ident,)).rowcount
                    if not count:
                        return self.reply({"error": "Note not found."}, 404)
                    return self.reply({"deleted": True, "id": ident})
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
    parser = argparse.ArgumentParser(description="Local Notes App")
    parser.add_argument("--host", choices=["127.0.0.1", "localhost"], default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--database", default="notes.db")
    args = parser.parse_args()
    server = create_server(args.host, args.port, args.database)
    print(f"Notes App: http://127.0.0.1:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
