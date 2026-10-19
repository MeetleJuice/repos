# 0.18.1 — Groq request identity fix

A user-run comparison on Windows used the same private saved key and the same Groq model-list endpoint. Python's default User-Agent returned HTTP403; `IdeaFoundry/0.18 desktop-client` returned HTTP200. This isolates a request-identity-dependent refusal in that environment. It does not identify which gateway component enforced it or prove generation quota.

The shared request_json helper now sends an honest `IdeaFoundry/<version> desktop-client` User-Agent. Both catalogue checks and chat/generation requests use that helper; provider-specific authorization, endpoints, JSON parsing, TLS validation, timeouts and budgets are unchanged. This identifies the actual app, not a spoofed browser. No key replacement, project migration, routing rewrite or acceptance change is needed.

After updating and restarting, open Models → Set up models automatically. This rechecks catalogues and rebuilds the route for new projects and the open idle project, so a previously skipped Groq model can participate. A catalogue pass still does not establish generation quota; later model/quota errors remain separately reported.

The frozen groq-request-identity-v1.json records the user-observed status pair without credentials. A controlled loopback server reproduces default Python HTTP403 and named-app success, then tests authenticated Groq discovery and generation with the shared helper. No real keys were available in the cloud environment, so live verification of the installed patch remains on the user's PC. Existing model settings, approvals, saved tasks and source files are preserved.

Validation: the final extracted package passed 309 automated tests (113.233 seconds). Two cloud/automatic-route browser workflows passed against byte-identical application source. Strict type checks passed for 18 modules. The test-only loopback fixture explicitly bypasses environment proxies, so its controlled HTTP403 cannot be confused with a sandbox proxy refusal. Publication verifies the downloaded release checksum and updater extraction.
