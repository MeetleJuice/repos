"""Actual workbench button -> separate dashboard window, without model calls."""
from pathlib import Path
import shutil
import sys
import tempfile
import threading
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from playwright.sync_api import sync_playwright,expect
from forge.core import Workbench
from forge.server import make_server


def main():
    with tempfile.TemporaryDirectory() as temp,patch('forge.server.connection_info',return_value={}):
        bench=Workbench(Path(temp)/'projects');server=make_server(0,bench)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(executable_path=shutil.which('chromium'))
                context=browser.new_context(viewport={'width':1440,'height':1000})
                page=context.new_page();errors=[]
                context.on('page',lambda opened:opened.on('pageerror',lambda error:errors.append(str(error))))
                page.on('pageerror',lambda error:errors.append(str(error)))
                page.goto('http://127.0.0.1:'+str(server.server_port))
                button=page.get_by_role('button',name='Dashboard',exact=False)
                expect(button).to_be_visible()
                assert button.evaluate("el=>Boolean(el.closest('.topbar'))")
                assert button.bounding_box()['y']<200
                page.locator('#idea').fill('Keep this unsaved idea while looking at the dashboard')
                with page.expect_popup() as opened:button.click()
                dashboard=opened.value
                expect(dashboard.locator('.ifd-shell')).to_have_attribute('data-layout','ready',timeout=30000)
                assert dashboard.url.endswith('/dashboard')
                assert dashboard.evaluate('window.opener===null')
                root_window=context.new_cdp_session(page).send('Browser.getWindowForTarget')['windowId']
                graph_window=context.new_cdp_session(dashboard).send('Browser.getWindowForTarget')['windowId']
                assert root_window!=graph_window,'Dashboard must request a separate browser window'
                button.click();page.wait_for_timeout(150)
                assert len(context.pages)==2,'Repeated clicks should reuse the dashboard window'
                expect(page.locator('#idea')).to_have_value('Keep this unsaved idea while looking at the dashboard')
                dashboard.close()
                page.evaluate('()=>{window.savedOpen=window.open;window.open=()=>null;}')
                button.click()
                fallback=page.locator('#dashboard-popup-fallback')
                expect(fallback).to_be_visible();expect(fallback).to_be_focused()
                assert fallback.get_attribute('href')=='/dashboard'
                page.evaluate('()=>{window.open=window.savedOpen;}')
                with page.expect_popup() as reopened:button.click()
                expect(reopened.value.locator('.ifd-shell')).to_have_attribute('data-layout','ready',timeout=30000)
                expect(fallback).to_be_hidden()
                reopened.value.close()
                page.set_viewport_size({'width':390,'height':844})
                expect(button).to_be_visible()
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                page.screenshot(path='/tmp/foundry-dashboard-button.png',full_page=True)
                assert bench.list_projects()==[],'Opening Dashboard must not start a project'
                assert not errors,errors
                browser.close()
        finally:server.shutdown();server.server_close()
    print('PASS: visible top workbench Dashboard button; distinct Chromium browser window; graph loads; opener detached; repeated clicks reuse window; blocked popup exposes keyboard-focusable fallback; reopen works; unsaved idea preserved; mobile has no overflow; no project/model job or JavaScript error.')


if __name__=='__main__':main()
