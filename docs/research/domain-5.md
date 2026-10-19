# Domain 5 — Independent verification and repair overfitting

Research/access date: 2026-10-19. This is a source audit, not a new live-model benchmark.

## Evidence and source quality

- **Primary, accessed:** [SWE-bench harness grading implementation](https://github.com/SWE-bench/SWE-bench/blob/main/swebench/harness/grading.py), retrieved from [raw source](https://raw.githubusercontent.com/SWE-bench/SWE-bench/main/swebench/harness/grading.py). `get_resolution_status` requires both fail-to-pass resolution and pass-to-pass maintenance to equal 1 for FULL. This supports retaining an independent regression suite while checking the reported defect. It does not establish a success rate for Foundry.
- **Primary, accessed:** [SWE-bench README](https://github.com/SWE-bench/SWE-bench/blob/main/README.md), retrieved from [raw source](https://raw.githubusercontent.com/SWE-bench/SWE-bench/main/README.md). Its reproducible execution harness is a useful pattern; Foundry's small generated browser apps differ substantially from SWE-bench repository issues.
- **Relevant publication, access blocked:** [The Strength of Random Search on Automated Program Repair](https://arxiv.org/abs/1507.08746), concerning plausible versus correct patches. The arXiv request was blocked by this environment's proxy (403); no numerical claim from the paper is adopted.
- **Relevant conceptual source, access blocked:** [Concrete Problems in AI Safety](https://arxiv.org/abs/1606.06565), including reward hacking. Same proxy restriction. Here the practical analogue is optimizing a visible test while missing the requested behavior; there is no evidence that Foundry's failures imply malicious intent.
- **Unverified:** icatagent/EnterpriseAPR percentage or performance claims have no verified primary source in this thread. Do not put their numbers in product claims or use them to justify rollout.

## Current implementation and measured code surface

Read-only audit counted `inspection.py` 61 lines, `harness.py` 320, `evidence.py` 81, `runner.py` 215; `test_evidence.py` defines 22 test methods and `test_verification.py` 10. These are static source counts, not executed-test results or coverage percentages.

**Existing contract strengths:** approved CHECKS/manual/browser documents are immutable; trusted test SHA-256 values prevent replacement; evidence is tied to a source fingerprint. HTTP acceptance, generated unit tests and launch run in separate subprocesses/disposable copies. Persistence checks close the server and start an independent process against the same phase data directory. Generated tests must run, pass, avoid skips/expected failures, and exercise `app.py`. Manual observations explicitly remain user evidence. Docker and trusted-local execution require distinct choices.

**Actual capability limits:** AST/import checks and one application-call observation reject some trivial tests, but cannot prove assertions cover meaningful behavior. New tests can be edited before their first successful verification; after success their hashes freeze. Approved tests are shown in repair context, so they are regression oracles, not hidden holdouts. HTTP delivery and asset checks cannot establish gameplay correctness. Source/output budgets and bounded retries prevent runaway loops but are not correctness evidence. Phase logs are bounded. None of these mechanisms makes trusted-local execution a hostile-code sandbox.

## Recommended scaffold contract

1. Give each deterministic scaffold an independently authored acceptance suite outside model-editable source. Version the scaffold/check bundle and preserve its hash in reports. Keep generated tests as supplemental evidence.
2. Report separate outcomes: **static-valid**, **acceptance-pass**, **regression-pass**, **browser/manual-pending**, and **verified-for-listed-checks**. Retain failed evidence on unchanged source; do not summarize “all working” from HTTP 200.
3. Require both target-defect reproduction (fail before / pass after) and unchanged regression success for repair fixtures, following SWE-bench's resolution-plus-maintenance distinction. A test-only workaround must not count as an implementation repair.
4. Start independent checks with observable user actions, fresh data, invalid input, restart persistence, missing IDs and alternate record order. Seeded boundary fixtures help detect hard-coded `/1` responses. Keep those cases deterministic and bounded.
5. Add adversarial verifier tests for duplicate application logic, trivial assertions, skipped suites, document/test tampering and stale fingerprints. Dynamic profiling is a useful signal, never a completeness claim. Hidden holdouts, mutation testing and learned verifiers remain **future work**, not current guarantees.

Success metric: completion of the independently checked workflow per fixture, with regression retention and failure taxonomy. Track attempts, elapsed time and reported tokens separately; do not conflate lower latency or more tests with higher correctness.
