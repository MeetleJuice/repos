"""Bounded, declarative verification contracts shared by planner, UI and runner."""
from __future__ import annotations

from typing import Any

ACTIONS = {'click', 'fill', 'press', 'wait', 'expect_text', 'expect_visible', 'expect_canvas_changes', 'reload', 'expect_storage'}


def validate_evidence(plan: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    manual = plan.get('manual_checks', [])
    browser = plan.get('browser_checks', [])
    for label, checks in [('manual_checks', manual), ('browser_checks', browser)]:
        if not isinstance(checks, list) or len(checks) > 12:
            raise ValueError(f'{label} must be a list of at most 12 checks.')
        for item in checks:
            if not isinstance(item, dict) or not isinstance(item.get('name'), str) or not 1 <= len(item['name']) <= 200:
                raise ValueError(f'Each {label} entry needs a name (1–200 characters).')
            indexes = item.get('feature_indexes')
            if not isinstance(indexes, list) or not indexes or any(type(i) is not int or not 0 <= i < len(plan['features']) for i in indexes):
                raise ValueError(f'Each {label} entry needs valid, nonempty feature_indexes.')
            if not isinstance(item.get('steps'), list) or not 1 <= len(item['steps']) <= 20:
                raise ValueError(f'Each {label} entry needs 1–20 steps.')
            if label == 'manual_checks':
                if not all(isinstance(s, str) and 1 <= len(s) <= 1000 for s in item['steps']) or not isinstance(item.get('expected'), str) or not 1 <= len(item['expected']) <= 2000:
                    raise ValueError('Manual checks need readable steps and a concrete expected result.')
            else:
                if not any(isinstance(s, dict) and str(s.get('action', '')).startswith('expect_') for s in item['steps']):
                    raise ValueError('Every browser check needs an actual expect_ assertion.')
                for step in item['steps']:
                    validate_step(step)
    return manual, browser


def validate_step(step: Any) -> None:
    if not isinstance(step, dict) or step.get('action') not in ACTIONS:
        raise ValueError('Unsupported browser action; arbitrary scripts and navigation are not allowed.')
    action = step['action']
    allowed = {'action', 'selector', 'value', 'ms'}
    if set(step) - allowed:
        raise ValueError('Unknown browser step field. Use action, selector, value or ms.')
    if action in {'click', 'fill', 'expect_text', 'expect_visible', 'expect_canvas_changes'}:
        if not isinstance(step.get('selector'), str) or not 1 <= len(step['selector']) <= 200:
            raise ValueError('Browser action needs a selector (up to 200 characters).')
    if action in {'fill', 'press', 'expect_text', 'expect_storage'}:
        if not isinstance(step.get('value'), str) or not 1 <= len(step['value']) <= 2000:
            raise ValueError('Browser action needs a nonempty string value.')
    if action == 'expect_storage' and (not isinstance(step.get('selector'), str) or not 1 <= len(step['selector']) <= 200):
        raise ValueError('expect_storage uses selector as the localStorage key.')
    if action in {'wait', 'expect_canvas_changes'}:
        ms = step.get('ms', 300)
        if type(ms) is not int or not 50 <= ms <= 2000:
            raise ValueError('Browser waits must be 50–2000 milliseconds.')


def manual_document(plan: dict[str, Any]) -> str:
    text = '# Manual acceptance checks\n\nThese are user observations, not automated verification. Test the downloaded app.\n'
    for index, check in enumerate(plan.get('manual_checks', [])):
        text += f'\n## {index + 1}. {check["name"]}\n\n'
        text += '\n'.join(f'{n + 1}. {step}' for n, step in enumerate(check['steps']))
        text += '\n\nExpected: ' + check['expected'] + '\n'
    return text
