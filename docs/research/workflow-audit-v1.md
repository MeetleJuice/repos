# Workflow audit and blueprint — v0.14.0

Baseline eeba116 / v0.13.0. Frozen before implementation on 2026-10-19. No live-provider keys are needed for these deterministic controller defects.

## Reproductions and priorities

1. `model_calls` retains only 100 entries and `events` only 300. UI/workspace totals sum the retained slices without stating retention; repeated jobs silently undercount.
2. Export copies status/checks from saved state without comparing the exported implementation or protected acceptance files against the verified contract. External source/check edits can inherit a stale `verified` label.
3. Export omits full journal/model ledger and the identity of each build/verification run, frustrating an end-to-end reconstruction.
4. A successful foundation test can mask a second module containing uncollected test functions. Current nonzero total and app-call checks do not prove that intended module ran.
5. Generic gameplay/shield UI wording appears for non-game apps. Model-written success summaries sit beside controller evidence without attribution. Size rejection gives a generic local-model message even for cloud projects.

Frozen fixture: tests/fixture_data/workflow-audit-v1.json. These are controlled baseline cases, not a live model-quality benchmark. Pocket Creature's observed size rejection is genuine; its recovery passed. Existing fixed 36K implementation /70K total character constraints remain intentional and must be named accurately.

## Research and design

- OpenTelemetry logs data model: https://github.com/open-telemetry/opentelemetry-specification/blob/main/specification/logs/data-model.md — timestamps, event identity and trace correlation separate events from unstructured messages. Adopt local run IDs and attributed structured records; no service/SDK dependency.
- CPython JSON documentation: https://github.com/python/cpython/blob/3.13/Doc/library/json.rst — JSON is not framed; repeated dump calls do not form one JSON document. Use explicit newline-framed records, validate reads, expose partial/capped history rather than silently claiming completeness.
- CPython unittest documentation: https://github.com/python/cpython/blob/3.13/Doc/library/unittest.rst — discovery produces suites of actual test cases. Compare intended test-bearing modules against collected cases; preserve app-call and success checks.

Primary sources fetched from upstream raw GitHub on 2026-10-19. Output evidence follows existing source-fingerprint/frozen-contract principles. A file checksum identifies bytes; it is not a security signature or proof of app correctness.

## Implementation blueprint

- Append bounded, structured project history outside generated source. Record job lifecycle, model attempts, controller messages, model summaries, file changes, inspection, verification and manual observations. Recover available legacy records with explicit incomplete provenance; do not fabricate missing history. Report malformed/truncated/full histories honestly.
- Add run identity and cumulative request statistics while retaining small state/UI windows. Label imported legacy counts as lower bounds. Persist metadata only: no provider transcripts or prompt/source copies in the new history.
- Build exports from one stable file snapshot. Include file digests, full available history, recent ledger/journal and current-vs-recorded evidence status. A stale source/contract must never retain an effective verified label. Preserve existing report fields/formats; add schema-versioned evidence fields.
- Add a history panel and download control, clear attribution and counts, source-evidence freshness checks and truthful scope-limit messages. Keep history out of model context and implementation size budgets.
- Reject uncollected test-bearing modules even when foundation tests pass. Cover with an actual unittest discovery regression.
- Preserve state schema 2, approvals/frozen tests/checks, runtime/cloud consent, checkpoint/restore, existing ZIP entry root, and bounded repair behavior. No new agents, provider, framework, live model optimization or autonomous Foundry source modification.

## Release gates

Frozen defect regressions; full unit/integration suite; strict typed modules; Chromium generation/verification/export/history flows; extracted distribution on Python 3.13; public updater checksum/extraction. Native Windows and live model quality remain unclaimed unless separately observed.

## Additional findings during implementation

Preflight budget/key failures were included in the UI's request count even when no transport was attempted. New metadata distinguishes controller attempts, adapter transport attempts and unknown legacy/custom-client transport status. Transport invocation does not prove receipt or billing. The retained `model_totals.requests` field is explicitly defined as attempts for compatibility.

A crash between durable history append and state-file replacement can leave counters behind history. Interrupted-run startup reconciles available counters without inventing legacy records; torn writes/missing tracking-start markers remain explicitly incomplete. A model JSON response being parseable is distinct from a passing proposal review, recorded as separate stages.

New full selected-file verification manifests bind launchers/documents as well as implementation. Older evidence lacks this historical full-file manifest and is labeled accordingly. Structured history also records proposal reviews, milestone outcomes, stop requests and checkpoint restoration. No model prompt serialization was changed; context module edits add typing only.

## Paired baseline outcomes

The same controlled comparison was executed against the published 0.13.0 extraction and candidate 0.14.0. After 105 scripted attempts, baseline retained/reported 100; candidate retains 100 recent details with cumulative 105. After an external source edit, baseline ZIP still reported verified/pass with no history/manifest; candidate reports needs_attention/historical pass with history/manifest. A free-function test module with a failing assertion was ignored by baseline discovery while another test passed; candidate rejects it as uncollected. These are confirmed controller behavior differences, not a live model-success improvement. Results are in workflow-results-v1.json.
