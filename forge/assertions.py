"""Assertion structure metadata and portable, versioned planning wire values."""
from __future__ import annotations
import copy
from typing import Any


class AssertionErrorDetail(ValueError):
    def __init__(self, code: str, path: str, message: str) -> None:
        self.code, self.path = code, path
        super().__init__(message)


def assertion_shape(check: dict[str, Any]) -> dict[str, Any]:
    valid = {'contains': isinstance(check.get('contains'), str) and bool(check['contains']),
             'json_contains': isinstance(check.get('json_contains'), (dict, list)) and bool(check['json_contains']),
             'json_equals': 'json_equals' in check,
             'empty_body': check.get('empty_body') is True}
    fields = [key for key in valid if key in check]
    if 'assertion' in check and (not isinstance(check['assertion'],dict) or fields):
        return {'assertion_fields':['assertion',*fields],'assertion_valid':False,'invalid_assertion_fields':['assertion']}
    if isinstance(check.get('assertion'), dict):
        wire = check['assertion']
        try:
            compile_assertion(wire, '/')
            return {'assertion_fields': ['assertion'], 'assertion_valid': True, 'invalid_assertion_fields': [],
                    'assertion_kind': wire.get('kind')}
        except ValueError:
            return {'assertion_fields': ['assertion'], 'assertion_valid': False, 'invalid_assertion_fields': ['assertion']}
    return {'assertion_fields': fields, 'assertion_valid': any(valid.values()) and not any(
        key in check and not valid[key] for key in ('contains', 'json_contains')) and not (
        'empty_body' in check and type(check['empty_body']) is not bool),
        'invalid_assertion_fields': [key for key in fields if not valid[key]]}


def compile_assertion(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {'kind', 'expected'}:
        raise AssertionErrorDetail('assertion_required', path, 'Assertion needs kind and expected, with no extra fields.')
    kind, expected = value['kind'], value['expected']
    if kind == 'text' and isinstance(expected, str) and expected:
        return {'contains': expected}
    if kind == 'json_subset' and isinstance(expected, (dict, list)) and expected:
        return {'json_contains': copy.deepcopy(expected)}
    if kind == 'json_exact':
        return {'json_equals': copy.deepcopy(expected)}
    if kind == 'empty' and expected is None:
        return {'empty_body': True}
    raise AssertionErrorDetail('assertion_value', path, 'Use nonempty text/JSON subset, an exact JSON value, or empty with expected:null.')


def compile_wire(candidate: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(candidate)
    checks = result.get('checks')
    if not isinstance(checks, list):
        raise AssertionErrorDetail('check_structure', '/checks', 'checks must be an array.')
    for index, check in enumerate(checks):
        if not isinstance(check, dict):
            raise AssertionErrorDetail('check_structure', f'/checks/{index}', 'Each check must be an object.')
        if any(key in check for key in ('contains', 'json_contains', 'json_equals', 'empty_body')):
            raise AssertionErrorDetail('assertion_value', f'/checks/{index}', 'Wire v2 requires assertion; do not mix legacy assertion fields.')
        compiled = compile_assertion(check.pop('assertion', None), f'/checks/{index}/assertion')
        check.update(compiled)
    return result
