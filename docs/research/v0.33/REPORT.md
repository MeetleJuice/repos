# v0.33 research and observed failure boundary

Primary repository documentation was fetched on 2026-10-21; URLs, sizes and digests are in sources.json. This is engineering guidance and controlled regression evidence, not a live-model success benchmark.

## What the uploaded run proves

The diagnostic manifest's 15 members match their hashes. Installed v0.32.0 build identity matches the published source. The selected run made 18 requests in 549.037 seconds, all in the outline stage. Twelve provider/rate/quota/timeout failures and six completed-but-invalid proposals prevented task compilation entirely. Qwen timed out at 300 seconds; DeepSeek returned normal stops around 30 tokens/second. GPU activity and available RAM were recorded, but they do not prove a memory-related timeout cause.

Fixed validator-message digests match: a non-object-array checks field; missing acceptance coverage for features [6,8] and [6,7]; missing concrete mutation data and meaningful restart evidence; and missing assertions in both DeepSeek replies. Original candidate bodies are absent. The new fixture records known messages and explicitly synthetic scope/acceptance examples, not reconstructed historical provider replies.

## Sources applied

- **Ollama official API**: schema `format` versus JSON mode; evaluation counters/timing; read-only `/api/ps` and `/api/version`. Add requested format/context metadata and loaded-model observations without fetching modelfiles/templates, loading models or generating text. Installed versions may omit context length; absence remains unknown.
- **OWASP Logging Cheat Sheet**: correlate meaningful events while excluding credentials, private data and arbitrary bodies. Apply the shared structural sanitizer to persistent Test results and exports. Test IDs link individual results; preserve previous run events in the bounded recorder while the separate report stores the latest run.
- **OpenTelemetry GenAI conventions**: requested model, response model, operation, error class, token usage and content handling are separate concerns. Our existing local recorder is retained; no telemetry dependency or automatic upload was introduced. The GenAI conventions include Development fields and are not treated as an immutable API.

## Decisions

Split scope and acceptance into separate schema-constrained requests before compiling tasks. Keep complete user requirements and request identity, preserve checked acceptance behavior, and require the unchanged final full-proposal review. Checkpoint validated scope so interruption does not force its regeneration. Return all deterministic acceptance findings with specific codes/paths.

The Test button distinguishes no-generation checks from optional fixed inference probes. At most one saved model per cloud provider and two saved local models are probed (nine total), once each without fallback/retries. Cloud probes require explicit consent and can incur charges. Storage/controller/catalogue checks do not execute generated code. A tiny successful response does not establish project fitness, remaining quota or GPU capacity. Test outcomes never change saved routes or routing cooldown decisions.

Read-only local runtime observations accompany existing resource samples roughly every 30 seconds and are also captured in Diag. Extra samples consume the same finite retention budget; they do not create complete lifetime history. Socket timeouts are not hard whole-run deadlines; Stop is cooperative between checks. Continuous metadata and Test probes provide evidence for the next real user run, not a promise that providers with exhausted credits will start working.
