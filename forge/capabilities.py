"""Versioned model ceilings and conservative planner output reservation."""
from __future__ import annotations
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any
from .credentials import atomic_text
from .schemas import PLAN_SCHEMA


@dataclass(frozen=True)
class Capability:
    max_output_tokens: int
    max_context_tokens: int
    supports_thinking_budget: bool
    thinking_budget_default: int
    estimated: bool
    source: str


@dataclass(frozen=True)
class PlannerBudget:
    max_output_tokens: int
    text_output_tokens: int
    thinking_budget: int
    input_estimate_tokens: int
    estimated_required_tokens: int


class CapabilityRegistry:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path
        self.builtin = json.loads(Path(__file__).with_name('model-capabilities-v1.json').read_text(encoding='utf-8'))
        self.overrides: dict[str, Any] = {}
        try:
            if path:
                saved = json.loads(path.read_text(encoding='utf-8'))
                if saved.get('schema') == 1 and isinstance(saved.get('models'), dict): self.overrides = saved['models']
        except (OSError, ValueError, AttributeError): pass

    def get(self, provider: str, model: str, options: dict[str, Any] | None = None) -> Capability:
        key = provider+'/'+model
        record = self.overrides.get(key, self.builtin['models'].get(key, self.builtin['defaults']))
        fallback = self.builtin['defaults']
        if not isinstance(record, dict): record = fallback
        output, context = record.get('max_output_tokens'), record.get('max_context_tokens')
        if type(output) is not int or not 256 <= output <= 1048576: output = fallback['max_output_tokens']
        if type(context) is not int or not 256 <= context <= 16777216: context = max(output, fallback['max_context_tokens'])
        thinking = record.get('supports_thinking_budget') is True
        budget = record.get('thinking_budget_default', 0)
        if type(budget) is not int or not 0 <= budget <= 4096: budget = 1024 if thinking else 0
        if provider == 'ollama':
            options = options or {}
            context = options.get('num_ctx', 16384)
            output = min(options.get('num_predict', 8192), context-1)
            thinking, budget = False, 0
        return Capability(output, context, thinking, budget, record.get('estimated', True) is not False, str(record.get('source', 'Unknown.'))[:300])

    def discover_openrouter(self, entries: list[Any]) -> None:
        """Persist published per-model limits; unknown free-router values stay estimated."""
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get('id'), str): continue
            model = entry['id']
            if len(model) > 200: continue
            top = entry.get('top_provider')
            output = top.get('max_completion_tokens') if isinstance(top, dict) else None
            output = output if output is not None else entry.get('max_completion_tokens')
            context = entry.get('context_length')
            published = type(output) is int and 256 <= output <= 1048576
            output_limit: int = output if isinstance(output,int) and not isinstance(output,bool) and published else 8192
            valid_context = type(context) is int and 256 <= context <= 16777216
            if not published and not valid_context: continue
            self.overrides['openrouter/'+model] = {
                'max_output_tokens':output_limit,
                'max_context_tokens':context if valid_context else max(131072, output_limit),
                'supports_thinking_budget':False,'thinking_budget_default':0,
                'estimated':not (published and valid_context),
                'source':'OpenRouter /models published top_provider.max_completion_tokens/context_length; missing fields use conservative estimates.'}
        if self.path:
            atomic_text(self.path, json.dumps({'schema':1,'models':self.overrides}, indent=2)+'\n')

    def reserve(self, provider: str, model: str, options: dict[str, Any], system: str, prompt: str) -> PlannerBudget:
        cap = self.get(provider, model, options)
        try: payload = json.loads(prompt)
        except ValueError: payload = {}
        if not isinstance(payload, dict): payload = {}
        proposals = [payload.get(k) for k in ('previous_proposal','existing_project','starter_example_plan')]
        valid_proposals: list[dict[str, Any]] = [p for p in proposals if isinstance(p,dict)]
        tasks = max([4]+[len(p.get('tasks',[])) for p in valid_proposals if isinstance(p.get('tasks'),list)])
        features = max([4]+[len(p.get('features',[])) for p in valid_proposals if isinstance(p.get('features'),list)])
        checks = max([8,features*2+2]+[len(p.get('checks',[])) for p in valid_proposals if isinstance(p.get('checks'),list)])
        estimate = 512 + len(PLAN_SCHEMA['required'])*40 + min(tasks,40)*320 + min(checks,80)*240 + min(features,40)*100
        thinking = cap.thinking_budget_default if cap.supports_thinking_budget else 0
        # Conservative heuristic (about two UTF-8 bytes/token), not a tokenizer
        # guarantee or billing measurement. Reserve schema/message framing too.
        input_estimate = (len((system+prompt).encode('utf-8',errors='surrogatepass')) + len(json.dumps(PLAN_SCHEMA)) + 1)//2 + 512
        room = min(cap.max_output_tokens, cap.max_context_tokens-input_estimate)
        text = max(self.builtin['planner_output_floor'], options.get('num_predict',4096), estimate)
        if text+thinking > room: raise ValueError('Planner output reservation exceeds the model output/context budget. Use a larger-capacity configured model or narrow the proposal; no request was sent.')
        return PlannerBudget(text+thinking, text, thinking, input_estimate, estimate)
