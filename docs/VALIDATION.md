# Validation of this first version

Validated in the provided Linux cloud workspace, using Python 3.12, system Chromium,
Playwright, and Docker. No actual Windows computer, user Ollama server, or paid API
account was accessible. Windows scripts are included; Windows execution remains to
be checked on the user's computer. A Windows/Linux CI matrix is provided but has
not run on GitHub in this workspace.

- 16 standard-library automated tests passed.
- Full HTTP API workflow: proposal → approval → generated source → execution →
  checks → downloadable ZIP with source, documentation, launchers, and a build report.
- A deliberately broken generated task tracker failed its approved retrieval check;
  a scripted repair corrected application code while test files stayed frozen.
- Real generated-app unittest and HTTP checks executed in local subprocesses.
- Docker verification passed: generated unit test, health endpoint, HTML response,
  task creation, task retrieval, and the actual Python launch command.
- Zero-test runs, early zero exits without completion evidence, exhausted repairs,
  missing execution consent, unauthorized HTTP requests, and cross-origin requests
  were rejected rather than reported as success.
- Checkpoint restore, interrupted-job recovery, model-error retry, timeout, and
  cancellation were exercised.
- Browser workflow passed through proposal, approval, generation, failing checks,
  repair, verification, source inspection, and an actual ZIP download. No JavaScript
  errors. Desktop and narrow-screen layout checked.
- `run.py` launched and served the real workbench and authenticated project list.
- Model adapter protocol tests passed using a local simulated Ollama HTTP server
  and simulated cloud replies. They do not establish live inference quality.

Cloud setup and startup instructions were saved as a draft. Saving a draft is separate
from user publication, which has not been performed or verified.

## Follow-up: real user Task Tracker repair

The user uploaded their actual local generated files. They contained an invalid Python else
block, no GET task-list route, incompatible form/JSON submission, shared SQLite cursor state,
and no tests. The approved scope promised six features but its single implementation task
only described the health endpoint. These exposed gaps that scripted first-version responses
did not expose.

The repaired app is shipped in examples/task-tracker with the original approved requirements
and checks preserved. It has 11 behavioral tests covering create/list, completion/reopening,
deletion, persistence after a server restart, concurrent writes, input validation, and safe text.
The browser check also exercises actual add/complete/filter/restart/delete actions.

Generator regressions cover incomplete task/check mapping, one planner correction attempt,
syntax and missing-test detection, adding missing tests without execution, existing test
immutability, and the shared static/runtime repair budget. The combined automated suite has
31 tests. Model responses remain simulated here; the user's uploaded output supplies the
real-world failure example, not a live connection to their Windows Ollama.

Research conclusions are based on official documentation, not hands-on competitive
benchmarking. See RESEARCH.md for sources and scope.
