"""Validated model settings and bounded explicit routes, with no implicit providers."""
from __future__ import annotations

from typing import Any, TypedDict

from .providers import PROVIDERS, LOCAL_PROVIDERS

PROVIDER_NAMES = set(PROVIDERS)
MAX_FALLBACKS = 15


class ModelSettings(TypedDict):
    num_ctx: int
    num_predict: int
    structured_outputs: bool
    timeout_seconds: int


class ModelIdentity(TypedDict):
    provider: str
    model: str


class ModelConfig(ModelIdentity, total=False):
    options: ModelSettings
    fallback: dict[str, Any]
    fallbacks: list[dict[str, Any]]


def validate_options(options: Any) -> ModelSettings:
    if not isinstance(options, dict) or set(options) - {'num_ctx', 'num_predict', 'structured_outputs', 'timeout_seconds'}:
        raise ValueError('Unsupported model settings.')
    context = options.get('num_ctx', 16384)
    output = options.get('num_predict', min(8192, context // 2) if type(context) is int else 8192)
    structured = options.get('structured_outputs', True)
    if type(context) is not int or context not in {4096, 8192, 16384, 32768}:
        raise ValueError('Ollama context must be 4096, 8192, 16384 or 32768.')
    if type(output) is not int or output not in {1024, 2048, 4096, 8192, 16384} or output >= context:
        raise ValueError('Output limit must be 1024/2048/4096/8192/16384 and smaller than context.')
    if type(structured) is not bool:
        raise ValueError('structured_outputs must be true or false.')
    timeout = options.get('timeout_seconds', 120)
    if type(timeout) is not int or timeout not in {15,30,60,120,300,600}:
        raise ValueError('Request timeout must be 15, 30, 60, 120, 300 or 600 seconds.')
    return {'num_ctx': context, 'num_predict': output, 'structured_outputs': structured, 'timeout_seconds':timeout}


def validate_config(config: Any, allow_fallback: bool = True) -> ModelConfig:
    if not isinstance(config, dict) or set(config) - {'provider', 'model', 'options', 'fallback', 'fallbacks'}:
        raise ValueError('Invalid model configuration.')
    provider, model = config.get('provider'), config.get('model')
    if provider not in PROVIDER_NAMES or not isinstance(model, str) or not model.strip() or len(model) > 200:
        raise ValueError('Choose a supported provider and a nonempty model name.')
    if provider in LOCAL_PROVIDERS and 'embed' in model.lower():
        raise ValueError('Embedding models cannot generate apps. Choose a chat/coding model.')
    result: ModelConfig = {'provider': provider, 'model': model.strip()}
    if 'options' in config:
        result['options'] = validate_options(config['options'])
    if 'fallbacks' in config:
        entries = config['fallbacks']
        if not allow_fallback or 'fallback' in config or not isinstance(entries, list) or not 1 <= len(entries) <= MAX_FALLBACKS:
            raise ValueError('Choose either one legacy fallback or a flat list of one to fifteen fallbacks.')
        chain = [validate_config(entry, allow_fallback=False) for entry in entries]
        identities = [(provider, model.strip()), *((entry['provider'], entry['model']) for entry in chain)]
        if len(set(identities)) != len(identities):
            raise ValueError('Fallback identities must be distinct.')
        result['fallbacks'] = [dict(entry) for entry in chain]
    if 'fallback' in config:
        if not allow_fallback:
            raise ValueError('Nested fallback chains are not supported.')
        fallback = validate_config(config['fallback'], allow_fallback=False)
        if (fallback['provider'], fallback['model']) == (provider, model.strip()):
            raise ValueError('Fallback must differ from the primary model.')
        result['fallback'] = dict(fallback)
    return result


def uses_cloud(config: dict[str, Any]) -> bool:
    return config.get('provider', 'ollama') not in LOCAL_PROVIDERS or bool(config.get('fallback') and uses_cloud(config['fallback'])) or any(uses_cloud(entry) for entry in config.get('fallbacks', []))


def truncation_fallback_allowed(current_ceiling: int, candidate_ceiling: int) -> bool:
    """Output exhaustion must never select a smaller model ceiling."""
    return current_ceiling > 0 and candidate_ceiling >= current_ceiling
