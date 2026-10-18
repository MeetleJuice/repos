"""Real Chromium: the uploaded shield bug must fail before an exact-edit repair passes."""
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
from forge.runner import verify
from forge.scaffolds import starter_files
from tests.test_evidence import CONFIG, game_plan
from tests.test_workbench import ScriptedModels, await_job

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'tests/fixture_data'
RANDOM = [0.5, 0.05, 0.5, 0.1, 0.5, 0.5, 0.5]
COLLISION = {'name':'Shield blocks one obstacle without an immediate repeat collision',
    'feature_indexes':[1], 'clock':True, 'random_values':RANDOM,
    'steps':[{'action':'click','selector':'#start'}, {'action':'advance_time','ms':5400},
             {'action':'expect_text_exact','selector':'#state','value':'Playing'}]}
DETAIL = {'name':'Collect, pause, consume, collide again and reset shield',
    'feature_indexes':[1], 'clock':True, 'random_values':RANDOM,
    'steps':[{'action':'click','selector':'#start'},
             {'action':'advance_time','ms':4600},
             {'action':'expect_text_exact','selector':'#shield-status','value':'Shield ready'},
             {'action':'click','selector':'#pause'},
             {'action':'advance_time','ms':32},
             {'action':'expect_canvas_still','selector':'#game','ms':500},
             {'action':'expect_text_exact','selector':'#shield-status','value':'Shield ready'},
             {'action':'click','selector':'#pause'},
             {'action':'advance_time','ms':800},
             {'action':'expect_text_exact','selector':'#shield-status','value':'Shield empty'},
             {'action':'expect_text_exact','selector':'#state','value':'Playing'},
             {'action':'advance_time','ms':1200},
             {'action':'expect_text_exact','selector':'#state','value':'Game over'},
             {'action':'click','selector':'#start'},
             {'action':'expect_text_exact','selector':'#score','value':'0'},
             {'action':'expect_text_exact','selector':'#shield-status','value':'Shield empty'}]}


def main():
    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp);files=starter_files('arcade')
        broken=(DATA/'neon-shield-broken.js').read_text()
        repair=json.loads((DATA/'neon-shield-repair.json').read_text())
        plan=game_plan();plan['browser_checks']=[COLLISION]
        models=ScriptedModels([{'files':{'game.js':broken}}, {'files':{'game.js':broken}}, repair])
        bench=Workbench(root/'projects',models)
        state=bench.create('Test the shield collision in a deterministic browser run.',CONFIG,CONFIG,'arcade',use_reviewed_plan=True)
        state=bench.approve(state['id'],plan)
        # The model fixture returns the actual uploaded broken game; all HTTP tests still pass.
        bench.start(state['id'],'build',{'execute':True,'consent':True,'runtime':'local','repairs':1})
        bench.jobs[state['id']][0].join(90)
        assert not bench.jobs[state['id']][0].is_alive()
        state=bench.load(state['id'])
        assert state['status']=='review_required',state.get('error') or state.get('checks')
        assert state['repair_count']==1
        assert 'Game over' in models.calls[-1]['failure'],models.calls[-1]
        assert 'Shield blocks one obstacle' in models.calls[-1]['failure']
        assert models.calls[-1]['feedback']['browser_failure']['step_number']==3
        assert bench.files(state['id'])['test_foundation.py']==files['test_foundation.py']
        # Additional real-browser assertions for the corrected reference implementation.
        source=bench.directory(state['id'])/'source'
        original=(source/'BROWSER-CHECKS.json').read_text()
        (source/'BROWSER-CHECKS.json').write_text(json.dumps([DETAIL]))
        report=verify(source,'local',threading.Event())
        assert report['passed'],report
        (source/'BROWSER-CHECKS.json').write_text(original)
        # Verify UI stores observations, performs a direct repair, and never re-plans.
        server=make_server(0,bench);threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(executable_path=shutil.which('chromium'))
                page=browser.new_page(viewport={'width':1280,'height':1000});errors=[]
                page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto(f'http://127.0.0.1:{server.server_port}')
                page.locator('#projects button').first.click()
                assert page.request.post(f'http://127.0.0.1:{server.server_port}/api/projects/{state["id"]}/repair',data={'repairs':1}).status==403
                expect(page.locator('#repair-manual')).to_be_disabled()
                for i in range(len(plan['manual_checks'])):
                    page.locator('#manual-'+str(i)).select_option('fail' if i==0 else 'pass')
                page.locator('#manual-note-0').fill('Shield status text needs a clearer label for the user.')
                page.locator('#save-manual').click()
                expect(page.locator('#project-status')).to_have_text('needs attention')
                expect(page.locator('#repair-manual')).to_be_enabled()
                page.reload();page.locator('#projects button').first.click()
                expect(page.locator('#manual-note-0')).to_have_value('Shield status text needs a clearer label for the user.')
                models.responses.extend([{'edits':[{'file':'game.js','search':'not present in current source','replace':'fixed'}]}, {}])
                failed_calls=len(models.calls)
                page.locator('#repair-manual').click()
                expect(page.locator('#project-status')).to_have_text('error',timeout=10000)
                expect(page.locator('#manual-note-0')).to_have_value('Shield status text needs a clearer label for the user.')
                expect(page.locator('#repair-manual')).to_be_enabled()
                assert len(models.calls)==failed_calls+2
                assert models.calls[-1]['response_mode']=='complete_files'
                assert bench.load(state['id'])['manual_results']['results'][0] is False
                page.locator('#runtime').select_option('local')
                page.locator('#execution-consent').check()
                page.locator('#repairs').select_option('0')
                page.locator('#verify').click()
                expect(page.locator('#project-status')).to_have_text('needs attention',timeout=20000)
                expect(page.locator('#manual-note-0')).to_have_value('Shield status text needs a clearer label for the user.')
                assert len(models.calls)==failed_calls+2
                assert bench.load(state['id'])['checks']['passed']
                page.locator('#repairs').select_option('1')
                models.responses.append({'edits':[{'file':'game.js','search':'  const shieldStatus = document.createElement("strong");','replace':'  // Repaired from saved user observations.\n  const shieldStatus = document.createElement("strong");'}]})
                calls=len(models.calls)
                page.locator('#repair-manual').click()
                expect(page.locator('#project-status')).to_have_text('Files ready · not tested',timeout=10000)
                assert len(models.calls)==calls+1
                assert models.calls[-1]['manual_evidence']['failures'][0]['observed'].startswith('Shield status')
                assert bench.load(state['id'])['plan']==plan
                assert bench.load(state['id'])['checks'] is None
                expect(page.locator('#repair-history')).to_contain_text('2 recorded repair')
                page.set_viewport_size({'width':390,'height':844})
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                assert not errors,errors
                browser.close()
        finally:
            server.shutdown();server.server_close()
        print('PASS: actual uploaded shield collision fails in Chromium → bounded exact-edit repair → same frozen browser/HTTP/regression checks pass; collection/pause/consumption/second collision/restart verified; failed format recovery retains notes and enables retry; direct successful repair makes one coder request, no planning/execution, mobile and no JavaScript errors.')


if __name__=='__main__':main()
