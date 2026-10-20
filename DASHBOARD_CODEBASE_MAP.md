# Application Execution Map — Idea Foundry

Baseline: v0.26.1, commit 531fe15. Inspected before dashboard implementation. All 351 tracked files were read/hash-inventoried (318 UTF-8 text, 33 binary including prior archives); this is not a claim of manually reviewing every archived binary. Deep source reads: forge/server.py, core.py, models.py, cloud.py, providers.py, history.py, execution.py, guided.py, planning.py, workflow.py, updates.py, runner.py, static/index.html and every static JavaScript module; package.py, run.py, bootstrap.py, AGENTS.md and existing tests/research contracts. Source hashes and research access records ship inside the isolated dashboard directory.

## Detected stack and boundaries

Python >=3.11 standard-library ThreadingHTTPServer; no root package.json, workspace manifest, JS lockfile, React router, Redux store or frontend build existed. The current UI is deferred plain JavaScript plus local CSS and HTML. Handler.dispatch routes by method/path; Handler.api dispatches project actions. A daemon thread runs Workbench._job; inference_lock serializes model requests. Session protection is Host/Origin checking plus a per-server X-Foundry-Token from the root HTML meta tag; it is not a user login system. Private dotenv values are not exposed to the dashboard. The dashboard has its own React Flow/ELK build and no imports from these modules.

## HTTP endpoint / frontend trigger / response map

Identifiers below use {id} for the existing project identifier. GET is the api() default; providing a body makes it POST. Downloads and health reconnect use direct fetch instead of JSON api(). There is no WebSocket/SSE event bus in the workbench UI; optional model SSE is server-to-model transport, not a browser activity stream.

| Method + backend path | Frontend trigger and detail | Source | Backend handler / frontend continuation |
|---|---|---|---|
| GET `/api/projects` | listProjects() — workspace list / browser bootstrap | `forge/static/app.js` | Workbench.list_projects() → listProjects() |
| POST `/api/projects` | #idea-form submit — idea-form.onsubmit / create-standard-game | `forge/static/app.js` | Workbench.create() → openProject() |
| GET `/api/projects/{id}` | openProject() / polling interval — openProject / 1800 ms polling | `forge/static/app.js` | Workbench.present() → render() |
| POST `/api/projects/{id}/plan` | #revise / #plan-guided / Retry proposal — job('plan') | `forge/static/app.js` | Workbench.start() → render() |
| POST `/api/projects/{id}/proposal` | #save-proposal-edits — saveReviewedProposal() | `forge/static/app.js` | Workbench.save_proposal() → render() |
| POST `/api/projects/{id}/review` | #review-proposal-button / editor debounce — reviewEditor() | `forge/static/planning.js` | Workbench.review_proposal() → renderProposalReview() |
| POST `/api/projects/{id}/starter-plan` | #recover-standard-game — recover-standard-game.onclick | `forge/static/app.js` | Workbench.load_starter_plan() → render() |
| POST `/api/projects/{id}/approve` | #approve — approve.onclick | `forge/static/app.js` | Workbench.approve() → render() |
| POST `/api/projects/{id}/build` | #generate / #verify — job('build'); execution flag distinguishes generation/verification | `forge/static/app.js` | Workbench.start() → render() |
| POST `/api/projects/{id}/repair` | #repair-manual / #repair-retest — repairManual() → job('repair') | `forge/static/app.js` | Workbench.start() → render() |
| POST `/api/projects/{id}/stop` | #stop / #live-local-stop — stop.onclick; scoped live stop in activity.js | `forge/static/app.js` | Workbench.stop() → render() |
| GET `/api/projects/{id}/workflow` | refreshWorkflow() — render() → refreshWorkflow() | `forge/static/workflow.js` | Workbench.workflow() → refreshWorkflow() DOM updates |
| GET `/api/projects/{id}/history` | #refresh-history / history-details toggle — loadHistory(); download-history reuses same endpoint | `forge/static/app.js` | Workbench.history() → loadHistory() |
| GET `/api/projects/{id}/files` | #refresh-files / Project files tab — loadFiles() | `forge/static/app.js` | Workbench.files() → loadFiles() |
| GET `/api/projects/{id}/download` | #download — download.onclick → fetch / Blob | `forge/static/app.js` | Workbench.export_snapshot() → URL.createObjectURL() |
| GET `/api/projects/{id}/diff` | #review-diff — review-diff.onclick | `forge/static/app.js` | Workbench.diff() → #diff-list.replaceChildren() |
| POST `/api/projects/{id}/manual` | #save-manual — save-manual.onclick | `forge/static/app.js` | Workbench.record_manual() → render() |
| POST `/api/projects/{id}/restore` | checkpoint Restore button — render() creates restore callback | `forge/static/app.js` | Workbench.restore() → render() |
| POST `/api/projects/{id}/models` | #model-form / applyCloud() — model-form.onsubmit; cloud.js applyCloud | `forge/static/app.js` | Workbench.configure_models() → render() |
| POST `/api/projects/{id}/change` | #request-change — request-change.onclick | `forge/static/app.js` | Workbench.fork() → openProject() |
| POST `/api/projects/{id}/resume-baseline` | #adopt-resume — explicit source adoption confirmation | `forge/static/workflow.js` | Workbench.adopt_resume_baseline() → openProject() |
| GET `/api/connections` | #connections-button / Check again / bootstrap — connections() | `forge/static/app.js` | connection_info() → refreshStudio() |
| GET `/api/model-status` | refreshModelStatus() interval — 1000 ms poll; skips hidden page | `forge/static/activity.js` | ModelStatus.snapshot() → refreshModelStatus() |
| POST `/api/cloud/import` | #cloud-env-file change — file import; values stay private | `forge/static/cloud.js` | CredentialStore.import_text() → connections() |
| POST `/api/cloud/reload` | #cloud-reload — cloud-reload.onclick | `forge/static/cloud.js` | CredentialStore.reload() → connections() |
| POST `/api/cloud/check` | #cloud-check — cloud-check.onclick; catalogue only | `forge/static/cloud.js` | CloudSetup.check() → connections() |
| POST `/api/cloud/select` | #cloud-new / #cloud-project — applyCloud() | `forge/static/cloud.js` | CloudSetup.select() → connections() |
| POST `/api/cloud/automatic` | #cloud-auto / #preset-local — setupAutomaticModels() | `forge/static/cloud.js` | CloudSetup.automatic() → connections() |
| POST `/api/local/setup` | #compatible-apply — explicit loopback-compatible setup | `forge/static/cloud.js` | CloudSetup.local_runtime() → connections() |
| POST `/api/local/calibrate` | #calibrate-local — two fixed local response checks | `forge/static/cloud.js` | Workbench.calibrate_local() → connections() |
| GET `/api/info` | #workspace-button / #update-button — workspaceInfo(); updates.js update-button | `forge/static/app.js` | Handler.api(): /api/info → workspaceInfo() |
| GET `/api/insights` | #workspace-button — workspaceInfo() | `forge/static/app.js` | Workbench.insights() → workspaceInfo() |
| GET `/api/backup` | #backup-workspace — saveDownload(); direct fetch | `forge/static/app.js` | Workbench.backup() → saveDownload() |
| GET `/api/updates` | bootstrap / update dialog interval — pollUpdate(); 1200 ms while dialog open | `forge/static/updates.js` | UpdateManager.status() → renderUpdate() |
| POST `/api/updates/check` | #check-update — check-update.onclick | `forge/static/updates.js` | UpdateManager.check() → renderUpdate() |
| POST `/api/updates/install` | #install-update — install-update.onclick; supervised installation | `forge/static/updates.js` | UpdateManager.install() → renderUpdate() |
| GET `/health` | reconnect() / #update-button — fetch /health; reconnect max attempts | `forge/static/updates.js` | Handler.dispatch(): /health → reconnect() |

## Static delivery and navigation

GET / serves static/index.html after substituting __TOKEN__; GET /icon.png serves the existing mascot. GET /app.js, /planning.js, /updates.js, /cloud.js, /activity.js, /workflow.js, /studio.js, /studio.css and /style.css serve local assets. These are browser document/deferred-script/stylesheet loads, not API mutations. tab(name) updates selected/aria-selected and hides proposal/build/files panels; opening files calls loadFiles(). New project clears current, shows create-view and refreshes listProjects(). Dialog showModal()/close() controls models, connections, workspace and updates; they are DOM state, not route transitions. URLs outside the explicit routes return 404.

## Representative complete trace: a proposed idea to an app ZIP

#idea-form.onsubmit → selectedModels()/modelConfig() → api(POST /api/projects) → Handler.check_request() / X-Foundry-Token validation / JSON body and cloud-consent checks → Workbench.create() validates configuration and saves draft → Workbench.start('plan') snapshots run_model_routes and starts _job → queued while inference_lock is occupied, otherwise call_model() → ModelClient.complete() through the selected configured provider → require_consistent() → saved proposed state (unapproved). The browser openProject() reads GET /api/projects/{id}, assigns current and render() displays the plan. Guided mode instead saves an outline and task batches; only the assembled full proposal reaches ordinary approval.

#approve → POST approve → Workbench.approve() freezes the reviewed plan/checks and installs its starter/documents → approved → render()/tab('build'). #generate invokes POST build with execute:false: begin_task / task_packet → focused context → call_model('coder') → response/scope validation → apply() → static inspection/repair within limits → finish_gate / finish_task → next_task advances with source-bound receipts → generated. No generated code has run. #verify posts build with execute:true and explicit runtime/consent: require_runtime → runner.verify() runs approved acceptance, collected tests and launch phases → verified, or review_required if manual interactions remain. Saved failed manual observations can initiate bounded repair/retest. #download uses GET download → export_snapshot() checks actual exported evidence → server builds app ZIP including BUILD-REPORT, RUN-HISTORY and .foundry delivery/checklist metadata → Blob download. A saved task or a successful model reply never establishes behavioral correctness.

## Backend state transitions (real state names / actions)

- create(): status=draft, plan=None, approved=False, next_task=0; start('plan') sets planning; inference_lock contention sets queued and then restores the prior running status.
- _job planning success: state.update(plan=..., status='proposed', plan_review=..., planning_stats=...); failed intermediate guided drafts remain unapproved.
- approve(): approved=True, status=approved; source/checkpoint contracts established. save_proposal(), load_starter_plan(): proposed only, no execution.
- start('build'/'repair'): building; _inspect_and_repair(): repairing or needs_attention; implementation loops set building, update next_task only at finish gates, and end generated when execution is not requested.
- _job verification: checking → verified or review_required; failed checks may transition repairing within approved repair bounds, then checking again; exhausted/blocked checks → needs_attention.
- record_manual(): verified if all accepted, otherwise needs_attention, tied to the verified source.
- stop(): cancel event; _job catches InterruptedError → stopped. Constructor recovery of formerly active work → interrupted. General _job exception → error with a bounded message.
- restore(): approved with checkpoint next_task, invalidated current evidence; source adoption changes resume baseline without approving a plan or marking tests passed. fork(): independent project, original retained.
- ModelStatus.start()/finish()/reject(): working → responded or explicit failure classification, with local circuits keyed by provider/model. Transport/parse/source rejection can advance configured routes; truncation uses bounded recovery and cannot select a smaller output ceiling. These are inference/controller observations, not quality rankings.
- UpdateManager.check(): checking → available/current/error; install(): installing → restarting / failure with backup/rollback safeguards. Installation remains explicit.

## Frontend state transitions and lifecycle touchpoints

- Deferred script evaluation binds existing DOM handlers. app.js initializes const token, activeStatuses, defaults and mutable current/lastPlan/fileCache/polling; no framework mount/unmount lifecycle exists.
- Browser startup runs listProjects(), connections(), initial GET updates and refreshModelStatus(). planning.js/cloud.js/workflow.js DOMContentLoaded listeners construct model controls, protect form validation, bind source adoption and install proposal editor debounce.
- openProject(): current = GET response; resets revision/editor tracking; render() updates badges, steps, task board, run routes, proposal/verification panels and refreshWorkflow(). api() rejection bubbles through handle() → notice(); it does not silently mark success.
- setInterval in app.js polls current active project (1800 ms); polling guard and project identity discard stale overlapping responses, then current changes and render()/listProjects() run.
- refreshWorkflow(): coalesces in-flight reads, rejects wrong-project results and uses a signature to preserve unchanged DOM/focus. Model activity polls 1000 ms, skips hidden/busy polling and only replaces changed icon signatures; optional local stream previews remain unvalidated and source-free.
- Proposal editor input debounces reviewEditor() by 500 ms; sequence/id/editor text checks discard stale review results. Model choices are editable local UI controls; fillModelSettings()/modelConfig() preserve explicit saved options. setupAutomaticModels() applies only after the explicit setup action.
- loadFiles(): assigns fileCache and renders safe text previews; saveDownload()/download handlers create Blob URL, click temporary anchor and revoke it after 1000 ms. Those timers do not run app generation.
- Update dialog starts a 1200-ms status interval, clears it on close/cancel, and disables mutation/close controls while installing. reconnect() polls /health every 1000 ms with at most 60 attempts and boot identity. foundry:update-ready is a real browser CustomEvent emitted by renderUpdate(); it is not a general backend event bus.
- studio.js uses localStorage for appearance/sound choices, pointerdown to unlock optional sound, and observeStudioJob() to avoid replaying historical completion cues. Sounds are muted by default. There are no existing React effects to intercept.

## Backend outbound HTTP calls and callers

- connection_info(): GET OLLAMA_URL/api/tags and loopback LOCAL_API_URL/models. Catalogue discovery is not generation/quota proof.
- CloudSetup._check_provider(): GET each configured provider base/models; Gemini GET https://generativelanguage.googleapis.com/v1beta/models?pageSize=1000; Cloudflare GET account-scoped ai/models/search?task=Text%20Generation&per_page=100; OpenRouter GET https://openrouter.ai/api/v1/key before its catalogue; Hugging Face identity GET https://huggingface.co/api/whoami-v2 before catalogue handling. Base origins are the explicit registry in forge/providers.py (Gemini, Groq, Cloudflare Workers AI, OpenRouter, NVIDIA, Requesty, Hugging Face). Loopback-compatible endpoints use LOCAL_API_URL, falling back to the registry default http://127.0.0.1:1234/v1.
- ModelClient._complete(): POST OLLAMA_URL/api/chat; POST loopback LOCAL_API_URL/chat/completions; POST cloud provider base/chat/completions; native Gemini POST /v1beta/models/{quoted-model}:generateContent. Optional NDJSON/SSE reads are in forge/streaming.py. No keys, account IDs or project prompts are needed in dashboard data.
- UpdateManager.check()/install() via fetch_bytes(): GET fixed repository releases/latest.json, then the manifest's versioned releases/Idea-Foundry-{version}.zip; checksum/version/path validation precedes extraction/installation.
- runner._execute() launches harness.py; its acceptance()/fetch() and browser_runner make generated-app HTTP requests described by approved checks. These are variable approved methods/paths against an ephemeral local app, not Foundry API routes. Docker execution requires Docker and its image; it is never inferred from HTTP delivery alone.

## Feature isolation, simulation and verification plan

Only one server registration line will adapt Handler. The feature directory contains local assets, React components/types, source-derived graph, ELK layout and a timer-based pub/sub engine. The workbench receives a feature-owned Dashboard link; no shared state, model routing, project logic or existing API client will be edited. The dashboard defaults to explicitly labeled simulation and does not issue mutation calls. An optional read-only observer may use existing project/history/model-status GET endpoints; polling snapshots are not complete traces. Every flow includes source references and simulated failures remain labeled.

Build: npm --prefix forge/dashboard run build. Typecheck: npm --prefix forge/dashboard run typecheck (developer dependencies only). Runtime assets are prebuilt and local; Windows users need neither Node nor npm. Repository baseline gate: python -m unittest discover -q. New tests live inside the removable feature directory so removal adds no dangling test imports. Deleting forge/dashboard and reverting the single registration line restores all pre-existing tracked file bytes. The root execution map is a deliverable, not an injected app dependency.

Release boundary: the brief permits only a route-registration edit to existing files. Accordingly this delivery will provide an isolated dashboard ZIP without changing the core version, existing updater manifest or previously published immutable release. A future updater version bump is a separate metadata change outside that explicit restriction.
