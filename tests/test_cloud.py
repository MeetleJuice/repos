"""Cloud setup uses local fixture keys; provider calls are mocked or loopback HTTP only."""
import copy
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from forge.cloud import CloudSetup
from forge.credentials import CredentialStore, parse_dotenv
from forge.core import Workbench
from forge.models import ModelError, ModelClient
from forge.routing import validate_config, uses_cloud
from tests.fixtures import PLAN
from tests.test_workbench import ScriptedModels, await_job

KEYS={'GEMINI_API_KEY':'fixture-gemini','GROQ_API_KEY':'fixture-groq','OPENROUTER_API_KEY':'fixture-router'}
CHAIN={'provider':'gemini','model':'checked-gemini','fallbacks':[{'provider':'groq','model':'checked-groq'}, {'provider':'openrouter','model':'checked-router'}]}


def state_for(bench):
    state={'id':'a'*32,'status':'approved','title':'Cloud fixture','created':bench.now(),'events':[],
           'planner':copy.deepcopy(CHAIN),'coder':copy.deepcopy(CHAIN),'job_cloud_consent':True}
    (bench.directory(state['id'])/'source').mkdir(parents=True)
    bench.save(state)
    return state


class CredentialTests(unittest.TestCase):
    def test_notepad_alias_quotes_comments_and_no_shell_evaluation(self):
        data=parse_dotenv('\ufeffexport GEMINI_API_KEY="fixture-gemini" # comment\nOPENROUTER_KEY=fixture-router\nGROQ_API_KEY=\nPATH=evil\nX=$(run)')
        self.assertEqual(data['OPENROUTER_API_KEY'],'fixture-router')
        self.assertNotIn('PATH',data);self.assertNotIn('GROQ_API_KEY',data)
        for text in ['GEMINI_API_KEY="unterminated','GEMINI_API_KEY="x" trailing','GEMINI_API_KEY=x\x00']:
            with self.subTest(text=text),self.assertRaises(ValueError):parse_dotenv(text)

    def test_precedence_reload_removal_and_process_binding(self):
        with tempfile.TemporaryDirectory() as temp,patch.dict(os.environ,{},clear=True):
            root=Path(temp);home=root/'home';home.mkdir();launch=root/'launch';launch.mkdir()
            (home/'.env').write_text('GROQ_API_KEY=home-value')
            (launch/'.env').write_text('GROQ_API_KEY=launch-value\nGEMINI_API_KEY=first')
            os.environ['OPENROUTER_API_KEY']='injected-value'
            store=CredentialStore(home,[launch]);self.assertEqual(os.environ['GROQ_API_KEY'],'home-value')
            (launch/'.env').write_text('GROQ_API_KEY=launch-value\nGEMINI_API_KEY=second')
            store.reload();self.assertEqual(os.environ['GEMINI_API_KEY'],'second')
            (launch/'.env').write_text('GROQ_API_KEY=launch-value')
            store.reload();self.assertNotIn('GEMINI_API_KEY',os.environ)
            self.assertEqual(os.environ['OPENROUTER_API_KEY'],'injected-value')

    def test_bad_local_env_does_not_prevent_starting_the_studio(self):
        with tempfile.TemporaryDirectory() as temp,patch.dict(os.environ,{},clear=True):
            root=Path(temp);(root/'.env').write_text('GEMINI_API_KEY="unclosed-sensitive-value')
            store=CredentialStore(root)
            self.assertTrue(store.status()['warnings'])
            self.assertNotIn('GEMINI_API_KEY',os.environ)
            self.assertNotIn('sensitive-value',json.dumps(store.status()))
            store.import_text('GEMINI_API_KEY=corrected-value')
            self.assertEqual(store.status()['warnings'],[])
            self.assertEqual(os.environ['GEMINI_API_KEY'],'corrected-value')

    def test_manual_notepad_utf16_file_loads_and_reloads(self):
        with tempfile.TemporaryDirectory() as temp,patch.dict(os.environ,{},clear=True):
            path=Path(temp)/'.env';path.write_bytes('GEMINI_API_KEY=notepad-value'.encode('utf-16'))
            store=CredentialStore(temp)
            self.assertEqual(os.environ['GEMINI_API_KEY'],'notepad-value')
            store.import_text('GROQ_API_KEY=imported-value')
            self.assertEqual(os.environ['GEMINI_API_KEY'],'notepad-value')
            self.assertEqual(os.environ['GROQ_API_KEY'],'imported-value')

    def test_import_is_private_preserves_other_entries_and_returns_no_secrets(self):
        with tempfile.TemporaryDirectory() as temp,patch.dict(os.environ,{},clear=True):
            root=Path(temp);(root/'.env').write_text('OTHER_SETTING=keep\nGROQ_API_KEY=old-value\n')
            (root/'.env.txt').write_text('not imported automatically')
            store=CredentialStore(root)
            result=store.import_text('GROQ_API_KEY=new-value\nOPENROUTER_KEY=router-value')
            self.assertIn('OTHER_SETTING=keep',(root/'.env').read_text())
            self.assertEqual(os.environ['GROQ_API_KEY'],'new-value')
            self.assertEqual(os.environ['OPENROUTER_API_KEY'],'router-value')
            self.assertNotIn('new-value',json.dumps(result));self.assertNotIn('router-value',json.dumps(result))
            self.assertTrue(result['txt_warning'])
            if os.name!='nt':self.assertEqual((root/'.env').stat().st_mode & 0o777,0o600)


class DiscoveryTests(unittest.TestCase):
    def catalogue(self,url,**kwargs):
        if url.endswith('/key'):return {'data':{'label':'fixture account'}}
        if 'googleapis' in url:
            return {'models':[{'name':'models/gemini-2.5-flash','supportedGenerationMethods':['generateContent']}, {'name':'models/embedding-model','supportedGenerationMethods':['embedContent']}]}
        if 'groq' in url:return {'data':[{'id':'llama-3.3-70b-versatile'},{'id':'whisper-large'}]}
        return {'data':[{'id':'openrouter/free'}]}

    def test_discovery_builds_checked_ordered_profiles_and_persists_no_keys(self):
        with tempfile.TemporaryDirectory() as temp,patch.dict(os.environ,KEYS,clear=True),patch('forge.cloud.request_json',side_effect=self.catalogue):
            cloud=CloudSetup(temp);checks=cloud.check()
            self.assertEqual(checks['gemini']['models'],['gemini-2.5-flash'])
            profile=cloud.select({p:c['selected'] for p,c in checks.items()})
            self.assertEqual(profile['planner']['provider'],'gemini')
            self.assertEqual([c['provider'] for c in profile['coder']['fallbacks']],['groq','openrouter'])
            self.assertEqual(profile['coder']['fallbacks'][0]['options']['num_predict'],4096)
            self.assertTrue(uses_cloud(validate_config(profile['coder'])))
            text=cloud.path.read_text();self.assertTrue(all(key not in text for key in KEYS.values()))
            self.assertEqual(CloudSetup(temp).selected,cloud.selected)
            changed=cloud.select({p:c['selected'] for p,c in checks.items()}, {'groq':2048})
            self.assertEqual(changed['coder']['fallbacks'][0]['options']['num_predict'],2048)
            self.assertEqual(CloudSetup(temp).limits['groq'],2048)
            with self.assertRaises(ValueError):cloud.select({'groq':checks['groq']['selected']},{'groq':True})

    def test_openrouter_public_catalogue_is_not_used_as_key_validation(self):
        with tempfile.TemporaryDirectory() as temp,patch.dict(os.environ,{'OPENROUTER_API_KEY':'invalid-fixture'},clear=True),patch('forge.cloud.request_json',side_effect=ModelError('Unauthorized','auth')) as request:
            cloud=CloudSetup(temp);result=cloud.check()
            self.assertEqual(result['openrouter']['status'],'auth')
            self.assertEqual(request.call_count,1)
            self.assertTrue(request.call_args.args[0].endswith('/key'))

    def test_missing_or_bad_provider_does_not_hide_healthy_tier(self):
        with tempfile.TemporaryDirectory() as temp,patch.dict(os.environ,{'GROQ_API_KEY':'fixture-groq'},clear=True),patch('forge.cloud.request_json',side_effect=self.catalogue) as request:
            cloud=CloudSetup(temp);checks=cloud.check();self.assertEqual(request.call_count,1)
            self.assertEqual(checks['gemini']['status'],'missing_key')
            profile=cloud.select({'groq':checks['groq']['selected']})
            self.assertNotIn('fallbacks',profile['coder']);self.assertEqual(profile['coder']['provider'],'groq')
            with self.assertRaises(ValueError):cloud.select({'groq':'made-up-model'})
        with tempfile.TemporaryDirectory() as temp,patch.dict(os.environ,KEYS,clear=True),patch('forge.cloud.request_json',side_effect=ModelError('Unauthorized','auth')):
            cloud=CloudSetup(temp);self.assertTrue(all(c['status']=='auth' for c in cloud.check().values()))
            with self.assertRaises(ValueError):cloud.select({'gemini':'gemini-3.8-flash'})


class PoolTests(unittest.TestCase):
    def test_validates_flat_unique_routes_and_consent_for_tail(self):
        validate_config(CHAIN)
        self.assertTrue(uses_cloud({'provider':'ollama','model':'local','fallbacks':[{'provider':'groq','model':'cloud'}]}))
        for config in [{**CHAIN,'fallback':{'provider':'ollama','model':'x'}}, {**CHAIN,'fallbacks':[CHAIN]}, {**CHAIN,'fallbacks':[{'provider':'gemini','model':'checked-gemini'}]}, {**CHAIN,'fallbacks':CHAIN['fallbacks']*2}]:
            with self.subTest(config=config),self.assertRaises(ValueError):validate_config(config)

    def test_failover_order_actual_provider_ledger_and_cooldown(self):
        with tempfile.TemporaryDirectory() as temp:
            models=ScriptedModels([ModelError('Unavailable','transport'),ModelError('Limited','rate_limit',60),PLAN,ModelError('Unavailable','transport'),PLAN])
            bench=Workbench(Path(temp),models);state=state_for(bench)
            self.assertEqual(bench.call_model(state,'coder','fixture','{}',threading.Event()),PLAN)
            self.assertEqual([c['provider'] for c in state['model_calls']],['gemini','groq','openrouter'])
            self.assertTrue(state['model_calls'][-1]['success'])
            bench.call_model(state,'coder','fixture','{}',threading.Event())
            self.assertEqual([c['provider'] for c in state['model_calls'][-2:]],['gemini','openrouter'])
            self.assertEqual(len(models.calls),5)

    def test_format_errors_stay_in_correction_loop_not_service_failover(self):
        with tempfile.TemporaryDirectory() as temp:
            models=ScriptedModels([ModelError('Invalid JSON','format')]);bench=Workbench(Path(temp),models);state=state_for(bench)
            with self.assertRaises(ModelError) as error:bench.call_model(state,'coder','fixture','{}',threading.Event())
            self.assertEqual(error.exception.category,'format');self.assertEqual(len(models.calls),1)
            state['job_cloud_consent']=False
            with self.assertRaisesRegex(ValueError,'consent'):bench.call_model(state,'coder','fixture','{}',threading.Event())
            self.assertEqual(len(models.calls),1)

    def test_all_tiers_fail_once_and_planner_stops_without_repeating_pool(self):
        with tempfile.TemporaryDirectory() as temp:
            models=ScriptedModels([ModelError('Unavailable','transport')]*3)
            bench=Workbench(Path(temp),models)
            created=bench.create('Create a local task tracker.',CHAIN,CHAIN,cloud_consent=True)
            state=await_job(bench,created['id'])
            self.assertEqual(state['status'],'error');self.assertEqual(len(models.calls),3)
            self.assertIn('All configured cloud tiers',state['error'])

    def test_reported_tokens_are_kept_even_for_invalid_or_truncated_output(self):
        with tempfile.TemporaryDirectory() as temp,patch.dict(os.environ,KEYS),patch('forge.models.request_json',return_value={
            'choices':[{'message':{'content':'invalid-json'},'finish_reason':'stop'}],
            'usage':{'prompt_tokens':123,'completion_tokens':17}}):
            bench=Workbench(Path(temp));state=state_for(bench)
            with self.assertRaises(ModelError):bench.call_model(state,'coder','fixture','{}',threading.Event())
            self.assertEqual(len(state['model_calls']),1)
            self.assertFalse(state['model_calls'][0]['success'])
            self.assertEqual(state['model_calls'][0]['prompt_tokens'],123)
            self.assertEqual(state['model_calls'][0]['completion_tokens'],17)
        with patch.dict(os.environ,KEYS),patch('forge.models.request_json',return_value={
            'choices':[{'finish_reason':'length'}],'usage':{'prompt_tokens':20,'completion_tokens':4096}}):
            client=ModelClient('groq','fixture')
            with self.assertRaises(ModelError):client.complete('fixture','{}')
            self.assertEqual(client.last_usage['completion_tokens'],4096)
            with patch('forge.models.request_json',side_effect=ModelError('Unavailable','transport')):
                with self.assertRaises(ModelError):client.complete('fixture','{}')
            self.assertEqual(client.last_usage,{})

    def test_stop_between_tiers_does_not_send_next_request(self):
        with tempfile.TemporaryDirectory() as temp:
            cancel=threading.Event()
            class StopClient:
                calls=0
                def __call__(self,provider,model):return self
                def complete(self,system,prompt):
                    self.calls+=1;cancel.set();raise ModelError('Unavailable','transport')
            client=StopClient();bench=Workbench(Path(temp),client);state=state_for(bench)
            with self.assertRaises(InterruptedError):bench.call_model(state,'coder','fixture','{}',cancel)
            self.assertEqual(client.calls,1)

    def test_real_loopback_http_requests_use_auth_caps_and_fail_over(self):
        requests=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                data=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                requests.append((self.path,data,self.headers.get('Authorization')))
                status=429 if '/gemini/' in self.path else 503 if '/groq/' in self.path else 200
                response={'choices':[{'message':{'content':json.dumps(PLAN)}}],'usage':{'prompt_tokens':25,'completion_tokens':10}}
                content=json.dumps(response).encode();self.send_response(status);self.send_header('Content-Length',str(len(content)));self.end_headers();self.wfile.write(content)
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            providers={p:(f'http://127.0.0.1:{server.server_port}/{p}',v) for p,v in [('gemini','GEMINI_API_KEY'),('groq','GROQ_API_KEY'),('openrouter','OPENROUTER_API_KEY')]}
            with tempfile.TemporaryDirectory() as temp,patch.dict(os.environ,KEYS),patch.dict('forge.models.PROVIDERS',providers):
                bench=Workbench(Path(temp));state=state_for(bench)
                result=bench.call_model(state,'coder','fixture','{}',threading.Event())
                self.assertEqual(result,PLAN)
                self.assertEqual([path.split('/')[1] for path,_,_ in requests],['gemini','groq','openrouter'])
                self.assertTrue(all(0<r[1]['max_tokens']<=8192 for r in requests))
                self.assertEqual(requests[-1][2],'Bearer fixture-router')
                self.assertEqual(state['model_calls'][-1]['completion_tokens'],10)
        finally:server.shutdown();server.server_close()
