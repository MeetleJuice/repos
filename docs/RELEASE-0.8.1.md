# Idea Foundry 0.8.1 — recover rejected repairs without losing observations

The live Windows/Ollama journal exposed a failure not established by the controlled success
fixtures: qwen2.5-coder returned an exact edit that did not match uniquely, then its one correction
returned no usable files or edits. No file replacement happened. A subsequent successful server
verification checked the same game and did not prove the shield was fixed.

## What changed

- The one response correction now explicitly switches to complete changed files. Ollama receives
  a dedicated schema requiring a nonempty files object and forbidding edit responses. Other
  providers receive the same explicit recovery instruction; application validation still enforces
  the file contract. Normal first responses can still use precise edits.
- Correction requests refresh the current source and retain the original proposal and reported
  failure. They explicitly prohibit diffs, ellipses, further edits or empty output. There are still
  at most two code-response requests per operation, excluding already configured provider fallback.
  Missing API access or truncated output is not retried as a format error.
- A rejected, cancelled or unchanged direct repair retains the previous automated report and saved
  manual observations only when the current source fingerprint still matches. Status remains
  error/stopped/needs attention, never verified. Actual source changes invalidate the old evidence.
- Re-running successful automated checks on unchanged code preserves a previously saved failed
  gameplay result and keeps needs-attention status. A green server report does not clear that failure.
- Existing checkpoints, frozen acceptance/tests, cloud/execution consent and schema-2 workspace
  compatibility remain. No existing generated game is automatically edited by this update.

This improves recovery and prevents lost feedback. It does not establish live-model compliance or
promise that another generated repair will fix the behavior. The reported shield still needs a new
code repair and play-test; its server checks do not exercise that gameplay.

## Continue the reported project

Update → Check for updates → Install & restart; keep the terminal open. Open the same latest
shield-repair project. Since the previous release already cleared its active results on the later
verification run, record your actual checklist results and failure notes once more, then save.
Choose at least one repair attempt. Repair files only generates without execution; Repair & retest
uses the chosen runtime and requires its execution approval. After a changed build, download and
play the new files before recording acceptance. A new failed response now keeps the saved notes
available for another retry while the source is unchanged.
