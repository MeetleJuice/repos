'use strict';
const $=id=>document.getElementById(id);
let notes=[];
function message(text){$('message').textContent=text;$('message').hidden=!text;}
async function request(path,method='GET',body){const response=await fetch(path,{method,headers:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});const data=await response.json();if(!response.ok)throw new Error(data.error||'Request failed.');return data;}
function render(){
  const query=$('search').value.toLocaleLowerCase();const visible=notes.filter(n=>n.title.toLocaleLowerCase().includes(query));
  $('count').textContent=`(${visible.length} of ${notes.length})`;
  $('notes').replaceChildren(...visible.map(note=>{const card=document.createElement('article');const title=document.createElement('h2');title.textContent=note.title;const body=document.createElement('p');body.textContent=note.body;const remove=document.createElement('button');remove.type='button';remove.className='delete';remove.textContent='Delete';remove.setAttribute('aria-label','Delete '+note.title);remove.onclick=async()=>{remove.disabled=true;try{await request('/api/notes/'+note.id,'DELETE');await load();message('');}catch(error){message(error.message);remove.disabled=false;}};card.append(title,body,remove);return card;}));
  $('empty').hidden=visible.length>0;$('empty').textContent=notes.length?'No notes match that title.':'No notes yet. Write your first one above.';
}
async function load(){notes=await request('/api/notes');render();}
$('note-form').onsubmit=async e=>{e.preventDefault();$('add-note').disabled=true;try{await request('/api/notes','POST',{title:$('title').value,body:$('body').value});$('note-form').reset();await load();message('');$('title').focus();}catch(error){message(error.message);}finally{$('add-note').disabled=false;}};
$('search').oninput=render;
load().catch(error=>message(error.message));
