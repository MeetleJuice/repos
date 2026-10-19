"""Small provider adapter. No provider SDKs or automatic paid fallbacks."""
import json
import http.client
import os
import urllib.error
import urllib.request
from typing import Any, cast

from .routing import validate_options
from .schemas import PLAN_SCHEMA, CODE_SCHEMA, COMPLETE_CODE_SCHEMA
from .prompts import PLAN, CODE

PROVIDERS = {
    "ollama": (None, None),
    "groq": ("https://api.groq.com/openai/v1", "GROQ_API_KEY"),
    "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai", "GEMINI_API_KEY"),
}


class ModelError(ValueError):
    def __init__(self, message: str, category: str = "format", retry_after: int = 0) -> None:
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

    def complete(self, system: str, prompt: str) -> dict[str, Any]:
        self.last_usage = {}
        messages = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
        complete_recovery = system == CODE and json.loads(prompt).get("response_mode") == "complete_files"
        if complete_recovery:
            messages[0]["content"] += "\nRESPONSE RECOVERY: Return a nonempty files object containing COMPLETE changed source files and optional summary. Do not return edits, diffs or ellipses. Read the current source in the request. This recovery requirement overrides the earlier preference for exact edits."
        if self.provider == "ollama":
            schema: dict[str, Any] | str = PLAN_SCHEMA if system == PLAN else CODE_SCHEMA if system == CODE else "json"
            if complete_recovery:
                schema = COMPLETE_CODE_SCHEMA
            result = request_json(os.getenv("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/") + "/api/chat", {
                "model": self.model, "messages": messages, "stream": False, "format": schema if self.options["structured_outputs"] else "json", "keep_alive": "5m",
                "options": {"temperature": 0.2, "num_ctx": self.options["num_ctx"], "num_predict": self.options["num_predict"]},
            })
            self.last_usage = {label: result[key] for key, label in [("prompt_eval_count", "prompt_tokens"), ("eval_count", "completion_tokens")] if type(result.get(key)) is int and result[key] >= 0}
            if result.get("done_reason") == "length":
                raise ModelError("Ollama reached the output limit. Use smaller tasks or increase the output limit within the context budget.", "truncated")
            message = result.get("message")
            if not isinstance(message, dict):
                raise ModelError("Ollama did not return a chat message.")
            content = message.get("content", "")
        else:
            base, variable = PROVIDERS[self.provider]
            if base is None or variable is None:
                raise ModelError("Invalid cloud provider adapter.", "provider")
            key = os.getenv(variable) or (os.getenv("OPENROUTER_KEY") if self.provider == "openrouter" else None)
            if not key:
                raise ModelError(f"Set {variable} in your local .env file and restart. Never put keys in project prompts.", "auth")
            result = request_json(base + "/chat/completions", {
                "model": self.model, "messages": messages, "temperature": 0.2,
                "max_tokens": self.options["num_predict"], "response_format": {"type": "json_object"},
            }, {"Authorization": "Bearer " + key}, timeout=60)
            usage = result.get("usage", {})
            self.last_usage = {key: usage[key] for key in ("prompt_tokens", "completion_tokens") if isinstance(usage, dict) and type(usage.get(key)) is int and usage[key] >= 0}
            choices = result.get("choices")
            if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
                raise ModelError("Provider did not return a chat completion.")
            if choices[0].get("finish_reason") == "length":
                raise ModelError("Provider reached the output limit. Use smaller tasks or increase the output limit.", "truncated")
            message = choices[0].get("message")
            if not isinstance(message, dict):
                raise ModelError("Provider did not return a chat message.")
            content = message.get("content", "")
        return extract_json(content)


def connection_info() -> dict[str, Any]:
    info: dict[str, Any] = {p: {"configured": p == "ollama" or bool(os.getenv(v or "") or p == "openrouter" and os.getenv("OPENROUTER_KEY")), "key_variable": v} for p, (_, v) in PROVIDERS.items()}
    try:
        data = request_json(os.getenv("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/") + "/api/tags", timeout=5)
        info["ollama"].update(connected=True, models=[m["name"] for m in data.get("models", [])])
    except (ValueError, KeyError, TypeError):
        info["ollama"].update(connected=False, models=[])
    return info
