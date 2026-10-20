# Task and release completion phase

Scope: task finish receipts, repeated-request limits, bounded optional streaming and update readiness. Approval, source consistency, automated verification and manual acceptance remain different states.

Human gates: approve the proposal before generation; approve the selected runtime before executing generated code; explicitly choose Update installation. Never infer these approvals from a model response.

Done when: frozen and new controller regressions, streamed local generation, real generated-app checks, export, mobile/reduced-motion and updater tests pass; the published manifest/archive pass checksum validation.
