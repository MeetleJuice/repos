# Domain 1 — Harness anatomy and the Foundry control loop

Research date: 2026-10-19. Code inspected at `a2a76074db8c5b59c55c0e2b0de9b8fbb02a8db0` (v0.10.1). This is a source audit and research memo, not a new runtime benchmark.

## Finding

The useful distinction is **model capability versus harness control**. Foundry already has a substantial harness: a persistent, human-approved state machine that supplies context, constrains edits, runs independent checks, records evidence and limits repair. Bigger models do not remove the need for those controls. Its greatest current mismatch is asking a model to invent routine plumbing and then repair it while enforcing a small whole-project source budget. A tested, explicit scaffold can reduce that work without giving models more authority or pretending that successful generation proves correctness.

For this audit, seven responsibilities are a practical decomposition, **not a verified universal taxonomy**:

| Responsibility | Actual Foundry evidence | Gap/opportunity |
|---|---|---|
| Requirements and task contracts | `forge/contracts.py`, `planning.py`, `schemas.py`; approval freezes checks | Structural feature coverage does not establish semantic adequacy; explicit scaffold capabilities can expose unsupported requirements earlier. |
| Context assembly | `forge/context.py`: AST symbol map; planning excerpts default to 8,000 characters | Build/repair still receives small-project source; the 36,000-character source cap also counts tests. Separate predictable scaffold code from model change surface rather than simply enlarging prompts. |
| Model routing | `forge/core.py:130`, `routing.py`, `models.py`; serialized calls, explicit fallback tiers, cooldowns and recorded attempts | Provider availability and response parsing are separate from useful application behavior. Track rejection/repair outcomes alongside actual provider and scaffold version. |
| Edit application | `core.py:578`, `edits.py`; validate paths, frozen files, Python syntax, sizes before staged replacement/checkpoint | Atomic validity is strong; it does not catch API/UI contract mismatches. Scaffold-owned contracts should be independently checked. |
| Execution and observation | `runner.py`, `harness.py`, `browser_runner.py`; independent HTTP, generated-tests, launch and optional browser phases | Current evidence is richer than server health; retain the distinction between delivery checks and gameplay/UI behavior. |
| Repair policy | `core.py:631`; one malformed-response correction, global repair budget 0–3, unchanged-source stop | A rejected edit currently triggers complete-file regeneration, potentially increasing output demand. Templates can reduce necessary edits; evaluation must measure actual recovery rather than merely attempts. |
| Persistence and user authority | `storage.py`, `core.py` checkpoints/manual results, `updates.py`, authenticated `server.py` | Keep old approved plans/projects unchanged; new scaffold metadata must be optional and versioned. No extra execution authority is justified by this work. |

## Authoritative sources actually accessed

1. [SWE-agent repository README](https://raw.githubusercontent.com/SWE-agent/SWE-agent/main/README.md), accessed successfully. Maintainers now recommend mini-SWE-agent; the page links their research and evaluation infrastructure. Its benchmark claims are upstream claims, not measurements of Foundry.
2. [mini-SWE-agent README](https://raw.githubusercontent.com/SWE-agent/mini-swe-agent/main/README.md), accessed successfully. Explicitly separates a small agent class from model, environment and run script; uses a linear trajectory and bash-only interface. This supports keeping orchestration inspectable and measuring it against a baseline. **Do not copy unrestricted bash into Foundry**: its novice-user, Windows and consent constraints differ materially.
3. [OpenHands README](https://raw.githubusercontent.com/All-Hands-AI/OpenHands/main/README.md), accessed successfully. Current Agent Canvas describes distinct frontend/control-center and agent-server/backends, local/VM/container execution, and explicit filesystem-access warnings. Transferable lesson: expose runtime/model/evidence state clearly; backend isolation is distinct from model selection. Its current product description is not a comparative efficacy study.
4. [Anthropic, Building effective agents](https://www.anthropic.com/engineering/building-effective-agents): fetch blocked by this environment's proxy (HTTP 403). Not used as directly verified support here.

The supplied numerical assertion about **11 harnesses, seven subsystems and 18 recommendations** is **unverified**: no identifiable paper/report with title, authors, URL and method was established from accessible sources. These numbers must not appear as measured evidence or a citation-backed consensus. The seven rows above are an engineering organization of inspected Foundry code only.

## Recommended contract and acceptance criteria

Introduce a small, explicit scaffold registry with stable identifiers/versions and declared capabilities (browser CRUD, SQLite, supported endpoint conventions). Reuse reviewed code; let models fill bounded feature changes. Never silently infer a scaffold or overwrite an existing source tree. Existing four starters (`web`, `arcade`, `notes`, `tasks`) in `forge/scaffolds.py` are the natural extension point, not a replacement architecture.

Measure new-project completion without human code edits, first-pass behavioral acceptance, response rejection count, repair count, model requests/tokens, wall time and source size. Compare the same requirement/model/seed fixture on foundation versus scaffold paths; report fixture results separately from live-model trials. Frozen checks, explicit execution consent, deterministic exports, baseline preservation and unchanged legacy loading are non-negotiable parity checks.

Documentation drift found: `docs/ARCHITECTURE.md` still says calls have no automatic provider fallback and later describes a single fallback, while current `core.py` supports configured tiers. Update that description as part of the release; it should describe actual bounded routing, not promise general autonomous agency.
