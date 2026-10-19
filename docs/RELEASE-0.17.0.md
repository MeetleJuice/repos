# 0.17.0 — Build contracts and observed model activity

## Updating and resuming Josh's project

Update and restart. All existing project directories, saved tasks, approved plans/checks, snapshots, ZIP exports and evidence formats remain compatible. Open Josh's existing project; do not create it again. Optionally choose Models → Set up models automatically to rebuild its route using the new selection preferences and recently observed model outcomes. This action may select paid models and includes an installed local fallback. Generation still requires cloud consent; execution approval remains separate.

Click Generate / resume code. Five saved tasks stay saved; the unfinished task is resumed. The original approved task remains unchanged, but a new explicit ownership contract tells the builder that Foundry already supplies README, proposal/tasks/check documents and launch scripts. APP-GUIDE.md is available for app-specific import formats and usage examples. This resolves the known instruction conflict without permitting model edits to acceptance files. Existing docs/checks are not silently regenerated during resume.

A malformed or prohibited code response still gets at most one focused response correction. In a flat pool, the rejected model is skipped for that correction so another eligible model can recover the task. The entire rejected batch remains unwritten. Frozen tests and approval/runtime repair limits remain enforced. If the correction is also invalid or the route is exhausted, Foundry stops honestly; it does not weaken the checks. No universal project-completion claim is made.

## Top-right status panel

Seven cloud provider monograms plus an individual icon for each installed local model. Local icons are numbered and their labels/tooltips identify the model; embedding models are explicitly marked. Hover/focus shows state, applicable model and observation time. Click opens Models. The panel polls lightweight local metadata, not paid inference or remote provider catalogues. Installed local models come from the last connection/discovery check; opening Models refreshes that discovery.

Working is tied to the current inference invocation, including its wait for the provider response. Queued work does not animate. Success, exceptions and cancellation clear working. If local status polling fails, existing indicators become unknown instead of continuing to animate. Hidden tabs stop polling; repeated unchanged snapshots do not replace focused buttons. Reduced-motion users get a static working indicator.

Key present means configured. Catalogue available means only catalogue access. Responded means a parsed model response, not a verified app. Quota/model/auth/configuration, response rejection and budget failures retain distinct states. State is an observed outcome, not a continuous provider uptime monitor. Initial keys do not imply successful authentication.

Recent model-access, auth, quota, missing configuration and rejected/schema-invalid response outcomes avoid that model for up to five minutes in pooled calls and automatic setup. A correction/compatibility/truncation recovery already in progress is not suppressed. Transport failures can be retried on later tasks; rate-limit Retry-After cooldowns retain their original behavior. Importing/reloading credentials clears observations; restarting also clears this in-memory state. This is intentionally temporary, not a permanent model blacklist.

## Model selection recommendations

The authoritative model IDs are those returned by each provider to your account. No model family is guaranteed available or best for every task. Versioned model-selection-v1.json favors currently advertised Gemini 3-family/general instruction models for planning, and Qwen3-Coder/Devstral or capable general code models for building. GPT-OSS-120B is documented by Hugging Face as a supported chat example and is a candidate where advertised. Newer coding families rank ahead of the legacy Qwen2.5/deepseek-coder/Granite code families that were selected in the reported run; small 1–8B cloud coders are deprioritized. Local model choice still depends on installed models; these are heuristic preferences, not live quality measurements.

For Gemini use the available Flash-family candidate rather than hardcoding an inaccessible retired ID. For OpenRouter prefer a concrete capable coding model over the free random router where available; costs vary. For NVIDIA prefer an advertised capable general/code model over a legacy tiny coder. Requesty/Hugging Face account quota/payment errors cannot be repaired by prompt changes; Foundry skips failed model choices while alternatives remain. Groq/Cloudflare can participate when account configuration, model access and budgets permit. Cloudflare still requires an Account ID. No new provider SDKs or dependencies are added.

Output/context reservation and the no-smaller-output-ceiling rule after truncation are unchanged. More providers cannot fix a missing account balance or increase a model's actual capacity. No live generation keys were available in this cloud environment.

## Research and validation

See research/build-operation-v1.md and research/build-operation-results-v1.json. The paired synthetic replay runs against the actual v0.16.0 distribution and this candidate. v0.16 stops at task 6 after two prohibited responses from Gemini; v0.17 accepts the single correction from Groq and finishes file generation. Both retain identical protected checks; neither executes the app during that replay. This establishes the targeted recovery behavior, not live-model quality or savings.

Browser tests separately exercise actual generated-app verification/export using controlled provider responses. Native Windows and real provider access remain user-machine checks.

Release checks: 299 automated tests passed in the extracted distribution, five Chromium workflows passed, and strict type checks passed for 17 modules. The release archive is compared with the tested extraction; only final validation documents may differ. The published ZIP is downloaded through the updater path and checked against its checksum at publication.
