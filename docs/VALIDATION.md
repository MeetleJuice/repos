# Validation of this first version

Validated in the provided Linux cloud workspace, using Python 3.12, system Chromium,
Playwright, and Docker. No actual Windows computer, user Ollama server, or paid API
account was accessible. Windows scripts are included; Windows execution remains to
be checked on the user's computer. A Windows/Linux CI matrix is provided but has
not run on GitHub in this workspace.

- 16 standard-library automated tests passed.
- Full HTTP API workflow: proposal → approval → generated source → execution →
  checks → downloadable ZIP with source, documentation, launchers, and a build report.
- A deliberately broken generated task tracker failed its approved retrieval check;
  a scripted repair corrected application code while test files stayed frozen.
- Real generated-app unittest and HTTP checks executed in local subprocesses.
- Docker verification passed: generated unit test, health endpoint, HTML response,
  task creation, task retrieval, and the actual Python launch command.
- Zero-test runs, early zero exits without completion evidence, exhausted repairs,
  missing execution consent, unauthorized HTTP requests, and cross-origin requests
  were rejected rather than reported as success.
- Checkpoint restore, interrupted-job recovery, model-error retry, timeout, and
  cancellation were exercised.
- Browser workflow passed through proposal, approval, generation, failing checks,
  repair, verification, source inspection, and an actual ZIP download. No JavaScript
  errors. Desktop and narrow-screen layout checked.
- `run.py` launched and served the real workbench and authenticated project list.
- Model adapter protocol tests passed using a local simulated Ollama HTTP server
  and simulated cloud replies. They do not establish live inference quality.

Cloud setup and startup instructions were saved as a draft. Saving a draft is separate
from user publication, which has not been performed or verified.

## Follow-up: real user Task Tracker repair

The user uploaded their actual local generated files. They contained an invalid Python else
block, no GET task-list route, incompatible form/JSON submission, shared SQLite cursor state,
and no tests. The approved scope promised six features but its single implementation task
only described the health endpoint. These exposed gaps that scripted first-version responses
did not expose.

The repaired app is shipped in examples/task-tracker with the original approved requirements
and checks preserved. It has 11 behavioral tests covering create/list, completion/reopening,
deletion, persistence after a server restart, concurrent writes, input validation, and safe text.
The browser check also exercises actual add/complete/filter/restart/delete actions.

Generator regressions cover incomplete task/check mapping, one planner correction attempt,
syntax and missing-test detection, adding missing tests without execution, existing test
immutability, and the shared static/runtime repair budget. The combined automated suite has
31 tests. Model responses remain simulated here; the user's uploaded output supplies the
real-world failure example, not a live connection to their Windows Ollama.

Research conclusions are based on official documentation, not hands-on competitive
benchmarking. See RESEARCH.md for sources and scope.


## Version 0.3

46 automated tests pass, including linked change projects, parent/test preservation, model
switching, queued-job cancellation, migration and corrupt-data handling, source-swap failure
and crash recovery, workspace locking, backups, and generated-app port/readiness handling.
The release browser test passed the full guided build/change/diff/backup workflow with
no JavaScript errors and no narrow-screen overflow. Real Docker verification also passed
through the new runtime readiness gate and transactional build path.

The extracted distribution was started from a fresh folder with a separate --data-dir;
its authenticated API reported version 0.3.0 and the correct workspace location. Browser
opening and Local AppData behavior still need confirmation on the user's actual Windows
machine. See RELEASE-0.3.md for shipped behavior and remaining scope.

## Notes App from the user's Windows generation

The original upload was preserved and tested in a container. Its tests duplicated server
code and blocked in handle_request without a client request; verification timed out before
any test completed. Static syntax/structure success did not establish meaningful test behavior.

The repaired copy in examples/notes-app passed 12 actual app tests, including independent
server and process restarts, plus all eight unchanged approved acceptance checks and the
fixed health, interface, and launch checks. Its browser workflow passed create, title/body
display, matching/nonmatching search, restart persistence, deletion, safe text rendering,
and mobile layout with no JavaScript errors. The combined repository suite now has 58
passing tests. No live Windows/Ollama connection or local project-state change is claimed.

## Version 0.4 verification engine

68 tests passed from a freshly extracted distribution. The suite includes the exact original
Notes App failures as non-executable text fixtures, an end-to-end controlled repair into the
working Notes App, protected regression tests, JSON array/object shape checks, exact empty
lists, per-phase isolation, timeouts, missing assets, and proof that tests call the actual app.

The repaired Notes App passes the new independent acceptance/tests/launch phases in Docker:
12 app tests, eight original approval checks plus health/interface/launch, and two local assets.
The workbench browser regression passes with the new phase UI, model switching, linked changes,
diffs, backups and mobile layout. Model repair replies in automation are controlled fixtures;
no live Ollama generation quality or Windows CI execution is claimed for this release.

## Version 0.5

99 automated tests passed in the Linux Python 3.12 workspace. These include real subprocess
startup of a new Foundry version and fallback to the original version after a broken startup;
authenticated update installation and backup; checksum/path/schema rejection; pointer-write
failure recovery; project/.env preservation; explicit starter installation and protected tests;
the latest uploaded invalid email/urllib APIs; real milestone HTTP checks, bounded repairs and
saved task positions; unchanged-repair stopping; and detection of edited approval checks.

The browser checks passed the original build/repair/export workflow, linked improvements with
parent preservation, model changes, diffs, workspace backups, and the new starter/update/search
interface. Missing Docker was simulated to verify clear guidance and a disabled Docker execution
button. Explicit local selection enabled testing; generation itself did not execute code.
Desktop and 390px layouts had no horizontal overflow or JavaScript errors.

The Notes starter passed the actual Docker verifier with 13 tests (12 behavior tests plus the
protected foundation test), all approved checks, local assets and CLI launch. Its approved first
two-check milestone also passed in Docker. Development model replies are controlled fixtures;
no connection to the user's Windows Ollama or paid providers is claimed. The original reviewed
standalone examples remain unchanged. Windows/Linux Python 3.11/3.12 CI is configured; this
report does not claim those hosted jobs ran. The CI now also tests an extracted distribution.

All 99 tests also passed from the updater-validated ZIP extracted into a fresh folder. Archive
inspection confirmed the stable launcher, starter assets and regression fixtures are present,
with no runtime data, .env files or Python caches. Final packaging changes only release documentation.

## Version 0.6 — Pass 1

127 automated tests passed in 70.155 seconds from a fresh updater-validated extracted ZIP
on Linux Python 3.12.14. The original 99-test baseline also passed before expansion.
New coverage includes two actual contradictory user proposals, bounded correction/fallback,
explicit cloud consent, side-effect-free authenticated review, legacy state/backup preservation,
and startup through the exact published 0.5 supervisor. Independent-process persistence checks
pass for SQLite and reject both startup database erasure and memory-only storage.

Workbench browser checks passed build/repair/export, linked changes, model controls, backups,
update flows, edited-proposal approval blocking, automatic legacy proposal review, and mobile
layout without JavaScript errors. Controlled planning recovered through three model replies;
these are fixtures, not evidence of live model generation quality. The Notes starter passed
Docker acceptance with one process restart, 13 actual tests, and CLI launch. Strict mypy checks
passed contracts, planning, routing, schemas and models.

The repeatable two-case benchmark rejected both bad proposals accepted by the original
structural validator: median review 0.1458 ms, p95 0.2353 ms (per-proposal batch averages).
This measures validator latency, not Ollama/GPU speed or general app completion rates.
No live Windows, user Ollama, paid-provider or hosted CI run is claimed. Final packaging
changes only release documentation after the extracted-distribution test.

## Version 0.7 — Pass 2

149 automated tests passed in 72.974 seconds from a fresh updater-validated extracted
distribution on Linux Python 3.12.14. New cases reproduce the actual Neon Dodge read-before-create
proposal, support browser-only plans without fake APIs, preserve server behavior requirements,
validate bounded browser/manual contracts, protect approved evidence, and exercise the full
plan/approval/build/HTTP/tests/launch/manual-acceptance pipeline. Tests reject incomplete or
non-boolean manual results, stale source, tampered checklists and repeated invalid code replies.
Malformed JSON gets one focused correction; authentication errors do not enter that correction
loop. Exact published 0.5 launcher compatibility and old-state preservation still pass.

Real Chromium checks passed the Foundry planning/review/fallback controls and the entire arcade
pipeline through export. The rendered ship moved with arrow/D keys and pointer-held controls.
Pause froze both score and canvas, collision produced game over, restart reset play, and the best
score survived refresh. Workbench and game mobile layouts had no horizontal overflow or JavaScript
errors. These checks use the actual app, not app-internal test hooks. Controlled randomness makes
the collision case repeatable. A deliberately broken Start button passed Python/HTTP delivery
checks but failed the browser phase, demonstrating that browser assertions detect that regression.
The browser UI's manual-results submission is exercised in disposable test state; this does not
claim that the user has performed the checklist on their own computer.

The existing browser build/repair/export and starter/update/search/backup/consent workflows
also passed. The new arcade starter passed Docker acceptance, four actual Python app tests,
two local asset checks and CLI launch. Docker tests do not claim to exercise JavaScript.
Strict mypy passed six modules: contracts, planning, routing, schemas, models and evidence.
The optional Chromium CI job is configured, but hosted CI and Windows execution are not claimed.

benchmarks/evidence-0.7.json records two deterministic contract comparisons against the exact
published 0.6 structural validator: an honest browser/manual plan is newly accepted, while the
actual uploaded read-before-create plan is newly rejected. This is regression evidence, not a
model benchmark. Model replies in integration tests are controlled; no live Ollama, paid-provider,
GPU-throughput or exponential performance improvement was measured. The supplied icon was
faithfully adapted with the image tool and inspected in the actual interface.

Final packaging changes only documentation after the source-distribution test. Published 0.5
and 0.6 archives remain byte-identical. The new version retains workspace schema 2, release
manifest schema 1 and the stable supervisor/update protocol.

## Version 0.7.1 — local planner omission recovery

155 automated tests passed in 72.413 seconds from an updater-validated fresh distribution.
Six new tests cover explicit standard creation/recovery without inference or execution; a
planner that repeatedly omits browser fields; busy/approved/change-project/maintenance guards;
unchanged custom planning; and native schema app_kind with legacy validation compatibility.

A real browser reproduces the user's empty-plan error, loads the reviewed standard plan into
the same project, and approves it with zero additional model requests. Direct standard creation,
endpoint authentication and mobile layout also pass. The full arcade generation/verification/
manual/export browser test and broken-Start-button negative test still pass, as does the
starter/update/search/backup/consent browser regression. Six typed modules pass strict mypy.
Native schema and prompts are corrected, but live Windows/Ollama model compliance is not claimed.
The deterministic standard-plan path removes that dependency for this specific standard scope.
Final package changes only validation documentation after the extracted-source test.

## Version 0.7.2 — Windows cleanup regression

The updater-validated extracted distribution passed all 165 tests on Linux Python 3.12
(72.608 seconds) and Python 3.13 (70.915 seconds). Ten new regression tests enforce the
Windows current-directory deletion rule during every phase, restoration after app failure
and generated cwd/import-path changes, explicit cleanup errors, creation/staging failures,
structured child-process reports, local-runner environment classification and zero model
repair requests for infrastructure failure. Actual application assertions still fail as app
errors; cleanup failures are not ignored or relabeled as successful verification.

The exact uploaded Neon Dodge source passed acceptance/assets, all four Python tests and
CLI launch using the corrected harness on Python 3.13. The complete arcade browser pipeline
and its broken-handler negative case passed, as did update/search/backup/consent browser
regressions. Six typed modules passed strict mypy. CI now includes Windows/Linux Python 3.13
in addition to 3.11/3.12; no hosted CI or native Windows execution is claimed here. The Windows
rule is simulated explicitly, while the Python 3.13 execution above is native Linux.

Final release packaging changes only validation documentation after the extracted tests.
No user project files or approved checks are changed by this patch. Existing repair history
is preserved. A diagnostic retry with repairs set to zero can verify the current project
without spending further model requests.

## Version 0.7.3 — repeated shield repair plan

169 automated tests passed in 72.310 seconds from a fresh updater-validated distribution on
Linux Python 3.12. New tests cover bounded relevance-ranked source excerpts, explicit truncation,
repeated repair-task rejection, controlled correction with real source evidence in the payload,
and persisted reviewed edits without model calls, source writes or approval. Inherited features,
HTTP/manual acceptance and original source remain protected.

A real browser reproduces the older saved five-task proposal, imports the reviewed two-task
repair, checks that task cards update immediately and survive reload, explicitly saves another
edit, verifies check-button feedback, then approves with no inference or execution. The token
boundary, repeated-plan rejection and mobile layout pass. The existing arcade pipeline/broken
Start-button test, planning/fallback controls and update/search/backup/consent browser flows pass.
Six typed modules pass strict mypy. No live model-compliance or shield implementation success
is claimed; the downloadable artifact is a reviewed proposal, not generated application code.

Final release packaging changes only this validation documentation after the source test.

## Version 0.8.0 — evidence-driven repairs

From a fresh distribution validated and extracted by the real updater, all **183 automated tests**
passed on Linux Python 3.12 in 90.148 seconds and native Linux Python 3.13 in 88.179 seconds.
This includes existing backup/export/update/rollback compatibility, generation and repair-budget
checks, plus fourteen new regression tests for exact edits, protected/atomic rejection, failed
manual notes, direct repairs, no-execution generation, stale evidence, unchanged-source stopping,
runtime preparation failures, strict execution booleans, bounded feedback and clock prerequisites.

The extracted distribution's real Chromium regression starts with the actual uploaded shield bug.
Its four Python server tests and HTTP/assets/CLI delivery pass, while the approved deterministic
browser check fails with Game over after the shield blocks an obstacle. A controlled six-edit
response repairs the source; the identical frozen browser check then passes. Additional real
browser assertions prove collection, paused canvas stability, retained shield during pause,
consumption, survival of the blocked hit, a later unprotected collision and restart. The UI test
records and reloads notes, makes one direct coder request without replanning or executing the
files-only repair, keeps the approved plan, clears stale acceptance, rejects an unauthenticated
repair request and checks mobile layout without JavaScript errors.

Existing real-browser scripts also passed: arcade generation/verification/manual/export with
rendered movement and a broken-handler negative case; reviewed proposal import/save/reload;
planner correction/fallback/context/cloud controls; missing-Docker/consent/update/search/backup
flows; standard arcade recovery without inference. Seven typed modules pass strict mypy.
JavaScript syntax checks and git diff whitespace checks pass. Earlier six release archives retain
their published checksums. The new ZIP was checked to exclude workspace data and secret files.

These are Linux cloud results, not a native Windows or hosted CI run. Model replies in orchestration
tests are controlled fixtures; no live Ollama inference-speed or general generation-quality claim
is made. The exact-edit fixture reduces response bytes by 77.7%, which is not a token/speed result.
Final release packaging changes only this validation document after the extracted tests; code,
tests, UI and all other entries are compared by hash against the tested archive before publishing.

## Version 0.8.1 — rejected-edit recovery and retained failure observations

The live Windows/Ollama log supplied by the user shows a nonunique/missing exact-edit search,
followed by an unusable correction response. No files were applied. The later four-test HTTP/server
success was on unchanged code and did not establish that the shield worked. This real outcome is
distinct from the successful controlled-response fixtures used to verify orchestration.

New regressions cover a rejected edit followed by complete-file recovery, the exact rejected-edit
then empty-response sequence with zero file writes, retained observations/checks on unchanged
source, and the native Ollama recovery request's dedicated required/nonempty-files schema. The
existing unchanged-source stop now also checks observation retention. Re-running real server
verification on that unchanged failed build preserves its manual failure and needs-attention status.

The real Chromium workflow reproduces the uploaded shield bug, checks the reference repair, then
exercises rejected response recovery through the UI. Failure notes remain visible and retry stays
enabled. A subsequent real server/Chromium verification remains needs attention with the same
failed manual result and no additional model request. A subsequent changed files-only repair clears
stale acceptance. Frozen checks/tests, cloud/execution approval, token boundary and mobile layout
remain covered. The browser update/consent/search/export workflow also passes.

All **186 automated tests** passed from a fresh updater-validated distribution on Linux Python
3.12 in 97.578 seconds and native Linux Python 3.13 in 94.744 seconds. The extracted artifact's
expanded Chromium repair regression passed, including unchanged-code re-verification with retained
failure notes. Seven typed modules pass strict mypy. No native Windows, hosted CI, or live-model
compliance result is claimed. Final packaging changes only this validation document; all other
ZIP entry hashes are compared with the tested artifact before publication.

## Version 0.9.0 — cloud-first studio

From a fresh ZIP validated/extracted by the real updater, all **201 automated tests** passed on
Linux Python 3.12 in 99.395 seconds and native Linux Python 3.13 in 94.847 seconds. Fifteen new cloud
regressions cover allowlisted/BOM/quoted/aliased dotenv parsing, process/workspace/launcher
precedence, reload/removal, private atomic import with existing entries preserved, UTF-16 files,
malformed-file startup recovery, checked catalogue profiles/caps/persistence, OpenRouter's
separate authenticated key check, distinct flat chains, cloud consent, service failover/cooldowns,
non-failover JSON correction, stop between tiers, exhausted-pool stopping, real loopback HTTP
headers/max_tokens/usage, and reported tokens retained on invalid/truncated output without stale
usage reuse. Fixture keys are used; no live account key or external generation request is needed.

The extracted artifact's real Chromium test imports a UTF-16 Notepad .env.txt, checks controlled
provider catalogues/key metadata, saves a three-tier profile, persists it across browser reload,
and proves no inference occurs before cloud consent. Planning fails over Gemini → Groq →
OpenRouter. Generation skips the cooling-down Gemini identity, fails over Groq → OpenRouter,
and runs real generated-app HTTP acceptance, unittest and launch phases. It checks the actual
provider ledger, planner fallback accounting, last-response label, saved route in model settings,
application of a changed Groq token cap to an existing approved project with no source mutation
or extra inference, missing-token rejection, secret-free metadata/HTML, and mobile layout.

Existing real-browser planning/correction/fallback/context/consent, update/search/export/runtime,
proposal import/reload, arcade gameplay/verification, and rejected shield-repair/evidence-retention
regressions passed during the upgrade. Nine typed modules pass strict mypy. JavaScript syntax
and git whitespace checks pass. ZIP allowlisting excludes local .env and workspace data.
Final packaging changes only this validation document; code/UI/tests are hash-compared with the
tested ZIP before publication. Previous published 0.8.0 and 0.8.1 archives remain immutable.

No native Windows or hosted CI execution is claimed. Hosted provider endpoints/documentation were
proxy-blocked in this cloud environment and the user's real keys remain on their PC. Official SDK
repository references were inspected. Account access, model support, generation quota, cost and
live model quality must be checked locally; controlled fixtures establish routing mechanics and
application execution, not a live-model success-rate or throughput benchmark.


## 0.10.0 — Resilient model routes

- Full standard-library suite: 203 tests passed on Linux Python 3.12 (98.841 seconds).
- Strict mypy: nine typed modules passed.
- Real Chromium cloud workflow passed, including private Notepad key import, checked catalogues, consent rejection, real generated-app HTTP/tests, route persistence, project-to-shared-model setup navigation, optional installed local fallback, 16384-token budget, unchanged approved plan/source, mobile layout and no JavaScript errors. Provider responses use controlled fixtures; no real API keys or paid inference were used.
- Real Chromium update/runtime workflow passed: missing Docker messaging, explicit execution consent, actual verification, project search, protected export and update dialog.
- New unit coverage proves truncated cloud output can reach an explicitly configured local model, each route step is attempted once, actual provider attempts are recorded, local choice survives preference reload, larger budgets validate, and disabling local fallback removes it. Existing format-correction, consent, cooldown, backup and legacy route checks remain enabled.
- Native Windows and live provider model quality/quota remain untested here. Local inference hardware performance is not benchmarked. Longer socket timeout is not a wall-clock cancellation deadline.
