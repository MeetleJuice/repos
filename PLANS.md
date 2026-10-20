# 0.25 local harness update

## Phase 1 — audit and research
Scope: provider adapters, routing, capabilities, task execution, model/workflow/update controls and release packaging. Record primary-source provenance in docs/research/local-harness-sources-0.25.0.json.
Non-goals: framework migration, adding cloud providers, live billed experiments.
Acceptance: architecture and phased decisions recorded before implementation; regression input frozen.

## Phase 2 — local runtime support
Scope: loopback-only OpenAI-compatible endpoint (LM Studio or llama.cpp), optional private runtime key, model discovery, explicit persisted routes, consent and status labels.
Non-goals: installing runtimes/models, remote gateways, silently replacing existing routes.
Acceptance: real local HTTP fixtures exercise discovery and inference; local-only routes require no cloud consent; remote endpoints are refused.

## Phase 3 — bounded task execution
Scope: deterministic finish gate rereading the approved task/checkpoint/source, repeated identical-call detection, optional local token streaming with cooperative cancellation and bounded previews.
Non-goals: additional model reviewers, semantic correctness inferred from static checks, unrestricted shell tools.
Acceptance: changed-plan, repeated-call, cancelled-stream and missing-terminator regressions fail safely; saved candidates remain resumable; frozen acceptance checks stay unchanged.

## Phase 4 — usability and release
Scope: discoverable model controls, quiet live response display, progressive disclosure, reduced motion, structured update-ready event and dismissible banner, versioned archive.
Non-goals: automatic installation, cloud response streaming, desktop notification permission prompts.
Acceptance: actual browser flows cover model selection, preserved approval, live progress and update banner; full checkout/extracted tests and strict type checks pass before publication; updater validates the published archive.

Each phase is developer-controlled. This file does not authorize a generated app or model to modify Foundry or bypass project approval.
