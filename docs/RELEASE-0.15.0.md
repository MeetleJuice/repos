# 0.15.0 — Seven-provider cloud studio

Supported cloud adapters: Gemini, Groq, Cloudflare Workers AI, OpenRouter, NVIDIA NIM, Requesty, and Hugging Face Inference Providers. Ollama remains available alone or as an explicitly configured last resort. Existing three-provider routes, project state, approved checks, files, snapshots, history and ZIP contracts are retained. No provider SDK dependency is added.

## Set up on your PC

1. Back up your workspace, update and restart Foundry. In Models, choose your Desktop .env/.env.txt again. The earlier private copy will not automatically follow Desktop edits.
2. Recognized canonical names are below; common aliases are documented in .env.example. Never share real values in chat or commit them.

```dotenv
GEMINI_API_KEY=
GROQ_API_KEY=
CLOUDFLARE_API_TOKEN=
CLOUDFLARE_ACCOUNT_ID=
OPENROUTER_API_KEY=
NVIDIA_API_KEY=
REQUESTY_API_KEY=
HUGGINGFACE_API_KEY=
```

HF_TOKEN is accepted for Hugging Face, OPENROUTER_KEY for OpenRouter, and CLOUDFLARE_API_KEY/CF_API_TOKEN for the Cloudflare Workers AI token. A legacy global Cloudflare API key is not a Workers AI bearer token. Cloudflare also needs the 32-character hexadecimal Account ID from your Cloudflare dashboard. If only its token exists, Foundry displays missing_configuration and other providers remain usable. Do not put the Account ID in a chat message.

3. Click Check cloud providers. This checks read-only catalogues (and additional identity endpoints where implemented); it sends no project content. Keys being present or a catalogue being reachable does not prove generation authentication, inference permissions, quota, pricing or JSON support. A provider requiring setup or returning an error can be left skipped.
4. Select an advertised chat/coding model for each provider you want. Previously skipped providers stay skipped until you choose a model; new providers are not silently added to approved routes. Requesty has no guessed default model. Review paid-model choices.
5. Use Earlier/Later to order the cards. The first selected model is primary; later selected models form the failover list. Optional Ollama is appended last. Set a socket timeout (15/30/60/120 seconds; new cloud profiles default to 60). These are socket timeouts, not absolute whole-job deadlines. Smaller timeouts may interrupt otherwise successful long generations.
6. Native JSON output is requested by default. If an advertised model does not support that API parameter, you can disable it for that provider and apply again; returned content must still parse as JSON. Ollama's separate advanced setting controls native schema use while retaining basic JSON mode. Model support varies.
7. Apply for new projects or this project. Applying does not generate code, approve a proposal or permit execution. Existing project files/requirements are kept. Cloud consent remains required when starting a job; execution consent remains separate.

## Failover behavior

Flat routes support seven cloud providers plus optional Ollama (eight total configurations). Eligible auth, model access, quota, rate-limit, service, transport, missing configuration, malformed JSON and response-size failures advance to the next explicitly configured tier. A single legacy fallback remains supported. A hung request must fail or time out before switching; there is no claim of instantaneous detection. Rate-limit cooldowns are recorded and skipped rather than slept through. Cloudflare requests use documented rejectIfBusy to avoid capacity-queue waits where supported.

Truncation is an output-budget failure. It still gets at most one same-model continuation and one fresh shortening, and cannot select a fallback with a smaller recorded output ceiling. Invalid continuation JSON uses shortening. Valid JSON with invalid app files goes through existing pre-write validation and the single focused response correction; it is not a claim the provider is down. Static/runtime/manual repairs retain the job's shared 0–3 allowance. Every attempt retains the requested provider/model, transport flag, timeout, error class and recovery path in project history. If an aggregator supplies a resolved model/provider name, it is recorded separately as provider-reported identity, not independently verified identity.

## Compact proposal budgeting

The reported Tiny Colony revision reserved more than 8192 estimated output tokens, blocking a free router that had previously returned a full proposal in 4163 reported tokens. The controller now allows an explicit compact schema-complete proposal at the existing configured/automatic output floor when that floor still fits the model input/context/output room. It retains the entire request and approval schema, adds a compact-response instruction, and labels budget_compaction. It never lowers a user floor, claims a known capacity is bigger, removes checks, or omits source context. Actual truncation remains bounded and capacity-safe. Fitting is not guaranteed; runtime responses and deterministic proposal review remain authoritative.

Published model limits are cached when available; absent values remain conservative/estimated. Parallel catalogue checks serialize cache updates so provider records do not overwrite one another. A cache write failure is reported without hiding an otherwise available catalogue.

## Validation and limits

The extracted distribution passed 279 automated tests and three browser workflows; strict type checks passed for 15 modules. These use controlled provider fixtures and loopback servers, not live cloud generation. See research/provider-pool-v1.md and research/provider-pool-results-v1.json. Fixture and loopback tests cover import/privacy, wire contracts, eight-model route validation, seven-tier fallback, timeout classification, compact planning, truncation bounds and real browser setup/generation/verification/export. Live keys are on the user's PC and are not available in this cloud checkout. Direct Requesty/NVIDIA documentation or live catalogue access was restricted here; their adapters still need generation checks with the user's actual keys/models. No universal provider-availability or model-quality claim is made.

After update, apply the new route to Tiny Colony, review/approve its corrected proposal if still pending, then generate/resume its saved tasks. Review history for the provider actually used. Keep the old working app folder until the new output has been tested.
