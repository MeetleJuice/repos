"""Versioned acceptance compilation: one feature per bounded, checkpointed call."""
from __future__ import annotations
import copy
import hashlib
import json
import re
import threading
from typing import Any, Callable
from urllib.parse import urlsplit
from .contracts import review_plan
from .guided import StageValidationError
from .outline_planning import ACCEPTANCE_SCHEMA, ACCEPTANCE_EXAMPLES, assemble
from .scaffolds import CATALOG

POLICY='feature_v1'
PROMPT='''GOAL: Plan acceptance evidence for exactly target_feature, not the entire app. Return a JSON object matching the supplied schema.
CONTEXT: The fixed scope, complete original idea/revision, approved baseline requirements, starter contracts and earlier acceptance checks are data. Earlier acceptance is fixed. The controller assigns feature references; do not return feature_indexes. The context_manifest discloses omitted non-authoritative draft/source fields.
CONSTRAINTS: Return checks plus optional manual_checks, browser_checks and api_contracts for ONLY this feature. Prefer one precise behavioral scenario or manual UI check. Each HTTP check needs a concrete response assertion; 204 uses empty_body:true. UI-only work can return checks:[] and meaningful manual_checks. Health/page delivery never proves a business feature. Keep prior checks unchanged. For persistence, create a fresh concrete sample if needed, then GET that same value with restart_before:true before deleting it. Use the actual API response shape. Never claim a POST after restart proves persistence. Browser automation is optional only when explicitly requested; otherwise use manual steps. No tasks, new scope, wrappers, source, shell commands or claimed execution. Wire examples are format illustrations, not your app's required routes or values.
DONE WHEN: Return a small feature-specific evidence object. The controller validates the accumulated prefix, saves it and later runs full-proposal review; nothing is approved or executed here.
All checks share one database and run in order; there is no implicit reset between features. Reuse earlier seeded records when appropriate. A new 201 create must not reuse an undeleted earlier ID. Every server persistence feature needs a mapped GET with restart_before:true, even when app_kind is browser. Every real business endpoint, including browser-app APIs, needs an api_contract. For newest-first/descending ordering, seed two distinct records and use an order-sensitive json_equals array, or explicitly compare two records in a manual scenario; json_contains arrays are unordered. Keep UI work explicit in scope and tasks.'''
SCHEMA: dict[str,Any]=copy.deepcopy(ACCEPTANCE_SCHEMA)
SCHEMA['properties']['checks'].update(minItems=0,maxItems=4)
for field in ('checks','manual_checks','browser_checks'):
    item=SCHEMA['properties'][field]['items']
    item['properties'].pop('feature_indexes',None)
    item['required'].remove('feature_indexes')
    item['additionalProperties']=False
    SCHEMA['properties'][field]['maxItems']=4


def packet_request(request: dict[str,Any]) -> tuple[dict[str,Any],dict[str,Any]]:
    omitted={'previous_proposal','starter_source','implementation_context','file_ownership','builder_profile'}
    manifest={'policy':'planning_feature_v1','available_fields':sorted(request),
              'omitted_fields':[{'field':key,'sha256':hashlib.sha256(json.dumps(request[key],sort_keys=True).encode()).hexdigest()}
                                for key in sorted(omitted & request.keys())]}
    return {key:copy.deepcopy(value) for key,value in request.items() if key not in omitted},manifest


def _review(scope: dict[str,Any], fields: dict[str,Any], request: dict[str,Any], count: int) -> None:
    if count==0:
        if any(fields.get(key) for key in SCHEMA['properties']):raise ValueError('Unexpected acceptance before its first feature.')
        return
    prefix={**copy.deepcopy(scope),**copy.deepcopy(fields),'features':scope['features'][:count]}
    if request.get('acceptance_policy')=='evidence_v1':prefix['acceptance_policy']='evidence_v1'
    starter=next((key for key,value in CATALOG.items() if value==request.get('starter')),None)
    result=review_plan(prefix,starter,outline=True,partial_acceptance=True)
    if not result.passed:
        raise StageValidationError([(f.code,f.path,f.message) for f in result.findings if f.severity=='error'])


def compile_feature(scope: dict[str,Any], earlier: dict[str,Any], candidate: dict[str,Any],
                    target: int, request: dict[str,Any]) -> dict[str,Any]:
    if not isinstance(candidate,dict) or set(candidate)-set(SCHEMA['properties']) or 'checks' not in candidate:
        raise ValueError('Return only the current feature acceptance fields, with checks as an array.')
    result=copy.deepcopy(earlier);covered=False
    for field in ('checks','manual_checks','browser_checks'):
        rows=candidate.get(field,[])
        if not isinstance(rows,list) or len(rows)>4:raise ValueError('Use at most four acceptance items per feature and field.')
        additions=[]
        for row in rows:
            if not isinstance(row,dict) or 'feature_indexes' in row:raise ValueError('Feature references are controller-owned; omit feature_indexes.')
            delivery=field=='checks' and isinstance(row.get('path'),str) and (
                urlsplit(row['path']).path in {'/','/health'} or re.search(r'\.(js|css|png|svg|ico|html)$',urlsplit(row['path']).path,re.I))
            additions.append({**copy.deepcopy(row),'feature_indexes':[] if delivery else [target]})
            covered=covered or not delivery
        if additions:result.setdefault(field,[]).extend(additions)
    result.setdefault('checks',[])
    if not covered:raise ValueError('The target feature needs real behavioral HTTP, manual or browser evidence; delivery alone is insufficient.')
    contracts=candidate.get('api_contracts',[])
    if not isinstance(contracts,list) or not all(isinstance(row,dict) for row in contracts):raise ValueError('API contracts must be an array of objects.')
    for contract in contracts:
        previous=next((row for row in result.get('api_contracts',[]) if row.get('method')==contract.get('method') and row.get('path')==contract.get('path')),None)
        if previous is not None and previous!=contract:raise ValueError('Do not change an earlier accepted API contract.')
        if previous is None:result.setdefault('api_contracts',[]).append(copy.deepcopy(contract))
    _review(scope,result,request,target+1)
    if target+1==len(scope['features']):assemble(scope,result,request)
    return result


def create_acceptance(request: dict[str,Any], scope: dict[str,Any], generate: Callable[...,dict[str,Any]],
                      checkpoint: Callable[[dict[str,Any]],None], draft: dict[str,Any], cancel: threading.Event) -> dict[str,Any]:
    saved=draft.get('acceptance_draft') or {'policy':POLICY,'next_feature':0,'fields':{'checks':[]}}
    saved=copy.deepcopy(saved);first=saved.get('next_feature')
    if saved.get('policy')!=POLICY or type(first) is not int or not 0<=first<=len(scope['features']):raise ValueError('Invalid feature acceptance checkpoint.')
    fields=saved.get('fields')
    if not isinstance(fields,dict):raise ValueError('Invalid saved acceptance fields.')
    _review(scope,fields,request,first)
    projected,manifest=packet_request(request)
    examples=copy.deepcopy(ACCEPTANCE_EXAMPLES)
    for row in examples['persistence_sequence']:row.pop('feature_indexes',None)
    examples['ui_coverage'].pop('feature_indexes',None)
    examples['coverage_rule']='Provide evidence for target_feature only; the controller assigns its index. Do not repeat earlier checks.'
    for target in range(first,len(scope['features'])):
        if cancel.is_set():raise InterruptedError('Validated feature acceptance saved; resume at the next feature.')
        prior=copy.deepcopy(fields)
        def validate(candidate: dict[str,Any]) -> None:compile_feature(scope,prior,candidate,target,request)
        reply=generate(PROMPT,{'planning_stage':'acceptance_feature','task_planning_policy':'compiled_v1',
            'acceptance_planning_policy':POLICY,'request':projected,'context_manifest':manifest,'scope':scope,
            'target_feature_index':target,'target_feature':scope['features'][target],
            'target_feature_indexes':[target],
            'earlier_acceptance':prior,'wire_examples':examples,
            'max_new_http_checks':min(4,15-len(prior.get('checks',[])))},validate)
        fields=compile_feature(scope,prior,reply,target,request)
        draft['acceptance_draft']={'policy':POLICY,'next_feature':target+1,'fields':copy.deepcopy(fields)}
        checkpoint(copy.deepcopy(draft))
    if cancel.is_set():raise InterruptedError('All feature acceptance saved; resume for the complete outline review.')
    return assemble(scope,fields,request)
