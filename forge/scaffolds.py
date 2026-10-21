"""Explicit, versioned starting points. Never replace existing project source."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = {
    'sqlite': {'title':'SQLite collection foundation','version':1,'description':'Reviewed Store with initialized schema, row mapping, closed per-operation connections and protected CRUD/restart tests. Existing /api/records supports POST {title,note} -> full record with id; GET -> {records,today_count}, ?filter=today; DELETE /{id} -> {deleted,id}. Adapt routes/UI without rebuilding storage. create_server(host,port,database_path=...) initializes the DB; default app.db stays beside app.py.'},
    'arcade': {'title': 'Neon Dodge browser arcade', 'version': 1, 'description': 'Working Canvas game: keyboard/touch, pause, restart and localStorage high score. Server checks plus explicit manual gameplay checklist.'},
    'web': {'title': 'Python web foundation', 'version': 1, 'description': 'Tested server, health endpoint, assets, launcher contract and foundation test.'},
    'notes': {'title': 'Notes application', 'version': 1, 'description': 'Reviewed SQLite notes, create/list/search/delete, safe browser UI and 12 behavioral tests.'},
    'tasks': {'title': 'Task tracker', 'version': 1, 'description': 'Reviewed SQLite tasks, create/list/complete/delete, safe browser UI and 11 behavioral tests.'},
}


def starter_files(name: str) -> dict[str, str]:
    if name not in CATALOG:
        raise ValueError('Choose a supported starter or start without a template.')
    if name=='sqlite':
        files=starter_files('web')
        for filename in ('app.py','storage.py','test_foundation.py'):
            files[filename]=(Path(__file__).with_name('starters')/'sqlite'/filename).read_text(encoding='utf-8')
        return files
    root = Path(__file__).with_name('starters') / 'web' if name == 'web' else Path(__file__).with_name('starters') / 'arcade' if name == 'arcade' else ROOT / 'examples' / ('notes-app' if name == 'notes' else 'task-tracker')
    names = ['app.py', 'index.html', 'style.css', 'test_foundation.py'] if name == 'web' else ['app.py', 'test_app.py', 'index.html', 'app.js', 'style.css']
    if name == 'arcade':
        names = ['app.py', 'index.html', 'style.css', 'game.js', 'test_app.py', 'test_foundation.py']
    files = {filename: (root / filename).read_text(encoding='utf-8') for filename in names}
    if name != 'web':
        files['test_foundation.py'] = (Path(__file__).with_name('starters') / 'web' / 'test_foundation.py').read_text(encoding='utf-8')
    return files
