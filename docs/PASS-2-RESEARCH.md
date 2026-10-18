# Pass 2 — workflow audit and research

Date: 2026-10-18. Baseline: published 0.6.0, 127 tests. Target: 0.7.0.
Theme: capability-aware app building and evidence, with the blue-flame studio identity.

## The observed failure

The actual Neon Dodge proposal replaced requested localStorage with SQLite. It expected a
record before the POST that created it and mapped a JavaScript source-string match to gameplay.
When corrected, planning failed because the validator required an HTTP route beyond / and
/health and only HTTP checks counted toward feature coverage. This made a supported client-side
browser game impossible to describe honestly. The UI then displayed the previous proposal with
the revision's error, making it unclear what had changed.

The generator's existing complete-file validation was transactional, but an invalid response
ended the job immediately. The verification engine tested Python/HTTP/CLI well; it did not run
JavaScript or distinguish pending human acceptance from automated success. Those were the
highest-value changes. Framework expansion, arbitrary shell tools, autonomous self-modification
and additional competing agents would not fix this contract mismatch.

## Official sources inspected

Some vendor documentation sites are blocked by the environment's network policy. The following
official GitHub source documents were successfully retrieved instead. This is design research,
not a paid-product trial, comparative ranking or a claim that a particular model is best.
No external product implementation was copied into Foundry.

| Source | Established practice | Application here |
| --- | --- | --- |
| [Anthropic agent workflows cookbook](https://github.com/anthropics/anthropic-cookbook/tree/main/patterns/agents) | Prompt chaining, routing and evaluator/optimizer loops as explicit workflows | Keep the existing bounded plan/build/evaluate/repair state machine. Add focused feedback for response-contract failures rather than unconstrained agent recursion. |
| [Playwright best practices](https://github.com/microsoft/playwright/blob/main/docs/src/best-practices-js.md) | Test user-visible behavior, isolate tests, use locators and auto-waiting | Optional declarative click/fill/press/assert steps in a real fresh Chromium profile. Never treat source text as proof of interaction. |
| [Playwright actionability](https://github.com/microsoft/playwright/blob/main/docs/src/actionability.md) and [assertions](https://github.com/microsoft/playwright/blob/main/docs/src/test-assertions-js.md) | Actionability checks and retrying assertions instead of arbitrary long sleeps | Locator actions and bounded expect assertions. Short explicit waits are limited to animation/timing observations. |
| [Playwright Python](https://github.com/microsoft/playwright-python) | Real browser automation on Windows/Linux/macOS | Optional development/runtime dependency, clearly diagnosed. Core and generated app remain standard-library Python plus local web assets. |
| [Ollama API](https://github.com/ollama/ollama/blob/main/docs/api.md) | Structured JSON and native response formats | Extend the existing native plan schema for browser/manual contracts; keep semantic review separate from JSON grammar. |
| [Aider repository map](https://github.com/Aider-AI/aider/blob/main/aider/repomap.py) | Rank source relevance under an explicit token budget | Retain bounded source maps and small projects. Retrieval-based editing is a future measured change, not an untested feature claim in this release. |
| [OpenHands](https://github.com/OpenHands/OpenHands) | Durable workspaces and separate execution environments | Preserve checkpoints, consent, isolated Docker checks and versioned update recovery. Browser automation currently requires explicit local execution; no silent Docker-to-host fallback. |

Existing competitor research in RESEARCH.md remains historical context. These sources support
patterns, not a numerical claim of exponential improvement or a guarantee of arbitrary app success.

## Changes and boundaries

- Optional app_kind, browser_checks and manual_checks extend existing plans without a state migration.
- Feature coverage is the union of HTTP/browser/manual evidence. Server apps still need a real
  HTTP behavior check; client-side apps can honestly declare manual/browser interactions.
- Automated success with outstanding manual checks becomes review_required, not verified.
  Human results are explicitly labeled and bound to the source fingerprint. They are not tests.
- Real browser checks run only after execution approval and the Python phases. Required tests
  cannot silently skip if Playwright/Chromium is absent. HTTP/assets remain distinct from gameplay.
- A known-working arcade starter reduces generation work. User changes still go through plan
  approval, bounded tasks and verification; choosing a template does not claim model quality.
- New source tests exercise the real app and exclude project/private files from serving.
- Rejected complete-file responses get one correction request per operation, no partial file
  writes. Existing repair-decision limits and explicitly configured fallback remain bounded.
- The icon asset is a faithful generated adaptation of the supplied mascot, created with the
  image tool. The visual theme uses local charcoal/cyan assets, accessible focus and reduced motion.

## Next measured pass

Use an opt-in benchmark on the user's actual Ollama models: accepted scope, usable app completion,
repair decisions, response-contract rejections, input/output tokens and wall time. Then implement
relevance-based context selection and stronger edit contracts, preserving frozen acceptance.
Add a separately built browser-test container only after its image, dependencies and isolation
are repeatably tested. Broader frameworks and migrations need their own environment contracts.
