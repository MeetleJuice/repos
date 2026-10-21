"""Versioned pre-approval task compilation; model prose never proves behavior."""
from __future__ import annotations

import copy
import hashlib
import json
import threading
from typing import Any, Callable
from urllib.parse import urlsplit

from .schemas import PLAN_SCHEMA

POLICY = 'compiled_v1'
FEATURE_PROMPT = '''GOAL: Design a short sequential implementation checklist for exactly ONE requested feature. Return {"tasks":[...]} only.
CONTEXT: The complete request, approved-for-planning outline, existing starter, builder limits and earlier task declarations are provided as data. No proposal is approved yet. Reuse starter behavior and stable API contracts. Follow target_feature_indexes exactly; never repeat unrelated earlier work.
CONSTRAINTS: Each task needs title, instructions (under 1800 characters), outcome (under 300 characters), files and done_when. Optional interfaces must describe real shared file/symbol/contract boundaries. Obey max_new_tasks and builder_profile.max_editable_files. Prefer one narrow behavior plus its focused test. Use root test_*.py modules unless package initialization already exists. Do not assign protected tests, controller documentation or launchers. Split storage setup before its consumers. No catch-all final task, source code, dependencies or execution. Do NOT return depends_on, feature_indexes or check_indexes: the controller owns sequential dependencies, feature references and runnable-prefix scheduling. Declared completion criteria are not test evidence.
DONE WHEN: Return only concrete, bounded tasks implementing the requested feature. Preserve all requirements and acceptance checks; report impossible scope through clear task instructions, never invent working behavior.'''

FEATURE_SCHEMA: dict[str, Any] = copy.deepcopy(PLAN_SCHEMA['properties']['tasks'])
FEATURE_SCHEMA.update(minItems=1, maxItems=3)
for field in ('depends_on', 'feature_indexes', 'check_indexes'):
    FEATURE_SCHEMA['items']['properties'].pop(field, None)
    if field in FEATURE_SCHEMA['items'].get('required', []):
        FEATURE_SCHEMA['items']['required'].remove(field)
FEATURE_SCHEMA = {'type': 'object', 'required': ['tasks'], 'additionalProperties': False,
                  'properties': {'tasks': FEATURE_SCHEMA}}
FEATURE_SCHEMA['properties']['tasks']['items']['additionalProperties'] = False


def validate_compilable_outline(candidate: dict[str, Any]) -> None:
    from .guided import validate_outline
    validate_outline(candidate)
    if candidate.get('acceptance_policy') != 'evidence_v1' or candidate.get('app_kind') == 'browser': return
    required: set[int] = set()
    for check in candidate['checks']:
        required.update(check.get('feature_indexes', []))
        if urlsplit(check['path']).path not in {'/', '/health'}:
            if len(candidate['features']) > 1 and required == set(range(len(candidate['features']))):
                raise ValueError('/checks: No early business prefix is schedulable: the first business check depends on every feature. Separate delivery/UI declarations from the first runnable business feature before creating tasks; preserve all requested behavior and checks.')
            break


def schedule(outline: dict[str, Any], tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Schedule unchanged ordered prefixes using declared last producers only.

    A future feature blocks the prefix. Scheduling grants no execution consent
    and does not establish that the implementation actually satisfies a check.
    """
    result = copy.deepcopy(tasks)
    for task in result:
        task.pop('check_indexes', None)
    if outline.get('acceptance_policy') != 'evidence_v1' or outline.get('app_kind') == 'browser':
        return result
    producers = {feature: index for index, task in enumerate(result) for feature in task['feature_indexes']}
    ready = 0
    for index, check in enumerate(outline['checks']):
        features = check.get('feature_indexes', [])
        if not result or any(feature not in producers for feature in features):
            break
        ready = max(ready, max((producers[feature] for feature in features), default=0))
        result[ready].setdefault('check_indexes', []).append(index)
    return result


def compile_tasks(candidate: dict[str, Any], outline: dict[str, Any], earlier: list[dict[str, Any]],
                  target: int, maximum: int, profile: dict[str, Any] | None) -> list[dict[str, Any]]:
    from .guided import validate_batch
    if not isinstance(candidate, dict) or set(candidate) != {'tasks'} or not isinstance(candidate['tasks'], list) or not 1 <= len(candidate['tasks']) <= maximum:
        raise ValueError('Return only 1–'+str(maximum)+' narrow tasks for the single requested feature.')
    tasks = copy.deepcopy(earlier)
    allowed = set(FEATURE_SCHEMA['properties']['tasks']['items']['properties'])
    for item in candidate['tasks']:
        if not isinstance(item, dict) or set(item) - allowed:
            raise ValueError('Task bookkeeping is controller-owned: omit depends_on, feature_indexes and check_indexes; return only the requested semantic task fields.')
        tasks.append({**copy.deepcopy(item), 'feature_indexes': [target],
                      'depends_on': [len(tasks)-1] if tasks else []})
    tasks = schedule(outline, tasks)
    # Earlier declarations remain unchanged except controller-owned scheduling.
    validate_batch({'tasks': tasks[len(earlier):]}, outline, tasks[:len(earlier)], [target], maximum, profile)
    return tasks


def run_compiled(request: dict[str, Any], generate: Callable[..., dict[str, Any]],
                 checkpoint: Callable[[dict[str, Any]], None], cancel: threading.Event,
                 saved: dict[str, Any] | None = None) -> dict[str, Any]:
    from .guided import OUTLINE_PROMPT, validate_batch
    identity = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
    draft = copy.deepcopy(saved) if saved and saved.get('request_sha256') == identity and saved.get('task_planning_policy') == POLICY else {
        'schema': 2, 'task_planning_policy': POLICY, 'request_sha256': identity,
        'outline': None, 'tasks': [], 'next_feature': 0}
    if cancel.is_set(): raise InterruptedError('Stopped before guided planning.')
    if draft['outline'] is None:
        outline = generate(OUTLINE_PROMPT, {**request, 'planning_stage': 'outline'}, validate_compilable_outline)
        validate_compilable_outline(outline)
        draft['outline'] = copy.deepcopy(outline)
        checkpoint(copy.deepcopy(draft))
    outline = draft['outline']
    validate_compilable_outline(outline)
    first = draft['next_feature']
    if type(first) is not int or not 0 <= first <= len(outline['features']):
        raise ValueError('Invalid compiled planning checkpoint position.')
    if first:
        validate_batch({'tasks': draft['tasks']}, outline, [], list(range(first)), 16, request.get('builder_profile'))
    elif draft['tasks']:
        raise ValueError('Unexpected tasks before the first compiled feature.')
    for target in range(first, len(outline['features'])):
        if cancel.is_set(): raise InterruptedError('Guided plan draft saved. Resume planning to continue.')
        earlier = copy.deepcopy(draft['tasks'])
        maximum = min(3, 16-len(earlier)-(len(outline['features'])-target-1))
        if maximum < 1: raise ValueError('Task allowance exhausted; revise the unapproved scope.')
        def validate(candidate: dict[str, Any]) -> None:
            compile_tasks(candidate, outline, earlier, target, maximum, request.get('builder_profile'))
        response = generate(FEATURE_PROMPT, {'request': request, 'outline': outline, 'earlier_tasks': earlier,
            'planning_stage': 'feature_tasks', 'task_planning_policy': POLICY,
            'target_feature_indexes': [target], 'next_task_index': len(earlier), 'max_new_tasks': maximum,
            'builder_profile': request.get('builder_profile', {}),
            'controller_owned_fields': ['depends_on', 'feature_indexes', 'check_indexes']}, validate)
        tasks = compile_tasks(response, outline, earlier, target, maximum, request.get('builder_profile'))
        draft.update(tasks=tasks, next_feature=target+1,
                     references={'tasks': [{'id': 'T'+str(i+1).zfill(3), 'index': i,
                         'feature_indexes': task['feature_indexes'], 'depends_on': task['depends_on'],
                         'check_indexes': task.get('check_indexes', [])} for i, task in enumerate(tasks)]})
        checkpoint(copy.deepcopy(draft))
    if cancel.is_set(): raise InterruptedError('Guided draft saved; final approval review has not run.')
    return {**copy.deepcopy(outline), 'tasks': copy.deepcopy(draft['tasks'])}
