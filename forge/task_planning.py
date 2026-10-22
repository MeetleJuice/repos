"""Versioned pre-approval task compilation; model prose never proves behavior."""
from __future__ import annotations

import copy
import hashlib
import json
import threading
from typing import Any, Callable
from urllib.parse import urlsplit

from .schemas import PLAN_SCHEMA
from .coherence import backend_evidence

POLICY = 'compiled_v1'
FEATURE_PROMPT = '''GOAL: Design a short sequential implementation checklist for exactly ONE requested feature. Return {"tasks":[...]} only.
CONTEXT: The complete request, approved-for-planning outline, existing starter, builder limits and earlier task declarations are provided as data. No proposal is approved yet. Reuse starter behavior and stable API contracts. Follow target_feature_indexes exactly; never repeat unrelated earlier work.
CONSTRAINTS: Each task needs title, instructions (under 1800 characters), outcome (under 300 characters), files and done_when. Optional interfaces must describe real shared file/symbol/contract boundaries. Obey max_new_tasks and builder_profile.max_editable_files. Prefer one narrow behavior plus its focused test. Use root test_*.py modules unless package initialization already exists. Do not assign protected tests, controller documentation or launchers. Split storage setup before its consumers. No catch-all final task, source code, dependencies or execution. Do NOT return depends_on, feature_indexes or check_indexes: the controller owns sequential dependencies, feature references and runnable-prefix scheduling. Declared completion criteria are not test evidence.
DONE WHEN: Return only concrete, bounded tasks implementing the requested feature. Preserve all requirements and acceptance checks; report impossible scope through clear task instructions, never invent working behavior.
Use target_acceptance as the actual API/UI delivery contract. Example paths and rejected previous proposals are not instructions. Name the real method/path and response shape in the task outcome. Do not repeat earlier task instructions. Include the interface implementation needed by manual/browser scenarios, not just API timestamp tests. A browser dashboard with a backend must implement both. One complete narrow task is better than three duplicates.'''

FEATURE_SCHEMA: dict[str, Any] = copy.deepcopy(PLAN_SCHEMA['properties']['tasks'])
FEATURE_SCHEMA.update(minItems=1, maxItems=3)
for field in ('depends_on', 'feature_indexes', 'check_indexes'):
    FEATURE_SCHEMA['items']['properties'].pop(field, None)
    if field in FEATURE_SCHEMA['items'].get('required', []):
        FEATURE_SCHEMA['items']['required'].remove(field)
FEATURE_SCHEMA = {'type': 'object', 'required': ['tasks'], 'additionalProperties': False,
                  'properties': {'tasks': FEATURE_SCHEMA}}
FEATURE_SCHEMA['properties']['tasks']['items']['additionalProperties'] = False


def validate_compilable_outline(candidate: dict[str, Any], starter: str | None = None) -> None:
    from .guided import validate_outline, StageValidationError
    from .contracts import review_plan
    validate_outline(candidate)
    review = review_plan(candidate, starter, outline=True)
    if not review.passed:
        raise StageValidationError([(f.code, f.path, f.message) for f in review.findings if f.severity == 'error'])
    if candidate.get('acceptance_policy') != 'evidence_v1' or not backend_evidence(candidate): return
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
    if outline.get('acceptance_policy') != 'evidence_v1' or not backend_evidence(outline):
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
    from .scaffolds import CATALOG
    starter = next((name for name, value in CATALOG.items() if value == request.get('starter')), None)
    identity = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
    draft = copy.deepcopy(saved) if saved and saved.get('request_sha256') == identity and saved.get('task_planning_policy') == POLICY else {
        'schema': 2, 'task_planning_policy': POLICY, 'request_sha256': identity,
        'outline': None, 'tasks': [], 'next_feature': 0}
    if cancel.is_set(): raise InterruptedError('Stopped before guided planning.')
    if request.get('outline_planning_policy') == 'split_v1' and draft.get('outline') is not None:
        try:
            validate_compilable_outline(draft['outline'], starter)
        except ValueError:
            # A pre-upgrade checkpoint can have passed the old, weaker stage gate.
            # Keep its validated scope, but never reuse tasks tied to rejected checks.
            from .outline_planning import validate_scope
            scope = draft.get('scope')
            if not isinstance(scope, dict):
                raise ValueError('Saved acceptance is invalid and no validated scope is available. Start a new unapproved draft.')
            validate_scope(scope)
            draft.update(outline=None, tasks=[], next_feature=0, references={}, acceptance_recovery=True)
            draft.pop('acceptance_draft',None)
            checkpoint(copy.deepcopy(draft))
    if draft['outline'] is None:
        if request.get('outline_planning_policy')=='split_v1':
            from .outline_planning import create_outline
            outline = create_outline(request,generate,checkpoint,draft,cancel)
        else:
            outline = generate(OUTLINE_PROMPT, {**request, 'planning_stage': 'outline'}, validate_compilable_outline)
        validate_compilable_outline(outline, starter)
        draft['outline'] = copy.deepcopy(outline)
        draft.pop('acceptance_recovery', None)
        checkpoint(copy.deepcopy(draft))
    outline = draft['outline']
    validate_compilable_outline(outline, starter)
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
        projected={key:copy.deepcopy(value) for key,value in request.items() if key!='previous_proposal'}
        manifest={'policy':'task_contract_v1','available_fields':sorted(request),
            'omitted_fields':[{'field':'previous_proposal','sha256':hashlib.sha256(json.dumps(request['previous_proposal'],sort_keys=True).encode()).hexdigest()}] if 'previous_proposal' in request else []}
        if request.get('planning_context_policy')=='stage_v1':
            from .stage_context import project_request
            projected,manifest=project_request(request,'feature_tasks')
        target_acceptance={field:[copy.deepcopy(row) for row in outline.get(field,[]) if target in row.get('feature_indexes',[])] for field in ('checks','manual_checks','browser_checks')}
        packet={'request': projected, 'context_manifest':manifest,
            'outline': outline, 'earlier_tasks': earlier, 'target_feature':outline['features'][target],
            'target_acceptance':target_acceptance,
            'planning_stage': 'feature_tasks', 'task_planning_policy': POLICY,
            'target_feature_indexes': [target], 'next_task_index': len(earlier), 'max_new_tasks': maximum,
            'builder_profile': request.get('builder_profile', {}),
            'controller_owned_fields': ['depends_on', 'feature_indexes', 'check_indexes']}
        if request.get('planning_context_policy')=='stage_v1':
            from .stage_context import project_memory,builder_contract
            packet.update(planning_context_policy='stage_v1',planning_memory=project_memory(request,outline,
                {key:outline[key] for key in ('checks','manual_checks','browser_checks','api_contracts') if key in outline},len(outline['features'])))
            packet['builder_profile']=builder_contract(request.get('builder_profile',{}))
        response = generate(FEATURE_PROMPT,packet,validate)
        tasks = compile_tasks(response, outline, earlier, target, maximum, request.get('builder_profile'))
        draft.update(tasks=tasks, next_feature=target+1,
                     references={'tasks': [{'id': 'T'+str(i+1).zfill(3), 'index': i,
                         'feature_indexes': task['feature_indexes'], 'depends_on': task['depends_on'],
                         'check_indexes': task.get('check_indexes', [])} for i, task in enumerate(tasks)]})
        checkpoint(copy.deepcopy(draft))
    if cancel.is_set(): raise InterruptedError('Guided draft saved; final approval review has not run.')
    return {**copy.deepcopy(outline), 'tasks': copy.deepcopy(draft['tasks'])}
