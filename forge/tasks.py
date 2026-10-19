"""Versioned, bounded task contracts; declarations are not execution evidence."""
from __future__ import annotations
import copy
import re
from typing import Any
from .reporting import OWNED
from .edits import expand_response

MAX_TASKS = 16
TASK_FIELDS = ('outcome', 'files', 'depends_on', 'done_when')


def validate_tasks(plan: dict[str, Any]) -> None:
    version=plan.get('task_contract_version')
    if version is None:return  # Historical proposals keep their exact approval artifact.
    if type(version) is not int or version != 1:raise ValueError('Unsupported task_contract_version; use 1.')
    for index,task in enumerate(plan['tasks']):
        label=f'Task {index+1}'
        if any(k not in task for k in TASK_FIELDS):raise ValueError(label+': needs outcome, files, depends_on and done_when. Split broad work before approval.')
        if not isinstance(task['outcome'],str) or not 1<=len(task['outcome'].strip())<=300:raise ValueError(label+': outcome must describe one observable result (1–300 characters).')
        if len(task['instructions'])>1800:raise ValueError(label+': instructions exceed 1800 characters; split into smaller tasks.')
        if re.search(r'\b(?:all remaining features|everything else|complete the entire app)\b',task['outcome']+' '+task['instructions'],re.I):raise ValueError(label+': catch-all task; assign each remaining behavior its own bounded task.')
        files=task['files']
        if not isinstance(files,list) or not 1<=len(files)<=3 or not all(isinstance(n,str) for n in files):raise ValueError(label+': list 1–3 editable file paths; split wider changes.')
        if len({n.lower() for n in files})!=len(files):raise ValueError(label+': duplicate/case-colliding file paths.')
        for name in files:
            parts=name.split('/')
            reserved={'CON','PRN','AUX','NUL',*(f'COM{i}' for i in range(1,10)),*(f'LPT{i}' for i in range(1,10))}
            if any(p.split('.')[0].upper() in reserved for p in parts) or name.lower() in OWNED or len(name)>160 or not re.fullmatch(r'[A-Za-z0-9_. /-]+',name) or any(p in {'','.','..'} or p.startswith('.') or p.endswith((' ','.')) for p in parts):raise ValueError(label+': invalid or controller-owned file path '+name+'. Use app source/tests or APP-GUIDE.md.')
        interfaces=task.get('interfaces',[])
        if not isinstance(interfaces,list) or len(interfaces)>6:raise ValueError(label+': interfaces must list at most six contracts.')
        for interface in interfaces:
            if not isinstance(interface,dict) or set(interface)!={'file','symbol','contract'} or not all(isinstance(interface[k],str) and 0<len(interface[k])<=500 for k in interface):raise ValueError(label+': each interface needs file, symbol and contract text.')
        deps=task['depends_on']
        if not isinstance(deps,list) or any(type(n) is not int or not 0<=n<index for n in deps) or len(set(deps))!=len(deps):raise ValueError(label+': depends_on must contain unique earlier zero-based task indexes; no forward references or cycles.')
        criteria=task['done_when']
        if not isinstance(criteria,list) or not 1<=len(criteria)<=4 or not all(isinstance(s,str) and 1<=len(s.strip())<=300 for s in criteria):raise ValueError(label+': done_when needs 1–4 concrete completion criteria (up to 300 characters each).')
        if not 1<=len(task['feature_indexes'])<=3:raise ValueError(label+': cover 1–3 feature indexes; split broad implementation work.')


def task_packet(plan: dict[str, Any], index: int, saved_tasks: int) -> dict[str, Any]:
    task=plan['tasks'][index]
    structured=plan.get('task_contract_version')==1
    deps=task.get('depends_on',[]) if structured else list(range(index))
    missing=[n for n in deps if n>=saved_tasks]
    if missing:raise ValueError('Task dependencies are not saved: '+', '.join(str(n+1) for n in missing))
    return {'schema':1,'task_index':index,'task_count':len(plan['tasks']),'structured':structured,
            'outcome':task.get('outcome',task['title']), 'files':copy.deepcopy(task.get('files',[])) if structured else [],
            'depends_on':copy.deepcopy(deps),'done_when':copy.deepcopy(task.get('done_when',[])) if structured else [],
            'interfaces':copy.deepcopy(task.get('interfaces',[])),
            'evidence_status':'Declared criteria only. Saved source/static inspection are not behavioral verification.',
            'scope_rule':'Implement only this task; preserve earlier behavior and interfaces. Do not implement later tasks or rebuild the entire app. The final task integrates prior work; it does not absorb missing features.'}


def validate_task_response(response: Any, current: dict[str,str], packet: dict[str,Any] | None) -> None:
    if not packet or not packet.get('structured'):return
    files=expand_response(response,current)
    changed=[name for name,text in files.items() if current.get(name)!=text]
    outside=sorted(set(changed)-set(packet['files']))
    if outside:raise ValueError('Task scope violation: '+', '.join(outside)+'. Change only approved task files: '+', '.join(packet['files'])+'. Preserve other files; return exact edits or only changed files.')
    if not changed:raise ValueError('Task produced no source changes. A model summary cannot complete a structured implementation task.')


def task_document(plan: dict[str,Any]) -> str:
    lines=['# Build tasks','','Tasks run sequentially. Criteria below are declarations, not behavioral verification.','']
    for index,task in enumerate(plan['tasks']):
        lines.extend([f'{index+1}. {task["title"]}', '   '+task['instructions']])
        if plan.get('task_contract_version')==1:
            lines.extend(['   Outcome: '+task['outcome'], '   Editable files: '+', '.join(task['files']),
                          '   Dependencies: '+(', '.join('Task '+str(n+1) for n in task['depends_on']) or 'none'),
                          *['   Done when: '+criterion for criterion in task['done_when']]])
    return '\n'.join(lines)+'\n'


def existing_task_evidence(response: Any, current: dict[str,str], packet: dict[str,Any] | None) -> dict[str,Any] | None:
    """Check quoted source only. Never infer behavior or execute generated code."""
    if not isinstance(response,dict) or 'already_satisfied' not in response:return None
    if not packet or not packet.get('structured'):raise ValueError('Existing-work claims require a structured task packet.')
    if set(response)-{'already_satisfied','summary'}:raise ValueError('Existing-work claim cannot be mixed with files or edits.')
    claim=response['already_satisfied']
    if not isinstance(claim,dict) or set(claim)!={'reason','evidence'}:raise ValueError('Existing-work claim needs reason and evidence only.')
    reason=claim['reason'];evidence=claim['evidence']
    if not isinstance(reason,str) or not 20<=len(reason.strip())<=1000:raise ValueError('Explain existing work in 20–1000 characters.')
    if not isinstance(evidence,list) or not 1<=len(evidence)<=4:raise ValueError('Cite 1–4 exact source excerpts for existing work.')
    for item in evidence:
        if not isinstance(item,dict) or set(item)!={'file','contains'}:raise ValueError('Each source reference needs file and contains.')
        name=item['file'];snippet=item['contains']
        if not isinstance(name,str) or name not in packet['files'] or name not in current:raise ValueError('Cite an existing file inside the approved task scope.')
        if not isinstance(snippet,str) or not 20<=len(snippet.strip())<=500 or snippet not in current[name]:raise ValueError('Source evidence must match an actual 20–500 character excerpt; do not guess.')
    return {'kind':'existing_source_supported','reason':reason,'evidence':copy.deepcopy(evidence),
            'behavior_verified':False,'note':'Quoted source exists. Semantics and acceptance remain unverified until execution/manual checks.'}
