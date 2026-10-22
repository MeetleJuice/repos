# Idea Foundry 0.39.0 — a stage-specific planning harness

Diagnostic (11) showed the planner repeatedly losing API/scenario facts between requests. This release gives scope, acceptance and task design their own context packets and retains validated project knowledge between stages. [Evidence, research and limits](research/stage-harness-0.39.md).

## Changes

- **One clear entry point:** **Plan feature by feature →** selects the new workflow and submits your idea. Older proof/builder methods remain under **Other planning methods**. Shape my idea still uses the selected dropdown mode.
- **Appropriate context per stage:** scope defers builder/source detail; acceptance reads the known API registry and exact earlier scenarios; task design receives static interface names/hashes and actual builder constraints. Original requirements and baseline values are preserved.
- **Bound project memory:** validated acceptance prefixes retain API contracts, sample references and request/prefix identities. Resume stops on drift. Memory is unapproved planning data, never a claim that code ran.
- **Less rediscovery:** reviewed starter APIs are declared by the controller. Examples use the starter's real JSON shape, and corrections receive concrete contract feedback. Unknown APIs and contradictory checks still fail review.
- **Explicit browser automation:** UI features use manual checklists by default. The new optional Playwright checkbox permits automated browser checks in a feature-by-feature proposal; it does not approve running generated code.
- **Scoped model failures:** rejection of one feature's content does not automatically exclude that model from later different stages. Existing account controls, transport cooldowns, consent and attempt limits remain.
- **Better budget evidence:** new stage requests use their actual schema in estimates. The output floor remains 8192. Refusals report required/effective context rather than presenting an unexplained list of identical provider names.
- **Stronger Diag:** four new API/scenario guards run without inference. Planning probe version 2 uses the evidence policy and requires a concrete create request and saved-title assertion. Old probe passes are weaker evidence and remain historical results.
- **Reliable Diag reopen:** reopening the panel immediately disables the old download and shows session lookup progress. A delayed status response can no longer leave the previous snapshot labeled ready while a new session is being selected.

No approved plan/check is rewritten. Saved legacy drafts and modes retain their policies. Explicitly choosing the new versioned strategy starts a new unapproved draft and retains the previous draft for inspection. ZIP exports, private keys, provider routes, execution approval and generated-app verification remain compatible.

## Try it

1. **Update → Check for updates → Install & restart**, keeping the Foundry terminal open. Confirm **0.39.0**.
2. Start a **New project**. Explicitly choose your planner and builder; settings on an older project are not necessarily defaults for new projects.
3. Use **Ollama / qwen2.5-coder:7b** for this controlled trial. Keep the planner's currently working 32768 context / 8192 output floor, and builder 16384 context / 4096 output. These are trial settings, not a GPU-fit guarantee.
4. Choose **SQLite collection foundation**, paste the idea below, and click the new **Plan feature by feature →** button. Leave the optional browser-automation checkbox off for this first trial.
5. Watch scope, feature acceptance, project memory and task progress. Only approve a complete proposal whose features/checks match your idea.
6. If it stops, open **Diag**, let the safe checks finish, download the ZIP and send it here. The report now includes memory counts/identities and budget refusals alongside the latest run.

Copyable trial idea:

> Build Tiny Wins, a small local accomplishment journal. Use the selected SQLite foundation and its existing API. One responsive browser page lets me add a win with a title and optional note, then view saved wins. Entries survive page reloads and server restarts. Include meaningful create, read, and restart-persistence checks, plus a manual browser checklist. No accounts, external services, extra packages, search, editing, or deletion.

To run the updated fixed model test, use **Diag → More checks & tools → Also test local planning → Run selected checks & collect**. This does use local inference. Default Diag does not. No project content is sent by fixed probes and no generated app runs during them.

## What the verification proves

The suite checks known-contract reuse without accepting unknown/wrong/missing-body scenarios, exact original values, memory resume/drift, static source indexing, per-stage rejection scope, the unchanged output floor and canonical checks. Browser tests cover the new button through actual SQLite verification, manual browser observations and ZIP export using scripted model responses. Final source/extracted/archive results are in `releases/validation-0.39.0.json`.

These tests do not establish a live-model success rate. The controlled two-feature plan fits 16K with scripted responses, but longer ideas, corrections and prefixes may need more context. Physical Windows/GPU performance and provider quota still require a local run.
