# 0.25.0 validation and evidence boundary

## Before / after

The new frozen `local-harness-v1.json` is synthetic protocol/controller evidence, SHA-256 `05390e0eac52362487e72791d4ddadd59c972826561c0023c0a2d24662702d96`. Before implementation, the runtime route failed configuration validation and its insufficient-context reservation was incorrectly accepted. After implementation, 15 focused local-harness tests pass, including real loopback discovery/inference, redirect refusal, NDJSON/SSE parsing, bounded output, real HTTP cancellation, checkpoint/scope gate, repeated-call stopping, private key handling and update readiness.

The manual Ollama planner regression initially failed before inference with `Planner output reservation exceeds the model output/context budget`. Its existing low configured floor now reserves at least 8192 output tokens when context permits; builder caps remain unchanged. Insufficient context still stops before transport. The ledger records the actual requested output budget.

## Checkout checks performed

- `python -m unittest discover -q`: **380 tests passed in 119.333 seconds** on the final Python implementation.
- `python -m unittest tests.test_local_harness -q`: **15 passed**.
- Strict mypy over the 25 modules listed by `tools/validate.py`: **no issues**.
- Initial complete browser pass: **17 flows passed**. The subsequently added discovered-model dropdown passed the local-harness browser flow, including reload persistence, actual local SSE output, safe scoped Stop, finish receipts, actual generated-app execution/export and the update-ready banner.
- `git diff --check`: clean.

The new cancellation fixture's initial event-order race was corrected without removing cancellation assertions. Existing unit/browser status tests now expect the added local runtime row and identify the embedding row by ID, retaining secret-redaction/state assertions. No frozen acceptance fixture was edited, skipped or weakened.

## Distribution/publication gate

Before publication, extract the exact versioned archive; rerun all 380 unit tests and all 17 browser flows against that extraction. Compare archive source/test/doc bytes to the checkout, verify its checksum with the production updater, and read the published manifest/archive back through the updater's transport. Record those final outcomes in the release commit. Earlier release ZIPs are immutable.

## Limits

Models return deterministic fixtures in these checks. The generated app really runs HTTP, unittest and launch checks; Chromium exercises the workbench. These facts do not measure live model coding quality, quota, billed cost, Windows behavior, GPU fit or best-model ranking. LM Studio/llama.cpp protocol compatibility is tested with a local HTTP fixture, not an installed model runtime. Streaming is opt-in and local only; cancellation remains cooperative. Finish receipts prove static controller consistency, not each declared criterion's behavior.
