# Architecture

`run.py` → `forge.server` (loopback HTTP + session token) → `forge.core.Workbench`
→ model adapter → validated file updates → `forge.runner` → fixed `forge.harness`.

- `models.py`: Ollama native JSON chat, plus the OpenAI-compatible endpoints for optional APIs.
- `prompts.py`: separate planning and coding contracts.
- `core.py`: validation, approval, jobs, inference queue, linked revisions, progress, checkpoints, diffs, backups, repairs, and documents.
- `storage.py`: Windows user-data location, explicit path overrides, workspace process lock, and non-destructive legacy import.
- `launch_template.py`: readiness-checked launcher shipped with generated apps.
- `runner.py`: fixed commands, explicit runtime, timeout/output bounds, child process cleanup.
- `inspection.py`: AST checks for syntax, actual app imports, copied test servers, blocking test calls, and unsupported cgi imports.
- `harness.py`: isolated acceptance, generated-test and launch phases, local asset checks, and runtime app-call measurement.
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

After each task, AST parsing checks Python syntax without executing code. After the full task list, structural inspection requires the server factory and test methods. Missing
app.py, create_server, test files, or test methods are reported. The coder may correct source
and add missing tests using the same bounded repair budget as runtime repairs. Trusted tests and acceptance checks remain frozen; unverified new test files can be corrected. Incomplete code ends in needs_attention. `generated`
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
- Repairs may edit app source and unverified tests. Approved checks and trusted baseline tests remain immutable.

The harness runs real approved HTTP requests first, generated unit tests second, and the launch command last. Each phase uses a separate subprocess and disposable directory. Unit tests have their own 30-second default limit inside the overall verification timeout. It requires a nonzero test count and no skipped/expected-failure tests. Health and
home-page checks alone are insufficient; the approved proposal must contain actual behavior.
This is engineering feedback, not a proof against adversarial code or weak assertions. Local
execution has the user's permissions. Docker narrows exposure; generated code is still untrusted.

## State and secrets

On Windows, state lives in `%LOCALAPPDATA%\IdeaFoundry` outside the downloaded program folder. Non-Windows defaults retain the portable `data/` layout. FOUNDRY_HOME and --data-dir override either default. Atomic JSON replacement prevents partial
state writes. A checkpoint is made before each source update and before manual restoration.
If the process exits between writing files and recording completed task progress, retrying may
repeat that task; snapshots preserve the prior version. A process-level workspace lock prevents two current workbench instances using the same data folder. Older releases do not know about this lock, so stop them before upgrading. Do not edit project state while jobs run.

API keys are loaded from the user's environment or local ignored `.env`. They are never saved
in project state, prompts, or exports by the workbench. The execution environment is filtered,
but a local program can still read accessible files. Docker mounts only the selected generated
source and the read-only harness, with networking off and no secrets passed through.

## Change requests and inference

A change forks source into a fresh project with a parent link, a new proposal/approval cycle,
and no inherited verification claim. Original features must remain a prefix of the new feature
list; baseline acceptance checks are reinserted if omitted. Original test file hashes are frozen
throughout the change build. New tests may be added. Parent files and metadata are not modified.
These constraints prevent silent regression-test deletion but cannot prove semantic correctness.

An inference lock serializes model requests across projects. Waiting jobs use `queued` and
can be cancelled before a provider call. Recorded times measure actual request duration, not
quality, token consumption, cost, or a model-ranking score. Calls have no automatic provider fallback.

Source writes prepare an entire new tree, swap directories, and preserve a pre-change checkpoint.
If a swap fails, the previous source is restored. Startup can recover the old source if termination
occurred between renames. Invalid project metadata is reported without blocking readable projects.

Workspace backup requires all jobs to stop. It excludes hidden files, credentials in .env,
and caches, and is bounded at 100 MB. User content can itself contain secrets; the backup is
private project data and should not be published. Credentials must be backed up separately.

## Verification in 0.4

Test files with test methods must import app.py rather than redefining application handlers.
Static checks reject the exact copied-server/handle_request patterns found in the uploaded Notes
App. Dynamic profiling requires at least one application function call during the test run;
module import and class-definition execution do not count. This is a minimum test-quality check,
not proof that the assertions are comprehensive or resistant to adversarial code.

Acceptance checks support contains (text), json_contains (object or nonempty list subset), and
json_equals (exact JSON, including []). Approved checks run independently of model-written tests.
The home page's local scripts, stylesheets and images are fetched to detect missing asset routes.
No automatic browser interaction is claimed for arbitrary generated apps.

After successful verification, test hashes are recorded as trusted regression tests. Inherited
change-request tests are protected from the start. Before first verification, faulty new tests
can be repaired while all approved checks stay protected. Checkpoints preserve the trust metadata;
restoring a checkpoint restores its source and trust state. Externally changed trusted tests stop
the build with a restore instruction rather than being silently accepted or sent for weakening.
