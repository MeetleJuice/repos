# 0.10.0 — Resilient model routes

Open Models, check providers, choose the cloud models and output budgets, and optionally select an installed Ollama coding model as the last resort. Apply to new projects or the current project. Project settings also link to this same setup. Changes preserve approved requirements, saved code and task progress. Cloud consent remains separate and must be confirmed when starting a job.

The route follows Gemini → Groq → OpenRouter → optional Ollama; skipped providers receive no calls. Local fallback is disabled by default. Embedding models are excluded. Applying a local fallback checks that Ollama is reachable and that the model is installed; availability can still change before inference. Saved preferences retain the local selection across restart. To disable it, select “Disabled” and reapply.

Each model is tried once per logical request. Authentication, quota, model access, provider, network, rate-limit and truncated-output failures may hand off to the next configured model. Invalid JSON still uses the existing single correction instead of circulating indefinitely. A stopped job checks cancellation before the next call, but an in-flight non-streaming request must finish or time out first. Each correction is another bounded logical request; total job requests depend on tasks and repairs.

Cloud socket timeout is now 120 seconds rather than 60. This is a socket timeout, not a total wall-clock deadline. Provider calls remain serialized. Rate-limit cooldowns still skip temporarily limited models and record real attempted providers and token usage. No hidden retry or provider is added.

Cloud output budgets now include 16384 tokens; the generated profile uses a 32768 context setting so the same settings validator remains compatible with Ollama. Cloud providers determine their own context limits and may reject unsupported output budgets. The planner remains capped at 4096 output tokens; builder budgets are per provider. Larger budgets can increase cost, latency and memory use. The default remains unchanged.

For a failed existing build, apply the desired route, confirm cloud consent and choose Generate / resume code. Completed tasks are kept. Generation does not execute the app; approve the selected runtime separately for verification. Docker is still optional and local execution is trusted host execution, not a sandbox.

This release improves routing resilience; it does not guarantee that free models produce correct code. Server tests do not prove that browser interactions work. Finish the manual acceptance checklist after running the app.
