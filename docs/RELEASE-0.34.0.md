# Idea Foundry 0.34.0 — living forge and acceptance recovery

## Findings from your diagnostic report

Report `ad36a5b2cf2d4d9a85d46cfdf28163f6`, exported 2026-10-21 at 21:19 UTC (5:19 p.m. EDT), matches the published v0.33.2 source identity. All 18 manifest member hashes and byte sizes matched. This is integrity evidence, not producer authentication.

The latest planning run `965f64e256e345d58b4a9c60123ee3f9` lasted 332.189 seconds. Its six local acceptance replies were rejected: two Qwen2.5 replies omitted feature coverage; two Qwen3.5 replies misplaced restart flags; DeepSeek omitted response assertions and later produced invalid check structure. No new feature-task request followed these rejected checks. The saved draft had five features and zero tasks; the ten tasks shown elsewhere belonged to an older rejected proposal. Nothing was approved, built or executed in this run.

v0.33.2 therefore moved validation to the intended early gate, but local acceptance generation still failed. Code inspection found a contradictory correction instruction: it required correction "without ... changing acceptance checks", although those draft checks had not been approved and were the invalid part. The instruction is a confirmed defect; the private model transcripts are unavailable, so it is not proof of why each model repeated an error.

## Implemented changes

- Acceptance-stage corrections explicitly permit repairing rejected draft names, methods, bodies, assertions, restart placement, ordering and feature references, and adding missing UI coverage. The saved scope and original requirements stay fixed. Approved baseline checks and frozen tests remain protected. Other correction stages keep their existing policy.
- Each acceptance request includes a labeled synthetic wire example: POST a concrete value, GET the same value with `restart_before:true`, then DELETE; a manual UI check example and an explicit all-feature coverage reminder. These are model inputs, never automatically installed tests. Starter contracts and the real scope take precedence.
- Native Ollama acceptance schemas restrict HTTP, manual and browser feature indexes to the actual saved scope. This does not force semantic coverage or make non-schema providers schema-enforced. All normal validators, six-rejection stage limit, whole-job allowance, output reservations and truncation capacity rules remain in place.
- Diag now separates retained proposal structure from actual approval. It records manual/browser feature references and uncovered indexes without user steps, names, expected prose or source. The workbench explains when older proposal task totals differ from the current saved draft.
- The original goat mascot is enlarged from 49 px to a 144 px desktop emblem, with a 110 px mobile layout. Independently animated SVG flame layers overlay the original PNG; the original artwork and favicon remain intact. The flame uses blue/cyan gradients, gentle transform/opacity motion and a soft halo. It intensifies only when the existing model-status snapshot reports an in-flight request, clears working state on failed status reads, pauses while the page is hidden and provides a persistent motion toggle. OS reduced-motion settings override animation. No sound or extra polling was added.

## Evidence and limits

Before the acceptance patch, the instruction-following controller fixture stopped with `schema_error`; missing scope constraints and wire examples also failed assertions. The corrected controller fixture proceeds through scope, acceptance, `schema_correction`, and only then feature tasks. Diag label/coverage regressions separately failed before their changes. Fixtures model protocol behavior, not live reasoning quality.

The archived observations and exact frozen provenance are in `tests/fixture_data/acceptance-guidance-v1.json`. The original model replies are unavailable; no private transcript is reconstructed. Prior frozen datasets remain unchanged in the append-only v18 manifest. Release validation records source/distribution checks in `releases/validation-0.34.0.json`.

## Known issues retained honestly

- A model may still omit requirements or generate invalid checks despite clearer instructions and schema constraints. Finite fallback and explicit failure remain necessary. No claim that every project or provider now succeeds.
- The old tiny Test report still contains Qwen3.5 truncation at a 1,024-token budget. It predates the latest run. This update does not turn that probe into a capability benchmark, fix the separate cloud-target preview issue, or establish provider quotas.
- Older tiny-probe rows can label an unaccepted truncated response as `response_received:false` even when finish/token metadata demonstrates returned output. That separate telemetry-label correction remains pending; these rows must not be interpreted as proof that the model was offline.
- The saved planner is Qwen2.5 local, while the builder route contains cloud backups. Builder cloud requests still require consent; this update does not silently rewrite that route.
- Older interrupted-session records and a long wall-clock gap do not establish a continuous two-hour request, GPU exhaustion or a specific shutdown cause.
- Matching saved scopes can resume. Changed request identities start fresh drafts; validators do not bypass this safeguard to manufacture resume.
- Live Windows GPU performance, model quality and cloud generation were not tested in this workspace.

## Try the update

1. Use Update, install and confirm 0.34.0 after restart.
2. Check the larger flame and use its motion toggle; it should remain calm while idle. Motion preference survives reload; reduced-motion settings stop animation.
3. Keep Tiny Wins open and its revision unchanged. Click Resume small-step planning once. Review the scope and checks if it reaches proposed; do not approve the older rejected proposal.
4. Export Diag after the run, before another retry or approval. Look for acceptance correction before feature tasks and current draft counts separated from retained proposal counts.

## Research basis

MDN's animation performance guidance supports using compositor-friendly transforms/opacity where possible; this is a design choice, not a measured performance claim on your PC. Its reduced-motion guidance supports honoring OS preferences alongside an explicit pause control. Ollama's structured-output documentation supports supplying JSON Schema and concrete response examples while keeping semantic validation separate. Source URLs, fetch dates and SHA-256 values are recorded in `docs/research/v0.34/sources.json`.

## Source proof

Before changing the acceptance instruction, scope schema or request examples:

```text
python -m unittest tests.test_acceptance_guidance -q
Ran 3 tests in 0.064s
FAILED (failures=2, errors=1)
```

The error was the deliberately absent native feature enum; the failed controller assertion reproduced the uncorrectable draft instruction, and the remaining failure identified absent wire examples. Separate Diag approval/coverage assertions also failed before their fixes.

After the patch and frozen-fixture/privacy assertions:

```text
python -m unittest tests.test_acceptance_guidance -q
Ran 6 tests in 0.102s
OK

python -m unittest discover -q
Ran 533 tests in 137.729s
OK
```

Strict mypy passed the 36 modules in `tools.validate.TYPED`. Dashboard TypeScript checks, all four Node tests and the production asset build passed. No existing tests were skipped or weakened. Final browser and extracted-distribution results are recorded in the release validation file after completing those checks.

All 24 workbench browser scripts listed in `tools.validate` passed, including the new emblem test, plus both Dashboard browser/launcher checks. The emblem test drives an actual in-flight Workbench job with fixture replies and verifies animation, completion/error clearing, persistent pause, reduced motion and desktop/mobile geometry. The Dashboard still renders 289 nodes, 445 edges and 178 scenarios. Browser screenshots were visually inspected; no Windows GPU or frame-time benchmark is inferred from them.
