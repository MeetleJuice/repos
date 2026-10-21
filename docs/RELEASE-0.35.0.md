# Idea Foundry 0.35.0 — smaller work units, saved progress

## Why this project still had no new code

Report `beec18d6f5d94ed5a9d90200ac3a9ea1` identifies v0.34.0 and the tested 426-file source tree. All 18 exported manifest members matched their size and SHA-256. Its latest run lasted **767.064 seconds**: eight local requests, six rejected acceptance objects and two 300.09-second timeouts. Waiting for those two requests consumed 600.18 seconds. The first Qwen2.5 reply and its correction had identical normalized JSON digests. Models responding incorrectly and models timing out are different problems.

The current saved scope had five features, no accepted outline and zero newly planned tasks. The ten tasks elsewhere were retained from an older rejected proposal. No new task-generation request, build, approval or execution occurred in this run. Earlier patches improved error classification and moved validation earlier, but still asked a small model for a complete multi-feature acceptance object. That all-or-nothing request remained the bottleneck.

## End-to-end architectural audit

| Category | Strength retained | Observed weakness / resulting change |
| --- | --- | --- |
| Core architecture | Separate proposal, approval, generation and execution; source-bound checks; controller-owned task dependencies | Acceptance still put cross-feature bookkeeping on the model. The new explicit strategy gives it one feature and assigns references deterministically. |
| UI and experience | Model activity and validation codes are visible | Old proposal totals obscured an empty current draft. New acceptance counts and a distinct planning action expose actual saved work. The emblem is larger and has more natural contour motion. |
| Developer tooling | Frozen regressions, strict typing, real browser tests and extracted-distribution validation | Happy-path fixtures did not show the repeated wholesale acceptance failure. A labeled five-feature fixture now exercises incremental acceptance, interruption, context projection and real delivery. No dependency/framework was added. |
| Performance and efficiency | Serialized local inference, explicit output reservation and finite attempts | The observed run spent 600.18 seconds waiting on two models. Smaller feature packets remove rejected-plan/source baggage; the UI socket-timeout default is now two minutes. This is not a measured live speedup or a hard job deadline. |
| Usability and integration | Approval, manual evidence and execution consent are separate | Repeating the same whole-stage retry discarded acceptance progress. New checkpoints retain each validated prefix, while strategy/request changes start a fresh unapproved draft. Existing routes and legacy planning remain available. |

## What changed

Choose **Plan feature by feature** on an unapproved project's workbench, or choose the corresponding new-project planning option. It selects the versioned `feature_v1` acceptance policy with evidence-ready review. Switching from the old strategy starts a fresh draft under a new full request identity; no old invalid checks are silently adopted.

1. Save and validate scope.
2. Ask for only one feature's HTTP/manual/browser acceptance evidence. Every HTTP check still needs an assertion. Manual-only UI features can contribute no HTTP checks. Delivery checks do not count as feature behavior.
3. Assign feature references in the controller. Reject model-supplied references, empty evidence and inconsistent earlier API contracts. Validate the entire accumulated prefix without pretending it is a complete proposal.
4. Save that prefix before requesting the next feature. A matching interrupted draft resumes at the next acceptance feature.
5. Run complete outline validation after all features, then compile sequential scoped tasks and apply the unchanged full-proposal reviewer. Only a complete proposal can be approved.

`planning_feature_v1` packets preserve exact original idea, revision, change request, fixed scope, starter contracts and approved baseline requirements. They omit the non-authoritative previous proposal, starter source, implementation context, ownership boilerplate and builder profile from acceptance requests, with field/digest disclosure. Scope creation and existing full-context modes are unchanged. This is an explicit planning-context policy, not silent truncation of a coding handoff. More small calls may increase cost; no billed-token or live-quality improvement is claimed.

Existing per-model correction, six-rejection stage bounds, 24-request planning-job allowance, cloud consent, output reservations and no-smaller-cap truncation fallback remain enforced. Large plans may require resume when the job allowance is reached. Legacy modes can be explicitly selected again; approved projects cannot be replanned in place.

Diag reports saved acceptance counts and structural coverage without check prose. The Dashboard's saved-prefix node follows actual recorded checkpoint events and does not imply app verification. The new planning action and default two-minute local timeout are visible; an explicit five-/ten-minute menu choice remains honored. Socket timeouts are not whole-job deadlines.

## Larger, more organic flame

The original PNG and static favicon remain. The emblem is now **192 px on desktop**, **144 px on mobile**, with a 128 px fit for very narrow screens. A taller flame has independently morphing contours, softer blue bloom and a brighter cyan/white core. The motion remains stylized vector fire rather than photorealistic footage. No network animation asset, shader library or extra polling is used.

The existing motion toggle, page visibility and OS reduced-motion preference now pause both SVG contour animation and CSS motion. Working-state brightness still comes from observed model status and clears if that status cannot be read. SVG shape morphing repaints a small flame region; no frame-rate or Windows GPU benchmark is inferred from the visual design.

## Regression and evidence boundaries

Before the feature planner, two new assertions failed: the controller made one whole-stage acceptance request, and it could not checkpoint/resume a feature prefix. Afterward, the eight focused tests cover one-feature requests, five-feature coverage including the missing UI slot, context preservation/omission disclosure, invalid references, delivery-only rejection, interruption/resume, native schema ownership and a real Workbench run that can switch back to legacy proof planning.

The browser fixture follows granular planning through an invalid feature correction, human approval, real SQLite checks, source-protected milestones, actual mobile browser interactions and a verified ZIP. Model replies are scripted; this is end-to-end harness evidence, not live model reasoning quality. Prior frozen bytes remain unchanged in the appended v19 manifest. The fixture's texts are synthetic; the private model replies from your export were unavailable.

Source verification:

```text
python -m unittest tests.test_feature_acceptance -q
Ran 8 tests in 0.256s
OK

python -m unittest discover -q
Ran 541 tests in 142.516s
OK

python -m mypy --strict <37 modules listed in tools/validate.py>
Success: no issues found in 37 source files
```

Before implementation, the two initial feature-packet/resume assertions failed because the old path requested one entire acceptance stage and never saved an individual feature prefix. The release validation record separately records source, browser and extracted-archive results; fixture providers never use the private keys on the user's PC.

All 25 workbench browser scripts listed in `tools/validate.py` passed, including the final new-project two-minute timeout assertion. Both `forge/dashboard/browser_check.py` and `forge/dashboard/launcher_check.py` passed. Dashboard TypeScript checking, all four Node tests and production asset build passed; its generated graph has 293 nodes, 453 edges and 179 source-backed scenarios. These counts describe the tested harness and UI, not 25 independent live-generated projects.

## Try this version

1. Update and confirm 0.35.0 after restart.
2. Open Tiny Wins, retain its revision, and click the new **Plan feature by feature** action. Leave the visible local planning timeout at two minutes for this test.
3. Expect scope, saved acceptance counts, task batches, then a complete proposal. Switching strategy can create a fresh scope; later matching runs retain their validated prefixes.
4. If a proposal is ready, review its persistence scenario, timestamps and browser actions before approval. If it stops, export Diag once rather than repeatedly retrying unchanged input.

## Known limits and next measurements

Live model quality and Windows GPU behavior remain untested here. Small models can still invent unsuitable assertions or misunderstand a feature; controller-assigned references prove declared coverage, not semantic correctness. Human approval and real app testing remain essential. Existing quota/account problems are not repaired by this planning policy.

The older tiny Test truncation and cloud-target preview issues remain separate. Historical shutdown gaps do not prove continuous hung work. The saved builder's cloud backups still require consent; this update does not silently change routes. Next measurements should compare saved acceptance progress, actual model time and completed app behavior on the user's PC, including whether the smaller calls justify their additional count.

Research sources: Ollama's structured-output guidance and MDN's SVG animation/accessibility guidance, plus the previously recorded v0.34 animation performance/reduced-motion sources. Fetch dates and SHA-256 values are in `docs/research/v0.35/sources.json`. The design applies deterministic bookkeeping and bounded staged work already used by Foundry's task compiler; it does not claim a new external agent framework benchmark.
