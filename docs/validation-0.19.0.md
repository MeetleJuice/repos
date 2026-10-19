# v0.19.0 validation

Date: 2026-10-19. Linux/Python 3.11, installed Chromium and Playwright 1.56.0. No real provider credentials or paid inference. Windows behavior is covered by compatibility code and updater fixtures; no physical Windows machine was tested here.

- Initial checkout suite: 315 tests passed in 111.883 seconds. A subsequent wire-level regression was added and the seven-test execution-boundary module passed.
- **Extracted distribution: 316 tests passed in 112.262 seconds.** No skipped/expected-failure result was reported. `python tools/validate.py --package --browser` completed successfully.
- Strict mypy: all 19 selected modules passed, including `build_contract.py`, `models.py`, `workflow.py` and `http_io.py`. This is selected-module coverage, not a claim of a fully typed repository.
- Six actual Chromium scripts passed: workflow overview, model activity, automatic routing, proposal import, updater, and arcade pipeline. The workflow script was rerun after adding identical-node/concurrent-request assertions and passed. Coverage includes real generated-app HTTP/test/launch verification, manual evidence, export manifest hashes, mobile layout and browser error assertions.
- Paired controlled v0.18.1/v0.19.0 replay: unchanged README echo changes from `error`/zero saved tasks to `generated`/one saved task; original README remains unchanged in both. A simulated slow-body response accepted after 18 simulated seconds under the old helper is classified as transport failure at 12 simulated seconds under the new helper's 10-second budget. These are fake-clock outcomes, **not measured wall-clock performance**. Results: [paired replay JSON](research/execution-boundary-paired-0.19.0.json).
- Append-only frozen fixture manifest v10 validates every retained fixture hash. Changed protected artifacts still reject atomically; original task/Unicode payload values remain equal.
- Final distribution runtime, tests, tools and assets are byte-compared against the extracted/tested package; final additions are audit/result documentation. Git diff whitespace check passed.

Remaining validation: real provider quotas/model adherence, Josh's final task, actual Windows/GPU runs and independent secure EVE OAuth integration. The elapsed reader guard is checked between reads and cannot promise hard cancellation during a blocked socket operation.
