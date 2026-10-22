"""Bounded task-loop evidence. No inference, source execution or state mutation."""
from __future__ import annotations

from typing import Any
import math
from datetime import datetime
from .execution import resume_problem, source_hash, plan_hash
from .tasks import task_packet


def task_readiness(state: dict[str, Any], index: int, files: dict[str, str]) -> dict[str, Any]:
    """Check existing execution boundaries before spending an implementation call."""
    codes = []
    if not state.get('approved'):
        codes.append('approval_required')
    if resume_problem(state, files):
        codes.append('checkpoint_mismatch')
    if state.get('next_task') != index:
        codes.append('cursor_mismatch')
    packet: dict[str, Any] = {}
    try:
        packet = task_packet(state['plan'], index, state.get('next_task', 0))
    except (KeyError, IndexError, TypeError, ValueError):
        codes.append('task_contract_not_ready')
    return {'schema': 1, 'task': index + 1, 'passed': not codes, 'review_codes': codes,
            'plan_sha256': plan_hash(state.get('plan') or {}), 'source_sha256': source_hash(files),
            'structured': bool(packet.get('structured')), 'dependency_count': len(packet.get('depends_on', [])),
            'editable_file_count': len(packet.get('files', [])), 'criterion_count': len(packet.get('done_when', [])),
            'behavior_verified': False}


def _number(value: Any) -> bool:
    return type(value) in (int, float) and value >= 0 and math.isfinite(value)


def _elapsed(start: Any, finish: Any) -> float | None:
    try:
        left = datetime.fromisoformat(str(start).replace('Z', '+00:00'))
        right = datetime.fromisoformat(str(finish).replace('Z', '+00:00'))
        if left.tzinfo is None or right.tzinfo is None:
            return None
        seconds = (right-left).total_seconds()
        return round(seconds, 3) if seconds >= 0 else None
    except (ValueError, TypeError, OverflowError):
        return None


def latest_execution(records: list[dict[str, Any]], coverage: dict[str, Any] | None = None) -> dict[str, Any]:
    """Summarize the latest retained build/repair, never a lifetime success rate.

    Only later checks of exactly the repair's saved source can validate it.
    Milestone prefixes, static checks and full verification remain distinct.
    Missing starts/ends/timing/usage are explicit; a changed candidate is not a pass.
    """
    rows = [r for r in records[-4000:] if isinstance(r, dict) and isinstance(r.get('data'), dict)]
    starts = [r for r in rows if r.get('kind') == 'job_started'
              and r['data'].get('action') in {'build', 'repair'} and r.get('run_id')]
    candidates = [r for r in rows if isinstance(r.get('run_id'), str) and (
        r.get('kind') == 'job_started' and r['data'].get('action') in {'build', 'repair'} or r.get('kind') in {
        'task_started', 'task_readiness', 'task_saved', 'repair_started', 'repair_finished', 'verification_finished',
        'job_finished'} and (r.get('kind') != 'job_finished' or r['data'].get('action') in {'build', 'repair'})
        or r.get('kind') == 'model_request_started' and r['data'].get('role') == 'coder')]
    if not candidates:
        return {'schema': 1, 'available': False, 'coverage': {'run_start_retained': False}}
    run_id = candidates[-1]['run_id']
    start = next((r for r in reversed(starts) if r['run_id'] == run_id), None)
    selected = [r for r in rows if r.get('run_id') == run_id]
    ends = [r for r in selected if r['kind'] == 'job_finished']
    end = ends[-1] if ends else None
    attempts = [r for r in selected if r['kind'] == 'model_attempt']
    completed_ids = {r['data']['attempt_id'] for r in attempts if isinstance(r['data'].get('attempt_id'), str)}
    requests = [r for r in selected if r['kind'] == 'model_request_started']
    pending = [r for r in requests if isinstance(r['data'].get('attempt_id'), str)
               and r['data']['attempt_id'] not in completed_ids]
    repair_starts = {r['data']['repair_id']: r for r in selected
                     if r['kind'] == 'repair_started' and isinstance(r['data'].get('repair_id'), str)}
    repairs = []
    finished_ids = set()
    for position, row in enumerate(selected):
        if row['kind'] != 'repair_finished':
            continue
        data = row['data']
        identity = data.get('repair_id')
        if not isinstance(identity, str):
            continue
        finished_ids.add(identity)
        repair = {key: data.get(key) for key in ('repair_id', 'stage', 'task', 'status', 'source_changed',
                  'before_source_sha256', 'after_source_sha256', 'seconds', 'model_attempts', 'failure_class')}
        repair.update(start_retained=identity in repair_starts, event_id=row.get('id'), validation='not_retested',
                      validation_event_id=None)
        if data.get('status') in {'failed', 'cancelled'}:
            repair['validation'] = 'repair_failed' if data['status'] == 'failed' else 'interrupted'
        else:
            digest = data.get('after_source_sha256')
            checks = [r for r in selected[position+1:] if digest and r['data'].get('source_sha256') == digest
                      and type(r['data'].get('passed')) is bool
                      and r['kind'] in {'static_inspection', 'milestone_verified', 'verification_finished'}]
            behavior = [r for r in checks if r['kind'] != 'static_inspection']
            observed = (behavior or checks)
            if observed:
                check = observed[-1]
                prefix = {'static_inspection': 'static', 'milestone_verified': 'milestone',
                          'verification_finished': 'behavioral'}[check['kind']]
                repair['validation'] = ('environment_failure' if check['data'].get('failure_kind') == 'environment'
                                        else prefix + ('_pass' if check['data']['passed'] else '_fail'))
                repair['validation_event_id'] = check.get('id')
        repairs.append(repair)
    for identity, row in repair_starts.items():
        if identity not in finished_ids:
            repairs.append({'repair_id': identity, 'stage': row['data'].get('stage'), 'task': row['data'].get('task'),
                            'status': 'unfinished', 'validation': 'interrupted_or_in_progress',
                            'event_id': row.get('id'), 'start_retained': True})
    model_rows: dict[tuple[Any, Any], dict[str, Any]] = {}
    for row in attempts:
        data = row['data']; key = (data.get('provider'), data.get('model'))
        if not all(value is None or isinstance(value, str) for value in key):
            continue
        model = model_rows.setdefault(key, {'provider': key[0], 'model': key[1], 'attempts': 0,
                                           'accepted_responses': 0, 'failed_responses': 0, 'seconds': 0.0,
                                           'unknown_timings': 0, 'transport_attempts': 0, 'transport_unknown': 0,
                                           'prompt_tokens': 0, 'completion_tokens': 0, 'usage_requests': 0,
                                           'prompt_tokens_requests': 0, 'completion_tokens_requests': 0,
                                           'rejected_code_responses': 0})
        model['attempts'] += 1
        model['accepted_responses'] += data.get('success') is True
        model['failed_responses'] += data.get('success') is False
        model['transport_attempts'] += data.get('transport_attempted') is True
        model['transport_unknown'] += data.get('transport_attempted') is None
        if _number(data.get('prompt_tokens')) or _number(data.get('completion_tokens')):
            model['usage_requests'] += 1
        for field in ('prompt_tokens', 'completion_tokens'):
            if _number(data.get(field)):
                model[field] += data[field]
                model[field+'_requests'] += 1
        if _number(data.get('seconds')):
            model['seconds'] += data['seconds']
        else:
            model['unknown_timings'] += 1
    for model in model_rows.values():
        model['seconds'] = None if model['unknown_timings'] == model['attempts'] else round(model['seconds'], 3)
        for field in ('prompt_tokens', 'completion_tokens'):
            if model[field+'_requests'] == 0:
                model[field] = None
        model['rejected_code_responses'] = sum(r['kind'] == 'code_response_rejected'
            and r['data'].get('provider') == model['provider'] and r['data'].get('model') == model['model'] for r in selected)
    active_tasks: dict[int, dict[str, Any]] = {}
    task_results = []
    for row in selected:
        data = row['data']; task = data.get('task')
        if type(task) is not int or task < 1:
            continue
        if row['kind'] == 'task_started':
            active_tasks[task] = row
        elif row['kind'] == 'task_saved':
            first = active_tasks.pop(task, None)
            task_results.append({'task': task, 'event_id': row.get('id'), 'start_retained': first is not None,
                'seconds': _elapsed(first.get('time'), row.get('time')) if first else None,
                'disposition': data.get('disposition'), 'behavior_verified': False,
                'source_sha256': data.get('after_sha256')})
    reported = end['data'].get('model_attempts') if end else None
    gaps = len(records) > 4000 or bool(coverage and (coverage.get('prefix_omitted') or coverage.get('record_limit_omitted')
                or coverage.get('malformed_records') or coverage.get('trailing_partial_record')
                or coverage.get('duplicate_event_ids') or coverage.get('out_of_order_timestamps')
                or coverage.get('export_records_omitted')
                or coverage.get('complete_since_tracking_started') is False))
    return {'schema': 1, 'available': True, 'run_id': run_id, 'action': start['data'].get('action') if start else None,
            'started': start.get('time') if start else None, 'finished': end.get('time') if end else None,
            'status': end['data'].get('status') if end else None,
            'seconds': end['data'].get('seconds') if end else None, 'attempts': len(attempts),
            'started_requests': len(requests), 'pending_requests': [{key: r['data'].get(key) for key in (
                'attempt_id', 'provider', 'model', 'execution_stage', 'repair_id', 'task', 'timeout_seconds')} for r in pending[-32:]],
            'pending_request_details_omitted': max(0, len(pending)-32),
            'requests_without_identity': sum(not isinstance(r['data'].get('attempt_id'), str) for r in requests),
            'reported_attempts': reported, 'unattributed_attempts': sum(not r['data'].get('execution_stage') for r in attempts),
            'model_results': list(model_rows.values())[-32:], 'model_details_omitted': max(0, len(model_rows)-32),
            'repairs': repairs[-100:],
            'repair_details_omitted': max(0, len(repairs)-100),
            'tasks_started': sum(r['kind'] == 'task_started' for r in selected),
            'tasks_saved': sum(r['kind'] == 'task_saved' for r in selected),
            'task_results': task_results[-200:], 'task_details_omitted': max(0, len(task_results)-200),
            'decisions': [{'event_id': r.get('id'), 'code': r['data'].get('code'), 'stage': r['data'].get('stage')}
                          for r in selected if r['kind'] == 'recovery_decision'][-100:],
            'readiness_failures': sum(r['kind'] == 'task_readiness' and r['data'].get('passed') is False for r in selected),
            'coverage': {'run_start_retained': start is not None, 'run_end_retained': end is not None,
                         'input_records_omitted': max(0, len(records)-4000),
                         'history_gaps': gaps, 'attempt_details_complete': reported == len(attempts) if _number(reported) else None},
            'meaning': 'Retained controller evidence for one run. Accepted replies and changed source are not behavioral success. '
                       'Repair validation describes a later matching-source check, not causality or current source freshness.'}


def loop_guards() -> dict[str, Any]:
    """Fixed evidence-classification probes; never execute a generated app."""
    def event(kind: str, **data: Any) -> dict[str, Any]:
        return {'kind': kind, 'run_id': 'fixture-run', 'id': kind, 'data': data}
    base = [event('job_started', action='build'), event('repair_started', repair_id='r'),
            event('repair_finished', repair_id='r', status='candidate_saved', after_source_sha256='abc', source_changed=True)]
    cases = [('changed_not_verified', [], 'not_retested'),
             ('static_not_behavior', [event('static_inspection', passed=True, source_sha256='abc')], 'static_pass'),
             ('same_source_pass', [event('verification_finished', passed=True, source_sha256='abc')], 'behavioral_pass'),
             ('other_source_ignored', [event('verification_finished', passed=True, source_sha256='different')], 'not_retested'),
             ('prefix_not_full', [event('milestone_verified', passed=True, source_sha256='abc')], 'milestone_pass'),
             ('environment_not_app', [event('verification_finished', passed=False, source_sha256='abc', failure_kind='environment')], 'environment_failure')]
    results = []
    for name, extra, expected in cases:
        observed = latest_execution(base+extra)['repairs'][0]['validation']
        results.append({'code': name, 'passed': observed == expected,
                        'expected_validation': expected, 'observed_validation': observed})
    return {'status': 'passed' if all(row['passed'] for row in results) else 'failed',
            'case_count': len(results), 'cases': results, 'executed': False, 'inference_tested': False}
