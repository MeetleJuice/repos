"""Read-only, bounded investigations and source-free diagnostic evidence bundles.

This collector never imports generated code, runs project commands, contacts cloud
providers, reads credential files, or changes a project's approval/evidence state.
Recorded failures are facts; their possible causes remain hypotheses.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import time
from typing import Any, Callable
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile

from . import __version__
from .diagnostics import redact, resource_snapshot, sanitize_event_data
from .history import totals_for
from .providers import CLOUD_ORDER, CONFIG_NAMES, environment_value, key_for

MAX_PROJECTS = 100
MAX_DETAILS = 25
MAX_STATE_BYTES = 2_000_000
MAX_HISTORY_BYTES = 2_000_000
MAX_HISTORY_RECORDS = 4000
MAX_REPORT_BYTES = 24_000_000
ACTIVE = {'planning', 'building', 'checking', 'repairing', 'queued'}

# Source bodies, model summaries, user observations and arbitrary metadata never
# become event payloads simply because they appeared in a project history file.
EVENT_FIELDS = {
    'model_request_started': {'provider', 'model', 'role', 'recovery_path'},
    'model_attempt': {'provider', 'model', 'role', 'success', 'category', 'seconds',
                      'prompt_tokens', 'completion_tokens', 'requested_max_output_tokens',
                      'max_output_tokens', 'output_tokens', 'observed_output_tokens',
                      'finish_reason', 'recovery_path', 'transport_attempted', 'http_status',
                      'transport_kind', 'request_characters', 'request_sha256', 'thinking_budget',
                      'reserved_text_output_tokens', 'estimated_required_output_tokens', 'input_estimate_tokens',
                      'max_output_ceiling', 'capability_estimated', 'timeout_seconds', 'input_characters',
                      'visible_output_tokens', 'thinking_tokens', 'ollama_load_seconds', 'ollama_eval_seconds',
                      'ollama_prompt_seconds', 'ollama_tokens_per_second', 'failure_class', 'error_category',
                      'review_codes', 'review_findings', 'candidate_shape', 'response_sha256', 'proposal_valid',
                      'planning_stage', 'task_planning_policy', 'target_feature_indexes', 'configured_num_ctx', 'structured_outputs_requested',
                      'response_format_mode', 'response_model', 'response_provider', 'api_family'},
    'job_started': {'action', 'execute', 'runtime', 'max_repairs', 'milestones'},
    'job_finished': {'action', 'status', 'seconds', 'next_task', 'model_attempts',
                     'repairs_used', 'repair_count_total'},
    'job_interrupted': {'reason'},
    'task_started': {'task', 'title'},
    'task_saved': {'task', 'task_id', 'index', 'source_sha256', 'changed_files',
                    'behavior_verified', 'static_passed', 'source_changed', 'syntax_passed',
                    'before_sha256', 'after_sha256', 'task_packet', 'finish_gate', 'disposition'},
    'task_finish_gate': {'passed', 'task', 'task_id', 'issues', 'source_sha256'},
    'task_context_expanded': {'included_files', 'remaining'},
    'code_response_rejected': {'provider', 'model', 'reason', 'files_replaced'},
    'files_committed': {'changed_files', 'deleted_files', 'source_sha256', 'repair', 'task',
                        'before_source_sha256', 'after_source_sha256'},
    'file_operation_failed': {'operation', 'files', 'error_type', 'exception_type', 'errno', 'reason', 'task'},
    'checkpoint_saved': {'checkpoint_id', 'label', 'next_task'},
    'checkpoint_restored': {'checkpoint_id', 'next_task'},
    'static_inspection': {'complete', 'passed', 'issues', 'source_sha256', 'repair_budget_remaining'},
    'verification_started': {'source_sha256', 'runtime'},
    'verification_finished': {'passed', 'runtime', 'failure_kind', 'source_sha256', 'phases',
                              'exit_code', 'command_template', 'command_paths_redacted', 'execution_seconds',
                              'failure_class', 'error_category'},
    'milestone_verified': {'task', 'passed', 'checks', 'runtime', 'source_sha256', 'failure_kind'},
    'export_prepared': {'source_sha256', 'effective_status', 'file_count'},
    'stop_requested': {'in_flight_output_will_be_discarded'},
    'proposal_review': {'passed', 'findings'},
    'guided_plan_checkpoint': {'stage', 'next_feature', 'tasks', 'features',
                               'features_planned', 'acceptance_features_planned', 'features_total', 'task_planning_policy'},
    'proposal_approved': {'tasks', 'http_checks', 'browser_checks', 'manual_checks'},
}
OPERATION_FIELDS = {'version', 'pid', 'returncode', 'healthy', 'seconds', 'phase', 'exception_type',
                    'code', 'rows', 'planned_probes', 'generation_requested', 'cloud_consent', 'passed',
                    'location', 'line', 'launch_id', 'reason', 'event_count', 'method', 'status', 'route',
                    'report_id', 'bytes', 'findings', 'safe_checks_only', 'port', 'update_restart',
                    'workspace_imported', 'error_type', 'operation', 'task', 'task_id', 'file', 'files',
                    'app_version', 'available', 'source_sha256', 'recorded_events', 'provider', 'model',
                    'role', 'success', 'category', 'duration_seconds', 'request_count', 'models',
                    'missing_setup', 'catalogue_available', 'supervised', 'previous_version', 'new_version',
                    'frames', 'errno', 'failure_class', 'requested_max_output_tokens', 'num_ctx', 'timeout_seconds',
                    'characters', 'idea_sha256', 'project_created', 'current_version', 'release_version', 'sha256',
                    'pending_health_check', 'backup_saved', 'providers'}

LOOP_FIELDS = {'repair_id', 'execution_stage', 'task', 'attempt_id'}
EVENT_FIELDS['model_attempt'] |= LOOP_FIELDS | {'schema_sha256', 'schema_version', 'planning_context_policy',
    'context_manifest_sha256','planning_memory_sha256','required_context_tokens','context_shortfall_tokens','effective_context_tokens'}
EVENT_FIELDS['model_attempt'] |= {'known_contracts','accepted_features','check_count'}
EVENT_FIELDS['guided_plan_checkpoint'] |= {'memory'}
EVENT_FIELDS['model_request_started'] |= LOOP_FIELDS | {'requested_max_output_tokens', 'timeout_seconds', 'request_sha256'}
EVENT_FIELDS['code_response_rejected'] |= LOOP_FIELDS
EVENT_FIELDS['task_readiness'] = {'schema', 'task', 'passed', 'review_codes', 'plan_sha256', 'source_sha256',
    'structured', 'dependency_count', 'editable_file_count', 'criterion_count', 'behavior_verified'}
EVENT_FIELDS['handoff_prepared'] = LOOP_FIELDS | {'policy', 'included_files', 'omitted_files', 'source_characters',
    'request_characters', 'request_sha256', 'prompt_sha256', 'retrievals_remaining'}
EVENT_FIELDS['repair_started'] = LOOP_FIELDS | {'stage', 'before_source_sha256', 'behavior_verified'}
EVENT_FIELDS['repair_finished'] = LOOP_FIELDS | {'stage', 'status', 'before_source_sha256', 'after_source_sha256',
    'source_changed', 'behavior_verified', 'failure_class', 'seconds', 'model_attempts'}
EVENT_FIELDS['recovery_decision'] = {'code', 'stage', 'source_sha256', 'repair_budget_remaining'}
EVENT_FIELDS['diagnostic_session_started'] = {'session_id', 'mode'}
EVENT_FIELDS['diagnostic_session_finished'] = {'session_id', 'status', 'report_id', 'seconds'}


EVENT_FIELDS['system_test_result'] = EVENT_FIELDS['model_attempt'] | {
    'code','status','report_id','exception_type','models_count','generation_tested','response_received','restart_read','cases','case_count','inference_tested',
    'project_id','plan_sha256','reviewer_version','passed','review_codes','findings','restart_check_indexes','duplicate_task_groups','business_http_checks','executed','approval_changed',
    'response_accepted','http_response_received','run_id','available','attempts','reported_attempts','tasks_started','tasks_saved',
    'readiness_failures','coverage','repairs','model_results','model_details_omitted','unattributed_attempts','repair_details_omitted','recorded_status','decisions',
    'task_results','task_details_omitted','started_requests','pending_requests','pending_request_details_omitted','requests_without_identity',
    'generated_code_executed','project_content_sent','probe_version'}


def _safe_recorder(snapshot: dict[str, Any]) -> dict[str, Any]:
    safe = dict(snapshot)
    rows = []
    excluded = 0
    for record in snapshot.get('records', []):
        if not isinstance(record, dict) or record.get('kind') == 'journal' or record.get('origin') == 'model_report':
            excluded += 1
            continue
        data = record.get('data')
        if not isinstance(data, dict):
            excluded += 1
            continue
        kind = str(record.get('kind', 'unknown'))
        fields = set(data) if kind in {'hardware_sample', 'resource_pressure', 'local_runtime_sample'} else EVENT_FIELDS.get(kind, OPERATION_FIELDS)
        row = {key: record.get(key) for key in ('schema', 'id', 'time', 'kind', 'project_id', 'run_id', 'origin', 'sequence', 'record_sha256')}
        row['data'] = sanitize_event_data(str(kind), {key: value for key, value in data.items() if key in fields}, str(record.get('origin', 'controller')))
        rows.append(row)
    safe['records'] = rows
    safe['export_privacy'] = {'excluded_prose_records': excluded,
                              'meaning': 'Journal/model prose and unselected payload fields excluded. Hashes identify original local records; redacted exported payloads are not hash-chain originals.'}
    return safe


def _scrub(value: Any, depth: int = 0) -> Any:
    """Preserve explicitly bounded report lists while using recorder redaction.

    The recorder bounds arbitrary event arrays to 256 items; a collected report
    deliberately contains more than 256 *records*. Applying that arbitrary-input
    limit to the entire report would silently discard already bounded evidence.
    """
    if depth > 24:
        return '[report nesting limit]'
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            probe = redact({str(key): None})
            safe_key, marker = next(iter(probe.items()))
            result[safe_key] = marker if marker == '[excluded]' else _scrub(item, depth + 1)
        return result
    if isinstance(value, (list, tuple)):
        return [_scrub(item, depth + 1) for item in value]
    return redact(value)


def _json(value: Any) -> bytes:
    return json.dumps(_scrub(value), ensure_ascii=False, indent=2, allow_nan=False).encode('utf-8')


def _text(value: Any, length: int = 1000) -> str:
    return str(redact(str(value)))[:length]


def _failure_signatures(value: Any) -> list[str]:
    """Known symptom tags only; never return a captured free-text fragment."""
    text = str(value).lower()
    patterns = {'urllib_urlopen_method_keyword': ('urlopen', 'unexpected keyword argument', 'method'),
                'sqlite_missing_table': ('no such table:',),
                'json_parse_failure': ('json', 'expecting'),
                'syntax_error': ('syntaxerror',),
                'output_budget_failure': ('truncated',),
                'scope_rejection': ('outside', 'scope'),
                'http_403': ('403',),
                'connection_failure': ('connection', 'failed')}
    return [name for name, parts in patterns.items() if all(part in text for part in parts)]


def _read_json(path: Path, limit: int) -> Any:
    if path.is_symlink() or not path.is_file():
        raise OSError('Expected a regular local evidence file.')
    with path.open('rb') as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError('Evidence file exceeds its bounded read limit.')
    return json.loads(raw)


def _workspace_health(home: Path, projects: Path) -> dict[str, Any]:
    return {'home_exists': home.is_dir(), 'projects_exist': projects.is_dir(),
            'projects_readable': os.access(projects, os.R_OK), 'home_writable_permission': os.access(home, os.W_OK),
            'generated_databases_inspected': False,
            'meaning': 'Read-only existence/permission checks; no probe files created. Permission bits do not guarantee a future write. Generated app databases were not opened.'}


def _update_health(home: Path, updater: Any) -> dict[str, Any]:
    directory = home / 'updates'
    status = updater.status() if updater else {'available': False}
    result = {'status': sanitize_event_data('update_state', status),
              'managed_supervisor': os.environ.get('FOUNDRY_SUPERVISED') == '1',
              'current_pointer_present': (directory / 'current.json').exists(),
              'pending_update_present': (directory / 'pending.json').exists(),
              'network_checked': False, 'pointer_valid': None, 'selected_program_present': None}
    pointer = directory / 'current.json'
    if pointer.exists():
        saved = _read_json(pointer, 20000)
        version = saved.get('version') if isinstance(saved, dict) else None
        valid = isinstance(version, str) and bool(re.fullmatch(r'\d{1,3}\.\d{1,3}\.\d{1,3}', version))
        result['pointer_valid'] = valid
        if valid and isinstance(version, str):
            result['selected_version'] = version
            result['selected_program_present'] = (directory / 'versions' / version / 'run.py').is_file()
    return result


def _git_info(root: Path) -> dict[str, Any]:
    """Read only the commit and modification count; never return remotes/paths."""
    if not (root / '.git').exists():
        return {'available': False, 'commit': None, 'reason': 'Source ZIP has no Git metadata.'}
    try:
        commit = subprocess.run(['git', '-C', str(root), 'rev-parse', 'HEAD'],
                                capture_output=True, text=True, timeout=3, check=False)
        value = commit.stdout.strip()
        if commit.returncode or not re.fullmatch(r'[a-fA-F0-9]{40,64}', value):
            return {'available': False, 'commit': None, 'reason': 'Git commit unavailable.'}
        dirty = subprocess.run(['git', '-C', str(root), 'status', '--porcelain', '--untracked-files=no'],
                               capture_output=True, text=True, timeout=3, check=False)
        return {'available': True, 'commit': value, 'tracked_modified_files': len(dirty.stdout.splitlines())
                if dirty.returncode == 0 else None}
    except (OSError, subprocess.TimeoutExpired):
        return {'available': False, 'commit': None, 'reason': 'Git unavailable or timed out.'}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req: Any, fp: Any, code: int, msg: str,
                         headers: Any, newurl: str) -> Any:
        fp.close()
        raise ValueError('Diagnostic loopback probe refused a redirect.')


def _ollama_probe(route: str = '/api/tags') -> dict[str, Any]:
    """A catalogue GET only: no model loading, inference, credentials or proxies."""
    base = os.getenv('OLLAMA_URL', 'http://127.0.0.1:11434').rstrip('/')
    if route not in {'/api/tags','/api/ps','/api/version'}:raise ValueError('Unsupported diagnostic runtime route.')
    try:
        parsed = urllib.parse.urlsplit(base)
        port = parsed.port
        if (parsed.scheme != 'http' or parsed.hostname not in {'127.0.0.1', 'localhost', '::1'}
                or parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.path not in {'', '/'} or port is not None and not 1 <= port <= 65535):
            raise ValueError('Ollama diagnostic probe requires a direct loopback HTTP endpoint.')
    except ValueError:
        return {'status': 'configuration_error', 'failure': 'Unsafe or invalid local endpoint; no request sent.'}
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
        request = urllib.request.Request(base + route, headers={'User-Agent': 'IdeaFoundry/' + __version__ + ' diagnostic-catalogue'})
        with opener.open(request, timeout=2) as response:
            raw = response.read(200001)
        if len(raw) > 200000:
            raise ValueError('Local model catalogue exceeds diagnostic limit.')
        data = json.loads(raw)
        if route=='/api/version':
            version=data.get('version') if isinstance(data,dict) else None
            return {'status':'available' if isinstance(version,str) and re.fullmatch(r'[A-Za-z0-9_.+-]{1,60}',version) else 'unknown',
                    'version':version if isinstance(version,str) and re.fullmatch(r'[A-Za-z0-9_.+-]{1,60}',version) else None,'generation_tested':False}
        models = data.get('models') if isinstance(data, dict) else None
        if not isinstance(models, list):
            raise ValueError('Local model catalogue has an unexpected shape.')
        rows = []
        for item in models[:100]:
            if isinstance(item, dict) and isinstance(item.get('name'), str):
                if route=='/api/ps':
                    rows.append({'model':item['name'],**{key:item[key] for key in ('size','size_vram','context_length')
                        if type(item.get(key)) is int and 0<=item[key]<=10**18}})
                else:rows.append({key: item[key] for key in ('name', 'size', 'digest') if key in item})
        return {'status': 'available', 'models': rows, 'models_omitted': max(0, len(models) - 100),
                'generation_tested': False, 'meaning': 'Loaded local model metadata only; no inference or GPU-fit claim.' if route=='/api/ps' else 'Catalogue connectivity only; no GPU fit or inference quota claim.'}
    except urllib.error.HTTPError as exc:
        status = exc.code
        exc.close()
        return {'status': 'unavailable', 'failure': 'http', 'http_status': status}
    except (OSError, ValueError, TimeoutError):
        return {'status': 'unavailable', 'failure': 'connection_or_catalogue', 'generation_tested': False}


def ollama_health() -> dict[str, Any]:
    """Public safe-check seam for integration tests and the diagnostic endpoint."""
    return _ollama_probe()


def ollama_process_health() -> dict[str, Any]:
    return _ollama_probe('/api/ps')


def _environment() -> dict[str, Any]:
    optional: dict[str, str | None] = {}
    for name in ('playwright', 'mypy'):
        try:
            optional[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            optional[name] = None
    return {'python': platform.python_version(), 'implementation': platform.python_implementation(),
            'system': platform.system(), 'release': platform.release(), 'machine': platform.machine(),
            'python_supported': sys.version_info >= (3, 11), 'optional_dependencies': optional,
            'credential_presence': {provider: bool(key_for(provider)) for provider in CLOUD_ORDER},
            'configuration_presence': {name: bool(environment_value(name)) for name in CONFIG_NAMES},
            'cloud_providers': list(CLOUD_ORDER), 'cloud_generation_probed': False,
            'privacy': 'No environment values, user/host name, .env file, IP address or install path included.'}


def _safe_history(directory: Path) -> dict[str, Any]:
    path = directory / 'workflow-history.jsonl'
    if not path.exists():
        return {'records': [], 'coverage': {'available': False, 'reason': 'No recorded project history.'}}
    if path.is_symlink():
        raise OSError('History symbolic links are excluded.')
    total = path.stat().st_size
    with path.open('rb') as stream:
        stream.seek(max(0, total - MAX_HISTORY_BYTES))
        raw = stream.read(MAX_HISTORY_BYTES + 1)
    prefix_omitted = total > MAX_HISTORY_BYTES
    if prefix_omitted:
        raw = raw.partition(b'\n')[2]
    lines = raw.splitlines()
    records: list[dict[str, Any]] = []
    malformed = 0
    unknown = 0
    for line in lines[-MAX_HISTORY_RECORDS:]:
        try:
            item = json.loads(line)
            if not isinstance(item, dict) or not isinstance(item.get('data'), dict):
                raise ValueError('Invalid event')
            kind = item.get('kind')
            if kind not in EVENT_FIELDS:
                unknown += 1
                continue
            records.append({**{key: item.get(key) for key in ('id', 'time', 'run_id', 'kind', 'origin')},
                            'data': sanitize_event_data(kind, {key: value for key, value in item['data'].items() if key in EVENT_FIELDS[kind]}, str(item.get('origin', 'controller')))})
        except (ValueError, UnicodeError):
            malformed += 1
    ids = [item['id'] for item in records if isinstance(item.get('id'), str)]
    stamps = []
    unknown_times = 0
    for item in records:
        try:
            stamp = datetime.fromisoformat(str(item.get('time', '')).replace('Z', '+00:00'))
            if stamp.tzinfo is None:
                raise ValueError('Unzoned timestamp')
            stamps.append(stamp)
        except ValueError:
            unknown_times += 1
    return {'records': _scrub(records), 'coverage': {'available': True, 'read_bytes': len(raw),
            'total_bytes': total, 'prefix_omitted': prefix_omitted,
            'record_limit_omitted': max(0, len(lines) - MAX_HISTORY_RECORDS),
            'malformed_records': malformed, 'unselected_event_kinds': unknown,
            'duplicate_event_ids': len(ids) - len(set(ids)),
            'out_of_order_timestamps': sum(stamps[index] < stamps[index - 1] for index in range(1, len(stamps))),
            'unknown_timestamps': unknown_times,
            'trailing_partial_record': bool(raw and not raw.endswith(b'\n')),
            'meaning': 'Bounded read-only controller history; journal prose, user notes and source payloads excluded.'}}


def _launcher_evidence(home: Path) -> dict[str, Any]:
    """Independent supervisor metadata remains useful after a server crash."""
    directory = home / 'diagnostics'
    records = []
    missing = []
    malformed = 0
    truncated = False
    omitted_records = 0
    if directory.is_symlink():
        raise OSError('Diagnostic directory symbolic links are excluded.')
    for name in ('launcher.jsonl.1', 'launcher.jsonl'):
        path = directory / name
        if not path.exists():
            missing.append(name)
            continue
        if path.is_symlink():
            raise OSError('Supervisor history symbolic links are excluded.')
        with path.open('rb') as stream:
            size = path.stat().st_size
            stream.seek(max(0, size - 1_000_000))
            raw = stream.read(1_000_001)
        if size > 1_000_000:
            raw = raw.partition(b'\n')[2]
            truncated = True
        lines = raw.splitlines()
        omitted_records += max(0, len(lines) - 2000)
        for line in lines[-2000:]:
            try:
                record = json.loads(line)
                if not isinstance(record, dict) or not isinstance(record.get('data'), dict):
                    raise ValueError('Invalid supervisor event')
                records.append({**{key: record.get(key) for key in ('schema', 'id', 'time', 'origin', 'kind')},
                                'data': sanitize_event_data(str(record.get('kind')), {key: value for key, value in record['data'].items() if key in OPERATION_FIELDS}, str(record.get('origin', 'independent_supervisor')))})
            except (ValueError, UnicodeError):
                malformed += 1
    session = None
    if (directory / 'launcher-session.json').exists():
        result = _read_json(directory / 'launcher-session.json', 20000)
        if isinstance(result, dict):
            session = {key: result.get(key) for key in ('status', 'pid', 'launch_id', 'returncode')}
    return {'records': records[-4000:], 'session': session,
            'coverage': {'available': bool(records), 'missing_files': missing, 'malformed_records': malformed,
                         'prefix_omitted': truncated, 'record_limit_omitted': omitted_records},
            'meaning': 'Independent supervisor metadata, not raw console output. An unfinished prior session establishes a missing clean end record, not the cause of termination. Older launchers may have no such evidence. Boot/session authentication nonces are excluded.'}


def _build_identity(root: Path) -> dict[str, Any]:
    path = root / 'forge' / 'build-info.json'
    if not path.exists():
        return {'available': False, 'reason': 'No packaged source identity is available.'}
    raw = _read_json(path, 20000)
    if not isinstance(raw, dict):
        raise ValueError('Invalid packaged identity')
    return {'available': True, **{key: raw.get(key) for key in ('schema', 'version', 'source_commit',
                                                              'tracked_modified_files', 'source_tree_sha256', 'source_file_count')},
            'meaning': 'Packager-recorded source identity; not a digital signature. Dirty state is reported explicitly.'}


def _project_detail(bench: Any, state: dict[str, Any], directory: Path) -> dict[str, Any]:
    from .run_diagnostics import latest_execution
    plan = state.get('plan') or {}
    current_history = _safe_history(directory)
    result = state.get('checks') or {}
    checks = []
    for index, check in enumerate(plan.get('checks', [])[:100]):
        if not isinstance(check, dict):
            continue
        path = str(check.get('path', ''))
        checks.append({'index': index,
                       'name_sha256': hashlib.sha256(str(check.get('name', '')).encode()).hexdigest(),
                       **{key: check[key] for key in ('method', 'status', 'restart_before', 'feature_indexes') if key in check},
                       'path': path.split('?', 1)[0], 'path_query_omitted': '?' in path})
    tasks = [sanitize_event_data('task_metadata', {key: task[key] for key in ('id', 'title', 'files', 'depends_on', 'feature_indexes', 'check_indexes') if key in task})
             for task in plan.get('tasks', [])[:200] if isinstance(task, dict)]
    verification: dict[str, Any]
    try:
        with bench.lock:
            verification = bench.evidence(state['id'])
    except (OSError, ValueError, KeyError, TypeError) as exc:
        verification = {'automated_evidence_current': None, 'manual_acceptance_current': None,
                        'reason': 'Current source identity could not be checked: ' + type(exc).__name__}
    return {'project_id': state['id'], 'status': state.get('status'), 'title_sha256': hashlib.sha256(str(state.get('title', '')).encode()).hexdigest(),
            'updated': state.get('updated'), 'approved': state.get('approved') is True,
            'next_task': state.get('next_task'), 'task_count': len(plan.get('tasks', [])),
            'planner': state.get('planner'), 'coder': state.get('coder'),
            'error_recorded': bool(state.get('error')), 'error_sha256': hashlib.sha256(str(state.get('error', '')).encode()).hexdigest() if state.get('error') else None,
            'error_symptom_tags': _failure_signatures(state.get('error', '')),
            'tasks': tasks, 'acceptance_check_metadata': checks,
            'model_totals': totals_for(state), 'history': current_history,
            'attempts': [sanitize_event_data('model_attempt', {key: value for key, value in attempt.items()
                         if key in EVENT_FIELDS['model_attempt']}) for attempt in state.get('model_calls', [])[-256:] if isinstance(attempt, dict)],
            'attempt_coverage': {'retained_in_state': len(state.get('model_calls', [])),
                                 'export_limit': 256, 'earlier_attempts_may_exist': True},
            'planning': _planning_metadata(state,current_history.get('records',[])),
            'execution': latest_execution(current_history.get('records', []), current_history.get('coverage')),
            'verification': verification,
            'test_evidence': {**{key: result.get(key) for key in ('passed', 'runtime', 'failure_kind', 'exit_code',
                                                               'command_template', 'command_paths_redacted', 'execution_seconds')},
                              'phases': [{key: value for key, value in phase.items() if key in {'phase', 'passed', 'behavior_passed', 'workspace_cleanup', 'tests_run', 'http_checks', 'asset_checks', 'app_calls', 'failure_kind', 'timed_out'}}
                                         for phase in result.get('phases', [])[:30] if isinstance(phase, dict)],
                              'log_characters': len(str(result.get('log', ''))),
                              'log_sha256': hashlib.sha256(str(result.get('log', '')).encode()).hexdigest(),
                              'log_symptom_tags': _failure_signatures(result.get('log', '')),
                              'log_exported': False,
                              'meaning': 'Recorded result; verification object states current source identity. Free-text logs/diagnoses are excluded because they can echo application data or unknown credentials.'},
            'preflight': sanitize_event_data('static_inspection', {key: value for key, value in (state.get('preflight') or {}).items()
                          if key in {'passed', 'issues', 'complete'}}),
            'privacy': 'Idea, source, model transcripts, sample-data bodies and manual observation notes excluded.'}


def _planning_metadata(state: dict[str, Any], records: list[dict[str,Any]] | None = None) -> dict[str, Any]:
    from .planning_diagnostics import candidate_shape, latest_planning_run
    from .coherence import audit_plan
    draft = state.get('guided_draft') or {}
    outline = draft.get('outline') or draft.get('scope') or {}
    digest = draft.get('request_sha256')
    return {'current_review':audit_plan(state['plan'],state.get('starter')) if isinstance(state.get('plan'),dict) else {'available':False},
            'stored_review_passed':(state.get('plan_review') or {}).get('passed'),
            'latest_run':latest_planning_run(records or []),
            'mode': state.get('planning_mode') if state.get('planning_mode') in {'guided', 'single'} else None,
            'memory':sanitize_event_data('planning_memory', {key:value for key,value in (
                (draft.get('acceptance_draft') or {}).get('planning_memory') or {}).items() if key in {
                'schema','policy','request_sha256','scope_sha256','accepted_prefix_sha256','accepted_features','check_count','known_contracts'}}),
            'previous_draft_retained':isinstance(state.get('previous_guided_draft'),dict),
            'builder_profile': sanitize_event_data('builder_profile', {key: value for key, value in (state.get('builder_profile') or {}).items()
                if key in {'schema', 'max_editable_files', 'max_feature_indexes', 'smallest_output_ceiling', 'available_files', 'protected_existing_files'}}),
            'draft': {'task_planning_policy': 'compiled_v1' if draft.get('task_planning_policy') == 'compiled_v1' else None,
                      'features_planned': draft.get('next_feature'),
                      'feature_count': len(outline.get('features', [])),
                      'acceptance_features_planned': (draft.get('acceptance_draft') or {}).get('next_feature',0),
                      'acceptance': candidate_shape({**outline,**(draft.get('acceptance_draft') or {}).get('fields',{})}),
                      'request_sha256': digest if isinstance(digest, str) and re.fullmatch(r'[a-f0-9]{64}', digest) else None,
                      **candidate_shape({**outline, 'tasks': draft.get('tasks', [])})},
            'failed_candidate': candidate_shape(state.get('failed_candidate')),
            'retained_proposal': candidate_shape(state.get('plan')),
            'proposal_approved': state.get('approved') is True,
            'approved_plan': candidate_shape(state.get('plan') if state.get('approved') is True else None),
            'meaning': 'Counts and declared references only. No prompt, source or free-text candidate content. Draft work is unapproved.'}


def collect_report(bench: Any, program_root: Path, updater: Any = None,
                   project_id: str | None = None, *, test_snapshot: dict[str, Any] | None = None) -> dict[str, Any]:
    """Collect independent sections; any failed section remains explicitly unknown."""
    started = time.monotonic()
    report_id = uuid.uuid4().hex
    from .planning_diagnostics import RULES
    evidence: dict[str, Any] = {'validation_rules': RULES}
    findings: list[dict[str, Any]] = []
    missing: list[str] = []
    omissions: list[str] = []

    def finding(code: str, classification: str, component: str, message: str,
                event_ids: list[str] | None = None) -> None:
        findings.append({'id': 'finding-' + str(len(findings) + 1), 'code': code,
                         'classification': classification, 'component': component,
                         'message': message, 'event_ids': event_ids or []})

    def section(name: str, operation: Callable[[], Any]) -> Any:
        try:
            value = operation()
        except Exception as exc:
            # No exception string: arbitrary exception text can contain user data.
            value = {'available': False, 'error_type': type(exc).__name__}
            missing.append(name)
            finding(name + '_unavailable', 'missing_evidence', name,
                    'This collection step failed (' + type(exc).__name__ + '); no result was inferred.')
        evidence[name] = value
        return value

    root = Path(program_root)
    from .system_tests import read_tests
    test_report=section('system_tests',lambda:test_snapshot if test_snapshot is not None else read_tests(bench.root.parent/'diagnostics'/'system-tests-v1.json',bool(getattr(bench,'test_busy',False))))
    section('local_runtime',ollama_process_health)
    section('local_runtime_version',lambda:_ollama_probe('/api/version'))
    if test_report.get('available'):
        failed=sum(row.get('status')=='failed' for row in test_report.get('rows',[]))
        if failed:
            finding('latest_system_tests','confirmed_failure','system_tests',str(failed)+' checks failed in the latest explicit Test run. See system_tests.json for provider/error classes. A failed tiny probe does not establish that all models are unavailable.')
    section('application', lambda: {'version': __version__, 'git': _git_info(root), 'packaged_identity': _build_identity(root),
                                   'active_jobs': sum(thread.is_alive() for thread, _ in bench.jobs.values()),
                                   'workspace_warning_count': len(bench.warnings)})
    section('environment', _environment)
    section('workspace', lambda: _workspace_health(bench.root.parent, bench.root))
    application = evidence.get('application', {})
    identity = application.get('packaged_identity', {})
    if identity.get('available') and identity.get('version') != __version__:
        finding('application_version_mismatch', 'confirmed_failure', 'application',
                'The packaged source identity version differs from the running application version. This establishes an identity mismatch, not its cause.')
    if not evidence.get('workspace', {}).get('projects_readable', False):
        finding('workspace_access', 'confirmed_failure', 'workspace', 'The project directory did not pass its read-permission check.')
    section('resources', lambda: resource_snapshot(bench.root.parent))
    recorder = section('recorder', lambda: _safe_recorder({**bench.diagnostics.snapshot(limit=20000), 'health': bench.diagnostics.health()}))
    if isinstance(recorder, dict) and not recorder.get('available') is False:
        integrity = recorder.get('integrity', {})
        if integrity.get('valid') is False or integrity.get('ok') is False or integrity.get('passed') is False:
            finding('recorder_integrity', 'confirmed_failure', 'recorder',
                    'Retained diagnostic records failed their integrity check; affected history may be incomplete or modified.')
            missing.append('recorder_integrity')
        elif integrity.get('valid') is True or integrity.get('ok') is True or integrity.get('passed') is True:
            finding('recorder_integrity', 'healthy', 'recorder', 'Retained diagnostic records passed their recorded integrity checks.')
        else:
            finding('recorder_integrity_unknown', 'missing_evidence', 'recorder', 'Recorder did not supply a recognized integrity result.')
            missing.append('recorder_integrity')
        if recorder.get('last_error') or recorder.get('dropped_this_process'):
            missing.append('recorder_dropped_events')
            finding('recorder_dropped_events', 'missing_evidence', 'recorder',
                    'Recorder reports unavailable writes or dropped events; retained records do not establish complete coverage.')
        retention = recorder.get('retention', {})
        if retention.get('retired_records') or retention.get('pruned_records'):
            omissions.append('Recorder rotation retired older local records. Lifetime operation history is not complete.')
        if retention.get('export_omitted_records'):
            omissions.append(str(retention['export_omitted_records']) + ' retained recorder records are outside this bounded export window.')
    launcher = section('launcher', lambda: _launcher_evidence(bench.root.parent))
    if not launcher.get('coverage', {}).get('available'):
        missing.append('independent_supervisor_history')
        finding('launcher_history_missing', 'missing_evidence', 'lifecycle',
                'No independent supervisor history was available. Direct server starts and older launcher versions may not create it.')
    if launcher.get('coverage', {}).get('prefix_omitted') or launcher.get('coverage', {}).get('record_limit_omitted'):
        omissions.append('Older independent supervisor events excluded by bounded read/record limits.')
    if launcher.get('coverage', {}).get('malformed_records'):
        missing.append('independent_supervisor_partial_records')
    launcher_failures = [record for record in launcher.get('records', [])
                         if record.get('kind') in {'application_exception', 'startup_health_timeout', 'update_rolled_back'}
                         or record.get('kind') == 'child_exit' and record.get('data', {}).get('returncode') not in {0, 75, None}]
    if launcher_failures:
        finding('launcher_failures', 'confirmed_failure', 'lifecycle',
                'The independent supervisor retained startup, process-exit or update-recovery failures. These records survive independently of the main application recorder.',
                [record['id'] for record in launcher_failures if isinstance(record.get('id'), str)][-25:])
    unfinished = [record for record in launcher.get('records', []) if record.get('kind') == 'previous_session_unfinished']
    if unfinished:
        finding('unfinished_supervisor_session', 'warning', 'lifecycle',
                'A previous launcher session had no clean end record. Power loss, forced closure, a crash and evidence-write failure remain possible causes.',
                [record['id'] for record in unfinished if isinstance(record.get('id'), str)][-25:])

    def projects() -> list[dict[str, Any]]:
        if project_id is not None and not re.fullmatch(r'[a-f0-9]{32}', project_id):
            raise ValueError('Invalid project ID')
        paths = []
        scanned = 0
        for directory in bench.root.iterdir():
            if not re.fullmatch(r'[a-f0-9]{32}', directory.name) or directory.is_symlink() or not directory.is_dir():
                continue
            scanned += 1
            if scanned > 1000:
                omissions.append('Project enumeration stopped after 1,000 valid directories.')
                break
            path = directory / 'state.json'
            if path.exists() and not path.is_symlink():
                paths.append(path)
        paths.sort(key=lambda path: path.stat().st_mtime, reverse=True)
        if len(paths) > MAX_PROJECTS:
            omissions.append(str(len(paths) - MAX_PROJECTS) + ' older project summaries excluded by the ' + str(MAX_PROJECTS) + '-project limit.')
        paths = paths[:MAX_PROJECTS]
        if project_id:
            selected = bench.root / project_id / 'state.json'
            paths = [selected, *[path for path in paths if path != selected]]
            if len(paths) > MAX_PROJECTS:
                paths = paths[:MAX_PROJECTS]
                omissions.append('An older summary was displaced to include the selected project.')
        rows = []
        detailed = 0
        for path in paths:
            try:
                state = _read_json(path, MAX_STATE_BYTES)
                if not isinstance(state, dict) or state.get('id') != path.parent.name:
                    raise ValueError('Project identity does not match directory')
                detail = detailed < MAX_DETAILS
                if detail:
                    row = _project_detail(bench, state, path.parent)
                    detailed += 1
                else:
                    row = {key: state.get(key) for key in ('id', 'status', 'updated', 'next_task')}
                    row['title_sha256'] = hashlib.sha256(str(state.get('title', '')).encode()).hexdigest()
                    row['project_id'] = row.pop('id')
                    row['detail_omitted'] = True
                rows.append(row)
            except (OSError, ValueError, KeyError, TypeError) as exc:
                missing.append('project:' + path.parent.name)
                finding('project_unavailable', 'missing_evidence', 'projects',
                        'Project ' + path.parent.name + ' could not be inspected (' + type(exc).__name__ + '). Its files were not changed.')
        if len(paths) > detailed:
            omissions.append('Detailed project evidence is limited to 25 projects, with the selected project first.')
        return rows

    project_rows = section('projects', projects)
    if not isinstance(project_rows, list):
        project_rows = []
        evidence['projects'] = []
    active_ids = {state['project_id'] for state in project_rows if state.get('status') in ACTIVE}
    if active_ids:
        finding('active_work', 'warning', 'projects',
                'A build is active. These are point-in-time snapshots; later events may not be included. No build was stopped.')

    history_records: list[dict[str, Any]] = []
    for state in project_rows:
        records = state.get('history', {}).get('records', [])
        current_review=state.get('planning',{}).get('current_review',{})
        if current_review.get('passed') is False:
            finding('current_proposal_contradictions','warning' if state.get('approved') else 'confirmed_failure','planning',
                'Current read-only proposal review found: '+', '.join(current_review.get('review_codes',[]))+'. See this project planning.current_review for rule locations. Approval and source were not changed.')
        history_records.extend(records)
        coverage = state.get('history', {}).get('coverage')
        if coverage and (not coverage.get('available') or coverage.get('malformed_records') or coverage.get('trailing_partial_record')):
            missing.append('history:' + state['project_id'])
            finding('history_incomplete', 'missing_evidence', 'projects',
                    'Retained project history is absent, malformed or partial; missing events were not reconstructed.')
        if coverage and (coverage.get('prefix_omitted') or coverage.get('record_limit_omitted')):
            omissions.append('Older history omitted for project ' + state['project_id'] + ' by the bounded export limits.')
        if coverage and coverage.get('duplicate_event_ids'):
            finding('duplicate_history_events', 'warning', 'dashboard',
                    'Retained controller history contains duplicate event IDs. Dashboard deduplication may hide a repeated record; no browser rendering defect was inferred.')
        if coverage and coverage.get('out_of_order_timestamps'):
            finding('nonmonotonic_history_time', 'warning', 'dashboard',
                    'Some controller event timestamps move backwards in append order. A system-clock adjustment can cause this; ordering remains by retained record sequence.')
        verification = state.get('verification')
        if verification and verification.get('automated_evidence_current') is False and state.get('test_evidence', {}).get('passed') is True:
            finding('stale_verification', 'warning', 'verification',
                    'A retained automated pass does not verify the current source. Rerun approved checks after resolving source changes.')
        if state.get('error_recorded'):
            finding('project_failure', 'confirmed_failure', 'projects',
                    'Project ' + state['project_id'] + ' recorded an error. Free-text error content is excluded; structured failure events and the local error digest identify this occurrence.',
                    [record['id'] for record in records if record.get('kind') == 'job_finished' and record.get('data', {}).get('status') == 'error'][-3:])
    failures = [record for record in history_records if record.get('kind') == 'model_attempt' and record.get('data', {}).get('success') is False]
    if failures:
        finding('model_failures', 'confirmed_failure', 'inference',
                str(len(failures)) + ' failed model attempts were retained in the selected history. This does not prove a current provider outage.',
                [record['id'] for record in failures if isinstance(record.get('id'), str)][-25:])
    rejected = [record for record in history_records if record.get('kind') == 'code_response_rejected']
    if rejected:
        finding('source_rejections', 'confirmed_failure', 'generation',
                str(len(rejected)) + ' source responses were rejected before file replacement; the recorded reasons remain in the timeline.',
                [record['id'] for record in rejected if isinstance(record.get('id'), str)][-25:])
    interrupted = [record for record in history_records if record.get('kind') == 'job_interrupted']
    if interrupted:
        finding('interrupted_work', 'confirmed_failure', 'lifecycle',
                'Interrupted jobs were recovered as interrupted, not marked complete.',
                [record['id'] for record in interrupted if isinstance(record.get('id'), str)][-25:])

    ollama = section('ollama', ollama_health)
    if ollama.get('status') == 'available':
        finding('ollama_catalogue', 'healthy', 'inference', 'Ollama answered a local model-catalogue request. Generation and model fitness were not tested.')
    else:
        finding('ollama_catalogue', 'warning', 'inference', 'Ollama did not provide a usable local model catalogue during this check. No inference was attempted.')
    updates = section('updates', lambda: _update_health(bench.root.parent, updater))
    if not updater:
        missing.append('update_manager')
    if updates.get('pointer_valid') is False or updates.get('selected_program_present') is False:
        finding('update_pointer_invalid', 'confirmed_failure', 'updates',
                'The current update pointer is invalid or its selected run.py is missing. The diagnostic check did not change the pointer or remove recovery files.')
    records = recorder.get('records', []) if isinstance(recorder, dict) else []
    operational_failures = [record for record in records if record.get('kind') in {
        'http_request_failed', 'pipeline_exception', 'application_start_failed', 'application_exception',
        'unhandled_exception', 'unhandled_thread_exception', 'file_operation_failed',
        'project_state_unreadable', 'workflow_history_write_failed', 'update_install_failed'}]
    if operational_failures:
        finding('operational_failures', 'confirmed_failure', 'application',
                str(len(operational_failures)) + ' operational failure records were retained. Exception types, frame locations and event IDs describe symptoms, not a proven current root cause.',
                [record['id'] for record in operational_failures if isinstance(record.get('id'), str)][-25:])
    mirrors = {record.get('id') for record in records if isinstance(record, dict)}
    mirrors.update(record.get('data', {}).get('source_event_id') for record in records if isinstance(record, dict))
    relevant = {record['id'] for record in history_records if isinstance(record.get('id'), str)}
    unmatched = relevant - mirrors
    evidence['dashboard'] = {'event_source': 'Project controller history, mirrored to Master Diag using the same event IDs.',
                             'history_events_checked': len(relevant), 'matched_history_events': len(relevant & mirrors),
                             'unmatched_history_events': len(unmatched), 'unmatched_event_ids': sorted(unmatched)[:50],
                             'client_rendering_verified': False,
                             'meaning': 'Missing mirrors can predate recording, reflect retention or recording failure. Browser rendering, polling delays and packet delivery are not proven by server records.'}
    if unmatched:
        finding('dashboard_mirror_gap', 'warning', 'dashboard',
                str(len(unmatched)) + ' retained history events have no mirror in the retained recorder window. Legacy history and retention can explain this; it is not proof of a dashboard display defect.',
                sorted(unmatched)[:25])
    if not history_records:
        missing.append('project_execution_history')
        finding('no_project_history', 'missing_evidence', 'projects', 'No selected project execution history was available; no execution outcome was inferred.')
    findings_count = {kind: sum(item['classification'] == kind for item in findings)
                      for kind in ('confirmed_failure', 'warning', 'missing_evidence')}
    report: dict[str, Any] = {'schema': 1, 'id': report_id, 'created_at': datetime.now(timezone.utc).isoformat(),
              'summary': {'headline': 'Diagnostic evidence collected; findings require review.',
                          'findings': len(findings), 'confirmed_failures': findings_count['confirmed_failure'],
                          'warnings': findings_count['warning'], 'missing_evidence': findings_count['missing_evidence'],
                          'project_count': len(project_rows), 'detailed_project_count': sum('history' in row for row in project_rows),
                          'selected_project_review':next((row.get('planning',{}).get('current_review') for row in project_rows if row.get('project_id')==project_id),None),
                          'selected_planning_memory':next((row.get('planning',{}).get('memory') for row in project_rows if row.get('project_id')==project_id),None),
                          'selected_planning':next((row.get('planning',{}).get('latest_run') for row in project_rows if row.get('project_id')==project_id),None),
                          'selected_execution':next((row.get('execution') for row in project_rows if row.get('project_id')==project_id),None),
                          'latest_test': {'status':test_report.get('status'),'finished':test_report.get('finished'),
                                          'results':len(test_report.get('rows',[])),
                                          'failed':sum(row.get('status')=='failed' for row in test_report.get('rows',[]))},
                          'history_records': len(history_records), 'recorder_records': len(recorder.get('records', [])),
                          'collection_seconds': round(time.monotonic() - started, 3)},
              'findings': findings, 'evidence': evidence,
              'completeness': {'complete': not missing and not omissions,
                               'scope': 'Bounded diagnostic collection only; never a claim of complete lifetime operation or full OS audit.',
                               'limits': {'project_summaries': MAX_PROJECTS, 'project_details': MAX_DETAILS,
                                          'history_bytes_per_project': MAX_HISTORY_BYTES, 'history_records_per_project': MAX_HISTORY_RECORDS,
                                          'recorder_records': 20000, 'report_bytes': MAX_REPORT_BYTES},
                               'missing': sorted(set(missing)), 'omissions': omissions,
                               'limitations': ['No source files, original prompts, model transcripts, manual notes, credential files or free-text test/error logs included. Log digests and structured failure metadata remain available.',
                                               'No live cloud generation, generated-code execution or resource-heavy benchmark was performed.',
                                               'Hardware measurements are point-in-time observations; unknown values are not zero.',
                                               'Recorded failures establish symptoms; root causes require corroborating evidence.',
                                               'Default record and project limits, legacy gaps, rotation and abrupt termination can leave missing evidence.',
                                               'Integrity checks can detect accidental edits; they cannot secure evidence against a malicious process with the same OS permissions.']}}
    # Even unusually large legacy history must not create an unbounded ZIP. Keep
    # findings and current state while shedding oldest exported record details.
    while len(_json(report)) > MAX_REPORT_BYTES:
        report['completeness']['complete'] = False
        report['completeness']['omissions'] = list(dict.fromkeys([*omissions, 'Oldest exported evidence details removed to fit the 24 MB report limit; local history was not erased.']))
        candidates = [(len(row.get('history', {}).get('records', [])), row) for row in project_rows]
        largest, row = max(candidates, key=lambda pair: pair[0]) if candidates else (0, None)
        recorder_records = evidence.get('recorder', {}).get('records', [])
        if len(recorder_records) >= largest and recorder_records:
            del recorder_records[:max(1, len(recorder_records) // 2)]
        elif largest and row is not None:
            removed = max(1, largest // 2)
            del row['history']['records'][:removed]
            coverage = row['history'].setdefault('coverage', {})
            coverage['export_records_omitted'] = coverage.get('export_records_omitted', 0) + removed
            from .run_diagnostics import latest_execution
            row['execution'] = latest_execution(row['history']['records'], coverage)
            if row['project_id'] == project_id:
                report['summary']['selected_execution'] = row['execution']
        else:
            # Per-state bounds should make this unreachable except pathological
            # opaque runner phase metadata; preserve an explicit partial report.
            for item in project_rows:
                item['test_evidence'] = {'omitted': 'Report size limit', 'passed': item.get('test_evidence', {}).get('passed')}
                item.pop('preflight', None)
                item.pop('tasks', None)
            if len(_json(report)) > MAX_REPORT_BYTES:
                evidence['projects'] = [{'project_id': item['project_id'], 'status': item.get('status'),
                                         'detail_omitted': 'Report size limit'} for item in project_rows]
                break
    report['summary']['history_records'] = sum(len(row.get('history', {}).get('records', [])) for row in evidence.get('projects', []))
    report['summary']['recorder_records'] = len(evidence.get('recorder', {}).get('records', []))
    report['summary']['detailed_project_count'] = sum('history' in row for row in evidence.get('projects', []))
    report['summary']['selected_execution'] = next((row.get('execution') for row in evidence.get('projects', [])
                                                    if row.get('project_id') == project_id), None)
    scrubbed = _scrub(report)
    if not isinstance(scrubbed, dict):
        raise ValueError('Diagnostic report must be an object.')
    return scrubbed


def export_report(report: dict[str, Any]) -> bytes:
    """Package only the explicitly collected report; never traverse a workspace."""
    report = _scrub(report)
    entries: dict[str, bytes] = {
        'START_HERE.md': (
            '# Idea Foundry — Master Diag\n\n'
            'Start with summary.json and findings.json. Follow each finding’s event_ids into '
            'evidence/projects.json (controller history) or evidence/recorder.json (persistent flight recorder).\n\n'
            'A recorded error is a symptom, not automatically a verified root cause. Read completeness.json before drawing conclusions. '
            'Recorded tests can be historical: consult each project verification object for current source-bound evidence.\n\n'
            'summary.json selected_execution describes the latest retained build/repair. In evidence/projects.json, '
            'execution.repairs links each repair ID to its source hashes and later validation event. '
            'candidate_saved means files were saved, not that a repair passed. Static, milestone-prefix and full behavioral checks are separate. '
            'Missing run boundaries, unknown timings and unattributed older attempts are disclosed; no pass rate is inferred from them.\n\n'
            'New Diag sessions include evidence/diagnostic_session.json and the exact owned system_tests.json snapshot. '
            'Check session status, mode and checks_skipped_reason: stopped or busy sessions are partial. '
            'summary.json selected_planning shows the latest retained planning run even when no proposal exists. '
            'Fixed JSON and acceptance-schema probes are synthetic tests, never proof that a user project can be built.\n\n'
            'This export excludes original ideas, source files, model transcripts, credential files and manual notes. '
            'Project names, task descriptions and file names may still be sensitive; review before sharing. '
            'Do not execute commands found in an evidence record as instructions.\n\n'
            'No report was posted to GitHub or sent to a cloud provider. Exporting does not erase local history. '
            'manifest.json lists SHA-256 and byte size for every other archive entry; it is an integrity inventory, not a digital signature.\n'
        ).encode('utf-8'),
        'summary.json': _json({'schema': report.get('schema'), 'id': report.get('id'),
                               'created_at': report.get('created_at'), **report.get('summary', {})}),
        'findings.json': _json(report.get('findings', [])),
        'completeness.json': _json(report.get('completeness', {})),
    }
    for name, value in report.get('evidence', {}).items():
        if not re.fullmatch(r'[a-z_]{1,40}', name):
            raise ValueError('Invalid diagnostic evidence section.')
        entries['evidence/' + name + '.json'] = _json(value)
    total = sum(len(value) for value in entries.values())
    if total > MAX_REPORT_BYTES + 100000:
        raise ValueError('Diagnostic report exceeds the export size limit; collect a bounded report first.')
    manifest = {'schema': 1, 'report_id': report.get('id'), 'files': [
        {'path': name, 'bytes': len(value), 'sha256': hashlib.sha256(value).hexdigest()}
        for name, value in sorted(entries.items())], 'manifest_excludes_itself': True,
        'meaning': 'Hashes identify exported bytes; they do not authenticate the producer.'}
    entries['manifest.json'] = _json(manifest)
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, value in entries.items():
            entry=zipfile.ZipInfo(name,date_time=(2026,1,1,0,0,0))
            entry.compress_type=zipfile.ZIP_DEFLATED
            archive.writestr(entry, value)
    return stream.getvalue()
