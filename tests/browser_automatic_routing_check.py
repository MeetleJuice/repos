"""Real browser automatic setup and semantic failover; provider catalogues are fixtures."""
import os
from pathlib import Path
import shutil
import sys
import tempfile
import threading
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from playwright.sync_api import sync_playwright, expect
from forge.core import Workbench
from forge.models import ModelError
from forge.providers import PROVIDERS
from forge.server import make_server
from tests.test_provider_pool import ENV, catalogue
from tests.test_workbench import ScriptedModels
from tests.fixtures import PLAN, APP, TEST


def main():
    info={p:{'configured':True,'key_variable':v} for p,(_,v) in PROVIDERS.items()}
    info['ollama']={'configured':True,'connected':True,'models':['qwen2.5-coder:7b']}
    env={k:v for k,v in ENV.items() if k!='CLOUDFLARE_ACCOUNT_ID'}
    with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,env,clear=True),patch('forge.cloud.request_json',side_effect=catalogue),patch('forge.server.connection_info',return_value=info):
        models=ScriptedModels([ModelError('Missing model','model'),{},{},PLAN,{'files':{'app.py':APP,'test_app.py':TEST}}])
        bench=Workbench(Path(d)/'projects',models);server=make_server(0,bench)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(executable_path=shutil.which('chromium'));page=browser.new_page(viewport={'width':1440,'height':1000})
                errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto('http://127.0.0.1:'+str(server.server_port))
                page.locator('#connections-button').click()
                expect(page.locator('#cloud-advanced')).not_to_have_attribute('open','')
                page.locator('#cloud-auto').click()
                expect(page.locator('#cloud-feedback')).to_contain_text('Automatic routes ready',timeout=15000)
                assert not models.calls
                page.locator('#close-connections').click();page.reload()
                page.locator('#idea').fill('Build a small task tracker')
                page.locator('#propose').click()
                assert not models.calls
                page.locator('#create-cloud').check();page.locator('#propose').click()
                expect(page.locator('#project-status')).to_have_text('proposed',timeout=15000)
                state=bench.list_projects()[0]
                assert [r['provider'] for r in state['model_calls']]==['gemini','groq','groq','openrouter']
                assert [r.get('failure_class') for r in state['model_calls'][:3]]==['provider_unavailable','schema_error','schema_error']
                assert not state['approved']
                page.locator('#approve').click();page.locator('#runtime').select_option('local')
                page.locator('#execution-consent').check();page.locator('#project-cloud-consent').check();page.locator('#repairs').select_option('0')
                page.locator('#verify').click();expect(page.locator('#project-status')).to_have_text('verified',timeout=20000)
                page.locator('#connections-button').click();page.locator('#cloud-auto').click()
                expect(page.locator('#cloud-feedback')).to_contain_text('and this project',timeout=15000)
                expect(page.locator('#project-status')).to_have_text('verified')
                page.set_viewport_size({'width':390,'height':844})
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                text=page.locator('body').inner_text();assert not any(v in text for v in ENV.values())
                assert not errors,errors
                browser.close()
        finally:server.shutdown();server.server_close()
    print('PASS: automatic catalogue setup, role routes persisted, missing Cloudflare config skipped, no pre-consent inference, model error and invalid proposals advance without restart, actual app verification, current project preservation, mobile, no secret values or JavaScript errors.')


if __name__=='__main__':main()
