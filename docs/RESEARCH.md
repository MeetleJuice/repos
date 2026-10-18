# Research → implementation decisions

Reviewed official repository documentation during this build (2026-10-18). This is a focused
comparison of relevant tools, not a verified market ranking or a hands-on benchmark. Product
claims below come from their documentation; no external project code was installed or executed.

| Source | Documented strengths | What Idea Foundry takes from the pattern |
| --- | --- | --- |
| [Cline](https://github.com/cline/cline/blob/main/README.md) | Plan/Act separation, human approvals, model choices, file diffs/checkpoints, terminal feedback | Separate proposal approval from execution consent; separate planner/coder models; snapshots and visible logs |
| [Aider](https://github.com/Aider-AI/aider/blob/main/README.md) | Repository maps, coordinated edits, Git history, local/cloud models, lint/test feedback | Feed bounded project context into each task; apply complete validated files; repair from actual test output |
| [Bolt.new](https://github.com/stackblitz/bolt.new/blob/main/README.md) | Prompt-to-app experience, execution environment, browser workflow, incremental scaffolding | A simple idea-first browser interface, sequential implementation, downloadable runnable output |
| [OpenHands](https://github.com/OpenHands/OpenHands/blob/main/README.md) | Persistent agent workspace, model/backend flexibility, local and Docker execution | Durable state, resumable tasks, explicit runtime selection and isolated checks |

The current OpenHands README describes Agent Canvas and links its Python agent SDK as a separate
repository. The design above follows the documented patterns rather than assuming a particular
older OpenHands architecture. Roo Code was also checked; its current README reports a shutdown,
so it was not used as the main implementation reference. GPT Pilot was inspected for its
idea-to-project workflow; its current README includes a security incident notice. No code or
dependencies from it were used. These observations are about the inspected documents, not an
independent audit of those products.

The Aider website and OpenRouter documentation site were blocked by this environment's network
policy. Aider's official GitHub README was available instead. We did not inspect private product
internals or claim hands-on tests of their commercial services.

## Why not combine the source code of all four?

Their runtimes, UI stacks, state models, and licenses differ. Combining whole implementations
would introduce a large maintenance surface and make a first Windows/Python version harder
to understand. Idea Foundry implements a small original workflow around the useful principles.

## Decisions for this user's setup

1. Python standard library: no Node toolchain or pip setup for the core application.
2. Ollama-first: planner `qwen3.5:9b`, coder `qwen2.5-coder:7b`, both editable. These are initial
   assignments, not measured superiority claims. Embeddings are unnecessary for small projects.
3. Manual cloud choice: Groq/OpenRouter/Gemini, explicit model IDs, local environment keys,
   explicit acknowledgement of data transfer/costs, no silent escalation.
4. Frozen scope: human-reviewed JSON proposal and machine-readable behavioral HTTP checks.
5. Small sequential work: one model call per task with bounded source context. Parallel agents,
   code indexing/embeddings, and automatic model ranking are deferred.
6. Execution approval: generate first; test only after consent. Docker is the default runtime.
7. Evidence over optimism: generated tests must run; fixed acceptance checks must pass;
   repair attempts stop at the chosen cap; export includes actual status and results.
8. Recovery: atomic state saves, task progress, source snapshots, and manual restore.

## Later, after real-world feedback

- Visual browser tests and screenshots for generated apps.
- Approved iterative feature requests on existing projects.
- Dependency-aware environments and broader frameworks.
- Relevance-based context selection, model success metrics, and user-reviewed routing suggestions.
- Generator improvements proposed as tested patches in a separate copy, with manual approval.

These are future work, not shipped features. The first version improves generated applications
using check results; it does not autonomously modify its own implementation.

## Protocol references

- [Ollama API](https://github.com/ollama/ollama/blob/main/docs/api.md): `/api/tags`, `/api/chat`, non-streaming JSON format.
- [Groq Python SDK documentation](https://github.com/groq/groq-python/blob/main/README.md): chat completions and GROQ_API_KEY.
- [Google GenAI SDK documentation](https://github.com/googleapis/python-genai/blob/main/README.md): API authentication context.
- [Gemini OpenAI compatibility](https://ai.google.dev/gemini-api/docs/openai): adapter endpoint reference; not live-tested here.
- [OpenRouter API overview](https://openrouter.ai/docs/api/reference/overview): adapter endpoint reference; site access blocked here.

The adapter tests check payloads and errors using simulated responses. No live cloud inference
was claimed, and no keys were supplied or needed to build the workbench.
