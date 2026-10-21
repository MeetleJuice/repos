# v0.30.0 — evidence-ready delivery

Update through **Update → Check for updates → Install & restart**. Keep the Foundry terminal open.

## What to try

Keep the old Tiny Wins project as evidence. Its approved creation check has no request body and its restart check expects empty data. The update does not rewrite frozen checks or relabel saved work as tested. An improvement copy must also preserve its parent checks, so use a **fresh project** to review a replacement contract.

1. Click **New project**, choose **SQLite collection foundation**, and paste the prompt below.
2. Click **Plan with proof →**. This is staged planning with the new evidence_v1 policy. Review the complete proposal before approval.
3. Look for concrete create/read/restart examples, stable API shapes and checkpoints assigned before dependent work. They are declared checks, not execution results.
4. Approve when the plan matches. To test while building, select the intended runtime, explicitly approve execution, keep **Check runnable milestones** enabled and choose **Build, test & repair**. Docker is optional; trusted local execution is a separate choice.
5. Keep Dashboard → Observe workspace open with Follow checked. After automated checks, run the app, perform the manual checklist and save actual observations before exporting.

```text
Build Tiny Wins, a local accomplishment tracker. Reuse the SQLite collection foundation and its existing /api/records API, storage.py and protected foundation tests. Keep its response shapes and database initialization; do not rebuild persistence.
Add a responsive dark interface with warm gold accents: required title, optional note, newest-first list, Today/All time filter, today's count, and deletion after confirmation. Render user text safely with textContent. No accounts, dependencies or external services.
Use concrete sample records in HTTP checks, prove they remain after restart before deleting them, and declare stable API contracts. Assign runnable check prefixes as soon as their declared features are implemented. Separate API inspection/verification from small UI tasks. Include manual browser/mobile checks. Do not claim saved files or model summaries prove behavior.
```

## Changes and limits

- **Plan with proof** is explicit opt-in. Legacy single/guided modes and existing approvals remain compatible. New proof drafts cannot bypass their policy by deleting the flag in the proposal editor.
- The reviewer rejects subsets containing only empty containers, success mutations without example input (unless an intentionally bodyless contract is explicitly explained), ungrounded restart checks, missing successful endpoint contracts and premature/deferred checkpoint declarations. Exact empty results can use `json_equals`.
- Readiness is based on declared feature/task relationships, not inferred code semantics. Real execution can still find defects. Proof-plan execution requires the declared checkpoint option; generating files alone never executes them.
- The new SQLite starter initializes on `create_server`, keeps a stable database path, uses parameterized SQL and closed per-operation connections, returns IDs and row dictionaries, parses filter paths correctly and counts today's entries independently of history. Its protected tests cover CRUD, server recreation, invalid input and literal SQL-like values. Its initial HTML remains a starter page until approved UI work is built.
- Milestone repairs now carry approved task scope into subsequent static corrections. Before verification, the cursor is marked unverified; failure, cancellation or worker exceptions cannot advance to later work. Success restores and seals the cursor.
- No new provider, dependency, automatic model replacement, paid generation or Windows/GPU benchmark is included. Quotas and socket timeouts can still stop a run. The app does not promise arbitrary projects or public-hosting security.

Research, audit and local-model guidance: [report](research/v0.30/REPORT.md). The actual Tiny Wins export is frozen in `tests/fixture_data/tiny-wins-evidence-v1.json`; controlled model fixtures are labeled separately.
