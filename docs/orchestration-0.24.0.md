# Orchestrated planning and local delivery — 0.24.0

## User workflow

1. Start Ollama. Open **Models → Cloud plans. Your computer builds.** Setup discovers configured cloud catalogues and installed eligible local text/coding models, then explicitly applies defaults and the open idle project's routes. No generation runs during setup. No eligible local coder means an actionable error before cloud discovery; existing saved profiles remain intact.
2. Create an idea and grant cloud consent for planning. The planner uses cloud providers in saved order, followed by eligible local fallbacks. Default provider order begins Gemini → Groq. Cloud primaries precede alternate cloud IDs, then up to two local models. Setup reads catalogues, not generation quota. Unconfigured/ineligible providers are skipped.
3. Review the actual proposal. Existing task contract v1 retains bounded task scope, declared outcomes, earlier-only dependencies, interfaces and criteria. No unapproved planner output starts implementation.
4. Approve. Foundry installs/reuses the reviewed starter and freezes approved checks. The builder route contains only installed local text/coding models in the new mode; it executes sequentially through the existing controlled file/edit loop.
5. Choose generation only, or select an execution runtime and grant approval for **Build, test & repair**. Generation-only never executes app code. Applicable declared HTTP milestones run during approved execution, then final inspection and the existing HTTP, generated-test, launch and optional browser phases run. Repairs retain the shared 0–3 per-job allowance.
6. Complete any required manual acceptance. Export the app ZIP, which contains launchers, source, reports/history, DELIVERY.md and the new WORK-CHECKLIST.md. Packaging does not confer verification, and the controller does not silently download unfinished output or mark manual checks passed.

## Route semantics

The explicit `orchestrated` mode complements hybrid, cloud-first, local-first and local-only; it does not migrate stored projects. Automatic setup persists the new mode and role routes. Default ranking remains a deterministic name/family preference; no observed benchmark establishes the best local model on the user's hardware. A coding-named model such as qwen2.5-coder is preferred for the builder where installed, with a second eligible local fallback. Two small response-calibration cases are not used to promote a model as best.

Cloud requests in this mode use a 30-second socket timeout; local requests retain 120 seconds. These are not absolute job deadlines. Errors advance through the existing bounded policy without deliberate sleeps. A hanging transport must report an error/timeout before the next call. Truncated output retains bounded same-model recovery and cannot downgrade to a smaller output ceiling, so a low-cap local model is not guaranteed eligible after truncation. Authentication, schema, capability, output and application errors remain distinct; “all cloud models unavailable” does not mean every failure can be solved locally.

Cloud consent for plan/build/repair actions now follows the role actually invoked: planner for planning; coder for building/repair. Each actual cloud call still has its own consent guard. Creation and improvement retain the existing conservative configured-route consent checks. This is not execution approval. A local-only build does not need consent for an unused cloud planner, and the browser hides that irrelevant build checkbox after approval. Cloud-capable builders and planner retries remain guarded; negative API and core tests cover them.

## Shared run allowance

Each new job records `job_max_model_calls`, default 64, API range 1–128. The UI offers 16/32/64/128 for the next run. The guard covers model `complete()` invocations across fallback, coding, retrieval and repair before launching the next invocation. The planner additionally retains its 24-attempt ceiling. Capacity refusals before `complete()` are not billed requests and are not counted as invocations. Provider transports and reported tokens remain separately defined in existing history.

This is not a dollar budget, billed-token cap, daily quota meter or hard wall-clock guarantee. A retry/resume is a new run with its selected allowance. Budget exhaustion preserves already saved source, the task cursor and pending state; resume can continue without regenerating earlier saved tasks. Legacy/direct history with no recorded run allowance remains unknown and is not retroactively capped or displayed as if it had a 64-call policy. Existing counters/history tests remain unchanged.

## Task delivery and context

The task board now presents an outcome, editable paths, dependencies, readable criterion bullets and related approved HTTP/browser/manual check names. Related checks are derived from declared feature overlap; they do not establish a per-criterion executable mapping or semantic correctness. Saved source dependencies still differ from verified behavior; this release does not claim a new verified-dependency contract v2.

Export-only `.foundry/WORK-CHECKLIST.md` records the source SHA-256, saved task/automated/overall acceptance states, sequential outcomes/criteria/check links, latest recorded run allowance and role models. It is listed as export metadata, excluded from the app source manifest and not written into user source. Unverified exports correctly leave verification boxes unchecked.

Focused context now resolves Python package-relative imports, imported local submodules and required package initializers; literal JS imports/requires/dynamic imports, HTML references and CSS URLs can normalize safe parent-relative paths. Query/hash suffixes are ignored for local references. Remote URLs, backslashes and project-root escapes are excluded. Selection only returns existing manifest files and does not execute imports. This remains a best-effort literal dependency map: computed imports, templates and semantic call/data dependencies are not fully analyzed. Full file values, explicit omission manifests, bounded reads and legacy full-context behavior remain intact.

The 36,000 implementation-source and 70,000 total merged-character caps remain. New errors explain that response size and total stored size differ, reject atomically, and do not suggest smaller patches alone can bypass the cap. No approved feature is silently dropped, no scope automatically expands and no new larger-storage profile is claimed.

## Evidence and research

Before implementation, orchestration-v1.json was frozen with synthetic controller scenarios and appended to frozen-regressions-v14.json, retaining previous fixture hashes. The [paired replay](research/orchestration-paired-0.24.0.json) compares the actual checksum-verified v0.23.0 ZIP with this source. [Replay script](research/replay-orchestration.py) accepts either checkout path and runs with fixed replies in disposable directories; it performs no provider inference or generated-app execution.

The replay demonstrates old hybrid placement versus the new explicit route, corrected relative-dependency discovery, and stage-aware local generation. The browser workflow separately executes real generated-app HTTP/milestone/unit/launch checks and downloads the ZIP after controlled cloud failures/local replies. These are controller/verification results, not live model coding-quality, speed or billed-cost measurements.

[Primary-source register](research/orchestration-sources-0.24.0.json) reuses the retrieved 2026-10-19 snapshots: Aider's repository map informs relevant dependency context; mini-SWE-agent informs keeping the loop understandable; LangGraph persistence informs checkpoint/run-state distinctions; Ollama documents resource/concurrency limits; Playwright documents meaningful browser interaction checks. No framework was installed and none of their performance claims are transferred to Foundry.

## Preservation and next work

Approved plans/checks, frozen tests, backups, private credentials, old route modes, source-bound evidence and optional sounds/themes are retained. No Windows/GPU/live-provider quality claim. Future work should independently evaluate representative product tasks, semantic task-check bindings and calibrated capacity profiles before relaxing source limits or making best-model/autonomous-completion promises.
