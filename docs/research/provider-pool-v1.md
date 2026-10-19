# Seven-provider routing audit and blueprint

Baseline: v0.14.0 / 4d1059a. User requests Gemini, Groq, Cloudflare, OpenRouter, NVIDIA, Requesty and Hugging Face; existing Ollama must remain optional. User confirmed only a Cloudflare token is saved: Workers AI also needs CLOUDFLARE_ACCOUNT_ID. Never request key/account values in chat.

## Current bottlenecks (frozen before implementation)

Only three cloud providers are allowlisted across credentials, adapters, route validation, catalogue setup and UI. Fallback lists are capped at three (four total models), and history redaction knows only the original keys. Provider checks do not prove generation quota. All cloud inference adapters use a 120-second socket timeout. A six-task Tiny Colony revision is refused by an estimated planner output requirement above the free router's 8192 ceiling, even though the previous complete response used 4163 reported output tokens.

## Research

- Cloudflare official docs, fetched raw GitHub: workers-ai/configuration/open-ai-compatibility.mdx. OpenAI-compatible base is https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1, Bearer token. cloudflare-python models resource documents /accounts/{account_id}/ai/models/search. workers-ai/features/reject-if-busy.mdx documents top-level options.rejectIfBusy=true; busy requests return HTTP429.
- Hugging Face official hub-docs docs/inference-providers/index.md documents its OpenAI-compatible router and GET /v1/models. tasks/chat-completion.md documents chat completion schema. Account identity checking does not prove inference permissions/quota.
- NVIDIA's langchain-nvidia endpoint implementation uses https://integrate.api.nvidia.com/v1 and /models. Direct NVIDIA API reference access was blocked here; no live key/quota verification is claimed.
- Requesty direct documentation and catalogue access were blocked in this environment. Integrate the known https://router.requesty.ai/v1 OpenAI-compatible endpoint behind explicit selection and authenticated catalogue checks; report failures without claiming live compatibility or inventing model IDs.

Source snapshots and fetch errors retained under /tmp/foundry015-research. No SDK dependency is needed: standard-library HTTP adapters already fit the supported contracts.

## Blueprint

Centralize provider identities, keys/aliases and endpoint rules. Import seven keys plus Cloudflare account configuration from the local UTF-8/Notepad .env. Store no keys in project state or cloud route profiles. Extend secret redaction to every supported alias. Validate seven-cloud-plus-optional-Ollama flat routes, with selectable order and per-provider timeouts; preserve older routes. Skip missing configuration/catalogue failures with clear diagnostics. Use advertised model IDs, not guessed unavailable defaults.

Try the next explicitly configured model immediately after eligible errors; never sleep for a rate-limit cooldown. A hung request must time out first. Record actual provider, transport attempt, failure category, recovery and timeout. Keep truncation separate, preserve same-model bounded recovery and the no-smaller-output-ceiling rule. Refuse unsupported response formatting only through explicit settings; do not silently invent schema support.

For preflight planning estimates larger than a model ceiling, allow a compact schema-complete response reservation at the configured/automatic floor only when that floor still fits input/context/output limits. Preserve the entire request and approval schema; never lower a user's floor or a known hard capability. Actual truncation still triggers bounded recovery and capacity-safe fallback. This is a controlled alternative to refusing all tiers on a conservative estimate, not a promise the proposal will fit.

## Gates

Freeze seven-provider fixture metadata before code changes; test aliases/config privacy, discovery wire contracts, ordered failover/cooldowns/timeouts/JSON errors, truncation ceiling guards, budget-compaction, auth/session/UI setup, actual generated-app verification and export. Full suite, strict types, Chromium, extracted distribution and public updater checksum required. Live access for all seven remains to be checked on user's PC with local keys.

## Paired release comparison

The concrete Tiny Colony request and reviewed full response are frozen in planner-compaction-v1.json before the paired release comparison. The initial provider-pool case metadata was frozen before implementation. Against published v0.14.0, that request fails output_budget with zero API invocations. Candidate v0.15.0 makes one controlled API invocation at cap 8192, recovery budget_compaction, and parses a full ten-feature/six-task/nine-manual-check proposal. The input user message is byte-for-byte preserved. These are fixture outcomes, not live provider tokens/quality. New regressions also cover compact truncation stopping after continuation/shortening, explicit floor refusal, socket-timeout fallback, concurrent catalogue cache writes, failed cache persistence and safe provider-reported identity metadata.
