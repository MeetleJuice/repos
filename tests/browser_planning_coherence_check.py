"""Old green proposal -> current blocker -> Test/Diag; hybrid build/ZIP regression."""
import io
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
from forge.server import make_server
from tests.fixtures import PLAN
from tests.test_workbench import ScriptedModels,await_job
from tests.test_planning_coherence import uploaded_plan
from tests.browser_evidence_planning_check import main as build_hybrid


def main():
    models=ScriptedModels([PLAN])
    with tempfile.TemporaryDirectory() as folder,patch('forge.server.connection_info',return_value={'ollama':{'connected':True,'models':['fixture']}}),patch('forge.cloud.CloudSetup.check',return_value={}),patch('forge.models.request_json',return_value={}):
        bench=Workbench(Path(folder)/'projects',models);config={'provider':'ollama','model':'fixture'}
        state=await_job(bench,bench.create('PRIVATE IDEA NEVER EXPORTED',config,config)['id'])
        state.update(plan=uploaded_plan(),plan_review={'passed':True},evidence_planning=True)
        bench.save(state);original=bench.load(state['id'])
        server=make_server(0,bench);threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(executable_path=shutil.which('chromium'))
                page=browser.new_page(viewport={'width':1440,'height':1000});errors=[]
                page.on('pageerror',lambda error:errors.append(str(error)))
                page.goto('http://127.0.0.1:'+str(server.server_port));page.locator('#projects .project-link').first.click()
                expect(page.locator('#proposal-review-status')).to_have_text('Resolve proposal contradictions before approval · earlier saved pass does not meet the current checks')
                expect(page.locator('#approve')).to_be_disabled()
                expect(page.locator('#proposal-findings')).to_contain_text('endpoint')
                page.locator('#diag-button').click()
                expect(page.locator('#diag-status')).to_contain_text('Evidence ready',timeout=15000)
                page.locator('#diag-advanced summary').click()
                page.locator('#system-test-button').click();page.locator('#system-test-start').click()
                expect(page.locator('#system-test-status')).to_contain_text('Run finished',timeout=15000)
                expect(page.locator('#system-test-results')).to_contain_text('8 fixed guard scenarios')
                expect(page.locator('#system-test-results')).to_contain_text('task_endpoint_mismatch')
                page.locator('#system-test-close').click();page.locator('#diag-button').click()
                expect(page.locator('#diag-summary')).to_contain_text('Selected proposal · current local review: needs attention',timeout=15000)
                with page.expect_download() as pending:page.locator('#diag-export').click()
                target=Path(folder)/'diag.zip';pending.value.save_as(target)
                with zipfile.ZipFile(target) as z:
                    rows=json.loads(z.read('evidence/projects.json'));audit=rows[0]['planning']['current_review']
                    assert not audit['passed'] and audit['duplicate_task_groups']
                    assert audit['restart_check_indexes']==[]
                    assert 'missing_persistence_scenario' in audit['review_codes']
                    result=json.loads(z.read('evidence/system_tests.json'))
                    assert next(row for row in result['rows'] if row['code']=='project_plan')['status']=='failed'
                    assert b'PRIVATE IDEA NEVER EXPORTED' not in b''.join(z.read(name) for name in z.namelist())
                assert bench.load(state['id'])==original
                assert len(models.calls)==1 and not bench.context_files(state['id'])
                page.locator('#close-diag').click();page.set_viewport_size({'width':390,'height':844})
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
                assert not errors,errors
                browser.close()
        finally:server.shutdown();server.server_close()
    build_hybrid(granular=True,hybrid=True)
    print('PASS: old green contradictory proposal blocked without mutation; eight planning guards and selected-plan failure in Test/Diag ZIP; hybrid browser/API granular planning, real early SQLite milestone, actual browser/manual checks and verified ZIP. Model replies are fixtures.')


if __name__=='__main__':main()
