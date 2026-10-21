"""One local-only idea request, separate from project planning and execution."""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from typing import Any
from urllib.parse import urlsplit

from .models import ModelError, request_json
from .routing import validate_options

SYSTEM = ('You suggest small, original software projects for a local Python standard-library browser-app builder. '
          'Return only JSON {"idea":"a complete editable project-building prompt"}. '
          'Propose one feasible app with 3-5 concrete features, local storage when useful, a clear interface, '
          'acceptance checks and a short manual checklist. No accounts, paid services, external APIs, installs, '
          'project execution or code. Keep the idea under 250 words. Vary the topic.')


def local_models() -> list[str]:
    url = os.getenv('OLLAMA_URL', 'http://127.0.0.1:11434').rstrip('/')
    parsed = urlsplit(url)
    if parsed.scheme != 'http' or parsed.hostname not in {'127.0.0.1', 'localhost', '::1'} or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path:
        raise ValueError('Generate Idea requires a direct loopback Ollama URL.')
    result = request_json(url + '/api/tags', timeout=3, local_only=True)
    entries = result.get('models', [])
    if not isinstance(entries, list):
        raise ValueError('Ollama returned an invalid model catalogue.')
    return [entry['name'] for entry in entries if isinstance(entry, dict) and isinstance(entry.get('name'), str)
            and re.fullmatch(r'[A-Za-z0-9_./:@+-]{1,200}', entry['name']) and 'embed' not in entry['name'].lower()]


def choose_model(installed: list[str], profiles: list[dict[str, Any]]) -> dict[str, Any]:
    for config in profiles:
        route = [config, *config.get('fallbacks', []), *([config['fallback']] if config.get('fallback') else [])]
        for entry in route:
            if entry.get('provider') == 'ollama' and entry.get('model') in installed:
                return dict(entry)
    raise ValueError('Choose an installed Ollama chat/coding model in Models first. Generate Idea never uses cloud providers.')


def generate_idea(bench: Any, profiles: list[dict[str, Any]], project_id: str | None = None) -> dict[str, Any]:
    with bench.lock:
        if bench.maintenance or bench.idea_busy or any(thread.is_alive() for thread, _ in bench.jobs.values()):
            raise ValueError('Finish or stop the running job before generating an idea.')
        if not bench.inference_lock.acquire(blocking=False):
            raise ValueError('A model request is already running. Try Generate Idea when it finishes.')
        bench.idea_busy = True
    started = time.monotonic()
    model = None
    client = None
    success = False
    category = None
    try:
        installed = local_models()
        selected = choose_model(installed, profiles)
        model = selected['model']
        options = validate_options(selected.get('options', {}))
        # A small isolated request, not the planner's 8192-token proposal floor.
        options['num_predict'] = 1024
        options['timeout_seconds'] = min(options['timeout_seconds'], 120)
        client = bench.client_factory('ollama', model)
        client.options = options
        bench.model_status.start('ollama', model, 'idea', project_id)
        bench.diagnostics.record('idea_request_started', {'provider': 'ollama', 'model': model,
            'requested_max_output_tokens': 1024, 'num_ctx': options['num_ctx'], 'timeout_seconds': options['timeout_seconds']}, project_id=project_id)
        result = client.complete(SYSTEM, json.dumps({'request': 'Suggest a fresh doable project.', 'variation': time.time_ns()}))
        idea = result.get('idea') if isinstance(result, dict) else None
        if not isinstance(idea, str) or not 40 <= len(idea.strip()) <= 6000:
            raise ModelError('The local model did not return a useful idea prompt. Your existing text was kept.', 'schema_error')
        success = True
        bench.diagnostics.record('idea_generated', {'provider': 'ollama', 'model': model,
            'characters': len(idea.strip()), 'idea_sha256': hashlib.sha256(idea.strip().encode()).hexdigest(),
            'project_created': False}, project_id=project_id)
        return {'idea': idea.strip(), 'provider': 'ollama', 'model': model}
    except Exception as exc:
        category = getattr(exc, 'category', type(exc).__name__)
        bench.diagnostics.record('idea_request_failed', {'model': model, 'provider': 'ollama',
            'failure_class': category, 'exception_type': type(exc).__name__, 'project_created': False}, project_id=project_id)
        raise
    finally:
        if model:
            bench.model_status.finish('ollama', model, 'responded' if success else category or 'error')
        bench.diagnostics.record('idea_request_finished', {'provider': 'ollama', 'model': model, 'success': success,
            'failure_class': category, 'seconds': round(time.monotonic() - started, 3),
            **getattr(client, 'last_usage', {}), **getattr(client, 'last_metadata', {})}, project_id=project_id)
        with bench.lock:
            bench.idea_busy = False
            bench.inference_lock.release()
