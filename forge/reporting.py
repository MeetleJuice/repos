"""Bind downloadable evidence to the exact selected source and approved contracts."""
from __future__ import annotations

import hashlib
import json
from typing import Any
from .context import fingerprint
from .evidence import manual_document

OWNED = {'readme.md','project.md','tasks.md','checks.json','run.bat','run.sh','launch.py','browser-checks.json','manual-checks.md','build-report.json','run-history.json'}


def evidence_status(state: dict[str, Any], files: dict[str, str]) -> dict[str, Any]:
    current = fingerprint({n:t for n,t in files.items() if n.lower() not in OWNED})
    verified = state.get('verification_fingerprint')
    issues = []
    plan = state.get('plan') or {}
    if state.get('approved'):
        for name, expected in [('CHECKS.json',plan.get('checks', [])), ('BROWSER-CHECKS.json',plan.get('browser_checks', []))]:
            try:
                actual = json.loads(files[name]) if name in files else []
                if (name == 'CHECKS.json' and name not in files) or json.dumps(actual, sort_keys=True) != json.dumps(expected, sort_keys=True):
                    issues.append(name+' does not match the approved checks.')
            except ValueError:
                issues.append(name+' is not valid JSON.')
        if plan.get('manual_checks') and files.get('MANUAL-CHECKS.md') != manual_document(plan):
            issues.append('MANUAL-CHECKS.md does not match the approved manual checks.')
        for name, expected_hash in state.get('frozen_tests', {}).items():
            if name not in files or hashlib.sha256(files[name].encode()).hexdigest() != expected_hash:
                issues.append('Protected test changed or missing: '+name)
    recorded_manifest = state.get('verification_manifest')
    snapshot = {n:t for n,t in files.items() if n.lower() not in {'build-report.json','run-history.json'}}
    if recorded_manifest is not None and recorded_manifest != file_manifest(snapshot):
        issues.append('Project file manifest changed since automated verification (including documents or launchers).')
    source_matches = bool(verified and verified == current)
    if verified and not source_matches:
        issues.append('Implementation changed since automated verification.')
    automated_current = bool((state.get('checks') or {}).get('passed') and source_matches and not issues)
    manual = state.get('manual_results') or {}
    results = manual.get('results', [])
    manual_required = bool(plan.get('manual_checks'))
    manual_current = bool(automated_current and manual.get('source_sha256') == current and
                          len(results) == len(plan.get('manual_checks', [])) and results and all(v is True for v in results))
    accepted = automated_current and (not manual_required or manual_current)
    status = state['status']
    if status in {'verified','review_required'} and not automated_current:
        status = 'needs_attention'
    elif status == 'verified' and not accepted:
        status = 'review_required' if automated_current else 'needs_attention'
    return {'current_source_sha256':current, 'verified_source_sha256':verified,
            'automated_evidence_current':automated_current, 'manual_acceptance_current':manual_current,
            'manual_checks_required':manual_required, 'accepted_current':accepted,
            'bundle_manifest_available':recorded_manifest is not None,
            'evidence_scope':'Project file manifest plus implementation/approved contracts' if recorded_manifest is not None else 'Legacy evidence: implementation and approved contracts only; no historical bundle manifest',
            'issues':issues, 'effective_status':status, 'recorded_status':state['status']}


def file_manifest(files: dict[str, str]) -> list[dict[str, Any]]:
    return [{'file':n,'bytes':len(t.encode('utf-8')),'sha256':hashlib.sha256(t.encode('utf-8')).hexdigest()} for n,t in sorted(files.items())]
