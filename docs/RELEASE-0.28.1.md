# v0.28.1 — guided planner wire contract

The Tiny Wins journal failed during outline creation, before task decomposition or code generation. Several responding models returned unsupported app/context values, dictionaries or strings instead of manual-check objects, or unnamed HTTP checks. Other providers independently returned rate limits, HTTP 402, HTTP 503 or transport failures. These are distinct causes.

Foundry's guided prompts referred to a supplied schema, but the cloud adapters only requested JSON mode and did not include that schema. Ollama received a native schema when enabled; JSON mode alone does not enforce these field names. The fix supplies the actual outline/task schema in the system instruction for every adapter, with explicit object/enum guidance, regardless of native JSON settings. Ollama reservation now counts both textual and native schemas. Generic legacy planning/coding prompts remain unchanged.

The deterministic approval reviewer, frozen tests/checks, task scope, quotas, retry limits, routing choices and saved project files are unchanged. This patch does not restore exhausted provider accounts or prove live-model success.

## Resume Tiny Wins

1. Click **Update → Check for updates → Install & restart**.
2. Open the existing failed **New project** containing the Tiny Wins idea.
3. Use **Plan in smaller steps** in the proposal area. Keep the displayed local planning timeout unless you deliberately want to change it. Do not use the ordinary Retry proposal button for this test.
4. If cloud providers are eligible, retain cloud consent only if you want their use. Otherwise apply **Use only this PC** first; local availability and the existing output/context gates still apply.
5. Stop at the complete proposal and inspect features, checks and small task scopes before approval. If it fails, retain the new journal instead of repeatedly retrying.

## Regression evidence

`tests/test_guided_wire_contract.py` checks actual mocked outbound payloads for Gemini, Groq, OpenRouter, Cloudflare, NVIDIA, Requesty, Hugging Face, Ollama and the compatible local adapter. Outline and task stages are checked with native JSON both on and off (36 combinations). The pre-patch run failed all 36 wire cases plus the duplicated-schema reservation assertion: `Ran 2 tests ... FAILED (failures=37)`. After the patch, the focused guided/truncation/capacity suites passed 45 tests. These are controlled adapter tests, not captured Tiny Wins responses or live provider generation.

Release validation additionally runs the full suite, both guided/capacity Chromium flows, strict typing and an extracted-distribution check before publication. Published release results are reported in the update response; this document does not assume future checks passed.
