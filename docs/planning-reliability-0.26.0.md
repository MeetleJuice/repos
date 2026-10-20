# 0.26.0 — Planning reliability

This update addresses the uploaded local-planning failure: one 120-second transport error followed by two invalid proposals from the fallback. It does not establish why the local model was slow. No paid provider or Windows GPU benchmark was run. The [research report](research/v0.26/REPORT.md) separates inspected sources, hypotheses and untested claims.

## What to do after updating

1. Save or stop any current run. Use **Update** to install the published release, then restart when prompted. Confirm **0.26.0** in the workspace. Installation preserves the private workspace and keys; a fresh extracted release also uses the configured private workspace.
2. Start Ollama. Keep your explicitly chosen local planner and coding models; this release does not silently migrate existing routes. A discovered model is not a proven fit for the request or GPU.
3. Create a small task-tracker idea. Choose **Small planning steps** and the visible local socket allowance (5 minutes is selected for this explicit mode). For an existing unapproved failed project use **Plan in smaller steps** instead. Cloud routes still need your consent and can incur charges.
4. Watch the saved outline/task-batch progress. You can stop and resume: validated stage results survive. After reopening the browser, select your saved project from the workspace, then use **Resume small-step planning**. A partial response is discarded; the last validated checkpoint remains. Cancellation is cooperative, and a blocked socket must return or time out first.
5. Review the assembled features, ordered tasks, file scope, dependencies and acceptance checks. Approval remains a separate action. A draft is never implementation or behavioral evidence.
6. Approve, generate, then choose an execution runtime and grant execution approval for real checks. Local trusted execution is explicit when Docker is unavailable. Record manual observations only after trying the actual app.
7. Download the app ZIP. Inspect its source, build report and delivery checklist. Verification describes the recorded source snapshot, not any later edits.

## Processing and evidence boundaries

| Stage | Controller action | What it establishes |
|---|---|---|
| Request | Validate idea, model route, context/output settings and relevant cloud consent | Eligible configuration, not model quality |
| Outline (optional new path) | Request complete features and acceptance definitions with native Ollama stage schema | Structurally valid unapproved outline |
| Task batches | Request two feature indexes at a time, with earlier tasks and the complete original request/outline | 1–4 tasks per batch within sixteen total; bounded file scope and earlier dependencies |
| Checkpoint | Save validated outline, tasks, cursor and full-request hash | Resumable draft for the identical request; changing revision restarts |
| Full review | Assemble the ordinary full proposal and apply existing consistency/revision guards | Approval eligibility; approval still requires the user |
| Generation | Install reviewed starter on approval; execute ordered coding calls, inspect candidate files and save checkpoints | Saved source and static receipts, not functioning behavior |
| Static repair | Supply active task packet when repairing a pending versioned task | Out-of-scope writes fail atomically before replacement |
| Verification | Run approved behavioral checks, collected generated tests and launch check in the selected runtime | Source-bound automated evidence; interaction checks remain separate |
| Export | Bundle current source, protected documents/launchers, manifest, history and delivery evidence | Portable app ZIP with accurate evidence state |

The single-pass API default and historical unversioned plans remain supported. Guided plans require task contract version 1; the approval endpoint never accepts an outline. The outline is capped at twelve features and fifteen HTTP checks. Unsupported scope must be explicitly revised, not silently removed. Task batching cannot change the outline's checks. Final consistency review can still reject a semantically contradictory outline after task generation.

The stage prompts are shorter than the full planner prompt, but requests retain the original idea/revision, starter and baseline information. Later batches also receive all earlier tasks. This is not unlimited context: larger requests may still fail reservation and require an explicitly smaller project. The planner output floor remains 8192. Existing truncation recovery, eligible fallback ceilings, planner/shared call limits, repair caps and consent apply to every stage. A longer timeout changes only local calls in the selected planning run; saved model routes and cloud call settings remain unchanged.

## Diagnostics and model settings

Each reviewed attempt now retains sanitized findings and a response SHA-256. Adapter failures retain a sanitized description; known socket/read timeouts and connection failures are distinguished, including a timeout wrapped in urllib's URLError. No load/prefill/decode explanation is invented when a failed request has no Ollama timing. The expandable failure list shows up to six recent retained failures across runs, explicitly historical. Detailed attempt history remains bounded at 100 with cumulative accounting preserved.

Advanced model controls offer 300/600-second socket timeouts alongside existing values. Saving unrelated choices preserves the options of an unchanged single fallback. A different fallback identity does not inherit the former model's options. Automatic pools remain intact until explicitly changed. No model is promoted based on a catalogue response or this fixture test.

Global repairs after all tasks retain the approved project scope; the new active-task guard applies when a pending task exists. It deliberately stops rather than widening that task to write a future task's files. Frozen tests/checks remain protected. A real scope correction requires a newly reviewed plan.

## Research decision

Inspecting source-level harness implementations supported bounded controller loops, explicit context and independently checked completion. It did not prove that framework removal, extra agents or additional reviewer calls improve this app. This release adds no dependency, framework, provider, hidden reviewer or autonomous source-promotion mechanism. No live-model repair-quality or speedup claim is made.

Reproducible checks: `python -m unittest tests.test_guided_planning -q`; `python tools/validate.py --types --browser --package` (optional pinned developer tools described in that script). The release validation record states actual runs separately. Next live target: one schema-valid small proposal and independently tested app on the user's Windows/Ollama machine, recording exact settings and observed timings.
