"""Small provider adapter. No provider SDKs or automatic paid fallbacks."""
import json
import re
import hashlib
import http.client
import time
import os
import urllib.error
import urllib.request
import urllib.parse
import threading
from typing import Any, Callable, cast

from . import __version__
from .http_io import read_bounded, ResponseTooLarge
from .build_contract import execution_directive
from .routing import validate_options
from .capabilities import PlannerBudget
from .schemas import PLAN_SCHEMA, CODE_SCHEMA, COMPLETE_CODE_SCHEMA
import copy
from .prompts import PLAN, CODE
from .guided import planner_schema

from .providers import PROVIDERS as PROVIDERS, LOCAL_PROVIDERS, endpoint, key_for



class ModelError(ValueError):
    def __init__(self, message: str, category: str = "format", retry_after: int = 0, partial_content: str = "", http_status: int | None = None, transport_kind: str | None = None) -> None:
        self.transport_kind=transport_kind
        self.http_status=http_status if type(http_status) is int and 100<=http_status<=599 else None
        self.partial_content = partial_content
        self.category = category
        self.retry_after = retry_after
        super().__init__(message)


class NoLocalRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> Any:
        fp.close()
        raise ModelError('Local runtime redirects are refused. Use its direct loopback /v1 endpoint.', 'configuration')


def request_json(url: str, payload: dict[str, Any] | None = None, headers: dict[str, str] | None = None, timeout: float = 300, local_only: bool = False) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    body = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(url, data=body, headers={"User-Agent": "IdeaFoundry/" + __version__ + " desktop-client", "Content-Type": "application/json", **(headers or {})})
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoLocalRedirect()).open if local_only else urllib.request.urlopen
        with opener(req, timeout=timeout) as response:
            data = read_bounded(response,deadline)
            parsed = json.loads(data)
            if not isinstance(parsed, dict):
                raise ModelError("Provider response must be a JSON object.")
            return parsed
    except ResponseTooLarge:
        raise ModelError("Model response exceeded 2 MB; use smaller tasks.", "size") from None
    except urllib.error.HTTPError as exc:
        # Provider bodies can echo submitted content. Do not leak them or API keys.
        raw_retry = exc.headers.get('Retry-After', '') if exc.headers else ''
        retry = min(300, int(raw_retry)) if len(raw_retry) <= 9 and raw_retry.isdigit() else 30 if exc.code == 429 else 0
        if exc.fp is not None:
            exc.close()
        category = "rate_limit" if exc.code == 429 else "auth" if exc.code in {401, 403} else "quota" if exc.code == 402 else "model" if exc.code == 404 else "request" if exc.code == 400 else "provider"
        raise ModelError(f"Provider returned HTTP {exc.code}. Check the key, model access, quota and service availability.", category, retry, http_status=exc.code) from None
    except TimeoutError as exc:
        raise ModelError("Model request timed out or exceeded its elapsed response-read budget. Trying another configured model may help.", "transport",transport_kind='timeout') from exc
    except urllib.error.URLError as exc:
        kind='timeout' if isinstance(exc.reason,TimeoutError) else 'connection'
        message='Model connection timed out.' if kind=='timeout' else 'Cannot reach the selected model service. Check the runtime or API connection.'
        raise ModelError(message,'transport',transport_kind=kind) from None
    except (OSError, http.client.HTTPException) as exc:
        raise ModelError("Cannot reach the selected model service. Start the selected local runtime or check the API connection.", "transport",transport_kind='connection') from exc
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


def output_contract(system: str) -> str:
    if (stage_schema:=planner_schema(system)) is not None:
        return system+'\nSTAGE OUTPUT SCHEMA:'+json.dumps(stage_schema)+'\nReturn an instance of this schema, never the schema itself or a wrapper. Use exact enum values. Checks and manual_checks are arrays of named objects, not dictionaries or strings. Omit unused optional fields instead of returning null. Keep all requested behavior; only the complete reviewed proposal can be approved.'
    if system != PLAN: return system
    return system + "\nAUTHORITATIVE ROOT OUTPUT CONTRACT (not a wrapper): " + json.dumps({"required":PLAN_SCHEMA["required"],"browser_behavior_evidence":"manual_checks or browser_checks"},separators=(",", ":")) + "\nReturn the proposal itself, never a proposal/plan wrapper, JSON schema or source files. Be concise; every feature needs task and acceptance coverage."


def request_schema(system: str, prompt: str, complete: bool = False) -> dict[str,Any] | str:
    """Constrain local JSON generation to this stage and already approved scope."""
    schema: dict[str,Any]=copy.deepcopy(planner_schema(system) or (PLAN_SCHEMA if system==PLAN else COMPLETE_CODE_SCHEMA if system==CODE and complete else CODE_SCHEMA if system==CODE else {}))
    if not schema:return 'json'
    try:payload=json.loads(prompt)
    except ValueError:return schema
    if not isinstance(payload,dict):return schema
    from .outline_planning import ACCEPTANCE_PROMPT
    if system == ACCEPTANCE_PROMPT and payload.get('planning_stage') == 'acceptance' and isinstance(payload.get('scope'),dict):
        features=payload['scope'].get('features')
        if isinstance(features,list) and 1 <= len(features) <= 12:
            for field in ('checks','manual_checks','browser_checks'):
                schema['properties'][field]['items']['properties']['feature_indexes']['items']['enum']=list(range(len(features)))
    profile=payload.get('builder_profile')
    if planner_schema(system) is not None and payload.get('planning_stage') in {'tasks','feature_tasks'} and isinstance(profile,dict):
        props=schema['properties']['tasks']['items']['properties']
        for key,limit in (('files',profile.get('max_editable_files')),('feature_indexes',profile.get('max_feature_indexes'))):
            if key in props and type(limit) is int and 1<=limit<=3:props[key]['maxItems']=limit
    packet=payload.get('task_packet')
    if system==CODE and isinstance(packet,dict) and packet.get('structured') is True:
        names=packet.get('files')
        if isinstance(names,list) and 1<=len(names)<=3 and all(isinstance(name,str) for name in names):
            schema['properties']['files']={'type':'object','properties':{name:{'type':'string'} for name in names},'additionalProperties':False,'minProperties':1}
            if 'edits' in schema['properties']:schema['properties']['edits']['items']['properties']['file']['enum']=names
            schema['properties']['already_satisfied']['properties']['evidence']['items']['properties']['file']['enum']=names
    return schema


class ModelClient:
    def __init__(self, provider: str, model: str, options: dict[str, Any] | None = None) -> None:
        if provider not in PROVIDERS:
            raise ValueError("Unknown provider.")
        if not isinstance(model, str) or not model.strip() or len(model) > 200:
            raise ValueError("Enter a model name.")
        if provider in LOCAL_PROVIDERS and "embed" in model.lower():
            raise ValueError("Choose a chat/coding model. Embedding models cannot generate apps.")
        self.provider, self.model = provider, model.strip()
        self.options = validate_options(options or {})
        self.last_usage: dict[str, int] = {}
        self.last_metadata: dict[str, Any] = {}
        self.planner_budget: PlannerBudget | None = None
        self.recovery_mode = "initial"
        self.continuation_prefix = ""
        self.stream_progress: Callable[[str],None] | None = None
        self.cancel_event = threading.Event()

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
        self.last_metadata = {'requested_max_output_tokens':output,'finish_reason':None,'observed_output_tokens':None,'transport_attempted':False,'timeout_seconds':self.options['timeout_seconds'],
                              'configured_num_ctx':self.options['num_ctx'],'structured_outputs_requested':self.options['structured_outputs']}
        messages = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
        messages[0]["content"] = output_contract(system)
        if self.recovery_mode == "continuation":
            messages += [{"role":"assistant","content":self.continuation_prefix},
                         {"role":"user","content":"Continue exactly where the previous response was cut off, no recap. Return only the missing JSON suffix, without fences or repeating the prefix."}]
        elif self.recovery_mode in {"shortening", "budget_compaction"}:
            if system == CODE:
                messages.append({"role":"user","content":"Return a fresh complete JSON object with only necessary changed files or exact edits. Keep the approved behavior and tests. Prefer small exact edits over rewriting unchanged files. Omit explanatory prose and never use placeholders or truncated file contents."})
            elif planner_schema(system) is not None:
                messages.append({'role':'user','content':'Return a fresh minimum-size JSON object matching ONLY this stage schema. Preserve all requested features and acceptance checks in an outline; for a task batch return only tasks for the target feature indexes. Keep every required field. Omit explanatory prose and wrappers.'})
            else:
                messages.append({"role":"user","content":"Emit the minimum viable SCHEMA-COMPLETE proposal. Keep all required fields, full task instructions, acceptance checks, feature indexes and requested behavior. Use short strings and few focused tasks. Omit explanatory prose; do not omit checks, invent a skeleton schema or weaken approval scope. Return a fresh complete JSON object."})
        complete_recovery = system == CODE and json.loads(prompt).get("response_mode") == "complete_files"
        if complete_recovery:
            messages[0]["content"] += "\nRESPONSE RECOVERY: Return a nonempty files object containing COMPLETE changed source files and optional summary. Do not return edits, diffs or ellipses. Read the current source in the request. For approved focused context, request_context is allowed to read missing listed files within its retrieval limit. For structured tasks with no needed changes, the explicit already_satisfied source-evidence response is also allowed; do not invent a change. This recovery requirement overrides the earlier preference for exact edits."
        if system == CODE and (directive := execution_directive(json.loads(prompt))):
            messages.append({"role":"user","content":directive})
        self.last_metadata.update(input_characters=sum(len(m['content']) for m in messages),
                                  effective_request_sha256=hashlib.sha256(json.dumps(messages).encode()).hexdigest())
        if self.provider == "gemini" and self.planner_budget and (system == PLAN or planner_schema(system) is not None or self.planner_budget.thinking_budget > 0):
            self.last_metadata['api_family']='gemini_generate_content'
            key = key_for('gemini')
            if not key: raise ModelError('Set GEMINI_API_KEY in your local .env file.', 'auth')
            generation: dict[str, Any] = {'maxOutputTokens':output,'temperature':0.2}
            if self.options['structured_outputs']:
                generation['responseMimeType'] = 'application/json'
            self.last_metadata['response_format_mode']='json_mime' if self.options['structured_outputs'] else 'off'
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
            self.last_metadata['api_family']='ollama_chat'
            schema = request_schema(system,prompt,complete_recovery)
            self.last_metadata['response_format_mode']='json_schema' if isinstance(schema,dict) and self.options['structured_outputs'] else 'json_object'
            self.last_metadata['transport_attempted'] = True
            url=os.getenv("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/") + "/api/chat"
            payload: dict[str,Any] = {
                "model": self.model, "messages": messages, "stream": False, "format": schema if self.options["structured_outputs"] else "json", "keep_alive": "5m",
                "options": {"temperature": 0.2, "num_ctx": self.options["num_ctx"], "num_predict": output},
            }
            if self.stream_progress:
                from .streaming import stream_chat
                result=stream_chat(url,payload,{},self.options['timeout_seconds'],'ollama',self.cancel_event,self.stream_progress)
            else:result=request_json(url,payload,timeout=self.options['timeout_seconds'])
            self._identity(result)
            self.last_usage = {label: result[key] for key, label in [("prompt_eval_count", "prompt_tokens"), ("eval_count", "completion_tokens")] if type(result.get(key)) is int and result[key] >= 0}
            for source,target in [('load_duration','ollama_load_seconds'),('eval_duration','ollama_eval_seconds'),('prompt_eval_duration','ollama_prompt_seconds')]:
                if type(result.get(source)) is int and 0<=result[source]<=10**15:self.last_metadata[target]=round(result[source]/1_000_000_000,3)
            if self.last_metadata.get('ollama_eval_seconds',0)>0 and type(result.get('eval_count')) is int and 0<=result['eval_count']<=1_000_000_000:
                self.last_metadata['ollama_tokens_per_second']=round(result['eval_count']/self.last_metadata['ollama_eval_seconds'],2)
            self._finish(result.get("done_reason"), result.get("message", {}).get("content", "") if isinstance(result.get("message"),dict) else "")
            message = result.get("message")
            if not isinstance(message, dict):
                raise ModelError("Ollama did not return a chat message.")
            content = message.get("content", "")
        else:
            self.last_metadata['api_family']='openai_chat'
            variable = PROVIDERS[self.provider][1]
            try:
                base = endpoint(self.provider)
            except ValueError as exc:
                raise ModelError(str(exc), "configuration") from None
            key = key_for(self.provider)
            if not key and self.provider != 'local':
                raise ModelError(f"Set {variable} in your local .env file and restart. Never put keys in project prompts.", "auth")
            payload = {"model":self.model,"messages":messages,"temperature":0.2,"max_tokens":output,"stream":False}
            if self.options['structured_outputs']:
                payload['response_format'] = {"type":"json_object"}
            self.last_metadata['response_format_mode']='json_object' if self.options['structured_outputs'] else 'off'
            if self.provider == 'cloudflare':
                payload['options'] = {'rejectIfBusy':True}
            self.last_metadata['transport_attempted'] = True
            headers={"Authorization":"Bearer "+key} if key else {}
            if self.provider == 'local':
                if self.stream_progress:
                    from .streaming import stream_chat
                    result=stream_chat(base+'/chat/completions',payload,headers,self.options['timeout_seconds'],'local',self.cancel_event,self.stream_progress)
                else:result = request_json(base+'/chat/completions',payload,headers,timeout=self.options['timeout_seconds'],local_only=True)
            else:
                result = request_json(base+'/chat/completions',payload,headers,timeout=self.options['timeout_seconds'])
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
    try:
        local_key=key_for('local')
        data=request_json(endpoint('local')+'/models',None,
                          {'Authorization':'Bearer '+local_key} if local_key else {},timeout=3,local_only=True)
        entries=data.get('data',[])
        if not isinstance(entries,list):raise ValueError('Invalid local model catalogue.')
        names=[entry['id'] for entry in entries if isinstance(entry,dict) and isinstance(entry.get('id'),str) and re.fullmatch(r'[A-Za-z0-9_./:@+-]{1,200}',entry['id'])]
        info['local'].update(configured=True,connected=True,models=names)
    except (ValueError, KeyError, TypeError):
        info['local'].update(configured=True,connected=False,models=[],configuration_detail='Start the OpenAI-compatible server in LM Studio (port 1234), or set LOCAL_API_URL for llama.cpp. Check local server authentication if enabled.')
    return info
