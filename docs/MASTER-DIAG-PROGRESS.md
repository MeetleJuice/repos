# Master Diag implementation — v0.31.0

## Frame

Goal: add persistent, privacy-conscious operational evidence and a Codex-ready diagnostic export without changing approved project behavior.

Scope: diagnostic/idea/desktop modules; existing core/server/history/update integration; workbench UI; Dashboard event/source maps; focused tests, validation tooling, release documentation and versioned distribution.

Acceptance: focused diagnostic, privacy, lifecycle, idea and recovery tests; existing complete unittest suite; workbench/Dashboard browser checks; strict checks on typed modules; validated extracted release and the existing Update-button delivery path.

Stop: ship the verified release and document untested Windows/live-model behavior. No autonomous self-modification, new provider/framework, silent cloud use or changed frozen project checks.

## Decisions

- Reuse controller events and exact history IDs; diagnostics live outside generated projects.
- The recorder is best-effort and bounded. A recorder failure must not turn a successful build into a failed build.
- The independent stable launcher retains process/startup/update evidence. Same-user host code is not a security sandbox; hash checks detect corruption, not privileged forgery.
- Diagnostics inspect recorded facts and safe local health endpoints. They do not run generated code, inference, test suites, cloud requests or updates.
- Export excludes project source, prompts, environment values and model transcripts by default. Missing evidence remains explicit.
- Generate Idea makes one bounded local request, never submits a project, and must preserve text edited during the request.

## Progress

- Baseline: clean checkout, v0.30.0 / `6a4ca4b`.
- Repository discovery confirmed existing project JSONL history, attributed events, attempt timings, source-bound verification, Dashboard observer and supervised update rollback.
- Confirmed gaps: no independent global recorder/retention; unexpected HTTP errors currently lose exception details; no reviewed diagnostic export or desktop shortcut.
- Implemented independent SQLite flight recorder, shared history IDs, bounded privacy projection, resource sampling, safe collector/manifest ZIP, two UI entrypoints, metadata-only crash supervision, desktop launcher and source packaging identity.
- Review corrected arbitrary prose leakage, lost exception frame metadata, omitted independent launcher history, retention completeness, and repeated-interrupt cleanup. Unknown check names/query samples are excluded; task scope and source/command evidence stay structural.
- Sealed source: `python -m unittest discover -q` — 489 tests /133.609s, OK. All 22 workbench browser scripts passed; Dashboard Chromium/launcher and four Node simulation tests passed. Strict mypy checked 32 modules. Browser/model replies are fixtures; generated-app behavior and supervisor recovery run real disposable processes.
- Primary-source research and access failures: `docs/research/v0.31/REPORT.md` and `sources.json`. Ten official files retrieved; blocked articles were not claimed read.
- Independent final review found no remaining release blocker; 30 diagnostic/integration/supervisor tests passed in 3.113s.
- Source implementation complete. Remaining release work: commit a coherent source milestone, package with that commit identity, validate extracted distribution, publish immutable ZIP/manifest, verify public Update delivery. The release validation file records the final archive checks outside the archive to avoid self-reference.

## Verification boundary

No Windows shortcut, actual owner's GPU, live provider quota or local-model quality is established by this cloud environment. Physical Windows verification will be documented.
