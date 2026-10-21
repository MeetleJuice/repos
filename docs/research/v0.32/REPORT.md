# v0.32 focused planning and diagnostic research

Access date: 2026-10-21. Exact URLs, response status, byte count and content digest are in `sources.json`. Public documentation is guidance, not a measured Foundry success-rate result.

## Sources actually inspected

- **Ollama official API documentation** (`ollama/ollama`, `docs/api.md`): JSON-schema `format`, `eval_count`, `eval_duration` and `prompt_eval_count` support existing structured local requests and provider-reported timing. Apply the feature-task schema to the actual local request and narrow its file limit. Schema-conforming output still needs semantic review. No minimum hardware/context claim follows from the API contract.
- **OpenTelemetry GenAI span conventions**: the old semantic-conventions path now points to `semantic-conventions-genai`; the current document was fetched and inspected. Operation, requested/response model, error class and token usage are distinct attributes. Apply this distinction to our existing ledger; do not add a telemetry dependency or automatic external export. Several GenAI conventions are marked Development and are not treated as a permanently stable standard.
- **OWASP Logging Cheat Sheet**, event attributes and “Data to exclude”: record meaningful operational failures and correlation while omitting access tokens/passwords and sanitizing exported data. Apply through the existing structural projector, not through pattern redaction alone. More useful metadata is preferable to copying every raw prompt or response.
- **Anthropic official Python agent SDK README**: request/session controls and explicit tool boundaries illustrate that runtime controls are distinct from model text. It does not demonstrate that adopting its SDK improves Foundry. No framework or SDK was added.

The direct Anthropic engineering, Ollama docs website, OpenTelemetry website and OWASP website requests failed in this environment. Their official repository sources were accessible as recorded. The unavailable engineering article is not claimed as directly reviewed evidence.

## Synthesis applied

The strongest local evidence is the user's own journal: task bookkeeping and milestone placement were causing repeated deterministic rejection before any coding. Use a small, versioned compiler to own those references, preserve all validation gates, and require one semantic feature at a time. Keep independent safe telemetry for the controller's decisions. Bound correction cost per stage, preserve accepted unapproved work, and make missing data visible.

## What is and is not demonstrated

Frozen synthetic replies exercise reference compilation, native schema integration, scope rejection, unchanged acceptance checks and interruption/resume. Browser tests execute real generated-fixture app behavior and test/ZIP delivery. They do not recreate the missing historical candidate JSON, measure model intelligence, prove provider quota, or benchmark the user's RTX 3050. A fresh user run and expanded Diag are the next necessary evidence.
