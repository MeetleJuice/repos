# Validation notes — 0.23.0 model studio

## Completed before packaging

- Checkout suite: **350 tests passed in 114.005 seconds** after the manual-route and local-only changes.
- Strict mypy: **24 source modules passed**, including the final cloud setup changes.
- The 14 existing browser workflows passed during development; the updater workflow was rerun successfully after replacing its obsolete fixed future-version expectation. Cloud/provider checks now explicitly open the newly collapsed key section; their failover, consent, source/export and privacy assertions are retained.
- New Chromium model-studio workflow passed: local-only setup makes no cloud catalogue calls; two local attempts produce a valid proposal after a simulated transport failure; reapplying routes preserves the approved plan and files; real generated-app checks and ZIP export pass. Route cards distinguish defaults/current project. Details work with keyboard; mobile has no horizontal overflow; reduced-motion working badges do not animate.
- Actual browser AudioContext checks cover off-by-default, user-gesture unlock, persistence of accent/volume/mute, silent reload and historical terminal states, one cue per observed completion/attention transition, and muted playback refusal. This checks playback machinery, not a human listening assessment.
- A fresh browser profile restores manually saved cloud defaults without generation. Existing browser choices retain priority. Local-only setup without usable models leaves saved settings unchanged.
- Draft ZIP integrity and exact new asset bytes passed; private `.env` and project directories were absent. Four retrieved research source hashes match the register; one failed, superseded URL is retained as an access limitation.

## Final distribution gate

The versioned release must be extracted and tested before publication. The release procedure runs the full unittest suite plus these 15 actual Chromium workflows from the extracted archive: cloud, provider_pool, automatic_routing, model_activity, workflow_overview, task_contract, hybrid_execution, delivery_control, model_studio, arcade, repair, proposal_import, starter_recovery, planning, upgrade. Any failure blocks publication until fixed and rerun. Compare runtime/tests/assets to the checked-out source, validate archive/checksum with the real updater, and confirm the published manifest/archive bytes after pushing.

Commands: `python -m unittest discover -q`; `python tests/browser_<name>_check.py`; `python package.py --release`. `tools/validate.py --package --browser` includes the new model-studio workflow in its normal browser subset.

## Boundaries

All provider inference/discovery responses use controlled fixtures or loopback servers. No live API tokens, provider quotas or billing were consumed or measured. The generated fixture app really runs during verification. Physical Windows 10, the user's GPU/Ollama installation, perceived sound quality and live-provider generation remain untested here. No new model quality, measured billed-token saving, GPU fit, repair-quality gain or universal project-completion claim is made. Approved checks, consent and task contracts remain authoritative.
