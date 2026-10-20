# Local runtime phase

Scope: optional loopback OpenAI-compatible discovery/inference, private local credential, explicit persisted role routes and runtime-aware status. Ollama and cloud defaults are not migrated.

Human gate: start the chosen runtime, load a chat/coding model with sufficient context, then explicitly apply its route in Models. This does not approve any project or code execution.

Done when: loopback wire tests, redirect/endpoint/redaction tests and the real model-setup browser flow pass. Fixture responses do not prove model quality or GPU fitness.
