"""Real browser and local SSE HTTP fixture: setup -> approval -> stream -> tests -> ZIP."""
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import zipfile
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from playwright.sync_api import sync_playwright,expect
from forge.core import Workbench
from forge.server import make_server
from forge.providers import PROVIDERS
from tests.fixtures import APP,TEST
from tests.test_task_contracts import structured_plan
from tests.test_updates import archive_for,manifest_for,NEXT_VERSION


def main():
    plan=structured_plan();requests=[];release=threading.Event()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_POST(self):
            body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            requests.append(body)
            result=json.dumps(plan if len(requests)==1 else {'files':{'app.py':APP,'test_app.py':TEST}})
            self.send_response(200)
            if not body.get('stream'):
                data=json.dumps({'choices':[{'finish_reason':'stop','message':{'content':result}}]}).encode()
                self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data);return
            self.send_header('Content-Type','text/event-stream');self.end_headers()
            def frame(text,reason=None):
                self.wfile.write(('data: '+json.dumps({'choices':[{'delta':{'content':text},'finish_reason':reason}]})+'\n\n').encode());self.wfile.flush()
            frame(result[:24]);release.wait(15);frame(result[24:]);frame('','stop');self.wfile.write(b'data: [DONE]\n\n')
    runtime=ThreadingHTTPServer(('127.0.0.1',0),Handler);runtime.daemon_threads=True
    threading.Thread(target=runtime.serve_forever,daemon=True).start()
    info={name:{'configured':False,'key_variable':key} for name,(_,key) in PROVIDERS.items()}
    info['ollama']={'configured':True,'connected':False,'models':[]}
    info['local']={'configured':True,'connected':True,'models':['fixture-coder']}
    try:
        with tempfile.TemporaryDirectory() as temp,patch.dict(os.environ,{'LOCAL_API_URL':'http://127.0.0.1:'+str(runtime.server_port)+'/v1'},clear=True),patch('forge.server.connection_info',return_value=info),patch('forge.cloud.request_json') as cloud:
            bench=Workbench(Path(temp)/'projects');server=make_server(0,bench)
            threading.Thread(target=server.serve_forever,daemon=True).start()
            try:
                with sync_playwright() as p:
                    browser=p.chromium.launch(executable_path=shutil.which('chromium'))
                    page=browser.new_page(viewport={'width':1440,'height':1050});errors=[]
                    page.on('pageerror',lambda error:errors.append(str(error)))
                    page.goto('http://127.0.0.1:'+str(server.server_port))
                    page.locator('#connections-button').click();page.locator('#compatible-runtime > summary').click()
                    expect(page.locator('#compatible-planner')).to_have_value('fixture-coder')
                    page.locator('#compatible-apply').click()
                    expect(page.locator('#cloud-feedback')).to_contain_text('Local server route applied',timeout=10000)
                    cloud.assert_not_called();assert not requests
                    page.locator('#close-connections').click()
                    expect(page.locator('#planner-provider')).to_have_value('local')
                    expect(page.locator('#planner-choice')).to_have_value('fixture-coder')
                    page.locator('#planner-choice').select_option('fixture-coder')
                    expect(page.locator('#planner-model')).to_have_value('fixture-coder')
                    page.reload()
                    expect(page.locator('#planner-provider')).to_have_value('local')
                    page.locator('#idea').fill('Build a local task tracker with SQLite persistence.')
                    page.locator('#propose').click()
                    expect(page.locator('#project-status')).to_have_text('proposed',timeout=15000)
                    page.locator('#approve').click()
                    page.locator('#stream-local').check()
                    page.locator('#runtime').select_option('local');page.locator('#execution-consent').check()
                    page.locator('#verify').click()
                    expect(page.locator('#live-local')).to_be_visible(timeout=10000)
                    expect(page.locator('#live-local-label')).to_contain_text('Local server · fixture-coder')
                    page.locator('#live-local summary').click()
                    expect(page.locator('#live-local-preview')).to_contain_text('files')
                    expect(page.locator('#live-local-stop')).to_be_enabled()
                    page.evaluate("const previous=current; current={id:'b'.repeat(32)}; document.getElementById('live-local-stop').click(); current=previous")
                    expect(page.locator('#notice')).to_contain_text('Open the project with the streaming request')
                    running=bench.list_projects()[0]['id']
                    assert not bench.jobs[running][1].is_set(), 'Switching projects must not cancel a different job'
                    release.set()
                    expect(page.locator('#project-status')).to_have_text('verified',timeout=25000)
                    expect(page.locator('#live-local')).not_to_be_visible(timeout=10000)
                    ident=bench.list_projects()[0]['id'];state=bench.load(ident)
                    assert state['task_receipts'][0]['finish_gate']['passed']
                    assert state['task_receipts'][0]['finish_gate']['behavior_verified'] is False
                    assert state['checks']['passed'] and len(requests)==2
                    assert state['planner']['provider']==state['coder']['provider']=='local'
                    assert 'preview' not in json.dumps(state) and all('partial_content' not in row for row in state['model_calls'])
                    response=page.request.get('http://127.0.0.1:'+str(server.server_port)+'/api/projects/'+ident+'/download',headers={'X-Foundry-Token':page.locator('meta[name=foundry-token]').get_attribute('content')})
                    assert response.ok
                    with zipfile.ZipFile(io.BytesIO(response.body())) as archive:
                        report=json.loads(archive.read('generated-app/BUILD-REPORT.json'))
                        assert report['task_receipts'][0]['finish_gate']['passed']
                    manifest=manifest_for(archive_for())
                    server.updater.downloader=lambda url,limit:json.dumps(manifest).encode()
                    page.evaluate("window.readyEvents=[];window.addEventListener('foundry:update-ready',e=>readyEvents.push(e.detail))")
                    page.locator('#update-button').click();page.locator('#check-update').click()
                    expect(page.locator('#update-status')).to_have_text('Version '+NEXT_VERSION+' is available.')
                    page.locator('#close-update').click()
                    expect(page.locator('#update-ready-banner')).to_be_visible()
                    expect(page.locator('#update-ready-message')).to_contain_text('Press the Update button')
                    assert page.evaluate('readyEvents.length')==1
                    assert page.evaluate('readyEvents[0].requires_user_action') is True
                    assert not server.updater.restart
                    page.locator('#update-ready-dismiss').click()
                    expect(page.locator('#update-ready-banner')).not_to_be_visible()
                    page.set_viewport_size({'width':390,'height':844});page.emulate_media(reduced_motion='reduce')
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                    cloud.assert_not_called();assert not errors,errors
                    browser.close()
            finally:release.set();server.shutdown();server.server_close()
    finally:release.set();runtime.shutdown();runtime.server_close()
    print('PASS: local-compatible setup/discovery choices persist; no cloud requests/consent; actual local SSE preview; scoped Stop control; finish gate; real generated-app verification and ZIP; human-controlled update-ready event/banner; mobile/reduced motion/no JS errors. Model responses are fixtures.')


if __name__=='__main__':main()
