# Architecture

`run.py` → `forge.server` (loopback HTTP + session token) → `forge.core.Workbench`
→ model adapter → validated file updates → `forge.runner` → fixed `forge.harness`.

- `models.py`: Ollama native JSON chat, plus the OpenAI-compatible endpoints for optional APIs.
- `prompts.py`: separate planning and coding contracts.
- `core.py`: validation, approval, jobs, events, progress, checkpoints, repairs, documents.
- `runner.py`: fixed commands, explicit runtime, timeout/output bounds, child process cleanup.
- `harness.py`: disposable app copy, real unittest execution, fixed and approved HTTP checks.
- `server.py`: authenticated local API, static UI, safe project exports.
- `static/`: dependency-free browser interface. User/model content is inserted as text.

## Lifecycle

`draft → planning → proposed → approved → building → generated`

Execution consent extends the workflow to `checking → [repairing → checking] → verified`.
Failures become `needs_attention` (repair cap), `error` (validation/provider/runtime failure),
or `stopped`. A restart marks in-progress jobs `interrupted`; resume uses `next_task`.
Only one job can run per project. Model output is discarded when a stop was requested.
The UI uses one local session token per server process; it must refresh after a restart.

New proposals must map every feature to task/check `feature_indexes`. A structurally incomplete
proposal gets one correction attempt before an error is reported. This explicit traceability is
not a semantic guarantee. Already-approved legacy projects are not silently rewritten.

After tasks are generated, AST parsing checks all Python files without executing them. Missing
app.py, create_server, test files, or test methods are reported. The coder may correct source
and add missing tests using the same bounded repair budget as runtime repairs. Existing tests
and acceptance checks remain frozen. Incomplete code ends in needs_attention. `generated`
is displayed as **Files ready · not tested**, never as a working-app claim.

## Generated-app contract

- Standard-library-only Python 3.11+.
- `app.py` exports `create_server(host, port)` returning an HTTPServer-compatible instance.
- Main block accepts `--host` and `--port`.
- `/health` returns HTTP 200 JSON `{"status":"ok"}`; `/` serves a usable HTML interface.
- `test_app.py` (or other `test_*.py`) contains actual unittest tests.
- Model output is JSON `{"summary":"...", "files":{"app.py":"complete text"}}`.
- No model-provided shell commands, file deletions, hidden files, symlinks, or binary artifacts.
- PROJECT.md, TASKS.md, CHECKS.json, README.md, and launchers are workbench-owned.
- Repairs may edit app source but cannot edit test filenames or frozen acceptance checks.

The harness runs tests and then real HTTP requests against an ephemeral server in a disposable
directory. It requires a nonzero test count and no skipped/expected-failure tests. Health and
home-page checks alone are insufficient; the approved proposal must contain actual behavior.
This is engineering feedback, not a proof against adversarial code or weak assertions. Local
execution has the user's permissions. Docker narrows exposure; generated code is still untrusted.

## State and secrets

State lives outside the package in ignored `data/`. Atomic JSON replacement prevents partial
state writes. A checkpoint is made before each source update and before manual restoration.
If the process exits between writing files and recording completed task progress, retrying may
repeat that task; snapshots preserve the prior version. Do not run two workbench processes
against the same data directory or edit it while jobs run.

API keys are loaded from the user's environment or local ignored `.env`. They are never saved
in project state, prompts, or exports by the workbench. The execution environment is filtered,
but a local program can still read accessible files. Docker mounts only the selected generated
source and the read-only harness, with networking off and no secrets passed through.
