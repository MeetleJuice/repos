# Dashboard edition 1.0 — delivery report

Historical report for the standalone Dashboard 1.0.0 edition at commit 0c239b3. Starting in core v0.27.0, the user's subsequent request authorizes normal Update-button releases and a prominent button that opens a separate window. See `../README.md` for current installation, launcher and release instructions. The results and single-existing-line scope below describe the original edition, not the later release metadata or launcher changes.

## Detected stack and audit

Idea Foundry core 0.26.1, commit 531fe15: Python standard-library HTTP server, daemon-thread job controller, explicit file-backed state/history, plain deferred JavaScript/HTML/CSS. No pre-existing React app, JS package manifest, frontend bundler, state store or general tracing/event bus.

All 351 tracked baseline files were read and hash-inventoried (318 UTF-8 text, 33 binaries including old release archives). This is a byte-level inventory, not a claim of manually understanding every historical binary. Deep reads covered server/core/models/providers/cloud/history/execution/guided/planning/workflow/updates/runner, all static JavaScript, HTML/CSS, run/bootstrap/package scripts, repository guidance, tests and research contracts. The complete file list and hashes are in `baseline-inventory.json`. Research sources, retrieval failures, design tradeoffs and validation limits are in `RESEARCH.md` and `baseline-research.json`.

The new, separate frontend uses React Flow 12.12.0, elkjs 0.12.0 and React/React DOM 19.3.1. Strict TypeScript and esbuild are developer-only tools. End-user runtime remains Python with prebuilt local assets.

## Execution map

The root `DASHBOARD_CODEBASE_MAP.md` documents 37 method/path operations and their actual UI callers, session/Host/Origin checks, job state changes, deferred evaluation/DOMContentLoaded/timers, configured provider discovery/inference, update downloads and generated-app acceptance calls. The graph has **245 source-referenced nodes, 371 directed transitions and 156 scenario paths**, including success, rejected requests, model failures, stop and repair journeys. Each node has a real source excerpt/line checked by tests. Paths intentionally elide intermediate calls; they are not stack traces or an assertion of complete runtime instrumentation. Background health polling and inline ZIP downloads are represented as direct fetches, not calls through the JSON wrapper. Rejected background requests do not invent a notice() continuation; that continuation is shown for an actual handle()-wrapped approval action.

Default simulation: timer-driven validated pub/sub, cyan pulsing nodes/animated SVG edges, green completed steps, red failures, pause/resume/Stop, tempo, pan/zoom/Fit, minimap, source inspector and searchable library. ELK runs in a cancellable local worker using top-to-bottom layered layout with ports. All nodes/edges are reachable in the scenario suite.

Optional observation: existing authorized GET endpoints only, retained history seeds a cursor, newly recorded mapped events emit activity, current active-state snapshots glow, and terminal/stopped activity clears. Unknown transitions are not invented. No model requests, job starts, execution approvals or project mutations are issued by the dashboard.

## Exact existing-file diff

```diff
diff --git a/forge/server.py b/forge/server.py
--- a/forge/server.py
+++ b/forge/server.py
@@ -271,6 +271,7 @@ def make_server(port=8765, workbench=None, credentials=None):
             if any(uses_cloud(c) for c in configs) and body.get("cloud_consent") is not True:
                 raise ValueError("Confirm that you allow sending this project's content to the selected cloud providers. API usage may cost money.")

+    from .dashboard import register; Handler = register(Handler)
     server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
     server.daemon_threads = True
     server.workbench = bench
```

No other pre-existing source, UI, test, CI, manifest or build file was modified. The root map, feature directory and separate Dashboard edition ZIP are new. The existing core release and updater manifest stay unchanged. The feature-owned response adapter adds the Dashboard link without editing the original HTML.

## Full feature tree

```text
forge/dashboard/
├── README.md
├── THIRD_PARTY_NOTICES.txt
├── __init__.py
├── assets/
│   ├── app.css
│   ├── app.js
│   ├── app.js.LEGAL.txt
│   └── elk-worker.js
├── browser_check.py
├── build.mjs
├── build_graph.py
├── docs/
│   ├── CODEBASE_MAP.md
│   ├── DELIVERY_REPORT.md
│   ├── RESEARCH.md
│   ├── baseline-inventory.json
│   ├── baseline-research.json
│   └── endpoints.json
├── index.html
├── package-lock.json
├── package.json
├── package_dashboard.py
├── removal_check.py
├── src/
│   ├── App.tsx
│   ├── engine.ts
│   ├── graph.json
│   ├── layout.ts
│   ├── observer.ts
│   ├── styles.css
│   └── types.ts
├── test_dashboard.py
├── tests/
│   └── engine.test.ts
└── tsconfig.json
```

Generated Python caches are not distributed. No node_modules or credentials are packaged.

## Verification evidence

During development the security regression caught an inherited duplicate/stricter CSP, which would reject dashboard inline transforms. The fix is confined to the feature's header adapter; root/API security policies are unchanged.

Before the CSP fix:

```text
$ python -m unittest discover -q
FAIL: test_exact_allowlist_host_guard_and_unchanged_api
AssertionError: "worker-src 'self'" not found in "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
Ran 407 tests in 120.292s
FAILED (failures=1)
```

After the fix:

```text
$ python -m unittest forge.dashboard.test_dashboard -q
Ran 3 tests in 1.059s
OK

$ python -m unittest discover -q
Ran 407 tests in 121.130s
OK

$ npm --prefix forge/dashboard run build
Built local dashboard assets. Dependencies remain in the OS temporary build cache.

$ npm --prefix forge/dashboard run typecheck
> node build.mjs typecheck
[exit 0; no application type errors]

$ npm --prefix forge/dashboard test
tests 4
pass 4
fail 0

$ python forge/dashboard/browser_check.py
PASS: Chromium desktop/mobile; local ELK worker; 245 disjoint HTML nodes / 371 SVG edges; running glow, animated paths, completion/failure, pause/resume/stop, fit/search/source inspector, reduced motion; simulation has no controller calls; observer ignores old history, maps new failure, clears finished activity and cancels polling; no mutations or JS errors.

$ python forge/dashboard/removal_check.py
Ran 404 tests in 118.776s
OK
PASS: all 351 baseline file hashes restored; feature deleted and registration removed in a temporary copy; baseline suite passes; original workbench has no Dashboard link and /dashboard returns 404.
```

The 19 existing browser checks from `tools/validate.py` were also run unchanged (workflow overview, task contracts, hybrid execution, delivery, orchestration, local harness, guided planning, local failover, model studio/activity, automatic routing, proposal import, upgrade, arcade, cloud, provider pool, repair, starter recovery, planning): `PASS: all 19 existing browser checks.` These include fixture-driven generation/verification/export; they are not live-provider benchmarks.

Existing strict Python check, using the already installed temporary mypy 1.18.2 tools:

```text
$ PYTHONPATH=/tmp/foundry-typecheck python -m mypy --strict forge/{contracts,planning,routing,schemas,models,evidence,edits,cloud,credentials,handoffs,capabilities,context,history,reporting,providers,model_status,build_contract,workflow,http_io,tasks,circuit,execution,focus,calibration,streaming,guided}.py
Success: no issues found in 26 source files
```

The system Python did not have mypy on its default import path; the existing isolated installation was used. Third-party elkjs declaration checking is skipped for its documented TS2536 defect; feature application source stays strict. No lint command was present for this isolated new feature; TypeScript strict/noUnused, Python tests and `git diff --check` were used. No test was deleted, skipped or weakened.

## Install and use

Extract `Idea-Foundry-Dashboard-1.0.0.zip` into a new folder, stop the old Foundry terminal, and run the new folder's `Start-Foundry.bat`. Click **Dashboard ↗**, or visit `/dashboard` on the running Foundry address. Select a journey and press **Play simulation**. **Observe workspace** is optional and read-only. Existing project/credential storage stays where it already is.

This edition does not advertise a new core version through Update; changing that existing manifest/version would violate the requested single-line isolation. Remove the feature directory and registration line to restore the prior runtime. The standalone root map may be kept or removed independently.

## Next measurable target

Any future truly instrumented full-call trace needs its own reviewed change boundary: emit correlated start/finish records for a fixed controller path, prove source/job identity and event-loss handling, and measure polling/transport cost. That is deliberately outside this isolated simulation delivery. Live provider quotas, Windows/GPU performance and generation-quality improvements remain untested and are not claimed.
