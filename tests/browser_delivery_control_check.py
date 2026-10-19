"""Chromium local calibration, focused task context, readiness and source-bound delivery."""
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
    from tests.test_task_contracts import structured_plan
    plan=structured_plan();plan['context_policy']='focused_v1'
    plan['tasks'][0]['interfaces']=[{'file':'app.py','symbol':'create_server','contract':'Returns HTTPServer; API response shapes match approved checks.'}]

    with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'GEMINI_API_KEY':'fixture-workflow-secret'},clear=True),patch('forge.server.connection_info',return_value=info):
        home=Path(d);(home/'cloud-models.json').write_text(json.dumps({'automatic_routes':profile,'models':{'gemini':'fixture-saved'}}))
        models=ScriptedModels([plan,{'request_context':['notes.py']},{'files':{'app.py':APP,'test_app.py':TEST}}])
        local=ScriptedModels([{'answer':7},{'edits':[{'file':'sample.py','search':'a + b','replace':'a - b'}]}])
        bench=Workbench(home/'projects',lambda provider,model:local if provider=='ollama' else models);server=make_server(0,bench)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(executable_path=shutil.which('chromium'));page=browser.new_page(viewport={'width':1440,'height':1000})
                errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto('http://127.0.0.1:'+str(server.server_port))
                expect(page.locator('#planner-model')).to_have_value('fixture-saved',timeout=10000)
                assert not models.calls
                page.locator('#connections-button').click();page.locator('#local-calibration > summary').click()
                page.locator('#calibrate-local').click()
                expect(page.locator('#calibration-feedback')).to_contain_text('JSON response passed',timeout=10000)
                assert len(local.calls)==2 and not models.calls
                assert (home/'local-calibration-v1.json').is_file()
                page.locator('#close-connections').click()
                page.locator('#idea').fill('Build a task tracker with persistence');page.locator('#create-cloud').check();page.locator('#propose').click()
                expect(page.locator('#project-status')).to_have_text('proposed',timeout=10000)
                page.locator('#workflow-overview > summary').click()
                expect(page.locator('.workflow-card')).to_have_count(5)
                expect(page.locator('#workflow-summary')).to_contain_text('Review the proposal')
                # Repeated identical polls preserve nodes/focus; overlapping calls coalesce.
                page.evaluate("window.workflowNode=document.querySelector('.workflow-card'); window.workflowCalls=0; window.realFetch=window.fetch; window.fetch=(...args)=>{if(String(args[0]).endsWith('/workflow'))window.workflowCalls++;return window.realFetch(...args)}")
                page.evaluate("async()=>{await Promise.all([refreshWorkflow(current.id),refreshWorkflow(current.id)]);await refreshWorkflow(current.id)}")
                assert page.evaluate("window.workflowCalls===2 && window.workflowNode===document.querySelector('.workflow-card')")

                page.locator('#approve').click()
                expect(page.locator('#project-status')).to_have_text('approved')
                state=bench.list_projects()[0];bench.apply(bench.load(state['id']),{'files':{'notes.py':'# café remains intact\nvalue = 3\n'}})
                page.locator('#runtime').select_option('local')
                page.locator('#execution-consent').check();page.locator('#project-cloud-consent').check();page.locator('#repairs').select_option('0');page.locator('#verify').click()
                expect(page.locator('#project-status')).to_have_text('verified',timeout=20000)
                expect(page.locator('#workflow-summary')).to_contain_text('Download this verified snapshot',timeout=5000)
                expect(page.locator('#workflow-receipts li')).to_have_count(1)
                expect(page.locator('#task-board-list')).to_contain_text('Included in accepted app snapshot')
                assert 'notes.py' not in models.calls[-2]['files'] and 'notes.py' in models.calls[-1]['files']
                assert models.calls[-1]['files']['notes.py']=='# café remains intact\nvalue = 3\n'
                page.get_by_role('tab',name='Project files').click()
                with page.expect_download() as download:page.locator('#download').click()
                path=home/'app.zip';download.value.save_as(path)
                with zipfile.ZipFile(path) as archive:
                    guide=archive.read('generated-app/.foundry/DELIVERY.md').decode();assert 'Current overall acceptance: YES' in guide
                    report=json.loads(archive.read('generated-app/BUILD-REPORT.json'))
                    assert report['workflow']['evidence']['accepted_current'];assert len(report['task_receipts'])==1
                    for entry in report['file_manifest']:
                        import hashlib
                        assert hashlib.sha256(archive.read('generated-app/'+entry['file'])).hexdigest()==entry['sha256']
                page.set_viewport_size({'width':390,'height':844})
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                assert 'fixture-workflow-secret' not in page.locator('body').inner_text();assert not errors,errors
                # External source drift blocks model replay; adoption is explicit and does not advance tasks.
                state=bench.list_projects()[0];app_path=bench.directory(state['id'])/'source/app.py'
                app_path.write_text(app_path.read_text()+'\n# reviewed external edit\n')
                before_calls=len(models.calls)
                page.get_by_role('tab',name='Build & results').click();page.locator('#generate').click()
                expect(page.locator('#project-status')).to_have_text('needs attention',timeout=10000)
                expect(page.locator('#resume-warning')).to_contain_text('files changed')
                page.locator('#adopt-resume').click()
                expect(page.locator('#project-status')).to_have_text('approved')
                expect(page.locator('#adopt-resume')).to_be_hidden()
                assert bench.load(state['id'])['next_task']==1 and len(models.calls)==before_calls
                # Existing explicit browser choices win over server defaults.
                page.evaluate("localStorage.setItem('foundry-models',JSON.stringify({planner:{provider:'ollama',model:'manual-local'},coder:{provider:'ollama',model:'manual-local'}}))")
                page.reload();expect(page.locator('#planner-model')).to_have_value('manual-local')
                browser.close()
        finally:server.shutdown();server.server_close()
    print('PASS: explicit local-only calibration, focused source request, task readiness/evidence and source-bound export; fresh-browser automatic route restore without inference, five-category workflow, declared coverage, exact task receipt, actual generated-app verification, ZIP guide/source hashes, manual route preservation, mobile, no exposed keys or JS errors.')


if __name__=='__main__':main()
