# Idea Foundry 0.3 — from a generator to a project workbench

This release focuses on the user's actual journey: understand the next step, keep the
original working version, request improvements, recover from failures, and update safely.

## Shipped

- Project next-step guidance and human-readable HTTP acceptance cards.
- Linked improvement projects with a new approval cycle, retained baseline features/checks,
  and immutable existing test files. Changes can add new tests.
- Per-project model editing; embedding models rejected as builders/planners.
- One inference request at a time across the workspace, cancellable waiting jobs, request counts/timings.
- Per-task Python syntax inspection and shared bounded static/runtime repairs.
- Transactional source updates, recoverable failed swaps, checkpoint diffs, and corrupt-project isolation.
- User-visible workspace location/version and a private project-backup download.
- Windows user-data separation and non-destructive copying of missing legacy projects.
- Process-level workspace locking.
- Docker readiness checks before model calls, and environment errors separated from application repairs.
- New generated-app launchers with readiness polling, free-port selection, browser opening, and child cleanup.

## Validation

46 automated standard-library tests passed in the Linux cloud workspace. They run real
generated-app subprocesses and HTTP requests, with scripted model replies. Browser checks
exercise the guided build, model switching, approved change, preserved original app, diffs,
backup download, and desktop/mobile layout. Docker execution is checked separately.
Live inference against the user's Windows Ollama and paid APIs remains unverified here.
The Windows/Linux CI workflow is provided; this document does not claim a completed Windows CI run.

## Deliberate remaining scope

Generated projects still use the Python standard library and the fixed app/server/test contract.
Behavioral checks run after all implementation tasks; intermediate milestones check syntax only.
The workbench does not host live previews of untrusted apps, deploy, install generated dependencies,
train models, automatically rank them, or rewrite itself. Browser automation tests the supplied
workbench/example workflows, not every arbitrary app a model might generate. These are material
boundaries, not hidden success claims.

## Updating

See the main README. Keep the old folder, extract into a new one, and copy the old data folder
beside the new program for the first migration. Windows imports missing projects to Local AppData;
existing project IDs are never overwritten. Subsequent updates reuse that user-data folder.
Back up from the Workspace dialog before updates. Keep .env separately and never send API keys.
