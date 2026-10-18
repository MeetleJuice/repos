# Idea Foundry 0.4 — verification grounded in a real failure

The user confirmed that the repaired Notes App works on Windows. This release turns the
original failed generation into regression data for Foundry's engine.

## Changed

- Static inspection detects copied application servers inside tests, missing real-app imports,
  blocking handle_request calls, and cgi/cgitb imports incompatible with newer Python versions.
- Acceptance checks run before generated tests, so a hanging suite cannot hide an app failure.
- Acceptance, tests and launch each run in fresh processes and data directories.
- Served HTML is inspected for local scripts/styles/images, which must be reachable.
- Runtime test instrumentation checks that application functions actually execute during tests.
- New unverified tests can be repaired. Trusted regression tests and inherited baseline tests
  remain protected. Approved acceptance checks are always immutable to the model.
- JSON list-of-object subsets and exact JSON assertions detect API shape mismatches and empty lists.
- UI phase cards distinguish passed, failed and unrun phases. Diagnoses explain missing tables,
  missing assets, test timeouts, non-exercising tests, JSON mismatches and launch failures.

## Evidence and limits

68 automated tests pass from the extracted distribution.

The automated suite includes the exact original Notes App source/test failure as text fixtures.
Its end-to-end repair case uses one controlled model repair reply, executes the repaired app's
12 real tests and unchanged acceptance checks, and verifies that trusted tests become protected.
This demonstrates engine behavior, not live model reliability. Runtime profiling proves that
application code ran, not that all possible behavior was asserted.

The supplied Notes App also passes the new verifier in Docker, including its local asset routes.
Browser automation checks the workbench's existing build/change/backup workflow and phase UI.
Live inference on the user's Windows Ollama and the Windows-specific process paths remain
separate local/CI checks. Model-written code still requires execution consent; local mode is
not a sandbox. This release does not install Docker or silently switch execution modes.

## Update

Use the main README's existing Windows update steps. Version 0.3 user-data locations are
retained. The standalone working Notes App does not need to be replaced to update Foundry.
