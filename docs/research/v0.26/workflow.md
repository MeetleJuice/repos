# Workflow audit for 0.26

Read-only checkout inspection; offline scripted probes only. No real models, APIs, credentials, packaging, or publication. Sources include AGENTS.md, PLANS.md, PROMPTS.md, GOALS.md, docs/status.md and the frozen-dataset provenance contract recorded there. This is source/fixture evidence, not a live planner-quality claim. Reproduction: `PYTHONDONTWRITEBYTECODE=1 python /workspace/foundry026-research/workflow/probe.py`.

## Prioritized defects

### P1: New model plans can silently bypass the task contract

`forge/core.py:1103` requests task_contract_version 1 but its generation boundary (`1115–1119`) only calls revision_plan/require_consistent. `forge/tasks.py:15–16` deliberately accepts missing version for historical proposals; `forge/contracts.py:44–49` accepts it through this same generic validator. `forge/tasks.py:43` then sets structured=False, and `56` disables changed-file scope enforcement. Native Ollama schema requests the right fields, but other transports use JSON-object mode, and no model request guarantees compliance. The offline new_unversioned_candidate probe passes deterministic review and creates an unstructured packet. The common tests/fixtures.py PLAN is itself unversioned, so many generation integration tests exercise this permissive path.

Fix: require the current complete generation contract at the new-candidate boundary, independent of transport. Keep historical saved proposals/load/replay exact; do not migrate frozen approval artifacts implicitly. Regression: an otherwise valid fresh response missing version/context policy/task fields must receive bounded correction and cannot reach proposed; historical loading remains lossless. Test new candidates separately from legacy fixtures.

### P1: Static repairs can write outside the approved task before the finish gate detects it

The normal task payload supplies task_packet at `forge/core.py:1206`, and generate_and_apply validates it at `957`. However, the post-candidate `_inspect_and_repair` call at `1208` generates repairs at `1029` without current_task/task_packet and says “Implement every approved feature.” validate_task_response explicitly returns without a packet (`forge/tasks.py:56`), and apply validates protected/frozen files but not current-task scope (`forge/core.py:865–908`). A repair to another ordinary app file therefore lands atomically as a saved candidate; only later does finish_gate reject changed scope (`forge/execution.py:70–72`). Repeated resume can remain blocked on the already committed unauthorized task changes. The probe demonstrates identical other.py change allowed without packet and rejected with packet. Milestone repairs also omit task_packet at core.py:1058, though milestone/global repair authority needs an explicit policy distinction.

Fix: thread the approved current task packet through task-local static repairs and validate merged changed scope before replacement. Use a clear separate global verification repair path after all tasks, retaining frozen checks/repair caps. Regression: force a static failure after an allowed candidate, have the repair return one allowed and one out-of-scope file, assert neither repair change lands, correction remains bounded, cursor/approval/checkpoint remain consistent, and resume can proceed.

### P2: Planner examples contradict the generated contract

`forge/prompts.py:78–100` labels legacy snippets “JSON schema by example,” omits context_policy and all required task metadata, and shows a single task despite the 2–16 instruction at line 35. It says copy/adapt starter_example_plan at line 102. The actual example supplied at `forge/core.py:1111` is `forge/starters/arcade/proposal.json`, a historical unversioned plan whose two tasks each cover four feature indexes; adding required v1 metadata then fails `forge/tasks.py:38` (maximum three). The offline adapt_arcade_example_to_required_contract probe reproduces this deterministic rejection. This gives models competing concrete patterns and prose. It does not prove these exact errors caused the user's deepseek failures; their response/findings are needed.

Fix: supply dedicated current-version server/browser examples that pass the same new-generation validator; preserve the reviewed historical starter artifact rather than silently rewriting old plans. Derive or verify prompt examples against production semantics. Regression: every example extracted/provided to the planner validates under the current generation contract and obeys task counts, file scope, outcomes, dependencies, coverage and acceptance semantics.

### P2: Error history loses the useful per-attempt explanation

`forge/core.py:341–343` records schema_error and review_codes but not finding paths/messages or bounded proposal excerpts/digest. Details are stored globally in plan_review/failed_candidate (`1126–1127`) and overwritten by subsequent candidates. `forge/contracts.py:validate_structure` raises the first error, which review_plan converts to `structure` at `/`, so the label schema_error alone gives no actionable diagnosis. `core.py:353` announces correction without the findings, and the exhausted summary at `433` lists provider/category only (even when two different Ollama models failed). The probe exactly models timeout → invalid JSON object → invalid correction: three model invocations, final error “All configured models failed: ollama: transport; ollama: schema_error”; both schema attempts retain only [structure]. The last detailed review survives globally, but earlier reasons and candidate-specific attribution do not.

Fix: attach sanitized bounded deterministic findings and candidate digest to each attempt and show the exact failing model/path/message with a remedy in UI. Keep provider response bodies/secrets out; do not mislabel semantic proposal rejection as provider outage. Regression: first/corrected/alternate candidates with different failures retain distinct findings and attribution in history/export; safe UI rendering; absent usage remains unknown.

### P2: Opening/saving model settings drops legacy fallback options

`forge/static/planning.js:55–79` restores primary options and only fallback provider/model. `modelConfig` at lines 34–39 reconstructs a fallback with no options. API config legitimately accepts options on fallback (`forge/routing.py:68–74`). Thus editing unrelated primary settings and saving strips the fallback's configured context/output/native-JSON/timeout values, defaulting its next call. Automatic fallbacks retain options through routePools, so this specifically affects the supported single-fallback route.

Fix: preserve unedited fallback options when serializing (and expose them clearly if editable); invalidate them deliberately only when identity changes. Browser regression: configure a fallback with nondefault context/output/timeout/native-JSON, open Models and save an unrelated field, assert exact route-option preservation and unchanged approval, source and cursor.

## Additional contract tension to address deliberately

Targeted improvements must preserve all original features (`forge/core.py:484–485`) and plan only needed work (`forge/prompts.py:53–56`), but `forge/contracts.py:45–48` requires every original feature to be covered by a newly planned task. With v1's 1–3 feature limit, a one-feature repair in an eight-feature baseline must manufacture more tasks or attach unrelated inherited feature declarations. This is an objective mismatch between the improvement framing and coverage representation. Consider explicit inherited feature coverage tied to the frozen baseline source/plan, without claiming behavior verified; test a focused repair of a many-feature baseline. Do not weaken original acceptance or expand approved scope to satisfy coverage.

## Controls observed working / boundaries

- The synthetic pooled route exhausted after qwen timeout plus two deepseek schema failures; no repeated qwen request was made. Existing exhausted-error handling in PlanningEngine avoids restarting this route.
- Source drift, plan digest, cursor and approval checks exist in execution.py; preserve these while fixing task-local repairs. Do not remove finish_gate to hide the scope violation.
- Approval and model configuration are separate: configure_models only updates routes at core.py:437–446; changing models need not approve or rebuild a plan.
- 120-second socket timeout failure does not establish model inability, GPU fit, or whole-request cancellation. No live timings were measured here.
- No claim that all tasks or browser usability work follows from these probes. No complete suite was run in this audit lane.

Artifacts: probe.py and probe-results.json contain the complete synthetic reproduction and output. Temporary project writes stay inside this lane and are cleaned up. Checkout files were not edited.
