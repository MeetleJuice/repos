# Cloud routing research and implementation decisions

Reviewed 18 October 2026. This pass extends Foundry's existing stdlib adapters; no extra Python
SDK, Node installation, server deployment or API-key upload to the development workspace is required.

## References checked

- [Google Gen AI Python SDK](https://github.com/googleapis/python-genai/blob/main/README.md):
  model discovery, API authentication, output configuration, and explicit client/network settings.
- [Groq Python SDK README](https://github.com/groq/groq-python/blob/main/README.md) and
  [API surface](https://github.com/groq/groq-python/blob/main/api.md): model listing, classified
  connection/status errors, default one-minute timeout, and SDK retries. Its default hidden
  retries would multiply our explicit provider loop; the stdlib adapter keeps attempts visible.
- [OpenRouter Python SDK](https://github.com/OpenRouterTeam/python-sdk/blob/main/README.md):
  provider aggregation and explicit model selection. Foundry keeps its existing OpenAI-compatible
  HTTP adapter and lets the account's returned catalogue determine selectable IDs. The official
  [key metadata implementation](https://github.com/OpenRouterTeam/python-sdk/blob/main/src/openrouter/api_keys.py)
  confirms GET /key for the authenticated current key. Foundry checks that endpoint before
  reading OpenRouter's public model catalogue; a public catalogue read alone cannot validate a key.

These official repository sources were retrieved during development. The Google/Groq/OpenRouter
hosted documentation and public model endpoints returned proxy 403 errors in this cloud environment.
No real account keys are available here: the user's keys are on their Windows desktop. Consequently
we do not claim a live provider availability, free-quota, model-quality or throughput benchmark.
The application's local checks are the route to establish account-specific access.

## Decisions grounded in the actual app

1. **Separate key presence, model access and generation.** A key detected in .env is not proof of
   valid credentials. A successful catalogue read is not proof of remaining generation quota,
   JSON-output support or adequate context. The UI labels those states separately; actual jobs
   show the provider that responded and provider-reported token counts when supplied, including
   malformed/truncated replies. A new request clears prior usage so transport failures cannot
   accidentally reuse the previous request's counts.
2. **Discover before selecting.** Do not assume `gemini-3.8-flash` or `qwen/qwen3.8-27b` exists.
   Prefer known IDs only if returned by the account's catalogue, otherwise let the user select
   another returned generative model. Embedding/audio/guard/image-only IDs are filtered. Catalogues
   are checked concurrently with ten-second socket timeouts, not during every generation request.
3. **Bound routing, not just exception handling.** A flat route has one primary and at most two
   fallbacks. Try Gemini, Groq and OpenRouter in that order among selected providers. Service,
   transport, authentication, unavailable-model, quota and request-format HTTP failures can move
   to the next tier. No automatic local-model fallback is introduced. Existing legacy single
   fallbacks retain their behavior. All tiers unavailable stops the planner's service retry loop.
4. **Do not confuse bad code with unavailable service.** Model JSON/contract failures use the
   bounded correction process; truncation needs output/scope adjustment. Actual failing app tests
   use the repair loop. Those are not reasons to silently cycle through every API.
5. **Respect resource limits visibly.** Every cloud completion has max_tokens. Per-provider caps
   are selectable from 1024/2048/4096/8192; Groq starts at 4096, other builders at 8192, and planners
   use at most 4096. Low limits can truncate output; output limits do not constrain input TPM or
   guarantee a free tier. A cloud request uses a 60-second socket timeout with no hidden SDK retries.
6. **Cooldown rather than immediate repeated rate-limit requests.** Numeric Retry-After is capped
   at 300 seconds; a 429 without a numeric value uses 30 seconds. Skip the affected provider/model
   on subsequent requests during that interval. Never sleep holding the inference lock. Importing
   or explicitly reloading credentials clears these temporary cooldowns; stop is checked before
   the next tier. A socket request already in flight must return/timeout before stop takes effect.
7. **Make Windows setup concrete.** A local file picker accepts .env/.env.txt and UTF-8/UTF-16
   Notepad files. Only known key assignments are imported, never evaluated. The copy is persisted
   atomically in the workspace, survives side-by-side updates, and never enters project exports.
   Existing unrelated local .env entries are preserved; no arbitrary Desktop scan occurs.

The controlled regression follows the complete key-file → catalogue → profile → consent → planning
failover → generation failover → actual generated-app tests/launch path. A real loopback HTTP test
also checks auth headers, max_tokens, error responses, ordered attempts and actual usage records.
These tests establish mechanics, not live model quality. The next meaningful benchmark is the
same fixed app tasks on the user's actual accounts/models, recording success, repairs, latency
and quota failures rather than assuming a model's size or provider guarantees quality.
