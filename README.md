# Idea Foundry

**Describe an idea. Approve a proposal. Generate, test, and repair a small working Python web app.**

An original, local-first Python workbench for Windows and VS Code. Ollama is the default;
Groq, OpenRouter, and Gemini are optional. No Python packages need installing for the workbench
or its generated apps. Python 3.11 or newer is required.

## Try the repaired Task Tracker

The corrected first app is included in **examples/task-tracker**. Open that folder and
double-click **run.bat**, then open `http://127.0.0.1:8080`. It works independently of
Idea Foundry and does not need Ollama. See that folder's README for details.

## Update an existing Windows copy

The GitHub repository, this cloud checkout, and your Windows folder are separate copies.
Changes on GitHub do not automatically update a ZIP you already extracted.

Download the latest repository ZIP, extract it into a **new folder**, and stop the old
workbench with Ctrl+C in its terminal. Copy the old workbench's `data` folder into the new
workbench folder to retain projects; also copy your local `.env` if you created one.
Keep the old folder as a backup. Start **Start-Foundry.bat** from the new folder and refresh
your browser. Do not overwrite or delete `data` to update the application code.

Existing approved projects remain usable. **Generate / resume code** now checks Python
syntax and missing tests without executing the app; it can ask the model for bounded repairs.
Approved requirements/checks and existing test files stay frozen. New proposals must explicitly
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

5. Open `http://127.0.0.1:8765` in your browser. Keep the terminal open while using the app.

Linux/macOS: run `python3 run.py`. To use another port: `python run.py --port 8766`.
The workbench binds only to this computer. It is not intended to be exposed on a network.

## Your first build

1. Try: “Build a task tracker with saved tasks and a list of unfinished tasks.”
2. Choose the planner and builder models, then click **Shape my idea**.
3. Read the proposal, scope, ordered tasks, and HTTP acceptance checks. Revise it if needed.
   You can edit the JSON directly before approval.
4. Click **Approve this project**. Requirements and acceptance checks are now frozen.
5. Click **Generate / resume code** to create files without executing them. Python syntax,
   the server factory, and test-file structure are inspected first, with bounded text-only repairs.
   **Files ready · not tested** means static inspection passed; behavioral verification is still pending.
6. Review the generated files. Select an execution runtime, explicitly approve execution,
   and click **Build, test & repair**. If code is already generated, it starts with checks.
7. Read the results. Download the app ZIP, extract it, and open it in VS Code.
   Its README and run.bat explain how to launch it.

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

Copy `.env.example` to `.env` in this folder, enter keys locally, then restart the workbench:

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
be sent to the selected providers, with possible charges. There is **no automatic paid fallback**.
Ollama model discovery reads your actual `/api/tags` list. Embedding models should not be used
as planner/builder models.

## What this first version does—and its limits

- Generates small standard-library Python web apps, with a browser UI and optional SQLite storage.
- Creates a project guide (`PROJECT.md`), `TASKS.md`, launch scripts, and frozen `CHECKS.json`.
- Breaks the build into ordered model calls, passing the approved proposal and current source.
- Runs generated `unittest` tests plus fixed health, home-page, and approved behavioral HTTP checks.
- Requires at least one executed generated test; failures, skipped tests, and expected failures
  do not pass verification. Repairs cannot change approved checks or existing test files.
- Makes at most three model-assisted repair attempts per run, shared between static fixes and runtime fixes, then reports a blocker.
- Preserves progress, checkpoints, verification logs, and an exportable build report.

This is a first working foundation, not a promise to build any app from any prompt. It does not
train models, rewrite its own code, deploy to the internet, install project packages, or run a
visual browser test of each generated app. Generated tasks are applied sequentially; full tests
run after the task list is complete. Passing checks proves only the covered behavior. Model-written
tests may be weak: inspect the approved acceptance checks and try the result yourself. There is
no automatic quality scoring or model-learning system yet. Changing approved scope currently
means creating a new project. Source is limited to 36,000 characters to fit smaller local models;
large ideas should start with a smaller version. Generated apps must implement the fixed contract
described in [the architecture](docs/ARCHITECTURE.md).

## Your files

Projects live in `data/projects/<id>/`, including `state.json`, `source/`, and `snapshots/`.
Back up `data/` to preserve your work. Downloaded app ZIPs contain generated source, documents,
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
```

Research and the feature decisions are documented in [RESEARCH.md](docs/RESEARCH.md).

## Troubleshooting

- **Ollama not connected:** start the Ollama desktop app; run `ollama list`. Check OLLAMA_URL.
  The workbench must run on the same Windows computer as Ollama for the default address to work.
- **Model times out / malformed JSON:** try a smaller scope or another instruction/coding model.
  Your available RAM and graphics memory determine speed; only one generation request runs per
  project, but starting several projects may still load competing models.
- **Docker image missing:** run the image pull command above. Docker errors appear in verification output.
- **Checks fail:** inspect the output, files, and acceptance checks. Repair attempts are bounded;
  a failure is not silently labeled working. Retry or restore a checkpoint as appropriate.
- **Port in use:** start with `py -3 run.py --port 8766` and open that port instead.
- **Session expired:** refresh the browser after restarting the workbench.

## License

MIT. This implementation does not include code from the researched projects.
