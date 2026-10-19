"""Provider identities and private environment configuration; no network calls."""
from __future__ import annotations
import os
import re

PROVIDERS: dict[str, tuple[str | None, str | None]] = {
    'ollama':(None,None),
    'gemini':('https://generativelanguage.googleapis.com/v1beta/openai','GEMINI_API_KEY'),
    'groq':('https://api.groq.com/openai/v1','GROQ_API_KEY'),
    'cloudflare':('https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1','CLOUDFLARE_API_TOKEN'),
    'openrouter':('https://openrouter.ai/api/v1','OPENROUTER_API_KEY'),
    'nvidia':('https://integrate.api.nvidia.com/v1','NVIDIA_API_KEY'),
    'requesty':('https://router.requesty.ai/v1','REQUESTY_API_KEY'),
    'huggingface':('https://router.huggingface.co/v1','HUGGINGFACE_API_KEY'),
}
CLOUD_ORDER = tuple(p for p in PROVIDERS if p != 'ollama')
ALIASES = {
    'GOOGLE_API_KEY':'GEMINI_API_KEY', 'GOOGLE_GENAI_API_KEY':'GEMINI_API_KEY', 'GEMINI_KEY':'GEMINI_API_KEY',
    'GROQ_KEY':'GROQ_API_KEY', 'OPENROUTER_KEY':'OPENROUTER_API_KEY',
    'CLOUDFLARE_API_KEY':'CLOUDFLARE_API_TOKEN', 'CF_API_TOKEN':'CLOUDFLARE_API_TOKEN','CF_API_KEY':'CLOUDFLARE_API_TOKEN',
    'CF_ACCOUNT_ID':'CLOUDFLARE_ACCOUNT_ID',
    'NVIDIA_NIM_API_KEY':'NVIDIA_API_KEY','NIM_API_KEY':'NVIDIA_API_KEY','NVIDIA_KEY':'NVIDIA_API_KEY',
    'REQUESTY_KEY':'REQUESTY_API_KEY',
    'HF_TOKEN':'HUGGINGFACE_API_KEY','HF_API_KEY':'HUGGINGFACE_API_KEY','HUGGINGFACE_TOKEN':'HUGGINGFACE_API_KEY',
    'HUGGINGFACE_API_TOKEN':'HUGGINGFACE_API_KEY','HUGGINGFACEHUB_API_TOKEN':'HUGGINGFACE_API_KEY','HUGGING_FACE_HUB_TOKEN':'HUGGINGFACE_API_KEY',
}
KEYS = tuple(variable for _,variable in PROVIDERS.values() if variable is not None)
CONFIG_NAMES = ('CLOUDFLARE_ACCOUNT_ID',)
SECRET_NAMES = (*KEYS, *(name for name,target in ALIASES.items() if target in KEYS))


def environment_value(name: str) -> str | None:
    return os.getenv(name) or next((os.getenv(alias) for alias,target in ALIASES.items() if target == name and os.getenv(alias)),None)


def endpoint(provider: str) -> str:
    base = PROVIDERS[provider][0]
    if base is None:
        raise ValueError('This provider does not use a cloud endpoint.')
    if provider == 'cloudflare':
        account = environment_value('CLOUDFLARE_ACCOUNT_ID') or ''
        if not re.fullmatch(r'[a-fA-F0-9]{32}',account):
            raise ValueError('Cloudflare Workers AI needs CLOUDFLARE_ACCOUNT_ID (32 hexadecimal characters) as well as an API token. Add it to your local .env and re-import; do not share values in chat.')
        base = base.replace('{account_id}',account)
    return base


def key_for(provider: str) -> str | None:
    name = PROVIDERS[provider][1]
    return environment_value(name) if name else None
