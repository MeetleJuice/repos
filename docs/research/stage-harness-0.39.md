# Stage-specific harness and project memory — 0.39.0

Research date: 2026-10-22. This revision follows Diagnostic (11), with (9) and (10) as separate local probe observations. It targets planning reliability, not a claim of universal autonomous software generation.

## Evidence before implementation

Diagnostic (11), report `f911bae465334efd8748a632f3a2fe2b`, records twelve attempts in the selected latest run: scope succeeded, one feature's acceptance was saved, seven replies failed semantic review and three requests timed out. Model time was 497.18 seconds; timeouts accounted for 360.27 seconds. No builder task started. The ledger contains repeated missing API contracts, wrong response wrappers, missing mutation bodies and inconsistent restart scenarios. Original rejected response bodies are unavailable; new candidate inputs are labeled synthetic.

Diagnostic (10) separately shows Qwen 2.5 Coder passing the old small planning probe in 8.602 seconds while Qwen3 timed out. That was a format/stage check, not complete project acceptance. Inspection found that the old probe could accept a read-only response to a create-record goal because it did not require a concrete mutation scenario. The new probe deliberately has a different version and stronger criteria; its results are not directly interchangeable.

The old 16K planning failure is reproducible without inference: the controller carries a bulky request and reserves 8192 output tokens, then rejects all six models configured with the same insufficient context. A scope packet needlessly contains builder/source information; the budget path also lacks the raw stage identity and can account for the full proposal schema instead of the actual smaller stage schema. Enlarging context is a workaround, not a repair of that handoff.

## Research and decisions

Primary source retrieval status, byte lengths and hashes are in [the source manifest](stage-harness-sources-0.39.json). These are current upstream documents, not proof about an installed provider/model version.

| Subject | Source guidance | Implemented response |
| --- | --- | --- |
| Agent workflows | Anthropic's effective-agents cookbook separates prompt chains, routing, orchestrator/workers and evaluation patterns. | Keep a deterministic stage chain. No agent swarm or general-purpose framework is added to solve a missing-contract problem. |
| Context engineering | OpenAI distinguishes application-local context from data actually sent to the model. Capability visibility is separate from authorization. | Version explicit stage projections, preserve complete user/baseline values, and disclose deferred controller fields. Keep tool authority in the controller. |
| Memory | OpenAI's sessions guide separates persistence, input filtering and storage authorization; complete/reordered history is not automatically trustworthy. | Bind project memory to the complete request and exact validated prefix. Use typed API/scenario references, not an unconstrained model-written diary or replay of every failed message. |
| Prompting and structured output | Ollama documents JSON/schema generation and explicit instructions. | Give each stage a concrete goal/context/constraints/completion prompt, starter-shaped examples, and exact feedback from the production reviewer. Native format does not prove semantics. |
| Loop engineering | OpenAI's runner documents typed output, maximum turns, guardrails and error/resource ownership. | Preserve invocation ceilings, correction limits, consent and transport cooldowns; scope content rejection to the current stage/input rather than poisoning later different work. |
| Evaluation and debugging | Anthropic's evaluator/optimizer example relies on concrete criteria and feedback. | Use deterministic existing checks, stronger fixed probes, frozen observed ledgers and bounded regression scenarios. Do not add a paid reviewer or adopt an unbounded optimizer loop. |

The requested Ollama thinking-document and a guessed cookbook workflow URL were unavailable. The cookbook README identifies the actual workflow notebooks. No new thinking flag, model ranking or unsupported runtime capability is inferred from those unavailable pages.

## What each role receives

The user still chooses **Planner** and **Builder** routes. A role is a scoped job with a contract, not necessarily another model or concurrent agent.

| Role/stage | Context and capabilities | Completion authority |
| --- | --- | --- |
| Scope designer | Original idea/revision, baseline requirements, selected starter/API facts; builder route prose/source excerpts are deferred with hashes. | Schema-valid bounded scope saved as unapproved data. |
| Acceptance designer | Fixed scope, API registry, full validated earlier checks, declared sample references and current target feature. | Same production semantic reviewer; no approval or execution. |
| Task designer | Requirements, accepted outline/checks, earlier tasks, actual builder limits and static source interface names/hashes. | Controller assigns references/dependencies/checkpoint prefixes and checks file scope. |
| Builder | Current approved task, original requirements, exact source values, bounded retrieval, allowed edits and completion criteria. | Existing source/syntax/scope/finish gates; saving files is not behavioral verification. |
| Repairer | Builder route with concrete current failures, source identity, active scope, frozen checks and repair budget. | Existing static/milestone/full behavioral tests remain separate evidence. |
| Reviewer/verifier | Complete canonical proposal or explicitly authorized runtime checks. | Deterministic controller/runtime results; no model's self-report can pass itself. |

No new LLM reviewer, provider, production dependency, code execution permission or external search tool is granted. The static interface index uses Python AST parsing without importing source. Its 32-file/32-symbol bounds and omissions are explicit; it is not a complete semantic understanding of a codebase. Actual source remains available to the builder's existing context/retrieval system.

## Project-specific memory and API knowledge

New browser feature-by-feature requests explicitly choose harness version 3 (`stage_v1` context, `feature_v3` acceptance). Legacy v1/v2 policies remain separate. Known reviewed starter API declarations and explicit approved-baseline overrides seed the planning registry. The controller does not infer a new contract from a rejected check. Unknown business routes still require declarations; wrong wrappers, missing mutation data and inconsistent persistence still fail the same reviewer.

Validated prefixes retain complete canonical checks and contract values. Memory stores request/scope/prefix hashes, accepted-feature/check/contract counts and references to declared mutations in that prefix. Synthetic examples use the selected starter's actual response wrapper. Once a real planning seed is available, subsequent stages refer to its exact existing values instead of repeatedly introducing unrelated synthetic samples. None of this claims that a database mutation actually ran.

Resume checks memory before another model call. A changed prefix or removed contract stops instead of being silently restored. Original user and baseline values remain unchanged in projected packets, including Unicode. Changing the explicit planning policy begins a new unapproved request; the previous draft is retained for inspection. Installing alone does not migrate approved projects or existing v1/v2 drafts. These local hashes detect drift, not malicious rewriting by another process with the user's OS permissions.

## Budget and routing changes

Version 3 budgets account for the actual rendered stage instruction plus the actual native schema, rather than substituting a full proposal schema. The 8192 planner output floor remains unchanged. No hard model/context ceiling is overridden, no source is silently truncated and no GPU-fit claim follows from a configured context. An overlarge request still stops before transport and records estimated input, reserved output, effective/configured context and shortfall.

Repeated content rejection is bounded within a stage. A primary model that failed one feature can handle a later, different feature with different validated context. Account failures and service/transport cooldowns keep their existing scopes; a timeout is not reclassified as content failure. The 24-inference planner ceiling and existing run-level budgets remain in force.

## Verification and claim boundary

Two pre-change assertions failed for the expected reasons: scope carried irrelevant builder details, and a valid starter POST could not advance without model-redeclared contracts. New tests also reject unknown routes, incorrect wrappers, missing samples, memory drift and a read-only reply to the create-record probe. A real native adapter with scripted HTTP results exercises the full scope → per-feature acceptance → task chain with unchanged canonical checks and the unchanged output floor.

`stage-harness-v1.json` freezes the observed sanitized Diagnostic (11) ledger plus six explicitly synthetic scenario descriptions. `frozen-regressions-v23.json` appends it without changing previous sets. Paired controller measurements use the same synthetic request on extracted 0.38.0 and 0.39.0 with mocked transport. They establish budget/contract behavior, not live model quality, billing, latency or success rate. Detailed final commands, source/extracted results and immutable ZIP identity are published in the release validation file.

Larger projects, correction packets and long accepted prefixes can still exceed 16K. The controlled two-feature case fitting is not a promise that every request will fit. Windows/Ollama/GPU behavior and live cloud quota remain local validation steps. The next useful trial is a new version-3 project with the user's existing settings, followed by Diag on the actual outcome.

## Next measurements

Measure accepted prefixes, missing-contract errors, correction outcomes and timeout totals on a fresh local run. Only add stage-specific model ranking, additional reviewers or broader tools after controlled evidence shows a benefit. Preserve complete request identity, task authority and source-bound verification during any future optimization.
