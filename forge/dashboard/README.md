# Execution Observatory — Dashboard 1.0

An isolated full-screen source map for Idea Foundry core 0.26.1. The default mode is an explicitly labeled **simulation**. It is not a live debugger and does not run generated apps.

## Open it

From **v0.27.0**, Dashboard ships in the normal Foundry release. Click **Update → Check for updates → Install & restart** in the workbench. Managed installation requires Foundry to have been started with `Start-Foundry.bat`; follow the existing updater's restart prompt if necessary. Future published releases use the same Update button. Your private workspace and credentials remain in place.

Click the highlighted **Dashboard ↗ button beside Update**. It requests a separate browser window and focuses that window on repeated clicks. If your browser blocks the window, an **Open Dashboard here** link appears beside the button. Browser settings can choose a tab instead. You can also open `/dashboard` on the running Foundry address.

Manual alternative: extract the regular `Idea-Foundry-0.27.0.zip` into a new folder, close the old Foundry terminal and run the new folder's `Start-Foundry.bat`.

1. Choose a journey, such as **Approved project · sequential generation**.
2. Press **Play simulation**. Cyan indicates a running step, green a completed step, and red a simulated failure. Pause/resume, Stop and Tempo control timer playback.
3. Pan/zoom the graph, use Fit, or keep Follow activity enabled. Full map shows every mapped node. All workflows tours every scenario; this can take several minutes even at Fast.
4. Click a node to inspect its source reference. Press `/` to search the process library. Search and area filters affect the library; they do not hide graph nodes. Selecting a process outside the current journey opens the full map.
5. Optionally choose **Observe workspace**, select a saved project, then start/resume that project in the ordinary workbench. This mode reads existing controller history and state snapshots. It never starts work, replays old completions as live, or infers unknown transitions. Stop ends polling. Existing session authorization still applies.

Reduced-motion settings disable the pulse/edge animation; textual status remains available. The graph and inspector remain readable on narrow screens. No sound is added.

## Architecture and scope

`register(Handler)` returns a handler subclass that serves an exact dashboard asset allowlist and adds its own header button plus external launcher script/styles to the root HTML response. This preserves the workbench's existing CSP without inline handlers. Host/Origin checks and all original API methods remain inherited. Dashboard CSS, state, timer engine, worker and React dependencies live here. Runtime Python imports only the standard library; runtime TypeScript imports only this feature and its declared third-party packages.

The runtime registration seam remains:

```diff
--- a/forge/server.py
+++ b/forge/server.py
@@
+    from .dashboard import register; Handler = register(Handler)
     server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
```

Delete `forge/dashboard/` and remove that line to restore the pre-feature runtime. `DASHBOARD_CODEBASE_MAP.md` is a standalone root deliverable with no runtime dependency. The normal release additionally changes core version/release notes, the updater manifest, the packager's root-map allowlist and release guidance in AGENTS.md/README.md, as explicitly requested after the isolated edition. No project, approval contract, frozen check or model route is changed.

## Build and verification

End users need **Python only**. The ZIP includes built JS/CSS and the ELK worker. Node/npm are developer-only requirements (Node 24 is used for TypeScript test execution).

```sh
npm --prefix forge/dashboard run build
npm --prefix forge/dashboard run typecheck
npm --prefix forge/dashboard test
python -m unittest forge.dashboard.test_dashboard -q
python forge/dashboard/browser_check.py
python forge/dashboard/launcher_check.py
python forge/dashboard/removal_check.py
python -m unittest discover -q
```

Build tooling installs exact locked packages in an OS temporary cache, not in the project/workspace. TypeScript checks application source in strict mode; external declaration checking is skipped for the upstream elkjs optional-children declaration defect documented in `docs/RESEARCH.md`. No production dependency is added to the Python app.

Browser checks require the existing optional Playwright/Chromium tools. Simulation tests cover every node/edge, cancellation and failed paths. Launcher checks cover a distinct browser window, reuse, blocked-popup fallback, mobile and unsaved form preservation. Route tests exercise security/allowlists and source excerpts. From v0.28.0 the core has additional authorized upgrades: the removal check snapshots the current packager-allowed core files, removes only the registration and feature in a temporary copy, validates every copied hash, runs the remaining core suite and checks `/dashboard` returns 404. This avoids incorrectly requiring later engine fixes to revert to the historical 0.26.1 source. The historical edition inventory remains unchanged. Test/developer scripts may import existing app modules solely to verify the integration; no such imports are in the runtime feature.

Publish normal releases with the existing `python package.py --release` process after incrementing the core version and completing validation. This writes the versioned archive and `releases/latest.json` used by the Update button. `package_dashboard.py` belongs to the historical standalone 1.0.0 edition; it is not the release path for this or future updates.

## Source and research provenance

See the root `DASHBOARD_CODEBASE_MAP.md` (also served at `/dashboard/map`), `docs/endpoints.json`, `docs/baseline-inventory.json`, `docs/baseline-research.json` and `docs/RESEARCH.md`. `build_graph.py` validates real source needles when regenerating `src/graph.json`. It is a developer tool, not a general-purpose static call-graph analyzer; journeys omit intermediate calls and represent conditional branches as separate scenarios. Source hashes pin this map to the audited baseline. Tests catch stale line excerpts.

No live paid API, Windows GPU or model-quality claims are made by this delivery. Green animation is never used as a substitute for Foundry's real verification.
