# Idea Foundry 0.9.0 — cloud-first studio

## Start with your Desktop Notepad file

1. Update → Check for updates → Install & restart. Keep the launch terminal open.
2. Click **Models** in the top bar. Under Cloud-first studio, choose your Desktop key file.
   `.env` and `.env.txt` are accepted; you do not need to rename a hidden Windows extension.
   UTF-8 and Notepad UTF-16 are supported. Never paste keys into chat, ideas, model IDs or GitHub.
3. Confirm the detected-key count, then click **Check cloud providers**. This makes read-only
   model-list requests and an authenticated OpenRouter current-key metadata check. It sends no
   project content and makes no inference request. OpenRouter's public model list alone is not
   treated as proof that its key works.
4. Review the returned model choices. Defaults are chosen only if listed by the provider.
   Choose output limits for each provider; Groq defaults to 4096 tokens. Smaller limits can help
   some quotas but may truncate a full proposal or source file. Input-token limits still apply.
5. Choose **Use cloud for new projects**, or open your existing project and choose
   **Use cloud for this project**. This saves model settings; it does not generate or execute code.
6. When starting a proposal, build or repair, check the cloud-use consent box. Execution approval
   remains separate. Your normal checkpoints, frozen checks and manual acceptance still apply.

The expected entries are GEMINI_API_KEY, GROQ_API_KEY and OPENROUTER_API_KEY. OPENROUTER_KEY is
also recognized. Missing providers can be skipped. A bad key or inaccessible catalogue is shown
as a failed check, not a verified connection. A selected provider may still hit a generation quota.
This release does not promise that all free APIs are always available or that every generated app
will work. Current account/model access must be checked locally.

## Where your .env lives

The importer copies recognized keys to **the exact private workspace path shown in Models**,
normally `%LOCALAPPDATA%\IdeaFoundry\.env` on Windows. It leaves your Desktop original in place.
That workspace location survives program updates. If you later edit the Desktop original, import
it again. If you edit an already loaded local .env, choose **Reload local .env**, then check providers.

At startup, nonempty process environment bindings take precedence, then the workspace .env, the
running program's .env and the original launcher folder's .env. Imported keys explicitly replace
those selected keys for this session and persist in the workspace for restart. Loaded file paths,
key-presence flags and .env.txt/format warnings are visible; key values are never returned. Existing unknown
entries in the workspace file are preserved; unknown variables in an imported file are ignored.
A malformed or unreadable local key file is skipped with a visible warning so the studio can
still start. Import/reload/check/profile changes are blocked while jobs run. No shell code or interpolation in
an environment file is executed. Local authentication/origin checks protect the import endpoint.

Project backups and app ZIPs exclude .env keys. Keep your key file separately; new-project browser
preferences are local to that browser. Projects store their own model route. Provider IDs/limits
are also saved without secrets in cloud-models.json. Discovery must be checked again after restart
before applying a fresh cloud profile. Existing saved project routes can run directly with consent.

## How the route works

Selected available providers are ordered Gemini → Groq → OpenRouter. If only Groq and OpenRouter
are selected, Groq becomes primary. Authentication, service, timeout/connection, rate-limit, quota
or unavailable-model failures move to the next configured tier. Each provider is attempted once
per inference operation. All tiers failing stops clearly. Temporary rate-limit cooldowns avoid
immediately hammering the same provider/model. Cancel prevents starting the next tier.

Malformed generated JSON uses the bounded response-correction process. Truncated output needs
more output budget or smaller scope. Failing application tests use bounded repair. These paths
retain the existing safety checks and do not silently weaken acceptance. Planning still has up to
three candidate/correction operations, each with at most three provider attempts. An exhausted
service route is not automatically repeated by that planning loop.

The build journal records routing failures and actual fallback responses. Model usage shows the
last successful provider/model and actual reported tokens when available, including tokens
reported on malformed/truncated output. Those counters are usage evidence, not a billing estimate. Manual model settings,
Ollama and legacy single fallbacks continue to work. In advanced settings, **Use manual model
settings** clears a cloud route before configuring another primary/fallback arrangement.

No live keys were available in the development environment, and provider documentation/API hosts
were proxy-blocked there. Validation used controlled responses plus real loopback HTTP and real
browser/application execution. See [research](CLOUD-RESEARCH.md) and [validation](VALIDATION.md).
