# Model operation audit — 0.16.0

Baseline: a151ec4 / 0.15.0. Trigger: user-provided 2026-10-19 Josh dashboard log. Raw provider responses and real keys were not provided. The frozen planner-semantic-routing-v1.json was created before this pass's implementation and labels its synthetic provenance.

## Scripts and responsibilities

- providers.py: provider registry, endpoint and environment aliases.
- credentials.py: private .env import/reload, no project credential storage.
- cloud.py: read-only catalogues, published limits, manual settings, automatic model ranking and persistent role-specific routes.
- capabilities.py + model-capabilities-v1.json: explicit output reservation and hard/estimated capability records.
- routing.py: validated flat configuration bounds, options, cloud detection and truncation-capacity eligibility.
- models.py: stdlib HTTP adapters, optional native output format, finish/usage metadata, strict JSON parsing, root contract.
- core.py: serialized requests, consent, per-job rejection/attempt state, semantic planner routing, compatibility and truncation recovery, ledger and file/approval gates.
- planning.py: outer deterministic proposal rounds; pooled routing now handles semantic corrections before returning a candidate.
- server.py: authenticated local setup/application endpoints; automatic setup uses existing key/Ollama discovery.
- static/cloud.js + index.html: one automatic setup action, advanced manual controls, role route application.
- static/planning.js: manual project/model settings and full route display.
- history.py/reporting.py: retained attempt metadata, attribution and exports.

## Research and design

Google's maintained python-genai README JSON Response Schema section recommends avoiding duplicated schema/example definitions in prompts when native schemas are used. This pass uses a concise authoritative root-field reminder rather than copying the full schema into every prompt; existing native Ollama schema support remains intact. Source retrieved 2026-10-19: https://raw.githubusercontent.com/googleapis/python-genai/main/README.md (56828 bytes). This is implementation documentation, not evidence that the user's specific Gemini model has access/quota.

OpenRouter maintained SDK README confirms the API compatibility/integration boundary; source retrieved https://raw.githubusercontent.com/OpenRouterTeam/typescript-sdk/main/README.md (6719 bytes). Provider-level routing cannot establish Foundry-specific proposal validity; that must be evaluated by Foundry and recorded separately. No claim that an aggregator's provider fallback fixes invalid proposal semantics.

Existing provider-pool-v1.md documents the seven endpoint sources and direct-site access limitations. No provider SDK or new dependency is introduced. The correction design follows bounded validation-feedback control: validate, one repair attempt, advance, retain provenance. Ranking is deliberately labeled heuristic; no live-model quality benchmark has been performed.

## Limits

Automatic setup cannot manufacture missing permissions, balance or Cloudflare Account ID. It performs read-only discovery without paid inference probes. All actual generation retains user consent and failure handling. The 24-call planning allowance bounds cost exposure per job but does not replace provider timeouts or user cancellation. No universal project-completion, cost-reduction or repair-quality claim follows from replay success.
