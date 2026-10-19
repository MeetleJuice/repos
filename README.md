# Idea Foundry 0.9.0

**Describe an idea. Approve a proposal. Generate, test, and repair a small working Python web app.**

An original, local-first Python workbench for Windows and VS Code. Ollama is the default;
Groq, OpenRouter, and Gemini are optional. No Python packages need installing for the workbench
or its generated apps. Optional real-browser automation uses Playwright/Chromium. Python 3.11 or newer is required.

## 0.9.0 cloud-first studio

**Models → Choose your API key file → Check cloud providers.** Import the .env or .env.txt
from your Desktop directly into your private local workspace. UTF-8 and Notepad UTF-16 work;
key values never appear in responses, projects or downloadable app bundles. The original file
stays on your computer. No provider SDK installation is required.

Choose advertised models and per-provider output limits, then **Use cloud for new projects**
or **Use cloud for this project**. The ordered Gemini → Groq → OpenRouter route skips missing
providers and fails over on service, quota and connection errors. Cloud jobs still require
explicit consent. Local models, frozen checks, checkpoints and existing projects remain available.
See [setup and testing](docs/RELEASE-0.9.0.md) and [research](docs/CLOUD-RESEARCH.md).

## 0.8.1 repair-response recovery

If an exact edit is rejected, the single correction now requests complete changed files with a
required nonempty `files` schema. A failed or unchanged repair retains saved checklist results
and notes when the source is unchanged. The failure stays unresolved; retrying does not require
re-entering the same observations. See [the recovery guide](docs/RELEASE-0.8.1.md).

## 0.8.0 evidence-driven repairs

A failed gameplay check can now include **what actually happened**. Save those notes and choose
**Repair files only** or **Repair & retest** to send the current source and failure directly to
the builder, preserving the approved plan and tests. Checkpoints protect the previous code;
changed files need fresh verification and manual acceptance. Exact edits reduce whole-file
rewrites, and optional Chromium checks gain controlled time, repeatable randomness and detailed
failure steps. No additional package is required for the manual-check repair workflow.
See [the update and repair guide](docs/RELEASE-0.8.0.md) and [research](docs/PASS-3-RESEARCH.md).

## 0.7.3 improvement planning and proposal imports

Improvement planning now receives bounded current-source evidence instead of relying only on
promised features. Repeated repair task lists are rejected. **Import proposal JSON** and
**Save edited proposal** explicitly save reviewed edits and update visible task cards without
inference, approval or execution. See [the repair guide](docs/RELEASE-0.7.3.md).

## 0.7.2 Windows verification fix

Fixes WinError 32 after passed acceptance checks by leaving the temporary working directory
before deleting it. Workspace failures stop verification without spending app-repair requests.
Update, reopen the existing project and retry verification with Maximum repairs set to 0.
See [the Windows recovery guide](docs/RELEASE-0.7.2.md). No regeneration is needed.

## 0.7.1 planning fix

If Neon Dodge planning stops before showing a proposal, update and open that failed project.
Click **Use standard Neon Dodge plan**, review the standard scope and approve before building.
This explicit recovery needs no planner request and never silently replaces custom requirements.
The same choice appears after **Try Neon Dodge** for new standard games. Custom planning still
uses your selected model. See [the recovery guide](docs/RELEASE-0.7.1.md).

## What’s new in 0.7 — blue-flame studio

- **Browser apps are first-class:** Canvas games and client-side tools no longer need fake APIs
  to satisfy planning. Coverage can combine HTTP tests, optional real-browser checks and manual checks.
- **Honest acceptance:** automated success with pending manual checks says “try the app.” Record
  explicit pass/fail observations after launching it; those results are separate from automated tests.
- **Try Neon Dodge:** a playable tested arcade starter with keyboard/touch controls, pause, restart,
  collision/game-over and localStorage high scores. No database or extra app dependencies.
- **Real Chromium checks:** optional bounded actions/assertions test actual interactions after consent.
  Missing tooling blocks required tests, never silently skips. Currently trusted local runtime only.
- **Focused response recovery:** invalid file responses get one correction before stopping; complete
  file validation and frozen checks still prevent partial or weakened updates.
- **New visual identity:** charcoal panels, cyan accents and the blue-flame mascot adaptation in
  the sidebar and favicon. The prominent Update button remains in the top bar.

Use **Update → Check for updates → Install & restart**, keeping the terminal open. Or extract
this ZIP into a new folder and launch Start-Foundry.bat. Existing projects remain supported.
See [the 0.7 test guide](docs/RELEASE-0.7.md), [research and audit](docs/PASS-2-RESEARCH.md), and
[validation](docs/VALIDATION.md). Start with **Try Neon Dodge**; review the proposal before approval.

## Previously added in 0.6 — contract-aware planning and recovery

- Checks proposals for API response-shape mismatches, impossible HTTP/body combinations,
  placeholder expected values and restart claims without a real restart operation.
- Uses reviewed starter API contracts as defaults and highlights explicit contract changes.
- Corrects proposal errors with exact JSON locations, within three planner requests total.
  Repeated unchanged invalid output stops; one explicitly configured fallback may be used.
- **Local settings & optional fallback** under each model: Ollama context/output budgets,
  native JSON schemas (with a JSON-mode compatibility toggle), and one fallback model.
  Cloud fallback requires explicit consent before any job request. No provider is chosen for you.
- A live proposal-review panel checks manual edits without inference requests and blocks invalid
  approval. Existing unapproved proposals are reviewed when opened; approved legacy checks stay frozen.
- `restart_before: true` on an acceptance GET closes the old server and starts an independent app
  process against the same data. This detects memory-only storage masquerading as persistence.
- Categorized provider errors, truncation diagnostics and actual token counts when reported.
- Typed validation/planning/routing modules keep these policies separate from project storage.

**Already on 0.5?** Click **Update → Check for updates → Install & restart**, keeping the terminal
open. The published 0.5 launcher protocol and data schema remain supported. A manual ZIP install
into a new folder remains available. Do not overwrite your project data.

See [the release guide](docs/RELEASE-0.6.md), [audit and blueprint](docs/PASS-1-AUDIT.md), and
[measured results](docs/benchmarks/planning-0.6.json). No live Windows/Ollama GPU speedup is claimed.

## Previously added in 0.5

- **Update** in the top bar: check published GitHub releases, review notes, back up projects,
  install a separate program version, restart and recover automatically if startup fails.
- Tested starters: a Python web foundation (default), the reviewed Notes App, and Task Tracker.
  Templates are explicit, installed only after approval, and never added to existing projects.
- A protected foundation test plus source maps and focused failure reports for local models.
- Optional approved milestone checks while building, under the same execution consent and repair cap.
- Stops unchanged repairs instead of repeating the same failing verification. Static inspection
  also runs after runtime repairs, with a shared budget of at most three repair requests.
- Additional checks for the actual bad HTTP APIs found in the latest Notes App upload.
- A clearer build/test layout, missing-Docker guidance, searchable projects, larger readable text,
  accessible focus styles, reduced-motion support and a prominent Update button.
- Readable project guides and local model/project outcome summaries, with no automatic ranking
  or paid-provider fallback.

**One-time installation:** extract this ZIP into a new folder, stop the old Foundry terminal,
then start **Start-Foundry.bat**. Windows projects already in Local AppData are reused.
Keep this new folder: its launcher is the stable entry point for future managed updates.
No Docker installation is required to generate source files or use the updater.

See [the 0.5 release guide](docs/RELEASE-0.5.md) for update recovery, validation and limits.

## Previously added in 0.4

The working Notes App supplied a real regression case for the generator. Foundry now:

- Rejects copied-server test suites and blocking `server.handle_request()` calls before execution.
- Requires tests to import the real application, and checks that its functions run during tests.
- Runs protected acceptance checks first, generated tests second, and the launch check third,
  each in a fresh copy/process so test data cannot leak into another phase.
- Checks local scripts, stylesheets, and images referenced by the served home page.
- Allows faulty **unverified** tests to be repaired; tests from a verified version or an inherited
  change-request baseline remain frozen. Approved acceptance checks are always protected.
- Supports JSON array/object subset assertions and exact JSON assertions such as an empty list.
- Shows which verification phases passed, failed, or did not run, with focused diagnoses.

These checks improve feedback; they do not guarantee model quality or exhaustive correctness.
The regression repair tests use controlled replies, not live inference against your Windows Ollama.

## Previously added in 0.3

- A next-step guide on every project, readable acceptance-check cards, and clearer failure explanations.
- **Plan this improvement**: request a feature/bug fix in a separate copy, preserving the original,
  its features, acceptance checks, and test files. Review and approve the change before building.
- Switch a project’s models without losing files or requirements.
- One model request runs at a time across the workspace, with cancellable queued jobs and measured response times.
- Python syntax is inspected after each task, with bounded repairs before proceeding.
- Transactional source updates, crash recovery, and checkpoint diffs.
- **Workspace & backups**: version, data location, warnings, and a downloadable project backup.
- On Windows, persistent projects now live outside the downloaded program folder.
- New generated-app launchers wait for readiness, choose a free port, and open the browser.
- Docker daemon/image problems are detected before inference; environment failures do not trigger pointless code repairs.

## Try the repaired Notes App

The reviewed Notes App is included in **examples/notes-app**. Open that folder and
double-click **run.bat**. Its launcher opens your browser when ready. This standalone app
does not require Ollama or Docker. It includes real HTTP tests and restart-persistence checks.
The corrected copy is separate from any older Notes App saved inside your Foundry workspace.

## Try the repaired Task Tracker

The corrected first app is included in **examples/task-tracker**. Open that folder and
double-click **run.bat**, then open `http://127.0.0.1:8080`. It works independently of
Idea Foundry and does not need Ollama. See that folder's README for details.

## Update an existing Windows copy

The GitHub repository, this cloud checkout, and your Windows folder are separate copies.
Changes on GitHub do not automatically update a ZIP you already extracted.

1. Stop the old workbench with **Ctrl+C** in its terminal. Keep its folder as a backup.
2. Download the latest repository ZIP and extract it into a **new folder**.
3. For your first update from an older version, copy the old **data** folder into the new
   program folder. Do not overwrite an existing data folder; keep both copies if uncertain.
4. Start **Start-Foundry.bat**. On Windows, Foundry copies missing legacy projects into
   `%LOCALAPPDATA%\IdeaFoundry\projects`, preserving the originals. It never overwrites an
   existing project ID during import.
5. Open **Workspace & backups** to confirm the version, project count, and actual data location.
6. If you used cloud keys in an old `.env`, copy that file separately into the data folder shown
   in Workspace (or the new program folder). Never upload it or include it in GitHub.

After this one-time move, future Windows program ZIPs can go in new folders without copying
projects again. Project backups intentionally exclude `.env`; preserve keys separately.
Version 0.5 adds managed updates through the top-bar **Update** button. It checks the published
release manifest in this repository; you choose **Install & restart**. The current terminal
must stay open. If GitHub is unavailable, keep using the installed version and retry later.
ZIP updates remain an alternative. Updates do not upload projects or synchronize generated code.

Existing approved projects remain usable. **Generate / resume code** now checks Python
syntax and missing tests without executing the app; it can ask the model for bounded repairs.
Approved requirements/checks and trusted regression tests stay frozen. New unverified tests can be corrected. New proposals must explicitly
map every feature to implementation tasks and acceptance checks. This mapping helps expose
omissions; it does not prove that model-written tasks/checks adequately implement a feature.

## Start on Windows

1. Download the Idea Foundry ZIP and **extract all files** into a folder, such as `Documents\IdeaFoundry`.
2. Open that folder in VS Code. In its PowerShell terminal, run `py -3 --version`.
   If Python is missing or older than 3.11, install a current supported Python from python.org.
3. Make sure Ollama is running. Your existing `qwen3.5:9b` and `qwen2.5-coder:7b` are the defaults.
4. Double-click **Start-Foundry.bat**, or run:

   ```powershell
   py -3 run.py
   ```

5. The launcher opens your browser. If it does not, open `http://127.0.0.1:8765`. Keep the terminal open while using the app.

Linux/macOS: run `python3 run.py`. To use another port: `python run.py --port 8766`.
The workbench binds only to this computer. It is not intended to be exposed on a network.

## Your first build

1. Try: “Build a task tracker with saved tasks and a list of unfinished tasks.”
2. Choose a tested starter (the Python web foundation is recommended) and your planner/builder
   models, then click **Shape my idea**. Notes/Tasks starters include working example features;
   review the proposal to decide which features the new app should keep or change.
3. Read the proposal, scope, ordered tasks, and HTTP/browser/manual acceptance checks. Revise it if needed.
   You can edit the JSON directly before approval.
4. Click **Approve this project**. Requirements and acceptance checks are now frozen.
5. Click **Generate / resume code** to create files without executing them. Python syntax,
   the server factory, and test-file structure are inspected first, with bounded text-only repairs.
   **Files ready · not tested** means static inspection passed; behavioral verification is still pending.
6. Review the generated files. Select an execution runtime, explicitly approve execution,
   and click **Build, test & repair**. If code is already generated, it starts with checks.
7. Read the results. Download the app ZIP, extract it, and open it in VS Code.
   Double-click its run.bat to launch it; the browser opens after readiness. Review its README first.
8. If the proposal includes manual checks, try every item and record its pass/fail result back in Foundry.

Local models may take several minutes per request. The current request has a five-minute
timeout. Stop discards a pending model response when it returns; it does not cancel Ollama's
inference remotely. Tests stop promptly. Progress and files are saved after each task.
Restart and reopen a project to resume. A failed task can be retried; completed tasks are retained.
Snapshots let you restore earlier generated files, with a backup made before restoration.

## Executing generated code

**Docker is the recommended verification runtime.** If Docker Desktop is supported on your
Windows installation, install/start it and run this once:

```powershell
docker pull python:3.12-slim
```

The workbench does not automatically download container images. It uses the existing image,
a read-only source mount, no network, a non-root user, resource limits, and temporary storage.
Verification runs in a fresh disposable copy so generated app data does not affect later checks.
Docker Desktop requirements vary by Windows version/build and WSL support; Windows 10 users
should check Docker's current requirements before installing.

**Trusted local execution is an explicit alternative, not a sandbox.** Generated Python runs
with your account's permissions and can access your files, network, and credentials. A project
directory, timeout, and filtered environment do not prevent that. Inspect code first. If you
do not trust it, use a container or a separate disposable VM. Starting a downloaded app on
Windows also executes generated code with your permissions.

Only a fixed test harness is invoked; models cannot supply arbitrary shell commands or install
dependencies through the UI. That limits accidental scope but does not make Python code safe.

## Optional cloud APIs

Copy `.env.example` to `.env` in the data folder shown in Workspace (or the program folder), enter keys locally, then restart the workbench. Data-folder values take precedence over program-folder values; existing process environment bindings take precedence over both:

```dotenv
OLLAMA_URL=http://127.0.0.1:11434
GROQ_API_KEY=
OPENROUTER_API_KEY=
GEMINI_API_KEY=
```

Never paste keys into ideas, generated files, chat, or GitHub. `.env` is ignored by Git and
excluded from distribution archives. The Model connections panel shows key presence without
displaying values. Presence does not prove that a key, model, or account is usable.

Select a provider and enter a model ID supported by that account. Groq and OpenRouter model
fields are intentionally blank rather than guessing an available model. Gemini uses its
OpenAI-compatible endpoint. Models must support chat and JSON-object output; provider support
can vary by model. Unsupported responses produce an actionable error rather than a fake success.
Cloud use requires a checkbox acknowledging that ideas, project code, and failure logs may
be sent to the selected providers, with possible charges. There is **no implicit paid fallback**. You may explicitly configure one fallback per role;
cloud consent covers both configured primary and fallback providers for that job.
Ollama model discovery reads your actual `/api/tags` list. Embedding models should not be used
as planner/builder models.

## Supported workflow and current limits

- Generates small standard-library Python web apps, with a browser UI and optional SQLite storage.
- Creates a project guide (`PROJECT.md`), `TASKS.md`, launch scripts, and frozen `CHECKS.json`.
- Breaks the build into ordered model calls, passing the approved proposal and current source.
- Runs generated `unittest` tests plus fixed health, home-page, and approved behavioral HTTP checks.
- Requires at least one executed generated test; failures, skipped tests, and expected failures
  do not pass verification. Repairs cannot change approved checks or trusted test files. New unverified tests can be corrected.
- Makes at most three repair decisions per run, shared between static and runtime fixes. Each code operation can request one response-format correction; configured fallback attempts are also logged. Repeated invalid output stops.
- Preserves progress, checkpoints, verification logs, and an exportable build report.

This release focuses on small Python web apps, not a promise to build any app from any prompt. It does not
train models, rewrite its own code, deploy to the internet, install project packages, or automatically
run browser tests for every generated app. Explicit browser checks are optional and require local tooling. Generated tasks are applied sequentially. Optional task `check_indexes` declare approved
ordered check prefixes ready at a runnable milestone; these run only with execution consent.
Full acceptance, generated tests, launch and any required browser checks run after the final task. Manual checks require separate user observations. Passing checks proves only the covered behavior. Model-written
tests may be weak: inspect the approved acceptance checks and try the result yourself. Local outcome summaries describe the current state of projects grouped by current builder;
they are not controlled model rankings or a model-training system. Use **Plan this improvement** to create a linked change copy with the original preserved. Source is limited to 36,000 characters to fit smaller local models;
large ideas should start with a smaller version. Generated apps must implement the fixed contract
described in [the architecture](docs/ARCHITECTURE.md).

## Your files

Open **Workspace & backups** for the actual path. On Windows the default is
`%LOCALAPPDATA%\IdeaFoundry`; on Linux/macOS the default remains `data` beside the program.
You can set `FOUNDRY_HOME` or use `python run.py --data-dir <folder>` for a different location.
Projects are under `projects/<id>/`, including `state.json`, `source/`, and `snapshots/`.
Download a workspace backup while jobs are stopped. To restore, stop Foundry, back up the
current data folder, and extract the backup’s `projects` folder into that data folder. Never
restore over a running workspace. The backup limit is 100 MB; larger workspaces should be
copied with your file manager. Downloaded app ZIPs contain generated source, documents,
launchers, and a build report; they do not include your workbench `.env` or other projects.
Project IDs are directory names rather than user-supplied paths. The UI shows generated files
as text, never embeds their HTML, and does not automatically launch generated apps.

## Development and checks

```powershell
py -3 -m unittest discover -v
```

The standard-library tests exercise real generated-app subprocesses and HTTP requests, including
an intentionally broken task tracker followed by a repair, approval enforcement, frozen checks,
checkpoints, timeout/cancellation, exports, request authentication, and provider request formats.
Models are simulated in these tests; they do not measure real Ollama generation quality or
verify paid API accounts. Optional browser tests require Playwright and Chromium:

```powershell
py -3 -m pip install playwright
py -3 -m playwright install chromium
py -3 tests/browser_check.py
py -3 tests/browser_release_check.py
py -3 tests/browser_tracker_check.py
py -3 tests/browser_notes_check.py
py -3 tests/browser_arcade_check.py
py -3 tests/browser_planning_check.py
py -3 tests/browser_upgrade_check.py
```

Research and the feature decisions are documented in [RESEARCH.md](docs/RESEARCH.md).

## Troubleshooting

- **Ollama not connected:** start the Ollama desktop app; run `ollama list`. Check OLLAMA_URL.
  The workbench must run on the same Windows computer as Ollama for the default address to work.
- **Model times out / malformed JSON:** try a smaller scope or another instruction/coding model.
  Your available RAM and graphics memory determine speed; only one generation request runs per
  workspace; additional projects queue rather than load competing models.
- **Docker image missing:** run the image pull command above. Docker errors appear in verification output.
- **Checks fail:** inspect the output, files, and acceptance checks. Repair attempts are bounded;
  a failure is not silently labeled working. Retry or restore a checkpoint as appropriate.
- **Port in use:** start with `py -3 run.py --port 8766` and open that port instead.
- **Session expired:** refresh the browser after restarting the workbench.

## License

MIT. This implementation does not include code from the researched projects.
