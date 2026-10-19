# 0.14.0 — Workflow history and evidence integrity

The app now makes its recorded work inspectable from planning through export, and stops stale verification evidence from certifying changed files.

## What changed

**Durable project history.** Each planning/build/repair job has a run ID. Structured local records cover job starts/finishes/interruption, model attempts, controller journal messages, model-written summaries, checkpoints, committed file hashes, static inspection, task progress, verification results, manual observations and export preparation. Model reports, controller results and user observations are attributed separately. Export preparation is not a claim that the browser successfully saved the file.

Open Build & results → Project history → Refresh history. The panel shows the most recent 200 records; Download history JSON and RUN-HISTORY.json in the app ZIP include all available records. Recent journal and model-detail windows remain limited to 300 and 100. New cumulative totals survive those windows. Older retained records are imported once and labeled incomplete; lost historical details cannot be reconstructed. History is capped at 16 MB per project. Write/parse failures, partial records and limits are disclosed, never silently labeled complete. Existing app files are preserved when history fails.

**Honest inference accounting.** A controller attempt can fail a budget/key check before transport. The UI now calls these model attempts, and records adapter transport attempts separately. A transport attempt does not prove provider receipt or billing. Missing provider token counters remain unknown. Legacy counts are lower bounds. No live model-quality or cost gain is claimed.

**Source-linked export.** BUILD-REPORT.json keeps its existing fields and adds report schema 2, original idea, approved plan, recent journal/attempts, cumulative totals, current-vs-recorded status, history coverage and per-file SHA256/UTF-8 byte counts. New successful verifications also retain a full selected-file manifest, detecting later launcher/document changes. Older evidence can compare implementation and approved contracts but has no historical full bundle manifest; this limit is explicit. Changed implementation, protected tests or checks cannot inherit a current verified label. Historical pass output remains available and labeled historical. File hashes identify bytes; they are not a signature or correctness proof.

**Verification collection guard.** Modules containing test definitions must be represented in the actual discovered unittest suite. Passing foundation tests can no longer mask an entirely uncollected test-bearing module. unittest.FunctionTestCase/load_tests remain supported. This is a collection guard, not proof that every requirement or branch has a test.

**UI and limits.** Generic manual-testing wording replaces game/shield-specific text. Recent windows, unknown usage and history limitations are labeled. The 36,000-character implementation and 70,000-character total project limits remain and are described accurately for cloud and local builds. No automatic framework expansion or hidden scope reduction was added.

## Compatibility and privacy

Project state remains schema 2. Existing projects, starter families, checkpoints, approval/check contracts, model routes, repair limits, manual evidence, backups and launchers remain supported. New history lives outside generated source and model context. The ZIP root remains generated-app/. Its two metadata filenames are reserved against model overwrite. Generated app databases/private workbench .env files are not bundled by the source-file exporter. Existing workspace backup includes project history.

History stores structured metadata and journal messages, not full provider requests/responses or source bodies. The report contains project requirements and saved user notes. Known currently loaded provider key values are redacted from history/report metadata; this is not a general secret scanner for generated source. This local history is not an authenticated OS audit or a transcript of every internal model thought.

## Update and test

1. Back up via Workspace & backups, then Update → Check → Install and restart. Alternatively extract the new ZIP into a fresh folder and run Start-Foundry.bat.
2. Open Pocket Creature. Existing generation remains saved. Open Project history: older events should be labeled imported; no missing history should be invented.
3. Run verification with your chosen runtime, explicit consent and zero repairs first. The new pass records a file manifest. Complete actual manual checks if still pending.
4. Open/refresh history. Confirm distinct model/controller/user records and run IDs. Download the history JSON.
5. Download the app ZIP. It should contain BUILD-REPORT.json and RUN-HISTORY.json beside the app and launchers. Report status must reflect the current evidence, including pending manual acceptance.
6. Run the app and check saved state/controls as before. Keep your existing working folder until the new download is tested.

## Research, validation and next pass

See research/workflow-audit-v1.md and research/workflow-results-v1.json for frozen cases, primary sources, actual checks and limitations. Native Windows execution and live provider performance are not inferred from Linux/fixture tests. Next priorities are observed Windows trial results, task-size/scaffold improvements supported by source-bound live outcomes, and more useful browser behavior contracts without adding unbounded agent loops.

Release validation passed: **258 tests** from the extracted ZIP on Linux Python 3.13, **22 dedicated history/integrity regressions**, a **50-test focused evidence/history/handoff run**, strict typing across **14 modules**, and both real Chromium workflows. Browser export checks include external source changes, stale evidence and per-file ZIP checksums. Fixture providers do not establish live quota, pricing or model quality.
