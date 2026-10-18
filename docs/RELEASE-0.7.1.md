# Idea Foundry 0.7.1 — recover the standard game plan

A real local planner can omit the browser evidence fields even with the 0.7 instructions.
The original integration tests supplied valid browser proposals and did not cover the resulting
empty-plan error page. This patch adds that failure regression and a deterministic way forward.

## Recover your existing failed Neon Dodge project

1. Update → Check for updates → Install & restart. Keep the terminal open.
2. Open the failed Neon Dodge/New project that used the arcade starter.
3. Click **Use standard Neon Dodge plan**. This loads the standard scope without another model
   request. It replaces only the unapproved proposal and preserves your original idea text.
4. Review its scope, localStorage requirement and manual gameplay checks, then approve.
5. Continue normal generation and explicitly approved verification. Loading a plan does not
   generate customized code, run tests or automatically approve execution.

For a new standard game, click Try Neon Dodge and then Use standard Neon Dodge plan in the new
panel. For custom requirements, Shape my idea still asks your selected planner to create a plan.
The standard plan is not a substitute for interpreting arbitrary custom requirements; compare it
with your idea before approval. No automatic standard-plan fallback discards user scope.

## Model path corrections

Native Ollama proposal schemas now require app_kind. The task-tracker example explicitly labels
itself server-side; a complete browser example shows page-delivery checks plus real manual
behavior evidence. Arcade planning supplies explicit required fields and focused feedback if the
model omits browser kind or behavioral evidence. Validation is not weakened to accept page text
as gameplay proof. Non-native and legacy plans keep their structural compatibility.

Standard-plan recovery rejects busy, approved, inherited/change projects and wrong starters.
The normal token/origin checks protect the endpoint. New and recovered proposals remain
unapproved, write no app source and make no model calls. Ordinary custom planning remains the
model path. The existing template installation, generation, consent, verification and exports
continue unchanged after approval. Reports record standard-plan provenance separately.

The failure test starts with a planner that repeatedly omits app_kind/manual_checks, reproduces
an error with no proposal, then recovers the same project in a real browser without inference.
No live model-compliance guarantee or Windows/Ollama execution is claimed.
