"""Task checkpoint reconciliation and evidence levels; never executes app code."""
from __future__ import annotations
import hashlib
import json
from typing import Any
from .context import fingerprint
from .reporting import evidence_status, OWNED


def plan_hash(plan: dict[str,Any]) -> str:
    return hashlib.sha256(json.dumps(plan,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def file_hashes(files: dict[str,str]) -> dict[str,str]:
    return {name:hashlib.sha256(text.encode()).hexdigest() for name,text in files.items()}


def source_hash(files: dict[str,str]) -> str:
    return fingerprint({n:t for n,t in files.items() if n.lower() not in OWNED})


def seal_checkpoint(state: dict[str,Any], files: dict[str,str]) -> None:
    state['execution_checkpoint']={'schema':1,'cursor':state.get('next_task',0),'source_sha256':source_hash(files),'plan_sha256':plan_hash(state.get('plan') or {})}


def resume_problem(state: dict[str,Any], files: dict[str,str]) -> str:
    cursor=state.get('next_task',0)
    if type(cursor) is not int or not 0<=cursor<=len((state.get('plan') or {}).get('tasks',[])):return 'Task position is outside the approved plan. Restore a consistent checkpoint.'
    pending=state.get('pending_task'); checkpoint=pending or state.get('execution_checkpoint')
    if not checkpoint:return ''
    if checkpoint.get('plan_sha256')!=plan_hash(state.get('plan') or {}):return 'Approved plan differs from the saved execution checkpoint. Review the plan before continuing.'
    if checkpoint.get('cursor')!=state.get('next_task',0):return 'Saved task position differs from its execution checkpoint. Restore a checkpoint or review the current files.'
    expected=(checkpoint.get('candidate_sha256') or checkpoint.get('before_sha256')) if pending else checkpoint.get('source_sha256')
    if expected!=source_hash(files):return 'Project files changed since the saved task checkpoint. No new implementation request was sent. Restore a checkpoint or explicitly keep these files as the new resume baseline.'
    return ''


def begin_task(state: dict[str,Any], index: int, files: dict[str,str]) -> bool:
    if resume_problem(state,files):raise ValueError(resume_problem(state,files))
    pending=state.get('pending_task')
    if pending and pending.get('phase') in {'candidate_saved','source_supported'}:
        state['last_task_support']=pending.get('source_support')
        return True
    state['pending_task']={'schema':1,'cursor':index,'plan_sha256':plan_hash(state['plan']),'before_sha256':source_hash(files),'before_files':file_hashes(files),'phase':'awaiting_candidate'}
    return False


def candidate_saved(state: dict[str,Any], files: dict[str,str], support: dict[str,Any] | None = None) -> None:
    pending=state.get('pending_task')
    if pending:
        pending.update(phase='source_supported' if support else 'candidate_saved',candidate_sha256=source_hash(files),source_support=support)
    elif state.get('execution_checkpoint'):seal_checkpoint(state,files)


def finish_task(state: dict[str,Any], files: dict[str,str]) -> None:
    state.pop('pending_task',None);seal_checkpoint(state,files)


def task_board(state: dict[str,Any], files: dict[str,str]) -> dict[str,Any]:
    plan=state.get('plan') or {};cursor=state.get('next_task',0);fresh=evidence_status(state,files)
    receipts={r['task']-1:r for r in state.get('task_receipts',[]) if r.get('task',0)<=cursor}
    rows=[]
    for index,task in enumerate(plan.get('tasks',[])):
        receipt=receipts.get(index,{});saved=index<cursor
        dependencies=task.get('depends_on',list(range(index)))
        blocked=[n+1 for n in dependencies if n>=cursor]
        state_name='Saved · checks pending' if saved else 'Blocked by earlier work' if blocked or index>cursor else 'Ready to build' if state.get('approved') else 'Awaiting approval'
        if not saved and index==cursor and state.get('status') in {'building','repairing','checking','queued'}:state_name='In progress'
        if not saved and index==cursor and state.get('pending_task',{}).get('candidate_sha256'):state_name='Candidate saved · inspection pending'
        if saved and receipt.get('disposition')=='existing_source_supported':state_name='Existing source cited · checks pending'
        if saved and fresh['automated_evidence_current']:state_name='Included in current automated run · review manual checks'
        if saved and fresh['accepted_current']:state_name='Included in accepted app snapshot'
        milestone=receipt.get('milestone_evidence')
        features=set(task.get('feature_indexes',[]))
        related=[{'kind':kind,'number':i+1,'name':check['name']} for kind in ('checks','browser_checks','manual_checks')
                 for i,check in enumerate(plan.get(kind,[])) if features.intersection(check.get('feature_indexes',[]))]
        rows.append({'task':index+1,'title':task['title'],'outcome':task.get('outcome',task['title']),'state':state_name,'blocked_by':blocked,'files':task.get('files',[]),
                     'related_checks':related,'related_checks_meaning':'Related by declared feature coverage; not per-criterion execution proof.',
                     'check_indexes':task.get('check_indexes',[]),'source_changed':receipt.get('source_changed'),
                     'milestone_evidence':milestone,'milestone_current':bool(milestone and milestone.get('passed') and milestone.get('source_sha256')==fresh['current_source_sha256']),
                     'interfaces':task.get('interfaces',[]),'criteria':task.get('done_when',[])})
    problem=resume_problem(state,files)
    return {'schema':1,'tasks':rows,'resume_problem':problem,'adopt_allowed':bool(problem and (state.get('pending_task') or state.get('execution_checkpoint') or {}).get('plan_sha256')==plan_hash(plan) and (state.get('pending_task') or state.get('execution_checkpoint') or {}).get('cursor')==cursor),'candidate_waiting':bool(state.get('pending_task',{}).get('candidate_sha256')),
            'context_policy':plan.get('context_policy','full'),'meaning':'Readiness uses saved source dependencies. Only named executed checks provide behavior evidence; source citations and model summaries do not.'}
