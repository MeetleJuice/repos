"""Bounded plan → deterministic review → focused correction orchestration."""
from __future__ import annotations

import copy
from dataclasses import dataclass
import hashlib
import json
import threading
from typing import Any, Callable

from .contracts import Plan, Review, ProposalError, Finding


@dataclass(frozen=True)
class PlanningResult:
    plan: Plan
    review: Review
    attempts: int
    fallback_used: bool


class PlanningEngine:
    """At most three requests, including at most one configured fallback request."""
    def run(self, request: Plan, generate: Callable[[Plan, bool], Plan],
            review: Callable[[Plan], tuple[Plan, Review]],
            report: Callable[[Plan | None, Review], None],
            event: Callable[[str], None], cancel: threading.Event,
            has_fallback: bool = False) -> PlanningResult:
        feedback: dict[str, Any] = {}
        seen: set[str] = set()
        last_review = Review(())
        fallback_used = False
        service_failed = False
        for attempt in range(3):
            if cancel.is_set():
                raise InterruptedError('Stopped before planner request.')
            fallback = has_fallback and not fallback_used and (attempt == 2 or service_failed)
            fallback_used |= fallback
            if fallback:
                event('Trying the explicitly configured planner fallback. Existing cloud-consent requirements still apply.')
            payload = {**copy.deepcopy(request), **feedback}
            try:
                candidate = generate(payload, fallback)
            except ValueError as exc:
                # Production adapters sanitize provider errors before they reach here.
                last_review = Review(())
                service_failed = True
                event('Planner request failed: ' + str(exc))
                if getattr(exc,"category",None) in {"truncated_output","output_budget"} or fallback or attempt == 2 or (not has_fallback and getattr(exc, "category", None) in {"auth", "provider", "rate_limit", "size", "truncated", "exhausted", "quota", "model", "request"}):
                    raise
                feedback = {'validation_error': str(exc), 'instruction': 'Return the requested JSON proposal using the supplied contract.'}
                continue
            if cancel.is_set():
                raise InterruptedError('Stopped. Planner output discarded.')
            service_failed = False
            try:
                candidate, result = review(candidate)
            except ValueError as exc:
                result = exc.review if isinstance(exc, ProposalError) else Review((Finding('structure', '/', str(exc)),))
            report(candidate, result)
            last_review = result
            if result.passed:
                return PlanningResult(candidate, result, attempt + 1, fallback_used)
            digest = hashlib.sha256(json.dumps(candidate, sort_keys=True, default=str).encode()).hexdigest()
            repeated = digest in seen
            seen.add(digest)
            feedback = {'previous_proposal': candidate, 'validation_error': '; '.join(f'{f.path}: {f.message}' for f in result.findings if f.severity == 'error'),
                        'review_findings': result.to_dict()['findings'],
                        'correction_instruction': 'Correct only the reported contradictions. Keep the requested scope, reuse the supplied starter, and return the full proposal JSON. Do not weaken feature coverage.'}
            event('Proposal consistency review found errors; requesting a focused correction: ' + feedback['validation_error'])
            if fallback or attempt == 2:
                break
            if repeated:
                if has_fallback and not fallback_used:
                    service_failed = True  # Use the one fallback rather than repeating unchanged output.
                else:
                    event('Planner repeated the same invalid proposal. Stopped to avoid wasting another request.')
                    break
        raise ProposalError(last_review)
