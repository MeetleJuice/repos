# Idea Foundry engineering contracts

These rules guide reviewed development of Foundry. They do not authorize messages, deployments, arbitrary execution, or self-modification by the product.

## Environment

Use the existing checkout; do not create a worktree unless the user requests one. The workbench uses Python standard library. `python -m unittest discover -q` is the primary check. Browser checks optionally require pinned Playwright and Chromium; provider tests use fixtures, never real keys. Package with `python package.py`; test the extracted distribution before publishing a versioned release.

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
