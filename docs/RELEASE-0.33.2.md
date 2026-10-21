# Idea Foundry 0.33.2 — acceptance before tasks

The uploaded report `dde982a42b9b484a9af61a33bd20132e` recorded a guided run that saved scope, acceptance and ten tasks, then failed final review with `restart_evidence` at `/checks/3` and `false_restart` at `/checks/4/name`. All ten model requests in that run were local. The first model timed out after 300 seconds; the run lasted 520.961 seconds. These are historical observations, not release performance measurements.

The acceptance gate previously checked structure and opt-in evidence rules, but omitted task-independent checks from the final consistency reviewer. A restart before POST could therefore pass the intermediate gate and fail after all feature-task calls.

## Changes

- Reuse the complete consistency reviewer in outline mode before compiling tasks. Only task-dependent checks wait for tasks. Starter API response contracts are included; restart placement, false restart claims, contradictory assertions and placeholders use their existing final-review rules.
- Existing per-model correction and fallback handle an invalid acceptance response. No new unbounded loop, provider, dependency, execution permission or weaker approval rule is added. Persistent failures stop before feature requests.
- A matching saved split-stage checkpoint with invalid acceptance keeps validated scope and clears dependent task declarations before requesting corrected acceptance. Valid checkpoints keep their checks. A changed full request starts a fresh draft; old checkpoints without a valid saved scope stop explicitly. Approved projects and frozen checks are not migrated.
- The workbench explains the acceptance gate and reports when a saved scope is retained while acceptance and dependent tasks are rebuilt. Diag exposes specific restart-rule descriptions.

## Reproduction and evidence

`tests/fixture_data/acceptance-boundary-v1.json` reproduces the observed five-check shape and two final-review paths. Candidate text and expected values are synthetic: original model output is excluded from the diagnostic export. `frozen-regressions-v17.json` appends this fixture without changing prior frozen bytes.

Before: three new tests failed. An invalid acceptance object was accepted by the stage gate; the real controller fixture reached final-review error; a matching invalid saved checkpoint returned without regeneration.

After: seven focused tests cover early rejection, correction before tasks, finite stop after repeated rejection, matching invalid/valid resume, frozen failure paths and starter response contracts. Successful correction uses `schema_correction` on the same model; persistent invalid replies use the existing configured fallback/stop policy. These are scripted-provider regressions, not proof of improved live model quality.

## Update and try

1. Use Update, install, and confirm version 0.33.2 after restart.
2. Open the unapproved Tiny Wins project. Keep its idea and revision. Do not approve the old failed candidate.
3. Click Resume small-step planning (or Plan in smaller steps). Matching checkpoints reuse validated scope. If the full request identity has changed, scope starts again; this safeguard is intentional.
4. Wait for a proposed plan or a clear error, then export Diag before approval. Expect acceptance rejection/correction to precede feature-task requests. Review actual saved-data restart and manual UI checks yourself.

Saved routes and timeout choices remain unchanged. This patch does not solve the repeatedly slow primary model by silently changing your selection. Qwen2.5:7b succeeded in the recorded run; that is evidence for this task only, not a universal model ranking. Catalogue access, tiny Test probes, generated files and verified app behavior remain separate.

Remaining work: protocol-aware Test probes and explicit cloud-target previews; local response-budget calibration; whole-run planning latency with live Windows/provider evidence. No live providers or Windows GPU benchmarks were run for this release.

## Source validation

Initial regression, before engine edits:

```text
python -m unittest tests.test_acceptance_boundary -q
Ran 3 tests in 0.098s
FAILED (failures=3)
```

Expanded focused suite, after the patch:

```text
python -m unittest tests.test_acceptance_boundary -q
Ran 7 tests in 0.141s
OK

python -m unittest discover -q
Ran 527 tests in 136.613s
OK
```

Strict mypy passed all 36 modules listed by `tools.validate.TYPED`, using the preinstalled `/tmp/foundry-typecheck` tool environment. Importing the starter catalogue into the typed stage modules required adding the existing `starter_files` function's argument/return annotations; its behavior did not change. Dashboard TypeScript, four Node tests and the production asset build passed.

Browser checks passed for `evidence_planning`, `guided_planning`, `capacity_delivery`, `system_tests`, `diagnostics`, Dashboard rendering and its separate-window launcher. The evidence-planning browser test now injects a false restart claim and asserts correction precedes every feature-task request, then runs actual generated-app SQLite and browser checks. Model replies remain fixtures.

One earlier full source run failed the Dashboard source-location assertion because the graph still referenced pre-edit line numbers when that test ran. After regenerating source locations and assets, the focused graph test and the full 527-test rerun above passed. No test was removed or weakened. Distribution results and immutable artifact identity are recorded separately in `releases/validation-0.33.2.json` after archive validation.
