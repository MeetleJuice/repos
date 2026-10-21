"""Reviewed collection storage: parameterized SQL and one closed connection per operation."""
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
import sqlite3


class Store:
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS records (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, note TEXT NOT NULL DEFAULT \'\', created_at TEXT NOT NULL)')
            conn.execute('CREATE INDEX IF NOT EXISTS records_created ON records(created_at DESC, id DESC)')

    @contextmanager
    def connection(self):
        conn = sqlite3.connect(self.path, timeout=5)
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def create(self, title, note=''):
        if not isinstance(title, str) or not title.strip() or len(title) > 2000:
            raise ValueError('Title must contain 1–2000 characters.')
        if not isinstance(note, str) or len(note) > 20000:
            raise ValueError('Note must be text, at most 20000 characters.')
        with self.connection() as conn:
            cursor = conn.execute('INSERT INTO records(title,note,created_at) VALUES(?,?,?)',
                                  (title.strip(), note, datetime.now().isoformat(timespec='microseconds')))
            return dict(conn.execute('SELECT * FROM records WHERE id=?', (cursor.lastrowid,)).fetchone())

    def listing(self, today=False):
        current_day = date.today()
        start = current_day.isoformat() + 'T00:00:00'
        end = (current_day + timedelta(days=1)).isoformat() + 'T00:00:00'
        with self.connection() as conn:
            count = conn.execute('SELECT COUNT(*) FROM records WHERE created_at>=? AND created_at<?', (start,end)).fetchone()[0]
            rows = conn.execute('SELECT * FROM records WHERE created_at>=? AND created_at<? ORDER BY created_at DESC,id DESC', (start,end)) if today else conn.execute('SELECT * FROM records ORDER BY created_at DESC,id DESC')
            return {'records': [dict(row) for row in rows], 'today_count': count}

    def delete(self, record_id):
        with self.connection() as conn:
            return conn.execute('DELETE FROM records WHERE id=?', (record_id,)).rowcount == 1
