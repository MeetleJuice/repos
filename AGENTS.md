# Idea Foundry engineering contracts

These rules guide reviewed development of Foundry. They do not authorize messages, deployments, arbitrary execution, or self-modification by the product.

## Environment

Use the existing checkout; do not create a worktree unless the user requests one. The workbench uses Python standard library. `python -m unittest discover -q` is the primary check. Browser checks optionally require pinned Playwright and Chromium; provider tests use fixtures, never real keys. Package with `python package.py`; test the extracted distribution before publishing a versioned release.

For requested updates, use the normal Update-button delivery path: increment the core version, run `python package.py --release`, validate the extracted archive and publish its versioned ZIP together with `releases/latest.json`. The user expects current and future releases through the existing Update button; a standalone edition ZIP must not be the only delivery path.

## Condition → prevention

- A truncated response is an output-budget failure, not a provider outage. Reserve output explicitly; never fall back to a model with a smaller output ceiling.
- If verification cleanup encounters database/file locks → let the app-owning worker exit before supervisor cleanup. Keep behavioral evidence and classify remaining cleanup errors as environment failures; do not spend application repair calls on them.

- If a model supplies changed Python, placeholder-only contents, or escaped HTML markup → validate before any replacement/checkpoint; give at most one focused response correction. This prevents the observed dashboard placeholder-file corruption.
- If a test imports a real project module such as db.py → inspect that real dependency rather than requiring app.py in every module test. This prevents the observed false-positive static-repair loop; imports alone still do not prove coverage.
- If changing context serialization → preserve exact JSON-decoded values for every frozen replay, including Unicode/source text; compare normalized size and full regressions. Never silently omit files or relabel character counts as provider tokens.
- If changing repair behavior → preserve approved checks, frozen test hashes, source fingerprints, global repair caps, and separate execution/cloud consent. A builder self-report cannot mark verification passed.
- If proposing a scaffold optimization → freeze the baseline and provenance first; record paired outcomes and token costs with unknown values explicit. Replays and cl100k input counts are not live-model repair success or billed cost.
- If a proposed change adds cost without measured benefit → retain its proposal/report for review and leave it out of production. Never let generated apps promote their own scaffold edits.
- If HTTP tests pass for interactive behavior → require actual browser or user evidence before declaring gameplay/UI working. Keep generated files, automated pass, and manual acceptance distinct.

- If exporting verification evidence → compare the actual exported snapshot with its verified source, approved contracts and available bundle manifest. Preserve historical results but never label changed files currently verified.
- If displaying attempt totals → separate retained details, cumulative attempts and actual transport attempts; absent token usage remains unknown. Disclose legacy/history retention gaps.
- If a foundation test passes → also verify intended test-bearing modules were collected. A nonzero total does not establish collection of every module.

- If adding a provider → update the central registry, dotenv aliases, private configuration, redaction, discovery, model controls, route bounds and wire tests together. Missing setup is not a provider outage. No catalogue check proves generation quota.
- If a conservative planner estimate exceeds capacity → a compact schema-complete request may use the unchanged output floor only if input/context/output room permits. Preserve all request data and approval requirements; never override a hard capability or lower the configured floor. Keep truncation recovery bounded.

## Research and promotion

Read docs/status.md and the frozen dataset contract before changing the measured handoff path. All eighteen cases are replay scenarios with labeled provenance, not independent historical model builds. No vector database, unbounded retry/tree search, hidden evaluator weakening, or autonomous source promotion. The next proposal lives in docs/research/harness-audit.json and requires a new reviewed measurement cycle.

- If a pooled planner returns valid JSON with invalid proposal semantics → record schema_error, permit one focused correction per model, then advance without restarting failed models. Keep a bounded job-level attempt allowance and all existing approval/check gates. Automatic routes must use discovered IDs and disclose paid usage; catalogue success is not inference success.

- If a task requests controller-owned documentation → supply the explicit file-ownership contract before coding, preserve the original approved task as data, and direct app-specific notes to APP-GUIDE.md. Never weaken protected-file or acceptance guards. Status animations must follow in-flight requests and clear on every exit; configured/catalogue/responded are different evidence states.

- If presenting workflow progress → distinguish declared coverage, saved-task changes, static inspection, current automated evidence and current manual acceptance. Export-only .foundry metadata must remain outside app source and its manifest; never invent receipts for legacy tasks or silently replace browser model choices.

- If a provider accepts the same saved key from another client but refuses urllib → compare request identity before rotating credentials. Use an honest named application User-Agent in the shared HTTP helper; test discovery and inference paths without exposing provider response bodies or secrets.

- If a generated response echoes a protected artifact → ignore only exact current snapshot text with explicit accounting; changed protected files must still fail atomically. Preserve original approved task data while supplying separate executable instructions and full merged-project character budgets.
- If enforcing a provider timeout → distinguish socket-operation timeout, between-read elapsed checks and hard cancellation. Never promise a whole-job deadline from a socket timeout or leave background requests running after a caller timeout. Exclude explicit batch-only IDs from automatic synchronous routes.

- If changing task decomposition → preserve original approved plans and source; version new task contracts explicitly. Validate earlier-only dependencies, safe bounded file scope and concrete declared outcomes before approval. Enforce changed-file scope before replacement; do not absorb missing features into a final catch-all task. Saved dependencies/criteria are not behavioral test evidence. Any post-approval task-scope change requires a new reviewed plan.

- If balancing cloud and local inference → use an explicitly applied route mode, honor capability/output gates and cloud consent, and keep observed local timing separate from GPU-fit claims. Temporary service/transport circuits must expire/reset and must not classify truncation as an outage.
- If an implementation task needs no changes → require an explicit source-reference response, validate exact excerpts inside approved task files and retain unchanged snapshot receipts. Quoted source supports inspection only; never label behavior verified, skip frozen checks, or invent an edit merely to advance progress.

- If focusing task context → require an explicit reviewed context policy, preserve complete file values and original task data, disclose every available/omitted file and bound source retrieval. Legacy/frozen full-context cases must remain lossless. A retrieval request is neither a write nor proof of behavior.
- If resuming execution → reconcile plan, task cursor and source fingerprint before another implementation request. Retain saved candidates for inspection; stop on ambiguous drift. Explicit source adoption never approves a changed plan, advances a cursor or preserves stale verification. Improvement copies need independent execution records.
- If calibrating local models → require an explicit local-only fixed-fixture action, serialize with inference, store diagnostics outside projects and never infer project/GPU fitness or automatically change routing from two response checks. Milestone receipts cover only their executed approved prefix and recorded source snapshot.

- If adding model setup shortcuts → show separate new-project and current-project routes, preserve explicit browser choices, restore validated manual as well as automatic defaults, and never describe catalogue access as remaining quota. Local-only setup must make no cloud discovery or inference calls.
- If adding notification sounds → keep them optional and muted by default, require a user gesture to unlock playback, preserve visual status, and never use a cue as proof of verification. Historical results and repeated terminal polls must remain silent.
- If applying orchestrated routing → try eligible cloud planner providers in saved order before local fallback; keep the builder route local-only and reject setup without a local model. This is explicit setup, not migration of existing projects or a benchmark of best-model quality.
- If enforcing shared run limits → count model invocations across coding, context retrieval and repair; retain the planner ceiling and repair cap. Legacy/direct histories without a recorded run allowance remain unknown, not retroactively capped. Check cloud consent against the stage's actual route, and keep per-call consent guards for every cloud transport.
- If resolving dependency context → normalize literal project-relative paths, include Python package imports, reject root escapes/remote URLs, and retain complete-file manifests and retrieval bounds. Export task criteria as declarations; related feature checks do not prove each criterion individually.
- If adding a local runtime → use LOCAL_PROVIDERS/uses_cloud consistently, keep its endpoint loopback-only with redirects/proxies disabled, and redact optional runtime credentials. Discovery does not configure the external server's loaded context or prove model fitness.
- If streaming local responses → cap response bytes and in-memory preview size, discard partial output on cancellation/missing completion marker, and close the response in the request worker. Cooperative cancellation is not a hard socket deadline; never save previews as source or verification evidence.
- If advancing a task → reread the approved task and reconcile plan/cursor/source at the finish gate. Static gate receipts do not establish declared behavior. Repeated-call guards must be scoped to a run and exact input identity, leaving changed-context calls and explicit resume available.
- If repairing a pending versioned task → carry its current task packet through every static-repair correction and reject out-of-scope writes before replacement. A later finish gate cannot undo an unauthorized earlier write.
- If splitting planning into stages → checkpoint only validated unapproved stages, bind resume to the complete request identity, and apply the ordinary full-proposal reviewer before approval. Partial outlines never authorize generation or weaken acceptance checks.
- If cooling down a local runtime failure → key the circuit by provider/model, not the entire provider. A timed-out model must not suppress untried installed alternatives; retain output-capacity gates, bounded routes and call limits.
- If sizing guided tasks for local builders → supply actual configured output/context and starter-file facts; validate nested-test package prerequisites and file/interface producer dependencies before approval. Never widen approved task files to repair a planning omission.
- If reporting model limits → distinguish published model ceilings, installed context metadata, configured budgets and unknowns. Generation defaults and community catalogues do not prove deployed maxima/minima or GPU fit. Metadata reads must not generate text or retain modelfiles/templates.
- If a structured builder returns invalid source/JSON or a failed exact edit → bound exclusions to that response-recovery scope; do not confuse content rejection with account/provider unavailability. New task/repair contexts remain eligible within existing run budgets.
- If dashboard Follow is enabled → follow actual recorded activity, including terminal observed events and the latest event after layout/re-enabling. Verify viewport geometry, not just checkbox state; never animate an invented execution path.
- If validating an evidence_v1 proposal → require meaningful sample data/assertions, stable API contracts and correctly placed ready checkpoints; exact empty results use json_equals. Apply new policy only to explicitly selected proof drafts, never silently rewrite approved legacy checks.
- If a milestone fails or its verifier raises → keep the cursor on the unverified task, retain its scope through every repair/static correction, and seal the restored cursor only after success. A checkpoint receipt never authorizes future-task writes.
- If exporting diagnostics → use the shared structural event projection before persistence and on legacy import; omit free-form prompts, source, journal/model prose and user notes. Preserve event IDs, unknowns and retention gaps. Hashes detect accidental corruption, not malicious same-user host rewriting.
- If compiling new guided tasks → let the model design one feature's semantic work and let the controller assign dependencies/references/check prefixes before approval. Preserve check order/content; reject unschedulable evidence outlines instead of weakening checkpoints. Bound each stage and retain validated draft work on interruption.
- If running system tests → keep fixed probes separate from project inference, require explicit cloud consent, serialize with jobs/updates, and never alter routes or cooldown decisions from a tiny fixture. Export persisted results with Test IDs; catalogue access and probe success are not project fitness. Do not run generated code or repository shell tests from the diagnostic button.
- If handling console shutdown → tolerate supervisor/child interrupt delivery during cleanup; allow a Windows child its graceful interval before forced termination. Keep independent launcher evidence outside application imports.
