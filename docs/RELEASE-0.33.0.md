# Idea Foundry 0.33.0 — Scope first, then Test → Diag

New guided/proof drafts separate feature scope from acceptance evidence. Validated scope is saved before acceptance is requested, and only a complete reviewed proposal reaches human approval. Existing approved plans, tests, routes, source and consent controls stay intact. A request/policy change starts a new unapproved planning draft.

Observed outline failures now have specific rule codes and paths; multiple evidence errors survive together. Model metadata records configured context and requested JSON mode. These are request settings, not proof that a provider enforced the schema or that a model fits in VRAM.

## The new Test button

1. **Quick checks**: private SQLite write/reopen/read/cleanup, two fixed controller validations, Ollama connectivity and provider catalogues. No model inference or generated-app execution.
2. **Quick checks + local responses**: the above plus a fixed tiny JSON probe for up to two saved local models.
3. **Quick checks + local/cloud responses**: the above plus one saved model per cloud provider, at most nine probes total. Separate cloud consent is required. Charges can apply; no project prompt/source is sent.

Choose an existing project to use its saved routes. Without a project, saved studio defaults are used. Probes use 4,096 configured context and at most 1,024 output tokens; local socket timeout 120 seconds, cloud 30 seconds. They do not change routing settings or influence response cooldowns. Stop takes effect between checks; an in-flight request must finish or time out. Catalogue timing is recorded for the whole sweep, not invented per provider.

Probes exercise the ordinary chat adapter. Planner requests can use a different API family (notably native Gemini generateContent); the actual family and response mode are recorded. A passing chat probe does not prove that native planner endpoint or a full proposal works.

Results are saved outside projects and included in Diag's ZIP. Prior result events remain subject to recorder retention; the separate test-report file contains the latest run. Interrupted tests are identified as interrupted. Diag distinguishes latest Test results from historical workspace findings.

## More operational evidence

The resource sampler additionally observes loaded Ollama models through read-only `/api/ps`, approximately every 30 seconds. Diag also includes the Ollama version. Context length and VRAM bytes are included when supplied as valid numeric metadata. No model is loaded for observation, and absent values stay unknown. Credentials, original prompts, source, raw provider/model prose and environment values remain excluded.

Update with the existing **Update** button and confirm **0.33.0** after restart. Start with **Test → Quick checks**, then optionally test model responses. Once finished, close Test, click **Diag**, and download its ZIP. Run a fresh small **Plan with proof** project separately to test the full builder workflow.

This release does not replenish API credits, guarantee external availability, or establish live-model quality from fixtures. See the versioned validation artifact for source/extracted/browser checks and the engineering brief for provenance and scope.

Source validation before packaging:

```text
python -m unittest discover -q
Ran 519 tests in 136.486s
OK
```

Strict mypy checks passed on 36 modules. All 23 workbench browser scripts passed, including the actual Test → persisted report → Diag ZIP workflow and scope/acceptance → task compilation → real generated-fixture app verification. Dashboard TypeScript checks, four Node tests, asset build, Chromium graph interaction and separate-window launcher checks passed. No live inference or Windows GPU benchmark was performed in this checkout.
