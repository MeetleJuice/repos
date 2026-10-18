"""Import a reviewed repair and visibly replace the repeated five-task plan."""
from pathlib import Path
import copy
import json
import shutil
import sys
import tempfile
import threading
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from playwright.sync_api import sync_playwright, expect
from forge.core import Workbench
from forge.server import make_server
from tests.test_evidence import CONFIG
from tests.test_workbench import ScriptedModels, await_job
from tests.test_improvement_planning import BASE, REPAIR, ROOT


def main():
    with tempfile.TemporaryDirectory() as temp:
        models = ScriptedModels([REPAIR])
        bench = Workbench(Path(temp) / 'projects', models)
        parent = bench.create('Use the standard Neon Dodge game.', CONFIG, CONFIG, 'arcade', use_reviewed_plan=True)
        parent['plan'] = copy.deepcopy(BASE);bench.save(parent)
        bench.approve(parent['id'], BASE)
        child = await_job(bench, bench.fork(parent['id'], 'Fix missing shield pickup implementation in game.js')['id'])
        # Actual user has a proposal accepted by the older release. Preserve that state for UI recovery.
        child.update(plan=copy.deepcopy(BASE), title='Repeated shield repair', status='proposed')
        bench.save(child)
        before = bench.files(child['id']);calls = len(models.calls)
        server = make_server(0, bench);threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(executable_path=shutil.which('chromium'))
                page=browser.new_page(viewport={'width':1280,'height':1000});errors=[]
                page.on('pageerror',lambda error:errors.append(str(error)))
                page.goto(f'http://127.0.0.1:{server.server_port}')
                page.locator('#projects button').filter(has_text='Repeated shield repair').click()
                expect(page.locator('#tasks li')).to_have_count(5)
                page.locator('#proposal-import').set_input_files(str(ROOT / 'docs/proposals/Neon-Dodge-Shield-Repair.json'))
                expect(page.locator('#proposal-edit-feedback')).to_contain_text('Saved 2 tasks',timeout=5000)
                expect(page.locator('#tasks li')).to_have_count(2)
                expect(page.locator('#tasks li').first).to_contain_text('Repair actual shield logic')
                assert len(models.calls)==calls
                assert bench.files(child['id'])==before
                assert not bench.load(child['id'])['approved']
                page.reload()
                page.locator('#projects button').filter(has_text='repair shield implementation').click()
                expect(page.locator('#tasks li')).to_have_count(2)
                page.get_by_text('Edit the proposal JSON before approval',exact=True).click()
                edited=copy.deepcopy(REPAIR);edited['title']='Saved shield repair'
                page.locator('#plan-editor').fill(json.dumps(edited))
                page.locator('#save-proposal-edits').click()
                expect(page.locator('#project-title')).to_have_text('Saved shield repair')
                page.locator('#review-proposal-button').click()
                expect(page.locator('#proposal-edit-feedback')).to_contain_text('Checked: valid')
                assert len(models.calls)==calls
                token=page.locator('meta[name="foundry-token"]').get_attribute('content')
                endpoint=f'http://127.0.0.1:{server.server_port}/api/projects/{child["id"]}/proposal'
                assert page.request.post(endpoint,data={'plan':REPAIR}).status==403
                response=page.request.post(endpoint,data={'plan':BASE},headers={'X-Foundry-Token':token})
                assert response.status==400 and 'repeats' in response.text()
                page.set_viewport_size({'width':390,'height':844})
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                page.locator('#approve').click()
                expect(page.locator('#project-status')).to_have_text('approved')
                assert len(bench.load(child['id'])['plan']['tasks'])==2
                assert bench.load(child['id'])['checks'] is None
                assert bench.files(parent['id'])==before
                assert not errors,errors
                browser.close()
                print('PASS: five-task stale proposal → imported two-task reviewed repair → persistent reload/cards → explicit editor save/check feedback → approval; no inference, source mutation or execution; token and recycled-plan guards; mobile.')
        finally:
            server.shutdown();server.server_close()


if __name__=='__main__':main()
