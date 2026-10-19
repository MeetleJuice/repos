# v0.21.0 — explicit hybrid routing and evidence-aware task progress

## Findings from Quest Board

The supplied log has 4/6 saved tasks, a rejected exact edit on the persistence task and a no-change correction rejected by v0.20.0. Local Ollama is last in a 15-model route and was never attempted in that run. The historical code is not attached, so persistence cannot be assumed implemented. Provider, rate-limit, transport, model-access and quota errors are separate problems; changing task logic does not restore quota or fix an inaccessible model.

Three weaknesses were actionable: cloud-first alternates delayed local participation; slow/unavailable providers were retried across tasks; and the structured-task rule required an edit even when existing source might address the task. This release addresses those boundaries without asserting that quoted code proves behavior.

## Research and chosen practices

Primary-source snapshots, sizes and hashes: [source register](research/hybrid-sources-0.21.0.json).

- **Ollama API documentation:** JSON schema output, explicit context/output settings, `keep_alive`, and load/evaluation timings. Foundry already uses native schema output, explicit budgets and five-minute residency. Keep these controls and record actual local timing rather than guessing GPU fitness from the model name.
- **Groq Python SDK README:** connection/status error distinctions, bounded retries, backoff and timeout configuration. Foundry keeps its standard-library transport instead of adding another SDK/retry layer. Retain Retry-After handling and non-sleeping fallback; add a finite provider transport/service circuit to pooled routes. A raw socket timeout is still not a hard job deadline.
- **GitHub Spec Kit task template:** deliverable stories, explicit paths, dependencies and independently testable increments. Retain v0.20's approved task contracts and file bounds; integrate persistence with storage behavior and tests instead of assigning mandatory late rewrites. The builder can request source-supported progression only through a checked response format.

These are authoritative implementation references, not comparative model-quality benchmarks. No source establishes that a particular model is universally best or that every project fits a local model. No extra consensus/planner agent, hidden truncation, unbounded retry, runtime dependency or automatic scope expansion is introduced.

## Routing modes

The Models panel now offers explicit automatic-setup modes:

| Mode | Planner | Builder | Cloud behavior |
|---|---|---|---|
| Hybrid (recommended UI default) | First eligible cloud, then local, then other cloud choices | Local coding model first, then eligible cloud choices | Existing cloud consent required |
| Cloud first | Existing cloud order; local last | Existing cloud order; local last | Existing cloud consent required |
| Local first | Local first | Local first | Configured cloud fallback still needs consent |
| Local only | Local only | Local only | Setup does not query cloud catalogues; inference route contains no cloud models |

When no eligible local model exists, hybrid/local-first use discovered cloud candidates; no model is invented. Local-only fails clearly if no eligible local model is installed. Embedding/vision candidates remain excluded. Coding-specialist installed models receive priority for local coding, so the user's `qwen2.5-coder:7b` is preferred over a general chat model for that role. This is a transparent name-based preference, not a measured quality or GPU-memory claim.

Selecting a mode does not silently rewrite running jobs or existing model choices. Click **Set up models automatically** to apply it to new projects and the open idle project. Historical API callers omitting `mode` retain cloud-first compatibility. Saved automatic mode is restored in the Models selector. Advanced manual routes remain available.

A local-first request is attempted only when the explicit context/output reservation fits the configured capability. Output ceilings and truncation-aware fallback remain authoritative; never force a smaller model after truncation merely to animate a local badge. GPU offloading, cold loads, context size and CPU speed can still make local inference slow. Installed/catalogue/responded/verified remain distinct states.

## Error handling and efficiency

Existing auth/model/quota rejection and Retry-After cooldowns remain. A new thread-safe in-memory circuit counts connection/timeout and provider-service failures. Two failures for a provider within five minutes trigger a two-minute cooldown on pooled routes. During that cooldown the controller logs a skipped provider without sending a request or sleeping. It then considers other configured eligible models. A successful response clears the provider's circuit; reloading the imported .env resets circuits alongside existing cooldown state. Cooldowns expire; they do not permanently remove models.

The circuit applies across a provider's models because the chosen failure classes may indicate a shared endpoint problem. This is deliberately conservative and can temporarily skip a working alternate at the same provider. It does not trip on source/schema rejections, output-budget refusal or truncation. Single-provider/manual legacy fallback semantics remain unchanged. No claim of a fixed overall speedup is made.

Safe HTTP status codes now accompany model-attempt records, journal failures and history presentation. Raw provider bodies remain hidden. Ollama-reported load/prompt-evaluation/generation seconds and output tokens/second are recorded when supplied; missing values remain unknown. These are provider timings, not a cloud cost estimate or a measured GPU benchmark.

## Task creation and execution

1. Review scope and reuse existing foundations.
2. Request bounded task contracts: one outcome, 1–3 editable paths, earlier dependencies and completion criteria.
3. Keep tests alongside behavior. A persistence task should add a meaningful restart regression if storage already exists; it must not demand an unnecessary storage rewrite.
4. Approve the unchanged proposal/acceptance artifact.
5. Supply full preserved source, budget and the approved task packet to the selected model.
6. Validate exact edits/file scope and frozen boundaries before applying changes.
7. If no change is needed, permit an explicit `already_satisfied` response containing a 20–1000-character reason and 1–4 exact 20–500-character excerpts from existing approved task files. It cannot be mixed with file updates or edits. Bad/missing/out-of-scope quotations reject. The bounded complete-files correction also supports this format, addressing Quest Board's exact failed-edit/correction sequence.
8. Record `existing_source_supported`, unchanged source hashes and `behavior_verified: false`. Uncited no-op responses still reject. Source citations establish only that the text exists; they can be semantically wrong and are **not proof** of task behavior.
9. Continue static inspection and saved task progress. The UI says existing source was cited and verification remains pending. Progress/dependencies remain saved-source progress rather than test success.
10. Run approved behavioral checks and manual acceptance only under existing execution/cloud consent. No source quote marks verification passed or weakens a frozen test. Existing checkpoint, repair-budget, export-fingerprint and portability protections remain.

The original task/proposal data and source are preserved. Existing approved plans are not secretly decomposed or given fabricated contracts. Structured Quest Board tasks can use the new source-response path without replanning. If a task's approved file list is genuinely wrong, scope changes still require a reviewed plan rather than disabling enforcement.

## Evidence, limits and next steps

See [validation](validation-0.21.0.md). Controlled regressions cover mode order/local specialist choice, no cloud catalogue calls for local-only, genuine source references, false/mixed claims, failed edit followed by source-supported correction, finite cooldown/reset and body-free HTTP diagnostics. Chromium tests exercise hybrid UI setup, actual cloud/local dispatch through a fixture adapter, unchanged task receipts, real generated-app verification and source-bound ZIP export.

There are no live provider credentials here. Local dispatch in tests uses a controlled adapter; it does not measure the user's Ollama, GPU, quota or model adherence. Fewer unnecessary edits, earlier local placement and bounded repeated failures are directly enforced. Improvement in end-to-end model success, cost or latency still needs representative real runs.

Next: collect per-task failures/latency/tokens on real apps, compare explicitly selected routes, identify oversized contexts and test independently checked behavior. Do not optimize by silently dropping files, lowering output floors, claiming success from model summaries or building an unbounded fallback loop.

## Provider-specific findings

Additional official references were read for Google Gen AI, OpenRouter, Hugging Face, Cloudflare and NVIDIA; hashes/access failures are in the source register.

| Connection | Relevant distinction | Foundry decision |
|---|---|---|
| Gemini | Native JSON configuration and explicit generation settings are separate from model access/quota | Keep the existing native adapter and budget reservation; do not infer generation health from the catalogue |
| Groq | SDK distinguishes HTTP status, rate limit and connection failures and already has configurable retries | Keep one controller retry/fallback policy; preserve cooldowns and expose safe HTTP codes rather than stack another SDK retry loop |
| Cloudflare | SDK also has retry/backoff and timeout behavior; account-scoped access is distinct from token presence | Keep account/token setup validation and avoid multiplying retries across layers; shared service/transport circuit bounds repeated failures |
| OpenRouter | The official SDK exposes both model selection and underlying provider routing | Preserve requested and returned model/provider identities; do not equate a model ID with a fixed backend, price or quota |
| Hugging Face | A Hub model, Inference Providers and dedicated Inference Endpoints are different deployment concepts | A discovered model does not prove served chat access; keep inference/quotas authoritative and do not treat every failure as a bad token |
| NVIDIA | Official examples distinguish hosted catalogue NIM endpoints and local/on-premises deployment | Keep NVIDIA API routing separate from Ollama; model-not-found is not proof the account key is invalid |
| Requesty | The attempted official-looking GitHub SDK README URL was unavailable | Retain the existing tested adapter; do not invent new provider-specific models or guarantees from an unavailable reference |
| Ollama | Native format/context/output controls, residency and measured load/evaluation metrics | Prefer an installed coding specialist in hybrid mode, retain explicit capacity checks and five-minute residency, expose real reported timing |

The NVIDIA/OpenRouter references are broad integration guides, not comprehensive endpoint specifications. Existing wire regression tests cover Foundry's adapters; the new research does not establish current per-account generation access. Provider upgrades are deliberately based on observable failures and explicit settings rather than an unverified “best model” list.

## Paired existing-work replay

[Results](research/hybrid-paired-0.21.0.json) compare the published v0.20.0 with this release using a valid implementation, a deliberately invalid exact edit, then the new explicit source-support response. Baseline stops with one saved task; candidate saves two tasks. Both preserve the original app source and report no behavioral verification. This tests the new response protocol; it does not claim the historical Quest Board model would automatically emit it or that persistence works.

Reproduce with `python docs/research/replay-hybrid-source.py`, optionally passing an extracted baseline release directory. The new prompt teaches the explicit protocol; ordinary uncited/no-change responses still reject.
