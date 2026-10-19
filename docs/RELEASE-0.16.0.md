# 0.16.0 — Automatic model routes and semantic proposal recovery

## Use the update

Restart after updating. Open Models and click **Set up models automatically**. It uses already imported private credentials; import the Desktop .env again only if those credentials have changed. It applies routes to new projects and the open idle project without changing source files, approved requirements, checks, backups or verification evidence. Generation and execution consent remain separate. No inference is performed by setup. Catalogues cannot prove quota or generation access.

Missing keys/account configuration and failed catalogues are skipped. Cloudflare still requires its Account ID and token. This update cannot supply missing account credentials, quota or paid credit. Installed Ollama chat/coding models are eligible as a last resort when automatic setup is chosen. The automatic action explicitly includes that local fallback; advanced manual mode still permits disabling it.

Automatic routes use advertised model IDs, a deterministic role-specific ranking, up to two candidates per provider, and an optional installed local model. Concrete free model IDs rank ahead of OpenRouter's free router when otherwise comparable; the generic free router remains available when needed. Ranking is a heuristic, not a benchmark or promise of model quality. Automatic mode does not restrict selection to free models: paid models may be selected and incur charges when generation is approved. Review the resulting route if cost matters.

Planner and builder routes can differ. One primary per available provider comes before their second candidates, then Ollama. Routes are capped at 16 configurations. Existing manual and legacy routes remain valid; advanced manual selection replaces automatic alternates. Advanced controls show one selected planner model per provider, not the entire automatic route; the full planner/builder route appears in the project and history. Automatic profile persistence contains no credentials.

## What failed and what changed

The supplied Josh dashboard log shows repeated Gemini model-access failures, valid JSON rejected for missing title/feature coverage/browser evidence, and truncated responses from OpenRouter. There are no raw response bodies in that log, so it does not establish whether missing fields came from wrapper objects, omitted fields or another output shape.

Previously, each deterministic proposal correction restarted the route at the failed primary. Any JSON object counted as success for provider routing, so later models were starved. Pooled planning now validates semantics inside routing: each model receives one focused correction; another invalid proposal advances to the next model. The current attempt records schema_error, finding codes, proposal validity and recovery_path=schema_correction. Model-access, auth, quota and missing-configuration failures are not retried for that model during the same job. New jobs reset that rejection map, allowing recovery after setup changes. Existing rate-limit cooldowns remain in effect.

Planner requests add a concise authoritative root-field contract to reduce ambiguity between proposals, code, schemas and wrapped objects. It is included in input reservation. No field is fabricated and no acceptance requirement is weakened. Corrective prompts preserve the original request and explicitly include review findings.

HTTP400 gets at most one compatibility retry without the optional native JSON-format parameter. HTTP400 alone does not establish which parameter was rejected; the retry is logged as json_compatibility, and returned content still must parse and pass deterministic validation. If rejected again, normal failover continues. No arbitrary response-body text or credentials are logged.

Planning has a 24-invocation job allowance, covering corrections, compatibility attempts and truncation recovery. Smaller-output fallback remains forbidden after truncation. One request runs at a time; hangs must time out before failover. There is no instantaneous hang-detection or guaranteed completion claim. Coding retains its original validation-before-replacement and single malformed-file correction; runtime repairs retain their existing per-job cap.

## Evidence

The synthetic frozen Josh failure fixture reproduces the observed failure classes, not unprovided raw cloud responses. Against the actual v0.15.0 distribution, it stops with error after Gemini → OpenRouter → Gemini → OpenRouter. With v0.16.0, Gemini → OpenRouter → OpenRouter correction → NVIDIA yields a valid unapproved proposal. Neither comparison writes app files or uses live cloud keys. Full results are in research/automatic-routing-results-v1.json.

The browser workflow checks automatic discovery/application, restart persistence, the cloud-consent boundary, missing Cloudflare configuration, semantic failover, actual generated-app verification, preservation of verified evidence when routes change, mobile layout and secret-value absence. Native Windows and live provider generation remain user-machine checks.

Release validation: the extracted ZIP passed 289 automated tests and four Chromium workflows. Strict type checks passed for 15 modules. The public archive and updater checksum are verified during publication.
