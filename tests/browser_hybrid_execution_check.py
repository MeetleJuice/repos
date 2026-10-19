"""Chromium hybrid setup/local dispatch, source-supported task and real verification."""
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
from forge.providers import PROVIDERS
from forge.server import make_server
from tests.fixtures import PLAN,APP,TEST
from tests.test_workbench import ScriptedModels


def main():
    config={'provider':'gemini','model':'fixture-saved'}
    profile={'planner':config,'coder':config}
    info={p:{'configured':p=='gemini','key_variable':v} for p,(_,v) in PROVIDERS.items()}
    info['ollama']={'configured':True,'connected':True,'models':['qwen3.5:9b']}
    import copy
    from tests.test_task_contracts import structured_plan
    from tests.test_hybrid_execution import supported
    from tests.test_automatic_routing import catalogue
    plan=structured_plan();second=copy.deepcopy(plan['tasks'][0]);second['title']='Inspect existing server';second['depends_on']=[0];plan['tasks'].append(second)
    providers=[]
    class RoutedModels(ScriptedModels):
        def __call__(self,provider,model):providers.append(provider);return self
    with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'GEMINI_API_KEY':'fixture-workflow-secret'},clear=True),patch('forge.server.connection_info',return_value=info),patch('forge.cloud.request_json',side_effect=catalogue):
        home=Path(d);(home/'cloud-models.json').write_text(json.dumps({'automatic_routes':profile,'models':{'gemini':'fixture-saved'}}))
        models=RoutedModels([plan,{'files':{'app.py':APP,'test_app.py':TEST}},supported()]);bench=Workbench(home/'projects',models);server=make_server(0,bench)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(executable_path=shutil.which('chromium'));page=browser.new_page(viewport={'width':1440,'height':1000})
                errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto('http://127.0.0.1:'+str(server.server_port))
                page.locator('#connections-button').click()
                page.locator('#routing-mode').select_option('hybrid');page.locator('#cloud-auto').click()
                expect(page.locator('#cloud-feedback')).to_contain_text('Automatic routes ready',timeout=15000)
                page.locator('#close-connections').click()
                assert not models.calls
                page.locator('#idea').fill('Build a task tracker with persistence');page.locator('#create-cloud').check();page.locator('#propose').click()
                expect(page.locator('#project-status')).to_have_text('proposed',timeout=10000)
                page.locator('#workflow-overview > summary').click()
                expect(page.locator('.workflow-card')).to_have_count(5)
                expect(page.locator('#workflow-summary')).to_contain_text('Review the proposal')
                # Repeated identical polls preserve nodes/focus; overlapping calls coalesce.
                page.evaluate("window.workflowNode=document.querySelector('.workflow-card'); window.workflowCalls=0; window.realFetch=window.fetch; window.fetch=(...args)=>{if(String(args[0]).endsWith('/workflow'))window.workflowCalls++;return window.realFetch(...args)}")
                page.evaluate("async()=>{await Promise.all([refreshWorkflow(current.id),refreshWorkflow(current.id)]);await refreshWorkflow(current.id)}")
                assert page.evaluate("window.workflowCalls===2 && window.workflowNode===document.querySelector('.workflow-card')")

                expect(page.locator('#tasks')).to_contain_text('Outcome:')
                expect(page.locator('#tasks')).to_contain_text('Files: app.py, test_app.py')
                expect(page.locator('#tasks')).to_contain_text('Criteria are declared, not verified.')
                page.locator('#approve').click();page.locator('#runtime').select_option('local')
                page.locator('#execution-consent').check();page.locator('#project-cloud-consent').check();page.locator('#repairs').select_option('0');page.locator('#verify').click()
                expect(page.locator('#project-status')).to_have_text('verified',timeout=20000)
                expect(page.locator('#workflow-summary')).to_contain_text('Download this verified snapshot',timeout=5000)
                expect(page.locator('#workflow-receipts li')).to_have_count(2)
                page.get_by_role('tab',name='Project files').click()
                with page.expect_download() as download:page.locator('#download').click()
                path=home/'app.zip';download.value.save_as(path)
                with zipfile.ZipFile(path) as archive:
                    guide=archive.read('generated-app/.foundry/DELIVERY.md').decode();assert 'Current overall acceptance: YES' in guide
                    report=json.loads(archive.read('generated-app/BUILD-REPORT.json'))
                    assert report['workflow']['evidence']['accepted_current'];assert len(report['task_receipts'])==2
                    assert report['task_receipts'][0]['task_packet']['structured']
                    assert report['task_receipts'][1]['disposition']=='existing_source_supported'
                    assert not report['task_receipts'][1]['source_changed']
                    assert [row['provider'] for row in report['model_calls']]==['gemini','ollama','ollama'],report['model_calls']
                    assert 'generated-app/outside.js' not in archive.namelist()
                    for entry in report['file_manifest']:
                        import hashlib
                        assert hashlib.sha256(archive.read('generated-app/'+entry['file'])).hexdigest()==entry['sha256']
                page.set_viewport_size({'width':390,'height':844})
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                assert 'fixture-workflow-secret' not in page.locator('body').inner_text();assert not errors,errors
                # Existing explicit browser choices win over server defaults.
                page.evaluate("localStorage.setItem('foundry-models',JSON.stringify({planner:{provider:'ollama',model:'manual-local'},coder:{provider:'ollama',model:'manual-local'}}))")
                page.reload();expect(page.locator('#planner-model')).to_have_value('manual-local')
                browser.close()
        finally:server.shutdown();server.server_close()
    print('PASS: hybrid mode setup, cloud planner/local builder dispatch, source-supported no-change receipt and real verification/ZIP; fresh-browser automatic route restore without inference, five-category workflow, declared coverage, exact task receipt, actual generated-app verification, ZIP guide/source hashes, manual route preservation, mobile, no exposed keys or JS errors.')


if __name__=='__main__':main()
