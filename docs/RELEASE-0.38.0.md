# Idea Foundry 0.38.0 — one Diag, precise planning evidence

The latest report showed a planning failure before any builder task: six acceptance drafts failed the same assertion requirement, while three timeouts consumed most of the run. This release targets that boundary and makes useful evidence easier to collect. [Research and limits](research/diag-harness-0.38.md).

## Changes

- **One Diag button:** safe checks → visible progress → collection → Download diagnostic ZIP. Separate Test tools remain in **More checks & tools**.
- **Owned snapshots:** closing/reopening rejoins the current session; Stop collects partial evidence; completed evidence persists across restart. Downloads use that exact session and Test result, even if a separate Test runs later. Busy jobs collect passively and disclose skipped checks.
- **Useful model testing:** optional local planning probes exercise the real acceptance prompt/schema, output reservation, compiler and reviewer with fixed synthetic data. Tiny JSON and explicitly consented cloud probes remain available. No app code runs or project content is sent by these probes.
- **New feature planning wire:** one required assertion object replaces the ambiguous mixed optional-field schema in new browser feature-by-feature drafts. Values compile losslessly into the existing approval checks. Corrections use actual target/earlier-check/example fields and specific assertion paths.
- **Better evidence:** assertion presence and validity are separate, schema identity is recorded, and latest planning timeouts/rejections appear even without a proposal. Reports distinguish historical failures, skipped checks, synthetic probes and project execution.

Installing does not rewrite approved projects, frozen checks, routes or saved legacy planning prefixes. Planner output floors and cloud/execution consent remain enforced. No new provider, dependency, extra model reviewer or unbounded retry loop.

## Try it on Windows

1. **Update → Check for updates → Install & restart**. Keep the Foundry terminal open. Confirm **0.38.0** after restart.
2. Open the affected project and click **Diag**. Wait for **Evidence ready**. Default checks do not generate text or run your app.
3. Download the ZIP. It contains `evidence/diagnostic_session.json`, the matching `system_tests.json`, latest planning/build summaries, sanitized recorder/history and a manifest. A stopped/busy report is explicitly partial.
4. To test local planning, expand **More checks & tools**, select **Also test local planning · real acceptance schema**, then **Run selected checks & collect**. This explicitly runs up to two saved local models and may take minutes. A context/output configuration that cannot fit the reservation is reported without a request.
5. After it finishes, download this new snapshot. Send the ZIP here for review. No upload happens automatically.
6. For an end-to-end trial, create a fresh small app, choose the **SQLite collection foundation** and **Feature by feature · local-model option**, review and approve the complete proposal, then generate and explicitly authorize verification. Keep automated pass and your manual observations separate.

Cloud probes require their own checkbox and may incur charges. Generation consent does not authorize execution. Stop is cooperative; it cannot instantly interrupt an in-flight socket read. Probe success is not proof a full project will build.

## Validation and remaining uncertainty

The regression fixture retains the observed diagnostic ledger and labels new assertion cases synthetic; previous frozen sets are unchanged. Tests cover full approval-check parity, correction/resume, actual loopback Ollama HTTP requests, diagnostic ownership/export/restart, stop/busy/consent behavior, privacy and mobile UI. Existing workbench/dashboard checks and extracted-package results are recorded in `releases/validation-0.38.0.json` after validation.

The llama.cpp schema limitation supports simplifying the wire; it does not prove the exact converter in the user's installed Ollama caused all observed rejections. Windows GPU performance, live provider quota and live model-quality improvement require the user's next local run. No success-rate or speedup claim is made from fixture tests.
