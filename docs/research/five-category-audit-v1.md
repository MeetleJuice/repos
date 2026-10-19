# Idea Foundry end-to-end audit — five major categories

Baseline: 8254bb4 / v0.17.0. Reviewed source paths, existing controlled regression evidence and the previous user-reported failures. This is an engineering audit, not live-model benchmarking. The frozen workflow-five-pillars-v1.json declares the synthetic cases before implementation. No real cloud keys were available.

## 1. Setup and model operation

**Purpose:** connect private credentials/local models, choose roles, reserve capacity, route one request at a time, recover from eligible failures and record the actual model.

**Strengths:** provider registry and aliases; private dotenv; catalogues; separate consent; explicit output floors; bounded truncation/format/semantic recovery; recent outcome observation; fallback/cooldown and actual usage metadata. Existing model icons distinguish observed activity from configured state.

**Weaknesses:** server-persisted automatic profiles were not restored to an empty browser profile. Catalogue lists do not prove inference permission or quota. Role heuristics are not quality/cost benchmarks. Context/source limits remain finite, and response-format support varies.

**Appearance/usability:** many advanced choices are available, but novice users should not have to rebuild an already saved route after switching browser. Keep advanced settings optional and status facts specific.

**Productivity change:** return validated automatic profiles with connection metadata and restore them only when browser model settings are absent. Do not overwrite explicit local browser choices; do not send an inference request or grant consent. Existing model-status, routing and hard-budget rules remain authoritative.

**Research:** maintained Hugging Face Inference Providers documentation distinguishes model discovery, routed inference and account access. Discovery cannot be promoted into a generation-success claim. Reuse existing configuration rather than repeat setup or add paid probes.

## 2. Idea, proposal and approval contract

**Purpose:** turn the idea into reviewable scope, tasks and checks, then freeze the user's approval.

**Strengths:** structural and semantic checks; feature-to-task/check indexes; starter/API contracts; bounded proposal correction; immutable approval/checks; browser/manual evidence is distinguished from HTTP delivery.

**Weaknesses:** declared coverage is hard to inspect in raw JSON. A task can mention protected documents without a prominent early reminder of controller ownership. Coverage indexes demonstrate planned coverage, not that implementation exists.

**Appearance/usability:** keep the main next-step controls. Add an optional readable feature map and protected-file advisories, so the review can be understood without editing JSON.

**Productivity change:** deterministic ownership warnings before approval and a declared coverage view. Warnings are advisory: preserve legacy plans verbatim, never remove requirements or silently amend approval. Existing file guards and generation contracts still enforce actual ownership.

**Research:** W3C's disclosure pattern explains optional content that expands without navigating away. Native details/summary provides this interaction without a framework or extra model call. It supports progressively revealing technical details while keeping existing controls usable.

## 3. Generation, change application and recovery

**Purpose:** implement one approved task at a time, validate every response before replacement, checkpoint and resume safely.

**Strengths:** exact edits/full files; path and syntax checks; atomic staging/replacement; protected tests; bounded malformed response correction; controller file ownership; task counter and snapshots.

**Weaknesses:** task-saved history did not say exactly which source files changed. A completed task counter alone is weak evidence: unchanged output may legitimately reuse existing behavior or may represent missed work. Older builds cannot retrospectively supply missing change provenance.

**Appearance/usability:** place concise changed-file receipts beside the existing task workflow. No-op receipts must be visible without pretending they prove a feature works.

**Productivity change:** record before/after implementation fingerprints, changed file names, time, task number, static result and explicit behavior_verified=false after each saved task. Keep unchanged-task warnings, preserve old task counters and checkpoints, and retain original audit events. After restoring an earlier checkpoint, do not show future task receipts as current saved work.

**Research:** CPython os.replace documentation describes atomic rename semantics when successful. Preserve the existing staging architecture rather than weaken it to write partial responses. Hash receipts improve attribution; they do not substitute for tests or demonstrate model quality.

## 4. Verification, acceptance and repair evidence

**Purpose:** separately establish delivered HTTP behavior, collected tests, launch/browser checks and user observations; repair only within the approved allowance.

**Strengths:** independent harness process; environment filtering; process cleanup; test-module collection checks; source fingerprints and bundle manifests; stale-evidence downgrade; manual repair notes and finite global per-job repair cap; environment failures do not spend app-repair requests.

**Weaknesses:** users can confuse static pass with execution or historical manual observations with acceptance of changed code. Availability of optional Docker/Chromium is an environment prerequisite, not proof about the generated app. No tests exhaust every behavior.

**Appearance/usability:** overview states absent/stale automated evidence explicitly and splits current manual passed/failed/pending. It keeps execution and cloud consent separate. It does not run tests merely by opening the view.

**Productivity change:** use the existing evidence_status evaluator as the single source of current verification truth. Stale observations become pending in the overview instead of retaining green-looking counts. Preserve runtime settings and manual/automated separation; no acceptance assertion is weakened.

**Research:** Playwright actionability documentation distinguishes visible/enabled/stable interactive elements from mere HTTP delivery. Keep browser observations separate and test the overview's controls in real Chromium, using controlled provider responses and actual generated-app verification. This is not a live provider quality result.

## 5. Workspace, delivery, backup and updates

**Purpose:** keep files portable and recoverable; export honest evidence; safely distribute validated Foundry releases.

**Strengths:** private workspace separate from program files; migration/lock handling; backups/checkpoints; source-bound export manifests/history; fixed repository updater URLs, checksum checks, safe extraction and immutable versioned ZIPs.

**Weaknesses:** the final handoff mostly requires reading technical JSON. A downloaded ZIP can be mistaken for verified output. LocalStorage's browser/origin/port scope is easy to misunderstand. Workspace backups, release downloads and generated-app ZIPs are separate artifacts.

**Appearance/usability:** keep stable download/backup/update controls; add a plain-text Markdown handoff guide in an export-only metadata folder. The guide explains launch prerequisites, current evidence, next step and data-location caveats.

**Productivity change:** BUILD-REPORT adds optional workflow/receipt/guide fields; the ZIP includes .foundry/DELIVERY.md. Hidden app paths are already forbidden, so this metadata namespace cannot collide with generated app source. It is excluded from the project source manifest, listed as export metadata and never written into the working app. Existing files, frozen checks, report schema and launchers are retained.

**Research:** preserve hash-based evidence and atomic publication controls; W3C disclosure guidance supports a compact overview rather than five new setup screens. No source hashes, updater TLS or extraction checks are bypassed. This pass adds no dependency or provider.

## Research provenance and limits

Official maintained source snapshots fetched 2026-10-19: CPython 3.13 os.rst, Microsoft Playwright actionability.md, W3C disclosure-pattern.html, and Hugging Face Inference Providers index.md. Exact URLs, sizes and SHA-256 values are recorded in five-category-results-v1.json. Existing provider-specific research and source-access limitations remain documented in prior release memos.

No live API quality, billed-cost, native Windows or universal project-completion claim. No vector database, compact handoff serializer, evaluator weakening or autonomous source promotion is introduced. Original request data and approved contracts remain intact. Next useful measurement is consenting, representative live builds with preserved source/evidence and per-model costs; do not infer that result from fixture passes.
