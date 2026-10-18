# Idea Foundry 0.6 — contract-aware planning and recovery

## Updating

From 0.5: click Update, Check for updates, then Install & restart. Keep the terminal and browser
open. The 0.5 supervisor protocol and data schema 2 are unchanged. Tests launch 0.6 through the
exact published 0.5 supervisor and confirm that project metadata and the local .env stay intact.

Manual alternative: stop Foundry, extract the new ZIP into a new folder, and start its launcher.
Existing Windows projects in Local AppData are reused. Do not copy a data folder over them.
Keep working standalone apps and workspace backups. No project/database migration ships here.

## Before approval: contracts and focused recovery

`contracts.py` separates the old structural checks from a deterministic consistency review.
`core.validate_plan` remains a structural compatibility alias. Approval uses the additional review.

The review catches objective contradictions in response kinds, exact required fields, bodyless
HTTP statuses, placeholder expectations and false restart claims. Reviewed starter API contracts
are defaults. A proposal can explicitly change a contract; that difference becomes a warning for
the user to inspect rather than a silent normalization. Warnings do not prove a plan is correct.

`api_contracts` entries contain method, path, status, response_kind (object, array, text, empty or
scalar), and required_fields. Missing contracts in legacy plans remain supported. Variable fields
can be omitted from json_contains; json_equals must express the exact expected value.
`empty_body: true` supports legitimate empty responses and cannot be combined with body assertions.

`planning.py` runs at most three requests, including at most one configured fallback request.
It supplies the exact findings and previous candidate for correction, preserves scope, and stops
repeated unchanged invalid proposals. Provider/configuration failures fail promptly when retrying
would not help. The last structurally valid invalid candidate can be edited or revised; it cannot
be approved until review passes. No application code runs during planning/review/approval.

The browser reviews edited proposals through an authenticated local endpoint without inference
or state/source writes. Old unapproved proposals are checked when opened. Already-approved
legacy checks remain frozen and are not silently upgraded or weakened. An old contradictory
approved plan can still fail its original runtime checks; a new proposal is needed to change scope.

## Model controls and explicit fallback

Under each model's Local settings & optional fallback, choose a context budget (4K/8K/16K/32K),
output limit and native Ollama JSON-schema mode. Default context remains 16K. Smaller contexts
use a smaller token budget but may not fit the project. Output must be smaller than context.
An older Ollama service that rejects schemas can use the JSON-mode compatibility toggle.
GPU placement and throughput remain Ollama's responsibility; no automatic GPU benchmark runs.

Fallback is off unless the user supplies a different provider/model. There is one fallback, no
recursive chain, no guessed model ID and no implicit paid escalation. Cloud consent is required
for a job if either role's primary or configured fallback is a cloud provider. Keys remain in local
environment settings. No keys are stored in model configuration or sent to generated apps.

Planner fallback can handle unsuccessful consistency corrections or provider errors within its
three-request ceiling. Builder fallback handles request/format failures, not a claim that it can
fix every semantic code bug. A builder request may try the primary and one fallback; these calls
are individually recorded. Existing static/runtime repair limits still bound repair decisions.
Cancellation is checked before fallback. Requests remain globally serialized.

Provider errors distinguish transport, rate limit, authentication, format, size and truncation.
When providers return actual prompt/output token counts, those are recorded and displayed as
reported counts; unavailable counts are not invented. Service success is not an app quality score.

## Real persistence evidence

Put `restart_before: true` on a GET that retrieves previously created data before it is deleted.
The acceptance harness closes the current server, starts an independent app process using its
CLI against the same disposable data directory, then performs the GET and its assertions.
Further restarts terminate the previous child before starting another. Process readiness and
cleanup are bounded. Memory-only globals cannot masquerade as disk persistence. The report
includes server_restarts/process_restarts, while the generated test and launch phases remain
independent. This new operation requires the 0.6 verifier; ordinary legacy checks retain their
meaning. Exported apps themselves remain standalone Python programs.

## Audit, validation and next pass

See PASS-1-AUDIT.md, VALIDATION.md and benchmarks/planning-0.6.json. The benchmark covers two
actual bad proposals and validator latency, not live model/GPU performance. Optional strict type
checks cover contracts.py, planning.py, routing.py, schemas.py and models.py. Mypy/Playwright are
development tools; the product still has no pip/Node installation requirement.

**Next proposed theme: context-aware code changes.** Add safe relevance-based source selection,
explicit edit contracts, stronger code-response validation and a repeatable opt-in benchmark on
the user's actual Ollama models. Measure app completion, repair counts, input/output tokens and
wall time before recommending model routing. Broader stacks and database migrations follow that
measured reliability work rather than being bundled into this pass.
