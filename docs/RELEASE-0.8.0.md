# Idea Foundry 0.8.0 — evidence-driven repairs

This update fixes a workflow gap: a generated browser app could pass its server tests, fail when
you played it, then send you back to planning. Failed checklist items now carry concrete observations
directly into a bounded code repair. Existing projects, frozen plans, tests and backups remain usable.
The update does not automatically replace code in your existing generated games.

## Update and repair your existing shield project

1. Choose **Update → Check for updates → Install & restart**. Keep the launch terminal open.
2. Open the latest shield build. If needed, review and approve execution, then run its automated checks.
3. In **Try the app. Tell us what works**, record each manual result. Beside a failed shield check,
   explain what happened: for example, “I collected the shield, hit one obstacle, and the game ended
   immediately afterward. Pickups are invisible and the shield indicator does not follow my ship.”
4. **Save my test results**. Choose **Repair files only** to generate without execution, or
   **Repair & retest** after selecting your runtime and checking the execution approval box above.
   Choose at least one repair attempt. The same explicit cloud-consent rules apply to cloud models.
5. A repair checkpoint is saved; the coder receives the current source, failed steps, expected behavior
   and your notes. It does not ask the planner to recreate the proposal. After changes, old results
   are cleared and the game must be downloaded, run and checked again. Do not reuse the old extracted
   generated-app folder when assessing a repaired download.

If you only use the existing manual checklist, no new package is required. Your observations are
always labelled user-reported, never converted to passing automated tests. Older saved results still
load; add notes and save them before requesting a repair. Earlier repair observations, their source
fingerprints and whether execution was requested remain in the downloaded BUILD-REPORT.json
(last twenty direct requests). A stopped or unsuccessful attempt is not proof of a fix.

## Precise edits for smaller models

Models may still return complete changed files. They can now instead return:

```json
{"summary":"Remove the collected pickup only","edits":[{"file":"game.js","search":"pickups = pickups.filter((p) => p !== p);","replace":"pickups = pickups.filter((other) => other !== p);"}]}
```

Search text must occur exactly once, including unique context if needed. At most twelve edits apply
sequentially in memory. New files use the existing `files` object; the same file cannot use both forms.
All results pass the existing path, Windows portability, size and frozen-file checks before a
checkpoint and atomic write. Rejected responses still get only one focused format correction.
This precise-edit example alone does not fix missing rendering or the repeat-hit collision bug.

## Repeatable optional browser checks

Browser checks still require an explicitly reviewed proposal, local execution consent and the optional
Playwright/Chromium tooling. Existing manual-only plans are not silently changed. Use the same Python
interpreter as Start-Foundry.bat. On Windows with the Python launcher:

```powershell
py -3 -m pip install playwright==1.56.0
py -3 -m playwright install chromium
```

If launching Foundry with `python` instead, use `python` for both commands. Restart Foundry afterward.
These commands install optional tooling; the app never silently runs them. Clock checks need at least
Playwright 1.45; 1.56.0 is the tested dependency in CI configuration. Browser verification currently
uses trusted local execution, not the standard Docker image. No hosted CI or native Windows run is
claimed by this release's cloud tests.

New approved browser-check fields are `clock: true`, `random_seed` (unsigned 32-bit integer), or
`random_values` (1–256 values in [0,1), final value repeats; choose one random method). `advance_time`
executes 1–10,000 virtual milliseconds per step, with 30 seconds per check and 60 per proposal overall.
`key_down`/`key_up` hold keys, `expect_text_exact` checks the whole DOM value, and
`expect_canvas_still` checks a paused drawing. `wait` and canvas comparisons use virtual time when
clock is enabled. Allow a frame after an action before comparing a newly drawn pause overlay.
Each check uses a fresh page, with only disposable browser storage shared. No arbitrary scripts or
external navigation are accepted. Failures report the check, step, completed actions and random
fixture to the repair loop. Missing tools remain setup failures and cannot be skipped.

See [research and next steps](PASS-3-RESEARCH.md) and [validation](VALIDATION.md).
