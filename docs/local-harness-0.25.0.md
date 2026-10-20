# Local harness research and implementation decisions

## Audit
Entry points are Start-Foundry.bat/bootstrap.py and forge/server.py. forge/core.py owns persistent plan/build/verify/repair jobs; forge/models.py adapts providers; forge/routing.py validates explicit bounded routes. forge/focus.py supplies complete-file context and bounded source retrieval. forge/execution.py reconciles source/plan/cursor checkpoints. forge/updates.py checks a fixed GitHub manifest, verifies archive hashes and stages backups before a human-authorized supervised restart.

This is an app-building harness, not a general chat/RAG workspace. Retrieval is project-source retrieval; introducing vector search or a chat agent framework would not address the observed planner budget/configuration failure.

## Research decisions
Official Ollama API documentation describes NDJSON chat streaming, explicit context/output options and structured responses. Its FAQ explains that larger context consumes more memory. llama.cpp documents an OpenAI-compatible server with model discovery, chat completions, response formatting and SSE streaming. LM Studio's SDK documentation confirms a local service and explicit model selection. mini-SWE-agent separates query/action/termination in a small inspectable controller; its shell authority is not appropriate for Foundry's existing source-only generation path.

Use these protocols through the standard library. Do not add runtime SDKs or hard-code speculative model names. Keep model IDs discovered or explicitly entered, local context budgets visible, tool authority limited to existing bounded source retrieval, and completion evidence separate from a model's summary. No published benchmark here proves improved generated-code quality.

Several public documentation sites were inaccessible in this environment; accessible official GitHub source files were used instead. The source register records successful hashes and failures. No claim about universal 2026 UI conventions or a best local model is made. Existing reduced-motion support, progressive disclosure and signature-based status rendering are retained; new UI follows those established repository patterns.

## Evidence boundaries
Streaming previews are incomplete, unvalidated local model output, never saved app files or proof of completion. Stop is cooperative: a blocked socket read must return or time out first. No background inference thread is abandoned. A finish gate proves source/checkpoint consistency only; frozen automated and manual checks remain authoritative. Repetition detection is run-local and bounded; a fresh resumed job has a new allowance.
