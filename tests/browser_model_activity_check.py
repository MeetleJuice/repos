"""Actual Chromium polling of controlled in-flight workbench requests; no live API keys."""
import os
from pathlib import Path
import shutil
import sys
import tempfile
import threading
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from playwright.sync_api import sync_playwright, expect
from forge.core import Workbench
from forge.models import ModelError
from forge.providers import PROVIDERS
from forge.server import make_server
from tests.fixtures import PLAN
from tests.test_workbench import await_job


def main():
    entered=threading.Event();release=threading.Event()
    class Models:
        calls=0
        def __call__(self,*_):return self
        def complete(self,system,prompt):
            self.calls+=1
            if self.calls==1:
                entered.set();release.wait(20);return PLAN
            raise ModelError('Fixture quota restriction','quota')
    info={p:{'configured':p=='gemini','key_variable':v} for p,(_,v) in PROVIDERS.items()}
    info['ollama']={'configured':True,'connected':True,'models':['qwen3.5:9b','nomic-embed-text:latest']}
    with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'GEMINI_API_KEY':'fixture-status-secret'},clear=True),patch('forge.server.connection_info',return_value=info):
        bench=Workbench(Path(d)/'projects',Models());server=make_server(0,bench)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(executable_path=shutil.which('chromium'));page=browser.new_page(viewport={'width':1440,'height':1000})
                errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto('http://127.0.0.1:'+str(server.server_port))
                expect(page.locator('.model-state')).to_have_count(10,timeout=10000)
                expect(page.locator('[data-model-id="local"]')).to_have_attribute('aria-label','LM Studio / llama.cpp: not checked')
                expect(page.locator('[data-model-id="ollama/nomic-embed-text:latest"]')).to_have_attribute('data-state','embedding')
                config={'provider':'gemini','model':'fixture-model'}
                state=bench.create('Build task tracker',config,config,cloud_consent=True)
                assert entered.wait(3)
                badge=page.locator('[data-model-id="gemini"]')
                expect(badge).to_have_attribute('data-state','working',timeout=5000)
                assert badge.evaluate('(e)=>getComputedStyle(e).animationName')=='model-working'
                page.emulate_media(reduced_motion='reduce')
                assert badge.evaluate('(e)=>getComputedStyle(e).animationName')=='none'
                expect(badge).to_have_attribute('data-state','working')
                release.set();state=await_job(bench,state['id']);assert state['status']=='proposed'
                expect(badge).to_have_attribute('data-state','responded',timeout=5000)
                state['job_cloud_consent']=True
                try:bench.call_model(state,'coder','fixture','{}',threading.Event())
                except ModelError:pass
                expect(badge).to_have_attribute('data-state','quota',timeout=5000)
                assert page.locator('[data-state="working"]').count()==0
                badge.click();expect(page.locator('#connections')).to_be_visible()
                page.locator('#close-connections').click()
                page.set_viewport_size({'width':390,'height':844})
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                assert 'fixture-status-secret' not in page.locator('body').inner_text()
                assert not errors,errors
                browser.close()
        finally:release.set();server.shutdown();server.server_close()
    print('PASS: seven provider icons and installed local models, embedding distinction, true in-flight animation, reduced-motion state, success and quota transitions, working cleared, model dialog navigation, mobile, privacy and no JS errors.')


if __name__=='__main__':main()
