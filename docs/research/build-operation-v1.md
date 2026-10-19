# Build-operation audit and reviewed change — 0.17.0

Baseline df4430c / v0.16.0. The supplied Josh log reports five saved tasks, model-access failures (Gemini/NVIDIA), quota failures (Requesty/Hugging Face), a builder reservation refusal, and two otherwise successful OpenRouter responses rejected for touching protected artifacts. This is not evidence that all providers are down. Raw response bodies and generated app files were not provided.

## Largest process problems and changes

1. Scope → plan → task ownership was inconsistent: the planner could ask for README/manual-check creation while CODE and apply() forbid editing those files. Add a versioned file-ownership payload, planner guidance and the existing controller's docs as the authority; preserve approved tasks verbatim. Separate app-specific APP-GUIDE.md from frozen artifacts.
2. Generation → validation recovery restarted at the same model after a prohibited response. Retain the two-invocation malformed-code bound; record rejection separately from API response success and move the single correction to another eligible pooled model. Never write a partial rejected batch.
3. Selection used family heuristics that could favor old small code models or repeatedly retry recently unavailable IDs. Put preference lists in a versioned file and apply temporary observed-outcome exclusions. Preserve hard output/context floors, JSON parsing and truncation guards.
4. Visibility mixed configured/available/responded/verified. Add a small independent thread-safe observer and authenticated local snapshot endpoint. Status polling performs no provider inference. Indicate active calls, separate transient transport and hard/configuration outcomes, clear activity in finally, and label catalogue presence/installation as limited evidence.
5. Approval/export/verification must remain distinct. The recovery replay finishes generated files only. Existing runtime/manual/fingerprint gates remain authoritative. New optional image guidance permits explicitly approved opt-in browser images with offline fallback; no credentials or unapproved server integrations are permitted.

## Sources and evidence boundary

Sources retrieved 2026-10-19 from maintained official repositories; URLs, byte sizes and SHA-256 snapshots are recorded in build-operation-results-v1.json. Google python-genai documents native JSON output/schema and thinking controls. Hugging Face inference-providers documentation documents routed models, chat discovery, and GPT-OSS-120B usage. NVIDIA's maintained LangChain endpoint client documents its compatible endpoint/model discovery contract. None is evidence that the user's account has inference quota or that a model is best at our actual tasks. Direct provider generation was not tested; no key values were available here.

Model ranking is a conservative, editable heuristic using only advertised IDs. The user's observed failures supply stronger immediate evidence of account/model unusability than a catalogue list. Temporary exclusions expire and reset on credential reload; network errors remain retryable on later tasks. We do not add paid diagnostic probes or send prompts before cloud consent.

## Frozen regression and serialization

build-ownership-v1.json was frozen before implementation with synthetic provenance. Its paired comparison uses the actual extracted v0.16.0 baseline and the candidate. Existing frozen datasets remain unchanged; v7 appends the new fixture hash. Original JSON-decoded task/source values are retained exactly. The new file_ownership metadata intentionally adds request content, uses schema=1, and keeps legacy json.dumps serialization and handoff-version=1; the production serialization regression now asserts the complete enriched payload plus exact preservation of every original key/value. No lossless compact-serializer prototype is promoted and no input-token or cost reduction is claimed. CODE/PLAN guidance changes are deliberate contract fixes, not benchmark optimization results.

## Remaining boundaries

No live API quality/cost benchmark, native Windows run, universal completion guarantee or autonomous source promotion. Keep the prior working folders. A subsequent pass can evaluate capacity-aware price/quality ranking against live consenting jobs and compare bounded recovery outcomes with complete provenance; no such benefit is assumed here.
