"""Real unified Diag workflow; inference is a fixed scripted reply, never a live model."""
import hashlib
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
from playwright.sync_api import expect,sync_playwright
from forge.core import Workbench
from forge.server import make_server
from tests.test_workbench import ScriptedModels,await_job
from tests.fixtures import PLAN


def main():
    reply={'checks':[{'name':'Create record','method':'POST','path':'/api/records','status':201,
                     'body':{'title':'Diagnostic sample'},'assertion':{'kind':'json_subset','expected':{'id':1,'title':'Diagnostic sample'}}}],
           'api_contracts':[{'method':'POST','path':'/api/records','status':201,'response_kind':'object','required_fields':['id','title']}]}
    with tempfile.TemporaryDirectory() as folder,patch('forge.server.connection_info',return_value={'ollama':{'connected':True,'models':['fixture']}}), \
         patch('forge.cloud.CloudSetup.check',return_value={}),patch('forge.diagnostic_report._ollama_probe',return_value={'status':'unavailable'}):
        models=ScriptedModels([PLAN,reply]);bench=Workbench(Path(folder)/'projects',models)
        config={'provider':'ollama','model':'fixture'}
        state=await_job(bench,bench.create('PRIVATE PROJECT NOT IN PROBE',config,config)['id'])
        state_path=bench.directory(state['id'])/'state.json';before=state_path.read_bytes()
        server=make_server(0,bench);threading.Thread(target=server.serve_forever,daemon=True).start()
        entered=threading.Event();release=threading.Event()
        session=server.diagnostic_session
        session.runner.local=lambda:(entered.set(),release.wait(10),{'connected':True})[-1]
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(executable_path=shutil.which('chromium'))
                page=browser.new_page(viewport={'width':1440,'height':1000});errors=[]
                page.on('pageerror',lambda error:errors.append(str(error)))
                base='http://127.0.0.1:'+str(server.server_port)
                page.goto(base);page.locator('#projects .project-link').first.click()
                page.locator('#diag-button').click()
                expect(page.locator('#diag-status')).to_contain_text('Diagnostics running',timeout=5000)
                assert entered.wait(3)
                ident=session.status()['id']
                expect(page.locator('#diag-export')).to_be_disabled()
                page.locator('#close-diag').click();page.locator('#diag-button').click()
                expect(page.locator('#diag-status')).to_contain_text('Diagnostics running')
                assert session.status()['id']==ident
                page.locator('#diag-stop').click();release.set()
                expect(page.locator('#diag-status')).to_contain_text('Evidence ready · stopped',timeout=15000)
                assert len(models.calls)==1
                with page.expect_download() as pending:page.locator('#diag-export').click()
                target=Path(folder)/'diag.zip';pending.value.save_as(target)
                with zipfile.ZipFile(target) as z:
                    recorded=json.loads(z.read('evidence/diagnostic_session.json'))
                    assert recorded['id']==ident and recorded['status']=='stopped'
                    manifest=json.loads(z.read('manifest.json'))
                    for row in manifest['files']:assert hashlib.sha256(z.read(row['path'])).hexdigest()==row['sha256']
                page.locator('#diag-advanced summary').click()
                page.locator('#diag-mode').select_option('planning');page.locator('#diag-run').click()
                expect(page.locator('#diag-status')).to_contain_text('Evidence ready · finished',timeout=15000)
                row=next(r for r in session.report['evidence']['system_tests']['rows'] if r['code']=='planner_stage_probe')
                assert row['status']=='passed' and row['schema_version']==2
                assert len(models.calls)==2 and models.calls[1]['acceptance_planning_policy']=='feature_v2'
                assert 'PRIVATE PROJECT' not in json.dumps(models.calls[1])
                assert state_path.read_bytes()==before
                page.locator('#diag-mode').select_option('cloud');page.locator('#diag-run').click()
                expect(page.locator('#diag-status')).to_contain_text('Explicitly allow')
                assert len(models.calls)==2
                # Busy jobs get a passive report, never a hidden inference request.
                bench.test_busy=True
                page.locator('#diag-mode').select_option('quick');page.locator('#diag-run').click()
                expect(page.locator('#diag-status')).to_contain_text('workbench_busy',timeout=15000)
                assert session.report['evidence']['system_tests']['rows']==[]
                bench.test_busy=False
                page.set_viewport_size({'width':390,'height':844})
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
                assert page.locator('#diag-dialog').evaluate('el=>el.scrollWidth<=el.clientWidth+1')
                assert not errors,errors
                assert page.request.post(base+'/api/diagnostics/session/start',data={'mode':'quick'}).status==403
                browser.close()
        finally:
            release.set();bench.test_busy=False
            if session.worker:session.worker.join(10)
            server.shutdown();server.server_close()
    print('PASS: one Diag entry -> progress -> close/rejoin same session -> stop/partial ZIP with checksummed owned evidence -> explicit native-schema planner fixture -> cloud consent -> busy passive snapshot; unchanged project, mobile layout and auth. No live model quality claim.')


if __name__=='__main__':main()
