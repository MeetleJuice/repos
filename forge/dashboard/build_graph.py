"""Developer-only source audit/generator; never imported by the running app."""
from pathlib import Path
import ast
import hashlib
import json
import re
import shutil

FEATURE=Path(__file__).resolve().parent
ROOT=FEATURE.parents[1]
nodes={};edges={};flows=[]


def slug(text):return re.sub('[^a-z0-9]+','-',text.lower()).strip('-')


def node(ident,label,kind,category,file,needle,description=''):
    text=(ROOT/file).read_text(encoding='utf-8')
    if needle not in text:raise ValueError(f'No source evidence for {label}: {file}: {needle}')
    line=text[:text.index(needle)].count('\n')+1
    nodes.setdefault(ident,dict(id=ident,label=label,kind=kind,category=category,source=file,line=line,
                               excerpt=text.splitlines()[line-1][:280],description=description))
    return ident


def proc(label,file=None,category='Workbench & session'):
    name=label.split('(')[0].split('.')[-1]
    file=file or ('forge/core.py' if label.startswith('Workbench.') else 'forge/static/app.js')
    return node('proc-'+slug(label),label,'process',category,file,'def '+name+'(' if file.endswith('.py') else 'function '+name+'(')


def flow(ident,label,category,path,failures=()):
    for source,target in zip(path,path[1:]):
        key=source+'--'+target
        edges.setdefault(key,dict(id=key,source=source,target=target,label='recorded call / continuation'))
    flows.append(dict(id=ident,label=label,category=category,path=path,failures=list(failures)))


root=node('document','GET / · index.html','lifecycle','Workbench & session','forge/server.py','elif path == "/":','Browser document request; no framework lifecycle is assumed.')
deferred=node('deferred','app.js · deferred evaluation','lifecycle','Workbench & session','forge/static/index.html','src="/app.js"')
guard=node('guard','Handler.check_request()','process','Workbench & session','forge/server.py','def check_request(')
token=node('token','secrets.compare_digest(X-Foundry-Token)','process','Workbench & session','forge/server.py','secrets.compare_digest(')
api_wrapper=proc('api(path, body)')
direct=node('direct-fetch','fetch(path, headers)','process','Delivery & recovery','forge/static/app.js','async function saveDownload(')
error=node('http-error','Handler.dispatch() → HTTP 403','state','Workbench & session','forge/server.py','except PermissionError','Possible Host/Origin/token rejection, not a fabricated provider failure.')
notice=proc('notice(message)')
ui=proc('render()')
flow('startup','Document & deferred scripts','Workbench & session',[root,deferred])

backend_files={'Workbench':'forge/core.py','ModelStatus':'forge/model_status.py','CloudSetup':'forge/cloud.py',
               'SystemTests':'forge/system_tests.py',
               'CredentialStore':'forge/credentials.py','UpdateManager':'forge/updates.py',
               'collect_report':'forge/diagnostic_report.py','export_report':'forge/diagnostic_report.py','generate_idea':'forge/ideas.py'}
endpoints=json.loads((FEATURE/'docs/endpoints.json').read_text())
for index,(method,path,trigger,backend,frontend,detail,after,category) in enumerate(endpoints):
    file='forge/static/'+frontend;text=(ROOT/file).read_text()
    suffix=path.rsplit('/',1)[-1]
    needle=path if path in text else '/'+suffix if '/'+suffix in text else '/api/projects' if '/api/projects' in text else 'api('
    trigger_id=node('action-'+str(index),trigger,'action',category,file,needle,detail)
    route_source=(ROOT/'forge/server.py').read_text()
    route_needle='if len(pieces) == 3' if path=='/api/projects/{id}' else path if path in route_source else '"'+suffix+'"' if '"'+suffix+'"' in route_source else "'"+suffix+"'"
    api_id=node('api-'+slug(method+' '+path),method+' '+path,'api',category,'forge/server.py',route_needle,detail)
    if backend.startswith('Handler.'):
        business=node('backend-'+str(index),backend,'process',category,'forge/server.py',path)
    elif backend=='connection_info()':business=proc(backend,'forge/models.py',category)
    elif backend.split('(')[0] in backend_files:business=proc(backend,backend_files[backend.split('(')[0]],category)
    else:business=proc(backend,backend_files[backend.split('.')[0]],category)
    # The continuation resumes the actual caller; labels use real statements/functions.
    end_id=node('return-'+str(index),after+' · response continuation','state',category,file,needle,
                'Returns to '+detail+'. This is UI/controller progress, not behavioral verification.')
    # Health and inline ZIP downloads fetch directly; do not invent a call
    # through saveDownload() or the JSON wrapper for those sites.
    transports=[direct] if path=='/api/backup' else [] if path=='/health' or path.endswith('/download') or path=='/api/diagnostics/export' else [api_wrapper]
    checks=[guard] if path=='/health' else [guard,token]
    flow('endpoint-'+str(index),method+' '+path,category,[root,deferred,trigger_id,*transports,api_id,*checks,business,end_id])
    flow('rejection-'+str(index),method+' '+path+' · rejected request',category,
         [root,deferred,trigger_id,*transports,api_id,guard,error],[error])

# Only an actual handle()-wrapped UI action is shown reaching notice().
# Background health/activity polling can suppress errors or retry instead.
approve_request=next(item for item in flows if item['id']=='rejection-7')
flow('ui-permission-notice','Approval request rejected · handle() / notice()','Planning & approval',
     [*approve_request['path'],notice],[error])

for asset in ['app.js','planning.js','updates.js','cloud.js','activity.js','workflow.js','studio.js','diagnostics.js','studio.css','style.css','icon.png']:
    asset_id=node('static-'+slug(asset),'GET /'+asset,'api','Workbench & session','forge/server.py','"/'+asset+'"' if asset!='icon.png' else '"/icon.png"')
    flow('static-'+slug(asset),'Local asset · '+asset,'Workbench & session',[root,asset_id])

for file,needle,label in [
 ('app.js','}, 1800);','setInterval · active project · 1800 ms'),
 ('activity.js','setInterval(refreshModelStatus, 1000)','refreshModelStatus() · 1000 ms poll'),
 ('updates.js','setInterval(pollUpdate, 1200)','pollUpdate() · 1200 ms while dialog open'),
 ('updates.js','}, 1000);','reconnect() · 1000 ms / 60 attempts'),
 ('planning.js','setTimeout(reviewEditor, 500)','reviewEditor() · 500 ms debounce'),
 ('app.js','setTimeout(() => URL.revokeObjectURL','URL.revokeObjectURL() · 1000 ms cleanup'),
 ('studio.js','pointerdown','pointerdown → unlockStudioAudio()'),
 ('app.js','addEventListener("toggle"','history-details toggle → loadHistory()'),
 ('planning.js','DOMContentLoaded','planning.js · DOMContentLoaded'),
 ('cloud.js','DOMContentLoaded','cloud.js · DOMContentLoaded'),
 ('workflow.js','DOMContentLoaded','workflow.js · DOMContentLoaded'),
 ('updates.js','new CustomEvent("foundry:update-ready"','foundry:update-ready · CustomEvent'),
 ('app.js','function tab(','tab(name) → aria-selected / hidden'),
 ('studio.js','function observeStudioJob(','observeStudioJob() → optional cue')]:
    ident=node('life-'+slug(label),label,'lifecycle','Workbench & session','forge/static/'+file,needle)
    flow(ident,label,'Workbench & session',[root,deferred,ident])

state_ids={}
core_text=(ROOT/'forge/core.py').read_text();core_ast=ast.parse(core_text)
for statement in ast.walk(core_ast):
    status=None
    if isinstance(statement,ast.Assign) and any(isinstance(t,ast.Subscript) and isinstance(t.slice,ast.Constant) and t.slice.value=='status' for t in statement.targets) and isinstance(statement.value,ast.Constant):status=statement.value.value
    if isinstance(statement,ast.Call) and isinstance(statement.func,ast.Attribute) and statement.func.attr=='update':
        for keyword in statement.keywords:
            if keyword.arg=='status' and isinstance(keyword.value,ast.Constant):status=keyword.value.value
    if isinstance(status,str) and status not in state_ids:
        needle=core_text.splitlines()[statement.lineno-1].strip()
        state_ids[status]=node('state-'+slug(status),'status = '+status,'state','Build & verification','forge/core.py',needle)
# Ternary/tuple/constructor assignments are explicit code sites rather than inferred states.
for status,needle in {'planning':'state["status"] = "planning" if action == "plan"','error':'state["status"], state["error"] = "error"',
                      'verified':'state["status"] = "review_required" if','review_required':'state["status"] = "review_required" if',
                      'draft':'"status": "draft"','approved':'state["approved"], state["status"] = True, "approved"'}.items():
    if status not in state_ids:state_ids[status]=node('state-'+slug(status),'status = '+status,'state','Build & verification','forge/core.py',needle)

owners={'draft':'create','approved':'approve','interrupted':'__init__','queued':'call_model','planning':'start','building':'start','repairing':'_inspect_and_repair'}
for status,ident in state_ids.items():
    owner=proc('Workbench.'+owners.get(status,'_job')+'()')
    path=[owner,ident,root] if status=='interrupted' else [root,owner,ident]
    flow('state-tour-'+status,'Controller state · '+status,'Build & verification',path,[ident] if status in {'error','needs_attention'} else [])

create=proc('Workbench.create()');start=proc('Workbench.start()');job=proc('Workbench._job()')
call=proc('Workbench.call_model()');model=proc('ModelClient.complete()','forge/models.py','Models & routing')
proposal=proc('require_consistent()','forge/contracts.py','Planning & approval')
apply=proc('Workbench.apply()');inspect=proc('Workbench._inspect_and_repair()')
generate=proc('Workbench.generate_and_apply()');approve=proc('Workbench.approve()')
begin=proc('begin_task()','forge/execution.py');finish=proc('finish_task()','forge/execution.py');gate=proc('finish_gate()','forge/execution.py')
response=proc('validate_task_response()','forge/tasks.py')
context=proc('prepare_context()','forge/focus.py')
checkpoint=proc('Workbench.checkpoint()')
cancel=proc('Workbench.stop()')
flow('project-plan','Shape an idea · planner success','Planning & approval',[root,create,start,state_ids['planning'],job,call,model,proposal,state_ids['proposed'],ui])
flow('guided-plan','Small-step planning · unapproved checkpoints','Planning & approval',[root,start,job,proc('run_guided()','forge/guided.py'),call,model,proc('validate_outline()','forge/guided.py'),call,model,proc('validate_batch()','forge/guided.py'),proposal,state_ids['proposed'],ui])
flow('compiled-plan','One feature · controller-owned task references and checkpoints','Planning & approval',[root,start,job,proc('run_guided()','forge/guided.py'),proc('run_compiled()','forge/task_planning.py'),call,model,proc('validate_compilable_outline()','forge/task_planning.py'),call,model,proc('compile_tasks()','forge/task_planning.py'),proc('schedule()','forge/task_planning.py'),proc('validate_batch()','forge/guided.py'),proposal,state_ids['proposed'],ui])
flow('split-outline','Saved scope · acceptance evidence · complete outline review','Planning & approval',[root,start,job,proc('run_compiled()','forge/task_planning.py'),proc('create_outline()','forge/outline_planning.py'),call,model,proc('validate_scope()','forge/outline_planning.py'),call,model,proc('assemble()','forge/outline_planning.py'),proc('validate_compilable_outline()','forge/task_planning.py'),proposal,state_ids['proposed'],ui])
flow('project-build','Approved project · sequential generation','Build & verification',[root,approve,state_ids['approved'],start,state_ids['building'],job,begin,context,generate,call,model,response,apply,checkpoint,inspect,gate,finish,state_ids['generated'],ui])
runtime=proc('require_runtime()','forge/runner.py');verify=proc('verify()','forge/runner.py')
acceptance=proc('acceptance()','forge/harness.py');tests=proc('generated_tests()','forge/harness.py');launch=proc('launch()','forge/harness.py')
flow('project-verify','Explicit execution · real verification','Build & verification',[root,start,job,runtime,state_ids['checking'],verify,acceptance,tests,launch,state_ids['verified'],ui])
flow('manual-review','Automated pass · manual acceptance still needed','Build & verification',[root,start,job,runtime,state_ids['checking'],verify,state_ids['review_required'],proc('Workbench.record_manual()'),state_ids['verified'],ui])
flow('repair-loop','Failed check · bounded repair / retest','Build & verification',[root,start,job,state_ids['checking'],verify,state_ids['repairing'],generate,call,model,response,apply,inspect,state_ids['checking'],verify,state_ids['verified'],ui],[])
flow('stop-job','Stop request · cooperative worker exit','Delivery & recovery',[root,cancel,job,state_ids['stopped'],ui])
flow('failed-job','Request failure · journal / error','Delivery & recovery',[root,start,job,call,state_ids['error'],ui],[state_ids['error']])
model_start=proc('ModelStatus.start()','forge/model_status.py','Models & routing')
model_finish=proc('ModelStatus.finish()','forge/model_status.py','Models & routing')
model_reject=proc('ModelStatus.reject()','forge/model_status.py','Models & routing')
flow('model-observed','Model activity · recorded request lifecycle','Models & routing',[root,call,model_start,model,model_finish,call])
flow('model-rejected','Source response rejected · focused correction','Models & routing',[root,generate,call,model_start,model,model_finish,response,model_reject,generate],[model_reject])
profile=proc('builder_profile()','forge/build_contract.py','Planning & approval')
handoff=proc('focused_handoff()','forge/build_contract.py','Build & verification')
native=proc('request_schema()','forge/models.py','Models & routing')
inventory=proc('refresh_local_limits()','forge/model_inventory.py','Models & routing')
show=node('local-model-show','POST OLLAMA_URL/api/show','api','Models & routing','forge/model_inventory.py',"+'/api/show'",'Installed metadata read only. Does not generate or load a model for inference.')
flow('builder-sized-planning','Builder profile · unapproved guided tasks','Planning & approval',[root,start,job,profile,proc('run_guided()','forge/guided.py'),call,model,proc('validate_outline()','forge/guided.py'),call,model,proc('validate_batch()','forge/guided.py'),proposal,state_ids['proposed']])
proof=proc('evidence_findings()','forge/acceptance.py','Planning & approval')
flow('evidence-ready-planning','Evidence-ready plan · scenario and checkpoint review','Planning & approval',[root,start,job,proc('run_guided()','forge/guided.py'),call,model,proc('validate_outline()','forge/guided.py'),proof,call,model,proc('validate_batch()','forge/guided.py'),proof,proposal,state_ids['proposed']])
flow('focused-builder','Focused Ollama task · native scoped JSON','Build & verification',[root,job,generate,handoff,call,model,native,response,apply])
flow('model-metadata','Installed model limits · no generation','Models & routing',[root,inventory,show])
trace=proc('Workbench.trace()')
persist=proc('FlightRecorder.record()','forge/diagnostics.py','Delivery & recovery')
investigate=proc('collect_report()','forge/diagnostic_report.py','Delivery & recovery')
flow('diagnostic-recorder','Controller event · shared IDs and independent persistence','Delivery & recovery',
     [root,job,trace,proc('append()','forge/history.py','Delivery & recovery'),persist])
flow('diagnostic-investigation','Diag · read-only local evidence export','Delivery & recovery',
     [root,investigate,proc('FlightRecorder.snapshot()','forge/diagnostics.py','Delivery & recovery'),proc('export_report()','forge/diagnostic_report.py','Delivery & recovery')])
flow('local-idea-helper','Generate Idea · local request without a project','Planning & approval',
     [root,proc('generate_idea()','forge/ideas.py','Planning & approval'),proc('choose_model()','forge/ideas.py','Planning & approval'),model,
      node('idea-prompt-insertion','Insert editable idea; no project submission','state','Planning & approval','forge/static/diagnostics.js','value = result.idea.trim()')])

provider_ast=ast.parse((ROOT/'forge/providers.py').read_text());providers={}
for statement in provider_ast.body:
    if isinstance(statement,ast.AnnAssign) and isinstance(statement.target,ast.Name) and statement.target.id=='PROVIDERS':providers=ast.literal_eval(statement.value)
for provider,(base,_) in providers.items():
    category='Models & routing'
    if provider=='ollama':catalogue='OLLAMA_URL/api/tags';inference='OLLAMA_URL/api/chat';source='forge/models.py';needle='/api/chat'
    elif provider=='local':catalogue='LOCAL_API_URL/models';inference='LOCAL_API_URL/chat/completions';source='forge/providers.py';needle=base
    elif provider=='gemini':catalogue='https://generativelanguage.googleapis.com/v1beta/models?pageSize=1000';inference='Gemini /v1beta/models/{model}:generateContent';source='forge/models.py';needle=':generateContent'
    elif provider=='cloudflare':catalogue='Cloudflare account ai/models/search';inference=base+'/chat/completions';source='forge/providers.py';needle=base
    else:catalogue=base+'/models';inference=base+'/chat/completions';source='forge/providers.py';needle=base
    catalogue_id=node('catalogue-'+provider,'GET '+catalogue,'api',category,'forge/models.py' if provider in {'ollama','local'} else 'forge/cloud.py','/api/tags' if provider=='ollama' else "endpoint('local')" if provider=='local' else 'def _check_provider(')
    inference_id=node('inference-'+provider,'POST '+inference,'api',category,source,needle)
    discovery=proc('connection_info()','forge/models.py') if provider in {'ollama','local'} else proc('CloudSetup._check_provider()','forge/cloud.py')
    discovery_path=[root,discovery]
    if provider=='openrouter':
        key_check=node('openrouter-key-check','GET https://openrouter.ai/api/v1/key','api',category,'forge/cloud.py',"metadata = request_json(base+'/key'")
        discovery_path.append(key_check)
    flow('catalogue-'+provider,provider+' · catalogue (not generation proof)',category,[*discovery_path,catalogue_id])
    flow('inference-'+provider,provider+' · configured inference',category,[root,call,model,inference_id,model])
    flow('fallback-'+provider,provider+' · failure / next eligible attempt',category,[root,call,model,inference_id,call],[inference_id])
identity=node('hf-identity','GET https://huggingface.co/api/whoami-v2','api','Models & routing','forge/cloud.py','https://huggingface.co/api/whoami-v2')
flow('hf-identity','Hugging Face identity discovery','Models & routing',[root,proc('CloudSetup._check_provider()','forge/cloud.py'),identity])
for label,needle in [('GET releases/latest.json','MANIFEST_URL ='),('GET releases/Idea-Foundry-{version}.zip','release["url"]')]:
    # Archive URL is selected from the validated manifest rather than synthesized by the UI.
    file='forge/updates.py';text=(ROOT/file).read_text()
    if needle not in text:needle="release['url']" if "release['url']" in text else 'def install('
    ident=node('outbound-'+slug(label),label,'api','Delivery & recovery',file,needle)
    flow(ident,label,'Delivery & recovery',[root,proc('fetch_bytes()','forge/updates.py'),ident])
approved=node('approved-app-http',"check['method'] · base + check['path']",'api','Build & verification','forge/harness.py','def fetch(','Approved generated-app HTTP checks, not an invented Foundry endpoint.')
flow('app-http','Generated app · frozen HTTP acceptance','Build & verification',[root,verify,acceptance,proc('fetch()','forge/harness.py'),approved])

version=next(ast.literal_eval(statement.value) for statement in ast.parse((ROOT/'forge/__init__.py').read_text()).body if isinstance(statement,ast.Assign) and any(isinstance(target,ast.Name) and target.id=='__version__' for target in statement.targets))
graph=dict(schema=1,baseline='core '+version+' · source excerpts checked by tests',nodes=list(nodes.values()),edges=list(edges.values()),flows=flows)
(FEATURE/'src/graph.json').write_text(json.dumps(graph,indent=2)+'\n')
shutil.copyfile(ROOT/'DASHBOARD_CODEBASE_MAP.md',FEATURE/'docs/CODEBASE_MAP.md')
for name in ('inventory','research'):
    source=Path('/tmp/dashboard-'+name+'.json')
    if source.exists():shutil.copyfile(source,FEATURE/'docs'/('baseline-'+name+'.json'))
print(f'Generated {len(nodes)} source-referenced nodes, {len(edges)} directed edges, {len(flows)} explicit execution scenarios.')
