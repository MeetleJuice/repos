# Execution Observatory — Dashboard 1.0

An isolated full-screen source map for Idea Foundry core 0.26.1. The default mode is an explicitly labeled **simulation**. It is not a live debugger and does not run generated apps.

## Open it

Extract the Dashboard edition ZIP into a **new folder**, close the old Foundry terminal, and launch `Start-Foundry.bat` from the new folder. Keep the existing private workspace; this edition does not move projects or credentials. Click **Dashboard ↗** in the workbench header, or open `http://127.0.0.1:8765/dashboard` while Foundry is running. If you launch on another port, use that port instead. Core version still reads **0.26.1** because this edition changes only one existing source line, not version/update metadata.

1. Choose a journey, such as **Approved project · sequential generation**.
2. Press **Play simulation**. Cyan indicates a running step, green a completed step, and red a simulated failure. Pause/resume, Stop and Tempo control timer playback.
3. Pan/zoom the graph, use Fit, or keep Follow activity enabled. Full map shows every mapped node. All workflows tours every scenario; this can take several minutes even at Fast.
4. Click a node to inspect its source reference. Press `/` to search the process library. Search and area filters affect the library; they do not hide graph nodes. Selecting a process outside the current journey opens the full map.
5. Optionally choose **Observe workspace**, select a saved project, then start/resume that project in the ordinary workbench. This mode reads existing controller history and state snapshots. It never starts work, replays old completions as live, or infers unknown transitions. Stop ends polling. Existing session authorization still applies.

Reduced-motion settings disable the pulse/edge animation; textual status remains available. The graph and inspector remain readable on narrow screens. No sound is added.

## Architecture and scope

`register(Handler)` returns a handler subclass that serves an exact dashboard asset allowlist and adds its own header link to the root HTML response. Host/Origin checks and all original API methods remain inherited. Dashboard CSS, state, timer engine, worker and React dependencies live here. Runtime Python imports only the standard library; runtime TypeScript imports only this feature and its declared third-party packages.

The only existing-file edit is:

```diff
--- a/forge/server.py
+++ b/forge/server.py
@@
+    from .dashboard import register; Handler = register(Handler)
     server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
```

Delete `forge/dashboard/` and remove that line to restore the pre-feature runtime. `DASHBOARD_CODEBASE_MAP.md` is a standalone root deliverable with no runtime dependency. No existing project, approval contract, frozen check, model route, updater manifest, build script or UI file is changed.

## Build and verification

End users need **Python only**. The ZIP includes built JS/CSS and the ELK worker. Node/npm are developer-only requirements (Node 24 is used for TypeScript test execution).

```sh
npm --prefix forge/dashboard run build
npm --prefix forge/dashboard run typecheck
npm --prefix forge/dashboard test
python -m unittest forge.dashboard.test_dashboard -q
python forge/dashboard/browser_check.py
python forge/dashboard/removal_check.py
python -m unittest discover -q
```

Build tooling installs exact locked packages in an OS temporary cache, not in the project/workspace. TypeScript checks application source in strict mode; external declaration checking is skipped for the upstream elkjs optional-children declaration defect documented in `docs/RESEARCH.md`. No production dependency is added to the Python app.

Browser checks require the existing optional Playwright/Chromium tools. Simulation tests cover every node/edge, cancellation and failed paths. Route tests exercise security/allowlists and source excerpts. The removal check validates all 351 frozen baseline hashes after removing the one line, deletes the feature in a temporary copy, runs the original suite and checks `/dashboard` returns 404. Test/developer scripts may import existing app modules solely to verify the integration; no such imports are in the runtime feature.

Build the separate archive with `python forge/dashboard/package_dashboard.py`. It invokes the unchanged source packager, adds the standalone root map, and writes an immutable Dashboard edition archive. It deliberately does not update `releases/latest.json` or the core version.

## Source and research provenance

See the root `DASHBOARD_CODEBASE_MAP.md` (also served at `/dashboard/map`), `docs/endpoints.json`, `docs/baseline-inventory.json`, `docs/baseline-research.json` and `docs/RESEARCH.md`. `build_graph.py` validates real source needles when regenerating `src/graph.json`. It is a developer tool, not a general-purpose static call-graph analyzer; journeys omit intermediate calls and represent conditional branches as separate scenarios. Source hashes pin this map to the audited baseline. Tests catch stale line excerpts.

No live paid API, Windows GPU or model-quality claims are made by this delivery. Green animation is never used as a substitute for Foundry's real verification.
