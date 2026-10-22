"""Actual Test → Diag HTTP/UI workflow; provider/model replies are fixtures."""
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
from tests.test_workbench import ScriptedModels,await_job
from tests.fixtures import PLAN


def main():
    models=ScriptedModels([PLAN,{'answer':7},{'answer':7}])
    info={'ollama':{'connected':True,'models':['fixture-local']}}
    catalogue={'gemini':{'status':'catalogue_available','models':['fixture-cloud']}}
    with tempfile.TemporaryDirectory() as folder,patch('forge.server.connection_info',return_value=info),patch('forge.cloud.CloudSetup.check',return_value=catalogue),patch('forge.models.request_json',return_value={}):
        bench=Workbench(Path(folder)/'projects',models)
        config={'provider':'ollama','model':'fixture-local'}
        state=await_job(bench,bench.create('PRIVATE TEST PROJECT IDEA',config,config)['id'])
        state['planner']={'provider':'gemini','model':'fixture-cloud'};bench.save(state)
        original=json.dumps(state['plan'],sort_keys=True)
        server=make_server(0,bench);threading.Thread(target=server.serve_forever,daemon=True).start()
        base='http://127.0.0.1:'+str(server.server_port)
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(executable_path=shutil.which('chromium'))
                page=browser.new_page(viewport={'width':1440,'height':1100});errors=[]
                page.on('pageerror',lambda error:errors.append(str(error)))
                page.goto(base);page.locator('#projects .project-link').first.click()
                page.locator('#diag-button').click()
                expect(page.locator('#diag-status')).to_contain_text('Evidence ready',timeout=15000)
                page.locator('#diag-advanced summary').click()
                page.locator('#system-test-button').click()
                expect(page.locator('#system-test-dialog')).to_be_visible()
                assert len(models.calls)==1
                page.locator('#system-test-start').click()
                expect(page.locator('#system-test-status')).to_contain_text('Run finished',timeout=15000)
                assert len(models.calls)==1
                expect(page.locator('#system-test-results')).to_contain_text('Private workspace storage')
                page.locator('#system-test-mode').select_option('cloud')
                page.locator('#system-test-start').click()
                expect(page.locator('#system-test-status')).to_contain_text('explicitly')
                assert len(models.calls)==1
                page.locator('#system-test-consent').check();page.locator('#system-test-start').click()
                expect(page.locator('#system-test-status')).to_contain_text('Run finished',timeout=15000)
                expect(page.locator('#system-test-results')).to_contain_text('Model response test')
                assert len(models.calls)==3
                assert all(call=={'numbers':[2,5],'operation':'add'} for call in models.calls[1:])
                page.locator('#system-test-close').click();page.locator('#diag-button').click()
                expect(page.locator('#diag-status')).to_contain_text('Evidence ready',timeout=15000)
                expect(page.locator('#diag-summary')).to_contain_text('Latest Test: finished')
                with page.expect_download() as pending:page.locator('#diag-export').click()
                target=Path(folder)/'diag.zip';pending.value.save_as(target)
                with zipfile.ZipFile(target) as z:
                    report=json.loads(z.read('evidence/system_tests.json'))
                    assert report['status']=='finished' and not report['generation_requested']
                    assert len([r for r in report['rows'] if r['code']=='fixed_json_probe'])==0
                    assert json.loads(z.read('evidence/diagnostic_session.json'))['test_report_id']==report['id']
                    assert b'PRIVATE TEST PROJECT IDEA' not in b''.join(z.read(n) for n in z.namelist())
                assert json.dumps(bench.load(state['id'])['plan'],sort_keys=True)==original
                assert page.request.post(base+'/api/system-tests/start',data={'mode':'quick'}).status==403
                page.locator('#close-diag').click();page.set_viewport_size({'width':390,'height':844})
                page.locator('#diag-button').click()
                expect(page.locator('#diag-status')).to_contain_text('Evidence ready',timeout=15000)
                page.locator('#system-test-button').click();expect(page.locator('#system-test-dialog')).to_be_visible()
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth+1')
                assert not errors,errors
                browser.close()
        finally:server.shutdown();server.server_close()
    print('PASS: Test quick checks without inference -> explicit cloud consent -> two fixed model probes -> persisted results in real Diag ZIP; unchanged project, no project prompt sent, auth boundary, mobile/no JS errors. Fixture providers do not prove live quota or model capacity.')


if __name__=='__main__':main()
