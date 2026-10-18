# Executive pass 3 — version 0.8.0

**Theme: evidence-driven repairs.** The app builder should repair a specific failed behavior,
not repeatedly rewrite a proposal or confuse working HTTP delivery with working gameplay.

The main changes are a direct saved-failure repair action, exact source edits validated before
transactional writes, and deterministic optional Chromium checks with useful failure reports.
The existing proposal → approval → build → verification workflow, local models/cloud routing,
frozen regression tests, starter templates, workspace schema 2, update manifest schema 1 and
side-by-side update/rollback protocol remain. No user-generated files are silently migrated.

The real uploaded shield build is now an executable negative regression: it passes four Python
server tests but fails the controlled browser collision check. A six-edit reference response
then passes that same frozen browser check. Further tests cover collection, pause, shield
consumption, a later collision and restart. Controlled responses establish the orchestration
and evaluator; they do not establish arbitrary live-model reliability.

In this fixture, exact-edit response JSON is 1,845 bytes versus 8,278 for a whole-file response
(77.7% smaller). No GPU, token-throughput or general speed improvement is claimed. Runtime and
cloud approval still apply; execution flags must be actual JSON booleans. Manual observations
remain labelled separately, and a repaired app needs fresh verification/acceptance.

Next: simpler optional Windows browser-tool setup, testable JavaScript logic in new starters,
and a reproducible multi-app evaluation set on the user's actual local models before broader
framework support. See [research](PASS-3-RESEARCH.md), [release guide](RELEASE-0.8.0.md) and
[validation](VALIDATION.md) for scope, rationale and executed checks.
