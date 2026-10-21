"""Reviewed SQLite web foundation. Adapt routes and UI, preserve the storage contract."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from storage import Store

ASSETS = Path(__file__).resolve().parent
COLLECTION_PATH = '/api/records'


def create_server(host='127.0.0.1', port=8080, *, database_path=None):
    store = Store(database_path if database_path is not None else ASSETS / 'app.db')

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def reply(self, value, status=200, content_type='application/json; charset=utf-8'):
            body = value if isinstance(value, bytes) else json.dumps(value).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            parsed = urlsplit(self.path)
            if parsed.path == '/health':
                return self.reply({'status':'ok'})
            assets = {'/':('index.html','text/html; charset=utf-8'), '/style.css':('style.css','text/css; charset=utf-8')}
            if parsed.path in assets:
                name, content_type = assets[parsed.path]
                return self.reply((ASSETS/name).read_bytes(), content_type=content_type)
            if parsed.path == COLLECTION_PATH:
                return self.reply(store.listing(today=parse_qs(parsed.query).get('filter') == ['today']))
            return self.reply({'error':'Not found'},404)

        def do_POST(self):
            if urlsplit(self.path).path != COLLECTION_PATH:
                return self.reply({'error':'Not found'},404)
            try:
                length = int(self.headers.get('Content-Length','0'))
                if not 0 < length <= 65536:
                    return self.reply({'error':'A JSON body of 1–65536 bytes is required.'},400)
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload,dict):
                    raise ValueError('Expected a JSON object.')
                record = store.create(payload.get('title'),payload.get('note',''))
            except (ValueError,UnicodeError) as error:
                return self.reply({'error':str(error)},400)
            return self.reply(record,201)

        def do_DELETE(self):
            path = urlsplit(self.path).path
            if not path.startswith(COLLECTION_PATH+'/'):
                return self.reply({'error':'Not found'},404)
            try:
                record_id = int(path[len(COLLECTION_PATH)+1:])
                if not 1 <= record_id <= 9223372036854775807:
                    raise ValueError()
            except ValueError:
                return self.reply({'error':'Invalid record ID'},400)
            if not store.delete(record_id):
                return self.reply({'error':'Not found'},404)
            return self.reply({'deleted':True,'id':record_id})

    return ThreadingHTTPServer((host,port),Handler)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--port',type=int,default=8080)
    args = parser.parse_args()
    create_server(args.host,args.port).serve_forever()
