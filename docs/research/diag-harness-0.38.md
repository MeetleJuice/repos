# Diagnostic-driven harness revision — 0.38.0

Research and implementation date: 2026-10-22. This revision addresses a measured planning blockage and an awkward evidence-collection workflow. It does not promise that every model or application will succeed.

## What the latest evidence establishes

Diagnostic report `4ba010aec9c7430e94c16053bc08c9a5`, packaged version 0.37.0, contains a complete retained planning run with ten requests and 499.28 model seconds. Scope succeeded after one timeout. The first feature's acceptance stage then had six schema rejections and two timeouts, with zero accepted drafts. No implementation task started. The three timeouts consumed 360.34 seconds, about 72% of model time.

All six rejected drafts share the digest of the existing source literal “Every check needs contains, nonempty json_contains, or json_equals.” The recorder retained generic `structure` findings and sometimes showed an assertion field present without establishing that its value was usable. Original rejected response bodies were intentionally excluded, so they cannot be reconstructed from this report. `diag-planner-wire-v2.json` freezes the observed sanitized ledger and labels new controller inputs synthetic.

Two tiny local JSON probes passed at 4096 context and 1024 output. That establishes those specific responses only. Real planning used 32768 context and 8192 output, with several models partly outside VRAM. Memory pressure is a plausible contributor to latency, not a proven cause of each timeout. Cloud catalogue checks do not establish inference quota. Historical workspace failures are not current provider failures.

## Research → implementation decisions

| Subject | Primary-source lesson | Applied decision | Boundary |
| --- | --- | --- | --- |
| Prompt engineering | Ollama recommends both a schema and an instruction to return JSON; a schema alone is not semantic guidance. | Feature wire v2 states goal, fixed context, constraints and completion; a rejected draft receives the actual target feature, earlier checks and precise finding path. | No extra model reviewer or hidden change to approved checks. |
| Context engineering | OpenAI's session-memory example discusses focused histories and the risks of losing important context during summarization. | Preserve complete user/baseline values, validated earlier acceptance and existing omission manifests. Correct the actual packet fields rather than referring to stale names. | No new lossy summarizer, embedding store or automatic context reduction. |
| Harness engineering | llama.cpp documents a JSON Schema subset, including a warning against mixing `properties` with `anyOf`/`oneOf`. | New explicit feature-by-feature requests use required `assertion:{kind,expected}`; the controller compiles exact values into existing canonical checks and invokes the same reviewer. | Compatibility hypothesis, not proof about the converter in the user's exact Ollama build. Legacy v1 remains supported. |
| Loop engineering | OpenAI's runner describes a bounded turn loop with typed output, terminal conditions and explicit exceptions. | Retain existing bounded correction/fallback rules. Add an independently identified diagnostic lifecycle with start, progress, stop, partial collection, completed snapshot and exact export. | No framework dependency, unbounded search, agent swarm or automatic self-modification. |
| Agentic evaluation | Anthropic's evaluator/optimizer example uses clear criteria and actionable feedback. | Deterministic assertion validation supplies specific correction evidence. A fixed planning probe uses the real stage prompt, schema, reservation, compiler and reviewer. | Do not copy its illustrative unbounded loop or let a model's own PASS authorize progress. |
| Debugging and observability | OpenTelemetry's developing GenAI conventions distinguish operation/error identifiers and correlated evaluation results. | Record schema version/hash, assertion validity, precise paths, owned Test/session IDs, latest-run rejection/timeout totals and explicit skipped work. | No telemetry SDK, automatic upload, raw prompts/source or sensitive trace capture. This is not an OpenTelemetry-conformant exporter. |

## Why the wire changes

The old schema offered several optional assertion fields and a mixed object/union requirement. A response could be syntactically JSON while missing a meaningful assertion. Wire v2 requires one named kind and one value. `text` compiles to `contains`, `json_subset` to nonempty `json_contains`, `json_exact` to `json_equals`, and `empty` with null to `empty_body:true`. Exact empty arrays/null and Unicode retain their values. Invalid assertions, mixed legacy fields and unrecognized kinds are rejected before a prefix is saved. The ordinary full approval contract, task/check compiler and execution gates remain authoritative.

The browser explicitly selects v2 for new feature-by-feature planning. Direct/legacy requests and saved v1 prefixes retain v1 unless a new v2 strategy is explicitly requested. Merely installing an update does not migrate approved projects. Single-pass, builder-stage and evidence-stage workflows retain their existing contracts.

## One Diag workflow

Default Diag starts safe private-storage/controller/planning/repair guards, selected-plan/build evidence audits and local/provider catalogue checks. It never runs generated code or model inference by default. An active job causes passive collection with a visible skipped reason. Catalogue calls are network operations and still use their existing timeouts.

Optional modes add either tiny local JSON probes, up to two local acceptance-stage probes, or tiny cloud/local probes with explicit cloud consent. Inputs are fixed synthetic data. Planning probes retain configured context and reserve at least the existing 8192-token floor; an impossible budget fails before transport. No probe ranks models, changes routes/cooldowns or establishes project/GPU fitness.

Each session owns its Test ID and captures that exact result before collection. An unrelated later Test cannot replace it. Status polling does not repeat checks. Closing/reopening joins active work. Stop requests take effect between operations; an in-flight socket operation must return or time out. Partial reports remain downloadable. Export requires the completed session ID and never silently recollects. The persisted last completed report survives a restart; an interrupted run without a report is labeled interrupted. Identical report content produces deterministic ZIP bytes and a manifest of its exported entries.

## Evidence and next measurement

`tests/test_diag_revision.py` covers the captured run totals, append-only frozen hashes, exact wire compilation, current correction fields, saved prefix resume, real loopback HTTP schema/reservation, session ownership, overlap, stop and consent. Browser checks exercise unified Diag, mobile layout, literal-text safety and a real SQLite application build/verification/export with scripted model responses. The final release validation file records source and extracted-archive command results.

Live Windows/Ollama quality, latency at the configured context, GPU residency and cloud quotas remain untested here. The next useful local measurement is the explicit acceptance-schema probe followed by one small feature-by-feature SQLite project. Compare accepted prefixes, validation paths, model seconds, timeouts and actual app checks with the frozen report; do not substitute tiny-probe success for end-to-end delivery.

## Sources and access limits

All retrieved sources are primary project documentation, not independent comparative benchmarks. Retrieval byte counts and SHA-256 values are retained in [the source manifest](diag-harness-sources-0.38.json). A moving upstream document is not proof about an installed version.

- [Ollama API](https://github.com/ollama/ollama/blob/main/docs/api.md): schema format, JSON instruction, output/context controls and timing metadata.
- [llama.cpp grammar documentation](https://github.com/ggml-org/llama.cpp/blob/master/grammars/README.md): supported subset and mixed `properties`/union limitation.
- [OpenAI session-memory example](https://github.com/openai/openai-cookbook/blob/main/examples/agents_sdk/session_memory.ipynb): focused context and summarization tradeoffs.
- [OpenAI running-agents guide](https://github.com/openai/openai-agents-python/blob/main/docs/running_agents.md): loop termination, maximum turns, guards, resource ownership and sensitive tracing.
- [Anthropic evaluator/optimizer example](https://github.com/anthropics/anthropic-cookbook/blob/main/patterns/agents/evaluator_optimizer.ipynb): feedback against explicit criteria; its unbounded sample loop was not adopted.
- [OpenTelemetry GenAI events](https://github.com/open-telemetry/semantic-conventions-genai/blob/main/docs/gen-ai/gen-ai-events.md): developing correlated evaluation/error semantics. The old repository page redirects to this repository.

An attempted Codex `core/prompt.md` URL was unavailable; GitHub API tree discovery was blocked by the network proxy. Neither supplied evidence for implementation claims. Existing repository research remains a historical comparator and was not relabeled as newly verified research.
