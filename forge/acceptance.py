"""Opt-in evidence-ready proposal policy; never mutate approved legacy checks."""
from __future__ import annotations
from typing import Any
from urllib.parse import urlsplit

POLICY='evidence_v1'
GUIDANCE='''Evidence-ready planning policy evidence_v1: declare stable api_contracts for every successful business HTTP endpoint (method/path/status/response_kind/required_fields). Every successful POST/PUT/PATCH check needs concrete nonempty JSON body example data; a deliberately bodyless endpoint needs a request_body_optional_reason explaining its contract. json_contains must contain a real scalar assertion, never only empty lists/objects. Exact empty-state checks may use json_equals:[] or {}. A restart_before check must read a concrete value created by an earlier successful mutation of that collection before deletion; checking health or empty lists is not persistence proof. Assign check_indexes to the earliest fully implemented tasks so the ordered prefix can execute before later work. Cover every HTTP check, and for multi-task server apps include a business check before the final task. Only execution consent permits actual milestone checks. Keep response shapes/IDs consistent across create, read, delete and tests. Database/table initialization and row mapping belong in the initial storage setup, not later persistence polish. Do not count a model summary as proof.'''


def scalar_values(value: Any) -> list[Any]:
    pending=[value];values=[]
    while pending:
        item=pending.pop()
        if isinstance(item,dict):pending.extend(item.values())
        elif isinstance(item,list):pending.extend(item)
        else:values.append(item)
    return values


def evidence_findings(plan: dict[str,Any], *, outline: bool = False, partial: bool = False) -> list[tuple[str,str,str]]:
    if plan.get('acceptance_policy')!=POLICY:return []
    from .contracts import _matches
    findings=[];checks=plan.get('checks',[])
    for index,check in enumerate(checks):
        pointer='/checks/'+str(index)
        if 'json_contains' in check and not scalar_values(check['json_contains']):
            findings.append(('vacuous_assertion',pointer,'json_contains has only empty containers and proves no saved value. Assert actual record values, or use json_equals for an intentionally exact empty result.'))
        success=200<=check['status']<300
        sample_values=scalar_values(check.get('body',{}))
        meaningful_sample=any(value is not None and (not isinstance(value,str) or bool(value.strip())) for value in sample_values)
        if success and check['method'] in {'POST','PUT','PATCH'} and not meaningful_sample:
            reason=check.get('request_body_optional_reason')
            if not isinstance(reason,str) or not 20<=len(reason.strip())<=500:
                findings.append(('mutation_example',pointer,'Supply concrete nonempty JSON request example data; for a deliberately bodyless endpoint explain request_body_optional_reason (20–500 characters).'))
        path=urlsplit(check['path']).path
        if success and plan.get('app_kind')!='browser' and path not in {'/','/health'}:
            candidates=[c for c in plan.get('api_contracts',[]) if isinstance(c,dict) and isinstance(c.get('path'),str) and c.get('method')==check['method'] and c.get('status')==check['status']]
            if not any(_matches(c,check) for c in candidates):
                findings.append(('missing_api_contract',pointer,'Declare the successful endpoint response shape in api_contracts; reuse it across task interfaces and tests.'))
        if check.get('restart_before'):
            observed=scalar_values(check.get('json_contains',check.get('json_equals',{})))
            if isinstance(check.get('contains'),str):observed.append(check['contains'])
            seeds=[value for prior in checks[:index] if prior['method'] in {'POST','PUT','PATCH'} and 200<=prior['status']<300 and (path==urlsplit(prior['path']).path or path.startswith(urlsplit(prior['path']).path.rstrip('/')+'/')) for value in scalar_values(prior.get('body',{})) if value is not None and value!='']
            if check['method']!='GET' or not any(type(a) is type(b) and a==b for a in observed for b in seeds):
                findings.append(('persistence_evidence',pointer,'Restart checks must GET a concrete value created by an earlier successful request to this collection. Health or empty data does not prove persistence.'))
    if not outline and plan.get('app_kind')!='browser':
        tasks=plan.get('tasks',[]);covered: set[int]=set();early=False
        producers={feature:index for index,task in enumerate(tasks) for feature in task.get('feature_indexes',[])}
        prefix_ready=0 if tasks else -1;missing=False
        for check_index,check in enumerate(checks):
            if partial and any(feature not in producers for feature in check.get('feature_indexes',[])):break
            prefix_ready=max(prefix_ready,max((producers.get(feature,-1) for feature in check.get('feature_indexes',[])),default=-1))
            assigned=tasks[prefix_ready].get('check_indexes',[]) if 0<=prefix_ready<len(tasks) else []
            if not assigned or max(assigned)<check_index:missing=True
        for index,task in enumerate(tasks):
            declared=task.get('check_indexes',[])
            if declared:
                needed={feature for check in checks[:max(declared)+1] for feature in check.get('feature_indexes',[])}
                if any(feature not in producers or producers[feature]>index for feature in needed):
                    findings.append(('premature_milestone','/tasks/'+str(index)+'/check_indexes','This checkpoint includes declared feature work from a later task. Schedule the prefix only after its prerequisites are implemented.'))
                covered.update(range(max(declared)+1))
                if index<len(tasks)-1 and any(urlsplit(c['path']).path not in {'/','/health'} for c in checks[:max(declared)+1]):early=True
        if missing or not partial and (set(range(len(checks)))-covered or plan.get('app_kind')!='browser' and len(tasks)>1 and not early):
            findings.append(('missing_milestone','/tasks','Assign each runnable HTTP prefix using check_indexes to the task that last implements its declared features, including a business check before the final server-app task. Do not defer ready checks to later work; saved criteria alone are not behavior evidence.'))
    return findings
