"""Five-category, source-bound workflow facts; never execute or approve anything."""
from __future__ import annotations
import re
from typing import Any
from .reporting import OWNED, evidence_status
from .execution import task_board


def ownership_warnings(plan: dict[str, Any]) -> list[dict[str, Any]]:
    warnings=[]
    for index,task in enumerate(plan.get('tasks',[])):
        text=str(task.get('title',''))+' '+str(task.get('instructions',''))
        names=[name for name in sorted(OWNED) if re.search(r'(?<![\w/-])'+re.escape(name)+r'(?![\w-]|\.\w)',text,re.I)]
        if names:warnings.append({'task':index+1,'files':names,'message':'Foundry supplies these protected artifacts. The builder must use APP-GUIDE.md for extra app documentation; the approved task remains unchanged.'})
    return warnings


def coverage(plan: dict[str, Any]) -> list[dict[str, Any]]:
    rows=[]
    for index,feature in enumerate(plan.get('features',[])):
        rows.append({'feature':feature,'tasks':[i+1 for i,t in enumerate(plan.get('tasks',[])) if index in t.get('feature_indexes',[])],
            **{kind:[i+1 for i,c in enumerate(plan.get(kind,[])) if index in c.get('feature_indexes',[])] for kind in ('checks','manual_checks','browser_checks')}})
    return rows


def workflow_snapshot(state: dict[str, Any], files: dict[str, str]) -> dict[str, Any]:
    plan=state.get('plan') or {}; fresh=evidence_status(state,files)
    tasks=len(plan.get('tasks',[])); saved=min(max(state.get('next_task',0),0),tasks)
    manual_total=len(plan.get('manual_checks',[])); observations=state.get('manual_results') or {}
    results=observations.get('results',[])
    observations_current=bool(fresh['automated_evidence_current'] and observations.get('source_sha256')==fresh['current_source_sha256'] and len(results)==manual_total)
    passed=sum(v is True for v in results) if observations_current else 0
    failed=sum(v is False for v in results) if observations_current else 0
    routes={role:[state[role],*(state[role].get('fallbacks') or ([state[role]['fallback']] if state[role].get('fallback') else []))] if state.get(role) else [] for role in ('planner','coder')}
    receipts=[r for r in state.get('task_receipts',[]) if r.get('task',tasks+1)<=saved]
    if not plan: next_step='Create a proposal'
    elif not state.get('approved'): next_step='Review the proposal'
    elif saved<tasks: next_step='Generate or resume saved tasks'
    elif not fresh['automated_evidence_current']: next_step='Run automated verification'
    elif failed: next_step='Repair the recorded failed checks and retest'
    elif not fresh['accepted_current']: next_step='Complete manual acceptance checks'
    else: next_step='Download this verified snapshot'
    if state.get('status') in {'planning','building','checking','repairing','queued'}:
        next_step='Job is '+state['status']+'. Wait for completion or use Stop job.'
    return {'schema':1,'project_id':state['id'],'status':fresh['effective_status'],
        'categories':[
            {'id':'models','name':'1 · Setup & models','state':'Configured' if all(routes.values()) else 'Needs setup','detail':f"Planner route: {len(routes['planner'])} models; builder route: {len(routes['coder'])}. Configuration does not prove access or quota.",'action':'models'},
            {'id':'planning','name':'2 · Plan & approval','state':'Approved' if state.get('approved') else 'Review' if plan else 'Pending','detail':f"{len(plan.get('features',[]))} features; {tasks} tasks. Coverage is declared, not proof of implementation.",'action':'proposal'},
            {'id':'generation','name':'3 · Build & recovery','state':f'{saved}/{tasks} tasks saved','detail':f"{len(receipts)} task change receipts available. Static checks do not prove behavior.",'action':'build'},
            {'id':'verification','name':'4 · Verification','state':'Accepted' if fresh['accepted_current'] else 'Manual review' if fresh['automated_evidence_current'] else 'Not currently verified','detail':f"Manual: {passed} passed, {failed} failed, {manual_total-passed-failed} pending. Automated evidence: {'current' if fresh['automated_evidence_current'] else 'absent or stale'}.",'action':'build'},
            {'id':'delivery','name':'5 · Workspace & delivery','state':'Verified snapshot' if fresh['accepted_current'] else 'Unverified snapshot','detail':f'{len(files)} project files. Export includes a readable handoff guide and source-bound evidence.','action':'files'}],
        'model_budget':{'used':state.get('job_inference_attempts'),'limit':state.get('job_max_model_calls'),'meaning':'Model complete() invocations in the latest run, including recovery and retrieval. Not provider transports, billed tokens, money or a hard wall-clock deadline.'},
        'task_board':task_board(state,files),'next_step':next_step,'coverage':coverage(plan),'ownership_warnings':ownership_warnings(plan),
        'task_receipts':receipts,'receipt_coverage':{'available':len(receipts),'saved_tasks':saved,'meaning':'Receipts exist only for tasks saved after this feature was introduced; no legacy changes are inferred.'},
        'evidence':fresh,'manual':{'required':manual_total,'passed':passed,'failed':failed,'pending':manual_total-passed-failed,'observations_current':observations_current},
        'meaning':'Controller facts and declared coverage; no new model requests, app execution, approvals or acceptance results.'}


def delivery_guide(state: dict[str, Any], snapshot: dict[str, Any]) -> str:
    fresh=snapshot['evidence']; manual=snapshot['manual']
    return '\n'.join(['# '+str(state.get('title','Generated app'))+' — handoff', '',
        'Status: '+snapshot['status'],
        'Current automated verification: '+('YES' if fresh['automated_evidence_current'] else 'NO'),
        'Current overall acceptance: '+('YES' if fresh['accepted_current'] else 'NO'),
        f"Manual checks: {manual['passed']} passed, {manual['failed']} failed, {manual['pending']} pending.",
        'Source SHA-256: '+fresh['current_source_sha256'],'',
        '## Run on your computer','Finish generation before launching incomplete output. Review the code first. Open the generated-app folder. When the launch files exist, on Windows double-click run.bat; otherwise run python3 launch.py. Keep the terminal open. Follow its printed address; the launcher may choose a different free port.',
        'Browser localStorage belongs to the browser and origin (including port). Changing the port can show different browser data. Use the app export feature when available for backups. Server database files remain in the app folder.','',
        '## What to do next',snapshot['next_step'],
        'A ZIP can contain unfinished or unverified files. Downloading it does not make it verified. Manual observations and automated evidence refer to their recorded source snapshot.',
        'Read README.md, PROJECT.md, MANUAL-CHECKS.md when present, and APP-GUIDE.md if generated. BUILD-REPORT.json and RUN-HISTORY.json provide detailed evidence and history.',
        'The .foundry folder contains export-only metadata; it is not app source or a test result. Keep the previous working folder until this version is tested.',''])


def delivery_checklist(state: dict[str,Any], snapshot: dict[str,Any]) -> str:
    """Export-only checklist: saved source and acceptance stay separate."""
    def mark(value: bool) -> str:return '[x]' if value else '[ ]'
    fresh=snapshot['evidence'];rows=snapshot['task_board']['tasks'];budget=snapshot['model_budget']
    lines=['# Work checklist — '+str(state.get('title','Generated app')),'',
           'Source SHA-256: '+fresh['current_source_sha256'],
           'This checklist describes the exported snapshot. Saved source is not proof of behavior.','',
           '- '+mark(bool(state.get('approved')))+' Proposal approval recorded',
           '- '+mark(state.get('next_task',0)>=len((state.get('plan') or {}).get('tasks',[])) and bool(rows))+' All task source saved',
           '- '+mark(fresh['automated_evidence_current'])+' Current automated checks passed',
           '- '+mark(fresh['accepted_current'])+' Current overall acceptance complete','',
           '## Sequential tasks']
    for row in rows:
        lines+=['',str(row['task'])+'. '+row['title']+' — '+row['state'],
                'Outcome: '+row['outcome'],'Editable files: '+(', '.join(row['files']) or 'Legacy task scope'),
                'Declared criteria (not individually verified):']
        lines+=['- '+criterion for criterion in row['criteria']]
        lines+=['Related approved checks (feature overlap, not execution evidence): '+('; '.join(c['kind']+' #'+str(c['number'])+' '+c['name'] for c in row['related_checks']) or 'None mapped')]
    lines+=['','## Model and verification boundaries',
            'Latest run: '+str(budget['used'] if budget['used'] is not None else 'unknown')+' / '+str(budget['limit'] if budget['limit'] is not None else 'allowance not recorded')+' model invocations. '+budget['meaning'],
            'Planner: '+str(state.get('planner',{}).get('provider',''))+'/'+str(state.get('planner',{}).get('model','')),
            'Builder: '+str(state.get('coder',{}).get('provider',''))+'/'+str(state.get('coder',{}).get('model','')),
            'Model rank is a preference heuristic, not a best-performance benchmark.',
            'Cloud consent, execution approval and manual acceptance remain separate.','',
            'Next step: '+snapshot['next_step'],'']
    return '\n'.join(lines)
