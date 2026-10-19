# Domain 2: Human-reviewed scaffold evolution

**Decision:** make scaffold improvement an offline, measured release process. Do not let generated apps rewrite Foundry or promote their own tests into evidence. Here “scaffold” covers both reviewed starter source and the planner/build/repair instructions; these are separate versioned artifacts.

## Sources and strength of evidence

- [Automated Design of Agentic Systems / Meta Agent Search (ADAS)](https://github.com/ShengranHu/ADAS), [paper](https://arxiv.org/abs/2408.08435). The authoritative repository README was retrieved during this audit. It describes an agent proposing executable agent designs from previous discoveries, with domain-specific evaluation functions. This supports an explicit candidate → evaluator → archive loop, not a claim that self-modifying production systems are reliable. Its repository also warns that running generated code can be destructive.
- [DSPy](https://github.com/stanfordnlp/dspy), [original paper](https://arxiv.org/abs/2310.03714), [GEPA reference linked by the project](https://arxiv.org/abs/2507.19457). The official README was retrieved. It describes modular LM programs and optimizing instructions/weights; it links reflective prompt evolution research. Transfer the modular contracts and evaluation discipline first. We have not reproduced its results, and adding its runtime is unnecessary for a small initial Foundry experiment.
- **Unresolved references:** “stationarity,” “selfHPO,” and “Ouroboros” in the requested research do not uniquely identify papers, authors, versions, or repositories. No conclusions or improvement percentages are attributed to those names. Direct arXiv retrieval was blocked by this environment; paper links above were verified as references in the retrieved official repositories, not independently read full texts.

## Foundry baseline from source

`forge/scaffolds.py` has four explicitly selected, version-1 starters: web, arcade, notes, tasks. `starter_files()` reads a fixed allowlist; it does not select or evolve starters from evidence. `forge/core.py` installs starter files only when approving an empty project, records `starter_version`, and freezes the foundation-test hash. This is already an appropriate seed boundary.

Core `OWNED` files include approved documentation, checks and launcher files. `apply()` rejects edits to owned files or frozen tests, enforces source limits, and checkpoints before changes. The bounded repair paths use source fingerprints, failure feedback and repair history. These protect individual projects; they do not yet provide a benchmark registry, candidate scaffold version, held-out evaluation, paired improvement report, or reviewed promotion process. A successful HTTP check cannot substitute for browser interaction or gameplay evidence.

## Contract versus optimizable capability

| Fixed release contract | Candidate capability |
|---|---|
| Approved requirements, acceptance checks and regression tests | Prompt wording and task decomposition |
| Explicit execution/cloud consent; no secret export | Context selection and bounded response format |
| Path/source budgets, atomic writes, checkpoints | Starter implementation and new optional templates |
| Existing project compatibility and selected runtime | Model routing policy within configured consent |

Changing a contract requires an explicit reviewed product change, not an optimizer scoring shortcut. Generated tests can supplement a candidate, but held-out checks remain owned independently of that candidate.

## Minimal evolution loop

1. Freeze replay fixtures for known failures: malformed response, oversized repair, provider outage, persistence, false-positive HTTP success, and game state behavior. Label these **replay cases**, not independent historical builds; 15–20 independent builds are not available from this audit.
2. Record baseline version, artifact hashes, model configuration, fixture identity, success/failure category, requests, latency and reported tokens. Use deterministic replay for controller correctness; separately label any live model experiment and its costs.
3. Propose exactly one change in a separate candidate artifact: e.g. narrower repair context or a smaller starter task. Keep the current released starter unchanged.
4. Run candidate and baseline against the same cases and reserve held-out requirements. Report regressions and resource costs as well as successes. Small samples justify a local result, not general reliability or exponential improvement claims.
5. Present diff plus measured report for human review. Only then publish a new starter/prompt version through the normal release mechanism. Existing projects retain their installed files and recorded starter version; migrations remain explicit and reversible.
6. Keep failed candidates and evidence for future analysis. Never automatically overwrite the evaluator, weaken acceptance checks, install dependencies, or execute generated workflow code on the host as part of promotion.

**Next useful experiment:** evaluate bounded repair-context selection against the existing full-source correction path using frozen failures. This is cheaper and more attributable than multi-agent voting or autonomous source mutation. No performance gain is claimed before the paired evaluation exists.
