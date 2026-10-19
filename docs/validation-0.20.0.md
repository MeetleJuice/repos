# v0.20.0 validation

Date: 2026-10-19. Linux/Python 3.11; Chromium with Playwright 1.56.0. No real provider keys, cloud inference, GPU benchmarks or physical Windows run.

- Initial checkout suite: 323 tests passed in 111.978 seconds. Focused task checks were extended during development; the final nine-test task-contract module passed, and the final task/workflow/handoff focused run passed 22 tests.
- **Extracted distribution: all 325 tests passed in 112.347 seconds.** The validation runner completed successfully. No skipped or expected-failure result was reported.
- Strict mypy: 20 selected modules passed, including the new task-contract boundary and changed capability reservation code. This is selected-module coverage, not full-repository typing.
- Six existing Chromium checks passed: workflow overview, model activity, automatic routing, proposal import, updater and arcade pipeline. The new seventh `browser_task_contract_check.py` passed separately: review structured task details, atomic out-of-scope rejection, focused correction, real generated-app verification, source-bound ZIP export, persistent task receipt, mobile layout and no page errors. The new script is included in CI and the validation runner for future runs.
- Published v0.19.0 and candidate v0.20.0 were compared using the same synthetic decomposition/scope replay. Baseline accepted invalid metadata and wrote an undeclared JS file; candidate rejected invalid metadata, rejected the out-of-scope response and completed after the allowed correction. No behavioral execution or live repair-quality gain is claimed for that replay.
- Frozen manifest v11 validates all retained fixture hashes; prior fixtures remain unchanged. The new fixture explicitly discloses its post-initial-implementation/pre-release timing.
- Final runtime, tools, tests and assets are byte-compared to the package that passed extracted-distribution tests. Final packaging adds only release/audit documentation. The real updater validates the archive layout and checksum before release publication.

New native schema and prompts request structured task metadata. Legacy-shaped/imported proposals still load and are visibly labelled; the update does not manufacture contracts for approved historical work. Criteria remain declarations, saved dependencies remain source progress, and final verification/manual acceptance remain separate.

Remaining work: real-provider task adherence and quota testing, representative local-model task-size measurements, and independent task-level behavioral coverage. A 1–3-file scope is useful enforcement, not proof that every task is feasible for every model.
