# Focused planning and expanded Diag — engineering brief

## Goal and completion boundary

Make new guided/proof planning produce smaller builder assignments without asking models to maintain task-index bookkeeping, and retain enough structured diagnostic evidence to distinguish bad plans from provider failures. Preserve human approval, immutable approved checks, explicit cloud/execution consent, source-bound verification and Update rollback.

Scope: staged planning/compiler, capability-schema integration, attempt ledger, diagnostic projection/collector/UI, source-derived Dashboard graph, regressions, developer guidance and release distribution. No new provider, inference framework, production dependency, automatic source execution, or migration of approved projects.

Completion: controller/frozen-fixture regressions, full Python suite, typed modules, workbench and Dashboard browser checks, extracted-distribution tests, checksum verification and Update-button publication. Fixtures establish controller reliability, not live-model success rates or GPU performance.

## Evidence and audit

The supplied diagnostic archive identifies v0.31.0 and an earlier failed planning run, not a new v0.31 execution. The detailed journal reports repeated premature checkpoint declarations, two-feature task-scope/coverage mistakes, and provider service/quota failures. Local Qwen and DeepSeek did respond normally; there was no evidence of output truncation in that run. Rejected candidate bodies were unavailable, so their exact semantics cannot be reconstructed. The new regression is explicitly synthetic and derived from observed failure classes.

1. **Architecture:** approval, source checkpoints, deterministic review and bounded calls are strengths. Models were managing both semantic decomposition and global numeric bookkeeping. New `compiled_v1` drafts separate these responsibilities; old direct guided contracts and approved projects retain their behavior.
2. **UX:** existing proposal/build/verification separation is retained. New Diag copy explains expanded coverage; summary counts show actual exported detail rather than implying an exhaustive audit. New graph scenario documents the real compiler path, without inventing live activity.
3. **Developer tooling:** shared schemas, root tests and protected starter tests remain. A versioned frozen fixture and new compiler tests exercise scope, reference ownership, scheduling, native local schema, stop/resume and stage limits. No general agent framework was added.
4. **Efficiency:** one feature per stage reduces assignment breadth; maximum three new tasks, with remaining task slots reserved for later features. Six rejected proposals per compiled stage bound repeated semantic failures in addition to existing whole-job limits. Provider outages do not consume that semantic allowance, so they can still reach later local fallbacks within the job limit. This can increase successful request count compared with two-feature batches; no net token/latency improvement is claimed without live measurements.
5. **Workflow/resilience:** outline feasibility is checked before task calls, validated stages are checkpointed against full request identity, and final review remains mandatory. Diag keeps more safe evidence, including where it is incomplete. It does not run project code or inference to collect a report.

## Implementation decisions

- Models return semantic task fields for one feature: title, instructions, outcome, editable files, criteria and optional interfaces.
- Controller assigns feature indexes, a previous-task dependency chain, draft reference IDs and unchanged ordered HTTP prefixes. Echoed controller fields are rejected rather than silently relabelled.
- Scheduling uses the last declared feature producer; future features block a prefix. Declarations are never test evidence. Existing final evidence checks still reject missing or late business milestones.
- Featureless delivery prefixes start at task zero, correcting the prior negative-index readiness bug. Existing acceptance contents/order are unchanged.
- A server outline whose first business prefix requires every feature cannot meet the early-checkpoint policy. It fails before spending calls on task decomposition; correction must preserve requirements and acceptance behavior.
- New guided/proof drafts use compiler policy `compiled_v1`, draft schema 2 and ordinary task contract 1. A different request identity (including an older planning policy) requests a fresh outline instead of reusing incompatible draft work. Historical event records remain; they do not contain a full backup of the old draft. Approved plans/source are untouched.
- Model attempts retain stage, target feature indexes, safe candidate counts, review codes and review field paths. Review prose remains hashed/omitted in shared evidence; a finite rule catalogue explains known codes.
- Diag expands to 25 detailed projects (selected first), 100 summaries, 4,000 history records / 2 MB per project, 20,000 retained recorder events and a 24 MB report ceiling. Local recorder retention remains 14 days / 20,000 events / 32 MB. Collection cannot recover already missing history.
- State attempt tails and original event records overlap deliberately; IDs and coverage distinguish them. Never sum these as independent calls. Unknown provider token usage remains unknown.

## Research and evidence boundaries

See [research report](research/v0.32/REPORT.md) and its source-access ledger. Design choices are engineering hypotheses tested with fixtures, not claims that new prompts outperform frontier models. No API credentials are available in this checkout; Windows desktop behavior and local GPU performance remain untested here.

## Next measurable bottleneck

Run one fresh proof project on the user's actual routes. Inspect Diag for outline/task stage success, corrections per feature, actual calls/tokens and stage-bound stops. Compare against the observed 23-attempt planning failure without claiming a paired model benchmark. If tasks are still semantically too broad, use the recorded shapes/rules to design a focused experiment; do not add unbounded reviewers or relax frozen checks.
