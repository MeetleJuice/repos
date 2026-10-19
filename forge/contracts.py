"""Typed proposal structure and deterministic consistency review; never execute code."""
from __future__ import annotations

from dataclasses import dataclass, asdict
import json
import re
from typing import Any, Literal
from urllib.parse import urlsplit

from .evidence import validate_evidence
from .workflow import ownership_warnings

Plan = dict[str, Any]

def validate_structure(plan: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(plan, dict):
        raise ValueError("Proposal must be a JSON object.")
    for name in ("title", "summary"):
        if not isinstance(plan.get(name), str) or not plan[name].strip() or len(plan[name]) > 6000:
            raise ValueError(f"Proposal needs a nonempty {name} (up to 6000 characters).")
    for name in ("features", "out_of_scope", "risks"):
        if not isinstance(plan.get(name), list) or len(plan[name]) > 20 or not all(isinstance(x, str) and len(x) < 3000 for x in plan[name]):
            raise ValueError(f"Proposal needs a list of {name}.")
    if not plan["features"]:
        raise ValueError("The proposal must list at least one feature.")
    manual, browser = validate_evidence(plan)
    if plan.get("app_kind", "server") not in {"server", "browser"}:
        raise ValueError("app_kind must be server or browser.")
    def coverage(items: list[dict[str, Any]], label: str) -> None:
        covered = set()
        for item in items:
            indexes = item.get("feature_indexes")
            if not isinstance(indexes, list) or not all(type(i) is int and 0 <= i < len(plan["features"]) for i in indexes):
                raise ValueError(f"Each {label} needs feature_indexes listing the feature numbers it covers (starting at 0).")
            covered.update(indexes)
        missing = set(range(len(plan["features"]))) - covered
        if missing:
            raise ValueError(f"Every feature needs {label} coverage. Missing feature indexes: {sorted(missing)}.")
    tasks = plan.get("tasks")
    if not isinstance(tasks, list) or not 1 <= len(tasks) <= 8:
        raise ValueError("Proposal must contain 1–8 ordered tasks.")
    for task in tasks:
        if not isinstance(task, dict) or not all(isinstance(task.get(k), str) and 0 < len(task[k]) <= 6000 for k in ("title", "instructions")):
            raise ValueError("Each task needs a title and instructions.")
    coverage(tasks, "task")
    checks = plan.get("checks")
    if not isinstance(checks, list) or not 1 <= len(checks) <= 15:
        raise ValueError("Proposal must contain 1–15 behavioral HTTP checks.")
    behavior = False
    for check in checks:
        if not isinstance(check, dict):
            raise ValueError("Each check must be an object.")
        path = check.get("path", "")
        if not isinstance(path, str) or not path.startswith("/") or path.startswith("//") or any(c in path for c in "\r\n\\#") or len(path) > 1000:
            raise ValueError("Checks must use local URL paths.")
        if check.get("method") not in {"GET", "POST", "PUT", "DELETE", "PATCH"}:
            raise ValueError("Unsupported HTTP check method.")
        if not isinstance(check.get("name"), str) or not check["name"]:
            raise ValueError("Every check needs a name.")
        if type(check.get("status")) is not int or not 100 <= check["status"] <= 599:
            raise ValueError("Every check needs an expected HTTP status.")
        has_contains = isinstance(check.get("contains"), str) and bool(check["contains"])
        has_json = isinstance(check.get("json_contains"), (dict, list)) and bool(check["json_contains"])
        has_equals = "json_equals" in check
        has_empty = check.get("empty_body") is True
        if "empty_body" in check and type(check["empty_body"]) is not bool:
            raise ValueError("empty_body must be true or false.")
        if not (has_contains or has_json or has_equals or has_empty):
            raise ValueError("Every check needs contains, nonempty json_contains, or json_equals.")
        if "contains" in check and not has_contains or "json_contains" in check and not has_json:
            raise ValueError("Invalid response assertion.")
        if path.split("?")[0] not in {"/", "/health"} and not re.search(r"\.(?:js|css|png|svg|ico|html)$", path.split("?")[0], re.I):
            behavior = True
    if not behavior and not (plan.get("app_kind") == "browser" and (manual or browser)):
        raise ValueError("Add a check of actual app behavior beyond / and /health. For browser apps, set app_kind to browser and provide browser_checks or explicit manual_checks.")
    coverage(checks + manual + browser, "acceptance check")
    for task in tasks:
        indexes = task.get("check_indexes", [])
        if not isinstance(indexes, list) or any(type(i) is not int or not 0 <= i < len(checks) for i in indexes):
            raise ValueError("Task check_indexes must refer to approved acceptance checks.")
    if len(json.dumps(plan)) > 30000:
        raise ValueError("Proposal too large. Narrow the scope.")
    return plan



@dataclass(frozen=True)
class Finding:
    code: str
    path: str
    message: str
    severity: Literal['error', 'warning'] = 'error'


@dataclass(frozen=True)
class Review:
    findings: tuple[Finding, ...]
    contracts: tuple[dict[str, Any], ...] = ()

    @property
    def passed(self) -> bool:
        return not any(item.severity == 'error' for item in self.findings)

    def to_dict(self) -> dict[str, Any]:
        return {'passed': self.passed, 'findings': [asdict(item) for item in self.findings],
                'contracts': list(self.contracts), 'executed': False,
                'meaning': 'Proposal consistency review. No generated code was run; passing does not establish app correctness.'}


class ProposalError(ValueError):
    def __init__(self, review: Review):
        self.review = review
        super().__init__('; '.join(f'{f.path}: {f.message}' for f in review.findings if f.severity == 'error'))


def _leaves(value: Any) -> list[Any]:
    if isinstance(value, dict):
        return [leaf for item in value.values() for leaf in _leaves(item)]
    if isinstance(value, list):
        return [leaf for item in value for leaf in _leaves(item)]
    return [value]


def _kind(value: Any) -> str:
    if isinstance(value, dict):
        return 'object'
    if isinstance(value, list):
        return 'array'
    if isinstance(value, str):
        return 'text'
    return 'scalar'


def _matches(contract: dict[str, Any], check: dict[str, Any]) -> bool:
    if contract['method'] != check['method']:
        return False
    pattern = re.escape(contract['path'])
    pattern = re.sub(r'\\\{[^{}]+\\\}', r'[^/]+', pattern)
    return re.fullmatch(pattern, urlsplit(check['path']).path) is not None


def starter_contracts(starter: str | None) -> list[dict[str, Any]]:
    common = [
        {'method': 'GET', 'path': '/health', 'status': 200, 'response_kind': 'object', 'required_fields': ['status']},
        {'method': 'GET', 'path': '/', 'status': 200, 'response_kind': 'text', 'required_fields': []},
    ]
    if starter not in {'notes', 'tasks'}:
        return common
    collection = '/api/' + starter
    fields = ['id', 'title', 'body'] if starter == 'notes' else ['id', 'title', 'completed']
    result = common + [
        {'method': 'POST', 'path': collection, 'status': 201, 'response_kind': 'object', 'required_fields': fields},
        {'method': 'GET', 'path': collection, 'status': 200, 'response_kind': 'array', 'required_fields': fields},
        {'method': 'DELETE', 'path': collection + '/{id}', 'status': 200, 'response_kind': 'object', 'required_fields': ['deleted']},
    ]
    if starter == 'notes':
        result.append({'method': 'GET', 'path': collection + '/search', 'status': 200, 'response_kind': 'array', 'required_fields': fields})
    else:
        result.append({'method': 'PUT', 'path': collection + '/{id}', 'status': 200, 'response_kind': 'object', 'required_fields': fields})
    return result


def _contains_body(expected: Any, body: Any) -> bool:
    return isinstance(expected, dict) and isinstance(body, dict) and bool(body) and all(expected.get(k) == v for k, v in body.items())


def review_plan(plan: Plan, starter: str | None = None) -> Review:
    """Reject objective contradictions; leave ambiguous product decisions as warnings.

    Starter contracts are defaults. An explicit api_contracts entry may change one,
    but that deviation is prominently reported for human approval.
    """
    findings: list[Finding] = []
    try:
        if not isinstance(plan, dict):
            raise ValueError('Proposal must be a JSON object.')
        validate_structure(plan)
        json.dumps(plan, allow_nan=False)
    except (ValueError, TypeError) as exc:
        return Review((Finding('structure', '/', str(exc)),))
    for warning in ownership_warnings(plan):
        findings.append(Finding("controller_owned_reference", "/tasks/"+str(warning["task"]-1), warning["message"]+" Files: "+", ".join(warning["files"]), "warning"))
    contracts = starter_contracts(starter)
    declared = plan.get('api_contracts', [])
    if not isinstance(declared, list) or len(declared) > 30:
        return Review((Finding('contracts', '/api_contracts', 'Use an array of at most 30 API contracts.'),))
    seen: set[tuple[str, str]] = set()
    for index, contract in enumerate(declared):
        pointer = f'/api_contracts/{index}'
        if not isinstance(contract, dict) or contract.get('method') not in {'GET', 'POST', 'PUT', 'PATCH', 'DELETE'} or not isinstance(contract.get('path'), str) or not contract['path'].startswith('/') or contract['path'].startswith('//'):
            findings.append(Finding('contract', pointer, 'Each API contract needs a local path and supported method.'))
            continue
        if contract.get('response_kind') not in {'object', 'array', 'text', 'empty', 'scalar'} or type(contract.get('status')) is not int or not 200 <= contract['status'] <= 599:
            findings.append(Finding('contract', pointer, 'Contract needs status 200–599 and response_kind object/array/text/empty/scalar.'))
            continue
        fields = contract.get('required_fields', [])
        if not isinstance(fields, list) or not all(isinstance(f, str) and 0 < len(f) <= 100 for f in fields) or len(fields) > 30:
            findings.append(Finding('contract', pointer, 'required_fields must be an array of field names.'))
            continue
        key = (contract['method'], contract['path'])
        if key in seen:
            findings.append(Finding('duplicate_contract', pointer, 'Duplicate API contract.'))
            continue
        seen.add(key)
        old = next((c for c in contracts if (c['method'], c['path']) == key), None)
        normalized = {**contract, 'required_fields': fields}
        if old and normalized != old:
            findings.append(Finding('starter_contract_changed', pointer, 'This explicitly changes the reviewed starter API. Check the status, response shape and fields before approval.', 'warning'))
        contracts = [c for c in contracts if (c['method'], c['path']) != key] + [normalized]
    for index, check in enumerate(plan['checks']):
        if urlsplit(check['path']).path == '/' and check.get('feature_indexes') and plan.get('app_kind') == 'browser':
            findings.append(Finding('page_is_not_gameplay', f'/checks/{index}', 'An HTTP page check proves delivery only. Gameplay needs browser or manual checks.', 'warning'))
    # Catch the common fresh-data mistake without guessing arbitrary API semantics.
    for index, check in enumerate(plan['checks']):
        expected = check.get('json_contains')
        if check['method'] == 'GET' and isinstance(expected, list) and expected:
            later_creates = [c for c in plan['checks'][index + 1:] if c['method'] == 'POST' and urlsplit(c['path']).path == urlsplit(check['path']).path and any(_contains_body(item, c.get('body')) for item in expected)]
            earlier_creates = [c for c in plan['checks'][:index] if c['method'] == 'POST' and urlsplit(c['path']).path == urlsplit(check['path']).path]
            if later_creates and not earlier_creates:
                findings.append(Finding('read_before_create', f'/checks/{index}', 'This fresh-data check expects records created by a later POST. Move creation before retrieval.'))
    request_values = _leaves([c.get('body') for c in plan['checks']])
    for index, check in enumerate(plan['checks']):
        pointer = f'/checks/{index}'
        assertions = [key for key in ('contains', 'json_contains', 'json_equals') if key in check]
        if check['status'] in {204, 304} and assertions:
            findings.append(Finding('empty_response', pointer, 'HTTP 204/304 has no response body. Use empty_body: true, or choose a status with the intended JSON response.'))
        if check.get('empty_body') and assertions:
            findings.append(Finding('conflicting_assertions', pointer, 'empty_body cannot be combined with body assertions.'))
        if 'restart_before' in check and type(check['restart_before']) is not bool:
            findings.append(Finding('restart_type', pointer + '/restart_before', 'restart_before must be true or false.'))
        if check.get('restart_before') and (check['method'] != 'GET' or urlsplit(check['path']).path in {'/', '/health'}):
            findings.append(Finding('restart_evidence', pointer, 'After restarting, GET saved application data; health/startup alone does not prove persistence.'))
        if re.search(r'\brestart\b|\breboot\b', check['name'], re.I) and not check.get('restart_before') and not re.search(r'\bunittest\b|\bunit test', check['name'], re.I):
            findings.append(Finding('false_restart', pointer + '/name', 'This check claims a restart but never restarts the server. Add restart_before: true to a GET of saved data, or describe the check accurately.'))
        for assertion in assertions:
            for value in _leaves(check[assertion]):
                if not isinstance(value, str) or value in request_values:
                    continue
                if value.strip().lower() in {'...', '…', 'todo', 'tbd', '<timestamp>'} or '(if not deleted)' in value.lower():
                    findings.append(Finding('placeholder', pointer + '/' + assertion, 'Replace placeholder or conditional expected values with an executable assertion. Use a subset assertion for variable timestamps.'))
        contract = next((c for c in contracts if _matches(c, check) and c['status'] == check['status']), None)
        matches = [c for c in contracts if _matches(c, check)]
        if not contract and matches and 200 <= check['status'] < 300:
            findings.append(Finding('status_mismatch', pointer + '/status', f"Success status conflicts with the declared API contract ({matches[0]['status']})."))
        if contract:
            for assertion in ('json_equals', 'json_contains'):
                if assertion in check and _kind(check[assertion]) != contract['response_kind']:
                    findings.append(Finding('response_shape', pointer + '/' + assertion, f"This endpoint returns {contract['response_kind']}; the assertion expects {_kind(check[assertion])}."))
            for assertion in ('json_equals', 'json_contains'):
                if assertion not in check:
                    continue
                expected = check[assertion]
                objects = [expected] if isinstance(expected, dict) else expected if isinstance(expected, list) else []
                if contract['response_kind'] == 'array' and contract.get('required_fields') and any(not isinstance(item, dict) for item in objects):
                    findings.append(Finding('item_shape', pointer + '/' + assertion, 'This API returns an array of objects, not scalar values or database rows.'))
                if assertion == 'json_equals' and any(isinstance(item, dict) and not set(contract.get('required_fields', [])).issubset(item) for item in objects):
                    findings.append(Finding('exact_fields', pointer + '/' + assertion, 'An exact assertion omits required response fields. Include them or use json_contains for a subset.'))
            if 'contains' in check and contract['response_kind'] in {'object', 'array'}:
                findings.append(Finding('weak_json_assertion', pointer + '/contains', 'Use json_contains or json_equals to verify JSON shape and fields, rather than a text fragment.', 'warning'))
        if urlsplit(check['path']).path == '/health' and check['feature_indexes']:
            findings.append(Finding('health_coverage', pointer + '/feature_indexes', 'Health proves server readiness; it does not prove business features.', 'warning'))
    if starter and starter != 'web' and len(plan['tasks']) > 4:
        findings.append(Finding('starter_rebuild', '/tasks', 'This reviewed starter already supplies the server, storage and UI. Prefer a short plan for actual changes and tests.', 'warning'))
    return Review(tuple(findings), tuple(contracts))


def require_consistent(plan: Plan, starter: str | None = None) -> Review:
    result = review_plan(plan, starter)
    if not result.passed:
        raise ProposalError(result)
    return result
