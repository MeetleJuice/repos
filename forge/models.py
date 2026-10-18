"""Small provider adapter. No provider SDKs or automatic paid fallbacks."""
import json
import os
import urllib.error
import urllib.request

PROVIDERS = {
    "ollama": (None, None),
    "groq": ("https://api.groq.com/openai/v1", "GROQ_API_KEY"),
    "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY"),
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai", "GEMINI_API_KEY"),
}


def request_json(url, payload=None, headers=None, timeout=300):
    body = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            data = response.read(2_000_001)
            if len(data) > 2_000_000:
                raise ValueError("Model response exceeded 2 MB; use smaller tasks.")
            return json.loads(data)
    except urllib.error.HTTPError as exc:
        # Provider bodies can echo submitted content. Do not leak them or API keys.
        raise ValueError(f"Provider returned HTTP {exc.code}. Check the model name, key, quota, and provider availability.") from None
    except (urllib.error.URLError, TimeoutError) as exc:
        raise ValueError("Cannot reach the model service. Check that Ollama is running or that the selected API is reachable.") from exc


def extract_json(content):
    content = content.strip()
    if "</think>" in content:
        content = content.split("</think>")[-1].strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        result = json.loads(content)
    except json.JSONDecodeError:
        raise ValueError("The model did not return valid JSON. Retry with a coding/instruction model or a smaller task.") from None
    if not isinstance(result, dict):
        raise ValueError("The model must return a JSON object.")
    return result


class ModelClient:
    def __init__(self, provider, model):
        if provider not in PROVIDERS:
            raise ValueError("Unknown provider.")
        if not isinstance(model, str) or not model.strip() or len(model) > 200:
            raise ValueError("Enter a model name.")
        self.provider, self.model = provider, model.strip()

    def complete(self, system, prompt):
        messages = [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
        if self.provider == "ollama":
            result = request_json(os.getenv("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/") + "/api/chat", {
                "model": self.model, "messages": messages, "stream": False, "format": "json",
                "options": {"temperature": 0.2, "num_ctx": 16384, "num_predict": 8192},
            })
            content = result.get("message", {}).get("content", "")
        else:
            base, variable = PROVIDERS[self.provider]
            key = os.getenv(variable)
            if not key:
                raise ValueError(f"Set {variable} in your local .env file and restart. Never put keys in project prompts.")
            result = request_json(base + "/chat/completions", {
                "model": self.model, "messages": messages, "temperature": 0.2,
                "max_tokens": 8192, "response_format": {"type": "json_object"},
            }, {"Authorization": "Bearer " + key})
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
        return extract_json(content)


def connection_info():
    info = {p: {"configured": p == "ollama" or bool(os.getenv(v)), "key_variable": v} for p, (_, v) in PROVIDERS.items()}
    try:
        data = request_json(os.getenv("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/") + "/api/tags", timeout=5)
        info["ollama"].update(connected=True, models=[m["name"] for m in data.get("models", [])])
    except (ValueError, KeyError, TypeError):
        info["ollama"].update(connected=False, models=[])
    return info
