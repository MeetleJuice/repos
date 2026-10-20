"""A fresh local project needs no manual fallback configuration."""
import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import zipfile
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from playwright.sync_api import sync_playwright,expect
from forge.core import Workbench
from forge.models import ModelError
from forge.providers import PROVIDERS
from forge.server import make_server
from tests.fixtures import PLAN,APP,TEST
from tests.test_workbench import ScriptedModels


def main():
    info={provider:{'configured':False,'key_variable':key} for provider,(_,key) in PROVIDERS.items()}
    info['ollama']={'configured':True,'connected':True,'models':['qwen3.5:9b','qwen2.5-coder:7b','granite4.2:8b','qwen2.5:7b','nomic-embed-text:latest']}
    responses=[ModelError('First timed out','transport',transport_kind='timeout'),ModelError('Second timed out','transport',transport_kind='timeout'),PLAN,
               {'files':{}},{'files':{}},{'files':{'app.py':APP,'test_app.py':TEST}}]
    models=ScriptedModels(responses)
    with tempfile.TemporaryDirectory() as temp,patch('forge.server.connection_info',return_value=info),patch('forge.cloud.request_json') as cloud:
        home=Path(temp);bench=Workbench(home/'projects',models);server=make_server(0,bench)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(executable_path=shutil.which('chromium'));page=browser.new_page(viewport={'width':1440,'height':1050})
                errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
                page.goto('http://127.0.0.1:'+str(server.server_port))
                page.locator('#idea').fill('Build a small task tracker with SQLite persistence')
                page.locator('#propose').click()
                expect(page.locator('#project-status')).to_have_text('proposed',timeout=15000)
                state=bench.list_projects()[0];ident=state['id']
                planning=[call for call in state['model_calls'] if call['role']=='planner']
                assert len(planning)==3 and len({call['model'] for call in planning})==3
                assert all(call['provider']=='ollama' for call in planning)
                assert 'fallbacks' not in state['planner'], 'Saved primary must not be silently rewritten'
                expect(page.locator('#local-failover-status')).to_contain_text('granite4.2:8b')
                expect(page.locator('#local-failover-status')).not_to_contain_text('nomic-embed')
                page.locator('#approve').click();page.locator('#runtime').select_option('local');page.locator('#execution-consent').check()
                page.locator('#repairs').select_option('0');page.locator('#verify').click()
                expect(page.locator('#project-status')).to_have_text('verified',timeout=25000)
                state=bench.load(ident);coding=[call for call in state['model_calls'] if call['role']=='coder']
                assert len(coding)==3 and len({call['model'] for call in coding})==3
                assert state['plan']==PLAN and state['checks']['passed']
                page.get_by_role('tab',name='Project files').click()
                with page.expect_download() as download:page.locator('#download').click()
                target=home/'app.zip';download.value.save_as(target)
                with zipfile.ZipFile(target) as archive:
                    report=json.loads(archive.read('generated-app/BUILD-REPORT.json'));assert report['checks']['passed']
                    assert archive.read('generated-app/app.py').decode()==APP
                page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                cloud.assert_not_called();assert not errors,errors
                browser.close()
        finally:server.shutdown();server.server_close()
    print('PASS: fresh project automatically detects local backups without model setup; two transport failures advance to third distinct Ollama model; two rejected code responses advance to third distinct builder; unchanged saved primary/approved plan; actual app verification and ZIP; no cloud calls/mobile overflow/JS errors. Model replies are fixtures.')


if __name__=='__main__':main()
