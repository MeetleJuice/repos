# Idea Foundry 0.5 — a dependable local build studio

This release preserves proposal approval, source-only generation, explicit execution consent,
protected acceptance checks, local models, saved projects and standalone exports.

## Install on your Windows computer

1. Keep your working standalone Notes App folder.
2. Stop the previous Foundry terminal with Ctrl+C.
3. Download Idea-Foundry-0.5.0.zip and extract all files into a new folder.
4. Double-click Start-Foundry.bat. Keep this folder as your stable launcher.
5. Check Workspace & backups: version 0.5.0 and your existing projects should appear.

Windows 0.3/0.4 projects remain in Local AppData; do not copy another data folder over them.
Older legacy folders use the existing non-destructive import. Program-folder .env files must
be copied separately when manually moving between downloaded folders; never upload them.

## Updates after this installation

Click **Update → Check for updates → Install & restart** when a newer release is available.
If you already have the latest version, there is nothing to install. Keep the terminal open.
The browser reconnects with a fresh session token after restart.

The updater downloads the fixed repository's published versioned ZIP, verifies its SHA256,
checks archive paths, version, Python requirement and supported data format, then saves a
workspace backup. It installs into `<data folder>/updates/versions/<version>` and atomically
changes a small active-version pointer. It never rewrites the running program or project files.
The original downloaded program folder remains the fallback and startup launcher.

The supervisor checks the new server's version and unique startup identity. A failed startup
returns to the previous program. No project-data migrations ship in 0.5; incompatible data
formats are refused. A backup is kept under updates/backups, separate from API settings.
Active jobs block installation. Keep credentials in the data .env for the most portable setup;
the original program-folder .env remains a fallback when launched through its stable launcher.

Integrity is anchored in HTTPS and control of the configured GitHub repository. The updater
is not a signed/TUF update system and does not claim protection against repository compromise.
It downloads only on request, never publishes code or syncs generated projects to GitHub.

Recovery: stop all Foundry terminals before touching updates/current.json. If necessary,
rename that pointer to current.disabled.json and launch the original 0.5 folder. Keep the
installed version directories and backups until the problem is understood. Automatic rollback
keeps the failed version for inspection; it does not overwrite/reinstall that same version.

## Smarter generation and repair

- Explicit, versioned Python foundation, Notes and Tasks starters; no template is retrofitted
  into an existing saved project. Approval still defines the app's actual intended scope.
- Foundation regression test protects server startup, health and HTML. Additional feature tests
  remain editable until verification, with trusted/parent tests protected as before.
- Repository symbol maps accompany generation and repair. Full small-project files remain
  available, rather than dropping unseen dependencies or silently truncating source.
- Repairs receive failed phase, concrete evidence and focused traceback text. Newly repaired
  source is statically inspected before another execution. All repairs share the selected cap.
- Identical source returned by a repair stops the loop before repeating full verification.
- Known invalid email and urllib calls from the user's second Notes App upload are rejected.
- Edited/missing approved CHECKS.json stops generation without spending repair requests.
- Optional task.check_indexes runs an approved check prefix after a runnable task. Checks use
  fresh data and the chosen runtime; source-only generation never runs them. Failed milestones
  receive bounded repairs before later tasks. Exhaustion preserves the unfinished task position.
- Export reports include generator/starter provenance and milestone evidence. PROJECT.md now
  explains scope, architecture, build order, acceptance criteria and remaining considerations.

## Interface

A permanent Update button, searchable project list, reviewed starter selector, readable text,
consistent spacing, responsive dialogs, keyboard focus, reduced-motion support and concise build
activity. Full logs remain expandable. Missing Docker is explained before attempting verification;
local execution is never silently selected. Consent resets on changing projects or regenerating.
Local result summaries are descriptive, not a quality leaderboard.

## Scope and evidence

Core operation still uses only Python's standard library. Node and Playwright are development
validation tools, not installation requirements. Docker remains optional for the workbench and
recommended for isolated generated-code verification. Trusted local execution is not a sandbox.

The release is checked with unit/integration tests, real application HTTP requests, actual
supervisor processes, Docker verification, browser interaction and a freshly extracted package.
See VALIDATION.md for results. Model replies in automation are scripted; this environment cannot
reach the user's Windows Ollama, and passing these tests does not establish universal 7B-model
success. No live paid inference or Windows execution is claimed by the cloud checks.

Browser preview/visual generation tests, generated-project GitHub sync, arbitrary frameworks,
deployment, model training and autonomous edits to Foundry itself remain separate future work.

## Publishing the next update

Bump the application version, update the release notes, run the regression/browser checks, then
run `python package.py --release`. Commit the new `releases/Idea-Foundry-<version>.zip` and
`releases/latest.json` with the matching source. Published versioned archives must not be replaced;
a fix needs a new version. The packager refuses a different ZIP under an existing version name.
The manifest's schema 1 promises the stable launcher's `--server`, exit-75 and readiness-file
protocol, and data schema 2 compatibility. A release changing either protocol must use a new
manifest schema and require a manual launcher/data upgrade rather than pretending compatibility.
