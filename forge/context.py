"""Bounded repository maps and structured failure feedback for small local models."""
import ast
import hashlib
import json
import re
from pathlib import Path

SOURCE_LIMIT = 36000


def source_map(files):
    result = []
    for name, content in sorted(files.items()):
        item = {'file': name, 'characters': len(content), 'sha256': hashlib.sha256(content.encode()).hexdigest()[:12]}
        if name.endswith('.py'):
            try:
                tree = ast.parse(content)
                item['symbols'] = [n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))][:35]
            except (SyntaxError, ValueError):
                item['syntax'] = 'invalid'
        result.append(item)
    return result


def failure_feedback(result):
    phases = result.get('phases', [])
    failed = next((p for p in phases if not p.get('passed')), {})
    raw = failed.get('error') or result.get('log', '')
    lines = raw.splitlines()
    # Keep the concrete request/assertion and final traceback rather than repeated phase JSON.
    evidence = [line for line in lines if any(word in line for word in ['AssertionError', 'Error:', 'FAIL:', 'ERROR:', 'expected HTTP', 'unexpected JSON', 'PASS:', 'File "'])]
    relevant = sorted(set(re.findall(r'([A-Za-z0-9_/-]+\.py)', raw)))
    return {'phase': failed.get('phase', 'unknown'), 'diagnosis': result.get('diagnosis', 'Inspect the failed check.'),
            'evidence': evidence[-20:], 'traceback_tail': '\n'.join(lines[-45:])[-6500:], 'referenced_files': relevant}


def fingerprint(files):
    return hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()


def planning_context(files, request, budget=8000):
    """Relevance-ranked excerpts, not inferred implementation claims or execution."""
    query = request.lower()
    words = {word for word in re.findall(r'[a-z][a-z0-9_]{2,}', query) if word not in {'the', 'and', 'with', 'from', 'this', 'that', 'app', 'code', 'file', 'existing', 'preserve'}}
    def rank(item):
        name, text = item
        score = (100 if name.lower() in query else 0) + sum(min(8, text.lower().count(word)) for word in words)
        if Path(name).name.startswith('test_') and name.lower() not in query:
            score -= 20
        return (-score, name)
    excerpts, remaining = [], budget
    for name, text in sorted(files.items(), key=rank)[:3]:
        if remaining <= 0:
            break
        excerpt = text[:remaining]
        excerpts.append({'file': name, 'content': excerpt, 'truncated': len(excerpt) < len(text)})
        remaining -= len(excerpt)
    mapping = []
    for item in source_map(files):
        item = {**item, 'symbols': [name[:80] for name in item.get('symbols', [])[:12]]}
        if len(json.dumps(mapping + [item])) > 2500:
            break
        mapping.append(item)
    return {'source_map': mapping, 'map_files_omitted': len(files) - len(mapping),
            'excerpts': excerpts, 'source_characters': budget - remaining,
            'files_omitted_from_excerpts': len(files) - len(excerpts),
            'meaning': 'Current source excerpts; truncation/omissions are explicit. Approved features are requirements, not proof they were implemented.'}


def same_tasks(first, second):
    def signature(tasks):
        if not isinstance(tasks, list) or not tasks or not all(isinstance(t, dict) and isinstance(t.get('title'), str) and isinstance(t.get('instructions'), str) for t in tasks):
            return None
        return [(re.sub(r'\s+', ' ', t['title']).strip().casefold(), re.sub(r'\s+', ' ', t['instructions']).strip().casefold()) for t in tasks]
    left, right = signature(first), signature(second)
    return left is not None and left == right
