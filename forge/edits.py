"""Exact, bounded text edits expanded before the existing transactional file checks."""
from __future__ import annotations

from typing import Any


def expand_response(response: Any, current: dict[str, str]) -> dict[str, str]:
    if not isinstance(response, dict):
        raise ValueError('Code response must be a JSON object containing files or edits.')
    files = response.get('files', {})
    edits = response.get('edits', [])
    if not isinstance(files, dict) or not isinstance(edits, list) or len(edits) > 12:
        raise ValueError('Return complete files and/or at most 12 exact edits.')
    result = dict(files)
    for edit in edits:
        if not isinstance(edit, dict) or set(edit) != {'file', 'search', 'replace'}:
            raise ValueError('Each edit needs exactly file, search and replace.')
        name, search, replacement = edit['file'], edit['search'], edit['replace']
        if not all(isinstance(v, str) for v in (name, search, replacement)) or not search or max(len(search), len(replacement)) > 40000:
            raise ValueError('Edits need a filename, nonempty exact search, and text replacement up to 40000 characters.')
        if name in files:
            raise ValueError('Do not mix edits and complete contents for the same file.')
        if name not in current:
            raise ValueError('Exact edits may only target existing files. Use files for new files.')
        content = result.get(name, current[name])
        first = content.find(search)
        if first < 0 or content.find(search, first + 1) >= 0:
            raise ValueError(f'{name}: search must match exactly once in the current file. Include unique surrounding context; do not guess or use ellipses.')
        if search == replacement:
            raise ValueError(f'{name}: edit would not change the file.')
        result[name] = content.replace(search, replacement, 1)
    if not 1 <= len(result) <= 24:
        raise ValueError('Model must return 1–24 complete source files or exact edits.')
    return result
