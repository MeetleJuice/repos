"""Real Chromium checks, scripted controller history; no external inference."""
from pathlib import Path
import json
import re
import shutil
import sys
import tempfile
import threading
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from playwright.sync_api import sync_playwright,expect
from forge.core import Workbench
from forge.server import make_server
from tests.fixtures import PLAN
from tests.test_workbench import ScriptedModels


def main():
    with tempfile.TemporaryDirectory() as temp,patch('forge.server.connection_info',return_value={}):
        bench=Workbench(Path(temp)/'projects',ScriptedModels([PLAN]))
        server=make_server(0,bench)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        base='http://127.0.0.1:'+str(server.server_port)
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(executable_path=shutil.which('chromium'))
                page=browser.new_page(viewport={'width':1600,'height':1000})
                errors=[];requests=[]
                page.on('pageerror',lambda error:errors.append(str(error)))
                page.on('request',lambda request:requests.append((request.method,request.url)))
                page.goto(base+'/dashboard')
                expect(page.locator('.ifd-shell')).to_have_attribute('data-layout','ready',timeout=30000)
                graph=json.loads((Path(__file__).parent/'src/graph.json').read_text())
                def centered(label):
                    ident=next(node['id'] for node in graph['nodes'] if node['label']==label)
                    page.wait_for_function("""id=>{const node=document.querySelector('[data-id="'+CSS.escape(id)+'"]');const view=document.querySelector('.react-flow');if(!node||!view)return false;const a=node.getBoundingClientRect(),b=view.getBoundingClientRect();return Math.abs(a.x+a.width/2-b.x-b.width/2)<4&&Math.abs(a.y+a.height/2-b.y-b.height/2)<4;}""",arg=ident,timeout=5000)
                assert page.locator('.react-flow__node').count()>10
                assert page.locator('canvas').count()==0
                page.locator('[aria-label="Playback tempo"]').select_option('80')
                page.get_by_role('button',name='Play simulation',exact=False).click()
                expect(page.locator('.ifd-running')).to_have_count(1)
                page.get_by_role('button',name='Pause simulation').click()
                assert page.locator('.ifd-edge-running').count()>0
                assert page.locator('.ifd-running').evaluate("el=>getComputedStyle(el).animationName")=='ifd-pulse'
                count=page.locator('.ifd-events button').count();page.wait_for_timeout(300)
                assert page.locator('.ifd-events button').count()==count
                page.get_by_role('button',name='Resume simulation').click()
                expect(page.locator('.ifd-footer')).to_contain_text('Scenario complete',timeout=15000)
                assert page.locator('.ifd-completed').count()>10
                page.locator('#ifd-scenario').select_option('failed-job')
                expect(page.locator('.ifd-shell')).to_have_attribute('data-layout','ready',timeout=30000)
                page.get_by_role('button',name='Play simulation',exact=False).click()
                expect(page.locator('.ifd-footer')).to_contain_text('Scenario complete',timeout=10000)
                expect(page.locator('.ifd-failed')).to_have_count(1)
                page.locator('.ifd-stop').click()
                page.get_by_label('Full map',exact=True).check()
                expect(page.locator('.ifd-shell')).to_have_attribute('data-layout','ready',timeout=30000)
                graph=json.loads((Path(__file__).parent/'src/graph.json').read_text())
                assert page.locator('.react-flow__node').count()==len(graph['nodes'])
                assert page.locator('.ifd-edge').count()==len(graph['edges'])
                # All layout boxes, including off-screen nodes, must be disjoint.
                boxes=page.locator('.react-flow__node').evaluate_all('els=>els.map(e=>{const r=e.getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height}})')
                for i,a in enumerate(boxes):
                    for b in boxes[i+1:]:
                        assert not(a['x']<b['x']+b['w']-.1 and a['x']+a['w']>b['x']+.1 and a['y']<b['y']+b['h']-.1 and a['y']+a['h']>b['y']+.1),'Overlapping ELK nodes'
                page.get_by_role('button',name='Fit graph to view').click()
                page.keyboard.press('/')
                expect(page.get_by_role('textbox',name='Find a process')).to_be_focused()
                page.get_by_role('textbox',name='Find a process').fill('call_model')
                page.locator('.ifd-library-list button').first.click()
                expect(page.locator('.ifd-source-card')).to_contain_text('forge/core.py:')
                page.get_by_role('button',name='Close step inspector').click()
                page.screenshot(path='/tmp/foundry-dashboard-desktop.png')
                assert all(method=='GET' for method,_ in requests),requests
                assert not any('/api/' in url for _,url in requests),'Simulation must never call controller APIs'
                # Existing history stays historical; only newly appended records emit activity.
                config={'provider':'ollama','model':'fixture'}
                state=bench.create('Build a small task app',config,config);ident=state['id']
                for _ in range(200):
                    state=bench.load(ident)
                    if state['status'] not in {'planning','queued'}:break
                    page.wait_for_timeout(20)
                page.get_by_role('button',name='Observe workspace',exact=False).click()
                expect(page.locator('#ifd-project option')).to_have_count(2,timeout=10000)
                page.locator('#ifd-project').select_option(ident)
                expect(page.locator('.ifd-observed-status')).to_have_text('proposed',timeout=10000)
                assert page.locator('.ifd-events button').count()==0
                state['status']='building';bench.save(state)
                expect(page.locator('[data-id="state-building"] .ifd-running')).to_have_count(1,timeout=5000)
                bench.trace(state,'model_request_started',{'provider':'ollama','model':'fixture','role':'coder'})
                expect(page.locator('.ifd-events button').filter(has_text='ModelClient.complete()')).to_have_attribute('title',re.compile('model_request_started'),timeout=5000)
                centered('ModelClient.complete()')
                bench.trace(state,'model_attempt',{'success':False,'error_category':'transport'})
                expect(page.locator('.ifd-events')).to_contain_text('ModelClient.complete()',timeout=5000)
                expect(page.locator('.ifd-failed')).to_have_count(1,timeout=5000)
                centered('ModelClient.complete()')
                page.get_by_label('Follow activity',exact=True).uncheck()
                viewport=page.locator('.react-flow__viewport').get_attribute('style')
                bench.trace(state,'code_response_rejected',{'reason':'Fixture: invalid Python; no files replaced','files_replaced':False})
                expect(page.locator('.ifd-events')).to_contain_text('Workbench.generate_and_apply()',timeout=5000)
                assert page.locator('.ifd-failed').count()==2
                expect(page.locator('.ifd-events button').filter(has_text='Workbench.generate_and_apply()')).to_have_attribute('title',re.compile('invalid Python'))
                page.wait_for_timeout(400)
                assert page.locator('.react-flow__viewport').get_attribute('style')==viewport,'Unchecked Follow moved the viewport'
                page.get_by_label('Follow activity',exact=True).check()
                centered('Workbench.generate_and_apply()')
                bench.trace(state,'task_readiness',{'task':1,'passed':True})
                expect(page.locator('.ifd-events')).to_contain_text('task_readiness()',timeout=5000)
                centered('task_readiness()')
                bench.trace(state,'repair_started',{'repair_id':'fixture-repair','stage':'static_repair'})
                expect(page.locator('[data-id="repair-start-event"] .ifd-running')).to_have_count(1,timeout=5000)
                centered('repair_started · correlated repair ID')
                bench.trace(state,'repair_finished',{'repair_id':'fixture-repair','status':'failed'})
                expect(page.locator('[data-id="repair-end-event"] .ifd-failed')).to_have_count(1,timeout=5000)
                centered('repair_finished · candidate, not behavioral pass')
                state['status']='generated';bench.save(state)
                expect(page.locator('.ifd-observed-status')).to_have_text('generated',timeout=5000)
                assert page.locator('.ifd-running').count()==0
                page.locator('.ifd-stop').click()
                seen=len(requests);page.wait_for_timeout(1700)
                assert len(requests)==seen,'Observer did not stop polling'
                expect(page.locator('#ifd-project')).to_have_value('')
                expect(page.locator('.ifd-observed-status')).to_contain_text('Stopped')
                page.locator('#ifd-project').select_option(ident)
                expect(page.locator('.ifd-observed-status')).to_have_text('generated',timeout=5000)
                page.get_by_role('button',name='Simulation',exact=False).click()
                expect(page.locator('.ifd-shell')).to_have_attribute('data-layout','ready',timeout=30000)
                page.set_viewport_size({'width':390,'height':844})
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),'Mobile overflow'
                assert page.locator('.ifd-shell').evaluate('el=>el.getBoundingClientRect().x===0&&el.getBoundingClientRect().width===innerWidth'),'Dashboard must fill the mobile viewport'
                page.screenshot(path='/tmp/foundry-dashboard-mobile.png',full_page=True)
                page.emulate_media(reduced_motion='reduce')
                page.get_by_label('Full map',exact=True).uncheck()
                expect(page.locator('.ifd-shell')).to_have_attribute('data-layout','ready',timeout=30000)
                page.get_by_role('button',name='Play simulation',exact=False).click()
                expect(page.locator('.ifd-running')).to_have_count(1)
                page.get_by_role('button',name='Pause simulation').click()
                assert page.locator('.ifd-running').evaluate('el=>getComputedStyle(el).animationName')=='none'
                page.locator('.ifd-stop').click()
                assert all(method=='GET' for method,_ in requests),requests
                assert not errors,errors
                browser.close()
        finally:server.shutdown();server.server_close()
    print(f'PASS: Chromium desktop/mobile; local ELK worker; {len(graph["nodes"])} disjoint HTML nodes / {len(graph["edges"])} SVG edges; running glow, animated paths, completion/failure, pause/resume/stop, fit/search/source inspector, reduced motion; simulation has no controller calls; observer ignores old history, maps new failure, clears finished activity and cancels polling; no mutations or JS errors.')


if __name__=='__main__':main()
