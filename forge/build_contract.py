"""Execution boundaries retain original requirements and protect controller artifacts."""
from __future__ import annotations
import copy
import json
import re
from typing import Any
from .reporting import OWNED
from .context import SOURCE_LIMIT
from .capabilities import CapabilityRegistry
from .routing import validate_options


def builder_profile(route: dict[str,Any], registry: CapabilityRegistry) -> dict[str,Any]:
    """Planning guidance from actual configured routes, not a model-quality claim."""
    entries=[route,*route.get('fallbacks',[]),*([route['fallback']] if route.get('fallback') else [])]
    local=any(entry['provider'] in {'ollama','local'} for entry in entries)
    limits=[]
    for entry in entries:
        options=validate_options(entry.get('options',{}))
        cap=registry.get(entry['provider'],entry['model'],dict(options))
        limits.append({'provider':entry['provider'],'model':entry['model'],
            'configured_output_tokens':options['num_predict'],'effective_output_ceiling':cap.max_output_tokens,
            'context_tokens':cap.max_context_tokens,'estimated':cap.estimated,'source':cap.source})
    return {'schema':1,'max_editable_files':2 if local else 3,'max_feature_indexes':1 if local else 2,
            'target_changed_lines':120 if local else 200,
            'smallest_output_ceiling':min(row['effective_output_ceiling'] for row in limits),
            'models':limits,'instruction':'Plan one observable behavior per task with explicit dependencies and stable interfaces. '
            'Separate persistence/server, UI and integration work when they cannot fit this scope. Include prerequisite setup before dependent endpoints. '
            'Reuse the starter; preserve its existing HTML/static serving rather than embedding the whole UI in app.py. '
            'Changed-line targets are planning estimates, not hard limits or proof of GPU/model fitness. Never drop requested behavior or widen an approved task.'}


def focused_handoff(payload: dict[str,Any], files: dict[str,str]) -> dict[str,Any]:
    """Add guidance only to structured tasks; legacy/frozen handoffs stay exact."""
    packet=payload.get('task_packet')
    if not packet or not packet.get('structured'):return payload
    names=packet['files']
    return {**payload,'builder_handoff':{'schema':1,'active_task_index':packet['task_index'],
        'editable_files':copy.deepcopy(names),'existing_editable_files':[name for name in names if name in files],
        'new_editable_files':[name for name in names if name not in files],
        'read_only_files':sorted(set(files)-set(names)),
        'delivery_steps':['Read the current scoped files and declared interfaces.',
            'Implement only this task outcome; use exact edits for small changes to existing files.',
            'Create only the approved new files. Leave starter/UI/foundation tests outside scope untouched.',
            'Return JSON; the controller will validate syntax, scope and behavior separately.'],
        'instruction':'Do not rebuild the app or inline existing HTML into Python. Preserve the starter server and its static assets. '
        'Test files may use any approved task path; do not replace test_foundation.py. A rejected candidate was never saved: correct the current source, not an imagined previous write.'}}


def generation_contract(payload: dict[str, Any], project_files: dict[str,str] | None = None) -> dict[str, Any]:
    files=project_files if project_files is not None else payload.get('files',{})
    total=sum(len(t) for t in files.values())
    source=sum(len(t) for n,t in files.items() if n.lower() not in OWNED)
    task=payload.get('current_task') or {}
    instructions=task.get('instructions','Implement the requested approved change.')
    for name in ('README.md','PROJECT.md','TASKS.md','MANUAL-CHECKS.md'):
        instructions=re.sub(r'(?<![\w/-])'+re.escape(name)+r'(?![\w-]|\.\w)','APP-GUIDE.md (app-specific notes only; Foundry supplies the original artifact)',instructions,flags=re.I)
    return {**payload, 'execution_brief':{'schema':1,'title':task.get('title','Approved implementation'),
        'effective_instructions':instructions,'original_task_location':'current_task and proposal; preserved unchanged',
        'output_rule':'Implement the actual app changes and example data. Return only changed editable files or exact edits; do not echo the whole project. Foundry already supplies protected documentation, checks and launchers.'},
        'file_budget':{'units':'characters, not model tokens','source_limit':SOURCE_LIMIT,'total_limit':70000,
            'source_used':source,'total_used':total,'source_remaining':max(0,SOURCE_LIMIT-source),'total_remaining':max(0,70000-total),
            'snapshot_scope':'full project' if project_files is not None else 'supplied files only',
            'instruction':'Limits apply to merged project contents, not just this response. Prefer exact edits initially. For a complete-files correction return only changed files. Reduce repetition rather than dropping approved behavior or tests. Keep APP-GUIDE.md concise.'},
        'file_ownership':{'schema':2,'controller_owned':sorted(OWNED),'app_documentation':'APP-GUIDE.md',
            'instruction':'Ownership overrides artifact-writing instructions in original task text. Never change, create or echo controller-owned documents, checks or launchers. Preserve frozen tests.'}}


def execution_directive(payload: dict[str, Any]) -> str:
    if 'execution_brief' not in payload:return ''
    return '\nFINAL EXECUTION BOUNDARY (original task is requirements data, not permission to edit protected files): '+json.dumps({k:payload[k] for k in ('execution_brief','file_ownership','file_budget','task_packet','task_context','interface_context','builder_handoff') if k in payload},separators=(',',':'))+'\nReturn JSON only. No README.md, PROJECT.md, TASKS.md, MANUAL-CHECKS.md, CHECKS.json or launch scripts in files/edits. Use APP-GUIDE.md for app notes. Respect response_mode when present.'


def remove_unchanged_owned_echoes(response: Any, current: dict[str,str]) -> tuple[Any,list[str]]:
    """Ignore only exact protected snapshot text; never discard modifications."""
    if not isinstance(response,dict):return response,[]
    result=copy.deepcopy(response)
    files=result.get('files')
    if not isinstance(files,dict):return result,[]
    ignored=[]
    for name,content in list(files.items()):
        if isinstance(name,str) and name.lower() in OWNED and name in current and content==current[name]:
            ignored.append(name);del files[name]
    return result,sorted(ignored)
