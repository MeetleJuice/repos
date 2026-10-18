# Notes App

A local notes app with create, list, title search, delete, a browser interface, and SQLite persistence. Python standard library only.

## Approved requirements

{
  "title": "Notes App",
  "summary": "A local notes app with create, list, title search, delete, a browser interface, and SQLite persistence. Python standard library only.",
  "features": [
    "Create note with title and body",
    "List all saved notes",
    "Search notes by title substring",
    "Delete a note by ID",
    "Store data persistently in SQLite database",
    "Serve HTML interface for browser access"
  ],
  "out_of_scope": [
    "User authentication",
    "Email notifications",
    "Cloud sync",
    "Rich text editing",
    "Markdown support"
  ],
  "risks": [
    "Intended for one local user, not public hosting.",
    "Behavioral tests and a manual browser check are needed before calling the app finished."
  ],
  "tasks": [
    {
      "title": "Initialize SQLite database and server factory",
      "instructions": "Create app.py (not notes_app.py), exporting create_server(host, port). Use SQLite notes(id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, body TEXT NOT NULL). Open a separate connection per request and close it reliably. No database creation or writes on module import. Initialize the database when create_server is called. Bind to loopback by default.",
      "feature_indexes": [
        4
      ]
    },
    {
      "title": "Implement HTML interface and health endpoint",
      "instructions": "Implement GET /health returning JSON {\"status\":\"ok\"} and GET / serving a usable notes interface. Provide title/body fields, Add Note button, notes list, title search, and delete buttons. Use JavaScript fetch with JSON for creation; render user content with textContent. Ensure every UI request has a matching server route.",
      "feature_indexes": [
        5
      ]
    },
    {
      "title": "Implement API endpoints for CRUD and Search",
      "instructions": "Implement POST /api/notes with JSON title/body, returning 201 and id/title/body; GET /api/notes returning all saved notes; GET /api/notes/search?q=... returning title-substring matches or []; DELETE /api/notes/{id} returning {\"deleted\":true,\"id\":...}, or 404 for absent IDs. Parse query strings correctly and use parameterized SQL.",
      "feature_indexes": [
        0,
        1,
        2,
        3
      ]
    },
    {
      "title": "Add security and validation logic",
      "instructions": "Validate that title is a nonempty trimmed string and body is a string. Return JSON errors for malformed input, invalid IDs, and missing notes. Close per-request SQLite connections. Render note titles and bodies as text, never raw HTML. Keep database file paths stable across server restarts.",
      "feature_indexes": [
        0,
        1,
        2,
        3
      ]
    },
    {
      "title": "Implement test suite and persistence verification",
      "instructions": "Deliver a complete app.py with a main block accepting --host and --port, plus test_app.py with real unittest tests. Use temporary databases/directories and isolate every test from the database used by later acceptance checks. Test create/list, matching and nonmatching title searches, delete followed by an empty list, invalid input, and the HTML page. For persistence: create a note, stop and close the server, start a new server instance using the SAME temporary database, and verify the note title and body remain. Do not delete that note before verifying restart persistence. Shut down servers and close SQLite connections before cleaning up temporary files. No database side effects on import, no skipped or empty tests. Implement ALL approved features.",
      "feature_indexes": [
        0,
        1,
        2,
        3,
        4,
        5
      ]
    }
  ],
  "checks": [
    {
      "name": "HTML notes interface is served",
      "method": "GET",
      "path": "/",
      "status": 200,
      "contains": "<form",
      "feature_indexes": [
        5
      ]
    },
    {
      "name": "Create a note with title and body",
      "method": "POST",
      "path": "/api/notes",
      "body": {
        "title": "Buy milk",
        "body": "Need to buy groceries"
      },
      "status": 201,
      "json_contains": {
        "id": 1,
        "title": "Buy milk",
        "body": "Need to buy groceries"
      },
      "feature_indexes": [
        0
      ]
    },
    {
      "name": "List the saved note",
      "method": "GET",
      "path": "/api/notes",
      "status": 200,
      "contains": "Buy milk",
      "feature_indexes": [
        1
      ]
    },
    {
      "name": "Search finds a matching title",
      "method": "GET",
      "path": "/api/notes/search?q=milk",
      "status": 200,
      "contains": "Buy milk",
      "feature_indexes": [
        2
      ]
    },
    {
      "name": "Search excludes nonmatching titles",
      "method": "GET",
      "path": "/api/notes/search?q=unmatched-title-xyz",
      "status": 200,
      "contains": "[]",
      "feature_indexes": [
        2
      ]
    },
    {
      "name": "Saved note remains readable before deletion; restart persistence is tested in unittest",
      "method": "GET",
      "path": "/api/notes",
      "status": 200,
      "contains": "Need to buy groceries",
      "feature_indexes": [
        4
      ]
    },
    {
      "name": "Delete the created note",
      "method": "DELETE",
      "path": "/api/notes/1",
      "status": 200,
      "json_contains": {
        "deleted": true
      },
      "feature_indexes": [
        3
      ]
    },
    {
      "name": "Deleted note is absent from the list",
      "method": "GET",
      "path": "/api/notes",
      "status": 200,
      "contains": "[]",
      "feature_indexes": [
        3
      ]
    }
  ]
}