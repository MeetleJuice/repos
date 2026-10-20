"""Idea Foundry: a local idea-to-app workbench."""

__version__ = "0.26.1"

__release_notes__ = "Local failover fix: Ollama cooldowns are model-specific, so a failed model cannot suppress healthy local alternatives. Local-only runs add detected text/coding backups (up to six automatic choices) without replacing saved primary preferences. Planning failures and rejected code advance through the eligible local route; failing local models are skipped for the rest of that run. The current/last run route is visible. Explicit cloud/mixed routes, approval, frozen checks, output-capacity gates and run limits are preserved. A blocked request must still time out; no live Windows/GPU or universal-completion claim."
