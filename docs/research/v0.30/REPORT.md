# Evidence-ready delivery audit — October 21, 2026

Baseline: `32c6ef8` / v0.29.0. This is a reliability update grounded in an actual uploaded Tiny Wins export. It is not a preregistered paired live-model benchmark. The user's sample system prompts informed the requested scope; claims such as zero local latency/cost and blanket production-grade quality were not adopted.

## Verified diagnosis

The immutable diagnostic fixture `tests/fixture_data/tiny-wins-evidence-v1.json` has SHA-256 `c02e038ac538cd5546d8b494339e54ae14d5e152bfaf9b91c26e37f5a77ecb1d`. It retains the actual approved plan, uploaded app/test source, original file digests and isolated probe results. It is distinct from scripted model replies used in controller/browser tests.

The exported implementation was unfinished, with five saved tasks and a sixth candidate. The initial HTML remained the expected starter page; UI tasks had not run. Calling that a UI rendering bug would be inaccurate. The actual blockers were:

- `create_server()` did not initialize the schema; the first valid POST disconnected with `no such table: wins`.
- After independent test setup created the table, POST returned only `{"status":"created"}`. The approved DELETE test required an ID.
- GET on populated data disconnected because `dict(row)` was used on ordinary SQLite tuples.
- Exact routing on `self.path == '/api/wins'` prevented the query-string URL from reaching its parser: `?filter=today` returned 404.
- The test's remaining `urlopen(..., method='GET')` raised TypeError; this was a real defect, not a static-inspection false positive.
- The approved creation check had no body, so the actual app returned HTTP 400. Empty nested subset assertions did not establish stored records, and an empty restart assertion did not establish persistence. Daily-count code also counted all returned records; that last observation is source inspection, not an independently runnable count test against the broken backend.

`tiny-wins-probe.json` records isolated execution outcomes. No Windows measurements or provider calls were used. Existing frozen checks were not edited to make this app pass.

## Six-point review across five categories

| Category | Purpose/scope | Existing strengths | Weakness/bottleneck | Presentation and usability | Productivity impact and action |
|---|---|---|---|---|---|
| Core/backend | Proposal, bounded task execution, persistence, routing | Separate consent, frozen approvals, scope checks, source fingerprints, serialized inference | Syntactically valid tasks could defer crucial prerequisites; milestone repair lost task scope; verifier exceptions could leave cursor advanced | Labels separated saved from verified, but the process still allowed too much untested work | Add explicit evidence policy, stable endpoint contracts, a reviewed storage foundation and scope-preserving fail-closed milestones |
| UI/UX | Guide idea through review, execution, manual acceptance and export | Modern workbench, model activity, separate dashboard with working Follow | A novice could choose generation-only and infer saved tasks were working behavior; planning errors arrived late | Add a clearly named Plan with proof action and SQLite choice; explain that plan review is not execution; keep familiar legacy actions | Preserve the UI and add focused controls rather than a framework rewrite; test real mobile interactions |
| Developer tooling | Reproducible development and portable distribution | Standard library runtime, deterministic fixtures, pinned optional browser tools, updater validation | Rebuilding generic database code made small models repeat avoidable plumbing errors | Source remains portable to VS Code/Windows; no new runtime dependency | Add a reusable tested Store and protected tests; integrate the new browser check in tools/validate.py; publish through the updater |
| Performance/efficiency | Use limited model context/output and controller budgets well | Focused packets, exact edits, capability gates, transport circuits, per-run limits | Long model-generated rewrites and repeated repair consumed time; saved settings/actual GPU fit remain unknown here | Keep reservations and measured timing visible, with unknown values explicit | Reuse working storage, keep tasks small, test ordered prefixes before downstream work; no claimed token/latency saving without a paired trial |
| Workflow/usability | Make a project finish with trustworthy evidence | Actual HTTP/tests/launch phases, manual observations and export freshness | Empty assertions looked meaningful; ready checks were deferred; early checks could accidentally include future features | Show named declared milestones, preserve manual acceptance, and explain old-project recovery | Reject inadequate proof drafts before approval, validate each batch, and stop failed milestone progression without widening scope |

## Severity and implemented plan

**Critical — milestone scope and resume.** Repairs of failed milestones now receive the original task packet, including current task/files. Subsequent static corrections receive the same scope even after the original pending task was cleared. The cursor is marked unverified before invoking the verifier, so exceptions/cancellation do not skip it. Success restores the cursor before sealing its checkpoint. Regressions reproduced out-of-scope writes and exception-driven advancement before fixes.

**High — acceptance quality.** New explicit proof mode imposes `acceptance_policy: evidence_v1` on the unapproved artifact. It rejects vacuous JSON subsets, success mutations without concrete example input (with an explicit explanation escape for deliberately bodyless endpoints), restart checks without observed values from earlier mutations, and missing successful business endpoint contracts. API typing continues through the existing consistency reviewer. This is a conservative deterministic quality gate, not proof of arbitrary semantics or complete feature coverage.

**High — task readiness.** Proof mode schedules ordered check prefixes at the task that last implements their declared feature work. Partial task batches cannot schedule checks for future features or defer currently ready prefixes. Full review requires coverage and an intermediate business checkpoint for multi-task server plans. These relationships are declared, not inferred from source. Actual execution is required to establish behavior.

**High — shared storage foundations.** The separate SQLite collection starter supplies a working collection API and Store, without changing old starter versions. Store initializes tables/indexes in construction, sets row_factory, uses parameterized values and explicitly closes each connection. Default DB location stays beside app.py; tests inject a disposable database path. Query routing parses path before filters. IDs, validation, date filtering/counts and delete results have protected regression tests. The starter page is intentionally unfinished; feature UI remains approved task work.

**Usability — explicit stronger mode.** Plan with proof uses the existing staged planner, includes the actual policy instructions and stage schema, and retains consent/routing/capacity guards. Editor changes cannot silently remove its policy. Executing a proof plan requires its declared checkpoint option; files-only generation remains available and never executes code. Existing single/guided plans are not migrated or retroactively rejected on build.

No general agent framework, parallel GPU inference, new provider, autonomous test weakening, dependency installation or automatic model replacement was introduced.

## Primary research and local-model guidance

`sources.json` records URLs, retrieval sizes and hashes. The reviewed primary sources were CPython's SQLite documentation, CPython's urllib implementation and Ollama's API documentation.

1. CPython explicitly states a Connection context manager **does not close the connection**. The Store wraps transaction management with `finally: conn.close()`. Row mapping is set when opening each connection. Request keywords belong on `urllib.request.Request`, not directly on `urlopen`.
2. Ollama reports load/evaluation timing and supports separate context/prediction settings. Context, output cap and observed throughput are different quantities. The existing workbench's bounded metadata and telemetry paths remain in use; no catalogue field is treated as a success-rate benchmark.
3. Local models offer local execution and control of data transfer, not zero latency, zero energy cost or guaranteed privacy for a separate cloud route. Loading, prompt evaluation, output generation and memory pressure all matter. Keep cloud consent explicit.
4. The user's installed Qwen coder/general models remain available. This update does not assert a current model leaderboard, invent a Llama coding-model ID, infer deployment maxima from example settings or download replacement models. The supplied Windows run is direct evidence of specific successes/timeouts; it does not isolate quantization or GPU fit.
5. Keep API/Storage setup deterministic, then give the local builder one bounded change with complete scoped source and fixed interfaces. Short JSON output and exact edits reduce required output work, but the newly supplied scaffold can add input context; net cost/latency was not measured. A larger system prompt alone cannot repair contradictory contracts.
6. GGUF/Ollama/llama.cpp, EXL2/ExLlama and AWQ/vLLM are different runtime/format choices. Swapping formats is not a Foundry repair. First measure the actual installed runtime using existing local calibration, `ollama ps` and vendor GPU tooling. Windows WMI AdapterRAM alone is insufficient to choose model fit. Calibration smoke tests do not prove project fitness.

The [v0.28 inventory](../v0.28/model-matrix.json) retains the user's nine installed Ollama tags and fourteen journal provider/model pairs, separating unknown maxima from secondary estimates. No new live ranking was established here. Keep cloud planning/local building as explicitly selected; use the installed coder for small changes and alternate models only within the configured route. A model that passes a smoke fixture is a candidate for a controlled project trial, not automatically the best model.

## Validation boundaries

The new controller tests freeze the actual failed plan, preserve legacy acceptance, test policy-removal attempts, correct/incorrect checkpoint placement, scoped repairs and cursor recovery. A test expectation was corrected from None to the existing resume_problem success value `''`; no existing test was weakened. The SQLite fixture's real HTTP tests execute in disposable directories.

The new Chromium flow uses scripted LLM replies but actual production planning/approval/build/verification/export paths. It executes a three-check SQLite milestone before UI work, runs final tests, opens the actual generated app, checks mobile create/reload/Today filtering/delete and safe literal HTML-like text, then saves the observations and downloads the verified bundle. This is controller/browser reliability evidence, not live Ollama repair-quality evidence.

Full suites, strict typing, existing browser regressions, dashboard build/simulation checks, archive byte equivalence and updater extraction are required before publication. Exact release results are reported on completion. Docker execution, the user's installed Windows models, GPU performance and live provider quota remain untested here.

## Next measurable gate

Create a fresh Tiny Wins draft using the SQLite foundation and Plan with proof. Review the replacement contract; do not overwrite the old approved project. Execute approved early milestones and retain the journal and receipts. The next patch should target the first reproducible failure or a controlled same-task comparison of local models/settings. Do not claim exponential improvement, arbitrary-project completion or public-hosting readiness from a fixture pass.
