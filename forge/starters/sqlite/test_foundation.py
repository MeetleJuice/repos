"""Protected foundation: real factory, storage, filters, validation and restart data."""
import json
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import app
from storage import Store


class FoundationTests(unittest.TestCase):
    def start(self, path):
        server=app.create_server('127.0.0.1',0,database_path=path)
        worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
        def cleanup():
            server.shutdown();server.server_close();worker.join(3)
        return 'http://127.0.0.1:'+str(server.server_port),cleanup

    def request(self, base, path, method='GET', body=None):
        request=urllib.request.Request(base+path,method=method,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json'})
        try:
            response=urllib.request.urlopen(request,timeout=3)
        except urllib.error.HTTPError as error:
            response=error
        with response:
            return response.status,json.loads(response.read())

    def test_factory_create_list_filter_delete_and_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'records.db';base,stop=self.start(path)
            try:
                self.assertTrue(path.exists())
                self.assertEqual(self.request(base,'/health'),(200,{'status':'ok'}))
                status,record=self.request(base,app.COLLECTION_PATH,'POST',{'title':'Saved proof','note':'A real record'})
                self.assertEqual(status,201);self.assertIsInstance(record['id'],int)
                status,data=self.request(base,app.COLLECTION_PATH+'?filter=today')
                self.assertEqual(status,200);self.assertEqual(data['records'][0]['id'],record['id'])
            finally:stop()
            base,stop=self.start(path)
            try:
                _,data=self.request(base,app.COLLECTION_PATH)
                self.assertEqual(data['records'][0]['title'],'Saved proof')
                self.assertEqual(self.request(base,app.COLLECTION_PATH+'/'+str(record['id']),'DELETE'),(200,{'deleted':True,'id':record['id']}))
                self.assertEqual(self.request(base,app.COLLECTION_PATH+'/'+str(record['id']),'DELETE')[0],404)
                self.assertEqual(self.request(base,app.COLLECTION_PATH)[1]['records'],[])
                with urllib.request.urlopen(base+'/',timeout=3) as response:self.assertIn('html',response.headers.get_content_type())
            finally:stop()

    def test_validation_history_daily_count_and_parameterized_values(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'records.db';store=Store(path)
            with store.connection() as conn:
                conn.execute('INSERT INTO records(title,note,created_at) VALUES(?,?,?)',('Yesterday','','2000-01-01T12:00:00'))
            title="Literal '); DROP TABLE records; --"
            saved=store.create(title)
            self.assertEqual(store.listing()['today_count'],1)
            self.assertEqual(len(store.listing()['records']),2)
            self.assertEqual(store.listing(today=True)['records'][0]['title'],title)
            self.assertTrue(store.delete(saved['id']))
            base,stop=self.start(path)
            try:
                for body in ({'title':'   '},{'title':'x','note':[]},[],{'title':'x'*2001}):
                    self.assertEqual(self.request(base,app.COLLECTION_PATH,'POST',body)[0],400)
                self.assertEqual(self.request(base,app.COLLECTION_PATH,'POST')[0],400)
                self.assertEqual(self.request(base,app.COLLECTION_PATH+'/invalid','DELETE')[0],400)
                self.assertEqual(self.request(base,app.COLLECTION_PATH+'/'+str(2**80),'DELETE')[0],400)
            finally:stop()
