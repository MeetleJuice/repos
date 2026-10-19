# v0.22.0 — task delivery, context and recovery

This release implements bounded parts of the six-priority research agenda. It preserves the standard-library runtime, explicit cloud/execution consent, approved scope, frozen checks/tests, portable exports and existing model choices. It does not claim universal project completion, GPU fitness or improved live-model repair quality.

## 1. Task readiness and completion evidence

The Build panel now has a readable **Task readiness & evidence** board. It distinguishes ready/blocked/in-progress work, saved candidates awaiting inspection, saved source with checks pending, source references, current automated-run inclusion and accepted app snapshots. Dependencies mean saved-source prerequisites, not automatically verified behavior.

Actual milestone verifier success is attached to its task receipt with the executed approved HTTP prefix count and source fingerprint. Later source changes make that milestone historical. Full app acceptance still requires current final verification and required manual results. Source quotations and the task's generation-time `behavior_verified: false` do not become full behavioral success merely because a prefix passed.

No new tests are invented after approval and no approved checks are weakened. The controller still needs explicit execution consent to run generated code. The real milestone integration regression executes a prefix, then changes the snapshot with a subsequent task and confirms the earlier evidence is historical.

## 2. Local calibration and focused context

Models includes an optional **Check local model performance → Run local checks** control. It runs two fixed Ollama response fixtures: exact JSON and an exact source edit. They use a 4,096-token configured context, 1,024-token output cap and bounded request timeout. No project files are sent, no generated code is executed, no cloud provider is used and routes are unchanged. Results/timing are stored in the private workspace, not generated projects. Calibration shares the model lock and activity display; it refuses to compete with a running inference request.

These are basic response checks, not a real-project benchmark, hardware/VRAM measurement or proof a 32K task will fit. A failed/slow test is information, not an automatic reason to modify keys or model choices. Timing may include a warm or cold load; the tool does not force a cold start.

New proposals request a reviewed `context_policy`: `focused_v1` or `full`. Historical plans without it retain full source. Focused mode includes complete existing editable files, transitive recognized local dependencies and relevant importing tests, plus an explicit manifest of all available source with sizes/hashes. A large/empty selection falls back to all source; files are never silently cut. Original proposal/task values stay intact.

A builder can return only `request_context` with up to five listed files; at most two retrieval rounds are allowed per task. The controller adds exact complete source and updates the included/omitted manifest. Unknown paths, mixed write/read responses, repeated already-included reads and excess rounds reject. A malformed-response correction falls back to full current source, accurately updates the manifest and grants no additional reads. All actual calls still undergo capacity/output reservation, consent and route rules.

Focused mode can reduce input and make a local reservation eligible; it can also incur extra calls or require cloud fallback when requested context grows. It is not a guaranteed cost or speed win. Existing 36,000-character source and 70,000-character total limits remain.

## 3. Interface-aware decomposition

Plans may declare up to six interfaces per task using `{file, symbol, contract}`. The planner is instructed to place producers before consumers and preserve API/data shapes. Task packets include the declarations and, when available, actual Python function signatures inspected through AST. Observations are static; missing/unrecognized symbols stay unknown. No return-value semantics are invented.

Import/asset dependency discovery improves the source packet, but it is intentionally not a complete Python/JavaScript resolver. The manifest and bounded reads provide a fallback. If a necessary write lies outside the approved task files, the implementation is still rejected; a new reviewed plan is required. Scope guards are not disabled to make a build finish.

## 4. Task-aware routing under failures

Explicit Hybrid/cloud-first/local-first/local-only profiles remain unchanged until the user applies setup. Routing continues to honor declared capability ceilings, configured output reservations, consent, temporary transport/service circuits and quota/auth/model failures. The new task-specific source packet can make an existing local route fit where the full-source packet did not. Additional retrieved files are rechecked by the same gate.

This is capacity-aware routing, not a new learned quality predictor. Small calibration results do not automatically reorder models or lower output floors. Truncation still cannot fall back to a smaller output ceiling. Existing controlled-failure and browser routing regressions remain in the validation set.

## 5. Reliable interruption and resume

Before a task begins, save its plan hash, cursor, original source hash and per-file hashes. When files commit, record a recoverable candidate hash before task advancement. A stopped/restarted workbench recognizes that candidate, repeats inspection and records the receipt **without requesting the same implementation again**. The receipt keeps the original before/after source identities and changed-file list.

If current files, approved plan or cursor disagree with the durable record, stop before new implementation requests. The UI explains the mismatch. For source-only drift, the explicit **Keep current files & retry unfinished task** action adopts the reviewed source snapshot, clears current verification, leaves the cursor unchanged and retries the unfinished work. It cannot approve a different plan or task position. Restore remains available. Model configuration and execution consent are not changed by adoption.

Checkpoint restore establishes a new consistent resume baseline. Improvement copies start their own execution records rather than inheriting their parent's cursor/hash. Parent source, tests and acceptance checks remain preserved.

This is recoverable reconciliation, not a claim of exactly-once execution. Source swaps and state persistence are separate operations. A crash in the ambiguous interval is detected as drift and requires review rather than blind replay. It does not resume a half-finished arbitrary application side effect. Windows locking/power-loss behavior still requires platform testing.

## 6. Extra reviewers and optimization only with evidence

No extra critic/consensus/planner calls or autonomous source promotion are added. Deterministic readiness, interface inspection, fingerprints, bounded retrieval and independent checks provide the new gates. The evaluation-only replay and frozen fixtures document controlled outcomes; real-provider success/cost needs a separate representative trial before promoting additional reviewer policies.

## User experience and compatibility

- New task/evidence panel has bounded scrolling and mobile wrapping.
- A saved candidate, a blocked dependency and accepted evidence have different language.
- Recovery controls remain disabled during an active job and update when job state changes, even when source facts are otherwise identical.
- Calibration is optional, explicitly local and visibly separate from app verification.
- Existing approved projects/backup schemas keep their tasks, context behavior and progress. New fields are additive.
- New focused proposals disclose context policy before approval; generated/exported source remains complete.
- HTTP delivery, static inspection, model availability, calibration and actual application acceptance remain separate observations.

## Research used

Primary-source URLs, fetch dates and hashes are in [the source register](research/delivery-control-sources-0.22.0.json).

- Google ADK dynamic workflows and LangGraph: durable stages, checkpointing and explicit resumption.
- Aider repository maps: discoverable source and context budgeting, adapted here as explicit complete-file selection/retrieval.
- Ollama FAQ: model residency, reported timing, context and concurrency tradeoffs; no automatic GPU-fit claim.
- GitHub Spec Kit: behavior-oriented increments, concrete paths and prerequisites.
- CPython `os.replace`: atomic replacement semantics do not make a multi-file source/state workflow one transaction; reconcile ambiguous interruptions.

No framework migration or extra runtime package was needed. This release builds on the prior broader research report rather than claiming to reproduce framework or research benchmark performance.

## Controlled before/after results

[Replay results](research/delivery-control-paired-0.22.0.json) compare the published v0.21.0 with this release:

| Scenario | v0.21.0 | v0.22.0 |
|---|---|---|
| Stop after candidate commit, before task cursor advances; restart | Repeats adapter invocation; fixture exhausts and stops | Inspects retained candidate; advances without another implementation invocation |
| Adapter calls in that replay | 2 → 3 | 2 → 2 |
| Candidate source after resume | Preserved | Preserved |
| Behavioral execution in that replay | None | None |
| Isolated context fixture UTF-8 payload | 30,157 bytes | 855 bytes with explicit omitted-file manifest |
| Same isolated 16K context / 8K output reservation | Refused | Eligible |

The budget probe excludes production CODE/system prompts, framing, real inference and GPU execution. Payload bytes are not provider tokens or billed cost. The omitted 30K file is synthetic unrelated source; this is not an average project saving. The replay does not establish live-model repair quality.

Run `python docs/research/replay-delivery-control.py`; an extracted baseline release root is an optional argument. Tests independently cover original Unicode/source equality, bounded retrieval, source drift, explicit adoption, active-run restart, actual milestone execution, private calibration and legacy parity.

## Validation and remaining work

See [validation results](validation-0.22.0.md). Priorities for a later measured cycle: real Windows/Ollama project calibration, context-selection quality on representative apps, independently checked task-level behavior and model/route comparisons on held-out cases. No runtime reviewer cost is justified merely by adding another agent name.
