"""Read-only provider discovery and explicit cloud-first profiles. Never store keys."""
import json
import os
import re
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from .models import request_json, ModelError, PROVIDERS
from .credentials import atomic_text
from .capabilities import CapabilityRegistry

ORDER = ('gemini', 'groq', 'openrouter')
PREFERRED = {'gemini': ['gemini-2.5-flash', 'gemini-3-flash-preview'],
             'groq': ['llama-3.3-70b-versatile', 'openai/gpt-oss-120b', 'qwen/qwen3-32b'],
             'openrouter': ['openrouter/free']}


class CloudSetup:
    def __init__(self, home: str | Path) -> None:
        self.path = Path(home) / 'cloud-models.json'
        self.checked: dict[str, dict[str, Any]] = {}
        self.selected: dict[str, str] = {}
        self.local_model = ""
        self.limits = {"gemini":8192,"groq":4096,"openrouter":8192}
        try:
            saved = json.loads(self.path.read_text(encoding='utf-8'))
            self.limits.update({p:n for p,n in saved.get('limits',{}).items() if p in ORDER and type(n) is int and n in {1024,2048,4096,8192,16384}})
            self.local_model = saved.get('local_model', '') if isinstance(saved.get('local_model', ''), str) else ''
            saved = saved.get('models', saved)
            self.selected = {p:m for p,m in saved.items() if p in ORDER and isinstance(m,str) and re.fullmatch(r'[A-Za-z0-9_./:@+-]{1,200}',m)}
        except (OSError, ValueError, AttributeError): pass

    def check(self) -> dict[str, dict[str, Any]]:
        with ThreadPoolExecutor(max_workers=3) as pool:
            self.checked = dict(zip(ORDER, pool.map(self._check_provider, ORDER)))
        return self.checked

    def _check_provider(self, provider: str) -> dict[str, Any]:
        base, variable = PROVIDERS[provider]
        if base is None or variable is None: return {'status':'provider','models':[]}
        key = os.getenv(variable or '') or (os.getenv('OPENROUTER_KEY') if provider == 'openrouter' else None)
        if not key:
            return {'status':'missing_key','models':[]}
        try:
            if provider == 'openrouter':
                # The public /models catalogue alone cannot validate an API key.
                metadata = request_json(base + '/key', headers={'Authorization':'Bearer '+key}, timeout=10)
                if not isinstance(metadata.get('data'), dict): raise ModelError('Invalid key-check response.', 'format')
            url = 'https://generativelanguage.googleapis.com/v1beta/models?pageSize=1000' if provider == 'gemini' else base + '/models'
            data = request_json(url, headers={'x-goog-api-key':key} if provider == 'gemini' else {'Authorization':'Bearer '+key}, timeout=10)
            entries = data.get('models' if provider == 'gemini' else 'data')
            if not isinstance(entries,list): raise ModelError('Invalid model catalogue.', 'format')
            if provider == "openrouter": CapabilityRegistry(self.path.parent / "model-capabilities-v1.json").discover_openrouter(entries)
            ids = []
            for entry in entries:
                if not isinstance(entry,dict): continue
                if provider == 'gemini' and (not isinstance(entry.get('supportedGenerationMethods'), list) or 'generateContent' not in entry['supportedGenerationMethods']): continue
                name = entry.get('name' if provider == 'gemini' else 'id','')
                if isinstance(name,str):
                    name = name.removeprefix('models/')
                    if re.fullmatch(r'[A-Za-z0-9_./:@+-]{1,200}',name) and not any(t in name.lower() for t in ('embed','whisper','tts','guard','image','audio','live')): ids.append(name)
            ids = sorted(set(ids))[:1200]
            chosen = self.selected.get(provider)
            if chosen not in ids: chosen = '' if self.selected and provider not in self.selected else next((m for m in PREFERRED[provider] if m in ids), '')
            return {'status':'catalogue_available','models':ids,'selected':chosen,
                'detail':'Key accessed the model catalogue. Generation, quota and JSON support are not yet proven.'}
        except ModelError as exc:
            return {'status':exc.category,'models':[],'detail':str(exc)}

    def select(self, choices: Any, limits: Any = None, local_model: Any = "") -> dict[str, Any]:
        if not isinstance(choices,dict) or set(choices)-set(ORDER): raise ValueError('Choose supported cloud models.')
        if not isinstance(local_model, str) or len(local_model) > 200 or 'embed' in local_model.lower():
            raise ValueError('Choose an installed Ollama chat/coding model.')
        limits = self.limits if limits is None else limits
        if not isinstance(limits, dict) or set(limits) - set(ORDER) or any(type(n) is not int or n not in {1024,2048,4096,8192,16384} for n in limits.values()):
            raise ValueError('Cloud output limits must be 1024, 2048, 4096, 8192 or 16384 tokens.')
        result = {}
        for provider, model in choices.items():
            if not model: continue
            if not isinstance(model,str): raise ValueError('Select a model ID returned by the provider.')
            check = self.checked.get(provider,{})
            if check.get('status') != 'catalogue_available' or model not in check.get('models',[]):
                raise ValueError('Check providers first and choose a model returned by that provider.')
            result[provider] = model
        if not result: raise ValueError('No checked cloud models selected.')
        self.selected = result; self.local_model = local_model.strip(); self.limits.update(limits); atomic_text(self.path, json.dumps({'models':result,'limits':self.limits,'local_model':self.local_model}, indent=2) + '\n')
        return {role:self.profile(role) for role in ('planner','coder')}

    def profile(self, role: str) -> dict[str, Any]:
        configs: list[dict[str, Any]] = []
        for provider in ORDER:
            model = self.selected.get(provider)
            if not model: continue
            configs.append({'provider':provider,'model':model,'options':{'num_ctx':32768,'num_predict':self.limits[provider],'structured_outputs':True}})
        if not configs: raise ValueError('Check providers and select cloud models first.')
        if self.local_model:
            configs.append({'provider':'ollama','model':self.local_model,'options':{'num_ctx':16384,'num_predict':8192,'structured_outputs':True}})
        result = configs[0]
        if len(configs)>1: result = {**result,'fallbacks':configs[1:]}
        return result
