# Repair notes

This is the corrected Task Tracker from the user's uploaded generated project.
The original PROJECT.md, TASKS.md, and CHECKS.json are retained as the approved record.
They describe the original generation, not a new task breakdown or expanded verification claim.

Corrected Python indentation/syntax, the absent GET /api/tasks route, the form/JSON mismatch,
and shared SQLite connection/cursor usage across request threads. Added independent per-request
connections, input validation, friendly errors, safe text rendering, completion/reopening,
deletion, filters, and behavioral tests including persistence after server restart.

No Ollama model is required to launch this app. Its code is already written. Running the
tracker does not modify the Idea Foundry workbench or its saved project state.

Tests are in test_app.py. A new BUILD-REPORT.json is produced only after running verification;
the uploaded report's original `generated` status is not reused as proof of success.
