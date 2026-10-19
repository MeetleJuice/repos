# v0.20.0 — bounded task decomposition

## What the supplied run establishes

The supplied Josh log still contains the six broad historical tasks: server; all HTML/CSS; core JavaScript; CRUD/search/filter/totals; import/export; and optional images/connection panel/documentation. It shows protected-file/budget failures followed by a route exhausted through provider, transport, quota and local output-budget failures. A task-logic change cannot restore unavailable provider quota. The final coding prompt also told the final task to deliver every feature even if the plan was incomplete. That catch-all instruction has been removed.

The log does not contain raw responses or the app's actual files. We cannot infer which UI features exist, whether historical README responses were unchanged echoes, or that a smaller task would have prevented those provider outages.

## The new process

1. **Scope the deliverable.** Continue to propose a small useful standard-library browser app and disclose deferred features. Reuse reviewed starter infrastructure.
2. **Plan focused outcomes.** New prompts and the native Ollama schema request `task_contract_version: 1`. A task includes a title, instructions, feature indexes, one observable `outcome`, 1–3 `files`, earlier zero-based `depends_on` indexes, and 1–4 `done_when` criteria. Use 2–16 tasks as appropriate rather than forcing every app into six broad buckets. Sixteen is a ceiling, not a target.
3. **Review deterministically.** Structured contracts reject missing fields, wide file lists, protected/unsafe/Windows-reserved paths, cyclic/forward/duplicate dependencies, instructions over 1,800 characters and literal catch-all assignments. Existing feature/acceptance coverage checks remain required. These checks constrain declared scope; they cannot prove a model can finish a task or that prose is semantically atomic.
4. **Approve the same artifact.** Display the outcome, editable files, dependencies and criteria beside each task. The user approves the proposal containing these fields. No hidden post-approval decomposition, scope expansion or new acceptance tests is performed.
5. **Issue one task packet.** The builder gets the original proposal/task plus its explicit task index/count, approved scope, criteria and saved dependency state. Original source remains available; no context is silently dropped. The packet is included in the final execution directive and its reservation accounting.
6. **Validate before applying.** Expand exact edits against the current snapshot. For structured tasks, reject changed files outside the approved list and no-change responses. Unchanged editable-file echoes are allowed; protected files retain v0.19's exact-echo-only policy. All original path, syntax, size, frozen-test and protected-check guards still run before replacement.
7. **Correct within bounds.** A rejected response gets the existing one focused correction. Recovery may not enlarge the task's file scope. A bad scope declaration requires revising and approving a plan, not quietly allowing unrelated changes.
8. **Save and inspect.** Checkpoint, save, inspect source, persist the task index and receipt. The receipt now contains the task packet, snapshot hashes and changed files. `TASKS.md` includes structured outcomes, paths, dependencies and criteria. Restart/resume uses saved progress.
9. **Verify separately.** Criteria and saved dependency state are declarations/source progress, not execution evidence. Existing optional milestone checks, global repair caps, cloud consent, runtime consent, final behavioral checks and manual acceptance remain separate. Repairs use the existing application-wide approved repair contract rather than silently pretending to be task implementation.
10. **Export the snapshot.** Existing source/evidence binding and ZIP manifests remain authoritative; task contracts accompany saved receipts without promoting model self-reports to verification.

## Compatibility and limitations

Old proposals, backups and approved in-progress projects remain valid and unchanged. They are explicitly labelled **Legacy task** in the UI and do not acquire invented file/dependency contracts. Native generation asks for the new schema; historical/imported plans without the version marker remain accepted. If a provider returns a legacy-shaped plan, the UI exposes that fact; review/revise it before approval to obtain bounded contracts. Versioned structured plans are strictly validated.

This release does not split an approved historical six-task plan automatically. To try the new decomposition, start a fresh project or revise an unapproved proposal: “Break this into focused task-contract-version-1 tasks, each with one outcome, up to three editable files, dependencies and completion criteria. Keep the same feature scope and acceptance checks.” Keep the original project available.

More tasks can mean more cloud calls and cost. No extra automatic planning model, consensus loop, parallel builder or unbounded retry is introduced. The 36,000-character source ceiling and 70,000-character project ceiling remain. A one-file task can still be difficult; smaller file counts are a deterministic scope control, not proof of local-model capability or completion quality.

Planner reservation estimates now account for the extra structured task fields (eight-task initial allowance and a larger per-task estimate). Capability ceilings, the configured output floor, compact planning and truncation recovery remain enforced. This is an estimate, not a billed-token measurement.

## Research and decisions

Primary-source snapshots/hashes: [source register](research/task-decomposition-sources-0.20.0.json).

- GitHub Spec Kit's task template groups work around independently deliverable/testable stories, explicit paths and prerequisite relationships. Adopt behavior-oriented task slices and explicit dependencies; do not copy its framework/authentication examples into Foundry's standard-library MVPs.
- Anthropic Claude Code's feature-dev workflow separates discovery, code exploration, architecture, implementation and quality review. Adopt explicit stage boundaries and inspection before implementation. Its multi-agent workflow is not implemented here; additional model calls have no measured benefit in this environment.

Neither document proves a percentage improvement for Foundry. No new live model, provider-quota, GPU, Windows or paid-quality trial was performed. New fixtures are explicitly synthetic; their provenance records that they were frozen after the initial implementation and before full release validation. Earlier frozen fixtures remain unchanged.

## Validation

See [validation results](validation-0.20.0.md). Tests cover scope/dependency/path/catch-all rejection, legacy parity, native schema requirements, structured output reservation, exact edits, atomic correction, persistent progress, receipts and exported task documentation. An actual Chromium test reviews the contract, rejects an out-of-scope response, accepts a focused correction, executes verification and downloads the source-bound ZIP. This is a controlled provider fixture, not a claim that Josh's live build is complete.

Next highest-value work: measure task outcomes on real representative apps/providers, identify oversized single-file changes from actual traces, and add independently checked task-level behavior coverage. Automatic scope changes or runtime execution still require preserving the user's review/consent contract.

## Paired replay against the published baseline

The [controlled comparison](research/task-decomposition-paired-0.20.0.json) was run against an extracted v0.19.0 release and this release:

| Gate | v0.19.0 | v0.20.0 |
|---|---|---|
| Structured proposal declaring four files and a self dependency | Metadata ignored; accepted | Rejected before approval |
| Builder returns valid app files plus an undeclared extra JS file | Extra file written | Entire response rejected; focused correction saves allowed files only |
| Task completed after controlled response sequence | One saved task | One saved task |
| Behavioral execution in this replay | None | None |

Reproduce with `python docs/research/replay-task-decomposition.py`; pass an extracted baseline release directory as an optional argument for the control. No live inference cost, latency or repair-quality comparison was measured. The extra correction is an existing bounded mechanism, not a free performance gain.
