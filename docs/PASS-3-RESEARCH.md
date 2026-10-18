# Pass 3 research and audit: repair from evidence

Reviewed 18 October 2026. Focus: make a reported or reproduced browser failure actionable,
without replaying a proposal or weakening its acceptance tests. This is a scoped engineering
upgrade, not a claim of exponential improvement or universal app generation.

## Findings from this repository and the real shield build

| Area | Existing strength | Concrete bottleneck | This pass |
| --- | --- | --- | --- |
| Generation | Sequential small tasks, reviewed starters, bounded model routing, transactional checkpoints | Small fixes require returning whole JavaScript files; local models can change unrelated working behavior | Optional exact search/replacement edits, with uniqueness checks and the same file protections |
| Verification | Independent real HTTP, unittest and launch phases; optional Chromium; honest manual acceptance | The shield build passes four server tests while the first blocked obstacle hits again on the next frame | Repeatable browser sequences and exact-text assertions; regression that actually fails on the uploaded game |
| Self-healing | Bounded automatic repair on automated failures | A failed play-test sends the user back into planning, losing a precise report and wasting requests | Saved observations can go directly to the coder, then static inspection and optionally full verification |
| Resilience | Frozen acceptance/tests, side-by-side updates, rollback, portable ZIPs | New repairs must invalidate stale acceptance while keeping the original failure evidence | Checkpoints plus bounded repair history with source fingerprints, included in exports |
| UX/extensibility | Local-first operation, explicit execution/cloud consent, Windows launchers | No place to attach observed behavior to individual failed checks | Per-check notes, explicit files-only versus repair-and-retest buttons, focused next-step guidance |

## Authoritative references and decisions

1. [Playwright clock guidance](https://github.com/microsoft/playwright/blob/main/docs/src/clock.md)
   documents installing clock instrumentation before page code and running animation/timers with
   `run_for`. Adopt controlled virtual time, held keys, bounded durations, and deterministic random
   fixtures. These test settings never change exported production code. A canvas animation assertion
   alone cannot establish collection or collision correctness.
2. [Playwright best practices](https://github.com/microsoft/playwright/blob/main/docs/src/best-practices-js.md)
   recommend testing visible behavior and keeping tests isolated. Use a new page per check so held
   keys, injected randomness and clock state cannot leak; retain only explicitly shared disposable
   browser storage. Check meaningful DOM states and record the exact failing step. Existing network
   restrictions, fresh profiles and explicit local-execution approval remain.
3. [Aider exact edit implementation](https://github.com/Aider-AI/aider/blob/main/aider/coders/editblock_coder.py)
   demonstrates resolving search/replacement operations against current source. Adopt a narrower
   JSON contract: at most twelve edits, exact unique matches only, sequential application in memory,
   no fuzzy matching. Expand to full files before existing validation/checkpoint/atomic replacement.
   Reject ambiguous, stale, missing, unchanged or protected targets without any partial write.
4. [Anthropic evaluator/optimizer example](https://github.com/anthropics/anthropic-cookbook/blob/main/patterns/agents/evaluator_optimizer.ipynb)
   supports an explicit evaluation-feedback-improvement loop. Here the evaluator is an actual test
   or a clearly labelled user observation, not a second model claiming success. Keep a shared bounded
   repair budget, preserve checks, and require fresh acceptance after changes.
5. [ESLint no-self-compare](https://github.com/eslint/eslint/blob/main/docs/src/rules/no-self-compare.md)
   explains the uploaded `p !== p` problem and documents limitations. Do not add a regex-based pretend
   JavaScript parser or require Node for the stdlib workbench. Real browser behavior catches the
   observed collision failure; a future optional parser/linter can add earlier feedback.

The clock, Aider, Anthropic and ESLint source documents were fetched from their official GitHub
repositories during this pass. Best-practice guidance was also inspected during the prior research
pass. These sources inform the implementation; they do not demonstrate this model/hardware's speed.

## Measured and unmeasured

The checked-in shield regression uses the actual 7,155-byte user-uploaded game. Its HTTP/assets,
four Python tests and CLI launch pass; a repeatable Chromium check then catches game-over after the
blocked hit. A controlled six-edit response repairs it, and the same frozen browser check passes.
Additional checks exercise collection, pause, consumption, later unprotected collision and restart.
The response fixture is 1,845 UTF-8 JSON bytes versus 8,278 bytes for complete resulting-file JSON:
77.7% fewer response bytes in this one case. This is an output-size comparison, not measured tokens,
GPU acceleration, model quality, inference speed or a general benchmark. Input source budget stays
unchanged. Model request counts and provider-reported token usage remain the actual measurements.

## Next highest-value work

- Make optional browser tooling easier to diagnose and install in the exact interpreter used by
  the Windows launcher, with explicit user choice and no silent dependency/runtime switch.
- Add testable pure JavaScript logic modules to new game starters, with rendering kept separate;
  preserve existing project directories and legacy checks rather than silently migrating them.
- Build a versioned evaluation set across notes/tasks/browser tools/games, recording actual model
  results, repair success, latency and output size on the user's models. Controlled fixtures test
  orchestration, not live-model compliance.
- Evaluate an optional real JS parser/linter and richer visible-state assertions before expanding
  supported frameworks. Multi-agent consensus and framework breadth do not fix a weak evaluator.
