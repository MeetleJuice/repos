"""Bounded model metadata reads; never generation, model loading or calibration."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
import copy
import os
import re
import time
from typing import Any
from .capabilities import CapabilityRegistry
from .history import redact


def refresh_local_limits(registry: CapabilityRegistry, names: list[str]) -> None:
    from .models import request_json
    now=time.time()
    def fresh(name: str) -> bool:
        record=registry.overrides.get('ollama/'+name,{})
        stamp=record.get('metadata_checked_at',0) if isinstance(record,dict) else 0
        return type(stamp) in {int,float} and 0<=now-stamp<=1800
    valid=[name for name in names if isinstance(name,str) and re.fullmatch(r'[A-Za-z0-9_./:@+-]{1,200}',name)]
    pending=[name for name in dict.fromkeys(valid) if not fresh(name)][:12]
    if not pending:return
    def read(name: str) -> tuple[str,dict[str,Any] | None]:
        try:return name,request_json(os.getenv('OLLAMA_URL','http://127.0.0.1:11434').rstrip('/')+'/api/show',{'model':name},timeout=2)
        except (ValueError,OSError):return name,None
    with ThreadPoolExecutor(max_workers=4) as pool:
        for name,data in pool.map(read,pending):
            if data is not None:registry.discover_local(name,data)
            existing=registry.overrides.get('ollama/'+name,registry.builtin['defaults'])
            record=copy.deepcopy(existing if isinstance(existing,dict) else registry.builtin['defaults'])
            record['metadata_checked_at']=now
            if data is None:record['metadata_note']='Installed model metadata unavailable; configured/estimated limits retained.'
            registry.overrides['ollama/'+name]=record
    try:registry.save()
    except OSError:pass  # Read-only workspace must not block model selection.


def limit_rows(registry: CapabilityRegistry, providers: dict[str,Any], profiles: dict[str,Any], selected: dict[str,str]) -> list[dict[str,Any]]:
    entries: list[dict[str,Any]]=[]
    for provider in ('ollama','local'):
        entries.extend({'provider':provider,'model':name} for name in providers.get(provider,{}).get('models',[])[:24])
    for provider,model in selected.items():entries.append({'provider':provider,'model':model})
    for role,route in profiles.items():
        if isinstance(route,dict) and route.get('model'):
            entries.extend({**entry,'profile_role':role} for entry in [route,*route.get('fallbacks',[]),*([route['fallback']] if route.get('fallback') else [])])
    seen=set();rows=[]
    for entry in entries:
        identity=(entry.get('provider'),entry.get('model'),entry.get('profile_role','detected/default'))
        if identity in seen or not all(isinstance(value,str) for value in identity):continue
        seen.add(identity)
        row=registry.describe(entry['provider'],entry['model'],entry.get('options'))
        row['profile_scope']=entry.get('profile_role','detected/default settings; not an applied route')
        row['configured_output_tokens']=entry.get('options',{}).get('num_predict',8192)
        row['generation_eligible']='embed' not in entry['model'].lower()
        rows.append(row)
        if len(rows)>=64:break
    result=redact(rows)
    return result if isinstance(result,list) else []
