"""Bounded repository maps and structured failure feedback for small local models."""
import ast
import hashlib
import json
import re

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
