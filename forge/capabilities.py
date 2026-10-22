"""Versioned model ceilings and conservative planner output reservation."""
from __future__ import annotations
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any
from .credentials import atomic_text
from .schemas import PLAN_SCHEMA,CODE_SCHEMA


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


class BudgetError(ValueError):
    def __init__(self, message: str, facts: dict[str,Any]) -> None:
        self.facts=facts
        super().__init__(message)


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

    def get(self, provider: str, model: str, options: dict[str, Any] | None = None, role: str = 'coder') -> Capability:
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
        if provider in {'ollama','local'}:
            options = options or {}
            configured = options.get('num_ctx', 16384)
            context = min(configured,context) if record.get('context_limit_published') is True else configured
            # Planner num_predict is a floor, not a model output ceiling. The
            # reservation below still accounts for input within this context.
            output = context-1 if role == 'planner' else min(options.get('num_predict', 8192), context-1)
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
                'output_limit_published':published,'context_limit_published':valid_context,
                'estimated':not (published and valid_context),
                'source':'OpenRouter /models published top_provider.max_completion_tokens/context_length; missing fields use conservative estimates.'}
        if self.path:
            atomic_text(self.path, json.dumps({'schema':1,'models':self.overrides}, indent=2)+'\n')

    def discover_models(self, provider: str, entries: list[Any]) -> None:
        if provider == 'openrouter':
            self.discover_openrouter(entries)
            return
        changed = False
        for entry in entries:
            if not isinstance(entry,dict): continue
            model = entry.get('name' if provider in {'gemini','cloudflare'} else 'id')
            if not isinstance(model,str) or len(model)>210: continue
            model = model.removeprefix('models/')
            output = entry.get('outputTokenLimit',entry.get('max_completion_tokens',entry.get('max_output_tokens')))
            context = entry.get('inputTokenLimit',entry.get('context_length',entry.get('max_context_length',entry.get('context_window'))))
            valid_output=type(output) is int and 256<=output<=1048576
            valid_context=type(context) is int and 256<=context<=16777216
            if not valid_output and not valid_context:continue
            previous = self.get(provider,model)
            resolved_output=output if isinstance(output,int) and valid_output else previous.max_output_tokens
            # Input-only limits are used conservatively as joint budget room.
            self.overrides[provider+'/'+model] = {'max_output_tokens':resolved_output,
                'max_context_tokens':context if valid_context else max(previous.max_context_tokens,resolved_output),
                'supports_thinking_budget':previous.supports_thinking_budget,'thinking_budget_default':previous.thinking_budget_default,
                'output_limit_published':valid_output,'context_limit_published':valid_context,
                'estimated':not (valid_output and valid_context),'source':'Authenticated catalogue limits; missing fields remain explicitly estimated.'}
            changed = True
        if changed and self.path:
            atomic_text(self.path,json.dumps({'schema':1,'models':self.overrides},indent=2)+'\n')

    def reserve(self, provider: str, model: str, options: dict[str, Any], system: str, prompt: str, compact: bool = False, *, contract_system: str | None = None) -> PlannerBudget:
        cap = self.get(provider, model, options, role='planner')
        try: payload = json.loads(prompt)
        except ValueError: payload = {}
        if not isinstance(payload, dict): payload = {}
        proposals = [payload.get(k) for k in ('previous_proposal','existing_project','starter_example_plan')]
        valid_proposals: list[dict[str, Any]] = [p for p in proposals if isinstance(p,dict)]
        structured_tasks = payload.get('task_contract_version') == 1
        tasks = max([8 if structured_tasks else 4]+[len(p.get('tasks',[])) for p in valid_proposals if isinstance(p.get('tasks'),list)])
        features = max([4]+[len(p.get('features',[])) for p in valid_proposals if isinstance(p.get('features'),list)])
        checks = max([8,features*2+2]+[len(p.get('checks',[])) for p in valid_proposals if isinstance(p.get('checks'),list)])
        estimate = 512 + len(PLAN_SCHEMA['required'])*40 + min(tasks,40)*(640 if structured_tasks else 320) + min(checks,80)*240 + min(features,40)*100
        from .guided import planner_schema
        schema=planner_schema(contract_system or system) or PLAN_SCHEMA
        if payload.get('planning_stage') in {'outline','scope','acceptance'} or contract_system is not None and payload.get('planning_stage')=='acceptance_feature':
            estimate=512+len(schema['required'])*40+min(checks,15)*240+min(features,12)*100
        elif payload.get('planning_stage') in {'tasks','feature_tasks'}:
            maximum=payload.get('max_new_tasks',4)
            maximum=maximum if type(maximum) is int and 1<=maximum<=4 else 4
            estimate=512+maximum*800
        thinking = cap.thinking_budget_default if cap.supports_thinking_budget else 0
        # Conservative heuristic (about two UTF-8 bytes/token), not a tokenizer
        # guarantee or billing measurement. Reserve schema/message framing too.
        input_estimate = (len((system+prompt).encode('utf-8',errors='surrogatepass')) + len(json.dumps(schema)) + 1)//2 + 512
        if contract_system is not None:
            # The rendered system already contains the textual stage schema.
            # Count that once, plus the actual separate native schema if used.
            input_estimate=(len((system+prompt).encode('utf-8',errors='surrogatepass'))+1)//2+512
        # Guided schemas are now present in the textual system instruction for
        # every adapter. Ollama also sends its native format schema separately.
        if planner_schema(contract_system or system) is not None and provider=='ollama' and options.get('structured_outputs',True):
            input_estimate+=(len(json.dumps(schema))+1)//2
        room = min(cap.max_output_tokens, cap.max_context_tokens-input_estimate)
        text = max(self.builtin['planner_output_floor'], options.get('num_predict',4096), 0 if compact else estimate)
        if text+thinking > room:
            raise BudgetError('Planner needs '+str(text+thinking)+' output tokens plus an estimated '+str(input_estimate)+' input tokens; output ceiling is '+str(cap.max_output_tokens)+' and context is '+str(cap.max_context_tokens)+'. Increase Ollama context in planner settings if memory permits, or choose a larger-capacity model; no request was sent.',
                {'requested_max_output_tokens':text+thinking,'reserved_text_output_tokens':text,'thinking_budget':thinking,
                 'input_estimate_tokens':input_estimate,'required_context_tokens':input_estimate+text+thinking,
                 'configured_num_ctx':options.get('num_ctx') if provider in {'ollama','local'} else None,
                 'effective_context_tokens':cap.max_context_tokens,'context_shortfall_tokens':max(0,input_estimate+text+thinking-cap.max_context_tokens),
                 'max_output_ceiling':cap.max_output_tokens})
        return PlannerBudget(text+thinking, text, thinking, input_estimate, estimate)

    def reserve_builder(self, provider: str, model: str, options: dict[str, Any], system: str, prompt: str) -> PlannerBudget:
        """Keep the configured visible-code cap; reserve reasoning separately."""
        cap = self.get(provider, model, options)
        text = options.get('num_predict', 8192)
        thinking = cap.thinking_budget_default if cap.supports_thinking_budget else 0
        input_estimate = (len((system+prompt).encode('utf-8', errors='surrogatepass'))+1)//2 + 512
        if provider=='ollama' and options.get('structured_outputs',True):input_estimate+=(len(json.dumps(CODE_SCHEMA))+1)//2
        if text+thinking > min(cap.max_output_tokens, cap.max_context_tokens-input_estimate):
            raise ValueError('Builder output reservation exceeds the model output/context budget. Choose a larger-capacity model or reduce the configured output cap; no request was sent.')
        return PlannerBudget(text+thinking, text, thinking, input_estimate, text)

    def discover_local(self, model: str, data: dict[str,Any]) -> bool:
        """Record only numeric context metadata, never modelfiles/templates/paths."""
        info=data.get('model_info',{})
        if not isinstance(info,dict):return False
        values=[value for key,value in info.items() if isinstance(key,str) and key.endswith('.context_length') and type(value) is int and 256<=value<=16777216]
        if not values:return False
        context=min(values)
        self.overrides['ollama/'+model]={'max_output_tokens':min(8192,context-1),'max_context_tokens':context,
            'supports_thinking_budget':False,'thinking_budget_default':0,'estimated':True,
            'output_limit_published':False,'context_limit_published':True,
            'source':'Installed Ollama /api/show model_info context_length. Generation room is configured, not a published maximum output or GPU-fit guarantee.'}
        return True

    def save(self) -> None:
        if self.path:atomic_text(self.path,json.dumps({'schema':1,'models':self.overrides},indent=2)+'\n')

    def describe(self, provider: str, model: str, options: dict[str,Any] | None = None) -> dict[str,Any]:
        record=self.overrides.get(provider+'/'+model,self.builtin['models'].get(provider+'/'+model,self.builtin['defaults']))
        if not isinstance(record,dict):record=self.builtin['defaults']
        cap=self.get(provider,model,options)
        published=record.get('estimated') is False
        return {'provider':provider,'model':model,'model_output_limit':record.get('max_output_tokens') if record.get('output_limit_published',published) else None,
            'model_context_limit':record.get('max_context_tokens') if record.get('context_limit_published',published) else None,
            'effective_output_ceiling':cap.max_output_tokens,'configured_context':(options or {}).get('num_ctx',16384) if provider in {'ollama','local'} else None,
            'effective_context':cap.max_context_tokens,'estimated':cap.estimated,'source':cap.source,
            'minimum_output_tokens':None,'minimum_note':'No universal useful minimum is published. Foundry planner reserves at least 8192 text tokens; builder configuration starts at 1024. These are application settings, not model minimums.'}
