# Idea Foundry 0.36.0 — a proposal must agree with its delivery plan

## What the new diagnostic proved

Report `a515ba01c43042139eb0a5b8105ed614` came from the expected clean v0.35.0 distribution. All 18 manifest members matched their exported size and SHA-256. The latest planning run reached `proposed` in **381.174 seconds**, using 16 local requests. Scope and all four acceptance prefixes were saved; LFM completed the four task batches after other models were rejected or timed out. The two 120-second timeouts still consumed about 240 seconds. This is one observed run, not a controlled speed comparison.

That was real controller progress, but the resulting proposal was unsuitable for approval. Its tasks named `/api/tasks` while its checks used `/api/accomplishments`; three groups repeated the same work; no check restarted the server; no task declared UI implementation; repeated creates assumed the same live ID; and a one-record unordered subset did not prove newest-first sorting. The old reviewer accepted the exact supplied JSON. The diagnostic ZIP excludes transcripts/source; the user separately supplied the complete unapproved proposal, which is the frozen comparator here.

## Root causes and changes

| Area | Gap | Change |
| --- | --- | --- |
| Backend and approval | `app_kind: browser` bypassed API-contract and checkpoint requirements even for a database/API dashboard | Business HTTP checks determine backend evidence requirements. Delivery-only games retain their HTTP/manual distinction. |
| Planning and task delivery | Structurally valid task references were treated as sufficient even when instructions named different endpoints or repeated work | Evidence-ready batch/final review checks explicit method/path references and identical instructions/outcome/criteria/file scope. Current-feature acceptance is included in each task packet. |
| Scenario state | Separate feature calls assumed fresh storage or declared persistence without requesting a restart | Check order carries known live fixture IDs and seeded values. Server-persistence features need mapped restart reads; deleted seeds cannot establish persistence. |
| Verification semantics | Unordered `json_contains` arrays were mistaken for sorting proof | Explicit newest/oldest-first/ascending/descending declarations require an exact ordered array over two seeded records or an explicit two-record manual comparison. Existing subset semantics and frozen checks are unchanged. |
| UI and user workflow | A stored pass remained green after reviewer improvements | Idle unapproved proposals receive a current read-only review for display. The UI blocks approval and explains an earlier saved pass when current checks fail. Approved projects are not migrated. |
| Test and Diag | Tiny JSON tests could succeed while a contradictory plan passed, or a truncated reply could appear absent | Test adds eight deterministic adversarial planning cases and a selected-proposal audit. New probe records distinguish a received reply from accepted JSON, including truncation. Diag separates current review, stored review and the latest run from lifetime failures. |

The new `forge/coherence.py` contains bounded declaration/scenario checks and an audit projection. No provider, dependency, external reviewer agent or extra automatic inference was added. Existing output reservations, native schemas, local/cloud consent, same-model correction, fallback/circuit rules, planning request allowance and repair bounds remain in place. Wrong batches are rejected before being checkpointed or handed to the builder. Approved plans, frozen tests and source are not rewritten.

## Better task handoffs

Compiled task requests now carry the exact target feature and its acceptance items. They retain the fixed outline, earlier tasks, starter source, builder limits and original request/baseline values. They omit the non-authoritative rejected previous proposal with a versioned context manifest and digest. This targets the observed repeated generic task pattern without claiming that old context was its sole cause. The older full-context coding path is unchanged.

New evidence guidance changes the full planning request identity, so a new run can start a fresh unapproved draft. A matching validated draft can still resume. Unapproved checks may be corrected; approved baseline checks may not. Rejections preserve their specific rule codes through stage correction and fallback.

If a matching saved outline fails current acceptance review, recovery now clears its associated invalid acceptance checkpoint along with dependent tasks while retaining validated scope. A regression reproduces the old pre-model failure and confirms acceptance and task generation resume without requesting scope again. Valid matching prefixes are retained as before.

## Useful diagnostic data

Per detailed project, `planning.current_review` includes reviewer version, plan digest, pass/fail, rule codes and structural paths, duplicate task index groups, restart check indexes and business HTTP check count. `stored_review_passed` remains separate. The selected project's current review appears prominently above workspace-history totals.

`planning.latest_run` groups retained events by the latest recorded planning run ID. It reports stage attempts/accepted/rejected/timing, recorded versus reported request count and timeout time. Missing timings remain unknown; incomplete history is disclosed. Acceptance-prefix counts now survive the export allowlist. These are retained controller observations, not reconstructed lifetime events or rendering/GPU measurements.

Test's **Quick checks** now performs eight fixed adversarial planning cases and a local audit of the selected proposal without calling a model, executing generated code, changing routes or approving anything. Its results persist with a Test ID and are included in Diag. A failure in the selected old proposal is expected until that proposal is corrected. These are bounded smoke/regression checks, not every possible repository test.

New failed probe records expose `response_received`, `response_accepted` and `http_response_received`. A truncated reply remains a failed output-budget test but is no longer reported as no generation reply. Historical records are not retroactively reclassified. A 1,024-token diagnostic probe still cannot establish project fitness or remaining quota.

No prompts, sample-data bodies, source files, model transcripts, credential files or manual notes were added to diagnostic exports. Rule codes, digests, counts and locations provide the new evidence. The read-only audit does not revoke a historical approved source snapshot or establish app behavior.

## Regression and end-to-end evidence

Before changes, `python -m unittest tests.test_planning_coherence -q` failed all three initial assertions: the exact uploaded plan passed, browser/API checkpoints were absent and wrong-endpoint tasks were accepted. The corrected controller rejects the frozen upload with eight distinct rule codes. An additional fail-before/pass-after assertion catches the old truncated-probe reporting error.

The appended v20 frozen manifest preserves all 20 earlier sets and adds this actual unapproved proposal. The new browser scenario opens the old green proposal, blocks approval, runs Test, exports its current Diag findings without mutation, then runs a correct hybrid browser/API fixture through granular planning, unchanged human approval, actual early SQLite restart checks, real browser/manual interactions and a verified app ZIP. Scripted model replies exercise the harness; they do not establish live reasoning quality.

One existing scheduling fixture copied identical task contents solely to test last-producer scheduling. It now describes distinct persistence-test work while retaining all of its original checkpoint assertions. No test was skipped or weakened to accept the uploaded contradiction.

Final source check:

```text
python -m unittest discover -q
Ran 557 tests in 134.057s
OK

python -m mypy --strict <38 modules listed in tools/validate.py>
Success: no issues found in 38 source files
```

All 26 workbench browser scripts passed, as did both Dashboard browser/launcher checks, TypeScript checking, four Node tests and the production asset build. The graph has 302 nodes, 469 edges and 182 source-backed scenarios. The last checkpoint recovery change additionally passed 58 focused planning/resume/Test tests. The release validation record separately records the extracted-distribution results and exact archive identity. These are harness/fixture results, not 26 independent live-model builds.

## After updating

1. Click **Update**, restart and confirm **0.36.0**.
2. Open the existing Tiny Wins project. Its old proposal may now correctly show **Resolve proposal contradictions**. Keep it unapproved.
3. Click **Plan feature by feature** once, retaining your intended revision and the visible two-minute timeout for this comparison. Do not approve the old proposal or repeatedly retry unchanged errors.
4. When a new proposal is ready, verify that task routes match its checks, UI work is explicit, persistence actually requests a restart and ordering compares two records. Share the new Diag ZIP and proposal for review before building if anything remains unclear.
5. If planning stops, send one fresh Diag ZIP. Its selected-plan audit and latest-run stages now distinguish a rejected plan from provider, timeout or output-budget failures.

## Limits and next measurement

These guards recognize explicit HTTP references, identical semantic task fields, known fixture IDs, selected English requirement patterns and declared UI work. They do not understand every possible paraphrase or prove arbitrary business logic. UI declarations still require actual browser/user testing. Unknown/custom identity and migration semantics can need explicit human review. A model can still exhaust the bounded correction/fallback route; both slow models and quota issues can remain.

Live model generation, paid cost, Windows GPU speed and the next PC build remain untested here. The useful next measurement is whether this same small project reaches a coherent proposal and a verified app, with per-stage time/requests and rejected rule codes—not merely whether it reaches `proposed`.

Primary-source research used OpenAPI 3.1.1 for per-path/operation/response contracts and MDN's HTTP 201 semantics for new-resource scenarios. Foundry's actual `subset()` implementation establishes that its existing subset arrays are unordered. Fetch records, hashes and the unavailable Playwright source URL are recorded in `docs/research/v0.36/sources.json`; no failed fetch is presented as evidence.
