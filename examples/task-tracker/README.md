# Task Tracker — repaired version

1. Open this folder on Windows and double-click **run.bat**.
2. Leave its terminal open; open **http://127.0.0.1:8080** in your browser.
3. Add tasks, tick their checkboxes to complete/reopen them, filter the list, or delete tasks.

Python 3.11+ is required. No additional packages or Ollama models are needed to run this tracker.
VS Code alternative: `py -3 app.py --port 8080` from this folder.

Tasks are saved in `tasks.db` in the launch directory. Preserve this file to keep your tasks.
The schema is compatible with the uploaded tracker. Stop the old tracker before copying a database.
If port 8080 is occupied, use `py -3 app.py --port 8081` and open that port instead.

Run the behavioral tests: `py -3 -m unittest discover -v` from this folder.
PROJECT.md and CHECKS.json retain the original approved scope/checks; the added tests cover
listing, completion, deletion, persistence, invalid requests, safe text, and concurrent writes.
This app is for one computer, not public hosting or multi-user authentication.
