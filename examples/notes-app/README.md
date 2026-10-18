# Notes App — repaired and tested version

Open this folder on Windows and double-click **run.bat**. Keep its terminal open.
The launcher opens your browser when the app is ready. It normally uses port 8080,
or chooses another available port if 8080 is occupied.

Create notes with a title and body, search their titles, and delete notes.
Notes are stored in `notes.db` in this folder when using the launcher and survive restarts.
Preserve that file to retain your notes. Stop the old app before copying a database.

Requires Python 3.11+; no Ollama, API account, Docker, or extra Python packages are needed
to run this corrected app. VS Code alternative: `py -3 launch.py` from this folder.

Tests: `py -3 -m unittest discover -v` from this folder. Tests use temporary databases,
import the actual app, and send real HTTP requests. They do not modify your saved notes.

This repairs the user's uploaded generated app. PROJECT.md, TASKS.md, and CHECKS.json
retain the approved requirements and checks. BUILD-REPORT.json records validation of
the repaired version; it does not change the status of the old project in Idea Foundry.
The original uploads were preserved separately during review.

This is a local, single-user app and is not intended for public hosting.
