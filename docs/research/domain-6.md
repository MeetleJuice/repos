# Domain 6 — Codex-native prompt contract

Research snapshot: 2026-10-19. Official Codex source inspected at commit `89461ea6833832b0551ce24ee32205824d5c108d`. This is an engineering recommendation, not a live-provider quality benchmark.

## What the official implementation establishes

Codex describes itself as an agentic coding interface whose capabilities come from its harness: workspace context, command/edit tools, planning, permissions, and execution feedback. A system prompt alone does not provide those tools. Its compaction prompt explicitly preserves progress, decisions, constraints, remaining steps, and continuation references. The current CLI source really does declare `/goal` ("set or view the goal for a long-running task") and `/compact`; these are CLI UI capabilities, not text commands automatically understood by Gemini, Groq, OpenRouter, or Ollama. A provider model with “codex” in its name does not establish access to the CLI's session, tool, or goal machinery.

Sources:
- [Official base coding-agent prompt](https://github.com/openai/codex/blob/89461ea6833832b0551ce24ee32205824d5c108d/codex-rs/models-manager/prompt.md).
- [Official compaction handoff contract](https://github.com/openai/codex/blob/89461ea6833832b0551ce24ee32205824d5c108d/codex-rs/prompts/templates/compact/prompt.md).
- [Actual slash-command enum and descriptions](https://github.com/openai/codex/blob/89461ea6833832b0551ce24ee32205824d5c108d/codex-rs/tui/src/slash_command.rs), including `Goal` and `Compact`.
- [Official CLI slash-command documentation](https://developers.openai.com/codex/cli/slash-commands).

## Foundry baseline and gaps

`forge/prompts.py` already separates PLAN and CODE, protects approved requirements/tests, marks source comments as untrusted data, requires small tasks, and forbids unsupported execution claims. `forge/planning.py` provides bounded deterministic proposal review and correction. `forge/core.py::apply` validates paths, owned files, frozen test hashes, Python AST syntax, source budgets, and stages atomic replacement. `generate_and_apply` permits one bounded correction and refreshes current source. These are strong executable contracts worth preserving.

The current `forge/models.py::complete` sends two messages to chat endpoints and returns JSON; it has no terminal tools, Codex SDK session, `/goal` dispatcher, or model-managed compaction. Ollama receives role-specific JSON schemas, while cloud calls request generic `json_object`. PLAN and CODE are lengthy monolithic instructions, with incidental matching of prompt strings used to select schemas. The CODE final-task instruction to deliver *all* approved features can induce a full rewrite despite narrow tasks and the 36,000-character source limit. There is no versioned role envelope or distinct repair/review output contract. A role change must therefore remain backward-compatible with legacy state and adapter behavior.

## Recommended contract and role separation

Use an additive, provider-independent task envelope with `contract_version`, `role`, `goal`, `approved_scope`, `current_task`, `allowed_paths`, `frozen_paths`, `source_fingerprint`, `budget`, `evidence`, and `completion_criteria`. Do not store secrets in it. Select schemas by explicit role/response mode rather than comparing system prompt text. Compile bounded role prompts from shared invariants instead of copying the complete instruction stack into every request.

Roles: **planner** decomposes scope and check coverage; **builder** performs the current task only; **repairer** addresses evidenced failures using minimal changed files; **reviewer** reports contradictions without changing approval; **verifier** is deterministic application code that actually runs checks. Planner/builder self-reports cannot mark verification passed. Preserve the existing edit/file response compatibility rather than requiring every provider to support a new tool protocol.

Completion requires: task artifact validated before replacement; approved checks and frozen regressions preserved; executed checks tied to the exact source fingerprint; pending manual observations shown honestly; runnable/exportable files with no implied execution. Handoffs should persist completed task IDs, failing checks, attempted repairs, decisions, source fingerprint, and next action, not an unconstrained narrative. Resume must revalidate actual source and test evidence rather than trusting the summary. Optional future Codex SDK integration needs separate capability discovery, permissions, sandboxing, and tests; it is not delivered by adding `/goal` to a prompt.
