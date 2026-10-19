# Model studio 0.23.0

This release makes applied model routes easier to understand and local-only work easier to start when cloud quota is exhausted. No live API credentials were used in development, no production quota was checked, and no live model quality or GPU-speed gain is claimed.

## Audit and decisions

1. **Model setup:** Automatic modes existed, but local-only was buried in a select. Existing project routes and new-project defaults were difficult to compare. Added explicit local-only and hybrid preset actions and separate route cards. Defaults and the open idle project change only on an explicit apply. The actual planner/builder/fallback IDs are displayed; catalogue availability is not described as generation quota.
2. **Local resilience:** Previously local-only chose one installed model. It now keeps at most two distinct eligible installed models for each role, ranked with the existing deterministic selection policy, tried sequentially under existing capability, truncation and attempt gates. No parallel GPU loading, new provider, lowered output floor or automatic calibration-based promotion. Hybrid/cloud-first ordering is unchanged. A local-only setup with no eligible models reports an actionable local error and preserves previous settings. Vision and embedding entries remain excluded by the existing eligibility filter, which is a naming heuristic rather than a complete capability proof.
3. **Feedback correctness:** Automatic setup now captures the intended project ID, rechecks idle state, and only reports applying to that project if it actually did so. The shared server still rejects setup changes while jobs are running. Preset buttons are disabled together during an in-flight apply. Failed or partial multi-request operations are reported as errors; applying defaults and applying an existing project are separate HTTP operations, not a transaction.
4. **Interface hierarchy:** A studio strip keeps the effective route scope visible. Model studio offers two short presets, then applied routes and customization. Key import, technical fallback explanations, manual controls and comfort settings are native expandable sections. The selected automatic mode is a setup control; route cards describe actual configurations. Existing manual model editing remains available. Both automatic and manual defaults now restore in fresh browser profiles; manual setup is persisted distinctly rather than inheriting a stale local-only mode. Explicit choices already saved in a browser retain priority.
5. **Appearance and accessibility:** Local CSS adds restrained panels, consistent route cards, responsive layout, visible keyboard focus and three accent palettes. Native details elements are keyboard operable. Reduced-motion preferences disable nonessential transitions and animations. No remote fonts or runtime UI library was added. Corrected inherited white backgrounds on the improvement/execution panels so pale text remains readable.
6. **Sound:** Optional synthesized sine cues are off by default, with a persistent browser mute setting, volume slider, and test button. An AudioContext is created/resumed only from a user gesture. A reopened page does not autoplay even when opt-in was saved. Cues follow observed active-to-terminal project transitions, not each provider call or poll. Historical terminal states are silent. Oscillators stop and disconnect; muting suspends the context. Audio failure cannot stop a build. A cue is not verification evidence.

## Research used

The [source register](research/model-studio-sources-0.23.0.json) records retrieved bytes/hashes and one superseded URL that returned HTTPError. Four documents were actually read:

- [Ollama FAQ](https://raw.githubusercontent.com/ollama/ollama/main/docs/faq.mdx): context size and parallelism consume memory; `ollama ps` reports loaded model placement; loading is not a quality or full-project capacity proof. Applied bounded sequential alternatives instead of concurrent local workers. Existing context/output and timeout policy is retained.
- [MDN Web Audio best practices](https://raw.githubusercontent.com/mdn/content/main/files/en-us/web/api/web_audio_api/best_practices/index.md): unlock/resume from a user gesture; provide mute and volume. Applied opt-in audio, no autoplay and failure isolation.
- [MDN details element](https://raw.githubusercontent.com/mdn/content/main/files/en-us/web/html/reference/elements/details/index.md): native disclosure controls can hide secondary information while retaining keyboard interaction. Applied expandable setup and comfort details, retaining all substantive consent and capability disclosures.
- [MDN reduced motion](https://raw.githubusercontent.com/mdn/content/main/files/en-us/web/css/reference/at-rules/@media/prefers-reduced-motion/index.md): respect the device preference for less nonessential animation. Applied a final stylesheet rule including existing working badges.

These are implementation guidance, not comparative app-builder benchmarks. No proprietary competitor code/assets were copied and no claim of exponential improvement is made.

## Preservation and limitations

Approved plans, frozen checks, task scopes, source preservation, user-cloud/runtime approvals and verification truth labels are unchanged. Update alone changes no stored routes or browser preferences. Legacy local-only configurations remain single-model routes until a user reapplies setup. Optional sounds use browser-local preferences, so different ports/browser profiles may have separate preferences.

Local-only work can still stop on insufficient context, unsupported JSON, timeout, syntax, validation or exhausted model attempts. The second model is not guaranteed to repair the first model's output. Two installed models do not prove suitable VRAM or speed. No API quota counters or daily reset times are invented. The user can explicitly return to hybrid after their cloud allowance returns.

Developer housekeeping also makes update/supervisor fixtures derive their next/later version numbers from the running release, retaining available/current/older, backup, integrity and rollback assertions across version bumps. The browser updater check uses the same fixture version rather than an unrelated hardcoded display string.

## Next useful work

Measure representative local-only builds on the user's actual installed models before changing context defaults or ranking. Add searchable catalogue filtering only if the advanced model selector remains a demonstrated usability problem. Keep provider usage/billing integrations optional and evidence-based; catalogue access alone cannot supply a remaining-token meter.
