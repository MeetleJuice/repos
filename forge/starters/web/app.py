"""Tested Python web foundation. Extend the routes for the approved proposal."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path

ASSETS = Path(__file__).resolve().parent


def create_server(host='127.0.0.1', port=8080):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def reply(self, value, status=200, content_type='application/json; charset=utf-8'):
            content = value if isinstance(value, bytes) else json.dumps(value).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(content)))
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(content)

        def do_GET(self):
            if self.path == '/health':
                return self.reply({'status': 'ok'})
            assets = {'/': ('index.html', 'text/html; charset=utf-8'), '/style.css': ('style.css', 'text/css; charset=utf-8')}
            if self.path in assets:
                filename, content_type = assets[self.path]
                return self.reply((ASSETS / filename).read_bytes(), content_type=content_type)
            return self.reply({'error': 'Not found'}, 404)

    return ThreadingHTTPServer((host, port), Handler)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8080)
    args = parser.parse_args()
    create_server(args.host, args.port).serve_forever()
