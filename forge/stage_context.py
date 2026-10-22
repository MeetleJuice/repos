"""Versioned stage context and project-local declarative memory. No inference/tools."""
from __future__ import annotations
import copy
import ast
import hashlib
import json
from typing import Any
from urllib.parse import urlsplit
from .contracts import starter_contracts
from .scaffolds import CATALOG

POLICY='stage_v1'


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=True).encode()).hexdigest()


def project_request(request: dict[str,Any], stage: str) -> tuple[dict[str,Any],dict[str,Any]]:
    """Defer controller scaffolding, never original user/baseline values.

    The complete request remains the checkpoint identity. The omission manifest
    discloses every deferred field; this is not lossy source summarization.
    """
    omitted={'previous_proposal','file_ownership','implementation_context','builder_profile','starter_source','evidence_requirements'}
    if stage in {'scope','acceptance_feature'}:omitted.add('planning_interfaces')
    projected={key:copy.deepcopy(value) for key,value in request.items() if key not in omitted}
    manifest={'policy':POLICY,'stage':stage,'request_sha256':digest(request),'available_fields':sorted(request),
              'included_fields':sorted(projected),'omitted_fields':[
                  {'field':key,'sha256':digest(request[key]),'characters':len(json.dumps(request[key])),
                   'reason':'Deferred controller context; original requirements and baseline stay included.'}
                  for key in sorted(omitted & request.keys())]}
    return projected,manifest


def interface_index(files: dict[str,str]) -> dict[str,Any]:
    """Inspect static Python declarations without importing generated modules."""
    rows=[]
    for name,text in sorted(files.items())[:32]:
        row: dict[str,Any]={'file':name,'sha256':hashlib.sha256(text.encode()).hexdigest(),'symbols':[]}
        if name.endswith('.py'):
            try:tree=ast.parse(text)
            except (ValueError,SyntaxError,RecursionError):row['parse_status']='unavailable'
            else:
                definitions=[node.name for node in tree.body if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)) and not node.name.startswith('_')]
                row.update(symbols=definitions[:32],symbols_omitted=max(0,len(definitions)-32),parse_status='parsed')
        rows.append(row)
    return {'schema':1,'files':rows,'files_omitted':max(0,len(files)-32),
            'meaning':'Observed top-level source declarations only. No code executed; symbols do not prove behavior.'}


def builder_contract(profile: dict[str,Any]) -> dict[str,Any]:
    result={key:copy.deepcopy(profile[key]) for key in ('schema','max_editable_files','max_feature_indexes',
        'target_changed_lines','smallest_output_ceiling','available_files','protected_existing_files') if key in profile}
    result['models']=[{key:copy.deepcopy(row[key]) for key in ('provider','model','configured_output_tokens',
        'effective_output_ceiling','context_tokens','estimated') if key in row} for row in profile.get('models',[])]
    result['profile_sha256']=digest(profile)
    return result


def api_registry(request: dict[str,Any]) -> list[dict[str,Any]]:
    """Reviewed starter defaults plus explicit approved-baseline declarations.

    Never infer contracts from a rejected check or call a model to fill them in.
    These are planning declarations, not evidence of implementation.
    """
    starter=next((key for key,value in CATALOG.items() if value==request.get('starter')),None)
    registry=starter_contracts(starter)
    baseline=request.get('existing_project')
    entries=baseline.get('api_contracts',[]) if isinstance(baseline,dict) else []
    for entry in entries if isinstance(entries,list) else []:
        if not isinstance(entry,dict):raise ValueError('Approved baseline API contracts must be objects.')
        key=(entry.get('method'),entry.get('path'))
        registry=[row for row in registry if (row['method'],row['path'])!=key]+[copy.deepcopy(entry)]
    return copy.deepcopy(registry)


def seed_contracts(fields: dict[str,Any], request: dict[str,Any]) -> dict[str,Any]:
    result=copy.deepcopy(fields)
    declared=result.setdefault('api_contracts',[])
    if not isinstance(declared,list):raise ValueError('API contracts must be an array.')
    keys={(row.get('method'),row.get('path')) for row in declared if isinstance(row,dict)}
    result['api_contracts']=[row for row in api_registry(request) if (row['method'],row['path']) not in keys]+declared
    return result


def project_memory(request: dict[str,Any], scope: dict[str,Any], fields: dict[str,Any], count: int) -> dict[str,Any]:
    """References to validated prefix values avoid duplicating bodies/source.

    Raw values remain in earlier_acceptance; this registry has no authority to
    approve source, grant tool access, or mark behavior verified.
    """
    mutations=[]
    for index,check in enumerate(fields.get('checks',[])):
        if check.get('method') in {'POST','PUT','PATCH','DELETE'} and 200<=check.get('status',0)<300:
            mutations.append({'check_index':index,'method':check['method'],'path':check['path'],
                              'body_ref':f'earlier_acceptance.checks[{index}].body' if 'body' in check else None,
                              'assertion_ref':f'earlier_acceptance.checks[{index}]'})
    return {'schema':1,'policy':'validated_prefix_v1','request_sha256':digest(request),'scope_sha256':digest(scope),
            'accepted_prefix_sha256':digest(fields),'accepted_features':count,
            'check_count':len(fields.get('checks',[])),'known_contracts':len(fields.get('api_contracts',[])),
            'api_registry_ref':'earlier_acceptance.api_contracts','declared_mutations':mutations,
            'authority':'Validated unapproved declarations only; no generated code executed or behavior verified.'}


def stage_examples(request: dict[str,Any]) -> dict[str,Any]:
    """Illustrate the actual selected starter shape without installing checks."""
    contracts=api_registry(request)
    create=next((c for c in contracts if c['method']=='POST' and c['path'].startswith('/api/')),None)
    read=next((c for c in contracts if create and c['method']=='GET' and c['path']==create['path']),None)
    examples: dict[str,Any]={'meaning':'Examples only, never automatically installed. Use only scenarios needed by target_feature.',
                            'assertion':{'kind':'json_subset','expected':{'status':'ok'}}}
    if not create or not read:return examples
    sample={'id':1,'title':'Saved sample'}
    fields=create.get('required_fields',[])
    body={'title':'Saved sample'}
    if 'note' in fields:body['note']='Keep this value';sample['note']=body['note']
    if 'body' in fields:body['body']='Keep this value';sample['body']=body['body']
    expected: Any=[sample] if read['response_kind']=='array' else {'records':[sample]} if 'records' in read.get('required_fields',[]) else sample
    examples['create_sample']={'name':'Create sample','method':'POST','path':create['path'],'status':create['status'],
                               'body':body,'assertion':{'kind':'json_subset','expected':sample}}
    examples['read_seeded_value']={'name':'Read seeded sample after restart','method':'GET','path':read['path'],
                                  'status':read['status'],'restart_before':True,
                                  'assertion':{'kind':'json_subset','expected':expected}}
    examples['scenario_rule']='Read after restart only after an earlier create of that same still-existing value. Reuse earlier_acceptance seeds; never delete them before persistence checks.'
    return examples


def check_contract_context(checks: list[dict[str,Any]], fields: dict[str,Any]) -> list[dict[str,Any]]:
    """Structured hints for the correction packet; no guessed API contracts."""
    from .contracts import _matches
    hints=[]
    if not isinstance(checks,list):return hints
    for index,check in enumerate(checks):
        if not isinstance(check,dict) or not isinstance(check.get('path'),str) or not isinstance(check.get('method'),str):continue
        matches=[copy.deepcopy(c) for c in fields.get('api_contracts',[]) if _matches(c,check)]
        hints.append({'check_index':index,'path':urlsplit(check['path']).path,'known_contracts':matches,
                      'request_example_required':check.get('method') in {'POST','PUT','PATCH'} and 200<=check.get('status',0)<300})
    return hints


def guard_probes() -> dict[str,Any]:
    """Small deterministic diagnostics of the production acceptance boundary."""
    from .feature_acceptance import compile_feature
    from .guided import StageValidationError
    scope={'title':'Diagnostic records','summary':'Save records','features':['Create a record'],
           'out_of_scope':[],'risks':[],'app_kind':'server','task_contract_version':1,'context_policy':'focused_v1'}
    request={'starter':CATALOG['sqlite'],'acceptance_policy':'evidence_v1','acceptance_planning_policy':'feature_v3'}
    check={'name':'Create record','method':'POST','path':'/api/records','status':201,
           'body':{'title':'Fixed diagnostic sample'},'json_contains':{'id':1,'title':'Fixed diagnostic sample'}}
    cases=[]
    scenarios: list[tuple[str,dict[str,Any],str | None]]=[('known_registry',{},None),('unknown_contract',{'path':'/api/unknown'},'missing_api_contract'),
            ('wrong_wrapper',{'json_contains':[{'title':'Fixed diagnostic sample'}]},'response_shape'),('missing_sample',{'body':{}},'mutation_example')]
    for name,change,expected in scenarios:
        codes=[]
        try:compile_feature(scope,{'checks':[]},{'checks':[{**copy.deepcopy(check),**change}]},0,request)
        except StageValidationError as exc:codes=[finding.code for finding in exc.review.findings]
        cases.append({'code':name,'passed':expected in codes if expected else not codes,
                      'expected_codes':[expected] if expected else [],'observed_codes':codes})
    return {'status':'passed' if all(row['passed'] for row in cases) else 'failed','case_count':len(cases),
            'cases':cases,'executed':False,'inference_tested':False}
