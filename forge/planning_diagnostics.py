"""Finite validation vocabulary and source-free candidate structure."""
from __future__ import annotations
import re
import math
from typing import Any

RULES = {
    'task_endpoint_mismatch': 'A task names an endpoint outside the accepted API/check contract.',
    'duplicate_task': 'A task repeats earlier instructions, outcome, criteria and file scope.',
    'missing_persistence_scenario': 'A declared server persistence feature has no mapped restart read.',
    'duplicate_create_id': 'A new-resource check reuses an undeleted earlier fixture ID.',
    'persistence_seed_state': 'A restart assertion does not match current seeded state.',
    'missing_ui_task': 'Browser actions lack an interface implementation task.',
    'ordering_scenario': 'Ordering lacks a two-record order-sensitive scenario.',
    'check_structure': 'Acceptance checks must be an array of check objects.',
    'acceptance_coverage': 'One or more declared features lack acceptance coverage.',
    'assertion_required': 'An HTTP check lacks a meaningful response assertion.',
    'mutation_example': 'A successful mutation needs concrete request example data.',
    'persistence_evidence': 'A restart check must read a value seeded by an earlier mutation.',
    'restart_evidence': 'Restart must happen immediately before reading saved data, not before creating it.',
    'false_restart': 'A check claims a restart without requesting one.',
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
        for needle,replacement,pointer in (
            ('Outline checks must be an array','check_structure','/checks'),
            ('Every feature needs acceptance check coverage','acceptance_coverage','/features'),
            ('Every check needs contains','assertion_required','/checks'),
            ('Supply concrete nonempty JSON request example','mutation_example','/checks'),
            ('Restart checks must GET a concrete value','persistence_evidence','/checks')):
            if needle in message:code,path=replacement,pointer;break
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
    covered: set[int]=set()
    for field in ('checks','manual_checks','browser_checks'):
        rows=candidate.get(field,[])
        structure: list[dict[str,Any]]=[{'index':index,'feature_indexes':[n for n in row['feature_indexes'][:32] if type(n) is int]}
                   for index,row in enumerate(rows[:32]) if isinstance(row,dict) and isinstance(row.get('feature_indexes'),list)] if isinstance(rows,list) else []
        if field!='checks':result[field.removesuffix('s')+'_structure']=structure
        covered.update(n for row in structure for n in row['feature_indexes'])
    if isinstance(candidate.get('features'),list):
        result['uncovered_feature_indexes']=[n for n in range(min(20,len(candidate['features']))) if n not in covered]
    return result


def latest_planning_run(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate only one recorded run; never mix workspace lifetime failures."""
    start=next((row for row in reversed(records) if row.get('kind')=='job_started' and row.get('data',{}).get('action')=='plan'),None)
    if not start or not start.get('run_id'):return {'available':False}
    selected=[row for row in records if row.get('run_id')==start['run_id']]
    attempts=[row['data'] for row in selected if row.get('kind')=='model_attempt']
    finish: dict[str,Any]=next((row['data'] for row in reversed(selected) if row.get('kind')=='job_finished'),{})
    stages: dict[str,dict[str,Any]]={}
    for attempt in attempts:
        stage=str(attempt.get('planning_stage') or 'unknown')
        counts=stages.setdefault(stage,{'attempts':0,'accepted':0,'rejected':0,'seconds':0.0,'unknown_timings':0})
        counts['attempts']+=1;counts['accepted']+=attempt.get('success') is True
        counts['rejected']+=attempt.get('success') is False
        elapsed=attempt.get('seconds')
        if type(elapsed) in {int,float} and math.isfinite(elapsed) and elapsed>=0:counts['seconds']=round(counts['seconds']+elapsed,3)
        else:counts['unknown_timings']+=1
    for counts in stages.values():
        if counts['unknown_timings']==counts['attempts']:counts['seconds']=None
    return {'available':True,'run_id':start['run_id'],'started':start.get('time'),
        'status':finish.get('status'),'seconds':finish.get('seconds'),
        'recorded_attempts':len(attempts),'reported_attempts':finish.get('model_attempts'),
        'stages':stages,'timeout_seconds':round(sum(a['seconds'] for a in attempts if a.get('transport_kind')=='timeout' and type(a.get('seconds')) in {int,float} and math.isfinite(a['seconds']) and a['seconds']>=0),3),
        'review_codes':sorted({code for attempt in attempts for code in attempt.get('review_codes',[]) if isinstance(code,str)}),
        'history_may_be_partial':len(attempts)!=finish.get('model_attempts')}
