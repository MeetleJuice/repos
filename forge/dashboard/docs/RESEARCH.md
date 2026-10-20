# Research and implementation decisions

Researched 2026-10-20 before implementation, against core 0.26.1 (531fe15). This is an isolated execution **viewer**, not a change to the planner, routing, model quality, task contracts or repair engine.

## Primary evidence

- [ELK upstream README](https://github.com/kieler/elkjs/blob/master/README.md): retrieved and SHA-256 recorded in `baseline-research.json`. ELK computes layout; it does not render a diagram. Its layered algorithm supports directed graphs and ports. The implementation therefore separates worker-side layout from React Flow's HTML/SVG rendering, fixes top/bottom ports, and terminates the worker on completion, cancellation or a 20-second layout deadline.
- [React Flow upstream package README](https://github.com/xyflow/xyflow/tree/main/packages/react): retrieved and hashed. It supplies custom nodes/edges, pan/zoom, controls, a minimap and keyboard accessibility. The actual pinned package types and shipped CSS were inspected to confirm this integration. No undocumented tracing integration is assumed.
- npm registry metadata and the installed packages confirmed exact versions and peer requirements: `@xyflow/react@12.12.0`, `elkjs@0.12.0`, `react@19.3.1`, `react-dom@19.3.1`. React and React DOM are React Flow peers. Only these and their transitive packages enter the runtime bundle. esbuild/TypeScript/@types are isolated developer tooling. Licenses ship in `THIRD_PARTY_NOTICES.txt` and the bundle's legal notices.

The React Flow documentation site and MDN reduced-motion page could not be fetched in this environment; guessed raw documentation URLs also failed. These are explicitly recorded as unavailable, not cited as read. Reduced motion, layout, keyboard focus and responsive behavior are tested in Chromium instead of inferred from inaccessible pages.

## Decisions grounded in this application

The existing application has no React tree, frontend build pipeline, general event bus or complete call trace. Changing every existing function to emit events would violate the requested isolation. The default dashboard is consequently a timer-driven simulation with actual source names and references, as the brief permits. Its pub/sub engine validates node and edge IDs. Scenario paths elide intermediate calls, conditionals and scheduling; they are source-guided journeys, not stack traces. Repeated function nodes may appear in a journey, representing repeated calls to that same source site.

The optional observer reads only existing session/project/history GET endpoints. It seeds its cursor with old history, publishes only newly seen mapped controller records, and separately displays the current active-state snapshot. It does not infer missing calls or their durations. Leaving an active state clears its glow rather than claiming the function completed successfully. Provider errors are rendered from recorded `success:false`, not from animation timing. Unknown record kinds remain unanimated. The observer never starts jobs or calls providers.

The graph includes the 37 controller HTTP operations, static delivery, major job states, core planning/build/verification/repair flows, provider discovery/inference and update/acceptance HTTP families. Dynamic generated-app endpoints are represented by their approved method/path expressions. Hostnames, prompts, private file paths and API key values are never copied from a user's environment into graph data.

## Deliberate safeguards

- Scoped styles and prefixed keyframes; separate document; existing root document/API CSP unchanged. The dashboard's policy permits inline styles because React Flow computes element transforms, while scripts/workers remain same-origin and framing/forms are blocked.
- Worker layout rather than main-thread ELK; exact dependency lock; prebuilt local assets, no CDN, npm or Node required to use the ZIP.
- Bounded journal (60 emitted events), serial 1.5-second observation, cancellation on mode changes/unmount/Stop, 10,000-ID observation bound and explicit oversized-history error. No hidden polling while stopped.
- All nodes/edges have a scenario; tests exhaust the paths. This proves playback reachability, not that every possible production execution has been instrumented.
- Green means a completed displayed step. Only Foundry's existing verification contracts establish project verification. Simulated failures are always labeled simulated.
- `skipLibCheck` is enabled because elkjs 0.12.0's declaration indexes optional `T['children']` and fails strict checking (TS2536). Application source retains strict/noUnused checking. No application errors are suppressed.

## Validation limits

Browser checks use real Chromium and the actual local ELK worker. Controller model replies are fixtures; no paid generation was requested. Windows hardware/GPU performance and live provider quota are untested. This dashboard does not claim to improve model quality or generation latency. The core version and updater manifest are intentionally unchanged: a separate Dashboard edition preserves the single-existing-line change contract.
