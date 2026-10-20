# 0.26.1 — Local model failover

## Fixed defects

1. The transport circuit was keyed by provider. Two failed Ollama models could open a provider-wide cooldown and skip a healthy third model without calling it. Local runtimes now use provider/model keys; cloud-provider circuits retain their behavior.
2. A saved local primary with no fallback could simply retry itself. The browser's existing local discovery now supplies detected models to the workbench. Each local-only run snapshots a bounded effective route: saved choices first, then eligible detected Ollama models, up to six automatic choices. No model downloads, cloud calls, new configuration fields or primary-preference migrations are needed. Explicit cloud/mixed and LM Studio routes remain unchanged. Existing explicit local lists longer than six are preserved, within the existing sixteen-configuration guard.
3. Source-response recovery stopped after two responses, even with more local models available. Local-only code generation can now advance through its bounded route after rejected source, protecting current source and frozen artifacts before every replacement. Context and invocation limits still apply; this does not increase the 0–3 behavioral repair allowance.

Transport/service/parse/size failures in a pooled local route reject that local model for the current job, preventing later tasks from restarting it immediately. The next run resets that job rejection set; temporary circuit/model-status cooldowns still expire or can be reset through setup. Cancellation remains cooperative. A request that has not failed yet must return or time out before fallback; no hard deadline or immediate cancellation is claimed.

## Scope and controls

Automatic backups use discovered model IDs only, excluding embedding and known vision selections. Unchanged primary options are inherited for added backups, while explicitly configured alternatives retain their options. A discovered model can still be too slow, lack structured-output capability or fail output reservation. Truncation retains bounded recovery and cannot fall back to a smaller output ceiling. Approved plans, source checkpoints, protected tests/checks and all consent boundaries remain unchanged.

The project header shows the current or last prepared local route. Saved model preferences remain visible in the existing model controls. Automatic local setup now includes up to six eligible installed choices per role instead of two; mixed-cloud setup still respects the sixteen-entry route bound. No cloud provider is automatically added to a local-only project.

## Verification

New offline regressions reproduce two transport failures followed by a healthy third model, missing configured backups, per-job failed-model skipping, explicit legacy fallback handling, route filtering/bounds and rejected source reaching a third builder. The existing local-setup assertion was updated from two to three choices because its three eligible installed models are now intentionally included; no test was skipped or weakened.

The new real-browser flow starts a fresh project without opening model setup, fails two planners, accepts the third, rejects two builder responses and accepts the third, runs real generated-app verification, and downloads/inspects the ZIP. Model responses are fixtures; this proves controller failover and actual app verification, not live Ollama/GPU quality or speed. Full-suite, typed-module and extracted-release checks are required before publication. Existing frozen fixture files remain unchanged.

## After updating

Start Ollama, update to **0.26.1**, restart Foundry and select your project. The local catalogue is checked as the browser connects; new project/retry endpoints also refresh it if no models have been detected. Use **Retry proposal**, **Resume small-step planning** or **Generate / resume code**, as appropriate. The header and journal show the prepared models, and the attempt ledger shows which ones actually ran. Keep execution approval separate from generation. If no eligible alternative is installed/detected, the application cannot invent a backup; the header directs you to **Models → Check again**.
