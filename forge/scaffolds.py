"""Explicit, versioned starting points. Never replace existing project source."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = {
    'web': {'title': 'Python web foundation', 'version': 1, 'description': 'Tested server, health endpoint, assets, launcher contract and foundation test.'},
    'notes': {'title': 'Notes application', 'version': 1, 'description': 'Reviewed SQLite notes, create/list/search/delete, safe browser UI and 12 behavioral tests.'},
    'tasks': {'title': 'Task tracker', 'version': 1, 'description': 'Reviewed SQLite tasks, create/list/complete/delete, safe browser UI and 11 behavioral tests.'},
}


def starter_files(name):
    if name not in CATALOG:
        raise ValueError('Choose a supported starter or start without a template.')
    root = Path(__file__).with_name('starters') / 'web' if name == 'web' else ROOT / 'examples' / ('notes-app' if name == 'notes' else 'task-tracker')
    names = ['app.py', 'index.html', 'style.css', 'test_foundation.py'] if name == 'web' else ['app.py', 'test_app.py', 'index.html', 'app.js', 'style.css']
    files = {filename: (root / filename).read_text(encoding='utf-8') for filename in names}
    if name != 'web':
        files['test_foundation.py'] = (Path(__file__).with_name('starters') / 'web' / 'test_foundation.py').read_text(encoding='utf-8')
    return files
