# v0.19.0 — execution boundary reliability

Audit date: 2026-10-19. Baseline: a9da611/v0.18.1. The supplied Josh log records 5/6 saved tasks, repeated protected README rejections, a 70,000-character rejection, long requests and a batch-labelled route entry. Raw rejected responses and the generated app were not supplied. This audit reviews the controller and its contracts; it does not establish that Josh's unfinished app works.

## 1. Core Architecture & Backend Systems

- **Purpose & scope:** `core.py` owns persistent proposal/approval/build/verification/repair jobs; routing/models/providers adapt cloud and Ollama calls. Runner, evidence, reporting and updates own separate boundaries.
- **Strengths:** atomic validated application, explicit approvals, frozen acceptance/tests, checkpoints, resumable task index and source-bound evidence. Seven cloud providers share authentication and error handling.
- **Weaknesses:** original tasks can ask for controller-owned artifacts despite a general ownership note; repeated whole-project responses waste budget. State-machine orchestration remains large and coupled.
- **Visual quality:** backend facts feed the workflow overview and task receipts; model summaries alone do not establish success.
- **Usability:** a late documentation conflict can block an otherwise saved project. This release adds an explicit final execution brief directing app notes to APP-GUIDE.md while preserving the original task/proposal values. Exact unchanged protected text may be ignored, counted and traced; changed protected files still reject the entire response. This does not prove the historical responses were unchanged echoes.
- **DX:** execution policy lives in `build_contract.py`; response I/O is isolated in `http_io.py`. Existing apply guards remain authoritative. No state migration or new provider is required.

## 2. User Interface & Experience

- **Purpose & scope:** idea entry, review, model choices, build status, verification, manual acceptance and portable files.
- **Strengths:** coherent dark/blue mascot design, mobile layout, semantic controls, actual in-flight model activity, separate verification states and five-stage workflow facts.
- **Weaknesses:** the main script mixes activity polling and project workflow rendering; repeated identical renders replace nodes and can disturb focus. Long provider chains remain cognitively demanding.
- **Visual quality:** retain the existing visual language; clarify the activity legend that green catalogue/response observations are not application verification. No cosmetic redesign is presented as a reliability fix.
- **Usability:** coalesce overlapping workflow requests, abort superseded requests, reject stale project responses and retain DOM nodes when facts have not changed. Existing errors remain visible; an abort is not shown as an outage.
- **DX:** extract `activity.js` and `workflow.js`, explicitly order deferred scripts and serve them through the static allowlist. These remain plain scripts sharing the workbench globals; this is modular separation, not a framework rewrite.

## 3. Developer Productivity & Tooling

- **Purpose & scope:** reproducible local development, fixture coverage, browser checks, typed boundaries and portable packaging.
- **Strengths:** standard-library runtime; cross-platform CI matrix; immutable release artifacts; frozen fixture hashes; extracted-distribution tests and real loopback/browser checks.
- **Weaknesses:** validation commands are scattered; newly added modules can be missed by the typed allowlist. Historical fixtures are evidence of controlled behavior, not live provider benchmarks.
- **Visual quality:** development reports use explicit scopes and outcomes rather than fabricated quality scores.
- **Usability:** `python tools/validate.py` runs the full unit/integration suite; `--types`, `--browser` and `--package` add explicit checks. Optional missing dependencies fail visibly. The tool neither installs dependencies nor publishes releases.
- **DX:** ship the validation tool in the distribution, extend CI's strict type coverage to the I/O boundary and append a version-10 frozen manifest without rewriting earlier fixtures. Updater test versions move ahead of the new release so those tests still exercise a future update.

## 4. System Performance & Efficiency

- **Purpose & scope:** finite model budgets, bounded requests/recovery, memory limits, efficient UI updates and context transmission.
- **Strengths:** serialized model requests, capability-aware output reservations, bounded truncation recovery, explicit context limits and response-size limits.
- **Weaknesses:** socket timeouts alone do not bound total streamed response time; a slow body can keep arriving between socket timeouts. Models were not given the actual remaining merged-project character budget. Batch-labelled candidates were eligible for synchronous routes.
- **Visual quality:** journal records remain observable; no invented speed multiplier or token savings is claimed.
- **Usability:** read response chunks with an elapsed-budget check between reads; retain the 2 MB ceiling and existing transport fallback classification. Exclude explicit `:batch` IDs from discovery/automatic choices. Existing saved routes are not silently rewritten: run automatic setup again to refresh them.
- **DX:** deterministic fake-clock tests cover elapsed reads and size bounds. Supply full-snapshot source/total used and remaining character budgets, distinguish characters from tokens, include the final directive in reservation accounting and prefer changed files/exact edits. Additional instructions cost input tokens; no net token or generation-latency improvement has been measured.

The read guard is **not hard asynchronous cancellation**. Connection/header operations and a blocked read still depend on socket behavior; the deadline is checked after return and may overrun by a socket timeout. No request thread is abandoned to continue spending quota. A future transport replacement needs cancellable I/O tests before stronger promises.

## 5. Usability & Workflow Integration

- **Purpose & scope:** preserve progress from idea through approval, generation, execution, manual observation and ZIP delivery.
- **Strengths:** saved task receipts, private keys outside projects, explicit cloud/runtime consent, backups and evidence linked to the exported snapshot.
- **Weaknesses:** a failed final task can look like a complete-project failure; configuration/catalogue availability can be mistaken for inference health. User code was not available to verify the particular EVE app.
- **Visual quality:** retain a recognizable workbench, clarify the status legend and stabilize workflow panels across polls.
- **Usability:** the controlled unchanged-README case now completes without rewriting protected artifacts. Resume retains saved task progress; verification remains a separate explicit action. Reject changed artifacts rather than silently ignoring a requested change. Do not retry unboundedly or promise that any project will finish.
- **DX:** regressions cover original Unicode/task equality, actual full-snapshot budgeting, wire instructions, successful echo recovery, atomic rejection, body limits/deadlines and synchronous catalogue filtering. Browser checks exercise real generated-app verification and ZIP source hashes, not model self-reports.

## Research used and limits

Primary-source snapshots and hashes are in `research/execution-boundary-sources-0.19.0.json`:

- CPython 3.13 `http.client` and `socket` documentation: incremental response reads and operation timeout semantics informed the bounded reader. A socket timeout is not a whole-job deadline.
- Playwright actionability documentation: observable application states and retrying assertions informed browser checks; arbitrary delays are not readiness evidence.
- OpenRouter's maintained SDK README: provider transport reference only. This audit does not infer current prices, quality rankings or quota from that document. Batch-labelled IDs are excluded conservatively for the synchronous interface.

No new live provider calls, Windows/GPU measurements or paid-model benchmarks were made. Current advertised catalogues remain discovery input, not proof of generation quota, context fidelity or JSON quality.

## Regression before / after

| Controlled failure | v0.18.1 behavior | v0.19.0 behavior |
|---|---|---|
| Valid app change plus exact unchanged protected README echo | Protected-file rejection | Ignore exact echo, apply valid source, count/trace ignored filename |
| Valid app change plus changed protected README | Atomic rejection | Same atomic rejection |
| Slow response delivering bytes within individual socket timeouts | No elapsed check inside the full-body read | Check deadline between incremental reads; transport error when exceeded |
| Explicit `:batch` catalogue entry | Eligible for selection | Excluded from discovered selectable IDs |
| Repeated identical workflow facts | Replace overview nodes | Preserve nodes; concurrent same-project requests coalesce |

These are controlled comparisons, not a measured increase in model repair quality. The earlier user log remains historical failure evidence.

## Validation and next priorities

See `validation-0.19.0.md` for executed checks. Retest the unfinished project with refreshed automatic routes, then resume its saved final task. Priorities after this release: independently evaluate real provider capability/latency, add narrowly scoped task decomposition for projects approaching the source cap, and split orchestration through tested interfaces. Expanded app frameworks and secure live EVE OAuth require their own scoped implementation and verification; they are not delivered by this reliability pass.
