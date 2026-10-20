"""Real UI: cloud failure -> local planner -> sequential local tasks -> tests -> ZIP."""
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
from tests.fixtures import APP,TEST
from tests.test_task_contracts import structured_plan
from tests.test_hybrid_execution import supported
from tests.test_workbench import ScriptedModels


def main():
    info={p:{'configured':p in {'gemini','groq'},'key_variable':key} for p,(_,key) in PROVIDERS.items()}
    info['ollama']={'configured':True,'connected':True,'models':['qwen3.5:9b','qwen2.5-coder:7b','qwen3-embedding:0.6b']}
    plan=structured_plan();plan['context_policy']='focused_v1'
    plan['tasks'][0]['check_indexes']=[0,1]
    task=copy.deepcopy(plan['tasks'][0]);task['title']='Inspect saved server contract';task['depends_on']=[0];task.pop('check_indexes');plan['tasks'].append(task)
    models=ScriptedModels([ModelError('Primary unavailable','transport'),ModelError('Secondary unavailable','transport'),plan,{'files':{'app.py':APP,'test_app.py':TEST}},supported()])
    def catalogue(url,**kwargs):
        if 'googleapis' in url:return {'models':[{'name':'models/fixture-gemini','supportedGenerationMethods':['generateContent']}]}
        if 'groq.com' in url:return {'data':[{'id':'fixture-groq'}]}
        raise AssertionError('Unexpected cloud catalogue request: '+url)
    with tempfile.TemporaryDirectory() as temp,patch.dict(os.environ,{'GEMINI_API_KEY':'fixture-only-gemini','GROQ_API_KEY':'fixture-only-groq'},clear=True),patch('forge.server.connection_info',return_value=info),patch('forge.cloud.request_json',side_effect=catalogue):
        bench=Workbench(Path(temp)/'projects',models);server=make_server(0,bench)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(executable_path=shutil.which('chromium'));page=browser.new_page(viewport={'width':1440,'height':1080});errors=[]
                page.on('pageerror',lambda e:errors.append(str(e)))
                base='http://127.0.0.1:'+str(server.server_port);page.goto(base)
                page.locator('#connections-button').click();page.locator('#preset-orchestrated').click()
                expect(page.locator('#cloud-feedback')).to_contain_text('Coding is local only',timeout=15000)
                expect(page.locator('#routing-mode')).to_have_value('orchestrated')
                profile=json.loads((Path(temp)/'cloud-models.json').read_text())['automatic_routes']
                assert [r['provider'] for r in [profile['planner'],*profile['planner']['fallbacks']]]==['gemini','groq','ollama','ollama']
                assert all(r['provider']=='ollama' for r in [profile['coder'],*profile['coder']['fallbacks']])
                assert not models.calls
                page.locator('#close-connections').click();page.locator('#idea').fill('Build a small task tracker with saved tasks')
                page.locator('#propose').click();expect(page.locator('#notice')).to_contain_text('Confirm that you allow')
                assert not models.calls  # No pre-consent cloud planning.
                page.locator('#create-cloud').check();page.locator('#propose').click()
                expect(page.locator('#project-status')).to_have_text('proposed',timeout=15000)
                state=bench.list_projects()[0]
                assert [r['provider'] for r in state['model_calls']]==['gemini','groq','ollama']
                token=page.locator('meta[name=foundry-token]').get_attribute('content')
                denied=page.request.post(base+'/api/projects/'+state['id']+'/plan',data={'cloud_consent':False},headers={'X-Foundry-Token':token})
                assert denied.status==400 and len(models.calls)==3
                page.locator('#approve').click()
                expect(page.locator('.project-cloud')).to_be_hidden()  # Local coding does not ask for unused planner consent.
                expect(page.locator('#task-board-list > li')).to_have_count(2)
                expect(page.locator('#task-board-list')).to_contain_text('Outcome:')
                expect(page.locator('#task-board-list')).to_contain_text('not individually verified')
                expect(page.locator('#task-board-list')).to_contain_text('Related approved checks')
                expect(page.locator('#task-board-list')).to_contain_text('Blocked by earlier work')
                page.locator('#runtime').select_option('local');page.locator('#execution-consent').check();page.locator('#repairs').select_option('0');page.locator('#max-model-calls').select_option('16')
                page.locator('#verify').click()
                expect(page.locator('#project-status')).to_have_text('verified',timeout=25000)
                expect(page.locator('#orchestration-progress')).to_contain_text('2 / 16 model invocations')
                state=bench.load(state['id'])
                assert state['next_task']==2 and state['job_inference_attempts']==2
                assert not state['job_cloud_consent']
                assert [r['provider'] for r in state['model_calls']]==['gemini','groq','ollama','ollama','ollama']
                assert state['model_calls'][-1]['model']=='qwen2.5-coder:7b'
                assert state['milestones'][0]['behavior_verified']
                assert state['checks']['passed'] and state['checks']['phases'][1]['tests_run']>0
                page.set_viewport_size({'width':390,'height':844})
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                page.get_by_role('tab',name='Project files').click()
                with page.expect_download() as downloaded:page.locator('#download').click()
                path=Path(temp)/'app.zip';downloaded.value.save_as(path)
                with zipfile.ZipFile(path) as z:
                    report=json.loads(z.read('generated-app/BUILD-REPORT.json'))
                    checklist=z.read('generated-app/.foundry/WORK-CHECKLIST.md').decode()
                    assert '- [x] Current automated checks passed' in checklist
                    assert '- [x] Current overall acceptance complete' in checklist
                    assert 'not individually verified' in checklist
                    assert report['workflow']['evidence']['current_source_sha256'] in checklist
                    assert report['workflow']['model_budget']['limit']==16
                    assert '.foundry/WORK-CHECKLIST.md' in report['export_metadata_files']
                    assert '.foundry/WORK-CHECKLIST.md' not in [row['file'] for row in report['file_manifest']]
                assert all(secret not in page.locator('body').inner_text() for secret in ['fixture-only-gemini','fixture-only-groq'])
                assert not errors,errors
                browser.close()
        finally:server.shutdown();server.server_close()
    print('PASS: explicit orchestration preset; primary/secondary cloud failures reach local planning; no pre-consent inference; sequential local-only coding without unused cloud consent; task outcome/criteria/checklist; real milestone/final HTTP, unit and launch checks; invocation allowance; verified ZIP/work checklist; mobile/privacy/no JS errors. Model replies are fixtures, not live quality measurements.')


if __name__=='__main__':main()
