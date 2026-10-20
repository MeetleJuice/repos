"""Real browser: staged approval, resumable draft, settings preservation and ZIP evidence."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import zipfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from playwright.sync_api import sync_playwright, expect
from forge.core import Workbench
from forge.models import ModelError
from forge.server import make_server
from tests.test_guided_planning import responses
from tests.test_workbench import ScriptedModels
from tests.fixtures import APP, TEST


def main():
    outline,batch,_=responses()
    # One outline, a failing batch route, then resume the same saved outline.
    models=ScriptedModels([outline,ModelError('Fixture local socket timeout','transport',transport_kind='timeout'),batch,
        {'files':{'app.py':APP}}, {'files':{'test_app.py':TEST}}])
    with tempfile.TemporaryDirectory() as temp:
        home=Path(temp);bench=Workbench(home/'projects',models);server=make_server(0,bench)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(executable_path=shutil.which('chromium'))
                page=browser.new_page(viewport={'width':1440,'height':1100});errors=[]
                page.on('pageerror',lambda error:errors.append(str(error)))
                page.goto('http://127.0.0.1:'+str(server.server_port))
                page.locator('#idea').fill('Build a local task tracker with saved tasks')
                page.locator('#new-plan-mode').select_option('guided')
                expect(page.locator('#new-local-timeout')).to_be_visible()
                page.locator('#propose').click()
                expect(page.locator('#project-status')).to_have_text('error',timeout=15000)
                expect(page.locator('#guided-progress')).to_contain_text('0/2 features planned')
                page.locator('#planning-diagnostics > summary').click()
                expect(page.locator('#planning-diagnostic-list')).to_contain_text('transport / timeout')
                expect(page.locator('#approve')).not_to_be_visible()
                assert len(models.calls)==2
                page.reload()
                page.locator('#projects .project-link').first.click()
                page.locator('#plan-guided').click()
                expect(page.locator('#project-status')).to_have_text('proposed',timeout=15000)
                expect(page.locator('#guided-progress')).to_contain_text('Assembled proposal ready for review')
                expect(page.locator('#proposal-review-status')).to_contain_text('small-step planning')
                expect(page.locator('#proposal-review-status')).not_to_contain_text('recovered')
                assert len(models.calls)==3 and models.calls[-1]['planning_stage']=='tasks'
                ident=bench.list_projects()[0]['id']
                state=bench.load(ident)
                # Verify a settings save preserves an existing fallback's output/context/timeout.
                fallback={'provider':'ollama','model':'backup-local','options':{'num_ctx':32768,'num_predict':8192,'timeout_seconds':600,'structured_outputs':True}}
                state['planner']['fallback']=fallback;bench.save(state)
                page.reload();page.locator('#projects .project-link').first.click()
                page.locator('#next-models').click()
                expect(page.locator('#project-planner-model')).to_have_value(state['planner']['model'])
                page.evaluate("document.getElementById('project-planner-timeout').value='300'")
                page.locator('#model-form button[type=submit]').click()
                expect(page.locator('#models-dialog')).not_to_be_visible()
                assert bench.load(ident)['planner']['fallback']==fallback
                assert bench.load(ident)['planner']['options']['timeout_seconds']==300
                page.locator('#approve').click()
                expect(page.locator('#guided-planning')).not_to_be_visible()
                page.locator('#runtime').select_option('local');page.locator('#execution-consent').check()
                page.locator('#repairs').select_option('0');page.locator('#verify').click()
                expect(page.locator('#project-status')).to_have_text('verified',timeout=25000)
                assert len(models.calls)==5
                page.get_by_role('tab',name='Project files').click()
                with page.expect_download() as download:page.locator('#download').click()
                path=home/'app.zip';download.value.save_as(path)
                with zipfile.ZipFile(path) as archive:
                    report=json.loads(archive.read('generated-app/BUILD-REPORT.json'))
                    assert report['checks']['passed'] and len(report['task_receipts'])==2
                page.set_viewport_size({'width':390,'height':844});page.emulate_media(reduced_motion='reduce')
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                assert not errors,errors
                browser.close()
        finally:server.shutdown();server.server_close()
    print('PASS: guided outline timeout -> actionable diagnosis -> reload/resume without replay; full approval; fallback options preserved; sequential scoped tasks; actual app tests and ZIP evidence; mobile/reduced motion/no JS errors. Model replies are fixtures, not live-model evidence.')


if __name__=='__main__':main()
