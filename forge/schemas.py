"""Small native Ollama JSON schemas. Semantic correctness is reviewed separately."""
from typing import Any

INDEXES = {'type': 'array', 'items': {'type': 'integer'}}
PLAN_SCHEMA: dict[str, Any] = {
    'type': 'object',
    'required': ['title', 'summary', 'features', 'out_of_scope', 'risks', 'tasks', 'checks', 'app_kind', 'task_contract_version', 'context_policy'],
    'properties': {
        'context_policy': {'type':'string','enum':['full','focused_v1']},
        'task_contract_version': {'type':'integer','enum':[1]},
        'title': {'type': 'string'}, 'summary': {'type': 'string'},
        **{key: {'type': 'array', 'items': {'type': 'string'}} for key in ['features', 'out_of_scope', 'risks']},
        'tasks': {'type': 'array', 'items': {'type': 'object', 'required': ['title', 'instructions', 'feature_indexes', 'outcome', 'files', 'depends_on', 'done_when'],
                  'properties': {'title': {'type': 'string','minLength':1}, 'instructions': {'type': 'string','minLength':1,'maxLength':1800}, 'outcome': {'type':'string','minLength':1,'maxLength':300}, 'files': {'type':'array','items':{'type':'string'},'minItems':1,'maxItems':3}, 'depends_on': INDEXES, 'interfaces': {'type':'array','maxItems':6,'items':{'type':'object','required':['file','symbol','contract'],'properties':{k:{'type':'string'} for k in ['file','symbol','contract']}}}, 'done_when': {'type':'array','items':{'type':'string'},'minItems':1,'maxItems':4}, 'feature_indexes': {**INDEXES,'minItems':1,'maxItems':3}, 'check_indexes': INDEXES}}},
        'checks': {'type': 'array', 'items': {'type': 'object', 'required': ['name', 'method', 'path', 'status', 'feature_indexes'],
                   'anyOf':[{'required':['contains']},{'required':['json_contains']},{'required':['json_equals']},{'required':['empty_body'],'properties':{'empty_body':{'const':True}}}],
                   'properties': {'name': {'type': 'string'}, 'method': {'type': 'string', 'enum': ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']},
                                  'path': {'type': 'string'}, 'status': {'type': 'integer'}, 'feature_indexes': {**INDEXES,'minItems':1},
                                  'body': {}, 'contains': {'type': 'string','minLength':1}, 'json_contains': {'anyOf':[{'type':'object','minProperties':1},{'type':'array','minItems':1}]},
                                  'json_equals': {}, 'empty_body': {'type': 'boolean'}, 'restart_before': {'type': 'boolean'}}}},
        'app_kind': {'type': 'string', 'enum': ['server', 'browser']},
        'manual_checks': {'type': 'array', 'items': {'type': 'object', 'required': ['name', 'steps', 'expected', 'feature_indexes'], 'properties': {
            'name': {'type': 'string'}, 'steps': {'type': 'array', 'items': {'type': 'string'}}, 'expected': {'type': 'string'}, 'feature_indexes': {**INDEXES,'minItems':1}}}},
        'browser_checks': {'type': 'array', 'items': {'type': 'object', 'required': ['name', 'steps', 'feature_indexes'], 'properties': {
            'name': {'type': 'string'}, 'feature_indexes': INDEXES, 'clock': {'type': 'boolean'}, 'random_seed': {'type': 'integer'}, 'random_values': {'type': 'array', 'items': {'type': 'number'}}, 'steps': {'type': 'array', 'items': {'type': 'object', 'required': ['action'], 'properties': {
                'action': {'type': 'string', 'enum': ['click', 'fill', 'press', 'wait', 'expect_text', 'expect_visible', 'expect_canvas_changes', 'reload', 'expect_storage', 'key_down', 'key_up', 'advance_time', 'expect_text_exact', 'expect_canvas_still']},
                'selector': {'type': 'string'}, 'value': {'type': 'string'}, 'ms': {'type': 'integer'}}}}}}},
        'api_contracts': {'type': 'array', 'items': {'type': 'object',
                          'required': ['method', 'path', 'status', 'response_kind', 'required_fields'],
                          'properties': {'method': {'type': 'string'}, 'path': {'type': 'string'}, 'status': {'type': 'integer'},
                                         'response_kind': {'type': 'string', 'enum': ['object', 'array', 'text', 'empty', 'scalar']},
                                         'required_fields': {'type': 'array', 'items': {'type': 'string'}}}}},
    },
}
CODE_SCHEMA: dict[str, Any] = {'type': 'object', 'anyOf': [{'required': ['files']}, {'required': ['edits']}, {'required':['already_satisfied']},{'required':['request_context']}], 'properties': {
    'request_context': {'type':'array','maxItems':5,'items':{'type':'string'}},
    'already_satisfied': {'type':'object','required':['reason','evidence'],'properties':{'reason':{'type':'string'},'evidence':{'type':'array','items':{'type':'object','required':['file','contains'],'properties':{'file':{'type':'string'},'contains':{'type':'string'}}}}}},
    'summary': {'type': 'string'}, 'files': {'type': 'object', 'additionalProperties': {'type': 'string'}},
    'edits': {'type': 'array', 'maxItems': 12, 'items': {'type': 'object', 'required': ['file', 'search', 'replace'], 'additionalProperties': False, 'properties': {key: {'type': 'string'} for key in ['file', 'search', 'replace']}}}}}

COMPLETE_CODE_SCHEMA = {'type': 'object', 'anyOf':[{'required':['files']},{'required':['already_satisfied']},{'required':['request_context']}], 'additionalProperties': False, 'properties': {
    'request_context': CODE_SCHEMA['properties']['request_context'],
    'already_satisfied': CODE_SCHEMA['properties']['already_satisfied'],
    'summary': {'type': 'string'}, 'files': {'type': 'object', 'minProperties': 1, 'additionalProperties': {'type': 'string'}}}}
