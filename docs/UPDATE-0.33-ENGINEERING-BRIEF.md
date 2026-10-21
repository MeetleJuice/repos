# Revision mandate: reliable outlines and Test → Diag

Goal: fix the measured pre-task failure in the v0.32 diagnostic run, and make model availability independently testable without confusing catalogue access, inference, proposal validity and app correctness.

Evidence: uploaded diagnostic report ec1d6a0819c64e1c898d2cd9e85a4b1c; all 15 manifest members matched. One new planning job made 18 actual requests in 549.037 seconds. Twelve requests failed through service/quota/rate-limit/timeout conditions; six completed responses failed outline validation. No outline, task or generated app was accepted. Local Qwen timed out at 300 seconds; DeepSeek responded around 30 tokens/second but omitted assertions. Original candidate prose is absent; fixed validator-message digest matches and structural metadata establish the specific rule failures, not complete candidate reconstructions.

Implementation scope: new versioned scope/acceptance staging for new guided/proof drafts; deterministic validation codes/paths; bounded asynchronous system tests; independent persisted operational evidence; Test UI and Diag integration; regression fixtures, Dashboard source graph, documentation and versioned updater delivery. Preserve approved projects, frozen acceptance/test contracts, original request identity, cloud/execution consent and rollback.

Approach:

1. Split the initial outline into scope and acceptance calls. Scope defines required features; acceptance defines actual examples and coverage against that stable scope. Do not ask the model to emit the entire proposal on every correction. Assemble and validate the complete outline before task compilation and approval.
2. Checkpoint validated scope separately and bind it to the complete request identity. A partial scope never permits approval or code generation. Preserve the existing direct/legacy guided protocol.
3. Give every observed rejection a finite rule code and safe JSON field path. Preserve meaningful assertions, concrete mutation data, persistence checks and complete feature coverage; never fill gaps by pretending tests passed.
4. Add an explicit Test action: controller/storage checks and provider catalogues by default; separately consented fixed-prompt inference probes for configured models. Bound requests, serialize with model work, support stopping between calls and retain results outside generated projects. Never execute generated source or arbitrary shell commands as a diagnostic action.
5. Persist safe test results, route/circuit observations and structural failure evidence. Diag exports the retained test report, counts, timestamps, limits and unknowns. No source, secrets, project prompts, raw provider bodies or model prose.
6. Verify with frozen synthetic regressions derived from observed failures, real HTTP/UI checks, full Python/type/Node/browser checks, extracted archive tests and the public Update download.

Stop when the tested release is available through Update. No new provider/framework/dependency; no claims that all models work, all tests are possible, or fixtures measure real model quality. Next evidence must come from the user's Test → Diag report and fresh proof-project run.
