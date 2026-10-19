# Scaffold research status — baseline before intervention

Baseline release: **0.10.1**, commit `a2a76074db8c5b59c55c0e2b0de9b8fbb02a8db0`. Research date: 2026-10-19. Six independent research threads completed before application edits. Primary sources and access limits are recorded in each memo. The supplied percentage improvements, eleven-harness taxonomy, stationarity/selfHPO/Ouroboros and iCat/InspectCoder attributions were not authenticated and are not release evidence.

## Six gap assessments

| Domain | Baseline measurement / actual behavior | Verified frontier comparison | Classification and bounded direction |
|---|---|---|---|
| [1 Harness anatomy](research/domain-1.md) | Four reviewed starter families; bounded persistent planner/build/verify/repair state machine; 36K source cap | mini-SWE-agent separates inspectable controller/model/environment; OpenHands separates interface/server/runtime | Contract: cross-stage evidence and scope; capability: richer independently tested starters. Preserve existing controls. |
| [2 Scaffold evolution](research/domain-2.md) | Four static version-1 starters; zero automatic scaffold promotion mechanisms | ADAS explicitly separates candidate proposals and evaluation; DSPy exposes modular optimization | Capability: versioned candidate registry/paired release evidence. Use reviewed commits, never production self-modification. |
| [3 Structured repair](research/domain-3.md) | One malformed-response correction; global 0–3 repair cap; existing structured failure feedback | RepairAgent separates understanding, context and repair states; RepairLLaMA studies representations | Contract: bounded evidence-to-patch handoff; deterministic verifier retains authority. Extra diagnosis calls are hypotheses, not defaults. |
| [4 Context isolation](research/domain-4.md) | Fresh two-message requests; planning 3 prefix excerpts /8K chars; build/repair full source | Official AGENTS.md convention; bounded context must preserve requirements and source identity | Contract: serialization and retained evidence; capability: location-aware retrieval. No vector database or hidden truncation. |
| [5 Verification](research/domain-5.md) | Separate acceptance/tests/launch phases; frozen test hashes; source-bound manual evidence | SWE-bench FULL requires fail-to-pass and pass-to-pass | Contract: defects and regressions must both pass; capability: independent holdouts/mutation checks. Generated tests alone cannot establish correctness. |
| [6 Prompt contract](research/domain-6.md) | PLAN/CODE system prompts; fresh user payload; role schemas; no CLI dispatcher | Official Codex source contains `/goal` and `/compact`; these are harness features | Contract: explicit goal/context/constraints/completion. API model naming does not grant Codex tools. |

## Frozen baseline and evidence boundary

The versioned dataset is `tests/fixture_data/handoff-regressions-v1.json`, frozen SHA-256 `bbd15c652c4c919a51987a25a6a309320204e2e1f4ce62e27b904560744491f7` before prototypes. Eighteen replay cases include Notes/Neon fixture conditions, uploaded dashboard failures, derived existing regressions, and one explicitly synthetic Unicode boundary. They are **not eighteen independent historical failed builds**. Original first-attempt repair outcomes/provider costs are unavailable and remain null. Some fixture failure descriptions localize an observed issue; the replay does not rerun that historical model.

`research/baseline-handoffs.json` records **55,841 normalized input tokens** for this set using pinned tiktoken 0.12.0/cl100k_base. The encoding asset matches OpenAI's published SHA-256. This counts CODE plus serialized payload, excluding provider schemas/chat framing. It is not a billed-token total, a latency benchmark, or a model-quality result. Baseline application suite and existing proposal benchmark are recorded separately; no actual API keys are used.

## Pre-implementation hypotheses and gates

1. **Compact JSON handoff**: change separators only; require exact decoded-payload equality on all cases and a normalized-token reduction. Revert if a payload changes or any applicable regression fails.
2. **Literal Unicode handoff**: avoid ASCII escape expansion while preserving exact JSON round-trip, including non-ASCII source and hostile text. Require equal decoded data and a non-increasing per-case token count, otherwise keep ASCII for that case or reject the prototype.
3. **Structured repair brief**: add a schema-validated goal/context/constraints/done envelope. Measure on the same cases; do not adopt if it increases normalized cost without measured repair improvement. The prototype belongs in the evaluation artifact until it earns promotion.

These gates can establish transport invariants and cost proxies. They cannot satisfy the requested live first-attempt repair-success increase. No such claim will be made without paired provider runs and independently checked repairs. Promotion remains a reviewed release decision; evaluation tooling never edits or promotes Foundry source automatically.

## Paired prototype results and decision

All 18 replay payloads retain exact decoded values/source in the transport prototypes. Counts below are normalized input tokens, not provider billing.

| Prototype | Paired control → candidate | Measured outcome | Production decision |
|---|---:|---|---|
| Compact JSON | 55,841 → 54,165 | −1,676 tokens (3.00%); same decoded payload in 18/18 | **Not promoted**: live repair equivalence unknown. Retained as reproducible prototype. |
| Literal Unicode after compact JSON | 54,165 → 54,089 | −76 tokens; gain comes from one synthetic boundary case | **Not promoted**: no historical-case gain or live repair evidence. |
| Structured repair brief after compact Unicode | 54,089 → 55,205 | +1,116 tokens (2.06%); no observed repair benefit | **Rejected for production**: adds cost without quality evidence. |

The combined transport saving is 3.14% on this set; it is not a claim about billed costs or success. `research/handoff-experiments.json` contains every paired row. The evaluator schema-validates the proposed brief, verifies exact round-trips, pins dataset/encoding SHA-256 values, and never calls a model or promotes code. The production planner/coder deliberately retain the original JSON representation; a regression test asserts this.

The release adds **observational request metrics** (version, character count, digest) to the existing attempt ledger and labels characters separately from provider-reported tokens in the workbench. No prompt text, new authority, context omission, extra model call, evaluator weakening or source auto-modification is introduced. Digest is an identity aid, not a secrecy guarantee. Legacy records without these optional fields still load.

## Durable rules and next audit

Root `AGENTS.md` records condition → prevention rules grounded in the uploaded dashboard corruption and database-test false alarm, plus lossless handoff/frozen-baseline rules. It ships with the source distribution as developer guidance; generated project authority is unchanged.

`research/harness-audit.json` is the independent auditor artifact. Its next single proposal is a preregistered six-case fail-before/pass-after repair trial, baseline/candidate paired, same provider/model settings, one candidate request per condition and independent regression checks (12 calls maximum). No automatic experiment execution or promotion is authorized by that artifact. A developer/user must explicitly choose the provider budget and review the change. Do not solicit API keys in chat.

## Completion boundary

The six memos, frozen replay baseline, three measured prototypes, durable rules and end-cycle auditor artifact are complete. **The requested measurable increase in first-attempt live repair success is not demonstrated.** Missing historical run-level costs and unavailable provider credentials in this cloud checkout prevent a valid reconstruction or paired live trial. Current keys on the user's Windows PC are not accessible here. Unknown results remain null; no successful fixture/round-trip is relabeled as a model-generated repair. Per the requested gate, prompt-policy changes stay unpromoted rather than claiming a frontier improvement.


### Provenance correction without rewriting the frozen comparator

Audit found that `notes-urlopen` pairs a constructed urlopen diagnostic with historical Notes source; that specific diagnostic is not established by the Notes fixture (which imports cgi and duplicates its server). Treat it as a **synthetic diagnostic**, not a historical Notes failure. The frozen input bytes and all paired counts remain unchanged so the comparator is not rewritten after seeing results. Effective provenance is five historical-fixture cases, three uploaded failures, eight derived regressions, one synthetic diagnostic and one synthetic Unicode boundary. The baseline/auditor artifacts record this erratum.


The replay envelopes deliberately reuse a constant task-tracker proposal across varied source/error stress inputs. They are serialization fixtures, **not reconstructions of the original Notes/Neon/dashboard model requests** and not a valid application-repair benchmark. The available uploaded dashboard journal does report an accumulated 35 requests /1,695.2 response seconds and 227,557 input /99,108 output tokens from 21 reporting requests; that aggregate is recorded separately, cannot be allocated to individual repair attempts, and does not establish a first-attempt comparator.

## Priority override: planner truncation reliability fix (0.12.0)

The user's later production log provides a specific blocking failure: Gemini length → smaller OpenRouter free length → generic route exhaustion. This takes priority over the proposed six-case repair-quality pilot. The frozen `planner-truncation-v1.json` and append-only `frozen-regressions-v2.json` manifest record the new controller regression without changing the eighteen serialization inputs.

The narrowly authorized fix reserves planner output and supported thinking separately; classifies `truncated_output`; tries one same-model continuation then one schema-complete shortening; and excludes smaller output ceilings after truncation, including across legacy outer planner fallback. Per-attempt requested/observed output, finish reason and recovery path are recorded. A native Gemini loopback HTTP regression exercises the real adapter and independent proposal consistency review. The approval artifact remains complete: an IDs-only skeleton cannot satisfy the existing required instructions/checks and was not substituted.

`research/planner-truncation-results.json` reports controlled before/after paths and reservations. This is a specific reliability fix, not repair-quality evidence, and does not promote the earlier three prompt-policy prototypes. The next live repair trial remains pending secure provider credentials usable in the cloud environment; keys on the user's Windows Desktop are not available here. No live six-case outcome is claimed.
