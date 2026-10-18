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

Research conclusions are based on official documentation, not hands-on competitive
benchmarking. See RESEARCH.md for sources and scope.
