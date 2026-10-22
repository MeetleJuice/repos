"""Explicit, fixed planner-stage probe. Never uses a user's project or executes code."""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
from typing import Any
from .capabilities import CapabilityRegistry
from .feature_acceptance import WIRE_PROMPT, WIRE_SCHEMA, compile_feature
from .assertions import compile_wire
from .guided import stage_review
from .models import ModelClient, ModelError, output_contract
from .planning_diagnostics import candidate_shape
from .routing import validate_options

SCOPE: dict[str, Any] = {'title':'Diagnostic records','summary':'Create a record with a title.',
    'app_kind':'server','features':['Create a record with a nonempty title'], 'out_of_scope':[], 'risks':[],
    'task_contract_version':1,'context_policy':'focused_v1'}


def probe_payload() -> dict[str, Any]:
    return {'planning_stage':'acceptance_feature','task_planning_policy':'compiled_v1',
            'acceptance_planning_policy':'feature_v2','scope':copy.deepcopy(SCOPE),
            'target_feature_index':0,'target_feature':SCOPE['features'][0], 'earlier_acceptance':{'checks':[]},
            'request':{'idea':'Create one diagnostic record with title Diagnostic sample; POST /api/records returns 201 and its id/title JSON.'},
            'wire_examples':{'assertion':{'kind':'json_subset','expected':{'id':1,'title':'Diagnostic sample'}}}}


def run_probe(client: Any, provider: str, model: str, target: dict[str,Any], registry_path: Path) -> dict[str, Any]:
    payload=probe_payload();prompt=json.dumps(payload)
    reservation: dict[str,Any]={}
    if isinstance(client, ModelClient):
        client.options=validate_options({**target.get('options',{}),'timeout_seconds':120})
        try:
            client.planner_budget=CapabilityRegistry(registry_path).reserve(provider,model,dict(client.options),output_contract(WIRE_PROMPT),prompt)
        except ValueError as exc:
            raise ModelError('Fixed planning probe does not fit the configured output/context reservation.',category='output_budget') from exc
        reservation={'reserved_text_output_tokens':client.planner_budget.text_output_tokens,
                     'thinking_budget':client.planner_budget.thinking_budget,
                     'input_estimate_tokens':client.planner_budget.input_estimate_tokens}
    try:
        result=client.complete(WIRE_PROMPT,prompt)
    except ModelError:
        raise
    def validate(candidate: dict[str,Any]) -> None:
        compile_feature(SCOPE,{'checks':[]},compile_wire(candidate),0,{})
    _,review=stage_review(validate,result)
    return {'status':'passed' if review.passed else 'failed','provider':provider,'model':model,
            'failure_class':None if review.passed else 'schema_error','response_received':True,
            'response_accepted':review.passed,'review_codes':[f.code for f in review.findings],
            'review_findings':[{'code':f.code,'path':f.path} for f in review.findings],
            'candidate_shape':candidate_shape(result),'schema_version':2,
            'schema_sha256':hashlib.sha256(json.dumps(WIRE_SCHEMA,sort_keys=True).encode()).hexdigest(),
            'request_sha256':hashlib.sha256(prompt.encode()).hexdigest(),
            'request_characters':len(prompt),'generated_code_executed':False,'project_content_sent':False,
            **reservation,
            **getattr(client,'last_usage',{}),
            **{key:value for key,value in getattr(client,'last_metadata',{}).items() if key in {
                'configured_num_ctx','requested_max_output_tokens','reserved_text_output_tokens','observed_output_tokens',
                'timeout_seconds','finish_reason','transport_attempted','ollama_load_seconds','ollama_eval_seconds',
                'ollama_tokens_per_second','api_family','response_format_mode'}}}
