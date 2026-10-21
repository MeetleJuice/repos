# Idea Foundry v0.31.0 — Master Diag

This update adds evidence collection around the existing software factory. It
does not change approved requirements, acceptance checks, model routes or the
meaning of saved/static/automated/manual verification.

## Update and first use

1. Finish or stop any active job. In Foundry press **Update**, check for the
   release, then install v0.31.0. Keep the launcher window open while it restarts.
2. Confirm v0.31.0 appears in the workbench. Your projects and private key file
   remain in their existing workspace.
3. Open the project that failed, then press **Diag** in the top toolbar. Wait for
   the local investigation. It reads available evidence and local health data;
   it does not run your app, tests, inference or cloud-provider checks.
4. Read the findings and coverage. Press **Download diagnostic ZIP**. This uses
   the displayed report snapshot. If that snapshot is unavailable after a server
   restart, a new collection is made; its timestamp identifies the new snapshot.
5. Open `START_HERE.md` in the ZIP and review the contents before sharing. Attach
   the ZIP to this conversation, with one sentence explaining what you expected
   and what happened. Nothing is uploaded to GitHub or a provider automatically.

To test **Generate Idea**, open **New project** and click the small button beside
the idea field. It uses an installed Ollama model from your current or saved
model selections, including configured local fallbacks. It makes one bounded
request and inserts an editable prompt. It does not start planning, create a
project or write project files. Existing text requires confirmation; text edited
while the request is running is preserved. Finish active jobs first.

## What Master Diag records

- Controller events with the same ID and run/project correlation as Dashboard
  history: model attempts, budgets, reported tokens/timings, retries, task gates,
  file manifests, checkpoints, inspection, verification and completion.
- Lifecycle and exception class/frame metadata without exception text or source
  lines; HTTP errors and failed file operations; successful operations as well
  as failures.
- Update checks, verified downloads, installation, pending health checks and
  independently observed launcher/rollback outcomes.
- Slow hardware samples: host CPU counters, process CPU/RSS, memory, free disk,
  and optional NVIDIA GPU/VRAM data from `nvidia-smi`. Missing measurements stay
  unknown. These measurements do not establish that a model fits the GPU.

The private SQLite recorder is outside generated project directories at
`diagnostics/flight-recorder.sqlite3` under Foundry's data home. Default retention
is 14 days, 20,000 events and 32 MB of event payload; SQLite storage has a separate
page ceiling. Independent launcher logs keep the current and prior 1 MB segment.
Retention, omitted records, failed writes and legacy gaps are reported. Export
does not erase local evidence. A recorder failure does not change a build result.

The diagnostic ZIP includes structured evidence, classified findings, application
and packaged source identity, current-versus-historical verification status,
coverage limitations and an exact SHA-256 member manifest. Source ZIPs have no
Git checkout: `forge/build-info.json` records the commit and source-byte digest at
packaging time, with dirty state explicit.

## Privacy and evidence boundaries

Default exports exclude `.env` files, environment values, credentials, generated
source, original prompts, model transcripts, manual notes and raw test/journal
prose. Free text is represented by lengths/digests; bounded structured symptoms,
exception locations, test counts/exit codes and path-redacted command templates
remain available. Review structural metadata before sharing it too.

The Dashboard still observes actual recorded controller history. Diag compares
retained event IDs and reports duplicate/time-order/retention gaps; it cannot
prove what a particular browser displayed or infer unrecorded transitions.

Hash checks detect accidental corruption within retained records. They are not
signatures. Trusted-local generated code has the owner's OS permissions; folder
separation cannot prevent malicious same-user rewriting. Existing Docker
isolation is the stronger execution option.

## Windows desktop verification

On a Windows startup, Foundry attempts to install a current-user **Idea Foundry**
desktop shortcut using the existing mascot icon. It targets a private stable
launcher rather than a version-specific server. The original folder and prior
launcher copies are retained for recovery. A shortcut failure is recorded and
does not disable `Start-Foundry.bat`.

Verify these locally; Windows shell integration was tested with mocks, not a
physical Windows desktop:

1. After updating, confirm the desktop shortcut and mascot appear.
2. Leave Foundry running and double-click the shortcut. It should open the
   existing instance instead of starting a second server.
3. With no active job, focus its console and press **Ctrl+C**. Allow shutdown to
   finish. Closing a browser tab alone does not stop Foundry.
4. Double-click the shortcut again. Confirm your projects remain, then export a
   Diag report and check that launcher/startup history is present.
5. Keep the original program folder. If shortcut creation fails, launch its
   `Start-Foundry.bat` and send the diagnostic ZIP; do not delete version folders
   or edit update pointers to experiment with recovery.

## Validation scope and next step

The release validation record contains executed commands and outcomes. Fixtures
exercise malformed output, unavailable runtime, failed source writes, abrupt
startup failure, interruption, secret exclusion and export integrity. Actual
Linux subprocess tests exercise startup, duplicate-instance handling, shutdown
and failed-update recovery. Browser tests exercise the UI with fixture model
replies; the protected SQLite delivery test still runs the generated application.

No live provider generation, owner's Windows/GPU model calibration or Docker
execution was established here. This is an observability/reliability foundation,
not a measured improvement in live-model repair quality.

The next development gate is one diagnostic ZIP from a real failed run and one
from a real successful run. Use them to identify the failed stage, attempt class,
task scope, source snapshot and evidence gaps before changing planning/routing.
