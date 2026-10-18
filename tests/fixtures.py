"""Deterministic model responses for integration tests; never used in real generation."""
PLAN = {
    "title": "Pocket Tasks", "summary": "A small persistent task tracker.",
    "features": ["Create a task", "List saved tasks"], "out_of_scope": ["Accounts"],
    "risks": ["Review generated code before running."],
    "tasks": [{"title": "Build the task tracker", "instructions": "Create app.py and behavioral unittest tests.", "feature_indexes": [0, 1]}],
    "checks": [
        {"name": "Create task", "method": "POST", "path": "/api/tasks", "body": {"title": "Buy milk"}, "status": 201, "json_contains": {"title": "Buy milk"}, "feature_indexes": [0]},
        {"name": "Retrieve saved task", "method": "GET", "path": "/api/tasks", "status": 200, "contains": "Buy milk", "feature_indexes": [1]},
    ],
}

APP = '''import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import sqlite3

def create_server(host, port):
    with sqlite3.connect("tasks.db") as db:
        db.execute("CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY, title TEXT)")
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def reply(self, value, status=200, html=False):
            body = value.encode() if html else json.dumps(value).encode()
            self.send_response(status)
            self.send_header("Content-Type", "text/html" if html else "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def do_GET(self):
            if self.path == "/health": self.reply({"status":"ok"})
            elif self.path == "/api/tasks":
                with sqlite3.connect("tasks.db") as db:
                    rows = db.execute("SELECT id, title FROM tasks ORDER BY id").fetchall()
                self.reply([{"id":row[0], "title":row[1]} for row in rows])
            elif self.path == "/":
                self.reply("<!doctype html><title>Pocket Tasks</title><h1>Pocket Tasks</h1><form id='f'><input id='title' required><button>Add task</button></form><ul id='tasks'></ul><script>async function load(){const rows=await(await fetch('/api/tasks')).json();tasks.replaceChildren(...rows.map(t=>{const li=document.createElement('li');li.textContent=t.title;return li;}));}f.onsubmit=async e=>{e.preventDefault();await fetch('/api/tasks',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title:document.getElementById('title').value})});f.reset();load();};load();</script>",html=True)
            else: self.reply({"error":"Not found"},404)
        def do_POST(self):
            if self.path != "/api/tasks": return self.reply({"error":"Not found"},404)
            data=json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            title=data.get("title", "").strip()
            if not title: return self.reply({"error":"Title required"},400)
            with sqlite3.connect("tasks.db") as db:
                ident=db.execute("INSERT INTO tasks (title) VALUES (?)",(title,)).lastrowid
            self.reply({"id":ident,"title":title},201)
    return ThreadingHTTPServer((host,port),Handler)

if __name__ == "__main__":
    p=argparse.ArgumentParser();p.add_argument("--host",default="127.0.0.1");p.add_argument("--port",type=int,default=8080);a=p.parse_args()
    create_server(a.host,a.port).serve_forever()
'''

TEST = '''import json
import os
import tempfile
import threading
import unittest
import urllib.request
from app import create_server

class TaskTests(unittest.TestCase):
    def test_health(self):
        original=os.getcwd()
        with tempfile.TemporaryDirectory() as temp:
            os.chdir(temp)
            server=create_server("127.0.0.1",0)
            threading.Thread(target=server.serve_forever,daemon=True).start()
            try:
                with urllib.request.urlopen("http://127.0.0.1:"+str(server.server_address[1])+"/health") as r:
                    self.assertEqual(json.load(r),{"status":"ok"})
            finally:
                server.shutdown();server.server_close();os.chdir(original)
'''

BROKEN = APP.replace('self.reply([{"id":row[0], "title":row[1]} for row in rows])', 'self.reply([])')
