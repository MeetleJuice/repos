"""Local, attributed workflow records. No model prompts or source bodies."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any
import uuid
from .providers import SECRET_NAMES

MAX_HISTORY_BYTES = 16_000_000


def redact(value: Any) -> Any:
    if isinstance(value, str):
        for name in SECRET_NAMES:
            secret = os.getenv(name)
            if secret:
                value = value.replace(secret, '[redacted]')
        return value
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, dict):
        return {k: redact(v) for k, v in value.items() if k.lower() not in {'api_key', 'authorization', 'partial_content'}}
    return value


def totals_for(state: dict[str, Any]) -> dict[str, Any]:
    saved = state.get('model_totals')
    if isinstance(saved, dict):
        return dict(saved)
    calls = state.get('model_calls', [])
    return {'requests':len(calls), 'seconds':round(sum(c.get('seconds', 0) for c in calls), 3),
            'prompt_tokens':sum(c.get('prompt_tokens', 0) for c in calls),
            'completion_tokens':sum(c.get('completion_tokens', 0) for c in calls),
            'usage_requests':sum('prompt_tokens' in c or 'completion_tokens' in c for c in calls),
            'legacy_incomplete':bool(calls),
            'transport_attempts':sum(c.get('transport_attempted') is True for c in calls),
            'transport_unknown':sum(c.get('transport_attempted') is None for c in calls)}


def add_attempt(state: dict[str, Any], record: dict[str, Any]) -> None:
    totals = totals_for(state)
    totals['transport_attempts'] = totals.get('transport_attempts', 0) + (record.get('transport_attempted') is True)
    totals['transport_unknown'] = totals.get('transport_unknown', 0) + (record.get('transport_attempted') is None)
    totals['requests'] += 1
    totals['seconds'] = round(totals['seconds'] + record.get('seconds', 0), 3)
    for field in ('prompt_tokens', 'completion_tokens'):
        totals[field] += record.get(field, 0)
    totals['usage_requests'] += 'prompt_tokens' in record or 'completion_tokens' in record
    state['model_totals'] = totals


def _path(directory: Path) -> Path:
    path = directory / 'workflow-history.jsonl'
    if path.is_symlink():
        raise OSError('History path is a symbolic link; original file was preserved.')
    return path


def ensure(directory: Path, state: dict[str, Any]) -> None:
    path = _path(directory)
    if path.exists():
        return
    records = [{'schema':1, 'id':uuid.uuid4().hex, 'time':datetime.now(timezone.utc).isoformat(),
                'run_id':None, 'kind':'history_started', 'origin':'controller',
                'data':{'prior_history_complete':not bool(state.get('events') or state.get('model_calls')),
                        'legacy_events_available':len(state.get('events', [])), 'legacy_attempts_available':len(state.get('model_calls', []))}}]
    for kind, items in [('journal',state.get('events', [])), ('model_attempt',state.get('model_calls', []))]:
        for item in items:
            records.append({'schema':1, 'id':uuid.uuid4().hex, 'time':item.get('time'), 'run_id':None,
                            'kind':kind, 'origin':'legacy_import', 'data':item})
    content = ''.join(json.dumps(redact(r), separators=(',',':'))+'\n' for r in records).encode('utf-8')
    if len(content) > MAX_HISTORY_BYTES:
        raise OSError('Legacy history exceeds the history size limit.')
    with path.open('xb') as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())


def append(directory: Path, state: dict[str, Any], kind: str, data: dict[str, Any], origin: str = 'controller') -> dict[str, Any]:
    ensure(directory, state)
    path = _path(directory)
    record = {'schema':1, 'id':uuid.uuid4().hex, 'time':datetime.now(timezone.utc).isoformat(),
              'run_id':state.get('active_run_id'), 'kind':kind, 'origin':origin, 'data':data}
    line = (json.dumps(redact(record), separators=(',',':'))+'\n').encode('utf-8')
    with path.open('rb') as previous:
        previous.seek(0, 2)
        if previous.tell():
            previous.seek(-1, 2)
            if previous.read(1) != b'\n':
                line = b'\n' + line
    if path.stat().st_size + len(line) > MAX_HISTORY_BYTES:
        raise OSError('Workflow history reached its 16 MB limit; later history records were not saved. Existing history and app files were preserved.')
    with path.open('ab') as stream:
        stream.write(line)
        stream.flush()
        os.fsync(stream.fileno())
    return record


def document(directory: Path, state: dict[str, Any]) -> dict[str, Any]:
    ensure(directory, state)
    path = _path(directory)
    if path.stat().st_size > MAX_HISTORY_BYTES:
        raise ValueError('Workflow history exceeds its 16 MB read limit.')
    content = path.read_bytes()
    records: list[dict[str, Any]] = []
    malformed = 0
    for line in content.splitlines():
        try:
            record = json.loads(line)
            if not isinstance(record, dict) or record.get('schema') != 1:
                raise ValueError('Invalid history record')
            records.append(record)
        except (ValueError, UnicodeError):
            malformed += 1
    start = next((r for r in records if r.get('kind') == 'history_started'), None)
    imported = bool(start and not start.get('data', {}).get('prior_history_complete', False))
    warning = state.get('history_warning')
    return {'schema':1, 'project_id':state['id'], 'records':redact(records),
            'coverage':{'legacy_history_incomplete':imported, 'tracking_origin_unknown':start is None, 'malformed_records':malformed,
                        'trailing_partial_record':bool(content and not content.endswith(b'\n')), 'warning':warning,
                        'complete_since_tracking_started':not bool(start is None or malformed or warning or (content and not content.endswith(b'\n')))},
            'meaning':'Recorded controller events and attributed model/user reports, not provider transcripts or a complete operating-system audit.'}
