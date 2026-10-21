# Master Diag research and architecture audit

Research date: 2026-10-21. Baseline inspected: v0.30.0, commit `6a4ca4b`.
This is a pre-implementation audit. The release validation record, rather than this
research memo, establishes which new implementation paths passed tests.

## Evidence and access boundary

The public articles requested in the assignment were attempted directly. This
environment refused the OpenAI, Anthropic, Aider, Continue, OpenCode, Cline and
Microsoft documentation-site requests with a proxy tunnel HTTP 403. Those pages
are **not** treated as read or verified. Some guessed current GitHub source paths
returned 404; a missing path is not evidence that the product lacks a feature.

Official repository raw files were accessible. `sources.json` records every
attempt, actual status, retrieval time, byte count and SHA-256 when available.
The downloaded files are research references, not runtime dependencies or source
copied into Foundry. Branch URLs are mutable; hashes identify the bytes examined.
No commercial-model, local-GPU, Windows-shortcut or live-provider benchmark was
performed for this memo.

## Repository discovery

| Component | Confirmed baseline implementation | Gap relevant to this assignment |
|---|---|---|
| Entry and lifecycle | `run.py` selects either `bootstrap.supervise()` or the child server. Bootstrap is standard-library-only and does not import the selected app. | The healthy server's ordinary exceptions and early import/startup failures have no shared persistent diagnostic service. |
| Mission and state | `forge/core.py:Workbench` persists schema-2 state, task cursor, plan approval, source checkpoints, attempts, repair state and evidence. Startup marks interrupted active projects stopped. | A project state snapshot cannot reconstruct an entire previous process or explain missing records. Do not relabel an interrupted task complete. |
| Execution loop | Separate proposal, approval, scoped generation, static inspection, consented runtime verification, bounded repair and manual acceptance. | Diagnostic investigation must observe these controls, not add hidden verification or model calls. |
| History | `forge/history.py` writes attributed JSONL events with UUID, UTC timestamp, run ID, kind, origin and data. Each append flushes/fsyncs. A 16 MB hard cap preserves old data and reports incomplete history. | There is no global startup/update/crash recorder or rotated diagnostic history; an export must disclose legacy gaps and retention. |
| Model integration | `forge/models.py` already captures provider finish reasons, reported tokens, requested budgets and Ollama load/evaluation duration. `core.call_model()` records attempts and routes under limits/consent. | Reuse these observed metrics; do not add duplicate raw responses or claim that an installed model fits GPU memory. |
| Context and edits | Focused task contexts, complete-file manifests, bounded retrieval, exact-edit validation, protected tests and atomic source replacement. | Recording source hashes and names is sufficient by default; request text and code may be private. |
| Verification | `runner.py` executes fixed Python/Docker/browser harness commands with output bounds, subprocess exit results and phase reports. `reporting.evidence_status()` binds results to source, contracts and bundle manifest. | Record failures and phase evidence without running generated code from Diag. Tests absent from a report remain missing, not passed. |
| Dashboard | `ReadOnlyObserver` polls the actual project state and `/history` every 1.5 s. It seeds retained event IDs instead of replaying old completions as live, then maps selected kinds into observed nodes. | It is a sampled projection, not a full event debugger. It can miss intermediate states, has a 4 MB read limit and 10,000-ID observation-session bound. Record gaps honestly. |
| Workspace safety | `storage.workspace_lock()` uses a per-data-home OS file lock; generated paths reject traversal, hidden paths and symlinks. Windows private home is under LocalAppData. | Generated trusted-local execution has the owner's OS privileges. Folder separation alone is not an adversarial sandbox. |
| Updates | Checksummed allowlisted ZIP extraction, staging, project backup, version pointer, pending update and bootstrap health nonce/version test. Failed startup rolls back to the prior pointer. | Validate and retain this recovery path; desktop launch should use a stable supervisor, not a version-specific app path. |
| HTTP boundary | Loopback server validates Host, Origin and session token. Unexpected errors return a generic 500 to avoid exposing internals. | Capture a sanitized exception reference privately rather than losing all evidence behind the generic response. |
| Packaging | `package.py` uses a source allowlist and excludes runtime data, keys, databases and published releases. | Ensure diagnostics and launcher runtime logs are outside distributable source; archive manifest is not a signature. |

## Five-category evaluation

| Category | Purpose and strengths | Weaknesses and proposed improvement | Usability, presentation and developer impact |
|---|---|---|---|
| Core architecture and backend | Durable controller state, deterministic guards, explicit consent and existing attributed traces are a sound integration spine. | Add a bounded global recorder and copy meaningful controller facts into it. Preserve event IDs and project/run correlation. Recorder failure must not change a build result. | One event vocabulary reduces contradictory explanations; a diagnostic summary should link findings back to event IDs. Avoid a replacement agent framework. |
| UI and experience | Workbench already has Update, Dashboard, model status and distinct evidence states. | Add only Diag and Generate Idea. Diag should report what it checked, what it could not check, and what it exported. | Keep technical details in the diagnostic report; button progress and downloadable evidence should be clear, keyboard reachable and responsive. |
| Developer productivity | Standard-library backend, fixture provider adapters, real browser scripts and extracted-release tests are established. | Add frozen failure tests for malformed output, file-write failure, unavailable Ollama, interrupted process and redaction. Add manifest-verification tests. | A START_HERE document plus structured files lets another coding agent investigate without reading an enormous pasted browser page. |
| Performance and efficiency | Sequential inference avoids unnecessary model contention; existing token/time metadata is useful. | Sample resource data slowly, bound subprocess and network reads, rotate stored evidence, avoid provider inference in diagnostic collection. Measure overhead separately from inference. | Report missing hardware counters explicitly. A cloud Linux fixture benchmark is not an RTX 3050 performance result. |
| Workflow integration | Existing update button, portable exports, approvals and manual tests match the owner's workflow. | Bridge Windows evidence to GitHub development through a downloadable diagnostic ZIP. Retain reports after export and provide a local verification procedure. | Do not publish to GitHub or upload telemetry automatically. The owner reviews the ZIP before attaching it. Generate Idea must only edit an empty idea field and remain isolated from active work. |

## Techniques supported by accessible primary sources

### Typed lifecycle records, not transcript accumulation

Codex's official `exec_events.rs` defines typed thread/turn/item start,
completion and failure records, command exit codes, file-change results and
usage. The transferable technique is an inspectable event envelope with stable
identifiers and terminal outcomes. Foundry already has much of this vocabulary:
extend the recorder at existing controller boundaries rather than inventing
unobserved model reasoning. A successful file commit and a failed file write
both deserve a record. A model claim remains attributed model output.

### Deterministic hooks and policy boundaries

Anthropic's official Agent SDK README distinguishes application-invoked hooks
from model-generated behavior and demonstrates pre-tool permission decisions.
It also warns that an auto-approval allowlist is not a tool-removal mechanism.
Foundry should keep diagnostics and policy in controller code outside generated
project directories. Existing cloud/execution approval remains authoritative;
Diag must not silently run user code to investigate it.

### Editing and testing as observable separate stages

Aider's official edit-block source identifies failed SEARCH/REPLACE blocks,
explains mismatches and distinguishes successful blocks from failed ones. Its
lint/test guide relies on commands, output and nonzero exit codes. Foundry
already applies edits atomically and validates scope; keep its stronger all-or-
nothing boundary. Capture rejected edit reason, affected approved task,
operation result and actual verification phase rather than importing Aider's
editing behavior wholesale.

### Model-aware tool shape and explicit modes

Continue's official tool registry selects multi-edit only for recommended agent
models and offers simpler edit/find-and-replace tools otherwise. This supports
measuring model/tool compatibility instead of assuming one universal tool
format. OpenCode's accessible README distinguishes read-only planning from
build access. Cline's accessible README describes plan/act, checkpoints and
lifecycle hooks. These are project descriptions, not independent proof of
reliability; no source-level claim is made for the guessed paths that returned
404. Foundry already has focused contexts and scoped tasks, so the present
upgrade should measure their failure modes before replacing them.

### Local inference timing is available without extra inference

Ollama's official API document defines load, prompt evaluation and generation
durations in nanoseconds, plus prompt and output token counts. Compute tokens/s
only when counts and nonzero duration are actually reported. Foundry already
converts those fields. Reuse them in diagnostics with null for missing values;
do not equate catalogue connectivity, installed context metadata, configured
output budget, inference quota, GPU fit or application success.

### Independent crash evidence

CPython's official `faulthandler` documentation supports early startup enabling
via `-X faulthandler` or an environment flag, plus a file kept open for the
handler lifetime. On Windows it installs a Windows exception handler; arbitrary
signal registration is unavailable there. A supervising process can also record
child startup, exit code, readiness timeout and rollback even if application
imports fail. Neither mechanism records a power loss after the last flush or
proves why an OS killed the process. A previous session with no clean shutdown
is an interruption finding, not a diagnosed crash cause.

## Diagnostic design decisions and threat model

1. Store global evidence under the private data home, outside generated projects.
   Keep the recorder independent from project-model output and do not let
   generated task responses write its location. Reuse controller trace IDs in the
   recorder, so Dashboard history and diagnostic records can be correlated.
2. Use bounded structured records and explicit rotation/retention metadata.
   An exported manifest lists size and digest for each archive member and
   reports missing, partial, pruned or corrupt evidence. Hashes detect accidental
   changes; they are not authenticity proofs against the same OS user.
3. Mask exact configured secrets and aliases, sensitive dictionary keys,
   authorization/bearer values, private-key material and personal path roots.
   Existing `history.redact()` alone is insufficient as a general export policy.
   Include regression cases with inactive/unknown key shapes and nested values.
4. Exclude `.env`, credential files, complete environment dumps, project prompts,
   source bodies, browser storage, model stream previews and raw provider
   responses by default. Summaries, exception classes, sanitized stacks,
   settings, operation outcomes and source hashes are usually sufficient.
5. Treat exception text, generated filenames, test logs and provider model IDs
   as untrusted data. Redaction must happen before persistent recording where
   possible and again at export. Bound fields and nesting. Preserve a record
   that redaction or collection failed without copying the unsafe original.
6. Do not probe cloud generation quota, load extra models, run the generated
   application's tests, inspect unrelated folders or install tooling from Diag.
   Short local metadata reads are appropriate; active inference remains
   serialized. Avoid blocking builds on an expensive health probe.
7. A trusted-local generated program runs with host-user access and can modify
   files outside its folder. A diagnostic directory and hashes are not an OS
   sandbox. Docker's existing isolation is the stronger available boundary;
   explicitly report this limitation instead of claiming tamper-proof logs.
8. Desktop shortcuts should target the stable supervisor and retain the last
   working launcher/application path. The Update button still verifies archives
   before activation and pending health checks still gate success. A browser
   tab is not an owned server-process handle, and closing it need not shut down
   Foundry; document how to stop the managed server cleanly.
9. Optional hardware measurements must distinguish availability and permissions
   from healthy readings. NVIDIA counters may require `nvidia-smi`; missing
   commands are not a GPU fault. Do not infer VRAM from WMI AdapterRAM or label a
   model calibrated merely because it appears in Ollama's catalogue.

## Evidence across the six disciplines

| Discipline | Useful observed evidence | What it does not establish |
|---|---|---|
| Prompt engineering | Role, schema version, input character count/hash, output budget, rejection classification | Hidden reasoning or correctness of a model's answer |
| Context engineering | Included/omitted file manifest, retrieval count, context policy and request identity | Complete context comprehension |
| Harness engineering | Operation/permission outcome, file hashes, environment and runtime availability | Host isolation for trusted-local code |
| Loop engineering | Task/stage transition, retry path, checkpoint, interruption and terminal outcome | That every attempted step completed |
| Evaluation-driven development | Actual commands, exit codes, collected test modules, source-bound check results | Untested requirements or current validity after source drift |
| Behavioral evaluation | Attempt count, observed latency/tokens, correction causes and route use | Counterfactual model quality, billed cost when not reported |

## Verification recommendations and next measured gate

The release tests should demonstrate normal recording/export, recorder restart
persistence, rotation, malformed/partial records, interrupted sessions, independent
child startup failure and nonzero exit, credential exclusion, failed filesystem
writes, trace-ID correlation and exact ZIP-manifest hashes. Generate Idea should
be tested through actual UI interaction with a fixture local client: no project
created, no auto-submit, existing text retained, and failures leave usable input.
Mocked counters test parsing only; real host measurements need separate evidence.

Windows desktop creation, icon association, process behavior and rollback need
an owner-machine checklist. Do not call them tested merely because generated
PowerShell text matches a unit test.

After this release, collect one real failed build and one real successful build
with Master Diag. The next measurable target is: an external developer can
identify the failing stage, exact attempt class, current task scope, source
snapshot and evidence gaps from each ZIP without asking for an API key or a
full browser-page paste. Better evidence is the outcome of this pass; improved
live model repair success requires a separate paired experiment.

