"""Real Chromium: local-only setup, preserved contracts, playback gating, mobile and ZIP."""
import copy
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
from playwright.sync_api import sync_playwright,expect
from forge.core import Workbench
from forge.models import ModelError
from forge.providers import PROVIDERS
from forge.server import make_server
from tests.fixtures import PLAN,APP,TEST
from tests.test_workbench import ScriptedModels


def main():
    info={name:{'configured':True,'key_variable':key} for name,(_,key) in PROVIDERS.items()}
    info['ollama']={'configured':True,'connected':True,'models':['qwen3.5:9b','qwen2.5-coder:7b','qwen3-embedding:0.6b']}
    calls=[]
    models=ScriptedModels([ModelError('Local request failed','transport'),copy.deepcopy(PLAN),{'files':{'app.py':APP,'test_app.py':TEST}}])
    def factory(provider,model):calls.append((provider,model));return models
    with tempfile.TemporaryDirectory() as temp,patch.dict(os.environ,{},clear=True),patch('forge.server.connection_info',return_value=info),patch('forge.cloud.request_json') as cloud:
        bench=Workbench(Path(temp)/'projects',factory);server=make_server(0,bench)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(executable_path=shutil.which('chromium'))
                page=browser.new_page(viewport={'width':1440,'height':1050});errors=[]
                page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto('http://127.0.0.1:'+str(server.server_port))
                expect(page.locator('#sound-toggle')).to_have_attribute('aria-pressed','false')
                assert page.evaluate('studioAudio === null')
                page.locator('#studio-local').click()
                expect(page.locator('#cloud-feedback')).to_contain_text('Local only: no cloud fallback',timeout=10000)
                expect(page.locator('#routing-mode')).to_have_value('local_only')
                expect(page.locator('#studio-route-title')).to_have_text('Local-only workspace')
                expect(page.locator('#studio-route-cards')).to_contain_text('qwen2.5-coder:7b')
                assert not calls;cloud.assert_not_called()
                # Advanced details are actually expandable with the keyboard.
                summary=page.locator('#studio-keys > summary');summary.focus();page.keyboard.press('Enter')
                expect(page.locator('#cloud-check')).to_be_visible()
                page.locator('#studio-comfort > summary').click()
                page.locator('#studio-accent').select_option('violet')
                page.locator('#studio-volume').fill('18')
                page.locator('#studio-sounds').check()
                expect(page.locator('#sound-toggle')).to_have_attribute('aria-pressed','true')
                assert page.evaluate('studioAudio.state')=='running'
                page.locator('#studio-sound-test').click()
                assert page.evaluate('playStudioCue()') is True
                page.locator('#close-connections').click()
                page.reload()
                expect(page.locator('#sound-toggle')).to_have_attribute('aria-pressed','true')
                assert page.evaluate('studioAudio === null')  # Persisted opt-in never autoplays on reload.
                assert page.evaluate('document.documentElement.dataset.studioAccent')=='violet'
                expect(page.locator('#studio-volume')).to_have_value('18')
                # User gesture unlocks subsequent polling cues; old terminal history stays silent.
                page.locator('#connections-button').click();page.locator('#studio-comfort > summary').click();page.locator('#studio-sound-test').click()
                page.locator('#close-connections').click()
                page.evaluate("window.cueCalls=[];window.realCue=playStudioCue;playStudioCue=(kind)=>{window.cueCalls.push(kind);return window.realCue(kind)};observeStudioJob({id:'history',status:'verified'});observeStudioJob({id:'history',status:'verified'})")
                assert page.evaluate('cueCalls.length')==0
                page.locator('#idea').fill('Build a simple task tracker with SQLite persistence')
                page.locator('#propose').click()
                expect(page.locator('#project-status')).to_have_text('proposed',timeout=15000)
                assert len(models.calls)==2 and all(provider=='ollama' for provider,_ in calls)
                assert calls[-2][1]!=calls[-1][1]
                page.locator('#approve').click()
                state=bench.list_projects()[0];before=bench.load(state['id'])
                frozen=copy.deepcopy(before['plan']);source=bench.files(state['id']);count=len(models.calls)
                page.locator('#connections-button').click();page.locator('#preset-local').click()
                expect(page.locator('#cloud-feedback')).to_contain_text('and this project',timeout=10000)
                expect(page.locator('#studio-route-cards article')).to_have_count(2)
                after=bench.load(state['id'])
                assert after['plan']==frozen and after['approved'] and bench.files(state['id'])==source
                assert len(models.calls)==count;cloud.assert_not_called()
                page.screenshot(path='/tmp/foundry023-model-studio-desktop.png',full_page=True)
                page.set_viewport_size({'width':390,'height':844})
                page.emulate_media(reduced_motion='reduce')
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                assert page.locator('#connections').evaluate('(e)=>e.scrollWidth <= e.clientWidth')
                page.evaluate("document.querySelector('.model-state').dataset.state='working'")
                assert page.locator('.model-state').first.evaluate('(e)=>getComputedStyle(e).animationName')=='none'
                page.screenshot(path='/tmp/foundry023-model-studio-mobile.png',full_page=True)
                page.locator('#close-connections').click();page.set_viewport_size({'width':1440,'height':1050})
                page.locator('#runtime').select_option('local');page.locator('#execution-consent').check();page.locator('#repairs').select_option('0')
                page.locator('#verify').click()
                expect(page.locator('#project-status')).to_have_text('verified',timeout=20000)
                assert len(models.calls)==3 and all(provider=='ollama' for provider,_ in calls)
                assert page.locator('.improve-panel').evaluate('(e)=>getComputedStyle(e).backgroundColor') != 'rgb(255, 255, 255)'
                assert page.evaluate("cueCalls.includes('complete')")
                page.evaluate("window.cueCalls=[];observeStudioJob({id:'stopped',status:'building'});observeStudioJob({id:'stopped',status:'stopped'});observeStudioJob({id:'stopped',status:'stopped'})")
                assert page.evaluate('cueCalls')==['attention']
                page.locator('#sound-toggle').click();assert page.evaluate('playStudioCue()') is False
                page.get_by_role('tab',name='Project files').click()
                with page.expect_download() as downloaded:page.locator('#download').click()
                path=Path(temp)/'app.zip';downloaded.value.save_as(path)
                with zipfile.ZipFile(path) as z:
                    report=json.loads(z.read('generated-app/BUILD-REPORT.json'))
                    assert report['workflow']['evidence']['accepted_current']
                    assert all(row['provider']=='ollama' for row in report['model_calls'])
                cloud.assert_not_called();assert not errors,errors
                browser.close()
        finally:server.shutdown();server.server_close()
    print('PASS: local-only no-cloud setup, two-local failover, existing plan/files preservation, separate route previews, keyboard details, persistent accents/volume/mute, user-gesture audio with silent reload/history, one cue per observed terminal transition, reduced-motion/mobile and real generated-app verification/ZIP. No live provider or GPU claims.')


if __name__=='__main__':main()
