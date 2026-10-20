# Foundry research synthesis — 2026-10-20

## What we are building

Foundry is a local-first, bounded software-generation harness. It should turn a manageable idea into an explicit full proposal, obtain human approval, execute scoped sequential tasks, inspect and test real behavior, repair within a shared allowance, and export a reproducible source/evidence bundle. Inference services supply model replies; Foundry supplies orchestration, authority, context, persistence and verification. Neither alone guarantees a completed app.

Baseline: release 0.25.0, commit e4df92b. The inventory reads/hashes all 330 tracked files (299 text, 31 binary, including immutable archives). It provides source/AST/line metadata, not a claim of manual line-by-line semantic review. The deep audit concentrates on the generator, provider/model/configuration path, planning/task/repair state machine, checkpoints, UI and updater; existing tests and archived research cover the other modules.

## 1. Models and benchmark evidence

**Verified:** accessible primary SWE-bench Pro and LiveCodeBench sources show that scores depend on version, task set, time window and evaluation configuration. SWE-bench Pro's current V2 documentation describes 642 tasks across 11 repositories, whereas legacy material uses a different dataset. Mixing these results would produce a false ranking. The detailed [model memo](models.md) and [register](model-sources.json) record sources and access failures.

**Unverified:** current AA rankings, the supplied FrontierCode GPT-6.1 Sol 60.4% medium claim, current provider prices and a best model for Foundry. Numbered reference placeholders were not evidence. Primary leaderboard sites were inaccessible through this environment; no paid API tests were run. The named incumbent is therefore a candidate for a future controlled comparison, not an authenticated benchmark winner here.

**Decision:** compare a fixed set of Foundry tasks using pinned model IDs and harness revisions. Measure full proposal validity, approved feature coverage, completed apps passing independent checks, calls/tokens, wall time, repairs and resume behavior. Keep cost per task and total session cost separate; absent usage/pricing stays unknown. Public issue-repair or algorithm scores do not directly measure new browser-app generation. Reject an ungrounded universal model ranking.

## 2. Harness architectures and their trade-offs

Seven subsystems organize the [42-cell evidence matrix](harness-matrix.json): loop, tools, context, safety, orchestration, extensions and memory. Five accessible implementations use product-owned core control loops. Codex, Gemini CLI, Aider, mini-SWE-agent and the OpenHands SDK expose different action/state/tool boundaries. Claude Code's core is not public; repository documentation cannot establish its internal algorithm. The [harness memo](harnesses.md) and [pinned register](harness-sources.json) distinguish code from documentation evidence.

The assertion that eleven production harnesses import no general-purpose framework is not verified. Its literal universal form is too broad: Aider's optional help uses LlamaIndex, while its coding loop remains custom. Some inspected projects are explicitly experimental. Source inspection does not establish causal benchmark superiority.

**Adopt now:** retain Foundry's small controller, existing bounded retrieval and execution/approval authority. Improve the actual contracts and failure evidence. **Prototype next:** independently evaluate alternative planning/context policies on matched tasks. **Reject for now:** framework replacement, multi-reviewer consensus, unrestricted shell tools, permanent agent swarms and source self-promotion without measurable benefit.

## 3. Orchestration and parallel work

Sequential work is appropriate when later app tasks depend on earlier interfaces or share a limited local GPU. Extra agents add context duplication, coordination and integration costs. Parallelism helps independent research, test execution and truly isolated tasks; it is not automatically useful for editing the same small app.

This campaign used four bounded read-only research lanes with separate artifact directories. One integrator edits the existing checkout. No parallel code-editing workers or worktrees were needed. If future independent editing workers are justified, use isolated branches/worktrees and an integration gate; never infer success from worker summaries.

**Adopt now:** named dependency/file/outcome contracts, matching-request draft checkpoints, full-proposal approval, per-attempt rejection findings and source-bound finish receipts. Preserve frozen behavioral checks. **Prototype next:** compare a single full-plan call with small schema-constrained planning stages on the same real model/hardware. **Untested:** latency/quality benefit from model parallelism or extra reviewers.

## 4. Local inference versus the harness

Ollama, LM Studio, llama.cpp and vLLM are serving/inference layers; OpenAI compatibility is a protocol surface. Foundry is the agent/controller layer above them. A discoverable model can still fail structured generation, run out of context, lack quota, or be too slow. vLLM's primary docs require Linux rather than native Windows; Windows use would need a separately validated compatibility route. See [local analysis](local.md) and [source register](local-sources.json).

The uploaded log proves a 120-second transport failure and subsequent invalid proposals. It does not identify a GPU-fit, load, prefill or decode bottleneck. Existing Ollama timing arrives only after a completed response. The RTX 3050 name and Windows AdapterRAM output do not establish usable VRAM or actual inference placement.

The existing full planner system prompt is 10,450 UTF-8 bytes before request data and schema. Its examples contradict its own task requirements. Shrinking a request without removing requirements, and requesting a smaller output artifact per call, are more grounded interventions than guessing a faster model. Explicit context/output reservation stays in place; the planner floor is not lowered. Guided stages use shorter purpose-specific system instructions while retaining the complete user request and final acceptance contract.

**Adopt now:** consistent examples, staged native schemas, bounded task batches, explicit longer local planning timeout choice, known timeout/connection distinctions and clear unknown phase data. **Prototype next:** representative local calibration of model load, prompt evaluation, generation rate, structured task validity and peak memory. Thinking controls are an experiment candidate, not automatically disabled: effects on quality remain unmeasured. **Reject for now:** hardware-fit claims, hard-coded speculative model IDs or moving Windows users to another runtime as if that alone created an agent.

## 5. Foundry's actual bottlenecks and adoption plan

The [workflow audit](workflow.md) and [baseline probes](baseline-probes.json) identify reproducible source-level defects: task examples omit required fields; legacy starter task examples conflict with new task limits; repair payloads omit active task scope; rejection attempts lose exact findings; model settings drop single-fallback options on unrelated saves. New single-pass proposals can also use the historical unversioned task format. Legacy loads must remain compatible, so the new guided path explicitly requires the versioned contract and never treats a partial outline as approvable. Existing single-pass compatibility remains visible; no saved plan is silently migrated.

| Priority | Adopted change | Acceptance boundary |
|---|---|---|
| P0 | Correct examples and add outline/task-batch planning | Complete proposal passes existing reviewer; original checks cannot be changed by task batches |
| P0 | Carry active task packet through static repairs | Out-of-scope candidates fail before replacement, with original source retained |
| P1 | Retain findings, digest and transport detail per attempt | User can distinguish response rejection, known timeout, connection and unknown phase |
| P1 | Resume guided drafts only when the complete request hash matches | Changed revision/request starts a new draft; partial state remains unapproved |
| P1 | Preserve fallback options and expose explicit route/mode controls | Saving another setting does not erase fallback context/output/timeout |
| P1 | Calm progress/recovery panel and one guided action | Browser proves the full plan/approve/build/check/export workflow |

The staged path may use more calls. It is an explicit action, retains call/repair ceilings and cloud consent, and is not silently enabled for paid routes. Unknown live-model quality/cost stays unknown. The release target is controller reliability and task delivery transparency, not an unsupported exponential quality claim.

## Verification boundary and next measurable target

Frozen historical inputs remain unchanged. New synthetic fixtures reproduce the uploaded failure class and task/configuration defects; real HTTP and Chromium exercise controller paths and generated-app verification. Passing these does not establish a live Ollama win. The next real target is one full, schema-valid Loot Locker proposal on the user's machine followed by an independently checked app. Record model IDs, local context/output/timeout settings, whether thinking is enabled, Ollama load/prefill/decode metrics, call usage and actual observed results. Do not request API keys in chat.
