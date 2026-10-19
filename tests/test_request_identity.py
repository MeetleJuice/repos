"""Reproduce the observed Groq User-Agent gate without live keys or inference."""
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import urllib.request
import urllib.error
from forge import __version__
from forge.cloud import CloudSetup
from forge.models import request_json, ModelClient, PROVIDERS
from tests.fixtures import PLAN


class RequestIdentityTests(unittest.TestCase):
    def setUp(self):
        self.calls=[]
        calls=self.calls
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*_):pass
            def respond(self):
                agent=self.headers.get('User-Agent','');calls.append((self.command,agent,self.headers.get('Authorization')))
                if agent.startswith('Python-urllib/'):
                    self.send_response(403);self.end_headers();return
                if self.command=='POST':
                    body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                    assert body['model']=='fixture-model'
                    value={'choices':[{'finish_reason':'stop','message':{'content':json.dumps(PLAN)}}]}
                else:value={'data':[{'id':'fixture-model'}]}
                data=json.dumps(value).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(data)
            do_GET=respond
            do_POST=respond
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        threading.Thread(target=self.server.serve_forever,daemon=True).start()
        self.base='http://127.0.0.1:'+str(self.server.server_port)

    def tearDown(self):
        self.server.shutdown();self.server.server_close()

    def test_frozen_default_403_named_200_reproduction(self):
        fixture=json.loads((Path(__file__).parent/'fixture_data/groq-request-identity-v1.json').read_text())
        with self.assertRaises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(self.base+'/models')
        self.assertEqual(error.exception.code,fixture['observed']['default_python_user_agent']);error.exception.close()
        self.assertEqual(request_json(self.base+'/models')['data'][0]['id'],'fixture-model')
        self.assertEqual(self.calls[-1][1],'IdeaFoundry/'+__version__+' desktop-client')

    def test_catalogue_and_generation_share_identity_and_keep_bearer_auth(self):
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'GROQ_API_KEY':'fixture-groq-only','NO_PROXY':'127.0.0.1,localhost','no_proxy':'127.0.0.1,localhost'},clear=True),patch('forge.cloud.endpoint',return_value=self.base),patch.dict(PROVIDERS,{'groq':(self.base,'GROQ_API_KEY')}):
            result=CloudSetup(d)._check_provider('groq')
            self.assertEqual(result['status'],'catalogue_available')
            self.assertEqual(ModelClient('groq','fixture-model').complete('Return JSON','{}'),PLAN)
        self.assertEqual([r[0] for r in self.calls],['GET','POST'])
        self.assertTrue(all(r[1]=='IdeaFoundry/'+__version__+' desktop-client' for r in self.calls))
        self.assertTrue(all(r[2]=='Bearer fixture-groq-only' for r in self.calls))
