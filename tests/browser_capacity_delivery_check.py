"""Builder-sized planning -> scoped correction -> real checks/export, fixture models."""
import copy
import json
import re
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
from forge.server import make_server
from forge.scaffolds import starter_files
from tests.test_guided_planning import responses,feature_batches,outline_replies
from tests.test_workbench import ScriptedModels
from tests.fixtures import APP,TEST


def main():
    outline,batch,_=responses()
    foundation=starter_files('web')['app.py']
    models=ScriptedModels([*outline_replies(outline),*feature_batches(batch['tasks']),{'files':{'app.py':'def broken(:\n'}},
        {'edits':[{'file':'app.py','search':foundation,'replace':APP}]},
        {'files':{'test_app.py':TEST}}])
    info={'ollama':{'configured':True,'connected':True,'models':['qwen2.5-coder:7b','qwen3-embedding:0.6b']}}
    with tempfile.TemporaryDirectory() as temp,patch('forge.server.connection_info',return_value=info),patch('forge.models.request_json',return_value={'model_info':{'qwen.context_length':32768}}) as metadata:
        bench=Workbench(Path(temp)/'projects',models);server=make_server(0,bench)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(executable_path=shutil.which('chromium'))
                page=browser.new_page(viewport={'width':1440,'height':1050});errors=[]
                page.on('pageerror',lambda error:errors.append(str(error)))
                page.goto('http://127.0.0.1:'+str(server.server_port))
                page.locator('#idea').fill('A small local task tracker with SQLite storage')
                page.locator('#plan-for-builder').click()
                expect(page.locator('#project-status')).to_have_text('proposed',timeout=15000)
                state=bench.list_projects()[0];ident=state['id']
                assert state['planning_mode']=='guided' and state['builder_profile']['max_editable_files']==2
                assert state['builder_profile']['max_feature_indexes']==1
                assert 'test_foundation.py' in state['builder_profile']['protected_existing_files']
                expect(page.locator('#builder-profile')).to_contain_text('up to 2 editable files')
                frozen=copy.deepcopy(state['plan'])
                page.locator('#connections-button').click()
                page.locator('#model-limit-details > summary').click()
                expect(page.locator('#model-limit-list')).to_contain_text(re.compile(r'32,?768 model context tokens'))
                expect(page.locator('#model-limit-list')).to_contain_text('Embedding model; not an app builder')
                page.get_by_role('button',name='Close connections',exact=True).click()
                page.locator('#approve').click()
                page.locator('#runtime').select_option('local');page.locator('#execution-consent').check()
                page.locator('#repairs').select_option('0');page.locator('#verify').click()
                expect(page.locator('#project-status')).to_have_text('verified',timeout=30000)
                state=bench.load(ident);assert state['plan']==frozen
                coding=[call for call in state['model_calls'] if call['role']=='coder']
                assert len(coding)==3 and coding[0]['model']==coding[1]['model']
                assert coding[1]['recovery_path']=='task_response_correction'
                assert models.calls[5]['response_mode']=='focused_changes'
                assert 'builder_handoff' in models.calls[4]
                assert state['generation_stats']['exact_edits_applied']==1
                assert state['checks']['passed'] and state['next_task']==2
                page.get_by_role('tab',name='Project files').click()
                with page.expect_download() as opened:page.locator('#download').click()
                destination=Path(temp)/'app.zip';opened.value.save_as(destination)
                with zipfile.ZipFile(destination) as archive:
                    report=json.loads(archive.read('generated-app/BUILD-REPORT.json'))
                    assert report['checks']['passed'] and len(report['task_receipts'])==2
                    assert archive.read('generated-app/app.py').decode()==APP
                    assert archive.read('generated-app/test_foundation.py').decode()==starter_files('web')['test_foundation.py']
                page.set_viewport_size({'width':390,'height':844})
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                assert all(call.args[0].endswith('/api/show') for call in metadata.call_args_list)
                assert not errors,errors
                browser.close()
        finally:server.shutdown();server.server_close()
    print('PASS: Plan for my builder -> validated outline/scoped tasks -> unchanged approval -> rejected Python -> same-model exact-edit correction -> sequential build -> real acceptance/tests/launch -> verified ZIP; frozen foundation retained; metadata-only model limits and embedding exclusion; mobile/no JS errors. Model replies are fixtures, not live-model quality evidence.')


if __name__=='__main__':main()
