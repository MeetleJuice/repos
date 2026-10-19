# Completion process audit — frozen before implementation

Baseline: v0.12.0, e6b0726. User evidence: Reading List accepted HTTP behavior, including independent restart persistence, then failed deleting reading_list.db on Windows. Generated tests and launch were unrun. Builder truncation also required a manual resume. These are reliability failures; no live-model quality improvement is asserted.

Frozen cases: tests/fixture_data/completion-process-v1.json, SHA256 211c250505291c37288837021c0712b261ed5eb63bce34a05b3a1597d95a1312. Unknown live usage/cost remains null.

## Blueprint

1. Verification supervisor owns disposable directories; application/test workers exit before cleanup. Retain behavior evidence if cleanup fails, label environment failures, and never spend model repairs on them. Retry transient cleanup a bounded three times.
2. Extend explicit output reservation and at most one continuation plus one compact fresh response to builders. Bound supported Gemini thinking separately. Never write partial JSON or downgrade output capacity on truncation. Ordinary outage fallback remains configured and consented.
3. Show phase counts and distinguish behavior success from cleanup failure. Verify with controlled provider responses, real generated-app subprocesses, the full regression suite and extracted release. Preserve approval, frozen checks, project state and manual acceptance.

## Primary-source research

- CPython 3.13 sqlite3 documentation: https://github.com/python/cpython/blob/3.13/Doc/library/sqlite3.rst — the connection context manager commits/rolls back but does not close the connection. A controller cannot assume a completed with block released native handles.
- CPython 3.13 subprocess documentation: https://github.com/python/cpython/blob/3.13/Doc/library/subprocess.rst — timeouts require terminating and waiting for children; process lifetime is the reliable ownership boundary.
- CPython 3.13 unittest documentation: https://github.com/python/cpython/blob/3.13/Doc/library/unittest.rst — discovery/importability and actual executed test counts matter, not a model's claim.
- mini-SWE-agent controller: https://github.com/SWE-agent/mini-swe-agent/blob/main/src/minisweagent/agents/default.py — keep model, controller and execution responsibilities inspectable and bounded. No extra agent loop or dependency is needed here.

Sources fetched from upstream raw GitHub on 2026-10-19. Windows reproduction uses a handle-lifetime regression plus CI coverage; this Linux environment cannot prove a native Windows run. Provider responses are fixtures, not generation-quota or model-quality evidence.

Fixture clarification: controlled builder response bodies were added before release validation, derived from the existing APP fixture. No historical provider response is represented by those bodies.

## Full path reviewed

| Stage | Existing strength retained | Change / remaining constraint |
|---|---|---|
| Model setup | Private key import, catalogues, ordered explicit routes, cooldowns and consent | Native bounded reasoning for supported builder profiles; catalogue access still does not prove generation quota |
| Proposal | Schema/feature coverage review, bounded planner corrections, output-ceiling guard | Preserved full approval artifact; no IDs-only plan replaces requirements |
| Approval | Frozen checks and checkpointed requirements | No schema migration or automatic re-approval |
| Generation | Sequential saved tasks, validated atomic file/edits, single malformed-response correction | Added bounded truncation recovery; partial source cannot land; 36K project source constraint remains |
| Static inspection | Real project-module imports and syntax/structure checks | Added nested-test package/importability check to avoid silently uncollected tests |
| Execution | Separate execution consent, Docker isolation or explicit trusted-local mode | Supervisor owns temporary directories; application-owned handles die with each phase worker |
| Repair | Shared global repair cap; immutable accepted checks and frozen tests | Workspace failures remain environment failures, retain behavior evidence and consume no app-repair requests |
| Acceptance | Source-bound automated evidence and explicit manual/browser checks | Actual counts/cleanup displayed; no synthetic HTTP checks stand in for UI gameplay |
| Recovery/export | Checkpoints, backup/restore, ZIP launchers and reports, stable private workspace | Preserved formats; tested exported files and updater using real browser with fixture providers |

The update does not remove provider uncertainty, the small-project source bound, or the need to try generated UI behavior. Broader template/decomposition changes require separate source-bound live outcomes rather than assuming more orchestration improves results.
