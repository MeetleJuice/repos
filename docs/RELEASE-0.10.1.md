# 0.10.1 — Validate source before replacement

An uploaded dashboard exposed a repair response containing only `NEW file contents` and `COMPLETE file contents` as Python test files. Its HTML contained doubly escaped markup. A separate false-positive inspection required database unit tests to import app.py, even when they already imported the project's actual db.py.

Changed Python files are now parsed before source staging, checkpoints or replacement. Known placeholder-only responses and doubly escaped HTML markup are rejected at the same boundary. The existing single focused correction receives the rejection reason and current source. A rejected response cannot corrupt working files. Existing malformed files remain available for repair; the update does not silently rewrite user projects.

Test inspection accepts imports of real Python modules present in the project while retaining the rejection of tests that import no application code and tests that reimplement a server. This is a structural heuristic, not proof of behavioral coverage; execution and reviewed acceptance checks remain necessary.

Existing source budgets, test hashes, frozen acceptance checks, project data and model routes remain unchanged. This patch does not promise that provider model-access errors disappear. Users should choose a model their provider actually permits for generation.
