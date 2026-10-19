"""Small provider adapter. No provider SDKs or automatic paid fallbacks."""
import json
import re
import hashlib
import http.client
import os
import urllib.error
import urllib.request
import urllib.parse
from typing import Any, cast

from .routing import validate_options
from .capabilities import PlannerBudget
from .schemas import PLAN_SCHEMA, CODE_SCHEMA, COMPLETE_CODE_SCHEMA
from .prompts import PLAN, CODE

from .providers import PROVIDERS as PROVIDERS, endpoint, key_for



class ModelError(ValueError):
    def __init__(self, message: str, category: str = "format", retry_after: int = 0, partial_content: str = "") -> None:
        self.partial_content = partial_content
        self.category = category
        self.retry_after = retry_after
        super().__init__(message)


def request_json(url: str, payload: dict[str, Any] | None = None, headers: dict[str, str] | None = None, timeout: float = 300) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            data = response.read(2_000_001)
            if len(data) > 2_000_000:
                raise ModelError("Model response exceeded 2 MB; use smaller tasks.", "size")
            parsed = json.loads(data)
            if not isinstance(parsed, dict):
                raise ModelError("Provider response must be a JSON object.")
            return parsed
    except urllib.error.HTTPError as exc:
        # Provider bodies can echo submitted content. Do not leak them or API keys.
        raw_retry = exc.headers.get('Retry-After', '') if exc.headers else ''
        retry = min(300, int(raw_retry)) if len(raw_retry) <= 9 and raw_retry.isdigit() else 30 if exc.code == 429 else 0
        if exc.fp is not None:
            exc.close()
        category = "rate_limit" if exc.code == 429 else "auth" if exc.code in {401, 403} else "quota" if exc.code == 402 else "model" if exc.code == 404 else "request" if exc.code == 400 else "provider"
        raise ModelError(f"Provider returned HTTP {exc.code}. Check the key, model access, quota and service availability.", category, retry) from None
    except (OSError, http.client.HTTPException) as exc:
        raise ModelError("Cannot reach the model service. Check that Ollama is running or that the selected API is reachable.", "transport") from exc
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ModelError("Provider returned invalid JSON.", "format") from exc


def extract_json(content: str) -> dict[str, Any]:
    if not isinstance(content, str):
        raise ModelError("The model did not return text content.")
    content = content.strip()
    if content.startswith("<think>"):
        end = content.find("</think>")
        if end < 0:
            raise ModelError("The model returned an incomplete reasoning block.")
        content = content[end + len("</think>"):].strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        result = json.loads(content)
    except json.JSONDecodeError:
        raise ModelError("The model did not return valid JSON. Retry with a coding/instruction model or a smaller task.") from None
    if not isinstance(result, dict):
        raise ModelError("The model must return a JSON object.")
    return cast(dict[str, Any], result)


class ModelClient:
    def __init__(self, provider: str, model: str, options: dict[str, Any] | None = None) -> None:
        if provider not in PROVIDERS:
            raise ValueError("Unknown provider.")
        if not isinstance(model, str) or not model.strip() or len(model) > 200:
            raise ValueError("Enter a model name.")
        if provider == "ollama" and "embed" in model.lower():
            raise ValueError("Choose a chat/coding model. Embedding models cannot generate apps.")
        self.provider, self.model = provider, model.strip()
        self.options = validate_options(options or {})
        self.last_usage: dict[str, int] = {}
        self.last_metadata: dict[str, Any] = {}
        self.planner_budget: PlannerBudget | None = None
        self.recovery_mode = "initial"
        self.continuation_prefix = ""

    def complete(self, system: str, prompt: str) -> dict[str, Any]:
        try:
            return self._complete(system, prompt)
        except ModelError as exc:
            if self.planner_budget and exc.category == "format":
                raise ModelError(str(exc), "parse_error") from None
            raise

    def _complete(self, system: str, prompt: str) -> dict[str, Any]:
        self.last_usage = {}
        output = self.planner_budget.max_output_tokens if self.planner_budget else self.options['num_predict']
        self.last_metadata = {'requested_max_output_tokens':output,'finish_reason':None,'observed_output_tokens':None,'transport_attempted':False,'timeout_seconds':self.options['timeout_seconds']}
        messages = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
        if self.recovery_mode == "continuation":
            messages += [{"role":"assistant","content":self.continuation_prefix},
                         {"role":"user","content":"Continue exactly where the previous response was cut off, no recap. Return only the missing JSON suffix, without fences or repeating the prefix."}]
        elif self.recovery_mode in {"shortening", "budget_compaction"}:
            if system == CODE:
                messages.append({"role":"user","content":"Return a fresh complete JSON object with only necessary changed files or exact edits. Keep the approved behavior and tests. Prefer small exact edits over rewriting unchanged files. Omit explanatory prose and never use placeholders or truncated file contents."})
            else:
                messages.append({"role":"user","content":"Emit the minimum viable SCHEMA-COMPLETE proposal. Keep all required fields, full task instructions, acceptance checks, feature indexes and requested behavior. Use short strings and few focused tasks. Omit explanatory prose; do not omit checks, invent a skeleton schema or weaken approval scope. Return a fresh complete JSON object."})
        complete_recovery = system == CODE and json.loads(prompt).get("response_mode") == "complete_files"
        if complete_recovery:
            messages[0]["content"] += "\nRESPONSE RECOVERY: Return a nonempty files object containing COMPLETE changed source files and optional summary. Do not return edits, diffs or ellipses. Read the current source in the request. This recovery requirement overrides the earlier preference for exact edits."
        self.last_metadata.update(input_characters=sum(len(m['content']) for m in messages),
                                  effective_request_sha256=hashlib.sha256(json.dumps(messages).encode()).hexdigest())
        if self.provider == "gemini" and self.planner_budget and (system == PLAN or self.planner_budget.thinking_budget > 0):
            key = key_for('gemini')
            if not key: raise ModelError('Set GEMINI_API_KEY in your local .env file.', 'auth')
            generation: dict[str, Any] = {'maxOutputTokens':output,'temperature':0.2}
            if self.options['structured_outputs']:
                generation['responseMimeType'] = 'application/json'
            if self.planner_budget.thinking_budget:
                generation['thinkingConfig'] = {'thinkingBudget':self.planner_budget.thinking_budget}
            gemini_base = PROVIDERS['gemini'][0]
            if not gemini_base: raise ModelError('Invalid Gemini adapter.', 'provider')
            self.last_metadata['transport_attempted'] = True
            result = request_json(gemini_base.removesuffix('/openai')+'/models/'+urllib.parse.quote(self.model,safe='')+':generateContent', {
                'systemInstruction':{'parts':[{'text':messages[0]['content']}]},
                'contents':[{'role':'model' if m['role']=='assistant' else 'user','parts':[{'text':m['content']}]} for m in messages[1:]],
                'generationConfig':generation,
            }, {'x-goog-api-key':key}, timeout=self.options["timeout_seconds"])
            self._identity(result)
            usage = result.get('usageMetadata',{})
            if not isinstance(usage,dict): usage = {}
            for source,target in [('promptTokenCount','prompt_tokens'),('candidatesTokenCount','visible_output_tokens'),('thoughtsTokenCount','thinking_tokens')]:
                if type(usage.get(source)) is int and usage[source] >= 0: self.last_usage[target] = usage[source]
            if 'visible_output_tokens' in self.last_usage or 'thinking_tokens' in self.last_usage:
                self.last_usage['completion_tokens'] = self.last_usage.get('visible_output_tokens',0)+self.last_usage.get('thinking_tokens',0)
            candidates = result.get('candidates')
            if not isinstance(candidates,list) or not candidates or not isinstance(candidates[0],dict): raise ModelError('Gemini did not return a candidate.','format')
            reason = candidates[0].get('finishReason',candidates[0].get('finish_reason'))
            parts = candidates[0].get('content',{}).get('parts',[]) if isinstance(candidates[0].get('content'),dict) else []
            content = ''.join(part['text'] for part in parts if isinstance(part,dict) and isinstance(part.get('text'),str) and not part.get('thought'))
            self._finish(reason,content)
        elif self.provider == "ollama":
            schema: dict[str, Any] | str = PLAN_SCHEMA if system == PLAN else CODE_SCHEMA if system == CODE else "json"
            if complete_recovery:
                schema = COMPLETE_CODE_SCHEMA
            self.last_metadata['transport_attempted'] = True
            result = request_json(os.getenv("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/") + "/api/chat", {
                "model": self.model, "messages": messages, "stream": False, "format": schema if self.options["structured_outputs"] else "json", "keep_alive": "5m",
                "options": {"temperature": 0.2, "num_ctx": self.options["num_ctx"], "num_predict": output},
            }, timeout=self.options['timeout_seconds'])
            self._identity(result)
            self.last_usage = {label: result[key] for key, label in [("prompt_eval_count", "prompt_tokens"), ("eval_count", "completion_tokens")] if type(result.get(key)) is int and result[key] >= 0}
            self._finish(result.get("done_reason"), result.get("message", {}).get("content", "") if isinstance(result.get("message"),dict) else "")
            message = result.get("message")
            if not isinstance(message, dict):
                raise ModelError("Ollama did not return a chat message.")
            content = message.get("content", "")
        else:
            variable = PROVIDERS[self.provider][1]
            try:
                base = endpoint(self.provider)
            except ValueError as exc:
                raise ModelError(str(exc), "configuration") from None
            key = key_for(self.provider)
            if not key:
                raise ModelError(f"Set {variable} in your local .env file and restart. Never put keys in project prompts.", "auth")
            payload: dict[str, Any] = {"model":self.model,"messages":messages,"temperature":0.2,"max_tokens":output,"stream":False}
            if self.options['structured_outputs']:
                payload['response_format'] = {"type":"json_object"}
            if self.provider == 'cloudflare':
                payload['options'] = {'rejectIfBusy':True}
            self.last_metadata['transport_attempted'] = True
            result = request_json(base + "/chat/completions", payload,
                                  {"Authorization":"Bearer "+key}, timeout=self.options["timeout_seconds"])
            self._identity(result)
            usage = result.get("usage", {})
            self.last_usage = {key: usage[key] for key in ("prompt_tokens", "completion_tokens") if isinstance(usage, dict) and type(usage.get(key)) is int and usage[key] >= 0}
            choices = result.get("choices")
            if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
                raise ModelError("Provider did not return a chat completion.")
            self._finish(choices[0].get("finish_reason", choices[0].get("finishReason")), choices[0].get("message",{}).get("content", "") if isinstance(choices[0].get("message"),dict) else "")
            message = choices[0].get("message")
            if not isinstance(message, dict):
                raise ModelError("Provider did not return a chat message.")
            content = message.get("content", "")
        if self.recovery_mode == 'continuation': content = self.continuation_prefix + content
        return extract_json(content)

    def _identity(self, result: dict[str, Any]) -> None:
        for field,value in [('response_model',result.get('modelVersion',result.get('model'))),
                            ('response_provider',result.get('provider'))]:
            if isinstance(value,str) and re.fullmatch(r'[A-Za-z0-9_./:@+-]{1,200}',value):
                if not any(secret and secret in value for provider in PROVIDERS if (secret := key_for(provider))):
                    self.last_metadata[field] = value

    def _finish(self, reason: Any, content: Any) -> None:
        reason = reason[:64] if isinstance(reason,str) else None
        self.last_metadata.update(finish_reason=reason, observed_output_tokens=self.last_usage.get('completion_tokens'))
        if reason and reason.upper() in {'LENGTH','MAX_TOKENS'}:
            partial = content if isinstance(content,str) and len(content) <= 200000 else ''
            raise ModelError('Response reached its reserved output budget; JSON was not accepted.', 'truncated_output', partial_content=partial)


def connection_info() -> dict[str, Any]:
    info: dict[str, Any] = {p: {"configured": p == "ollama" or bool(key_for(p)), "key_variable": v} for p, (_, v) in PROVIDERS.items()}
    for provider in info:
        if provider == 'cloudflare':
            try: endpoint(provider)
            except ValueError as exc: info[provider]['configuration_detail'] = str(exc)
    try:
        data = request_json(os.getenv("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/") + "/api/tags", timeout=5)
        info["ollama"].update(connected=True, models=[m["name"] for m in data.get("models", [])])
    except (ValueError, KeyError, TypeError):
        info["ollama"].update(connected=False, models=[])
    return info
