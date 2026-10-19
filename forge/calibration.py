"""Explicit local-only fixed-fixture calibration; no project source or code execution."""
from __future__ import annotations
from datetime import datetime, timezone
import json
import time
from pathlib import Path
from typing import Any, Callable
from .credentials import atomic_text
from .edits import expand_response
from .models import ModelClient, ModelError
from .routing import validate_options


def read_calibration(path: Path) -> dict[str,Any]:
    try:
        result=json.loads(path.read_text(encoding='utf-8'))
        if isinstance(result,dict) and result.get('schema')==1:return result
    except (OSError,ValueError):pass
    return {}


def calibrate(model: str, path: Path, factory: Callable[[str,str],Any] = ModelClient) -> dict[str,Any]:
    client=factory('ollama',model)
    if isinstance(client,ModelClient):client.options=validate_options({'num_ctx':4096,'num_predict':1024,'timeout_seconds':60})
    sample='def calculate(a, b):\n    return a + b\n'
    cases=[('JSON response',{'instruction':'Return exactly {"answer":7}.','input':[2,5]}),
           ('Exact edit',{'instruction':'Return JSON with edits [{file,search,replace}]. Change only a + b to a - b in sample.py.','files':{'sample.py':sample}})]
    rows=[]
    for name,payload in cases:
        started=time.monotonic()
        try:
            result=client.complete('Return JSON only. Follow the fixed local calibration case; no project is involved.',json.dumps(payload))
            passed=result=={'answer':7} if name=='JSON response' else bool(result.get('edits')) and not result.get('files') and expand_response(result,{'sample.py':sample})=={'sample.py':sample.replace('a + b','a - b')}
            row={'name':name,'passed':passed,'error':None if passed else 'Response did not match the fixed fixture.'}
        except (ModelError,ValueError) as exc:
            row={'name':name,'passed':False,'error':getattr(exc,'category','format')}
        row.update(seconds=round(time.monotonic()-started,3),metrics={k:v for k,v in getattr(client,'last_metadata',{}).items() if k.startswith('ollama_')},usage=getattr(client,'last_usage',{}))
        rows.append(row)
    report={'schema':1,'model':model,'provider':'ollama','time':datetime.now(timezone.utc).isoformat(),'context_tokens':4096,'output_cap':1024,
            'cases':rows,'passed':all(row['passed'] for row in rows),'meaning':'Two fixed local response checks. No generated code executed. Does not prove project-size capacity, GPU fit or app correctness. Routes unchanged.'}
    atomic_text(path,json.dumps(report,indent=2)+'\n')
    return report
