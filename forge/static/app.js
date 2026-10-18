'use strict';
const $ = id => document.getElementById(id);
const token = document.querySelector('meta[name="foundry-token"]').content;
const activeStatuses = new Set(['planning','building','checking','repairing','queued']);
let current = null, lastPlan = '', fileCache = {}, polling = false;
const defaults = {ollama:'qwen3.5:9b',groq:'',openrouter:'',gemini:'gemini-2.5-flash'};

async function api(path, body) {
  const response = await fetch(path, {method:body === undefined?'GET':'POST', headers:{'X-Foundry-Token':token,'Content-Type':'application/json'},body:body === undefined?undefined:JSON.stringify(body)});
  if (!response.ok) { const result = await response.json(); throw new Error(result.error || 'Request failed.'); }
  return response.json();
}
function notice(message) { $('notice').textContent = message; $('notice').hidden = !message; }
function handle(fn) { return async event => { if(event) event.preventDefault(); try { notice(''); await fn(event); } catch(error) { notice(error.message); } }; }
function button(text, fn, className='quiet') { const b=document.createElement('button'); b.textContent=text; b.className=className; b.type='button'; b.onclick=handle(fn); return b; }
function cloudConsent() { return $('project-cloud-consent').checked || $('change-cloud-consent').checked; }
function statusLabel(status) { return status==='generated'?'Files ready · not tested':status.replaceAll('_',' '); }
function selectedModels() { return {planner:{provider:$('planner-provider').value,model:$('planner-model').value},coder:{provider:$('coder-provider').value,model:$('coder-model').value}}; }
function updateCloud() { document.querySelector('.cloud-option').hidden = ['planner','coder'].every(r => $(r+'-provider').value==='ollama'); }
function tab(name) {
  document.querySelectorAll('[data-tab]').forEach(b => { const selected=b.dataset.tab===name; b.classList.toggle('selected',selected); b.setAttribute('aria-selected',String(selected)); });
  ['proposal','build','files'].forEach(t => $('panel-'+t).hidden=t!==name);
  if(name==='files' && current && !activeStatuses.has(current.status)) loadFiles().catch(e=>notice(e.message));
}
async function listProjects() {
  const projects=await api('/api/projects'); $('projects').replaceChildren();
  $('workspace-project-count').textContent=projects.length+' saved projects';const calls=projects.flatMap(p=>p.model_calls||[]);$('workspace-call-count').textContent=calls.length+' model requests · '+calls.reduce((n,c)=>n+c.seconds,0).toFixed(1)+'s';
  if(!projects.length){ const p=document.createElement('p');p.className='muted';p.textContent='Your ideas will live here.';$('projects').append(p); }
  for(const p of projects){const b=button('',()=>openProject(p.id),'project-link'+(current?.id===p.id?' selected':''));const title=document.createElement('strong');title.textContent=p.title+(p.parent_id?' · improvement':'');const status=document.createElement('small');status.textContent=statusLabel(p.status);b.append(title,status);$('projects').append(b);}
}
async function openProject(id) {
  current=await api('/api/projects/'+id);lastPlan='';$('revision').value='';$('project-cloud-consent').checked=false;$('change-cloud-consent').checked=false;
  $('create-view').hidden=true;$('project-view').hidden=false;render();tab(current.approved?'build':'proposal');await listProjects();
}
function fillList(id, items) { $(id).replaceChildren(...items.map(text=>{const li=document.createElement('li');li.textContent=text;return li;})); }
function render() {
  if(!current)return;const p=current,busy=activeStatuses.has(p.status);
  $('breadcrumb').textContent=p.title;$('project-title').textContent=p.title;$('project-summary').textContent=p.plan?.summary||p.idea;
  $('project-status').textContent=statusLabel(p.status);$('project-status').className='badge '+p.status;
  $('step-plan').classList.toggle('done',!!p.plan);$('step-approve').classList.toggle('done',p.approved);$('step-build').classList.toggle('done',!!p.plan&&p.next_task===p.plan.tasks.length&&p.preflight?.passed===true);$('step-check').classList.toggle('done',p.status==='verified');
  $('proposal-loading').hidden=!!p.plan;$('proposal-loading').textContent=p.status==='error'?'Planning stopped: '+p.error+' — retry below.':'Your planner is shaping the idea. Local models may take a few minutes.';
  if(!p.plan && !busy){$('proposal-loading').replaceChildren(document.createTextNode(p.error||'No proposal yet.'),button('Retry proposal',()=>job('plan',{}),'secondary'));}
  $('proposal-content').hidden=!p.plan;
  if(p.plan){
    fillList('features',p.plan.features);fillList('limits',[...p.plan.out_of_scope.map(x=>'Later: '+x),...p.plan.risks.map(x=>'Consider: '+x)]);
    $('tasks').replaceChildren(...p.plan.tasks.map((t,i)=>{const li=document.createElement('li');li.textContent=(i<p.next_task?'✓ ':'')+t.title;const small=document.createElement('small');small.textContent=t.instructions;li.append(small);return li;}));
    $('acceptance').textContent=JSON.stringify(p.plan.checks,null,2);
    const serialized=JSON.stringify(p.plan,null,2);if(lastPlan!==serialized){$('plan-editor').value=serialized;lastPlan=serialized;}
  }
  renderGuidance(p); renderChecks(p);
  $('plan-editor').disabled=p.approved||busy;$('proposal-actions').hidden=p.approved;
  $('approve').disabled=busy;$('revise').disabled=busy;
  $('generate').disabled=busy||!p.approved;$('verify').disabled=busy||!p.approved;$('stop').disabled=!busy;
  $('download').disabled=busy||!p.approved;$('refresh-files').disabled=busy;
  $('progress-text').textContent=`${p.next_task} of ${p.plan?.tasks.length||0} tasks saved. ${p.repair_count} repairs applied in total.`;
  $('edit-models').disabled=busy;$('improve-panel').hidden=!p.approved; $('request-change').disabled=busy;
  $('project-lineage').hidden=!p.parent_id; $('project-lineage').replaceChildren(); if(p.parent_id){$('project-lineage').append(document.createTextNode('Improvement of '+p.parent_title+' · '),button('Open original',()=>openProject(p.parent_id)));}
  $('model-usage').textContent=`${(p.model_calls||[]).length} model requests · ${(p.model_calls||[]).reduce((n,c)=>n+c.seconds,0).toFixed(1)} seconds of model response time. One request runs at a time.`;
  document.querySelector('.change-cloud').hidden=[p.planner,p.coder].every(m=>m.provider==='ollama');
  $('model-label').textContent=`Planner: ${p.planner.provider}/${p.planner.model} · Builder: ${p.coder.provider}/${p.coder.model}`;
  document.querySelector('.project-cloud').hidden=[p.planner,p.coder].every(m=>m.provider==='ollama');
  $('test-badge').textContent=p.checks?(p.checks.passed?'Checks passed':'Checks failed'):'Not verified';$('test-badge').className='badge '+(p.checks?.passed?'verified':p.checks?'error':'');
  $('test-output').textContent=p.checks?`Runtime: ${p.checks.runtime} · Exit: ${p.checks.exit_code}\n\n${p.checks.log}`:p.preflight?(p.preflight.passed?'Static syntax/structure checks passed. No generated code has run. Behavioral verification still requires execution approval.':'Static inspection found problems (no code executed):\n\n'+p.preflight.issues.join('\n')):'No checks have run yet.';
  $('events').replaceChildren(...p.events.map(e=>{const d=document.createElement('div');d.className='event';const time=document.createElement('time');time.textContent=new Date(e.time).toLocaleTimeString();d.append(time,document.createTextNode(e.message));return d;}));
  $('snapshots').replaceChildren(...p.snapshots.slice().reverse().map(s=>{const b=button(s.label,async()=>{if(!confirm('Restore this checkpoint? Current files will be backed up first.'))return;current=await api(`/api/projects/${p.id}/restore`,{snapshot:s.id});render();await loadFiles();},'secondary');b.disabled=busy;return b;}));
}
async function job(action,options) {
  if(!current)return;
  current=await api(`/api/projects/${current.id}/${action}`,{...options,cloud_consent:cloudConsent()});render();await listProjects();
}
async function loadFiles(){fileCache=await api(`/api/projects/${current.id}/files`);$('file-list').replaceChildren();for(const [name,content] of Object.entries(fileCache)){const b=button(name,()=>{$('file-content').textContent=content;document.querySelectorAll('#file-list button').forEach(x=>x.classList.toggle('selected',x===b));});$('file-list').append(b);}const first=Object.keys(fileCache).find(n=>n==='app.py')||Object.keys(fileCache)[0];$('file-content').textContent=first?fileCache[first]:'No generated files yet.';}
async function connections(){
  $('connection-list').textContent='Checking connections…';const info=await api('/api/connections');$('connection-list').replaceChildren();$('ollama-models').replaceChildren();
  for(const [name,p] of Object.entries(info.providers)){const div=document.createElement('div');div.className='connection-item';const strong=document.createElement('strong');strong.textContent=name;const text=document.createElement('p');text.textContent=name==='ollama'?(p.connected?'Connected · '+p.models.join(', '):'Not connected. Start Ollama, then check again.'):(p.configured?'API key present · connection not yet tested':`Optional · add ${p.key_variable} to .env`);div.append(strong,text);$('connection-list').append(div);if(name==='ollama')for(const m of p.models){const o=document.createElement('option');o.value=m;$('ollama-models').append(o);}}
  const d=document.createElement('p');d.className='muted';d.textContent=info.docker?.image_ready?'Docker is ready for isolated verification.':info.docker?.running?'Docker is running. Prepare its image with: docker pull python:3.12-slim':info.docker_installed?'Docker is installed but not running. Start Docker Desktop.':'Docker not installed. Code generation works without it; isolated verification needs Docker Desktop.';$('connection-list').append(d);
}
$('idea-form').onsubmit=handle(async()=>{const models=selectedModels();$('propose').disabled=true;try{const p=await api('/api/projects',{idea:$('idea').value,...models,cloud_consent:$('create-cloud').checked});localStorage.setItem('foundry-models',JSON.stringify(models));await openProject(p.id);}finally{$('propose').disabled=false;}});
$('new-project').onclick=handle(async()=>{current=null;lastPlan='';$('create-view').hidden=false;$('project-view').hidden=true;$('breadcrumb').textContent='A new beginning';await listProjects();});
document.querySelectorAll('[data-idea]').forEach(b=>b.onclick=()=>{$('idea').value=b.dataset.idea;$('idea').focus();});
document.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>tab(b.dataset.tab));
['planner','coder'].forEach(role=>$(role+'-provider').onchange=()=>{$(role+'-model').value=$(role+'-provider').value==='ollama'?(role==='coder'?'qwen2.5-coder:7b':'qwen3.5:9b'):defaults[$(role+'-provider').value];updateCloud();});
$('revise').onclick=handle(()=>job('plan',{revision:$('revision').value}));
$('approve').onclick=handle(async()=>{current=await api(`/api/projects/${current.id}/approve`,{plan:JSON.parse($('plan-editor').value)});render();tab('build');await listProjects();});
$('generate').onclick=handle(()=>job('build',{execute:false,repairs:Number($('repairs').value)}));
$('verify').onclick=handle(async()=>{if(!$('execution-consent').checked)throw new Error('Review the execution settings and check the approval box first.');await job('build',{execute:true,consent:true,runtime:$('runtime').value,repairs:Number($('repairs').value)});});
$('stop').onclick=handle(async()=>{const result=await api(`/api/projects/${current.id}/stop`,{});notice(result.message);});
$('runtime').onchange=()=>{$('execution-consent').checked=false;$('runtime-note').textContent=$('runtime').value==='local'?'Generated Python will run with your Windows account permissions. A project folder is NOT a security sandbox. Use only code you trust; Docker is recommended.':'Requires Docker Desktop and the python:3.12-slim image. No network or host API keys inside the container.';};
$('refresh-files').onclick=handle(loadFiles);
$('download').onclick=handle(async()=>{const response=await fetch(`/api/projects/${current.id}/download`,{headers:{'X-Foundry-Token':token}});if(!response.ok){const result=await response.json();throw new Error(result.error);}const blob=await response.blob();const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='generated-app.zip';document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);});
$('connections-button').onclick=handle(async()=>{$('connections').showModal();await connections();});$('close-connections').onclick=()=>$('connections').close();$('refresh-connections').onclick=handle(connections);
try{const saved=JSON.parse(localStorage.getItem('foundry-models')||'null');if(saved)for(const role of ['planner','coder']){$(role+'-provider').value=saved[role].provider;$(role+'-model').value=saved[role].model;}}catch(_){}
updateCloud();listProjects().catch(e=>notice(e.message));connections().catch(()=>{});
setInterval(async()=>{if(polling||!current||!activeStatuses.has(current.status))return;polling=true;try{const id=current.id;const p=await api('/api/projects/'+id);if(current?.id!==id)return;current=p;render();if(!activeStatuses.has(p.status))await listProjects();}catch(e){notice(e.message);}finally{polling=false;}},1800);

function renderChecks(p){
  $('check-cards').replaceChildren();
  if(!p.plan)return;
  for(const check of p.plan.checks){const card=document.createElement('div');card.className='check-card';const title=document.createElement('strong');title.textContent=check.name;const detail=document.createElement('code');detail.textContent=`${check.method} ${check.path} → HTTP ${check.status}`;const covers=document.createElement('small');covers.textContent=(check.feature_indexes||[]).map(i=>p.plan.features[i]).filter(Boolean).join(' · ');card.append(title,detail,covers);$('check-cards').append(card);}
}
function renderGuidance(p){
  const busy=activeStatuses.has(p.status);let title,description,action='View progress',target=p.approved?'build':'proposal';
  if(busy){title=p.status==='queued'?'Waiting for a model':'Your project is moving forward';description=p.events.at(-1)?.message||'Your work is saved as each task completes.';}
  else if(!p.approved&&p.plan){title='Review the plan before we build';description='Check the features, scope, and expected behavior below. Revise anything that does not match your idea.';action='Review proposal';}
  else if(!p.approved){title='Let’s get your proposal ready';description=p.error||'Your planner can retry or take a new direction. You can also change the selected models.';action='Retry proposal';}
  else if(p.status==='verified'){title='Your app passed its checks';description='Download it, follow its README, and try the workflows yourself. Describe the next improvement below when you’re ready.';action='Get my app';target='files';}
  else if(p.status==='generated'){title='Files are ready. Now test the app.';description='Code has been inspected without running it. Choose an execution option and approve it to run real behavioral checks.';action='Go to verification';}
  else if(['error','needs_attention','stopped','interrupted'].includes(p.status)){title='Your work is saved. Let’s resolve the next step.';description=p.error||p.preflight?.issues?.join(' ')||'Review the verification output, switch models if needed, and resume. Existing checkpoints remain available.';action='Review and resume';}
  else {title='Your plan is approved. Let’s build.';description='Generate the files first, or approve execution to build and test in one run. Your code stays in its own project.';action='Choose build options';}
  $('next-title').textContent=title;$('next-description').textContent=description.slice(0,450);$('next-action').textContent=action;$('next-models').hidden=busy;$('next-models').onclick=()=>$('edit-models').click();
  $('next-action').onclick=handle(async()=>{if(!p.approved&&!p.plan&&!busy){await job('plan',{});return;}tab(target);$('panel-'+target).scrollIntoView({behavior:'smooth',block:'start'});});
  const failed=!!p.error||p.preflight?.passed===false||p.checks?.passed===false;
  $('build-diagnosis').hidden=!failed;$('build-diagnosis').replaceChildren();
  if(failed){const h=document.createElement('strong');h.textContent='What needs attention';const text=document.createElement('p');text.textContent=p.error||(p.preflight?.passed===false?p.preflight.issues.join(' '):'The app did not pass its behavioral checks. The output below shows the failing test or request. You can retry with another model or restore a checkpoint.');$('build-diagnosis').append(h,text);$('test-details').open=true;}
}
async function workspaceInfo(){const info=await api('/api/info');$('workspace-version').textContent='IDEA FOUNDRY '+info.version;$('workspace-project-count').textContent=info.projects+' saved projects';$('workspace-call-count').textContent=info.model_calls+' model requests · '+info.model_seconds+'s';$('workspace-details').textContent='Version '+info.version+' · Projects: '+info.projects+' · Data folder: '+info.data_folder;$('workspace-warnings').textContent=info.warnings.join(' ');return info;}
async function saveDownload(path,name){const response=await fetch(path,{headers:{'X-Foundry-Token':token}});if(!response.ok){const result=await response.json();throw new Error(result.error);}const url=URL.createObjectURL(await response.blob());const a=document.createElement('a');a.href=url;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);}
$('workspace-button').onclick=handle(async()=>{$('workspace-dialog').showModal();await workspaceInfo();});$('close-workspace').onclick=()=>$('workspace-dialog').close();
$('backup-workspace').onclick=handle(()=>saveDownload('/api/backup','Idea-Foundry-workspace-backup.zip'));
$('edit-models').onclick=handle(()=>{for(const role of ['planner','coder']){$('project-'+role+'-provider').value=current[role].provider;$('project-'+role+'-model').value=current[role].model;}$('models-dialog').showModal();});
$('close-models').onclick=()=>$('models-dialog').close();
$('model-form').onsubmit=handle(async()=>{const models={};for(const role of ['planner','coder'])models[role]={provider:$('project-'+role+'-provider').value,model:$('project-'+role+'-model').value};current=await api('/api/projects/'+current.id+'/models',models);$('models-dialog').close();$('project-cloud-consent').checked=false;$('change-cloud-consent').checked=false;render();});
$('request-change').onclick=handle(async()=>{const b=$('request-change');b.disabled=true;try{const next=await api('/api/projects/'+current.id+'/change',{request:$('change-request').value,cloud_consent:cloudConsent()});$('change-request').value='';await openProject(next.id);}finally{b.disabled=false;}});
$('review-diff').onclick=handle(async()=>{const files=await api('/api/projects/'+current.id+'/diff');$('diff-list').replaceChildren();if(!files.length)$('diff-list').textContent='No source changes since the last checkpoint.';for(const file of files){const d=document.createElement('details');const title=document.createElement('summary');title.textContent=file.kind+' · '+file.name;const pre=document.createElement('pre');pre.textContent=file.diff;d.append(title,pre);$('diff-list').append(d);}});
workspaceInfo().catch(()=>{});
