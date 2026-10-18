# Executive log — Pass 1

Version: **0.6.0**. Theme: **Contract-aware planning and recovery**.

The core proposal → approval → build → verification workflow remains intact. New deterministic
proposal review catches contradictory API expectations before approval. Correction is bounded
to three requests with at most one explicitly configured fallback. Cloud usage still needs
consent. Model context/output controls, optional native Ollama schemas and actual provider
token reporting make requests easier to inspect and tune. No GPU speedup is claimed.

The verifier now proves persistence across an independent process restart. Existing approved
checks, project directories, backups and standalone exports retain their formats. The existing
top-level Update workflow remains compatible with the published 0.5 launcher.

Validation: 127 tests passed from a freshly extracted distribution, plus browser workflows,
Docker Notes verification and strict type checks for five modules. Both actual bad proposal
fixtures are now rejected; controlled correction recovers within three requests. See
VALIDATION.md and benchmarks/planning-0.6.json for scope and measurement details.

Next pass proposal: context-aware code changes, with relevance-based source selection and
stronger edit contracts. Add an opt-in benchmark on real local models before selecting model
routes based on completion rate, repair counts, tokens and wall time. Broader frameworks and
database migrations remain later work.
