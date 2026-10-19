"""Real UI + actual app verification; all cloud responses use controlled local fixtures."""
from pathlib import Path
import json
import os
import shutil
import sys
import tempfile
import threading
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from playwright.sync_api import sync_playwright, expect
from forge.core import Workbench
from forge.models import ModelError
from forge.server import make_server
from tests.test_cloud import DiscoveryTests, KEYS
from tests.test_workbench import ScriptedModels
from tests.fixtures import PLAN, APP, TEST


def main():
    with tempfile.TemporaryDirectory() as temp,patch.dict(os.environ,{},clear=False),patch('forge.cloud.request_json',side_effect=DiscoveryTests().catalogue):
        for key in [*KEYS,'OPENROUTER_KEY']:os.environ.pop(key,None)
        models=ScriptedModels([ModelError('Rate limited','rate_limit',60),ModelError('Service unavailable','transport'),PLAN,
                               ModelError('Service unavailable','transport'),{'files':{'app.py':APP,'test_app.py':TEST}}])
        bench=Workbench(Path(temp)/'projects',models);server=make_server(0,bench)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(executable_path=shutil.which('chromium'))
                page=browser.new_page(viewport={'width':1280,'height':1000});errors=[]
                page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto(f'http://127.0.0.1:{server.server_port}')
                page.locator('#connections-button').click()
                expect(page.locator('#cloud-env-status')).to_contain_text('0/3 API keys')
                content='\ufeffGEMINI_API_KEY=fixture-gemini\nGROQ_API_KEY=fixture-groq\nOPENROUTER_KEY=fixture-router\n'
                page.locator('#cloud-env-file').set_input_files({'name':'.env.txt','mimeType':'text/plain','buffer':content.encode('utf-16le')})
                expect(page.locator('#cloud-env-status')).to_contain_text('3/3 API keys',timeout=10000)
                assert all(key not in page.content() for key in KEYS.values())
                assert (Path(temp)/'.env').is_file()
                page.locator('#cloud-check').click()
                expect(page.locator('#cloud-model-gemini')).to_have_value('gemini-2.5-flash',timeout=10000)
                expect(page.locator('#cloud-model-groq')).to_have_value('llama-3.3-70b-versatile')
                page.locator('#cloud-new').click()
                expect(page.locator('#cloud-feedback')).to_contain_text('Cloud route applied')
                assert len(models.calls)==0
                page.locator('#close-connections').click()
                page.reload()
                expect(page.locator('#planner-provider')).to_have_value('gemini')
                await_ready=page.locator('#coder-pool-label')
                expect(await_ready).to_contain_text('openrouter/openrouter/free')
                page.locator('#idea').fill('Build a small task tracker with persistent storage.')
                page.locator('#propose').click()
                expect(page.locator('#notice')).to_contain_text('Confirm')
                assert len(models.calls)==0
                page.locator('#create-cloud').check();page.locator('#propose').click()
                expect(page.locator('#project-status')).to_have_text('proposed',timeout=15000)
                state=bench.list_projects()[0]
                assert [c['provider'] for c in state['model_calls']]==['gemini','groq','openrouter']
                assert state['planning_stats']['fallback_used']
                page.locator('#approve').click()
                page.locator('#runtime').select_option('local');page.locator('#execution-consent').check()
                page.locator('#project-cloud-consent').check();page.locator('#repairs').select_option('0')
                page.locator('#verify').click()
                expect(page.locator('#project-status')).to_have_text('verified',timeout=20000)
                state=bench.load(state['id'])
                assert [c['provider'] for c in state['model_calls'][-2:]]==['groq','openrouter']
                assert state['checks']['passed'] and state['checks']['phases'][1]['tests_run']>0
                expect(page.locator('#model-usage')).to_contain_text('Last response: openrouter/openrouter/free')
                page.locator('#edit-models').click()
                expect(page.locator('#project-coder-pool-label')).to_contain_text('openrouter/openrouter/free')
                page.locator('#model-form button[type=submit]').click()
                assert len(bench.load(state['id'])['coder']['fallbacks'])==2
                token=page.locator('meta[name=foundry-token]').get_attribute('content')
                endpoint=f'http://127.0.0.1:{server.server_port}/api/cloud/import'
                assert page.request.post(endpoint,data={'text':'GROQ_API_KEY=ignored'}).status==403
                info=page.request.get(f'http://127.0.0.1:{server.server_port}/api/connections',headers={'X-Foundry-Token':token}).text()
                assert all(key not in info for key in KEYS.values())
                before=bench.files(state['id']);calls=len(models.calls)
                page.locator('#connections-button').click()
                page.locator('#cloud-limit-groq').select_option('2048')
                page.locator('#cloud-project').click()
                expect(page.locator('#cloud-feedback')).to_contain_text('Cloud route applied')
                changed=bench.load(state['id'])
                assert changed['coder']['fallbacks'][0]['options']['num_predict']==2048
                assert changed['approved'] and changed['plan']==state['plan']
                assert len(models.calls)==calls and bench.files(state['id'])==before
                page.set_viewport_size({'width':390,'height':844})
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                assert not errors,errors
                browser.close()
                print('PASS: UTF-16 Notepad .env.txt → private key import → checked catalogues → persisted cloud route → consent gate → Gemini/Groq/OpenRouter failover → real generated-app HTTP/tests/launch → cooldown skip → saved project settings; no secret responses, auth boundary, mobile and no JS errors.')
        finally:server.shutdown();server.server_close()


if __name__=='__main__':main()
