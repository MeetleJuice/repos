# 0.11.0 — Measured harness research and request observability

This release adds optional character-count, version and digest metadata to actual model attempt records. The build panel shows the latest request size labeled as characters, separately from provider-reported token usage. Existing projects and model routes remain compatible. No extra API requests are made, and prompt/source content is not copied into the new metrics.

Six source-backed research gap memos, a frozen 18-case handoff replay set, three paired prototype comparisons, structured developer guidance, and an independent auditor proposal are included. Research access limits and unverified supplied paper/statistic claims are explicit. `docs/status.md` is the executive report.

Compact JSON and literal Unicode save 3.14% normalized cl100k input tokens on these replays, but no live repair-quality or billed-cost improvement is established. The structured-brief prototype adds cost without measured benefit. **All prompt prototypes remain unpromoted; production inference retains its prior prompt representation, repair limits, source budgets, verification and consent.**

This is an evidence/measurement foundation, not a new autonomous app builder or proof of a higher repair success rate. The next bounded experiment requires paired real-model runs with independently checked defects. No vector database, tree search or autonomous source promotion was added.

Developer replay commands:

- `python tests/benchmark_handoffs.py` checks the frozen dataset and character counts without dependencies.
- For normalized token reproduction only, install `tiktoken==0.12.0` outside the product and pass `--encoding-file` with SHA-verified cl100k_base data. Expected SHA-256 is `223921b76ee99bde995b7ff738513eef100fb51d18c93597a113bcffe865b2a7`; the evaluator rejects mismatches. This optional tool is not a workbench runtime dependency.
- `python -m unittest discover -q` runs the normal suite, including handoff invariants and production non-promotion checks.
