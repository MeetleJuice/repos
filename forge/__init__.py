"""Idea Foundry: a local idea-to-app workbench."""

__version__ = "0.33.2"

__release_notes__ = "Acceptance before tasks: staged planning now uses the same task-independent consistency rules as final review, catching incorrect restart placement, false restart claims, response-shape contradictions and placeholders before task-generation calls. Existing bounded correction and fallback handle these failures without extra retry loops. Matching saved split-stage drafts retain validated scope but regenerate invalid acceptance and dependent tasks; complete-request identity and final approval checks remain enforced. Diagnostics expose distinct restart findings. Approved projects, source, checks, routes and consent are unchanged. Frozen synthetic regressions reproduce the observed failure class; live-model quality and Windows performance remain untested."
