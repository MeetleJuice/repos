# Builder-sized delivery research and audit — v0.28.0

Research date: October 20, 2026 (user timezone). Baseline: core 0.27.0 / `8cfdd21`. The immutable baseline inventory was reconstructed from Git blobs after the audit began; this is not a preregistered live-model experiment. Existing frozen handoff/truncation/task fixtures and their acceptance contracts are unchanged.

## What the supplied run actually establishes

The uploaded journal contains 33 requesting lines: 21 calls in the failed full-proposal run, six in successful staged planning, and six builder calls. Failed source bodies, exact proposal/task JSON, provider receipts and the Windows runtime configuration are not attached. The diagnostic fixture therefore labels reconstructed bad code as a mock, not a captured model reply.

- Full planning encountered missing assertions, broad task scopes, missing browser acceptance, invalid randomness options and body assertions on HTTP 204. These are semantic/schema failures, not evidence that an otherwise working provider is unavailable.
- Guided planning completed an outline plus feature batches and passed the unchanged full-proposal reviewer. Staging already has a production success in this journal; another unbounded planning framework is not warranted.
- The builder returned invalid Python twice, off-scope files twice, and timed out twice. A valid JSON response did not establish valid source. The approved first task allowed only `app.py` and `tests/test_movies.py`, so writing foundation tests or UI files was correctly rejected.
- That nested test path also needs `tests/__init__.py` for this harness's unittest discovery. The missing package prerequisite is a real planning hazard inferred from the declared scope and existing harness, even though this run stopped before verification.
- OpenRouter, Requesty and Hugging Face returned HTTP 402 on different model IDs. Retrying a second model on the same out-of-credit account cannot restore its balance. Model-specific HTTP 403 or rate limits do not necessarily have account-wide scope and are not given that assumption.
- The final blank `All configured models failed:` came from a later pass skipping already rejected models without adding their reasons to the local failure list. Fix the explanation without clearing the guard or repeating the rejected requests.

## Primary research and access limits

`sources.json` records each requested URL, retrieval outcome, byte count and SHA-256. Retrieved primary sources include Ollama's API documentation and API types, Google GenAI model types, Groq's model type, mini-SWE-agent's controller and Qwen/DeepSeek project READMEs. Provider documentation websites and Hugging Face model configs were inaccessible here. The provider account keys and installed Windows models remain on the user's PC; no attempt was made to obtain keys through chat.

Important source distinctions:

1. Ollama's documented `POST /api/show` returns `model_info.<architecture>.context_length`. This is an appropriate source for the installed context ceiling. Its template/modelfile can contain local paths, so only numeric context metadata is retained. `/api/show` does not generate a reply or calibrate model quality. Foundry caches reads for 30 minutes, at most 12 names per refresh with four metadata workers and two-second socket settings; this is not a hard total deadline.
2. Google model types expose input and output token limits separately. Groq's retrieved public model object only defines identity/creation/ownership; it is not evidence of a particular model's output ceiling. A catalogue field missing its output maximum must stay unknown rather than inherit a made-up authoritative value.
3. Current Qwen2.5 repository URLs now contain Qwen3/Qwen3-Coder material. Current-family context claims cannot be assigned to the user's older 7B tags. DeepSeek's documented 32,768 generation setting is an evaluation setting, not proof of the deployed Ollama output maximum. An example's `max_new_tokens` is not a model's minimum or guaranteed maximum response.
4. The retrieved LiteLLM model catalogue is useful secondary corroboration and is hashed. Its 65,536 estimates for Gemini Flash variants and Groq GPT-OSS, for example, are **not provider-verified deployment limits**. No routing ceiling is promoted from those estimates. `model-matrix.json` separates secondary references from published/discovered values.
5. mini-SWE-agent's controller has explicit step/cost/time checks, feedback and retained trajectories. The transferable pattern is a small bounded observe/act/validate loop. It does not establish that a local 7B model has frontier-model capability, nor justify extra reviewers or a new agent framework.

## Model inventory and budgets

The matrix covers all nine Ollama IDs supplied by the user and fourteen provider/model pairs in this journal. It includes embedding and vision models with their distinct roles. An embedding vector dimension is not an output-token budget. Automatic local text routes continue excluding embeddings/known vision-only choices.

The app learns current numeric limits from authenticated provider catalogues and installed local metadata. Context-only catalogues are now retained. The Models panel labels published limits, installed context, configured/default budgets, role-specific profiles and estimates. The panel does not claim catalogue access proves generation quota.

There is **no universal useful minimum output** established for these models. A maximum-token parameter is a cap; generation can stop earlier. Foundry's 8,192 planner text floor and 1,024–16,384 builder choices are application configuration, not provider minima. The planner floor is preserved. Stage-aware estimates use the outline/batch schema rather than reserving for an entire plan at every stage. Local native-schema overhead is included in the conservative builder input estimate. Character/byte heuristics remain estimates, not billed tokens.

Fresh explicit automatic local builder setup now uses 16K context / 4K output; planners retain 32K / at least 8K. This is a conservative configuration choice, not a Windows/GPU benchmark. Saved project/model choices are not silently rewritten. Users may retain larger settings where tested appropriate. Known installed context ceilings constrain requests; raising a configured context cannot override a smaller discovered model context.

## Implemented process changes

**Planning.** A prominent `Plan for my builder` action uses the existing guided path and the ordinary consent/form validation. It adds the actual builder route's capacity profile and starter source facts. Local guided tasks are limited to two writable files and one feature per task. Before approval, validation checks protected starter tests, nested test-package prerequisites and dependencies on earlier file/interface producers. Model corrections must split or declare prerequisites without dropping requested behavior. The fully assembled proposal remains the only approval artifact. Approved tasks are never automatically split, widened or reordered.

**Builder handoff.** Structured tasks receive an explicit editable/new/read-only file list and delivery sequence, preserving original task/plan data. Ollama's per-request JSON schema constrains `files` keys and edit/evidence paths to the already approved scope. The deterministic transactional validator remains authoritative for all providers. Generic legacy handoffs keep their original JSON representation and behavior.

**Recovery.** Invalid Python or off-scope structured source can receive one focused correction on the same model. Exact edits remain available and the focused context is retained; rejected source is never installed. If correction fails, eligible fallback remains available. Generic failed-search/legacy complete-file recovery is preserved. Invocation, truncation, source, repair and consent limits still apply, including to corrections. Twelve outer response attempts is not a promise of twelve transport attempts: nested bounded recovery shares the global run allowance.

**Routing.** Explicit HTTP 401 authentication or 402 quota failures suppress other model IDs on the same cloud provider for that run. HTTP 403, model errors, rate limits, truncation and local failures retain their more specific policies. A new explicit run resets the account rejection state. Skip reasons are included in exhaustion messages. Hanging requests still need to time out before fallback can proceed.

**Evidence/UX.** The dashboard distinguishes a recorded source rejection from a transport returning valid JSON. Its source references and new profile/schema/metadata paths are regenerated. Model-limit and planning panels explain budgets and remaining uncertainty without exposing keys, modelfiles or prompts. Existing execution and cloud consent, frozen acceptance/tests, checkpoints, source fingerprints and export evidence remain enforced.

## Validation and limits

`watchlist-delivery-v1.json` is a frozen diagnostic-derived controller fixture. Its SHA is recorded in `regression-fixture.json`. The initial regressions reproduced a redundant second account-quota call and a rejected exact-edit correction. Updated tests cover the new paths, scope, staged budgets, model metadata privacy/cache, missing producer/test-package prerequisites, native JSON scope and preserved original contracts.

The new Chromium test exercises the recommended planning action, approval, an intentionally rejected Python response, same-model exact-edit correction, sequential tasks, **actual** generated-app acceptance/tests/launch and verified ZIP export with the foundation test retained. It also checks metadata-only calls, embedding labels and mobile layout. Replies are controlled fixtures. Existing suites remain the compatibility gate. The release's recorded command results are in `validation.json`.

This proves specific controller reliability, not that arbitrary ideas will now complete, that a particular local model is best, or that live repair success/token cost/Windows latency improved. Those remain unmeasured. No paid provider generation or local GPU execution occurred in this cloud checkout.

## Next update gate

After installing, run one fresh small Windows project with the recommended action. Retain the proposal, task packet, selected model, input/output reservation, actual usage/timing, source rejection and verification outcome. The next patch should address the first reproducible failure from that run, or a controlled comparison of 4K versus 8K builder budgets with the same tasks and independent tests. There is no justified calendar or success-rate promise before that evidence exists. Update-button publication remains the delivery path.
