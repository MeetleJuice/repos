'use strict';
const $=id=>document.getElementById(id);
let tasks=[], filter='all';
function message(text){$('message').textContent=text;$('message').hidden=!text;}
async function request(path,method='GET',body){const r=await fetch(path,{method,headers:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});const data=await r.json();if(!r.ok)throw new Error(data.error||'Request failed.');return data;}
async function load(){tasks=await request('/api/tasks');render();}
function render(){
  const remaining=tasks.filter(t=>!t.completed).length;$('count').textContent=`${remaining} remaining · ${tasks.length} total`;
  const visible=tasks.filter(t=>filter==='all'||(filter==='done'?t.completed:!t.completed));
  $('tasks').replaceChildren(...visible.map(task=>{
    const li=document.createElement('li');li.className=task.completed?'done':'';
    const label=document.createElement('label');const checkbox=document.createElement('input');checkbox.type='checkbox';checkbox.checked=task.completed;checkbox.setAttribute('aria-label',`Complete ${task.title}`);
    checkbox.onchange=async()=>{checkbox.disabled=true;try{await request('/api/tasks/'+task.id,'PUT',{completed:checkbox.checked});await load();message('');}catch(e){checkbox.checked=task.completed;message(e.message);}finally{checkbox.disabled=false;}};
    const title=document.createElement('span');title.textContent=task.title;label.append(checkbox,title);
    const remove=document.createElement('button');remove.type='button';remove.className='delete';remove.textContent='Delete';remove.setAttribute('aria-label',`Delete ${task.title}`);
    remove.onclick=async()=>{remove.disabled=true;try{await request('/api/tasks/'+task.id,'DELETE');await load();message('');}catch(e){message(e.message);remove.disabled=false;}};
    li.append(label,remove);return li;
  }));$('empty').hidden=visible.length>0;$('empty').textContent=tasks.length?'No tasks in this view.':'Your list is clear. Add something above.';
}
$('add-form').onsubmit=async e=>{e.preventDefault();const title=$('title').value.trim();if(!title)return;$('add').disabled=true;try{await request('/api/tasks','POST',{title});$('title').value='';await load();message('');$('title').focus();}catch(error){message(error.message);}finally{$('add').disabled=false;}};
document.querySelectorAll('[data-filter]').forEach(button=>button.onclick=()=>{filter=button.dataset.filter;document.querySelectorAll('[data-filter]').forEach(b=>{b.classList.toggle('selected',b===button);b.setAttribute('aria-pressed',String(b===button));});render();});
load().catch(e=>message(e.message));
