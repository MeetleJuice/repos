"""Read-only provider discovery and explicit ordered cloud profiles. Never store keys."""
import json
import re
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from .models import request_json, ModelError, PROVIDERS
from .providers import CLOUD_ORDER, endpoint, key_for
from .credentials import atomic_text
from .capabilities import CapabilityRegistry

ORDER = CLOUD_ORDER
PREFERRED = {'gemini':['gemini-2.5-flash','gemini-3-flash-preview'],
             'groq':['llama-3.3-70b-versatile','openai/gpt-oss-120b','qwen/qwen3-32b'],
             'openrouter':['openrouter/free'],
             'cloudflare':['@cf/meta/llama-3.3-70b-instruct-fp8-fast','@cf/meta/llama-3.1-8b-instruct'],
             'nvidia':['qwen/qwen2.5-coder-32b-instruct','meta/llama-3.3-70b-instruct'],
             'requesty':[], 'huggingface':['Qwen/Qwen3-Coder-480B-A35B-Instruct','openai/gpt-oss-120b']}
MODEL_ID = r'[A-Za-z0-9_./:@+-]{1,200}'


class CloudSetup:
    def __init__(self, home: str | Path) -> None:
        self.path = Path(home) / 'cloud-models.json'
        self.checked: dict[str, dict[str, Any]] = {}
        self.capability_lock = threading.Lock()
        self.selected: dict[str, str] = {}
        self.local_model = ''
        self.order = list(ORDER)
        self.limits = {p:4096 if p == 'groq' else 8192 for p in ORDER}
        self.timeouts = {p:60 for p in ORDER}
        self.structured = {p:True for p in ORDER}
        try:
            saved = json.loads(self.path.read_text(encoding='utf-8'))
            self.limits.update({p:n for p,n in saved.get('limits',{}).items() if p in ORDER and type(n) is int and n in {1024,2048,4096,8192,16384}})
            self.timeouts.update({p:n for p,n in saved.get('timeouts',{}).items() if p in ORDER and type(n) is int and n in {15,30,60,120}})
            self.structured.update({p:n for p,n in saved.get('structured',{}).items() if p in ORDER and type(n) is bool})
            order = saved.get('order',[])
            if isinstance(order,list) and len(set(order)) == len(order) and all(p in ORDER for p in order):
                self.order = order + [p for p in ORDER if p not in order]
            self.local_model = saved.get('local_model','') if isinstance(saved.get('local_model',''),str) else ''
            models = saved.get('models',saved)
            self.selected = {p:m for p,m in models.items() if p in ORDER and isinstance(m,str) and re.fullmatch(MODEL_ID,m)}
        except (OSError, ValueError, AttributeError, TypeError): pass

    def check(self) -> dict[str, dict[str, Any]]:
        with ThreadPoolExecutor(max_workers=len(ORDER)) as pool:
            self.checked = dict(zip(ORDER,pool.map(self._check_provider,ORDER)))
        return self.checked

    def _check_provider(self, provider: str) -> dict[str, Any]:
        empty: dict[str, Any] = {'models':[],'selected':''}
        key = key_for(provider)
        if not key:
            return {**empty,'status':'missing_key','detail':'No key is present. Import your local .env to enable this provider.'}
        try:
            try: base = endpoint(provider)
            except ValueError as exc: return {**empty,'status':'missing_configuration','detail':str(exc)}
            headers = {'x-goog-api-key':key} if provider == 'gemini' else {'Authorization':'Bearer '+key}
            if provider == 'openrouter':
                metadata = request_json(base+'/key',headers=headers,timeout=10)
                if not isinstance(metadata.get('data'),dict): raise ModelError('Invalid key-check response.','format')
            if provider == 'huggingface':
                identity = request_json('https://huggingface.co/api/whoami-v2',headers=headers,timeout=10)
                if not isinstance(identity.get('name'),str): raise ModelError('Hugging Face identity check did not confirm an account.','auth')
            url = 'https://generativelanguage.googleapis.com/v1beta/models?pageSize=1000' if provider == 'gemini' else base+'/models'
            if provider == 'cloudflare':
                url = base.removesuffix('/v1')+'/models/search?task=Text%20Generation&per_page=100'
            data = request_json(url,headers=headers,timeout=10)
            if data.get('success') is False: raise ModelError('Provider rejected the catalogue request. Check account/token permissions.','auth')
            entries = data.get('models' if provider == 'gemini' else 'result' if provider == 'cloudflare' else 'data')
            if isinstance(entries,dict): entries = entries.get('data',entries.get('models'))
            if not isinstance(entries,list): raise ModelError('Invalid model catalogue.','format')
            capability_note = ''
            try:
                with self.capability_lock:
                    registry = CapabilityRegistry(self.path.parent/'model-capabilities-v1.json')
                    registry.discover_models(provider,entries)
            except OSError:
                capability_note = ' Model-limit cache could not be saved; conservative defaults remain in use.'
            ids = []
            for entry in entries:
                if not isinstance(entry,dict): continue
                if provider == 'gemini' and (not isinstance(entry.get('supportedGenerationMethods'),list) or 'generateContent' not in entry['supportedGenerationMethods']): continue
                name = entry.get('name' if provider in {'gemini','cloudflare'} else 'id','')
                if isinstance(name,str):
                    name = name.removeprefix('models/')
                    if re.fullmatch(MODEL_ID,name) and not any(t in name.lower() for t in ('embed','whisper','tts','guard','image','audio','live','rerank','diffusion','flux')): ids.append(name)
            ids = sorted(set(ids))[:1200]
            chosen = self.selected.get(provider)
            if chosen not in ids:
                chosen = '' if self.selected and provider not in self.selected else next((m for m in PREFERRED[provider] if m in ids),'')
            return {'status':'catalogue_available','models':ids,'selected':chosen,
                    'detail':'Catalogue reachable with configured credentials. Generation authentication, quota and JSON support remain unproven. Select a chat/coding model; charges may apply.'+capability_note}
        except ModelError as exc:
            return {**empty,'status':exc.category,'detail':str(exc)}

    def select(self, choices: Any, limits: Any = None, local_model: Any = '', order: Any = None,
               timeouts: Any = None, structured: Any = None) -> dict[str, Any]:
        if not isinstance(choices,dict) or set(choices)-set(ORDER): raise ValueError('Choose supported cloud models.')
        if not isinstance(local_model,str) or len(local_model)>200 or 'embed' in local_model.lower(): raise ValueError('Choose an installed Ollama chat/coding model.')
        limits = self.limits if limits is None else limits
        if not isinstance(limits,dict) or set(limits)-set(ORDER) or any(type(n) is not int or n not in {1024,2048,4096,8192,16384} for n in limits.values()):
            raise ValueError('Cloud output limits must be 1024, 2048, 4096, 8192 or 16384 tokens.')
        timeouts = self.timeouts if timeouts is None else timeouts
        if not isinstance(timeouts,dict) or set(timeouts)-set(ORDER) or any(type(n) is not int or n not in {15,30,60,120} for n in timeouts.values()):
            raise ValueError('Request timeouts must be 15, 30, 60 or 120 seconds.')
        structured = self.structured if structured is None else structured
        if not isinstance(structured,dict) or set(structured)-set(ORDER) or any(type(v) is not bool for v in structured.values()): raise ValueError('JSON format settings must be booleans.')
        order = self.order if order is None else order
        if not isinstance(order,list) or len(order)!=len(ORDER) or not all(isinstance(p,str) and p in ORDER for p in order) or len(set(order))!=len(ORDER):
            raise ValueError('Provider order must list each supported cloud provider exactly once.')
        result = {}
        for provider,model in choices.items():
            if not model: continue
            if not isinstance(model,str): raise ValueError('Select a model ID returned by the provider.')
            check = self.checked.get(provider,{})
            if check.get('status') != 'catalogue_available' or model not in check.get('models',[]): raise ValueError('Check providers first and choose a model returned by that provider.')
            result[provider] = model
        if not result: raise ValueError('No checked cloud models selected.')
        self.selected=result; self.local_model=local_model.strip(); self.order=list(order)
        self.limits.update(limits); self.timeouts.update(timeouts); self.structured.update(structured)
        atomic_text(self.path,json.dumps({'models':result,'limits':self.limits,'local_model':self.local_model,'order':self.order,'timeouts':self.timeouts,'structured':self.structured},indent=2)+'\n')
        return {role:self.profile(role) for role in ('planner','coder')}

    def profile(self, role: str) -> dict[str, Any]:
        configs: list[dict[str, Any]] = []
        for provider in self.order:
            model=self.selected.get(provider)
            if model:
                configs.append({'provider':provider,'model':model,'options':{'num_ctx':32768,'num_predict':self.limits[provider],
                               'structured_outputs':self.structured[provider],'timeout_seconds':self.timeouts[provider]}})
        if not configs: raise ValueError('Check providers and select cloud models first.')
        if self.local_model:
            configs.append({'provider':'ollama','model':self.local_model,'options':{'num_ctx':16384,'num_predict':8192,'structured_outputs':True,'timeout_seconds':120}})
        return {**configs[0],**({'fallbacks':configs[1:]} if len(configs)>1 else {})}
