# Task-loop engineering review

The source audit and controlled red regressions are the release's change evidence. External guidance provides design context, not evidence of Foundry success.

OpenAI's official cookbook `examples/agents_sdk/session_memory.ipynb` discusses bounded context, stable handoffs, observability and the tradeoffs of trimming versus generated summaries. This revision keeps complete selected files, original task/plan values and explicit omission manifests. It does not introduce lossy summaries, hidden context dropping or an Agents SDK dependency. Token ceilings quoted in that tutorial are not imported as current provider capabilities.

Anthropic's official `patterns/agents/README.md` documents chaining, routing, orchestrator/workers and evaluator/optimizer patterns. Its evaluator_optimizer notebook illustrates explicit evaluation criteria and feedback, but also contains an unbounded while loop, model-reported PASS and printed intermediate reasoning. Those examples are not suitable production defaults for Foundry. This revision keeps deterministic execution checks, bounded retries, no raw reasoning capture and source-bound evidence instead of adding another model reviewer.

The structured builder work order uses explicit goal/context/constraints/completion references and existing tool boundaries. It does not change authority: approved task scopes, frozen checks, runtime consent and the controller remain responsible for completion. The fixed JSON-character comparison is only a request-size proxy; live output quality and billed cost remain untested.

The two engineering article pages could not be retrieved in this environment. Their official cookbook counterparts were retrieved and inspected; exact URLs, hashes, byte sizes and failed accesses are in sources.json. No claim relies on an unread article.
