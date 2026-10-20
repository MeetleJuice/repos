# Validation notes — orchestrated delivery 0.24.0

## Completed checkout checks

- Full checkout suite: **362 tests passed in 120.317 seconds** after correcting the new run-budget guard's interaction with legacy/direct history. Existing history assertions were retained. One additional no-cloud/all-local configuration case was then added; all **13 orchestration tests passed**. The final distribution gate reruns the resulting full suite.
- Strict mypy: **24 source modules passed** with the route, context, workflow and export changes.
- **15 existing Chromium workflows passed**: cloud, provider_pool, automatic_routing, model_activity, workflow_overview, task_contract, hybrid_execution, delivery_control, model_studio, arcade, repair, proposal_import, starter_recovery, planning and upgrade.
- New **orchestration Chromium workflow passed**: explicit preset, primary/secondary cloud errors → local planning, no pre-consent inference, sequential local-only coding without unused cloud-planner consent, task outcome/criteria/check links, real intermediate milestone and final HTTP/unit/launch checks, invocation allowance and verified ZIP/work-checklist export. Mobile, secret exclusion and no JavaScript errors are checked.
- New controller tests cover missing-local setup preserving old profiles before cloud discovery, explicit saved provider order, local-only coding fallback, every-stage invocation allowance, saved-task/cursor preservation and resume after exhaustion, stage-scoped cloud consent with negative guards, safe relative Python/web dependency resolution, merged-cap no-write rejection, unknown legacy budget and no-cloud all-local routes.
- A checksum-verified v0.23.0 ZIP and the candidate were replayed with the same script and controlled replies. Paired JSON records exact route/context/local-generation differences. These are not live model or generated-product quality comparisons.
- Frozen manifest v14 appends orchestration-v1.json; previous fixture contents/hashes remain intact.

## Final distribution and publication gate

Extract the exact versioned ZIP and run the full unittest suite plus all **16** browser workflows above, including orchestration, before publishing. Validate ZIP checksum/version/portable paths through the actual updater and compare shipped runtime/tests/docs/assets to the checkout. After a non-force push, fetch the public updater manifest and archive and verify they are byte-identical to the tested distribution. A failure blocks publication pending correction and rerun.

`tools/validate.py --package --browser` includes orchestration in its normal browser subset; the full 16-workflow release run is broader. Packaging remains an explicit allowlist and excludes private dotenv/workspace contents.

## Evidence limits

Provider discovery and inference use fixtures or loopback servers. No live credentials, API billing, local GPU or model-quality benchmark is involved. The generated fixture application really executes under the approved local runtime during browser verification. Physical Windows 10 behavior and the user's installed models/quotas are not tested here. No guarantee of instant failover from a hanging socket, best-performing local selection or arbitrary-project completion is claimed. Per-run limits count model invocations, not a hard money/token/time allowance. Declared related checks do not individually prove each task criterion.
