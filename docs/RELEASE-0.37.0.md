# Idea Foundry 0.37.0 — observable task and recovery loop

The revision connects prompt/context engineering to the existing deterministic harness. It preserves the planner's approval artifact, generated-project directories, frozen acceptance checks, execution/cloud consent, scoped edits, bounded routes and existing model configuration. It adds no dependency or provider.

## What the audit found

1. Static repair could receive identical files, observe identical failures, and spend the remaining repair allowance repeating the operation. A controlled regression made five model calls (planning, implementation, three unchanged repairs). It now makes three (planning, implementation, one unchanged repair), stops with needs_attention, and records stop_unchanged_static. This is a demonstrated avoided-repeat case, not a general speed or repair-quality benchmark.
2. A successful fixture repair had no repair lifecycle ID connecting its model request, source change and later test. Diag could retain a final pass without explaining the repair. New repair_started/repair_finished events and attempt attribution fill that gap.
3. Static inspections omitted their source hash, preventing a reliable matching-source repair audit. They now carry it. Milestone failure_kind is also retained by the export.
4. The selected proposal had a current audit, but the selected build had no comparable latest-run summary. Lifetime failure totals could not answer what happened in the most recent build. Diag now summarizes that build separately.

## The revised operation

1. **Readiness:** before implementation, record approval, checkpoint/source consistency, cursor and task-dependency checks. These are the existing execution boundaries made explicit, not proof of task semantics or model fitness.
2. **Focused work order:** structured builder handoff schema 2 identifies goal, context, constraints and completion references. Original task, proposal, complete supplied file values and declared criteria remain unchanged. Legacy unstructured payloads retain their prior contract. The ordinary CODE prompt and frozen serialization dataset remain unchanged. One fixed structured fixture is 1,901 to 1,879 JSON characters; characters are not provider tokens, cost or model-quality evidence.
3. **Context receipt:** handoff_prepared records selected/omitted filenames, source/request character sizes, request/prompt hashes and retrieval allowance. Existing bounded complete-file retrieval remains available. No prompt or source bodies enter diagnostics.
4. **Implementation/recovery attribution:** coder attempts carry execution_stage, task when applicable and repair_id. Repairs distinguish static, milestone, final behavioral and user-reported repair paths. Repair start/end includes source hashes, elapsed time, attempted calls and candidate/failed/cancelled outcome. A candidate save never counts as a successful repair.
5. **Validation:** the report links a later check only when its source hash matches the repair's saved source. Static, approved HTTP-prefix milestone, full automated behavior and environment failure have different classifications. These are historical matching-source observations, not causality, full requirement completion, current file freshness or manual acceptance.
6. **Bounded recovery:** unchanged static source plus unchanged issues stops the loop. Existing output recovery, model fallback, environment refusal, frozen-check protection and global budgets retain authority. Recovery decisions are exported by controlled code rather than free-text logs.
7. **Review and delivery:** the existing real verification, manual acceptance and tested-source export process stays intact. No generated app can modify Foundry or promote a new routing policy itself.

## Test and Diag

Test retains the eight planning guards and adds six fixed repair-evidence guards: changed/unverified, static-only, same-source behavior, unrelated-source pass, prefix-only and environment failure. It also audits the selected build's recorded evidence. A successful audit does not mark a failed project passed, rerun its code, call a model or change routes. The UI labels the recorded build outcome separately.

Diag includes latest selected execution, tasks saved and timed when possible, repair IDs and validation event IDs, per-model response/call/timing/usage coverage, rejected source responses, readiness failures and stop decisions. Request-start and attempt IDs reveal unfinished requests without declaring a provider outage; they may still be running, interrupted or missing completion history. Unknown timing/usage remains null; reported token totals include only reporting attempts. Retained counts, missing run boundaries, older unattributed calls and capped details remain explicit. Source freshness still comes from each project's verification object. START_HERE explains how to trace the evidence. ZIP manifests retain byte sizes and SHA-256 hashes.

The dashboard graph includes readiness and repair observation paths. Follow uses actual newly observed controller events; simulation remains labeled and separate. No execution edge is invented from a model's claim.

## Validation boundaries

The regression suite covers real fixture application failure/repair/retest, unchanged static repair, readiness and source drift, interrupted/failed repairs, partial/legacy histories, unknown metrics, preserved Unicode/source/task values, read-only Test/Diag, export privacy and manifest integrity. Browser checks exercise the actual workbench and dashboard, including Follow geometry and mobile layout. Frozen-regressions-v21 appends one synthetic evidence set without changing the preceding sets. Final measured commands/results and extracted-release identity are recorded in releases/validation-0.37.0.json.

No live cloud request, user's Windows Ollama run, GPU benchmark or paired model-quality trial was performed here. This release does not prove a higher autonomous project-completion rate. The official references and access failures are recorded in docs/research/v0.37; no model-based evaluator, framework migration, raw reasoning capture or automatic routing promotion was added.

## After Update

1. Use the existing Update button, restart when prompted, and confirm 0.37.0.
2. Keep previous projects; start one small fresh project using your chosen local/cloud mode.
3. Plan feature by feature. Review the proposal before approval.
4. Generate files. If you approve local execution, select this computer and run checks with a bounded repair allowance. Docker remains optional for isolated verification.
5. Open the dashboard to follow the recorded readiness, model and repair activity.
6. When the job ends or stops, open Test and run quick checks. Optional model probes require their separate choices/consent; quick checks do not prove model quality.
7. Open Diag, read the latest selected-build summary, download the ZIP and send it here. Keep failed attempts as evidence rather than deleting the project.

Next measurement: one small live Windows project, including an interrupted/resumed task if practical. Compare attempted calls, time by stage, repeat-stop decisions and matching-source verification. Use those observations to justify future task decomposition or routing changes instead of adding more prompts/reviewers speculatively.
