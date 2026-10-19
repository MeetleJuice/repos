# 0.13.0 — Completion reliability

This release addresses two Reading List failures: truncated builder output requiring manual resume, and successful HTTP acceptance blocked by Windows database cleanup before tests/launch could run.

## Changes

Verification workspaces belong to a supervisor. App imports, SQLite connections and generated tests live in a worker that exits before cleanup. Each phase gets a fresh copy. Transient cleanup errors retry three times with short delays. Persistent failures remain environment failures and never request model repair. Reports retain actual behavioral evidence and show cleanup separately; incomplete verification cannot become verified.

Builder calls reserve configured visible output plus bounded reasoning on supported profiles, check context/output room before sending, and record budgets/finish reasons. Supported Gemini profiles use native controls; unknown profiles keep the compatible endpoint without invented thinking support. Truncation gets at most one same-model continuation and one compact fresh response per configured model. Full JSON and files are validated before replacement. Smaller-capacity fallback models are skipped. Extra calls and reasoning reservations can increase API use.

Nested test directories need __init__.py for unittest discovery across supported Python releases. Phase cards show actual HTTP/test/asset counts and cleanup status. HTTP success still does not prove browser gameplay quality.

Existing projects, approved requirements, frozen checks/tests, checkpoints, backups, manual results, consent and ZIP contracts remain compatible. No new provider, dependency or data migration. This is a reliability fix, not a measured live repair-quality improvement. [Research and frozen provenance](research/completion-process-v1.md).

## Update and test

1. Back up using Workspace & backups. Click Update, check for 0.13.0, install and restart. If the launcher cannot install, extract the new ZIP into a fresh folder and run Start-Foundry.bat. Keep the older folder until testing is complete.
2. Open Reading List. Keep its four saved tasks. Choose This computer only if you approve running this generated code, check execution consent, select zero repairs for the first verification, then click Build, test & repair.
3. Confirm approved behavior/assets, tests of the actual app, and launch command all finish with Passed and Workspace cleanup: passed. A cleanup failure must not spend model requests.
4. Download and run the app. Add a book, toggle read/unread, restart to confirm persistence, then delete it. Record required manual observations.
5. A fresh small app can exercise the cloud route. The journal now reports builder reservation and continuation/shortening. Provider access and quota still need to work.

## Validation and next priorities

Results: research/completion-process-results.json. This Linux checkout cannot establish native Windows or live cloud generation without the user's local setup/keys. The handle-lifetime regression runs in the existing Windows/Python 3.11–3.13 CI matrix.

Next: test the user's actual Windows Reading List workspace, collect consented source-bound live build outcomes, then improve task sizing/templates based on observed failures. The separate six-case live repair trial remains pending credentials and budget; scripted outcomes do not replace it.

Release checks passed: 236 tests on Python 3.12, 236 from the extracted ZIP on Python 3.13, 24 dedicated completion/planner regressions, strict type checks on 11 modules, and two real Chromium workflows with fixture providers. No live provider keys were present.
