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
quality, token consumption, cost, or a model-ranking score. Calls use only explicitly configured fallback routes: service/output-limit failures can hand off to the next configured model; invalid-format correction remains bounded. Local fallback is optional, and cloud consent is required before cloud inference.

Source writes prepare an entire new tree, swap directories, and preserve a pre-change checkpoint.
If a swap fails, the previous source is restored. Startup can recover the old source if termination
occurred between renames. Invalid project metadata is reported without blocking readable projects.

Workspace backup requires all jobs to stop. It excludes hidden files, credentials in .env,
and caches, and is bounded at 100 MB. User content can itself contain secrets; the backup is
private project data and should not be published. Credentials must be backed up separately.

## Verification in 0.4

Test files with test methods must import actual project modules (app.py or a module such as db.py) rather than redefining application handlers.
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

## 0.5 release and generation boundaries

`run.py` uses the standard-library `bootstrap.py` supervisor. The original launcher selects a
versioned installation from the same stable data folder and starts `run.py --server` in a child.
The child retains the workspace lock and existing API origin/token protections. On an approved
update, `updates.py` blocks new mutations, verifies a fixed-source release archive, backs up the
workspace, installs side-by-side, writes pending/current metadata atomically and requests exit 75.
The supervisor restarts the selected version, verifies its health/version/boot nonce, and restores
the old pointer if startup fails. Project schema stays at 2; unsupported data formats are refused.
No inference, arbitrary install hooks, in-place source updates or project migrations occur here.

`scaffolds.py` describes explicit versioned starters. Approval writes owned documents then seeds
only empty new projects. A foundation test hash is protected; feature tests are unverified until
the actual app passes. Existing projects and linked revisions are never reseeded. `context.py`
provides AST symbol maps, source fingerprints and focused phase/traceback feedback. Current source
still fits the 36,000-character contract; retrieval/indexing is not claimed.

A plan's optional task.check_indexes names approved checks ready after the task. Milestone checks
run the ordered prefix through the highest index in disposable source/data, with explicit runtime
consent. They do not require final tests or claim full verification. Failures get bounded repairs
before later tasks; exhaustion resets next_task to the unfinished task. Final verification still
requires acceptance, actual generated tests and the launch phase. Static, milestone and full-runtime
repairs share one cap. Unchanged repairs stop; approved check-file changes stop before generation.

The update UI is in static/updates.js, separate from project rendering. It refreshes after a new
boot nonce so the local session token is replaced. GET /health exposes only readiness, version and
an ephemeral startup identity, without project data or credentials. Model outcome summaries group
current project states by current builder and explicitly do not rank models.

## 0.6 contract-aware planning

`contracts.py` owns structural validation, typed findings, starter/API response contracts and
consistency review. `planning.py` owns a three-request maximum correction loop and one optional
fallback. `routing.py` validates local settings and a single explicit fallback; `schemas.py`
provides native Ollama output schemas. `models.py` reports typed service failures and real usage
metadata. Workbench retains atomic project state, approvals and inference serialization.

The local review endpoint is authenticated and side-effect-free. Approval reruns review on the
actual submitted JSON; client-side disabled buttons are only guidance. New planning metadata is
optional in schema-2 states. Older approved projects do not acquire new plan constraints during
loading or building. Legacy backups and exports remain readable.

The harness's restart_before operation closes the factory server and uses an independent CLI
process on the same disposable data, preventing module-global storage from passing persistence.
Child readiness, termination and outer process-tree cleanup remain bounded. No execution occurs
before the existing explicit runtime approval. The helper is shared with final CLI launch checks.

## 0.7 evidence contracts

contracts.py composes evidence.py validation with legacy HTTP structure. New manual/browser
checks are optional additions to the approved plan, not a state migration. documents() writes
owned BROWSER-CHECKS.json/MANUAL-CHECKS.md. Source generation cannot replace them. Review and
approval use the same combined feature coverage; linked changes retain baseline checks.

runner.py runs the existing independent acceptance/tests/launch processes. If required, a fourth
optional browser_runner.py process uses real Chromium, a disposable copy/profile and fixed
actions/assertions. Missing dependencies fail as environment errors rather than triggering model
repairs. Standard-library generated apps remain independent of the optional test tool.

Automated pass with manual requirements sets review_required. The authenticated manual endpoint
accepts explicit booleans only after a successful run with matching source fingerprint. Human
observations are exported separately. Source replacement, restore and new runs invalidate results.
The two outcomes must not be conflated in UI or build reports.


## Measured handoffs in 0.11

Actual inference attempts additionally record a handoff version, system-plus-user character count, and SHA-256 request identity. This metadata contains no prompt text and is not a token estimate or secrecy guarantee. Optional fields preserve legacy state loading. The UI labels characters separately from actual provider-reported token usage.

Production JSON serialization remains unchanged. `forge/handoffs.py::serialize_handoff` and `tests/benchmark_handoffs.py` contain evaluation-only lossless-format prototypes; they are not an automatic optimizer. The frozen eighteen-case dataset has labeled provenance and is not eighteen independent historical builds. See docs/status.md for measured proxy costs, rejected promotion decisions and unavailable live repair-success evidence. Source and evaluator changes still require reviewed commits.
