"""Isolated Dashboard routes. No imports from existing Foundry modules."""
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parent
ASSETS={'/dashboard':('index.html','text/html; charset=utf-8'),
        '/dashboard/':('index.html','text/html; charset=utf-8'),
        '/dashboard/assets/app.js':('assets/app.js','text/javascript'),
        '/dashboard/assets/app.css':('assets/app.css','text/css'),
        '/dashboard/assets/elk-worker.js':('assets/elk-worker.js','text/javascript'),
        '/dashboard/map':('docs/CODEBASE_MAP.md','text/plain; charset=utf-8')}
ENTRY=b'<a class="secondary ifd-entry" href="/dashboard" target="_blank" rel="noopener">&#9672; Dashboard &#8599;</a>'


def register(base: Any) -> Any:
    """Adapt only GET/static delivery; original dispatch/API/state remain untouched."""
    class DashboardHandler(base):
        def send_header(self, keyword: str, value: str) -> None:
            if keyword.lower()=='content-security-policy' and urlsplit(self.path).path.startswith('/dashboard'):
                value="default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; worker-src 'self'; font-src 'self'; base-uri 'none'; frame-ancestors 'none'; object-src 'none'; form-action 'none'"
            super().send_header(keyword,value)

        def send_bytes(self, status: int, content: bytes, content_type: str = 'application/json', filename: str | None = None) -> None:
            if status==200 and urlsplit(self.path).path=='/' and content_type.startswith('text/html'):
                content=content.replace(b'<div class="topbar-actions">',b'<div class="topbar-actions">'+ENTRY,1)
            super().send_bytes(status,content,content_type,filename)

        def do_GET(self) -> None:
            path=urlsplit(self.path).path
            if not path.startswith('/dashboard'):
                super().do_GET();return
            try:
                self.check_request()
                if path not in ASSETS:
                    self.json({'error':'Dashboard resource not found.'},404);return
                filename,kind=ASSETS[path]
                self.send_bytes(200,(ROOT/filename).read_bytes(),kind)
            except PermissionError as error:self.json({'error':str(error)},403)
            except (BrokenPipeError,ConnectionResetError):pass
            except OSError:self.json({'error':'Dashboard assets unavailable. Rebuild the isolated feature.'},503)

        def end_headers(self) -> None:
            if urlsplit(self.path).path.startswith('/dashboard'):
                self.send_header('X-Frame-Options','DENY')
            super().end_headers()
    return DashboardHandler
