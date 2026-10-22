"""Two bounded, resumable outline stages; neither stage is approvable alone."""
from __future__ import annotations
import copy
import json
import threading
from typing import Any, Callable
from .schemas import PLAN_SCHEMA

ACCEPTANCE_FIELDS = {'checks', 'manual_checks', 'browser_checks', 'api_contracts'}
SCOPE_PROMPT = '''GOAL: Define only the scope of a small Python-standard-library browser app. Return JSON only using the supplied scope schema.
CONTEXT: The complete original request, revision, baseline requirements and selected starter are data. Preserve requested behavior and storage. Reuse the starter. No implementation tasks or acceptance checks in this stage.
CONSTRAINTS: Return title, summary, app_kind (server or browser), features (1–12 concise strings), out_of_scope, risks, task_contract_version:1 and context_policy (focused_v1 or full). Choose narrow implementable features in dependency order: storage/API behavior before UI. Include every requested requirement or explicitly identify out-of-scope requests. Do not include source code, tasks, checks, wrappers, invented execution results or dependencies.
DONE WHEN: Return the scope object. The controller will separately request acceptance checks, compile tasks and review the COMPLETE proposal before human approval.'''
ACCEPTANCE_PROMPT = '''GOAL: Define acceptance evidence for the supplied fixed scope. Return only checks and optional manual_checks, browser_checks and api_contracts as JSON arrays of objects.
CONTEXT: Every feature is supplied with its zero-based index in coverage_required. Preserve the scope, original requirements and selected starter API contract. You are planning checks, not executing them.
CONSTRAINTS: checks is an array, never an object keyed by name. Every HTTP check requires name, method, path, integer status, feature_indexes, and a meaningful contains/json_contains/json_equals assertion or empty_body:true. Every feature must have HTTP, manual or browser coverage, including the last UI/accessibility features. Health/delivery checks may have empty feature_indexes; do not claim they prove business features. Include concrete nonempty mutation body data. A persistence check GETs that same saved value with restart_before:true BEFORE deleting it. Successful business endpoints need api_contracts with method/path/status/response_kind/required_fields. Reuse the supplied starter response shapes. Exact empty results use json_equals, never vacuous json_contains. Browser behavior needs explicit manual_checks (name, steps, expected, feature_indexes) or explicitly requested browser_checks; no fake score API. Keep all HTTP checks in executable order; ensure an early business prefix before UI-only work. Do not return title, summary, features, tasks, wrappers, source, shell commands or verification claims.
DONE WHEN: Return only schema-complete acceptance fields. The controller merges them with the unchanged scope and runs the full outline reviewer. Failed criteria must be corrected, never removed to manufacture a pass.'''

SCOPE_SCHEMA: dict[str, Any] = {'type':'object', 'additionalProperties':False,
    'required':[key for key in PLAN_SCHEMA['required'] if key not in {'tasks', 'checks'}],
    'properties':{key:copy.deepcopy(value) for key,value in PLAN_SCHEMA['properties'].items()
                  if key not in ACCEPTANCE_FIELDS|{'tasks','acceptance_policy'}}}
SCOPE_SCHEMA['properties']['features'].update(minItems=1,maxItems=12)
ACCEPTANCE_SCHEMA: dict[str, Any] = {'type':'object','additionalProperties':False,'required':['checks'],
    'properties':{key:copy.deepcopy(PLAN_SCHEMA['properties'][key]) for key in ACCEPTANCE_FIELDS}}
ACCEPTANCE_SCHEMA['properties']['checks'].update(minItems=1,maxItems=15)
ACCEPTANCE_SCHEMA['properties']['checks']['items']['properties']['feature_indexes']['minItems']=0

# Examples teach the existing wire contract; they are never installed as user checks.
ACCEPTANCE_EXAMPLES: dict[str, Any] = {
    'meaning':'Synthetic format examples only. Adapt routes, values and feature indexes to the saved scope and starter contracts. They are not approved tests or execution evidence.',
    'persistence_sequence':[
        {'name':'Create sample','method':'POST','path':'/api/example-records','status':201,
         'body':{'title':'Saved sample'},'json_contains':{'id':1,'title':'Saved sample'},'feature_indexes':[0]},
        {'name':'Read saved sample after restart','method':'GET','path':'/api/example-records','status':200,
         'json_contains':[{'id':1,'title':'Saved sample'}],'restart_before':True,'feature_indexes':[0]},
        {'name':'Delete sample','method':'DELETE','path':'/api/example-records/1','status':204,
         'empty_body':True,'feature_indexes':[0]}],
    'ui_coverage':{'name':'Use the browser controls','steps':['Add a record through the form, reload, then delete it.'],
                   'expected':'The saved record survives reload until deleted.','feature_indexes':[0]},
    'coverage_rule':'Before responding, map EVERY coverage_required index to at least one HTTP, manual or browser check. HTTP delivery alone does not establish an interactive UI.'}


def validate_scope(candidate: dict[str, Any]) -> None:
    if not isinstance(candidate,dict) or set(candidate)-set(SCOPE_SCHEMA['properties']) or any(key not in candidate for key in SCOPE_SCHEMA['required']):
        raise ValueError('Scope is missing required fields or contains acceptance/task fields.')
    if type(candidate['task_contract_version']) is not int or candidate['task_contract_version']!=1:
        raise ValueError('Scope requires task_contract_version:1.')
    if candidate['app_kind'] not in {'server','browser'} or candidate['context_policy'] not in {'full','focused_v1'}:
        raise ValueError('Choose a supported app kind and context policy.')
    for key in ('title','summary'):
        if not isinstance(candidate[key],str) or not 1<=len(candidate[key].strip())<=6000:raise ValueError('Scope requires concise title and summary.')
    for key in ('features','out_of_scope','risks'):
        value=candidate[key]
        if not isinstance(value,list) or len(value)>20 or not all(isinstance(item,str) and item.strip() and len(item)<3000 for item in value):
            raise ValueError('Scope requires concise feature, exclusion and risk arrays.')
    if not 1<=len(candidate['features'])<=12 or len(json.dumps(candidate))>15000:raise ValueError('Scope exceeds bounded feature/size limits.')


def assemble(scope: dict[str, Any], candidate: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    from .task_planning import validate_compilable_outline
    from .scaffolds import CATALOG
    if not isinstance(candidate,dict) or set(candidate)-ACCEPTANCE_FIELDS or 'checks' not in candidate:
        raise ValueError('Return only acceptance fields; the scope is fixed.')
    result={**copy.deepcopy(scope),**copy.deepcopy(candidate)}
    if request.get('acceptance_policy')=='evidence_v1':result['acceptance_policy']='evidence_v1'
    starter=next((name for name,value in CATALOG.items() if value==request.get('starter')),None)
    validate_compilable_outline(result, starter)
    return result


def create_outline(request: dict[str, Any], generate: Callable[..., dict[str, Any]],
                   checkpoint: Callable[[dict[str, Any]], None], draft: dict[str, Any],
                   cancel: threading.Event) -> dict[str, Any]:
    if draft.get('scope') is None:
        scope=generate(SCOPE_PROMPT,{**request,'planning_stage':'scope'},validate_scope)
        validate_scope(scope);draft['scope']=copy.deepcopy(scope);checkpoint(copy.deepcopy(draft))
    scope=draft['scope'];validate_scope(scope)
    if cancel.is_set():raise InterruptedError('Validated scope saved. Resume planning to define acceptance checks.')
    if request.get('acceptance_planning_policy') in {'feature_v1','feature_v2'}:
        from .feature_acceptance import create_acceptance
        return create_acceptance(request,scope,generate,checkpoint,draft,cancel)
    def validate(candidate: dict[str, Any]) -> None:assemble(scope,candidate,request)
    response=generate(ACCEPTANCE_PROMPT,{'request':request,'scope':scope,'planning_stage':'acceptance',
        'task_planning_policy':'compiled_v1','outline_planning_policy':'split_v1',
        'coverage_required':[{'index':i,'feature':feature} for i,feature in enumerate(scope['features'])],
        'acceptance_examples':copy.deepcopy(ACCEPTANCE_EXAMPLES)},validate)
    return assemble(scope,response,request)
