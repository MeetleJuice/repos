# 0.12.0 — Planner output reservation and truncation recovery

The reported revision failed because both tiers returned truncated proposal JSON. Foundry treated that as service exhaustion and switched from a 65,536-output-token Gemini profile to an estimated 8,192-token free router. The existing cloud planner profile also limited normal requests to 4,096 output tokens. This patch distinguishes output exhaustion from service availability.

## Budget and capabilities

`forge/model-capabilities-v1.json` is the versioned capability registry. Each profile has max output/context tokens, thinking-budget support/default, estimation status and provenance. Gemini 3.8 Flash registers the requested 65,536 output ceiling; its profile is explicitly not live-verified. Unknown models/free-router downstream selection use an estimated 8,192-output ceiling. Provider discovery persists OpenRouter published `top_provider.max_completion_tokens` (or `max_completion_tokens`) and `context_length` locally in `model-capabilities-v1.json`; missing fields remain estimated. No new provider is added.

Each actual planner request reserves output from required schema fields, task/feature/check counts, and the configured planning floor. The automatic minimum is 8,192 text-output tokens; Gemini's supported profile adds a bounded 1,024-thinking-token reservation. The request never exceeds the known/estimated output ceiling or estimated remaining context. A reservation that cannot fit is refused before inference and can try another configured model, rather than silently lowering the requested output room. Input/output estimates are conservative heuristics, not tokenizer guarantees. These larger reservations and bounded extra calls can increase API use; the journal records actual settings.

Gemini planning uses its native `generateContent` endpoint so `generationConfig.maxOutputTokens` and `generationConfig.thinkingConfig.thinkingBudget` are explicit. Other cloud calls continue using OpenAI-compatible `max_tokens`; Ollama uses `num_predict`. Gemini thinking-budget support/ranges remain model-dependent; this implementation does not claim live verification of the user-specified 3.8 model. Existing builder adapters and provider keys are retained.

## Recovery and evidence

`finish_reason`/`finishReason` values `length`/`MAX_TOKENS` (and Ollama `done_reason`) produce `truncated_output`. Incomplete response text is held only in memory, never committed as a proposal or copied into the attempt ledger.

For planning: one same-model continuation joins the exact retained prefix and returned suffix; if it remains truncated or invalid, one same-model shortening asks for a fresh, compact **schema-complete** proposal. If the provider supplies no partial text, or the text exceeds the 200,000-character in-memory continuation bound, the controller goes straight to shortening. No prefix is silently clipped. No unbounded continuation loop is allowed. After those attempts, only configured models with equal-or-larger output ceilings are eligible. The ceiling guard persists across the outer proposal-correction loop and legacy fallback route for that planning job, and resets for a new explicit planning job. Stop/consent checks apply before every attempt. A later provider outage after truncation does not remove the ceiling guard.

Each attempt records finish reason, requested output tokens, observed output tokens when supplied, text/thinking reservation, recovery path, capability estimate status and error class. Native Gemini visible and thinking usage are recorded separately and totalled only from reported counters. Schema/consistency rejection is labeled `schema_error`, malformed JSON `parse_error`, and service errors `provider_unavailable` while retaining their detailed legacy categories. Actual request text is not persisted by these new metadata fields.

The current approval schema requires task instructions, feature coverage and concrete checks, so an IDs-only skeleton would weaken the approval artifact. No skeleton/detail-call split was introduced. Shortening retains the existing full approval contract, and deterministic consistency review still runs before a proposal is marked ready. Frozen acceptance checks and approved projects are unchanged.

## Frozen before/after reproduction

`planner-truncation-v1.json` reproduces truncated model content inside valid HTTP-200 JSON envelopes. The append-only `frozen-regressions-v2.json` manifest adds it without rewriting the eighteen-case v1 comparator. `docs/research/planner-truncation-results.json` contains paired fixture results.

- Before: Gemini length → OpenRouter length → generic `exhausted`, no valid proposal.
- After, continuation fixture: Gemini `MAX_TOKENS` → Gemini continuation `STOP` → schema-valid proposal; no OpenRouter call. The fixture reserves 8,192 text +1,024 thinking =9,216 total output tokens.
- After, shortening fixture: initial → continuation → shortening → schema-valid proposal; no smaller fallback.
- After, exhaustion fixture: three bounded attempts, smaller free router refused, terminal `truncated_output` rather than a provider-outage claim.

These are controlled reliability regressions, not repair-quality improvement or live model/quota evidence. The previously proposed six-case live repair trial remains pending credentials in this cloud checkout; local Desktop keys are not accessible here. No trial outcome is invented or substituted with scripted success. This urgent planning fix precedes that separate trial as requested.

The change is isolated in one release commit for single-revert rollback; saved state remains schema 2. Use Update, reopen the existing unapproved Reading List project, confirm cloud consent and retry the revision. Existing valid proposal/source files are preserved on failure.
