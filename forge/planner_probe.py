"""Explicit, fixed planner-stage probe. Never uses a user's project or executes code."""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
from typing import Any
from .capabilities import CapabilityRegistry
from .feature_acceptance import WIRE_PROMPT, WIRE_SCHEMA, MEMORY_PROMPT, compile_feature
from .assertions import compile_wire
from .guided import stage_review
from .models import ModelClient, ModelError, output_contract
from .planning_diagnostics import candidate_shape
from .routing import validate_options

SCOPE: dict[str, Any] = {'title':'Diagnostic records','summary':'Create a record with a title.',
    'app_kind':'server','features':['Create a record with a nonempty title'], 'out_of_scope':[], 'risks':[],
    'task_contract_version':1,'context_policy':'focused_v1'}


def probe_payload(version: int=1) -> dict[str, Any]:
    if version==2:
        from .scaffolds import CATALOG
        from .stage_context import seed_contracts,project_memory,stage_examples
        request={'idea':'Create one diagnostic record with title Diagnostic sample; POST /api/records returns 201 with id/title JSON.',
                 'starter':CATALOG['sqlite'],'acceptance_policy':'evidence_v1',
                 'planning_context_policy':'stage_v1','acceptance_planning_policy':'feature_v3'}
        earlier=seed_contracts({'checks':[]},request)
        return {'planning_stage':'acceptance_feature','task_planning_policy':'compiled_v1',
                'planning_context_policy':'stage_v1','acceptance_planning_policy':'feature_v3',
                'scope':copy.deepcopy(SCOPE),'target_feature_index':0,'target_feature':SCOPE['features'][0],
                'earlier_acceptance':earlier,'planning_memory':project_memory(request,SCOPE,earlier,0),
                'request':request,'wire_examples':stage_examples(request)}
    return {'planning_stage':'acceptance_feature','task_planning_policy':'compiled_v1',
            'acceptance_planning_policy':'feature_v2','scope':copy.deepcopy(SCOPE),
            'target_feature_index':0,'target_feature':SCOPE['features'][0], 'earlier_acceptance':{'checks':[]},
            'request':{'idea':'Create one diagnostic record with title Diagnostic sample; POST /api/records returns 201 and its id/title JSON.'},
            'wire_examples':{'assertion':{'kind':'json_subset','expected':{'id':1,'title':'Diagnostic sample'}}}}


def run_probe(client: Any, provider: str, model: str, target: dict[str,Any], registry_path: Path, *, version: int=1) -> dict[str, Any]:
    payload=probe_payload(version);prompt=json.dumps(payload)
    system=MEMORY_PROMPT if version==2 else WIRE_PROMPT
    reservation: dict[str,Any]={}
    if isinstance(client, ModelClient):
        client.options=validate_options({**target.get('options',{}),'timeout_seconds':120})
        try:
            client.planner_budget=CapabilityRegistry(registry_path).reserve(provider,model,dict(client.options),output_contract(system),prompt,contract_system=system if version==2 else None)
        except ValueError as exc:
            from .capabilities import BudgetError
            if isinstance(exc,BudgetError):client.last_metadata.update(exc.facts)
            raise ModelError('Fixed planning probe does not fit the configured output/context reservation.',category='output_budget') from exc
        reservation={'reserved_text_output_tokens':client.planner_budget.text_output_tokens,
                     'thinking_budget':client.planner_budget.thinking_budget,
                     'input_estimate_tokens':client.planner_budget.input_estimate_tokens}
    try:
        result=client.complete(system,prompt)
    except ModelError:
        raise
    def validate(candidate: dict[str,Any]) -> None:
        canonical=compile_wire(candidate)
        compile_feature(SCOPE,payload.get('earlier_acceptance',{'checks':[]}),canonical,0,payload.get('request',{}) if version==2 else {})
        if version==2 and not any(c.get('method')=='POST' and c.get('path')=='/api/records' and c.get('status')==201
                                 and isinstance(c.get('body'),dict) and c['body'].get('title')=='Diagnostic sample'
                                 and isinstance(c.get('json_contains',c.get('json_equals')),dict)
                                 and c.get('json_contains',c.get('json_equals',{})).get('title')=='Diagnostic sample' for c in canonical['checks']):
            from .guided import StageValidationError
            raise StageValidationError([('probe_mutation_required','/checks','The create-record probe requires a concrete POST body and assertion of its saved title.')])
    _,review=stage_review(validate,result)
    return {'status':'passed' if review.passed else 'failed','provider':provider,'model':model,
            'failure_class':None if review.passed else 'schema_error','response_received':True,
            'response_accepted':review.passed,'review_codes':[f.code for f in review.findings],
            'review_findings':[{'code':f.code,'path':f.path} for f in review.findings],
            'candidate_shape':candidate_shape(result),'schema_version':3 if version==2 else 2,'probe_version':version,
            'schema_sha256':hashlib.sha256(json.dumps(WIRE_SCHEMA,sort_keys=True).encode()).hexdigest(),
            'request_sha256':hashlib.sha256(prompt.encode()).hexdigest(),
            'request_characters':len(prompt),'generated_code_executed':False,'project_content_sent':False,
            **reservation,
            **getattr(client,'last_usage',{}),
            **{key:value for key,value in getattr(client,'last_metadata',{}).items() if key in {
                'configured_num_ctx','requested_max_output_tokens','reserved_text_output_tokens','observed_output_tokens',
                'timeout_seconds','finish_reason','transport_attempted','ollama_load_seconds','ollama_eval_seconds',
                'ollama_tokens_per_second','api_family','response_format_mode'}}}
