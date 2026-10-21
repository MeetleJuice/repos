"""Bounded declaration/scenario checks. No prose claim establishes implementation."""
from __future__ import annotations
import copy
import hashlib
import json
import re
from typing import Any
from urllib.parse import urlsplit

ENDPOINT = re.compile(r'\b(GET|POST|PUT|PATCH|DELETE)\s+(/[A-Za-z0-9_{}:/?.=-]+)')
PERSISTENCE = re.compile(r'\bpersist\w*|\brestart\w*|\breboot\w*', re.I)
ORDERING = re.compile(r'\bnewest.first\b|\boldest.first\b|\b(?:ascending|descending)\b', re.I)
UI = re.compile(r'\b(?:browser|interface|html|canvas|form|controls|frontend|front.end|ui)\b', re.I)


def business_checks(plan: dict[str, Any]) -> list[dict[str, Any]]:
    rows=plan.get('checks',[])
    if not isinstance(rows,list):return []
    return [check for check in rows if isinstance(check, dict)
            and isinstance(check.get('path'), str) and type(check.get('status')) is int
            and 200 <= check['status'] < 300 and urlsplit(check['path']).path not in {'/', '/health'}
            and not re.search(r'\.(?:js|css|png|svg|ico|html)$', urlsplit(check['path']).path, re.I)]


def backend_evidence(plan: dict[str, Any]) -> bool:
    return plan.get('app_kind') != 'browser' or bool(business_checks(plan))


def task_text(task: dict[str, Any]) -> str:
    return ' '.join(str(task.get(key, '')) for key in ('title', 'instructions', 'outcome', 'done_when', 'interfaces'))


def task_digest(task: dict[str, Any]) -> str:
    # Labels/references can differ while the actual instruction remains identical.
    fields={key:task.get(key) for key in ('instructions','outcome','done_when','files','interfaces')}
    return hashlib.sha256(re.sub(r'\s+', ' ', json.dumps(fields,sort_keys=True).lower()).encode()).hexdigest()


def matches(method: str, path: str, contract: dict[str, Any]) -> bool:
    if not isinstance(contract,dict) or method != contract.get('method') or not isinstance(contract.get('path'), str):return False
    pattern=re.sub(r'\\\{[^{}]+\\\}', r'[^/]+', re.escape(urlsplit(contract['path']).path))
    return re.fullmatch(pattern, urlsplit(path).path) is not None


def duplicate_groups(tasks: list[Any]) -> list[list[int]]:
    groups: dict[str,list[int]]={}
    for index,task in enumerate(tasks):
        if isinstance(task,dict):groups.setdefault(task_digest(task),[]).append(index)
    return [indexes for indexes in groups.values() if len(indexes)>1]


def ui_tasks(plan: dict[str, Any]) -> list[int]:
    return [index for index,task in enumerate(plan.get('tasks',[]))
            if UI.search(task_text(task)) or any(str(name).endswith(('.html','.js','.jsx','.tsx')) for name in task.get('files',[]))]


def persistence_features(plan: dict[str, Any]) -> list[int]:
    if not business_checks(plan):return []
    return [index for index,feature in enumerate(plan.get('features',[]))
            if isinstance(feature,str) and PERSISTENCE.search(feature)
            and not re.search(r'localStorage|sessionStorage|indexedDB',feature,re.I)]


def _ordered_arrays(value: Any) -> bool:
    if isinstance(value,list):return len(value)>=2 and value[0]!=value[1]
    return isinstance(value,dict) and any(_ordered_arrays(item) for item in value.values())


def coherence_findings(plan: dict[str, Any], *, outline: bool = False, partial: bool = False) -> list[tuple[str,str,str]]:
    if plan.get('acceptance_policy')!='evidence_v1':return []
    findings: list[tuple[str,str,str]]=[];checks=plan.get('checks',[])
    for feature in persistence_features(plan):
        if not any(check.get('restart_before') and check.get('method')=='GET' and feature in check.get('feature_indexes',[]) for check in checks):
            findings.append(('missing_persistence_scenario','/features/'+str(feature),
                'This feature promises server persistence/restart, but has no mapped GET with restart_before:true reading a seeded value. Correct the unapproved scenario, not the requirement.'))
    for feature,text in enumerate(plan.get('features',[])):
        if not isinstance(text,str) or not ORDERING.search(text):continue
        http=any(feature in check.get('feature_indexes',[]) and _ordered_arrays(check.get('json_equals')) for check in checks)
        manual=any(feature in row.get('feature_indexes',[]) and ORDERING.search(str(row.get('expected','')))
                   and re.search(r'\btwo\b|\b2\b',str(row.get('steps',[])),re.I) for row in plan.get('manual_checks',[]))
        if not http and not manual:
            findings.append(('ordering_scenario','/features/'+str(feature),
                'Ordering needs two distinct seeded records and an order-sensitive json_equals array (json_contains is unordered), or a manual scenario comparing two records in the requested order.'))
    active: dict[tuple[str,str],int]={};ordering_evidence: set[int]=set()
    for index,check in enumerate(checks):
        if not 200<=check['status']<300:continue
        path=urlsplit(check['path']).path;expected=check.get('json_contains',check.get('json_equals',{}))
        if check['method'] in {'POST','PUT','PATCH'}:
            identifier=expected.get('id') if isinstance(expected,dict) else None
            known_id=type(identifier) in {int,str}
            key=(path,'id:'+json.dumps(identifier,sort_keys=True) if known_id else 'unknown:'+str(index))
            if key in active and check['method']=='POST' and check['status']==201 and not (isinstance(check.get('body'),dict) and 'id' in check['body']):
                findings.append(('duplicate_create_id','/checks/'+str(index),
                    'This new-resource POST expects the same ID as an earlier undeleted create in this collection. Use consistent distinct fixture IDs; do not assume each check resets the database.'))
            active[key]=index
        if check['method']=='DELETE':
            parent,_,identifier=path.rpartition('/')
            for key in list(active):
                if key[0]==parent and key[1].startswith('id:') and str(json.loads(key[1][3:]))==identifier:del active[key]
        live=[prior for (collection,_),prior in active.items() if collection==path or path.startswith(collection+'/')]
        if check['method']=='GET' and _ordered_arrays(check.get('json_equals')) and len(live)>=2:
            ordering_evidence.update(check.get('feature_indexes',[]))
        if check.get('restart_before'):
            from .acceptance import scalar_values
            observed=scalar_values(expected)
            if not any(any(type(a) is type(b) and a==b for a in observed for b in scalar_values(checks[prior].get('body',{}))) for prior in live):
                findings.append(('persistence_seed_state','/checks/'+str(index),'The restart read does not assert the currently seeded record values. Preserve scenario state across checks.'))
    for feature,text in enumerate(plan.get('features',[])):
        if isinstance(text,str) and ORDERING.search(text) and feature not in ordering_evidence:
            manual=any(feature in row.get('feature_indexes',[]) and ORDERING.search(str(row.get('expected','')))
                and re.search(r'\btwo\b|\b2\b',str(row.get('steps',[])),re.I) for row in plan.get('manual_checks',[]))
            if not manual and not any(code=='ordering_scenario' and pointer=='/features/'+str(feature) for code,pointer,_ in findings):
                findings.append(('ordering_scenario','/features/'+str(feature),'The ordered comparison needs two distinct live records seeded before its GET. Checks share one evolving scenario.'))
    if outline:return findings
    tasks=plan.get('tasks',[]);routes=[*checks,*plan.get('api_contracts',[])]
    for group in duplicate_groups(tasks):
        for index in group[1:]:findings.append(('duplicate_task','/tasks/'+str(index),
            'This repeats the same instructions, outcome, criteria and files as task '+str(group[0]+1)+'. Plan only the remaining feature work; different feature references do not make duplicate work useful.'))
    for index,task in enumerate(tasks):
        text=task_text(task);endpoints=ENDPOINT.findall(text)
        for method,path in sorted(set(endpoints)):
            path=path.rstrip('.,;')
            if urlsplit(path).path in {'/','/health'} or any(matches(method,path,row) for row in routes):continue
            findings.append(('task_endpoint_mismatch','/tasks/'+str(index),
                'Task endpoint '+method+' '+path+' is absent from the accepted API/check contract. Implement the actual approved routes; do not copy example endpoints.'))
    complete=not partial or set(range(len(plan.get('features',[]))))<={feature for task in tasks for feature in task.get('feature_indexes',[])}
    interactive_manual=any(re.search(r'\b(?:form|button|interface|controls|frontend|ui|canvas)\b',str(row),re.I) for row in plan.get('manual_checks',[]))
    needs_ui=bool(plan.get('browser_checks')) or interactive_manual or plan.get('app_kind')=='browser' and bool(plan.get('manual_checks'))
    if complete and needs_ui and not ui_tasks(plan):
        findings.append(('missing_ui_task','/tasks','Browser actions are required, but no task declares interface work or an HTML/JavaScript file. Assign the real UI before approval.'))
    return findings


def audit_plan(plan: dict[str, Any], starter: str | None = None) -> dict[str, Any]:
    """Recompute current review without source, prompts, sample values or mutation."""
    from .contracts import review_plan
    from . import __version__
    review=review_plan(plan,starter)
    tasks=plan.get('tasks',[]) if isinstance(plan.get('tasks'),list) else []
    return {'available':True,'reviewer_version':__version__,'passed':review.passed,
        'plan_sha256':hashlib.sha256(json.dumps(plan,sort_keys=True).encode()).hexdigest(),
        'review_codes':sorted({finding.code for finding in review.findings}),
        'findings':[{'code':finding.code,'path':finding.path,'severity':finding.severity} for finding in review.findings],
        'restart_check_indexes':[i for i,row in enumerate(plan.get('checks',[]) if isinstance(plan.get('checks'),list) else []) if isinstance(row,dict) and row.get('restart_before') is True],
        'duplicate_task_groups':duplicate_groups(tasks),
        'business_http_checks':len(business_checks(plan)),
        'executed':False,'approval_changed':False}


def guard_probes() -> dict[str, Any]:
    """Small deterministic adversarial controller checks, never a model benchmark."""
    from .contracts import review_plan
    plan: dict[str,Any]={'title':'Fixed guard probe','summary':'Synthetic local review only.',
        'features':['Persist records across server restart','Browser interface'],
        'out_of_scope':[],'risks':[],'app_kind':'browser','acceptance_policy':'evidence_v1',
        'task_contract_version':1,'context_policy':'focused_v1',
        'checks':[{'name':'Create record','method':'POST','path':'/api/records','status':201,
                   'body':{'title':'Probe one'},'json_contains':{'id':1,'title':'Probe one'},'feature_indexes':[0]},
                  {'name':'Read records','method':'GET','path':'/api/records','status':200,
                   'restart_before':True,'json_contains':[{'id':1,'title':'Probe one'}],'feature_indexes':[0]}],
        'api_contracts':[{'method':'POST','path':'/api/records','status':201,'response_kind':'object','required_fields':['id','title']},
                         {'method':'GET','path':'/api/records','status':200,'response_kind':'array','required_fields':['id','title']}],
        'manual_checks':[{'name':'Browser controls','steps':['Add a record through the form.'],'expected':'The record is visible.','feature_indexes':[1]}],
        'tasks':[{'title':'Implement storage API','instructions':'Implement POST /api/records and GET /api/records with SQLite storage and tests.',
                  'outcome':'A saved record survives server restart.','files':['app.py','test_app.py'],'depends_on':[],
                  'done_when':['POST and GET preserve the saved record.'],'feature_indexes':[0],'check_indexes':[1]},
                 {'title':'Build interface','instructions':'Implement an HTML form and record list.',
                  'outcome':'Browser controls use the saved-record API.','files':['index.html'],'depends_on':[0],
                  'done_when':['The form adds a visible record.'],'feature_indexes':[1]}]}
    cases: list[tuple[str,dict[str,Any],set[str]]]=[('valid_hybrid',plan,set())]
    bad=copy.deepcopy(plan);bad['tasks'][0]['outcome']='POST /api/wrong creates records.'
    cases.append(('wrong_endpoint',bad,{'task_endpoint_mismatch'}))
    bad=copy.deepcopy(plan);bad['tasks'].append(copy.deepcopy(bad['tasks'][0]));bad['tasks'][-1]['depends_on']=[1]
    cases.append(('duplicate_work',bad,{'duplicate_task'}))
    bad=copy.deepcopy(plan);bad['checks'][1].pop('restart_before')
    cases.append(('missing_restart',bad,{'missing_persistence_scenario'}))
    bad=copy.deepcopy(plan);bad['checks'].insert(1,copy.deepcopy(bad['checks'][0]));bad['tasks'][0]['check_indexes']=[2]
    cases.append(('repeated_create_id',bad,{'duplicate_create_id'}))
    bad=copy.deepcopy(plan);bad['tasks'][1].update(title='Check timestamps',instructions='Add timestamp tests.',outcome='Timestamps are correct.',files=['test_dates.py'],done_when=['Timestamp tests pass.'])
    cases.append(('missing_ui',bad,{'missing_ui_task'}))
    bad=copy.deepcopy(plan);bad['tasks'][0].pop('check_indexes')
    cases.append(('missing_backend_checkpoint',bad,{'missing_milestone'}))
    bad=copy.deepcopy(plan);bad['features'][0]+='; list newest first'
    cases.append(('unordered_subset',bad,{'ordering_scenario'}))
    rows=[]
    for code,candidate,expected in cases:
        review=review_plan(candidate);observed={finding.code for finding in review.findings}
        passed=review.passed if not expected else not review.passed and expected<=observed
        rows.append({'code':code,'passed':passed,'expected_codes':sorted(expected),'observed_codes':sorted(observed)})
    return {'status':'passed' if all(row['passed'] for row in rows) else 'failed','case_count':len(rows),'cases':rows,'executed':False}
