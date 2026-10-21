# v0.29.0 — task recovery and working Follow

## Resume Tiny Wins

1. Use **Update → Check for updates → Install & restart**.
2. Open the existing **Tiny Wins** project. Keep its approved proposal and five saved tasks; do not create a replacement project or approve a different plan.
3. Review the pending task/candidate and choose **Generate / resume code**. The controller first reconciles saved source and task position. A retained candidate still needs static inspection; a saved task is not verified behavior.
4. Open **Dashboard ↗ → Observe workspace**, select Tiny Wins, and keep **Follow activity** checked. The chart follows recorded steps. Uncheck it to inspect manually; recheck to center the latest activity.
5. After generation succeeds, inspect source, choose your execution runtime, explicitly approve execution and run behavioral verification. Run the app and record manual results only after automated checks. Retain the journal if another failure occurs.

## What the supplied journal establishes

Planning completed after v0.28.1: seven features were assigned to nine tasks and the complete proposal was approved. Five tasks were saved; task six retained a candidate but static inspection rejected `urlopen(..., headers=..., method=...)`. Later repair responses were empty or out of scope, and two local models timed out. The app was not verified.

Qwen3.5 completed multiple tasks, but one unmatched exact edit excluded it for the remainder of the job. Source rejections were stored in the same job-level exclusion map used for unavailable models. A separate recent-response status could continue excluding the model for five minutes. Blindly clearing the map would risk restarting failed routes or bypassing account failures.

## Changes

- Structured implementation/static-repair response rejections now use an invocation-local exclusion set. After bounded correction, a rejected model is skipped for that response recovery. A later task or static-repair context can use it again. Content rejection stays visible in model status; authentication/quota, transport circuits and other job-level availability rules retain their distinct handling.
- A failed exact search or empty source change can receive one same-model correction. Exact-search correction requires complete changed files from the approved scope; no guessed edits or widened task files. Invalid Python/scope correction still permits scoped edits. Rejected responses never replace source. An empty response never advances a task.
- Static repair includes named defects, the active task's editable files, explicit output-envelope rules and correct `urllib.request.Request` usage. Metadata such as `source_map` is identified as input, not a filename. This is guidance, not an automatic rewrite or proof a model follows it.
- Existing call and repair allowances, cancellation, frozen checks/tests, source fingerprints, approval, execution/cloud consent and legacy handoff behavior remain enforced. No saved model settings or approved tasks are migrated.
- Follow now centers running activity and completed/failed observed events. It remembers the latest event while disabled or while ELK layout loads, and reacts to repeated events on the same node. Enabling it again catches up. Reduced-motion mode uses immediate centering. History observation does not fabricate transitions or replay old completions as live.
- New `model_request_started` history records expose actual invocation starts to the read-only observer. Starts are activity, not proof of provider receipt, valid generated source or successful tests. Existing request completion records retain results.

## Evidence and limits

The new diagnostic-derived controller tests use mock replies, not captured failed source. Before fixes, the three initial routing/correction tests failed; the missing repair contract and malformed-JSON context tests reproduced separately. Focused recovery/capacity/legacy tests pass after changes. The Chromium regression failed before the Follow patch because the failed model step was not centered. It now checks actual node/canvas geometry, disabled viewport stability, re-enabled catch-up, invocation starts and terminal events.

Full source and extracted-distribution suites, browser workflows, typing and dashboard build/simulation checks are release gates. Results are reported when publication completes. No live-provider repair-quality, Windows GPU speed or arbitrary-project completion claim is made. HTTP 402/429/503, exhausted credits and local socket timeouts remain real external/runtime limitations.

Next measurable gate: resume this exact saved Windows project, retain the pending-task source and journal, then check whether task six passes inspection and the final frozen checks pass. New-plan interface design and live-model performance calibration need their own evidence; this patch does not silently change the approved GET response shape or task scopes.
