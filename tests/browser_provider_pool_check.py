"""Seven-provider setup through real Chromium; provider responses are fixtures."""
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import zipfile
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from playwright.sync_api import sync_playwright, expect
from forge.core import Workbench
from forge.models import ModelError
from forge.providers import PROVIDERS, CLOUD_ORDER, SECRET_NAMES
from forge.server import make_server
from tests.test_provider_pool import ENV, MODELS, catalogue
from tests.test_workbench import ScriptedModels
from tests.fixtures import PLAN, APP, TEST


def main():
    provider_info={p:{'configured':False,'key_variable':v} for p,(_,v) in PROVIDERS.items()}
    provider_info['ollama']={'configured':True,'connected':True,'models':['qwen2.5-coder:7b']}
    with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,{},clear=False),patch('forge.cloud.request_json',side_effect=catalogue),patch('forge.server.connection_info',return_value=provider_info),patch('forge.server.runtime_diagnostics',return_value={'installed':False,'running':False,'image_ready':False}):
        for name in [*SECRET_NAMES,'CLOUDFLARE_ACCOUNT_ID','CF_ACCOUNT_ID']:os.environ.pop(name,None)
        models=ScriptedModels([ModelError('Unavailable','transport')]*6+[PLAN,{'files':{'app.py':APP,'test_app.py':TEST}}])
        bench=Workbench(Path(directory)/'projects',models);server=make_server(0,bench)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(executable_path=shutil.which('chromium'));page=browser.new_page(viewport={'width':1440,'height':1000})
                errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto('http://127.0.0.1:'+str(server.server_port));page.locator('#connections-button').click()
                expect(page.locator('#cloud-env-status')).to_contain_text('0/7 API keys')
                env='\n'.join(k+'='+v for k,v in ENV.items() if k!='CLOUDFLARE_ACCOUNT_ID')
                page.locator('#cloud-env-file').set_input_files({'name':'.env.txt','mimeType':'text/plain','buffer':env.encode()})
                expect(page.locator('#cloud-env-status')).to_contain_text('7/7 API keys')
                page.locator('#cloud-check').click()
                expect(page.locator('[data-provider="cloudflare"]')).to_contain_text('missing_configuration',timeout=15000)
                expect(page.locator('#cloud-model-nvidia')).to_be_enabled()
                page.locator('#cloud-env-file').set_input_files({'name':'.env.txt','mimeType':'text/plain','buffer':('CLOUDFLARE_ACCOUNT_ID='+'a'*32).encode()})
                page.locator('#cloud-check').click()
                expect(page.locator('#cloud-model-cloudflare')).to_be_enabled(timeout=15000)
                for provider,model in MODELS.items():page.locator('#cloud-model-'+provider).select_option(model)
                for _ in range(4):page.get_by_role('button',name='Move nvidia earlier',exact=True).click()
                order=page.locator('.cloud-provider-card').evaluate_all('(cards)=>cards.map(c=>c.dataset.provider)')
                assert order[0]=='nvidia'
                page.locator('#cloud-timeout-nvidia').select_option('15')
                page.locator('#cloud-json-nvidia').uncheck()
                page.locator('#cloud-new').click();expect(page.locator('#cloud-feedback')).to_contain_text('Cloud route applied')
                page.locator('#close-connections').click();page.reload()
                expect(page.locator('#planner-provider')).to_have_value('nvidia')
                expect(page.locator('#planner-timeout')).to_have_value('15')
                page.locator('#idea').fill('Build a small persistent task tracker')
                page.locator('#create-cloud').check();page.locator('#propose').click()
                expect(page.locator('#project-status')).to_have_text('proposed',timeout=15000)
                state=bench.list_projects()[0]
                assert [c['provider'] for c in state['model_calls']]==order
                page.locator('#approve').click();page.locator('#runtime').select_option('local')
                page.locator('#execution-consent').check();page.locator('#project-cloud-consent').check();page.locator('#repairs').select_option('0')
                page.locator('#verify').click();expect(page.locator('#project-status')).to_have_text('verified',timeout=20000)
                state=bench.load(state['id']);assert state['checks']['passed']
                assert state['coder']['options']['timeout_seconds']==15
                assert not state['coder']['options']['structured_outputs']
                assert len(state['coder']['fallbacks'])==6
                page.get_by_role('tab',name='Project files').click()
                with page.expect_download() as download:page.locator('#download').click()
                destination=Path(directory)/'app.zip';download.value.save_as(destination)
                with zipfile.ZipFile(destination) as archive:
                    report=json.loads(archive.read('generated-app/BUILD-REPORT.json'))
                    assert report['evidence_status']['automated_evidence_current']
                    assert len(report['models']['coder']['fallbacks'])==6
                page.locator('#connections-button').click()
                expect(page.locator('#cloud-timeout-nvidia')).to_have_value('15')
                page.set_viewport_size({'width':390,'height':844})
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                assert all(value not in page.content() for key,value in ENV.items() if key!='CLOUDFLARE_ACCOUNT_ID')
                assert not errors,errors
                browser.close()
                print('PASS: seven-key private import; missing Cloudflare account then local configuration import; seven catalogues; reordered route; timeout/JSON settings persisted; seven-tier failover; actual app verification/export; mobile; no exposed keys or JS errors.')
        finally:server.shutdown();server.server_close()

if __name__=='__main__':main()
