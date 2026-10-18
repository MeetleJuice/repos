# Task Tracker

Simple local web app to add, complete, and view tasks with SQLite persistence using only Python standard library.

## Approved requirements

{
  "title": "Task Tracker",
  "summary": "Simple local web app to add, complete, and view tasks with SQLite persistence using only Python standard library.",
  "features": [
    "Add new tasks via POST /api/tasks",
    "Mark tasks complete via PUT /api/tasks/{id}",
    "View all tasks via GET /api/tasks",
    "Delete tasks via DELETE /api/tasks/{id}",
    "HTML interface at GET /",
    "SQLite persistence across restarts"
  ],
  "out_of_scope": [
    "User authentication",
    "Task categories/tags",
    "Notifications",
    "Mobile app",
    "Deployment to cloud"
  ],
  "risks": [
    "SQLite file corruption if not closed properly",
    "Concurrent requests may need threading (handled by http.server.ThreadingHTTPServer)",
    "Large task lists may slow down simple queries"
  ],
  "tasks": [
    {
      "title": "Create basic server with health check",
      "instructions": "Implement create_server(host, port) returning ThreadingHTTPServer. Add GET /health returning JSON {\"status\":\"ok\"}. Include main block parsing --host and --port arguments.",
      "code_snippet": "from http.server import ThreadingHTTPServer\nimport json\n\ndef create_server(host='127.0.0.1', port=8000):\n    server = ThreadingHTTPServer((host, port), TaskHandler)\n    return server\n\nif __name__ == '__main__':\n    import argparse\n    parser = argparse.ArgumentParser()\n    parser.add_argument('--host', default='127.0.0.1')\n    parser.add_argument('--port', type=int, default=8000)\n    args = parser.parse_args()\n    server = create_server(args.host, args.port)\n    print(f'Server running on http://{args.host}:{args.port}')\n    server.serve_forever()"
    }
  ],
  "checks": [
    {
      "name": "Health check",
      "method": "GET",
      "path": "/health",
      "status": 200,
      "json_contains": {
        "status": "ok"
      }
    },
    {
      "name": "Create task",
      "method": "POST",
      "path": "/api/tasks",
      "body": {
        "title": "Buy milk"
      },
      "status": 201,
      "json_contains": {
        "title": "Buy milk"
      }
    }
  ]
}