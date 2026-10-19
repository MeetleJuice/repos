"""Idea Foundry: a local idea-to-app workbench."""

__version__ = "0.18.1"

__release_notes__ = "Fix Groq HTTP403 caused by the default Python request identity: shared provider HTTP requests now identify IdeaFoundry explicitly. Applies to catalogue checks and inference without changing keys, routes, approvals or project files. Based on a user-confirmed same-key 403/200 comparison."
