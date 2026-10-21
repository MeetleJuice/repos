"""Proof planning -> real SQLite milestone -> UI -> verification/export. Mock LLM replies."""
import copy
import json
import os
from pathlib import Path
import shutil
import socket
import sqlite3
import subprocess
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
from tests.test_workbench import ScriptedModels
from tests.test_evidence_planning import sqlite_plan
from tests.test_guided_planning import feature_batches,outline_replies

HTML='''<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>Tiny Wins</title><link rel="stylesheet" href="/style.css"></head><body><main><h1>Tiny Wins</h1><form id="form"><input id="title" required placeholder="Your win"><input id="note" placeholder="A note"><button>Add win</button></form><label>Show <select id="filter"><option value="all">All time</option><option value="today">Today</option></select></label><p id="count"></p><p id="message" role="status"></p><ul id="wins"></ul></main><script>
async function refresh(){const suffix=document.querySelector('#filter').value==='today'?'?filter=today':'';const response=await fetch('/api/records'+suffix);const data=await response.json();document.querySelector('#count').textContent=data.today_count+' wins today';const list=document.querySelector('#wins');list.replaceChildren();for(const item of data.records){const li=document.createElement('li');const text=document.createElement('span');text.textContent=item.title+' — '+item.note;li.append(text);const button=document.createElement('button');button.textContent='Delete';button.onclick=async()=>{if(confirm('Delete this win?')){await fetch('/api/records/'+item.id,{method:'DELETE'});await refresh();}};li.append(button);list.append(li);}}
document.querySelector('#form').onsubmit=async event=>{event.preventDefault();const response=await fetch('/api/records',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title:document.querySelector('#title').value,note:document.querySelector('#note').value})});if(!response.ok){document.querySelector('#message').textContent='Could not save';return;}document.querySelector('#form').reset();await refresh();};document.querySelector('#filter').onchange=refresh;refresh();
</script></body></html>'''
CSS='body{background:#111827;color:#f8fafc;font:16px system-ui;margin:0}main{max-width:650px;margin:3rem auto;padding:1rem}h1{color:#fbbf24}form{display:flex;gap:.5rem;flex-wrap:wrap}input{min-width:0;max-width:100%}li{padding:1rem;border:1px solid #475569;display:flex;justify-content:space-between;gap:1rem;overflow-wrap:anywhere}button{background:#fbbf24;color:#111827;border:0;padding:.6rem;border-radius:.4rem}span{min-width:0}'


def main(granular=False,hybrid=False):
    plan=sqlite_plan()
    if hybrid:plan['app_kind']='browser'
    outline={k:v for k,v in plan.items() if k!='tasks'}
    claim={'already_satisfied':{'reason':'The reviewed starter already implements record creation, retrieval and SQLite persistence; retain it and run the approved prefix.',
        'evidence':[{'file':'storage.py','contains':'class Store:\n    def __init__(self, path):'}]}}
    scope,acceptance=outline_replies(outline)
    invalid=copy.deepcopy(acceptance)
    invalid['checks'][2].pop('restart_before')
    if granular:
        from tests.test_feature_acceptance import feature_replies
        packets=feature_replies(acceptance,2);invalid=copy.deepcopy(packets[0]);invalid['checks'][0]['restart_before']=True
        planning=[scope,invalid,*packets]
    else:planning=[scope,invalid,acceptance]
    models=ScriptedModels([*planning,*feature_batches(plan['tasks']),claim,{'files':{'index.html':HTML,'style.css':CSS}}])
    info={'ollama':{'connected':True,'models':['qwen2.5-coder:7b']}}
    with tempfile.TemporaryDirectory() as folder,patch('forge.server.connection_info',return_value=info),patch('forge.models.request_json',return_value={}):
        bench=Workbench(Path(folder)/'projects',models);server=make_server(0,bench)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(executable_path=shutil.which('chromium'));page=browser.new_page(viewport={'width':1440,'height':1000});errors=[]
                page.on('pageerror',lambda error:errors.append(str(error)))
                page.goto('http://127.0.0.1:'+str(server.server_port))
                page.locator('#idea').fill('A local Tiny Wins tracker with tested SQLite storage and a simple browser interface')
                page.locator('#starter').select_option('sqlite')
                if granular:
                    page.locator('#new-plan-mode').select_option('granular')
                    expect(page.locator('#new-local-timeout')).to_have_value('120')
                    page.locator('#propose').click()
                else:page.locator('#plan-with-proof').click()
                expect(page.locator('#project-status')).to_have_text('proposed',timeout=15000)
                state=bench.list_projects()[0];ident=state['id'];frozen=copy.deepcopy(state['plan'])
                assert state['evidence_planning'] and frozen['acceptance_policy']=='evidence_v1'
                expected=['scope','acceptance_feature','acceptance_feature','acceptance_feature','feature_tasks','feature_tasks'] if granular else ['scope','acceptance','acceptance','feature_tasks','feature_tasks']
                assert [call['planning_stage'] for call in models.calls[:len(expected)]]==expected
                assert state['model_calls'][1]['failure_class']=='schema_error'
                assert ('restart_evidence' if granular else 'missing_persistence_scenario') in state['model_calls'][1]['review_codes']
                expect(page.locator('#builder-profile')).to_contain_text('Evidence-ready')
                page.locator('#approve').click();page.locator('#runtime').select_option('local')
                page.locator('#execution-consent').check();page.locator('#repairs').select_option('0');page.locator('#milestone-checks').check();page.locator('#verify').click()
                expect(page.locator('#project-status')).to_have_text('Automated checks passed · try the app',timeout=45000)
                state=bench.load(ident);assert state['plan']==frozen
                receipt=state['task_receipts'][0]
                assert receipt['milestone_evidence']['passed'] and receipt['milestone_evidence']['http_prefix_count']==3
                assert not receipt['source_changed'];assert state['checks']['passed']
                assert bench.files(ident)['test_foundation.py']==starter_files('sqlite')['test_foundation.py']
                # Run the actual generated app and perform its manual browser scenario.
                with socket.socket() as reserved:reserved.bind(('127.0.0.1',0));port=reserved.getsockname()[1]
                source=bench.directory(ident)/'source'
                child=subprocess.Popen([sys.executable,'app.py','--port',str(port)],cwd=source,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,env={k:v for k,v in os.environ.items() if k in {'PATH','SYSTEMROOT','WINDIR','TEMP','TMP'}})
                try:
                    pet=browser.new_page(viewport={'width':390,'height':844});pet.on('pageerror',lambda error:errors.append(str(error)))
                    for attempt in range(50):
                        try:pet.goto('http://127.0.0.1:'+str(port));break
                        except Exception:
                            if attempt==49:raise
                            pet.wait_for_timeout(50)
                    with sqlite3.connect(source/'app.db') as conn:
                        conn.execute('INSERT INTO records(title,note,created_at) VALUES(?,?,?)',('Yesterday','','2000-01-01T12:00:00'))
                    pet.reload();expect(pet.locator('#wins')).to_contain_text('Yesterday')
                    title='<img src=x onerror=alert(1)>'
                    pet.locator('#title').fill(title);pet.locator('#note').fill('A real browser observation');pet.get_by_role('button',name='Add win').click()
                    expect(pet.locator('#wins')).to_contain_text(title)
                    expect(pet.locator('#wins li')).to_have_count(2)
                    pet.locator('#filter').select_option('today');expect(pet.locator('#wins li')).to_have_count(1)
                    expect(pet.locator('#wins')).not_to_contain_text('Yesterday')
                    pet.reload();expect(pet.locator('#wins')).to_contain_text(title)
                    pet.locator('#filter').select_option('today');expect(pet.locator('#wins li')).to_have_count(1)
                    assert pet.locator('#wins img').count()==0
                    assert pet.evaluate('document.documentElement.scrollWidth<=innerWidth')
                    pet.once('dialog',lambda dialog:dialog.accept());pet.get_by_role('button',name='Delete',exact=True).click()
                    expect(pet.locator('#wins li')).to_have_count(0);pet.close()
                finally:child.terminate();child.wait(timeout=5)
                page.locator('#manual-0').select_option('pass');page.locator('#save-manual').click()
                expect(page.locator('#project-status')).to_have_text('verified')
                page.get_by_role('tab',name='Project files').click()
                with page.expect_download() as pending:page.locator('#download').click()
                archive=Path(folder)/'Tiny-Wins.zip';pending.value.save_as(archive)
                with zipfile.ZipFile(archive) as z:
                    report=json.loads(z.read('generated-app/BUILD-REPORT.json'))
                    assert report['approved_plan']['acceptance_policy']=='evidence_v1'
                    assert report['checks']['passed'] and report['task_receipts'][0]['milestone_evidence']['passed']
                assert not errors,errors;browser.close()
        finally:server.shutdown();server.server_close()
    print('PASS: proof-mode proposal -> protected SQLite foundation -> unchanged approval -> executed 3-check milestone before UI -> real final tests -> mobile browser create/reload/filter/delete and literal text safety -> observed manual result -> verified ZIP. LLM replies are fixtures, not live model quality evidence.')


if __name__=='__main__':main()
