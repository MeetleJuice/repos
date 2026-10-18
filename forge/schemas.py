"""Small native Ollama JSON schemas. Semantic correctness is reviewed separately."""
INDEXES = {'type': 'array', 'items': {'type': 'integer'}}
PLAN_SCHEMA = {
    'type': 'object',
    'required': ['title', 'summary', 'features', 'out_of_scope', 'risks', 'tasks', 'checks', 'app_kind'],
    'properties': {
        'title': {'type': 'string'}, 'summary': {'type': 'string'},
        **{key: {'type': 'array', 'items': {'type': 'string'}} for key in ['features', 'out_of_scope', 'risks']},
        'tasks': {'type': 'array', 'items': {'type': 'object', 'required': ['title', 'instructions', 'feature_indexes'],
                  'properties': {'title': {'type': 'string'}, 'instructions': {'type': 'string'}, 'feature_indexes': INDEXES, 'check_indexes': INDEXES}}},
        'checks': {'type': 'array', 'items': {'type': 'object', 'required': ['name', 'method', 'path', 'status', 'feature_indexes'],
                   'properties': {'name': {'type': 'string'}, 'method': {'type': 'string', 'enum': ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']},
                                  'path': {'type': 'string'}, 'status': {'type': 'integer'}, 'feature_indexes': INDEXES,
                                  'body': {}, 'contains': {'type': 'string'}, 'json_contains': {'type': ['object', 'array']},
                                  'json_equals': {}, 'empty_body': {'type': 'boolean'}, 'restart_before': {'type': 'boolean'}}}},
        'app_kind': {'type': 'string', 'enum': ['server', 'browser']},
        'manual_checks': {'type': 'array', 'items': {'type': 'object', 'required': ['name', 'steps', 'expected', 'feature_indexes'], 'properties': {
            'name': {'type': 'string'}, 'steps': {'type': 'array', 'items': {'type': 'string'}}, 'expected': {'type': 'string'}, 'feature_indexes': INDEXES}}},
        'browser_checks': {'type': 'array', 'items': {'type': 'object', 'required': ['name', 'steps', 'feature_indexes'], 'properties': {
            'name': {'type': 'string'}, 'feature_indexes': INDEXES, 'steps': {'type': 'array', 'items': {'type': 'object', 'required': ['action'], 'properties': {
                'action': {'type': 'string', 'enum': ['click', 'fill', 'press', 'wait', 'expect_text', 'expect_visible', 'expect_canvas_changes', 'reload', 'expect_storage']},
                'selector': {'type': 'string'}, 'value': {'type': 'string'}, 'ms': {'type': 'integer'}}}}}}},
        'api_contracts': {'type': 'array', 'items': {'type': 'object',
                          'required': ['method', 'path', 'status', 'response_kind', 'required_fields'],
                          'properties': {'method': {'type': 'string'}, 'path': {'type': 'string'}, 'status': {'type': 'integer'},
                                         'response_kind': {'type': 'string', 'enum': ['object', 'array', 'text', 'empty', 'scalar']},
                                         'required_fields': {'type': 'array', 'items': {'type': 'string'}}}}},
    },
}
CODE_SCHEMA = {'type': 'object', 'required': ['files'], 'properties': {
    'summary': {'type': 'string'}, 'files': {'type': 'object', 'additionalProperties': {'type': 'string'}}}}
