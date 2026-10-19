# Idea Foundry engineering contracts

These rules guide reviewed development of Foundry. They do not authorize messages, deployments, arbitrary execution, or self-modification by the product.

## Environment

Use the existing checkout; do not create a worktree unless the user requests one. The workbench uses Python standard library. `python -m unittest discover -q` is the primary check. Browser checks optionally require pinned Playwright and Chromium; provider tests use fixtures, never real keys. Package with `python package.py`; test the extracted distribution before publishing a versioned release.

## Condition → prevention

- A truncated response is an output-budget failure, not a provider outage. Reserve output explicitly; never fall back to a model with a smaller output ceiling.

- If a model supplies changed Python, placeholder-only contents, or escaped HTML markup → validate before any replacement/checkpoint; give at most one focused response correction. This prevents the observed dashboard placeholder-file corruption.
- If a test imports a real project module such as db.py → inspect that real dependency rather than requiring app.py in every module test. This prevents the observed false-positive static-repair loop; imports alone still do not prove coverage.
- If changing context serialization → preserve exact JSON-decoded values for every frozen replay, including Unicode/source text; compare normalized size and full regressions. Never silently omit files or relabel character counts as provider tokens.
- If changing repair behavior → preserve approved checks, frozen test hashes, source fingerprints, global repair caps, and separate execution/cloud consent. A builder self-report cannot mark verification passed.
- If proposing a scaffold optimization → freeze the baseline and provenance first; record paired outcomes and token costs with unknown values explicit. Replays and cl100k input counts are not live-model repair success or billed cost.
- If a proposed change adds cost without measured benefit → retain its proposal/report for review and leave it out of production. Never let generated apps promote their own scaffold edits.
- If HTTP tests pass for interactive behavior → require actual browser or user evidence before declaring gameplay/UI working. Keep generated files, automated pass, and manual acceptance distinct.

## Research and promotion

Read docs/status.md and the frozen dataset contract before changing the measured handoff path. All eighteen cases are replay scenarios with labeled provenance, not independent historical model builds. No vector database, unbounded retry/tree search, hidden evaluator weakening, or autonomous source promotion. The next proposal lives in docs/research/harness-audit.json and requires a new reviewed measurement cycle.
