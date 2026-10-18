# Idea Foundry 0.7.3 — source-aware repair plans and visible proposal imports

The shield repair proposal repeated the failed build's five tasks. Improvement planning had the
approved feature list but no source evidence, so the model could mistake promised features for
implemented features. Previous Linux/browser tests used controlled valid replies and did not
establish local-model compliance. This patch addresses that missing context and provides an
explicit no-inference route for a reviewed plan; it does not guarantee arbitrary model quality.

## Recover this shield repair project

1. Update → Check for updates → Install & restart. Keep the terminal open.
2. Open the newest proposed shield improvement, not the original verified game.
3. In Use a reviewed proposal, choose the reviewed shield repair JSON through the file picker.
4. Confirm the visible plan now has **two tasks**, beginning **Repair actual shield logic in game.js**.
   The feedback says Saved 2 tasks. No model request. It remains unapproved.
5. Review and approve, then generate. Review the resulting files before approving execution.

The reviewed JSON is included at docs/proposals/Neon-Dodge-Shield-Repair.json. A separately
published versioned JSON file is also available alongside the 0.7.3 release. It preserves the
actual eight inherited manual checks and HTTP checks, adds two shield-specific checks, and
specifies concrete creation/update/collection/drawing/reset paths. It is a proposal, not fixed
application code, and importing it does not prove that generation will implement it.

## Changes

- Improvement planners receive relevance-ranked current source excerpts: at most 8,000 source
  characters across three files and a bounded map. Truncation and omissions are explicit.
  No app source is executed. Existing job cloud-consent requirements apply to the content.
- A repair with unchanged features and the same task titles/instructions as the baseline is
  rejected with focused correction feedback. Whitespace/case changes do not bypass this guard.
  This is a narrow repetition check, not a semantic proof that a changed plan is good.
- Instructions distinguish actual source from promised baseline features and keep manual
  play-testing out of code-generation tasks. Starters and frozen regression checks stay intact.
- Import proposal JSON validates and saves it locally, updating task cards, title and editor.
  Save edited proposal does the same for direct edits. Neither action runs inference, installs
  starter code, approves scope or executes generated code. Invalid/busy/approved edits are blocked.
- Check edited proposal remains a side-effect-free review, now with explicit visible feedback.
  Automatic editor checking still does not save or approve a proposal.
- Approved legacy projects, original source, backups and the update protocol remain unchanged.
  An older unapproved repair proposal that repeats its baseline tasks may now require revision
  before approval. The reviewed import path handles the current observed case without inference.

Source context improves the planner's evidence; it does not replace actual browser/manual
verification of the generated shield behavior. Do not mark the shield project verified based
only on the unchanged server tests.
