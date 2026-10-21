"""Real Chromium checks for the living emblem; controller replies are fixtures."""
from pathlib import Path
import shutil
import sys
import tempfile
import threading
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from playwright.sync_api import sync_playwright,expect
from forge.core import Workbench
from forge.server import make_server
from tests.fixtures import PLAN
from tests.test_workbench import await_job


def main():
    entered=threading.Event();release=threading.Event()
    class Models:
        def __call__(self,*args):return self
        def complete(self,*args):entered.set();release.wait(30);return PLAN
    info={'ollama':{'connected':True,'models':['fixture']}}
    with tempfile.TemporaryDirectory() as temp,patch('forge.server.connection_info',return_value=info):
        bench=Workbench(Path(temp)/'projects',Models());server=make_server(0,bench)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(executable_path=shutil.which('chromium'))
                page=browser.new_page(viewport={'width':1440,'height':1000});errors=[]
                page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto('http://127.0.0.1:'+str(server.server_port))
                emblem=page.locator('#brand-emblem');outer=page.locator('.fire-outer');button=page.locator('#brand-motion')
                expect(emblem).to_have_attribute('data-working','false')
                assert emblem.bounding_box()['width']==192
                assert outer.evaluate('(e)=>getComputedStyle(e).animationName')=='forge-flame'
                expect(page.locator('.brand-mark')).to_have_attribute('src','/icon.png')
                page.locator('.brand').screenshot(path='/tmp/034-brand-desktop.png')
                button.click();expect(button).to_have_attribute('aria-pressed','false')
                assert outer.evaluate('(e)=>getComputedStyle(e).animationPlayState')=='paused'
                assert page.locator('.brand-fire').evaluate('(e)=>e.animationsPaused()')
                page.reload();expect(emblem).to_have_attribute('data-motion','false')
                button.click();expect(emblem).to_have_attribute('data-motion','true')
                config={'provider':'ollama','model':'fixture'}
                state=bench.create('Build local task tracker',config,config)
                assert entered.wait(3)
                expect(emblem).to_have_attribute('data-working','true',timeout=5000)
                assert outer.evaluate('(e)=>getComputedStyle(e).animationDuration')=='1.4s'
                page.emulate_media(reduced_motion='reduce')
                assert outer.evaluate('(e)=>getComputedStyle(e).animationName')=='none'
                assert page.locator('.brand-fire').evaluate('(e)=>e.animationsPaused()')
                expect(emblem).to_have_attribute('data-working','true')
                release.set();assert await_job(bench,state['id'])['status']=='proposed'
                expect(emblem).to_have_attribute('data-working','false',timeout=5000)
                page.emulate_media(reduced_motion='no-preference')
                # A failed status read must clear the last working display.
                page.route('**/api/model-status',lambda route:route.abort())
                page.evaluate("document.querySelector('#brand-emblem').dataset.working='true'")
                expect(emblem).to_have_attribute('data-working','false',timeout=5000)
                page.unroute('**/api/model-status')
                page.set_viewport_size({'width':390,'height':844})
                assert emblem.bounding_box()['width']==144
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                page.locator('.brand').screenshot(path='/tmp/034-brand-mobile.png')
                page.set_viewport_size({'width':320,'height':740})
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                assert not errors,errors
                browser.close()
        finally:release.set();server.shutdown();server.server_close()
    print('PASS: larger desktop/mobile emblem; independent flame animation; true in-flight controller activity and completion; status-error clearing; persistent motion pause; reduced motion; no horizontal overflow or JavaScript errors. No live model quality tested.')


if __name__=='__main__':main()
