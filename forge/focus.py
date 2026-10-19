"""Explicit, opt-in task context with complete-file retrieval and no hidden truncation."""
from __future__ import annotations
import ast
import copy
import re
from pathlib import PurePosixPath
from typing import Any
from .execution import file_hashes


class ContextRequestError(ValueError):
    pass


def dependencies(name: str, text: str, files: dict[str,str]) -> set[str]:
    result=set()
    if name.endswith('.py'):
        try:
            for node in ast.walk(ast.parse(text)):
                modules=[n.name for n in node.names] if isinstance(node,ast.Import) else [node.module or ''] if isinstance(node,ast.ImportFrom) else []
                for module in modules:
                    for candidate in [module.replace('.','/')+'.py',module.replace('.','/')+'/__init__.py']:
                        if candidate in files:result.add(candidate)
        except (SyntaxError,ValueError):pass
    for ref in re.findall(r'''(?:src|href)=["']([^"'#?]+)|(?:from\s*|import\s*)["']([^"']+)["']''',text):
        path=next((p for p in ref if p),'')
        if '://' in path or path.startswith('//'):continue
        candidate=str(PurePosixPath(name).parent/path).removeprefix('./')
        if candidate in files:result.add(candidate)
        if path.lstrip('/') in files:result.add(path.lstrip('/'))
    return result


def prepare_context(payload: dict[str,Any], files: dict[str,str]) -> dict[str,Any]:
    observed=interface_context(payload.get('current_task') or {},files)
    if observed:payload={**payload,'interface_context':observed}
    if payload.get('proposal',{}).get('context_policy')!='focused_v1' or not payload.get('task_packet',{}).get('structured'):return payload
    result=copy.deepcopy(payload); selected=set(payload['task_packet']['files'])&files.keys()
    # Include transitive local dependencies; use all source if closure is large.
    for _ in range(len(files)):
        expanded=selected|set().union(*(dependencies(n,files[n],files) for n in selected)) if selected else set()
        if expanded==selected:break
        selected=expanded
    selected|={n for n,t in files.items() if PurePosixPath(n).name.startswith('test_') and dependencies(n,t,files)&selected}
    if not selected or sum(len(files[n]) for n in selected)>24000:selected=set(files)
    result['files']={n:files[n] for n in sorted(selected)}
    result['task_context']={'version':1,'policy':'focused_v1','available_files':[{'file':n,'characters':len(t),'sha256':file_hashes({n:t})[n]} for n,t in sorted(files.items())],
        'included_files':sorted(selected),'omitted_files':sorted(set(files)-selected),'retrievals_remaining':2,
        'instruction':'All listed source remains available. If necessary return only {"request_context":["exact/file.py"]}; at most five existing files/request and two requests/task. Never guess omitted source. Files are complete, never truncated. Original proposal/task and writable scope remain authoritative.'}
    return result


def retrieve_context(response: Any, payload: dict[str,Any], files: dict[str,str]) -> dict[str,Any] | None:
    if not isinstance(response,dict) or 'request_context' not in response:return None
    context=payload.get('task_context')
    if not context or set(response)!={'request_context'}:raise ContextRequestError('Context requests require an approved focused task and cannot contain files, edits or claims.')
    names=response['request_context']
    if context['retrievals_remaining']<=0:raise ContextRequestError('Task context retrieval limit reached. Use the supplied source or revise the plan.')
    if not isinstance(names,list) or not 1<=len(names)<=5 or not all(isinstance(n,str) and n in files for n in names):raise ContextRequestError('Request 1–5 existing source files from the context manifest.')
    if all(n in payload['files'] for n in names):raise ContextRequestError('Requested files are already included. Use the existing complete source.')
    result=copy.deepcopy(payload);result['files'].update({n:files[n] for n in names})
    result['task_context'].update(retrievals_remaining=context['retrievals_remaining']-1,included_files=sorted(result['files']),omitted_files=sorted(set(files)-result['files'].keys()))
    return result


def interface_context(task: dict[str,Any], files: dict[str,str]) -> list[dict[str,Any]]:
    result=[]
    for contract in task.get('interfaces',[]):
        name=contract['file'];symbol=contract['symbol'];signature=None
        if name in files and name.endswith('.py'):
            try:
                for node in ast.walk(ast.parse(files[name])):
                    if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name==symbol:
                        signature=node.name+'('+ast.unparse(node.args)+')';break
            except (SyntaxError,ValueError):pass
        result.append({**contract,'file_exists':name in files,'observed_python_signature':signature,
                       'meaning':'Static source observation only; declared contract semantics remain unverified.'})
    return result
