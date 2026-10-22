"""Bounded, local operational evidence, deliberately outside generated workspaces.

The hash chain detects accidental edits within retained evidence. It is not a
signature: a trusted host program able to rewrite the database can rewrite it.
No prompt, source body, credential file or model transcript belongs here.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import threading
import time
from typing import Any, Callable
import uuid

from .providers import SECRET_NAMES

SCHEMA = 1
MAX_RECORD_BYTES = 32768
_PRIVATE = re.compile(r'(?i)(?:^|_)(?:api_?key|key|token|password|passwd|secret|authorization|cookie|access_?token|refresh_?token|private_?key)(?:$|_)')
_BODIES = {'prompt', 'system_prompt', 'source', 'source_text', 'partial_content', 'response_body', 'raw_response', 'transcript', 'request_body', 'messages', 'snippet', 'excerpt', 'preview', 'model_output'}


def _text(value: str) -> str:
    for name in SECRET_NAMES:
        secret = os.getenv(name)
        if secret and len(secret) >= 6:
            value = value.replace(secret, '[redacted]')
    value = re.sub(r'-----BEGIN [^-\r\n]*PRIVATE KEY-----.*?-----END [^-\r\n]*PRIVATE KEY-----', '[private key redacted]', value, flags=re.S)
    value = re.sub(r'(?i)\b(Bearer|Basic)\s+[A-Za-z0-9._~+/-]+=*', r'\1 [redacted]', value)
    value = re.sub(r'\b(?:sk-(?:or-v1-)?|gsk_|hf_|nvapi-)[A-Za-z0-9_-]{8,}', '[redacted]', value)
    value = re.sub(r'(?i)((?:(?:[a-z0-9]+[_-])*(?:api[_-]?key|password|access[_-]?token|refresh[_-]?token|secret|authorization|token))["\']?\s*[=:]\s*)["\']?[^\s,"\';<>]+', r'\1[redacted]', value)
    value = re.sub(r'(?i)(https?://)[^\s/@:]+:[^\s/@]+@', r'\1[redacted]@', value)
    value = re.sub(r'(?i)([?&](?:key|token|api_key|access_token)=)[^\s&#]+', r'\1[redacted]', value)
    value = re.sub(r'(?i)[A-Z]:[\\/]Users[\\/][^\\/\s\"\']+', '<user-home>', value)
    value = re.sub(r'/(?:home|Users)/[^/\s\"\']+', '<user-home>', value)
    home = str(Path.home())
    if home not in {'/', '.'}:
        value = value.replace(home, '<user-home>')
    value = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b', '[email redacted]', value)
    return value


def redact(value: Any, _depth: int = 0) -> Any:
    """Sanitize before persistence and again before export; bound arbitrary input."""
    if _depth > 12:
        return '[nesting limit]'
    if isinstance(value, str):
        return _text(value)[:12000]
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in list(value.items())[:256]:
            name = str(key)
            if _PRIVATE.search(name) or name.lower() in _BODIES or name.lower().endswith('_token'):
                result[_text(name)] = '[excluded]'
            else:
                result[_text(name)] = redact(item, _depth + 1)
        if len(value) > 256:
            result['_omitted_keys'] = len(value) - 256
        return result
    if isinstance(value, (list, tuple)):
        items = [redact(item, _depth + 1) for item in value[:256]]
        if len(value) > 256:
            items.append({'omitted_items': len(value) - 256})
        return items
    if value is None or isinstance(value, (int, float, bool)):
        return value
    return '<' + type(value).__name__ + '>'


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


_IDENTIFIERS = {'provider', 'model', 'role', 'status', 'category', 'error_category', 'exception_type',
                'error_type', 'failure_kind', 'runtime', 'action', 'phase', 'stage', 'operation',
                'recovery_path', 'finish_reason', 'transport_kind', 'version', 'commit', 'report_id',
                'source_sha256', 'before_source_sha256', 'after_source_sha256', 'plan_sha256',
                'request_sha256', 'handoff_sha256', 'sha256', 'task_id', 'source_event_id', 'file', 'path', 'function',
                'id', 'time', 'started', 'finished', 'method', 'code', 'severity', 'outcome', 'state',
                'failure_class', 'response_model', 'response_provider', 'current_version', 'release_version',
                'previous_version', 'command_template', 'before_sha256', 'after_sha256', 'disposition',
                'review_codes', 'expected_codes', 'observed_codes', 'project_id', 'reviewer_version', 'planning_stage', 'task_planning_policy', 'outline_planning_policy', 'response_sha256', 'response_format_mode', 'api_family',
                'repair_id', 'attempt_id', 'event_id', 'run_id', 'validation', 'validation_event_id', 'execution_stage', 'policy', 'prompt_sha256', 'recorded_status',
                'expected_validation', 'observed_validation', 'assertion_fields', 'invalid_assertion_fields',
                'assertion_kind', 'schema_sha256', 'session_id', 'active_check', 'mode', 'checks_skipped_reason'}
_FREE_TEXT = {'message', 'reason', 'meaning', 'notes', 'note', 'title', 'label', 'summary', 'description',
              'log', 'stdout', 'stderr', 'error', 'error_detail', 'detail', 'diagnosis', 'criteria',
              'done_when', 'expected', 'observed', 'outcome', 'issues', 'request', 'response',
              'instruction', 'question', 'answer', 'body', 'content', 'value', 'message_omitted'}
_FILE_LISTS = {'files', 'included_files', 'changed_files', 'deleted_files', 'available_files', 'omitted_files'}


def _summary(value: Any) -> dict[str, Any]:
    if (isinstance(value, dict) and value.get('content_omitted') is True
            and set(value) <= {'content_omitted', 'bytes', 'sha256', 'items'}
            and type(value.get('bytes')) is int and value['bytes'] >= 0
            and isinstance(value.get('sha256'), str) and re.fullmatch(r'[a-f0-9]{64}', value['sha256'])
            and ('items' not in value or type(value['items']) is int and value['items'] >= 0)):
        return dict(value)
    encoded = _canonical(value).encode('utf-8')
    return {'content_omitted': True, 'bytes': len(encoded), 'sha256': hashlib.sha256(encoded).hexdigest(),
            **({'items': len(value)} if isinstance(value, (list, dict)) else {})}


def sanitize_event_data(kind: str, data: dict[str, Any], origin: str = 'controller') -> dict[str, Any]:
    """Project operational facts, not arbitrary prose, into the flight recorder.

    Pattern redaction cannot recognize an old, unprefixed password hidden in a
    model's prose. Journal/model reports therefore retain only length/digest.
    The same projection can safely import legacy events without copying bodies.
    """
    cleaned = redact(data)
    if origin == 'model_report' or kind == 'journal':
        return _summary(cleaned)

    def project(value: Any, key: str = '') -> Any:
        if key in _FREE_TEXT or key in _BODIES:
            return _summary(value)
        if isinstance(value, dict):
            result = {}
            for child_key, item in value.items():
                if item == '[excluded]':
                    result[child_key] = item
                else:
                    result[child_key] = project(item, child_key)
            return result
        if isinstance(value, list):
            return [project(item, key) for item in value]
        if isinstance(value, str):
            if key in _IDENTIFIERS or key in _FILE_LISTS or (kind == 'hardware_sample' and key in {'name', 'limitations'}):
                if len(value) <= 240 and re.fullmatch(r'[A-Za-z0-9_./:@+ <>=,\[\]()-]+', value):
                    return value
            return _summary(value)
        return value

    projected = project(cleaned)
    return projected if isinstance(projected, dict) else {'data': projected}


class FlightRecorder:
    """A failure-isolated, cross-thread/process SQLite flight recorder.

    A transaction stores an event and advances its head together. Retention keeps
    the hash immediately preceding the retained range. This makes deliberate
    rotation distinguishable from a broken chain, without claiming authenticity.
    """

    def __init__(self, directory: Path, *, max_records: int = 20000, max_age_days: int = 14, max_bytes: int = 32_000_000) -> None:
        self.directory = Path(directory)
        self.path = self.directory / 'flight-recorder.sqlite3'
        self.max_records = max(1, max_records)
        self.max_age_days = max(1, max_age_days)
        self.max_bytes = max(1024, max_bytes)
        self.last_error: str | None = None
        self.dropped = 0
        self.lock = threading.RLock()
        self._ready = False
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        if self.directory.is_symlink() or self.path.is_symlink():
            raise OSError('Diagnostic location is a symbolic link; no diagnostic data was written.')
        connection = sqlite3.connect(self.path, timeout=1.0)
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA busy_timeout=1000')
        connection.execute('PRAGMA synchronous=FULL')
        return connection

    def _initialize(self) -> None:
        try:
            self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            if self.directory.is_symlink():
                raise OSError('Diagnostic location is a symbolic link.')
            connection = self._connect()
            try:
                connection.execute('PRAGMA journal_mode=WAL')
                connection.execute('PRAGMA wal_autocheckpoint=128')
                connection.execute('PRAGMA max_page_count=16384')
                connection.execute('CREATE TABLE IF NOT EXISTS events (sequence INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT UNIQUE NOT NULL, time_utc TEXT NOT NULL, kind TEXT NOT NULL, project_id TEXT, run_id TEXT, origin TEXT NOT NULL, body TEXT NOT NULL, previous_hash TEXT NOT NULL, record_hash TEXT NOT NULL, bytes INTEGER NOT NULL)')
                connection.execute('CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
                for key, value in {'anchor': '', 'head': '', 'retired_records': '0', 'retired_bytes': '0', 'schema': str(SCHEMA), 'live_records': '0', 'live_bytes': '0'}.items():
                    connection.execute('INSERT OR IGNORE INTO metadata VALUES (?, ?)', (key, value))
                count, size = connection.execute('SELECT count(*),coalesce(sum(bytes),0) FROM events').fetchone()
                connection.execute("UPDATE metadata SET value=? WHERE key='live_records'", (str(count),))
                connection.execute("UPDATE metadata SET value=? WHERE key='live_bytes'", (str(size),))
                connection.commit()
                self._ready = True
                if os.name != 'nt':
                    self.path.chmod(0o600)
            finally:
                connection.close()
        except (OSError, sqlite3.Error, ValueError) as error:
            self.last_error = type(error).__name__ + ': ' + _text(str(error))[:300]

    def _prune(self, connection: sqlite3.Connection) -> None:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=self.max_age_days)).isoformat()
        metadata = dict(connection.execute("SELECT key,value FROM metadata WHERE key IN ('live_bytes','live_records')").fetchall())
        total, count = int(metadata['live_bytes']), int(metadata['live_records'])
        retired = []
        for row in connection.execute('SELECT sequence,record_hash,bytes,time_utc FROM events ORDER BY sequence'):
            if count <= self.max_records and total <= self.max_bytes and row['time_utc'] >= cutoff:
                break
            retired.append(row)
            count -= 1
            total -= row['bytes']
        if retired:
            last = retired[-1]
            connection.execute('DELETE FROM events WHERE sequence<=?', (last['sequence'],))
            connection.execute("UPDATE metadata SET value=? WHERE key='anchor'", (last['record_hash'],))
            for key, amount in [('retired_records', len(retired)), ('retired_bytes', sum(row['bytes'] for row in retired))]:
                connection.execute('UPDATE metadata SET value=CAST(value AS INTEGER)+? WHERE key=?', (amount, key))
            connection.execute("UPDATE metadata SET value=? WHERE key='live_records'", (str(count),))
            connection.execute("UPDATE metadata SET value=? WHERE key='live_bytes'", (str(total),))

    def record(self, kind: str, data: dict[str, Any] | None = None, *, project_id: str | None = None, run_id: str | None = None, origin: str = 'controller', event_id: str | None = None, time_utc: str | None = None) -> str | None:
        with self.lock:
            if not self._ready:
                self._initialize()
            try:
                event_id = event_id or uuid.uuid4().hex
                stamp = time_utc or datetime.now(timezone.utc).isoformat()
                # Correlation IDs and names are data too; sanitize before storage.
                body: dict[str, Any] = redact({'schema': SCHEMA, 'id': event_id, 'time': stamp, 'kind': kind, 'project_id': project_id, 'run_id': run_id, 'origin': origin,
                                             'data': sanitize_event_data(kind, data or {}, origin)})
                for key in ('id', 'time', 'kind', 'project_id', 'run_id', 'origin'):
                    if isinstance(body[key], str):
                        body[key] = body[key][:512]
                encoded = _canonical(body)
                if len(encoded.encode('utf-8')) > MAX_RECORD_BYTES:
                    body['data'] = {'omitted': 'Event data exceeded the 32 KB diagnostic record limit.', 'original_bytes': len(encoded.encode('utf-8'))}
                    encoded = _canonical(body)
                connection = self._connect()
                try:
                    connection.execute('BEGIN IMMEDIATE')
                    previous = connection.execute("SELECT value FROM metadata WHERE key='head'").fetchone()[0]
                    digest = hashlib.sha256((previous + '\n' + encoded).encode('utf-8')).hexdigest()
                    connection.execute('INSERT INTO events(event_id,time_utc,kind,project_id,run_id,origin,body,previous_hash,record_hash,bytes) VALUES (?,?,?,?,?,?,?,?,?,?)', (body['id'], body['time'], body['kind'], body['project_id'], body['run_id'], body['origin'], encoded, previous, digest, len(encoded.encode('utf-8'))))
                    connection.execute("UPDATE metadata SET value=? WHERE key='head'", (digest,))
                    connection.execute("UPDATE metadata SET value=CAST(value AS INTEGER)+1 WHERE key='live_records'")
                    connection.execute("UPDATE metadata SET value=CAST(value AS INTEGER)+? WHERE key='live_bytes'", (len(encoded.encode('utf-8')),))
                    self._prune(connection)
                    connection.commit()
                finally:
                    connection.close()
                self.last_error = None
                return str(body['id'])
            except (OSError, sqlite3.Error, ValueError, TypeError, OverflowError) as error:
                self.dropped += 1
                self.last_error = type(error).__name__ + ': ' + _text(str(error))[:300]
                return None

    def snapshot(self, limit: int = 5000) -> dict[str, Any]:
        with self.lock:
            limit = max(1, min(int(limit), 20000))
            try:
                connection = self._connect()
                try:
                    connection.execute('BEGIN')
                    check = connection.execute('PRAGMA quick_check').fetchone()[0]
                    metadata = dict(connection.execute('SELECT key,value FROM metadata').fetchall())
                    rows = connection.execute('SELECT * FROM events ORDER BY sequence').fetchall()
                finally:
                    connection.close()
                previous = metadata.get('anchor', '')
                issues = []
                records: list[dict[str, Any]] = []
                for row in rows:
                    digest = hashlib.sha256((row['previous_hash'] + '\n' + row['body']).encode('utf-8')).hexdigest()
                    if row['previous_hash'] != previous or row['record_hash'] != digest:
                        issues.append({'sequence': row['sequence'], 'error': 'hash_chain_mismatch'})
                    previous = row['record_hash']
                    try:
                        record = json.loads(row['body'])
                        if not isinstance(record, dict):
                            raise ValueError('Invalid record shape')
                        # Recheck stored event identity, not merely its hash.
                        if any(record.get(key) != row[column] for key, column in [('id', 'event_id'), ('time', 'time_utc'), ('kind', 'kind'), ('project_id', 'project_id'), ('run_id', 'run_id'), ('origin', 'origin')]):
                            issues.append({'sequence': row['sequence'], 'error': 'index_identity_mismatch'})
                        records.append({**redact(record), 'sequence': row['sequence'], 'record_sha256': row['record_hash']})
                    except (ValueError, TypeError):
                        issues.append({'sequence': row['sequence'], 'error': 'malformed_record'})
                if previous != metadata.get('head', ''):
                    issues.append({'error': 'head_mismatch'})
                if check != 'ok':
                    issues.append({'error': 'sqlite_quick_check_failed'})
                return {'schema': SCHEMA, 'records': records[-limit:], 'integrity': {'passed': not issues, 'issues': issues[:100], 'checked_records': len(rows), 'scope': 'Retained rows and local anchor/head only; not a cryptographic signature or proof against privileged host modification.'}, 'retention': {'max_records': self.max_records, 'max_age_days': self.max_age_days, 'max_payload_bytes': self.max_bytes, 'retired_records': int(metadata.get('retired_records', '0')), 'retired_payload_bytes': int(metadata.get('retired_bytes', '0')), 'available_records': len(rows), 'export_omitted_records': max(0, len(records) - limit)}, 'last_error': self.last_error, 'dropped_this_process': self.dropped}
            except (OSError, sqlite3.Error, ValueError, TypeError) as error:
                self.last_error = type(error).__name__ + ': ' + _text(str(error))[:300]
                return {'schema': SCHEMA, 'records': [], 'integrity': {'passed': False, 'issues': [{'error': self.last_error}]}, 'retention': {'unknown': True}, 'last_error': self.last_error, 'dropped_this_process': self.dropped}

    def health(self) -> dict[str, Any]:
        return {'enabled': self._ready, 'last_error': self.last_error, 'dropped_this_process': self.dropped, 'storage': 'diagnostics/flight-recorder.sqlite3', 'max_records': self.max_records, 'max_age_days': self.max_age_days, 'max_payload_bytes': self.max_bytes}

    def close(self) -> None:
        """Connections belong to each operation, so nothing remains open."""


def resource_snapshot(home: Path) -> dict[str, Any]:
    """Best-effort observations, never GPU-fit conclusions or model generation."""
    result: dict[str, Any] = {'time': datetime.now(timezone.utc).isoformat(), 'pid': os.getpid(), 'cpu_count': os.cpu_count(), 'process_cpu_seconds': time.process_time(), 'process_rss_bytes': None, 'ram_total_bytes': None, 'ram_available_bytes': None, 'disk_free_bytes': None, 'cpu_counters': None, 'gpu': None, 'limitations': []}
    try:
        result['disk_free_bytes'] = shutil.disk_usage(home).free
    except OSError:
        result['limitations'].append('Disk availability unavailable.')
    try:
        if os.name == 'nt':
            import ctypes
            from ctypes import wintypes
            windll = getattr(ctypes, 'windll')
            class MemoryStatus(ctypes.Structure):
                _fields_ = [('length', wintypes.DWORD), ('load', wintypes.DWORD), ('total', ctypes.c_ulonglong), ('available', ctypes.c_ulonglong), ('page_total', ctypes.c_ulonglong), ('page_available', ctypes.c_ulonglong), ('virtual_total', ctypes.c_ulonglong), ('virtual_available', ctypes.c_ulonglong), ('extended', ctypes.c_ulonglong)]
            memory = MemoryStatus()
            memory.length = ctypes.sizeof(memory)
            global_memory = windll.kernel32.GlobalMemoryStatusEx
            global_memory.argtypes = [ctypes.POINTER(MemoryStatus)]
            global_memory.restype = wintypes.BOOL
            if global_memory(ctypes.byref(memory)):
                result.update(ram_total_bytes=memory.total, ram_available_bytes=memory.available)
            class ProcessMemory(ctypes.Structure):
                _fields_ = [('size', wintypes.DWORD), ('faults', wintypes.DWORD), *[(name, ctypes.c_size_t) for name in ('peak_working', 'working', 'quota_peak_paged', 'quota_paged', 'quota_peak_nonpaged', 'quota_nonpaged', 'pagefile', 'peak_pagefile')]]
            process = ProcessMemory()
            process.size = ctypes.sizeof(process)
            kernel = windll.kernel32
            kernel.GetCurrentProcess.restype = wintypes.HANDLE
            process_memory = windll.psapi.GetProcessMemoryInfo
            process_memory.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessMemory), wintypes.DWORD]
            process_memory.restype = wintypes.BOOL
            if process_memory(kernel.GetCurrentProcess(), ctypes.byref(process), process.size):
                result['process_rss_bytes'] = process.working
            idle, kern, user = wintypes.FILETIME(), wintypes.FILETIME(), wintypes.FILETIME()
            if kernel.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kern), ctypes.byref(user)):
                values = [(value.dwHighDateTime << 32) + value.dwLowDateTime for value in (idle, kern, user)]
                result['cpu_counters'] = {'idle': values[0], 'total': values[1] + values[2]}
        elif Path('/proc/meminfo').is_file():
            memory_values = {parts[0].rstrip(':'): int(parts[1]) * 1024 for line in Path('/proc/meminfo').read_text().splitlines() if len(parts := line.split()) >= 2 and parts[1].isdigit()}
            result.update(ram_total_bytes=memory_values.get('MemTotal'), ram_available_bytes=memory_values.get('MemAvailable'))
            for line in Path('/proc/self/status').read_text().splitlines():
                if line.startswith('VmRSS:'):
                    result['process_rss_bytes'] = int(line.split()[1]) * 1024
            values = list(map(int, Path('/proc/stat').read_text().splitlines()[0].split()[1:]))
            result['cpu_counters'] = {'idle': values[3] + (values[4] if len(values) > 4 else 0), 'total': sum(values[:8])}
        else:
            result['limitations'].append('RAM/RSS/host CPU counters unavailable on this platform.')
    except (OSError, ValueError, AttributeError, TypeError):
        result['limitations'].append('Some host memory/CPU measurements unavailable.')
    executable = shutil.which('nvidia-smi')
    if executable:
        try:
            probe = subprocess.run([executable, '--query-gpu=name,memory.used,memory.total,utilization.gpu', '--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=2, check=False, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0) if os.name == 'nt' else 0)
            if probe.returncode == 0:
                cards = []
                for line in probe.stdout[:8192].splitlines()[:8]:
                    fields = [value.strip() for value in line.split(',')]
                    if len(fields) == 4:
                        cards.append({'name': fields[0], 'memory_used_mib': float(fields[1]) if fields[1].replace('.', '', 1).isdigit() else None, 'memory_total_mib': float(fields[2]) if fields[2].replace('.', '', 1).isdigit() else None, 'utilization_percent': float(fields[3]) if fields[3].replace('.', '', 1).isdigit() else None})
                result['gpu'] = cards or None
            else:
                result['limitations'].append('nvidia-smi returned an error; GPU measurements unavailable.')
        except (OSError, subprocess.TimeoutExpired, ValueError):
            result['limitations'].append('GPU measurement failed or exceeded its two-second timeout.')
    else:
        result['limitations'].append('nvidia-smi unavailable; GPU/VRAM unknown.')
    return result


class ResourceSampler:
    def __init__(self, recorder: FlightRecorder, home: Path, interval: float = 30.0,
                 local_probe: Callable[[], dict[str,Any]] | None = None) -> None:
        self.recorder, self.home = recorder, Path(home)
        self.interval = max(1.0, interval)
        self._stop = threading.Event()
        self.thread: threading.Thread | None = None
        self.local_probe=local_probe

    def start(self) -> None:
        if self.thread is not None and self.thread.is_alive():
            return
        self._stop.clear()
        self.thread = threading.Thread(target=self._run, name='Foundry-resource-sampler', daemon=True)
        self.thread.start()

    def _run(self) -> None:
        previous: dict[str, Any] | None = None
        while not self._stop.is_set():
            try:
                current = resource_snapshot(self.home)
                counters = current.get('cpu_counters')
                if counters and previous:
                    total = counters['total'] - previous['total']
                    idle = counters['idle'] - previous['idle']
                    current['cpu_utilization_percent'] = round(max(0.0, min(100.0, (total - idle) / total * 100)), 2) if total > 0 else None
                else:
                    current['cpu_utilization_percent'] = None
                previous = counters
                self.recorder.record('hardware_sample', current, origin='resource_sampler')
                if self.local_probe and not self._stop.is_set():
                    self.recorder.record('local_runtime_sample',self.local_probe(),origin='resource_sampler')
                total_ram, available = current.get('ram_total_bytes'), current.get('ram_available_bytes')
                if (total_ram and available is not None and available < total_ram * 0.05) or (current.get('disk_free_bytes') is not None and current['disk_free_bytes'] < 500_000_000):
                    self.recorder.record('resource_pressure', {'available_ram_bytes': available, 'disk_free_bytes': current.get('disk_free_bytes'), 'meaning': 'Observed low resource availability; not proof of a pipeline failure cause.'}, origin='resource_sampler')
            except Exception as error:
                self.recorder.record('resource_sampling_failed', {'error_type': type(error).__name__}, origin='resource_sampler')
            self._stop.wait(self.interval)

    def stop(self) -> None:
        self._stop.set()
        if self.thread is not None:
            self.thread.join(timeout=3.0)
