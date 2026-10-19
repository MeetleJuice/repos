"""Thread-safe observed model state. No prompts, credentials, or paid probes."""
from __future__ import annotations
import copy
import re
import threading
import time
from typing import Any
from .providers import CLOUD_ORDER, key_for, endpoint


class ModelStatus:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.active: dict[str, Any] | None = None
        self.observed: dict[tuple[str, str], dict[str, Any]] = {}

    def reset(self) -> None:
        with self.lock:
            self.observed.clear()

    def start(self, provider: str, model: str, role: str) -> None:
        with self.lock:
            self.active = {'provider':provider,'model':model,'role':role,'started':time.time()}

    def finish(self, provider: str, model: str, outcome: str) -> None:
        with self.lock:
            self.observed[(provider,model)] = {'state':outcome,'at':time.time()}
            self.active = None

    def reject(self, provider: str, model: str) -> None:
        with self.lock:
            self.observed[(provider,model)] = {'state':'response_rejected','at':time.time()}

    def avoid(self, provider: str, model: str) -> bool:
        with self.lock:
            result = self.observed.get((provider,model),{})
            return result.get('state') in {'model','auth','quota','configuration','response_rejected','schema_error'} and time.time()-result.get('at',0)<300

    def snapshot(self, checked: dict[str, Any], local: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            active=copy.deepcopy(self.active); observed=copy.deepcopy(self.observed)
        secrets=[key for p in CLOUD_ORDER if (key := key_for(p))]
        def safe(model: str) -> bool:
            return bool(re.fullmatch(r'[A-Za-z0-9_./:@+-]{1,200}',model)) and not any(k in model for k in secrets)
        rows=[]
        for provider in CLOUD_ORDER:
            present=bool(key_for(provider)); state='configured' if present else 'missing_key'
            if present:
                try: endpoint(provider)
                except ValueError: state='missing_configuration'
                else:
                    if checked.get(provider): state=checked[provider].get('status','configured')
            recent=[(model,value) for (p,model),value in observed.items() if p==provider and safe(model)]
            model=''; observed_at=None
            if recent and present:
                model,value=max(recent,key=lambda item:item[1]['at'])
                state=value['state']; observed_at=value['at']
            if active and active['provider']==provider:
                state='working'; model=active['model'] if safe(active['model']) else ''; observed_at=active['started']
            rows.append({'id':provider,'label':provider,'state':state,'model':model,'observed_at':observed_at})
        for model in local.get('models',[]):
            if not isinstance(model,str) or not safe(model): continue
            value=observed.get(('ollama',model),{})
            state=value.get('state','installed') if local.get('connected') else 'offline'
            if 'embed' in model.lower(): state='embedding'
            if active and active['provider']=='ollama' and active['model']==model:state='working'
            rows.append({'id':'ollama/'+model,'label':model,'provider':'ollama','model':model,'state':state,'observed_at':active['started'] if active and active['provider']=='ollama' and active['model']==model else value.get('at')})
        if not local.get('models'):rows.append({'id':'ollama','label':'Ollama','state':'offline' if local.get('connected') is False else 'not_checked','model':''})
        return {'items':rows,'sampled_at':time.time(),'note':'Observed request state, not verified app behavior or guaranteed provider availability.'}
