# Idea Foundry 0.7 — blue-flame studio

## Install or update

Use Update → Check for updates → Install & restart from 0.5 or 0.6; keep the terminal open.
Alternatively stop the old terminal, extract this ZIP into a new folder and start
Start-Foundry.bat. Existing Local AppData projects remain in place. Do not overwrite data.
The schema-2 workspace, schema-1 release manifest and stable updater protocol are unchanged.

## First test: Neon Dodge

1. Click Try Neon Dodge on the new-project page. It selects the arcade starter and fills the idea.
2. Choose your local planner and builder, then generate and review the proposal.
3. Check that localStorage is retained, gameplay is listed, and gameplay checks are manual or
   real-browser checks. HTTP page/script checks only prove delivery. Approve when satisfied.
4. Generate files. To execute checks choose Docker if available, or explicitly approve trusted
   local execution after reviewing the source. No automatic switch occurs.
5. Download the app ZIP into a separate folder, extract and launch run.bat. Play the game.
6. Return to Foundry and record every approved manual check as passed or failed. The result is
   labeled user-reported, not automated. All passed makes the project verified; a failure needs
   attention and can be described in a separate improvement proposal.

The tested starter includes keyboard and pointer/touch controls, collisions, score, bounded
increasing difficulty, pause/resume, automatic pause on blur, restart, start/game-over screens,
localStorage high score and storage-failure guidance. No database, pip, CDN or downloaded assets.
Its server serves only intended assets. Selecting the starter installs it only after approval;
existing projects are not converted or overwritten.

## Verification contracts

Legacy plans remain valid. New plans can set app_kind to browser and use manual_checks and/or
browser_checks. Every feature still needs task coverage and explicit combined evidence. Server
apps retain the HTTP behavior requirement; static asset routes cannot masquerade as business logic.
Fresh-data GET checks that expect records created by a later POST are rejected.

manual_checks entries have name, feature_indexes, steps (strings) and expected. They are exported
in MANUAL-CHECKS.md and the frozen proposal. Automated success alone leaves review_required.
Recording results requires successful automated verification of the same source fingerprint.
New writes, restores, forks and verification runs invalidate manual results. Approved baseline
browser/manual checks survive linked improvements; model output cannot edit owned check files.

browser_checks entries have name, feature_indexes and steps. Allowed actions: click, fill, press,
wait (50–2000ms), expect_text, expect_visible, expect_canvas_changes, reload, expect_storage.
Use selector for a CSS locator (or localStorage key), value for text/key/input and ms for waits.
Each check begins at /; storage is shared only inside its disposable profile. Each needs an
expect assertion. No arbitrary evaluation, shell tools, downloads or external navigation steps.
Canvas changes prove rendering activity, not collision correctness. Choose assertions accordingly.

Browser automation is OPTIONAL and currently runs only under explicit trusted local consent.
Install into the Python environment used to start Foundry:

```
python -m pip install playwright
python -m playwright install chromium
```

The runner also detects system Chromium/Chrome on Linux. Restart Foundry after installation and
check Models. If the proposal requires browser tests, missing tooling or choosing Docker blocks
the run before inference; required browser tests never silently skip. Use manual checks instead
in a revised, unapproved proposal when automation isn't available. Existing approved checks
cannot be weakened in place. The core workbench and generated apps do not require Playwright.

Browser tests run in another process and disposable copy after acceptance/tests/launch, with
bounded execution/output, a fresh profile, no inherited API keys, same-origin HTTP routing and
blocked WebSockets/service workers. Trusted local generated code still has host privileges;
this is not a browser/container sandbox. Docker remains the default for Python checks.

## Reliability and interface

A rejected complete-file code response gets one focused correction before the operation stops.
This is separate from the existing 0–3 repair decisions; requests and explicit fallback attempts
are all logged. Invalid file sets never partially land. Provider calls remain serialized.

Failed revisions identify when the page is showing the previous proposal. Technical acceptance
shows all evidence types; browser phases and manual acceptance appear separately in results.
The charcoal/cyan theme uses the supplied mascot's generated adaptation in branding and favicon.
No remote fonts, telemetry or new product dependency is introduced.

See PASS-2-RESEARCH.md and VALIDATION.md for evidence and limitations. No live Windows/Ollama
benchmark, general arbitrary-app guarantee or exponential performance gain is claimed.
