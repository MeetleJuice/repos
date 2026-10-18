"""Local-only static arcade server. No directory listing or project-file exposure."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import urlsplit

ASSETS = {'/': ('index.html', 'text/html; charset=utf-8'), '/game.js': ('game.js', 'text/javascript; charset=utf-8'), '/style.css': ('style.css', 'text/css; charset=utf-8')}


def create_server(host='127.0.0.1', port=8080):
    root = Path(__file__).resolve().parent
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_GET(self):
            path = urlsplit(self.path).path
            if path == '/health':
                content, mime = json.dumps({'status': 'ok'}).encode(), 'application/json'
            elif path in ASSETS:
                name, mime = ASSETS[path]
                content = (root / name).read_bytes()
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(content)))
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(content)
    return ThreadingHTTPServer((host, port), Handler)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8080)
    args = parser.parse_args()
    print(f'Neon Dodge: http://{args.host}:{args.port}', flush=True)
    create_server(args.host, args.port).serve_forever()
