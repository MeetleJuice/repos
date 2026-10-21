"""Finite validation vocabulary and source-free candidate structure."""
from __future__ import annotations
import re
from typing import Any

RULES = {
    'task_width': 'Task exceeds the configured builder file/feature scope.',
    'feature_scope': 'Task refers to features outside the requested batch.',
    'feature_coverage': 'Requested features are missing task declarations.',
    'premature_milestone': 'A test prefix depends on work declared in a later task.',
    'missing_milestone': 'A ready prefix or early business checkpoint is missing.',
    'controller_owned_fields': 'Task references and scheduling belong to the controller.',
    'test_collection': 'Nested test modules lack prerequisite package initialization.',
    'task_dependencies': 'A consumer lacks an earlier producer dependency.',
    'guided_contract': 'Stage does not satisfy its structured planning contract.',
    'checkpoint_schedule_unsatisfiable': 'An early business test prefix requires every feature; revise the unapproved outline before task planning.',
}


def classify_finding(code: str, path: str, message: str) -> tuple[str, str]:
    if code == 'guided_contract':
        for needle, replacement in (
            ('No early business prefix', 'checkpoint_schedule_unsatisfiable'),
            ('too broad', 'task_width'), ('only to the requested feature batch', 'feature_scope'),
            ('cover every requested feature', 'feature_coverage'), ('from a later task', 'premature_milestone'),
            ('Assign each runnable HTTP prefix', 'missing_milestone'), ('controller-owned', 'controller_owned_fields'),
            ('would not be collected', 'test_collection'), ('must depend on earlier tasks', 'task_dependencies')):
            if needle in message: code = replacement; break
        match = re.search(r'(/(?:tasks|checks)(?:/\d+)?(?:/check_indexes)?):', message)
        if match: path = match.group(1)
    return code, path


def candidate_shape(candidate: Any) -> dict[str, Any]:
    if not isinstance(candidate, dict): return {'object': False}
    result: dict[str, Any] = {'object': True}
    for field in ('features', 'checks', 'manual_checks', 'browser_checks', 'tasks'):
        value = candidate.get(field)
        if isinstance(value, list): result[field+'_count'] = len(value)
    result['check_structure'] = [{'index': index,
        'feature_indexes': [n for n in check.get('feature_indexes', [])[:32] if type(n) is int] if isinstance(check.get('feature_indexes', []), list) else [],
        'restart_before': check.get('restart_before') is True,
        'has_body': 'body' in check,
        'has_assertion': any(key in check for key in ('contains', 'json_contains', 'json_equals', 'empty_body')),
    } for index, check in enumerate(candidate.get('checks', [])[:32]) if isinstance(check, dict)] if isinstance(candidate.get('checks', []), list) else []
    result['task_structure'] = [{
        'index': index, 'file_count': len(task.get('files', [])) if isinstance(task.get('files'), list) else None,
        **{field: [n for n in task[field][:32] if type(n) is int] for field in ('feature_indexes', 'depends_on', 'check_indexes') if isinstance(task.get(field), list)},
        'criteria_count': len(task.get('done_when', [])) if isinstance(task.get('done_when'), list) else None,
        'instruction_characters': len(task['instructions']) if isinstance(task.get('instructions'), str) else None,
    } for index, task in enumerate(candidate.get('tasks', [])[:16]) if isinstance(task, dict)] if isinstance(candidate.get('tasks', []), list) else []
    return result
