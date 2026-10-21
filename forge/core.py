"""Persistent projects and a deliberately bounded plan/build/check/repair state machine."""
from datetime import datetime, timezone
import copy
import ast
import difflib
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import threading
import time
import uuid
import zipfile
from typing import Any, Callable

from .workflow import workflow_snapshot, delivery_guide, delivery_checklist
from .model_status import ModelStatus
from .build_contract import generation_contract, execution_directive, remove_unchanged_owned_echoes, builder_profile, focused_handoff
from .tasks import task_packet, validate_task_response, task_document, existing_task_evidence
from .circuit import TransportCircuit
from .cloud import local_failover_route
from .execution import resume_problem, begin_task, candidate_saved, finish_task, finish_gate, seal_checkpoint, file_hashes, plan_hash
from .focus import prepare_context, retrieve_context, ContextRequestError
from .calibration import calibrate
from .models import output_contract, ModelClient, ModelError
from . import history, __version__
from .reporting import OWNED, evidence_status, file_manifest
from .handoffs import handoff_metrics
from .capabilities import CapabilityRegistry
from .contracts import validate_structure as validate_plan, require_consistent, review_plan, Review, Finding, ProposalError, starter_contracts
from .planning import PlanningEngine, PlanningResult
from .guided import run_guided, stage_review
from .routing import validate_config, uses_cloud, validate_options, truncation_fallback_allowed
from .prompts import PLAN, CODE
from .inspection import inspect_files
from .edits import expand_response
from .runner import verify, require_runtime, verify_milestone, require_browser_runtime
from .scaffolds import CATALOG, starter_files
from .evidence import manual_document
from .context import SOURCE_LIMIT, source_map, failure_feedback, fingerprint, planning_context, same_tasks

ACTIVE = {"planning", "building", "checking", "repairing", "queued"}


def preflight(files, complete=True):
    return inspect_files(files, complete=complete)


def safe_file(root, name):
    if not isinstance(name, str) or len(name) > 160 or "\\" in name or ":" in name:
        raise ValueError("Invalid generated filename.")
    parts = PurePosixPath(name).parts
    if not parts or PurePosixPath(name).is_absolute() or any(p.startswith(".") or p.endswith((" ", ".")) for p in parts):
        raise ValueError("Hidden files, absolute paths and parent paths are forbidden.")
    reserved = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
    if any(p.split(".")[0].upper() in reserved or not re.fullmatch(r"[A-Za-z0-9_. -]+", p) for p in parts):
        raise ValueError("Filename is not portable to Windows.")
    if Path(name).suffix.lower() not in {".py", ".html", ".css", ".js", ".json", ".txt", ".md"}:
        raise ValueError("Only source and text files are supported.")
    target = root.joinpath(*parts)
    if any(p.is_symlink() for p in [target, *target.parents]) or not target.resolve().is_relative_to(root.resolve()):
        raise ValueError("File escapes the project directory.")
    return target


class Workbench:
    def __init__(self, root, client_factory=ModelClient, verifier=verify):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.client_factory, self.verifier = client_factory, verifier
        self.lock = threading.RLock()
        self.inference_lock = threading.Lock()
        self.provider_cooldowns = {}
        self.transport_circuit = TransportCircuit()
        self.installed_ollama_models = []
        self.model_status = ModelStatus()
        self.jobs = {}
        self.warnings = []
        self.maintenance = False
        self.milestone_verifier = verify_milestone
        for path in self.root.glob("*/state.json"):
            try:
                state = self.load(path.parent.name)
            except (ValueError, OSError):
                self.warnings.append(f"Could not read project {path.parent.name}. Its files were preserved. Restore from a workspace backup.")
                continue
            if not (path.parent / "source").exists():
                recoverable = sorted(path.parent.glob(".source-before-*"), key=lambda p: p.stat().st_mtime, reverse=True)
                if recoverable:
                    os.replace(recoverable[0], path.parent / "source")
                    self.warnings.append(f"Recovered project {state['title']} after an interrupted file update. Original source was restored.")
            if state.get("status") in ACTIVE:
                # A durable attempt record can precede the atomic state-file swap.
                # Recover available counters without inventing lost legacy history.
                if (path.parent / "workflow-history.jsonl").exists():
                    try:
                        journal = history.document(path.parent, state)
                        records = [r["data"] for r in journal["records"] if r.get("kind") == "model_attempt"]
                        if len(records) > history.totals_for(state)["requests"]:
                            rebuilt = {"model_totals":history.totals_for({})}
                            for record in records:
                                history.add_attempt(rebuilt, record)
                            rebuilt["model_totals"]["legacy_incomplete"] = bool(history.totals_for(state).get("legacy_incomplete") or journal["coverage"].get("legacy_history_incomplete") or not journal["coverage"].get("complete_since_tracking_started"))
                            state["model_totals"] = rebuilt["model_totals"]
                            self.trace(state, "attempt_totals_recovered", {"available_attempts":len(records)})
                    except (OSError, ValueError, KeyError, TypeError):
                        state["history_warning"] = "Interrupted-run counters could not be reconciled with history; retained counts may be incomplete."
                state["status"] = "interrupted"
                self.trace(state, "job_interrupted", {"reason":"Workbench restarted before job completion."})
                state.pop("active_run_id", None)
                self.event(state, "Workbench restarted. Resume to continue from the last saved task.")

    @staticmethod
    def now():
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def directory(self, ident):
        if not re.fullmatch(r"[a-f0-9]{32}", ident):
            raise ValueError("Invalid project ID.")
        return self.root / ident

    def load(self, ident):
        with self.lock:
            try:
                state = json.loads((self.directory(ident) / "state.json").read_text(encoding="utf-8"))
                if not isinstance(state, dict) or state.get("id") != ident or not all(isinstance(state.get(k), str) for k in ("status", "created", "title")) or not isinstance(state.get("events"), list):
                    raise ValueError("Project metadata is invalid. Original files were preserved.")
                return state
            except FileNotFoundError:
                raise ValueError("Project not found.") from None
            except json.JSONDecodeError:
                raise ValueError("Project metadata is damaged. Original files were preserved; restore from a backup.") from None

    def save(self, state):
        with self.lock:
            path = self.directory(state["id"])
            path.mkdir(exist_ok=True)
            state["schema_version"] = 2
            state["updated"] = self.now()
            temporary = path / ("state-" + uuid.uuid4().hex + ".tmp")
            temporary.write_text(json.dumps(state, indent=2), encoding="utf-8")
            os.replace(temporary, path / "state.json")

    def trace(self, state, kind, data, origin="controller"):
        with self.lock:
            try:
                history.append(self.directory(state["id"]), state, kind, data, origin)
            except (OSError, ValueError) as exc:
                state["history_warning"] = "History incomplete: " + str(exc)[:500]

    def history(self, ident):
        with self.lock:
            state = self.load(ident)
            try:
                return history.document(self.directory(ident), state)
            except (OSError, ValueError) as exc:
                return {"schema":1, "project_id":ident, "records":[], "coverage":{"warning":str(exc), "complete_since_tracking_started":False}, "meaning":"History unavailable; app files preserved."}

    def workflow(self, ident):
        with self.lock:
            return workflow_snapshot(self.load(ident),self.files(ident))

    def evidence(self, ident):
        with self.lock:
            return evidence_status(self.load(ident), self.files(ident))

    def present(self, ident):
        state = self.load(ident)
        if (state.get("checks") or {}).get("passed") or state.get("verification_fingerprint"):
            freshness = evidence_status(state, self.files(ident))
            state["evidence_status"] = freshness
            state["status"] = freshness["effective_status"]
            if (state.get("checks") or {}).get("passed") and not freshness["automated_evidence_current"]:
                state["checks"] = {**state["checks"], "passed":False, "historical_passed":True,
                                   "diagnosis":"Verification evidence is stale. Run checks again after resolving protected-file changes."}
                state["error"] = "Verification evidence is stale. " + " ".join(freshness["issues"])
        return state

    def export_snapshot(self, ident):
        with self.lock:
            state = self.load(ident)
            if state["status"] in ACTIVE:
                raise ValueError("Wait for the running job to stop before exporting.")
            files = {n:t for n,t in self.files(ident).items() if n.lower() not in {"build-report.json","run-history.json"}}
            freshness = evidence_status(state, files)
            self.trace(state, "export_prepared", {"source_sha256":freshness["current_source_sha256"],
                       "effective_status":freshness["effective_status"], "file_count":len(files)}, "user")
            self.save(state)
            journal = self.history(ident)
            plan = state.get("plan") or {}
            report = {k:state.get(k) for k in ("starter","starter_version","milestones","checks","preflight","plan_review","planning_stats","proposal_source","generation_stats","manual_results","repair_history","verification_fingerprint","verification_manifest")}
            report.update(report_schema=2, generator_version=__version__, project_id=ident, exported_at=self.now(),
                          status=freshness["effective_status"], recorded_status=state["status"], evidence_status=freshness,
                          original_idea=state.get("idea"), approved_plan=state.get("plan") if state.get("approved") else None,
                          parent_id=state.get("parent_id"),
                          manual_checks=plan.get("manual_checks", []), models={"planner":state["planner"],"coder":state["coder"]},
                          model_totals=history.totals_for(state), model_calls=state.get("model_calls", []),
                          model_totals_definition="requests is the legacy field name for recorded model attempts, not confirmed provider requests or billed usage.",
                          journal=state.get("events", []), file_manifest=file_manifest(files),
                          manifest_scope="UTF-8 project entries only; BUILD-REPORT.json and RUN-HISTORY.json are metadata, excluded from this file manifest.",
                          history_coverage=journal["coverage"])
            if (report.get("checks") or {}).get("passed") and not freshness["automated_evidence_current"]:
                report["checks"] = {**report["checks"], "passed":False, "historical_passed":True, "evidence_current":False}
            snapshot = workflow_snapshot(state,files)
            report.update(workflow=snapshot, task_receipts=snapshot["task_receipts"], delivery_guide=delivery_guide(state,snapshot), work_checklist=delivery_checklist(state,snapshot), export_metadata_files=["BUILD-REPORT.json","RUN-HISTORY.json",".foundry/DELIVERY.md",".foundry/WORK-CHECKLIST.md"])
            report["manifest_scope"] = "UTF-8 project entries only; export_metadata_files are metadata and excluded from this file manifest."
            return files, history.redact(report), journal

    def event(self, state, message, origin="controller"):
        self.trace(state, "journal", {"message":message}, origin)
        state["events"].append({"time": self.now(), "message": message, "origin":origin})
        state["events"] = state["events"][-300:]
        self.save(state)

    def list_projects(self):
        with self.lock:
            states = []
            for path in self.root.glob("*/state.json"):
                try:
                    states.append(self.present(path.parent.name))
                except (ValueError, OSError):
                    continue
        return sorted(states, key=lambda p: p["created"], reverse=True)

    def call_model(self, state: dict[str, Any], role: str, system: str, prompt: str, cancel: threading.Event, fallback: bool = False, allow_fallback: bool = True, review_candidate: Callable[[dict[str, Any]], tuple[dict[str, Any], Review]] | None = None, only_model: tuple[str,str] | None = None, response_rejections: set[tuple[str,str]] | None = None) -> dict[str, Any]:
        """Serialize requests, record the actual provider, and bound an explicit fallback."""
        previous = state["status"]
        if not self.inference_lock.acquire(blocking=False):
            state["status"] = "queued"
            self.event(state, "Waiting for the other model request to finish. You can stop this queued job.")
            while not self.inference_lock.acquire(timeout=0.2):
                if cancel.is_set():
                    raise InterruptedError("Stopped while waiting for a model.")
        try:
            config = state.get('run_model_routes',{}).get(role,state[role]) if state.get('active_run_id') else state[role]
            pool = bool(config.get("fallbacks"))
            choices = [(config["fallback"], True)] if fallback and config.get("fallback") else [(config, False)]
            if not fallback and allow_fallback and config.get("fallback"):
                choices.append((config["fallback"], True))
            if pool and allow_fallback:
                choices.extend((entry, True) for entry in config["fallbacks"])
            if only_model is not None:
                choices=[(entry,flag) for entry,flag in choices if (entry['provider'],entry['model'])==only_model]
            failures = []
            registry = CapabilityRegistry(self.root.parent / 'model-capabilities-v1.json')
            minimum_ceiling = state.get("planner_truncation_ceiling", 0) if role == "planner" else 0
            recoveries = {}
            correction_prompts = {}
            schema_retries = set()
            budget_failed = False
            for index, (selected, is_fallback) in enumerate(choices):
                if cancel.is_set():
                    raise InterruptedError("Stopped before model inference.")
                if selected['provider'] in {'ollama','local'} and state.get('job_local_timeout'):
                    selected=copy.deepcopy(selected)
                    selected['options']={**selected.get('options',{}),'timeout_seconds':state['job_local_timeout']}
                if uses_cloud({'provider':selected['provider']}) and not state.get("job_cloud_consent"):
                    raise ValueError("Explicit cloud consent is required for the selected primary or fallback model.")
                identity = (selected["provider"], selected["model"])
                if response_rejections is not None and identity in response_rejections:
                    failures.append('/'.join(identity)+': response_rejected for this response-recovery scope (no request sent)')
                    self.event(state,'Skipping '+ '/'.join(identity)+' after its bounded correction in this response-recovery scope; a later task or static-repair context may use it again.')
                    continue
                if selected['provider'] in state.get('job_provider_rejections',{}):
                    reason=state['job_provider_rejections'][selected['provider']]
                    failures.append(selected['provider']+': '+reason+' (provider skipped, no request sent)')
                    self.event(state,'Skipping '+selected['provider']+' for this run after account-wide '+reason+'; another model cannot restore account credit/authentication.')
                    continue
                circuit_key=selected['provider']+'/'+selected['model'] if selected['provider'] in {'ollama','local'} else selected['provider']
                if pool and self.transport_circuit.remaining(circuit_key)>0:
                    self.event(state,'Skipping '+circuit_key+' during its temporary transport/service circuit cooldown; no request sent.')
                    failures.append(selected['provider']+': temporary transport/service circuit cooldown (no request sent)')
                    continue
                rejected = state.get("job_model_rejections", {})
                if rejected.get(selected["provider"] + "/" + selected["model"]):
                    self.event(state, "Skipping model already rejected during this job: " + selected["provider"] + "/" + selected["model"] + ".")
                    failures.append(selected['provider']+'/'+selected['model']+': '+str(rejected[selected['provider']+'/'+selected['model']])+' (already rejected)')
                    continue
                if role == "planner" and state.get("job_inference_attempts", 0) >= 24:
                    raise ModelError("This job reached its 24-attempt inference limit. Review model history before retrying.", "attempt_budget")
                if state.get("job_max_model_calls") is not None and state.get("job_inference_attempts",0)>=state["job_max_model_calls"]:
                    raise ModelError("This run reached its model invocation allowance. Saved files were kept. Review the journal and resume with an appropriate allowance; no further model was called.", "attempt_budget")
                capability = registry.get(selected['provider'], selected['model'], selected.get('options',{}), role=role)
                if minimum_ceiling and not truncation_fallback_allowed(minimum_ceiling, capability.max_output_tokens):
                    self.event(state, 'Skipped ' + selected['provider'] + '/' + selected['model'] + ': output ceiling ' + str(capability.max_output_tokens) + ' is smaller than truncated model ceiling ' + str(minimum_ceiling) + '.')
                    continue
                recovery_mode, prefix = recoveries.get(index, ('initial', ''))
                effective_prompt = correction_prompts.get(index, prompt)
                if pool and only_model is None and recovery_mode == 'initial' and self.model_status.avoid(selected['provider'],selected['model'],include_response=response_rejections is None):
                    failures.append(selected['provider']+': recent_failure')
                    self.event(state,'Skipping recently failed model for up to five minutes: '+selected['provider']+'/'+selected['model']+'.')
                    continue
                identity = (selected["provider"], selected["model"])
                if pool and self.provider_cooldowns.get(identity, 0) > time.monotonic():
                    failures.append(selected["provider"] + ": cooldown")
                    self.event(state, "Skipping " + selected["provider"] + " during its temporary rate-limit cooldown.")
                    continue
                record = {"role": role, "provider": selected["provider"], "model": selected["model"],
                          "fallback": is_fallback, "time": self.now(), "success": False, **handoff_metrics(system, effective_prompt),
                          "recovery_path": 'task_response_correction' if only_model else recovery_mode if recovery_mode != 'initial' else 'capacity_fallback' if minimum_ceiling and is_fallback else 'initial',
                          "max_output_ceiling": capability.max_output_tokens, "capability_estimated": capability.estimated, "transport_attempted":None, "timeout_seconds":selected.get("options", {}).get("timeout_seconds",120)}
                started = time.monotonic()
                client = None
                try:
                    state["status"] = previous
                    self.save(state)
                    self.event(state, "Requesting " + selected["provider"] + "/" + selected["model"] + " (route step " + str(index + 1) + "/" + str(len(choices)) + ").")
                    budget_system=output_contract(system)+(execution_directive(json.loads(effective_prompt)) if system==CODE else "")
                    client = self.client_factory(selected["provider"], selected["model"])
                    if isinstance(client, ModelClient):
                        client.last_usage = {}
                        client.last_metadata = {"transport_attempted":False}
                        client.options = validate_options(selected.get("options", {}))
                        if role in {'planner', 'coder'}:
                            try:
                                reserve = registry.reserve if role == 'planner' else registry.reserve_builder
                                budget = reserve(selected['provider'],selected['model'],client.options,budget_system+prefix,effective_prompt)
                            except ValueError as exc:
                                if role != 'planner': raise ModelError(str(exc),'output_budget') from None
                                try:
                                    budget = registry.reserve(selected['provider'],selected['model'],client.options,budget_system+prefix,effective_prompt,compact=True)
                                except ValueError:
                                    raise ModelError(str(exc),'output_budget') from None
                                if recovery_mode == 'initial':
                                    recovery_mode = 'budget_compaction'
                                    record['recovery_path'] = recovery_mode
                                record['budget_compacted'] = True
                                self.event(state,'Estimated proposal exceeds capacity; reserving the unchanged output floor for a compact schema-complete proposal. No request content or checks were omitted.')
                            client.planner_budget = budget
                            client.recovery_mode, client.continuation_prefix = recovery_mode, prefix
                            record.update(requested_max_output_tokens=budget.max_output_tokens,
                                          reserved_text_output_tokens=budget.text_output_tokens,
                                          thinking_budget=budget.thinking_budget,
                                          estimated_required_output_tokens=budget.estimated_required_tokens,
                                          input_estimate_tokens=budget.input_estimate_tokens)
                            self.event(state, role.title()+' output reservation: '+str(budget.text_output_tokens)+' text + '+str(budget.thinking_budget)+' thinking tokens; recovery '+record['recovery_path']+'.')
                    state["job_inference_attempts"] = state.get("job_inference_attempts", 0) + 1
                    if state.get('job_max_model_calls') is not None:
                        signature=hashlib.sha256(json.dumps([role,selected['provider'],selected['model'],system,effective_prompt,recovery_mode,prefix],ensure_ascii=True).encode()).hexdigest()
                        counts=state.setdefault('job_call_signatures',{})
                        if counts.get(signature,0)>=3:
                            state['job_inference_attempts']-=1
                            self.event(state,'Repeated identical model request stopped before inference. Review the task/context rather than repeating the same call.')
                            raise ModelError('Repeated identical request reached the three-call run limit. Saved files were kept; review and resume with new evidence.','loop_detected')
                        counts[signature]=counts.get(signature,0)+1
                    self.model_status.start(selected["provider"], selected["model"], role, state['id'])
                    self.trace(state,'model_request_started',{'provider':selected['provider'],'model':selected['model'],'role':role,'recovery_path':record['recovery_path']})
                    if isinstance(client,ModelClient) and selected['provider'] in {'ollama','local'} and state.get('job_stream_local'):
                        client.cancel_event=cancel
                        client.stream_progress=self.model_status.progress
                    result = client.complete(system, effective_prompt)
                    self.transport_circuit.success(circuit_key)
                    if cancel.is_set(): raise InterruptedError("Stopped. Model output discarded.")
                    if role=='planner':
                        record['response_sha256']=hashlib.sha256(json.dumps(result,sort_keys=True).encode()).hexdigest()
                    if review_candidate is not None:
                        result, review_result = review_candidate(result)
                        record["proposal_valid"] = review_result.passed
                        record['review_findings']=history.redact(review_result.to_dict()['findings'])
                        if not review_result.passed:
                            reasons='; '.join(f.path+': '+f.message for f in review_result.findings if f.severity=='error')
                            self.event(state,'Proposal rejected by review: '+reasons[:1800])
                            record["review_codes"] = [f.code for f in review_result.findings if f.severity == "error"]
                            record["failure_class"] = "schema_error"
                            record["error_category"] = "schema_error"
                            if identity not in schema_retries:
                                schema_retries.add(identity)
                                feedback = json.loads(prompt)
                                feedback.update(previous_proposal=result,
                                    validation_error="; ".join(f.path + ": " + f.message for f in review_result.findings if f.severity == "error"),
                                    correction_instruction="Return the complete requested stage object at the root, following its output schema. Correct the findings without dropping requirements or changing acceptance checks.")
                                choices.insert(index+1, (selected, is_fallback))
                                correction_prompts[index+1] = json.dumps(feedback)
                                recoveries[index+1] = ("schema_correction", "")
                                self.event(state, "Proposal failed deterministic review; one focused correction on " + selected["provider"] + "/" + selected["model"] + ".")
                                continue
                            state.setdefault("job_model_rejections", {})[selected["provider"] + "/" + selected["model"]] = "schema_error"
                            failures.append(selected["provider"] + ": schema_error")
                            self.event(state, "Proposal correction failed; advancing to the next model without restarting the route.")
                            continue
                    record.update(success=True, **getattr(client, "last_usage", {}))
                    if pool and is_fallback:
                        self.event(state, "Response received from " + selected["provider"] + "/" + selected["model"] + ".")
                    return result
                except ModelError as exc:
                    record['error_detail']=history.redact(str(exc)[:1200])
                    if exc.transport_kind:record['transport_kind']=exc.transport_kind
                    if exc.category in {'transport','provider'}:self.transport_circuit.failure(circuit_key)
                    elif exc.category not in {'output_budget','configuration'}:self.transport_circuit.success(circuit_key)
                    if exc.http_status is not None:record["http_status"]=exc.http_status
                    category = 'truncated_output' if exc.category in {'truncated','truncated_output'} else exc.category
                    if pool and selected['provider'] in {'ollama','local'} and category in {'transport','provider','format','parse_error','size'}:
                        if response_rejections is not None and category in {'format','parse_error','size'}:
                            # A failed continuation still owes its bounded
                            # same-model shortening before response exclusion.
                            if recovery_mode!='continuation':response_rejections.add(identity)
                        else:state.setdefault('job_model_rejections',{})[selected['provider']+'/'+selected['model']]=category
                    record['error_category'] = category
                    record['failure_class'] = category if category in {'truncated_output','parse_error','schema_error','output_budget','configuration'} else 'parse_error' if category == 'format' else 'provider_unavailable' if category in {'auth','rate_limit','provider','transport','quota','request','model','configuration'} else category
                    if category == 'truncated_output' or (role in {'planner', 'coder'} and recovery_mode == 'continuation' and category in {'format','parse_error','output_budget'}):
                        minimum_ceiling = max(minimum_ceiling, capability.max_output_tokens)
                        if role == "planner": state["planner_truncation_ceiling"] = minimum_ceiling
                        if role in {'planner', 'coder'} and recovery_mode != 'shortening':
                            partial = getattr(exc,'partial_content','')
                            mode = 'continuation' if recovery_mode in {'initial','budget_compaction'} and partial else 'shortening'
                            choices.insert(index+1,(selected,is_fallback))
                            recoveries[index+1] = (mode,partial if mode == 'continuation' else '')
                            correction_prompts[index+1] = effective_prompt
                            self.event(state,role.title()+' truncated_output recovery: '+mode+' on '+selected['provider']+'/'+selected['model']+'.')
                            continue
                        failures.append(selected['provider']+': truncated_output')
                        # Legacy planner fallback orchestration must obey the same ceiling gate.
                        if role == 'planner' and not fallback and config.get('fallback') and not any(c is config['fallback'] for c,_ in choices):
                            choices.append((config['fallback'],True))
                        self.event(state,'Output recovery exhausted; considering only configured models with output ceiling >= '+str(minimum_ceiling)+'.')
                        continue
                    if category == 'output_budget':
                        budget_failed = True
                        failures.append(selected['provider']+': output_budget')
                        self.event(state,role.title()+' reservation refused before inference: '+str(exc)+' Trying the next configured model without lowering the required budget.')
                        continue
                    if exc.category == "request" and selected.get("options", {}).get("structured_outputs", True) and recovery_mode != "json_compatibility":
                        compatible = copy.deepcopy(selected)
                        compatible.setdefault("options", {})["structured_outputs"] = False
                        choices.insert(index+1, (compatible, is_fallback))
                        recoveries[index+1] = ("json_compatibility", "")
                        correction_prompts[index+1] = effective_prompt
                        self.event(state, "Request rejected; retrying once without the optional native JSON parameter. Returned JSON and proposal validation remain required.")
                        continue
                    if exc.category in {"model", "auth", "configuration", "quota"}:
                        state.setdefault("job_model_rejections", {})[selected["provider"] + "/" + selected["model"]] = exc.category
                    if selected['provider'] not in {'ollama','local'} and (exc.category=='quota' and exc.http_status==402 or exc.category=='auth' and exc.http_status==401):
                        state.setdefault('job_provider_rejections',{})[selected['provider']]=exc.category
                    if exc.retry_after: record["retry_after_seconds"] = exc.retry_after
                    if pool:
                        if exc.category not in {"auth", "rate_limit", "provider", "transport", "quota", "request", "model", "configuration", "format", "parse_error", "size"}:
                            raise
                        failures.append(selected["provider"] + ": " + exc.category)
                        if exc.retry_after or exc.category == 'rate_limit':
                            self.provider_cooldowns[identity] = time.monotonic() + (exc.retry_after or 30)
                        self.event(state, selected["provider"] + " request failed (" + exc.category + (" HTTP " + str(exc.http_status) if exc.http_status else "") + "). " + ("Trying the next configured tier." if index + 1 < len(choices) else "No more configured tiers."))
                        continue
                    if is_fallback or not allow_fallback or not config.get("fallback"):
                        raise
                    if cancel.is_set():
                        raise InterruptedError("Stopped before fallback inference.")
                    self.event(state, "Primary model request failed (" + exc.category + "). Trying the explicitly configured fallback.")
                finally:
                    if client is not None:
                        record.update(**getattr(client, "last_usage", {}))
                        record.update(**getattr(client, "last_metadata", {}))
                    self.model_status.finish(selected["provider"], selected["model"], "responded" if record["success"] else record.get("error_category", "cancelled" if cancel.is_set() else "failed"))
                    record["seconds"] = round(time.monotonic() - started, 2)
                    record["run_id"] = state.get("active_run_id")
                    history.add_attempt(state, record)
                    self.trace(state, "model_attempt", record)
                    state.setdefault("model_calls", []).append(record)
                    state["model_calls"] = state["model_calls"][-100:]
                    self.save(state)
            if minimum_ceiling:
                raise ModelError('Output remained truncated after bounded recovery. No eligible equal/larger configured fallback resolved it. '+ '; '.join(failures),'truncated_output')
            if budget_failed:
                raise ModelError('Configured route exhausted. Some models could not fit the output/context reservation; other provider failures are listed here: '+ '; '.join(failures),'output_budget')
            if pool or review_candidate is not None:
                raise ModelError("All configured models failed: " + ("; ".join(failures) or 'No eligible configured model remains; review prior source/transport rejections in this run.'), "exhausted")
        finally:
            self.inference_lock.release()

    def configure_models(self, ident: str, planner: dict[str, Any], coder: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            state = self.load(ident)
            if state["status"] in ACTIVE:
                raise ValueError("Wait for or stop the running job before changing models.")
            planner, coder = validate_config(planner), validate_config(coder)
            state.update(planner=planner, coder=coder)
            self.trace(state, "models_configured", {"planner":planner, "coder":coder}, "user")
            self.event(state, "Model choices updated. Project files and approved requirements were kept.")
            return state

    def fork(self, ident: str, request: str, cloud_consent: bool = False) -> dict[str, Any]:
        with self.lock:
            parent = self.load(ident)
            if parent["status"] in ACTIVE or not parent["approved"]:
                raise ValueError("Finish or stop an approved project before requesting a change.")
            if not isinstance(request, str) or not 10 <= len(request.strip()) <= 6000:
                raise ValueError("Describe the change in 10–6000 characters.")
            state = copy.deepcopy(parent)
            state.update(id=uuid.uuid4().hex, parent_id=ident, parent_title=parent["title"],
                         change_request=request.strip(), baseline_plan=copy.deepcopy(parent["plan"]),
                         frozen_tests={name: hashlib.sha256(text.encode()).hexdigest() for name, text in self.context_files(ident).items() if Path(name).name.startswith("test_") and name.endswith(".py")},
                         title=parent["title"] + " · change", created=self.now(), status="draft", approved=False,
                         plan=None, plan_review=None, planning_stats=None, failed_candidate=None, plan_is_previous=False, generation_stats={}, manual_results={}, repair_history=[], verification_fingerprint=None, next_task=0, events=[], snapshots=[], checks=None, preflight=None, model_calls=[], model_totals=history.totals_for({}), milestones=[], repair_count=0)
            state.pop("active_run_id", None)
            state.pop("history_warning", None)
            state.pop("verification_manifest", None)
            for key in ('pending_task','execution_checkpoint','last_task_support'):state.pop(key,None)
            state['task_receipts']=[]
            target = self.directory(state["id"]) / "source"
            target.mkdir(parents=True)
            for name, content in self.files(ident).items():
                path = target / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
            state["baseline_frozen_tests"] = copy.deepcopy(state["frozen_tests"])
            self.save(state)
            self.start(state["id"], "plan", {"cloud_consent": cloud_consent})
            return self.load(state["id"])

    @staticmethod
    def revision_plan(state, plan):
        if not isinstance(plan, dict):
            raise ValueError("Proposal must be a JSON object.")
        plan = copy.deepcopy(plan)
        baseline = state.get("baseline_plan")
        if baseline:
            if plan.get("features", [])[:len(baseline["features"])] != baseline["features"]:
                raise ValueError("A change must preserve the original features in their original order, then append new features.")
            if state.get("change_request") and plan.get("features") == baseline["features"] and same_tasks(plan.get("tasks"), baseline.get("tasks")):
                raise ValueError("This improvement repeats the previous build tasks. Plan targeted changes for the current request using implementation_context; do not replay the old build or assign manual play-testing to the coding model.")
            for kind in ("manual_checks", "browser_checks"):
                for check in baseline.get(kind, []):
                    if check not in plan.get(kind, []):
                        plan.setdefault(kind, []).append(copy.deepcopy(check))
            for check in baseline["checks"]:
                original = {**check, "feature_indexes": check.get("feature_indexes", [])}
                if original not in plan.get("checks", []):
                    plan.setdefault("checks", []).append(original)
        return validate_plan(plan)

    def backup(self):
        with self.lock:
            if any(thread.is_alive() for thread, _ in self.jobs.values()):
                raise ValueError("Wait for or stop all jobs before backing up a consistent workspace.")
            stream = io.BytesIO()
            total = 0
            with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(self.root.rglob("*")):
                    relative = path.relative_to(self.root)
                    if not path.is_file() or any(p.is_symlink() for p in [path, *path.parents]) or any(p.startswith(".") for p in relative.parts) or "__pycache__" in relative.parts or path.suffix in {".pyc", ".tmp"}:
                        continue
                    total += path.stat().st_size
                    if total > 100_000_000:
                        raise ValueError("Workspace exceeds the 100 MB browser-backup limit. Copy the data folder using your file manager.")
                    archive.write(path, "projects/" + relative.as_posix())
                archive.writestr("BACKUP-README.txt", "Idea Foundry workspace backup. Stop Foundry, extract projects/ into your data folder, then restart. Back up the current folder before restoring. API keys and .env files are intentionally excluded.\n")
            return stream.getvalue()

    def diff(self, ident):
        state = self.load(ident)
        if state["status"] in ACTIVE:
            raise ValueError("Wait until the job stops before reviewing changes.")
        current = self.files(ident)
        before = {}
        if state["snapshots"]:
            root = self.directory(ident) / "snapshots" / state["snapshots"][-1]["id"]
            for name in current:
                path = root / name
                if path.is_file() and not any(p.is_symlink() for p in [path, *path.parents]):
                    before[name] = path.read_text(encoding="utf-8")
        result = []
        for name, content in current.items():
            if before.get(name) != content:
                lines = difflib.unified_diff(before.get(name, "").splitlines(), content.splitlines(), fromfile="before/" + name, tofile="after/" + name, lineterm="")
                result.append({"name": name, "kind": "modified" if name in before else "added", "diff": "\n".join(lines)[:20000]})
        return result

    def create(self, idea: str, planner: dict[str, Any], coder: dict[str, Any], starter: str | None = None, cloud_consent: bool = False, use_reviewed_plan: bool = False, plan_mode: str = 'single', local_timeout: int | None = None) -> dict[str, Any]:
        if self.maintenance:
            raise ValueError("An update is being installed. Wait for the restart.")
        if plan_mode not in {'single','guided'}:
            raise ValueError('Choose single or guided planning.')
        if local_timeout is not None and (type(local_timeout) is not int or local_timeout not in {120,300,600}):
            raise ValueError('Guided local timeout must be 120, 300 or 600 seconds.')
        if type(use_reviewed_plan) is not bool or (use_reviewed_plan and starter != "arcade"):
            raise ValueError("A reviewed standard plan is available only for the Neon Dodge starter.")
        if starter is not None and starter not in CATALOG:
            raise ValueError("Unknown starter template.")
        if not isinstance(idea, str) or not 10 <= len(idea.strip()) <= 12000:
            raise ValueError("Describe your idea in 10–12000 characters.")
        planner, coder = validate_config(planner), validate_config(coder)
        if any(uses_cloud(c) for c in (planner, coder)) and not cloud_consent:
            raise ValueError("Confirm cloud use for the configured primary/fallback models.")
        for config in (planner, coder):
            self.client_factory(config["provider"], config["model"])
        ident = uuid.uuid4().hex
        state = {"id": ident, "idea": idea.strip(), "title": "New project", "created": self.now(),
                 "status": "draft", "planner": planner, "coder": coder, "plan": None,
                 "approved": False, "next_task": 0, "events": [], "checks": None,
                 "snapshots": [], "repair_count": 0, "starter": starter, "model_totals": history.totals_for({})}
        (self.directory(ident) / "source").mkdir(parents=True)
        self.save(state)
        self.trace(state, "project_created", {"starter":starter, "idea_characters":len(state["idea"]), "planner":planner, "coder":coder}, "user")
        if use_reviewed_plan:
            return self.load_starter_plan(ident)
        self.start(ident, "plan", {"cloud_consent": cloud_consent, 'plan_mode':plan_mode, 'local_timeout':local_timeout})
        return self.load(ident)

    def insights(self):
        groups = {}
        for state in self.list_projects():
            coder = state["coder"]
            key = coder["provider"] + "/" + coder["model"]
            group = groups.setdefault(key, {"model": key, "projects": 0, "verified": 0, "generated": 0, "calls": 0, "seconds": 0})
            group["projects"] += 1
            group["verified"] += state["status"] == "verified"
            group["generated"] += state["status"] == "generated"
            calls = [c for c in state.get("model_calls", []) if c.get("role") == "coder"]
            group["calls"] += len(calls)
            group["seconds"] = round(group["seconds"] + sum(c["seconds"] for c in calls), 2)
        return {"models": list(groups.values()), "explanation": "Current project results, grouped by current builder. Model switches and different prompts/scopes affect these counts; they are not a controlled model ranking."}

    def client(self, state, role):
        config = state[role]
        return self.client_factory(config["provider"], config["model"])

    def start(self, ident, action, options):
        with self.lock:
            if self.maintenance:
                raise ValueError("An update is being installed. Wait for the restart.")
            state = self.load(ident)
            existing = self.jobs.get(ident)
            if existing and existing[0].is_alive():
                raise ValueError("A job is already running for this project.")
            options = dict(options)
            if options.get('plan_mode','single') not in {'single','guided'}:raise ValueError('Choose single or guided planning.')
            if options.get('local_timeout') is not None and (type(options['local_timeout']) is not int or options['local_timeout'] not in {120,300,600}):raise ValueError('Guided local timeout must be 120, 300 or 600 seconds.')
            state['job_local_timeout']=options.get('local_timeout') if action=='plan' else None
            if type(options.get('stream_local',False)) is not bool:raise ValueError('Local streaming setting must be a JSON boolean.')
            state['job_stream_local']=options.get('stream_local',False)
            state['job_call_signatures']={}
            if action not in {"plan", "build", "repair"}:
                raise ValueError("Unknown job action.")
            if action in {"build", "repair"} and not state["approved"]:
                raise ValueError("Approve the proposal first.")
            if action == "plan" and state["approved"]:
                raise ValueError("An approved proposal is frozen. Create another project for a new scope.")
            active_role="planner" if action=="plan" else "coder"
            if uses_cloud(state[active_role]) and options.get("cloud_consent") is not True:
                raise ValueError("Explicit cloud consent is required for this stage's configured primary/fallback models.")
            state["job_cloud_consent"] = options.get("cloud_consent") is True
            mode = options.get("runtime", "docker")
            if type(options.get("execute", False)) is not bool:
                raise ValueError("Execution settings must use a JSON boolean for execute.")
            execute = options.get("execute", False) is True
            if mode not in {"docker", "local"}:
                raise ValueError("Unknown execution runtime.")
            if execute and options.get("consent") is not True:
                raise ValueError("Explicit execution consent is required.")
            if state["status"] == "verified" and not state.get("frozen_tests"):
                state["frozen_tests"] = {name: hashlib.sha256(text.encode()).hexdigest() for name, text in self.context_files(ident).items() if Path(name).name.startswith("test_") and name.endswith(".py")}
            max_calls=options.get("max_model_calls",64)
            if type(max_calls) is not int or not 1<=max_calls<=128:
                raise ValueError("Model invocation allowance must be an integer from 1 to 128.")
            attempts = options.get("repairs", 2)
            if type(attempts) is not int or not 0 <= attempts <= 3:
                raise ValueError("Repair limit must be between 0 and 3.")
            if action == "repair":
                report = state.get("manual_results") or {}
                results = report.get("results", [])
                checks = state["plan"].get("manual_checks", [])
                notes = report.get("notes", [""] * len(checks))
                if not (state.get("checks") or {}).get("passed") or len(results) != len(checks) or not any(v is False for v in results):
                    raise ValueError("Save failed manual checks after automated verification before requesting a repair.")
                if state.get("verification_fingerprint") != fingerprint(self.context_files(ident)) or report.get("source_sha256") != state.get("verification_fingerprint"):
                    raise ValueError("Source changed since those observations. Verify and test the current app again.")
                if attempts == 0:
                    raise ValueError("Choose at least one repair attempt.")
                if any(not notes[i].strip() for i, value in enumerate(results) if value is False):
                    raise ValueError("Describe what actually happened for each failed check, then save the results.")
                options["manual_evidence"] = {"source_sha256": report["source_sha256"], "recorded": report["time"],
                    "failures": [{"name": checks[i]["name"], "steps": checks[i]["steps"], "expected": checks[i]["expected"], "observed": notes[i]} for i, value in enumerate(results) if value is False],
                    "kind": "User observations; not independently reproduced or automated proof."}
            state["status"] = "planning" if action == "plan" else "building"
            state["error"] = None
            state["active_run_id"] = uuid.uuid4().hex
            state['run_model_routes']={role:local_failover_route(state[role],list(self.installed_ollama_models),role) for role in ('planner','coder')}
            self.trace(state, "job_started", {"action":action, "execute":execute, "runtime":mode,
                       "repair_budget":attempts, "max_model_calls":max_calls, "cloud_consent":state["job_cloud_consent"], "next_task":state.get("next_task", 0)})
            self.save(state)
            cancel = threading.Event()
            thread = threading.Thread(target=self._job, args=(state, action, options, cancel), daemon=True)
            self.jobs[ident] = (thread, cancel)
            thread.start()

    def calibrate_local(self, model):
        if not self.inference_lock.acquire(blocking=False):raise ValueError('A model request is already running. Wait for it to finish before calibration.')
        try:
            self.model_status.start('ollama',model,'calibration')
            report=calibrate(model,self.root.parent/'local-calibration-v1.json',self.client_factory)
            self.model_status.finish('ollama',model,'responded' if report['passed'] else 'response_rejected')
            return report
        finally:
            if self.model_status.active:self.model_status.finish('ollama',model,'failed')
            self.inference_lock.release()

    def adopt_resume_baseline(self, ident):
        with self.lock:
            state=self.load(ident)
            if state['status'] in ACTIVE or not state.get('approved'):raise ValueError('Stop the job and approve a proposal before adopting a source baseline.')
            checkpoint=state.get('pending_task') or state.get('execution_checkpoint')
            if checkpoint and (checkpoint.get('plan_sha256')!=plan_hash(state['plan']) or checkpoint.get('cursor')!=state['next_task']):raise ValueError('The approved plan or task position changed. Restore a consistent checkpoint; source-baseline adoption cannot approve a different plan.')
            state.pop('pending_task',None);seal_checkpoint(state,self.context_files(ident))
            state.update(status='approved',error=None,checks=None,manual_results={},verification_fingerprint=None)
            state.pop('verification_manifest',None)
            self.trace(state,'resume_baseline_adopted',{'cursor':state['next_task'],'source_sha256':state['execution_checkpoint']['source_sha256']},'user')
            self.event(state,'Kept the current files as the resume baseline. No task advanced; verification is pending. Resume will retry the current task.')
            return self.present(ident)

    def stop(self, ident):
        with self.lock:
            job = self.jobs.get(ident)
            if job:
                job[1].set()
                self.trace(self.load(ident), "stop_requested", {"in_flight_output_will_be_discarded":True}, "user")
        return {"message": "Stop requested. An in-flight model request must return or time out before the job stops; its output will be discarded."}

    def approve(self, ident, plan):
        with self.lock:
            state = self.load(ident)
            if state["status"] in ACTIVE or state["approved"]:
                raise ValueError("Cannot change this proposal while a job runs or after approval.")
            candidate = self.revision_plan(state, plan)
            state["plan_review"] = require_consistent(candidate, state.get("starter")).to_dict()
            if candidate != state.get("plan"):
                state.pop("proposal_source", None)
            state["plan"] = candidate
            plan = state["plan"]
            state["title"] = plan["title"]
            state["approved"], state["status"] = True, "approved"
            self.documents(state)
            if state.get("starter") and not self.context_files(ident):
                files = starter_files(state["starter"])
                self.apply(state, {"files": files, "summary": "Installed reviewed starter: " + CATALOG[state["starter"]]["title"]})
                state["starter_version"] = CATALOG[state["starter"]]["version"]
                # Protect the minimal contract; feature-specific starter tests can be adapted
                # until the actual approved app passes verification.
                state.setdefault("frozen_tests", {})["test_foundation.py"] = hashlib.sha256(files["test_foundation.py"].encode()).hexdigest()
            self.trace(state, "proposal_approved", {"tasks":len(plan["tasks"]), "http_checks":len(plan["checks"]),
                       "manual_checks":len(plan.get("manual_checks", [])), "browser_checks":len(plan.get("browser_checks", []))}, "user")
            self.event(state, "Proposal approved. Requirements and acceptance checks frozen.")
            return state

    def save_proposal(self, ident: str, plan: dict[str, Any]) -> dict[str, Any]:
        """Persist explicit reviewed edits without approval, inference or source writes."""
        with self.lock:
            if self.maintenance:
                raise ValueError("An update is being installed. Wait for the restart.")
            state = self.load(ident)
            if state["approved"] or state["status"] in ACTIVE:
                raise ValueError("Only an idle, unapproved proposal can be edited.")
            candidate = self.revision_plan(state, plan)
            review = require_consistent(candidate, state.get("starter"))
            state.update(plan=candidate, title=candidate["title"], status="proposed", error=None,
                         plan_review=review.to_dict(), failed_candidate=None, plan_is_previous=False,
                         proposal_source={"kind": "user_edit"},
                         planning_stats={"attempts": 0, "fallback_used": False, "source": "user_edit"})
            self.event(state, "Reviewed proposal edits saved. No model call, source change, approval or execution.")
            return state

    def load_starter_plan(self, ident: str) -> dict[str, Any]:
        """Explicit standard-scope recovery; never infer consent or replace approved scope."""
        with self.lock:
            if self.maintenance:
                raise ValueError("An update is being installed. Wait for the restart.")
            state = self.load(ident)
            if state["status"] in ACTIVE or state["approved"] or state.get("baseline_plan") or state.get("parent_id"):
                raise ValueError("Only an idle, unapproved original project can load a standard starter plan.")
            if state.get("starter") != "arcade":
                raise ValueError("Choose the Neon Dodge starter to use its reviewed standard plan.")
            plan = json.loads((Path(__file__).with_name("starters") / "arcade" / "proposal.json").read_text(encoding="utf-8"))
            result = require_consistent(plan, "arcade")
            state.update(plan=plan, title=plan["title"], status="proposed", error=None,
                         failed_candidate=None, plan_is_previous=False, plan_review=result.to_dict(),
                         planning_stats={"attempts": 0, "fallback_used": False, "source": "reviewed_starter"},
                         proposal_source={"kind": "reviewed_starter", "starter": "arcade", "version": CATALOG["arcade"]["version"]})
            self.event(state, "Loaded the reviewed standard Neon Dodge plan at your request. No model call or app execution. Review this standard scope against your idea before approval.")
            return state

    def record_manual(self, ident: str, results: list[bool], notes: list[str] | None = None) -> dict[str, Any]:
        with self.lock:
            if self.maintenance:
                raise ValueError("An update is being installed. Wait for the restart.")
            state = self.load(ident)
            checks = (state.get("plan") or {}).get("manual_checks", [])
            if state["status"] in ACTIVE or not state["approved"] or not (state.get("checks") or {}).get("passed"):
                raise ValueError("Complete automated verification before recording manual results.")
            if not checks or not isinstance(results, list) or len(results) != len(checks) or any(type(v) is not bool for v in results):
                raise ValueError("Record an explicit pass/fail result for every approved manual check.")
            if not evidence_status(state, self.files(ident))["automated_evidence_current"]:
                raise ValueError("Source changed or approved checks changed since verification. Run automated checks again before recording acceptance.")
            notes = [""] * len(checks) if notes is None else notes
            if not isinstance(notes, list) or len(notes) != len(checks) or any(not isinstance(note, str) or len(note) > 2000 for note in notes):
                raise ValueError("Provide a note of at most 2000 characters for each manual check.")
            state["manual_results"] = {"notes": notes, "results": results, "time": self.now(), "source_sha256": state["verification_fingerprint"], "evidence": "User-reported observations, not automated tests."}
            state["status"] = "verified" if all(results) else "needs_attention"
            self.trace(state, "manual_observations", {"results":results, "source_sha256":state["verification_fingerprint"], "notes":notes}, "user")
            self.event(state, "User reported all manual checks passed." if all(results) else "User reported a manual check failed. Add concrete failure notes, save the results, then use Repair files only or Repair & retest. Automated checks alone did not prove it worked.")
            return state

    def review_proposal(self, ident: str, plan: dict[str, Any]) -> dict[str, Any]:
        state = self.load(ident)
        try:
            candidate = self.revision_plan(state, plan)
        except ValueError as exc:
            return Review((Finding("scope_or_structure", "/", str(exc)),)).to_dict()
        return review_plan(candidate, state.get("starter")).to_dict()

    def documents(self, state):
        source = self.directory(state["id"]) / "source"
        plan = state["plan"]
        guide = "# " + plan["title"] + "\n\n" + plan["summary"]
        guide += "\n\n## Approved features\n\n" + "\n".join("- " + feature for feature in plan["features"])
        guide += "\n\n## Architecture and execution contract\n\nPython 3.11+, standard library only. app.py exposes create_server(host, port), /health and a browser interface. Persistence follows the approved plan: browser localStorage belongs to its browser/origin; server SQLite/JSON stays in the app data directory. Network features are limited to the approved scope. No package installation.\n"
        guide += "\n## Build order\n\n" + "\n".join(f'{i+1}. {task["title"]} — {task["instructions"]}' for i, task in enumerate(plan["tasks"]))
        guide += "\n\nTasks run sequentially. Later tasks build on saved files; checkpoints preserve previous versions.\n"
        guide += "\n## Acceptance criteria\n\n" + "\n".join(f'- {check["name"]}: {check["method"]} {check["path"]} → HTTP {check["status"]}' for check in plan["checks"])
        guide += "\n\n" + manual_document(plan) if plan.get("manual_checks") else ""
        guide += "\n\n## Scope boundaries\n\n" + "\n".join("- " + item for item in plan["out_of_scope"])
        guide += "\n\n## Known considerations\n\n" + "\n".join("- " + item for item in plan["risks"])
        guide += "\n\nVerification evidence is in BUILD-REPORT.json after export. A passing report covers the executed checks; it is not a guarantee of every possible behavior.\n"
        guide += "\n## Frozen proposal\n\n```json\n" + json.dumps(plan, indent=2) + "\n```\n"
        (source / "PROJECT.md").write_text(guide, encoding="utf-8")
        (source / "TASKS.md").write_text(task_document(plan), encoding="utf-8")
        (source / "CHECKS.json").write_text(json.dumps(plan["checks"], indent=2), encoding="utf-8")
        if plan.get("browser_checks"):
            (source / "BROWSER-CHECKS.json").write_text(json.dumps(plan["browser_checks"], indent=2), encoding="utf-8")
        elif (source / "BROWSER-CHECKS.json").exists():
            (source / "BROWSER-CHECKS.json").unlink()
        if plan.get("manual_checks"):
            (source / "MANUAL-CHECKS.md").write_text(manual_document(plan), encoding="utf-8")
        elif (source / "MANUAL-CHECKS.md").exists():
            (source / "MANUAL-CHECKS.md").unlink()
        (source / "README.md").write_text(f'# {plan["title"]}\n\n{plan["summary"]}\n\nRequires Python 3.11+. No third-party packages.\n\nRun `python app.py --host 127.0.0.1 --port 8080`, then open http://127.0.0.1:8080.\nOn Windows you can double-click run.bat.\n\nAI-generated code: review it before running. See PROJECT.md for the agreed scope and CHECKS.json for acceptance checks.\nPassing checks is evidence of the tested behaviors, not a guarantee of all requirements.\n', encoding="utf-8")
        (source / "launch.py").write_text(Path(__file__).with_name("launch_template.py").read_text(encoding="utf-8"), encoding="utf-8")
        (source / "run.bat").write_text('@echo off\r\ncd /d "%~dp0"\r\nwhere py >nul 2>&1\r\nif %errorlevel% equ 0 (\r\n    py -3 launch.py\r\n) else (\r\n    python launch.py\r\n)\r\npause\r\n', encoding="utf-8")
        (source / "run.sh").write_text('#!/bin/sh\ncd "$(dirname "$0")" || exit 1\nexec python3 launch.py\n', encoding="utf-8")
        with (source / "README.md").open("a", encoding="utf-8") as readme:
            readme.write("\nThe launch scripts wait for the app to become ready and open your browser. If port 8080 is busy, the launcher chooses another free port and prints the address. Keep its terminal open.\n")

    def files(self, ident):
        root = self.directory(ident) / "source"
        files = {}
        for path in sorted(root.rglob("*")):
            relative = path.relative_to(root)
            if not path.is_file() or any(p.startswith(".") or p == "__pycache__" for p in relative.parts):
                continue
            if path.suffix.lower() not in {".py", ".html", ".css", ".js", ".json", ".txt", ".md", ".bat", ".sh"}:
                continue
            if any(p.is_symlink() for p in [path, *path.parents]):
                continue
            if path.stat().st_size > 1_000_000:
                raise ValueError("A project file exceeds the 1 MB inspection limit.")
            files[relative.as_posix()] = path.read_text(encoding="utf-8")
        return files

    def context_files(self, ident):
        return {name: content for name, content in self.files(ident).items() if name.lower() not in OWNED}

    def checkpoint(self, state, label):
        number = uuid.uuid4().hex
        target = self.directory(state["id"]) / "snapshots" / number
        shutil.copytree(self.directory(state["id"]) / "source", target)
        state["snapshots"].append({"id": number, "label": label, "next_task": state["next_task"], "frozen_tests": copy.deepcopy(state.get("frozen_tests", {}))})
        self.trace(state, "checkpoint_saved", {"checkpoint_id":number, "label":label, "next_task":state["next_task"]})
        self.save(state)

    def _swap_source(self, ident, prepared):
        root = self.directory(ident) / "source"
        previous = root.with_name(".source-before-" + uuid.uuid4().hex)
        os.replace(root, previous)
        try:
            os.replace(prepared, root)
        except BaseException:
            os.replace(previous, root)
            raise
        shutil.rmtree(previous)

    def restore(self, ident, snapshot):
        with self.lock:
            state = self.load(ident)
            if state["status"] in ACTIVE:
                raise ValueError("Stop the current job before restoring.")
            match = next((s for s in state["snapshots"] if s["id"] == snapshot), None)
            if not match:
                raise ValueError("Checkpoint not found.")
            source = self.directory(ident) / "source"
            self.checkpoint(state, "Backup before manual restore")
            staging = source.with_name(".restore-" + uuid.uuid4().hex)
            try:
                shutil.copytree(self.directory(ident) / "snapshots" / snapshot, staging)
                self._swap_source(ident, staging)
            finally:
                if staging.exists():
                    shutil.rmtree(staging)
            state.update(next_task=match["next_task"], status="approved", checks=None, manual_results={}, verification_fingerprint=None, preflight=None, frozen_tests=copy.deepcopy(match.get("frozen_tests", state.get("baseline_frozen_tests", state.get("frozen_tests", {}) if state.get("baseline_plan") else {}))))
            state.pop("verification_manifest", None)
            state.pop("pending_task",None);seal_checkpoint(state,self.context_files(ident))
            self.trace(state, "checkpoint_restored", {"checkpoint_id":snapshot, "next_task":match["next_task"]}, "user")
            self.event(state, "Restored checkpoint: " + match["label"])
            return state

    def apply(self, state, response, repair=False):
        root = self.directory(state["id"]) / "source"
        current = self.files(state["id"])
        files = expand_response(response, current)
        targets, normalized = [], set()
        for name, content in files.items():
            target = safe_file(root, name)
            lower = name.lower()
            if lower in normalized or any(n.lower() == lower and n != name for n in current):
                raise ValueError("Case-colliding filenames are not portable to Windows.")
            normalized.add(lower)
            if lower in OWNED:
                raise ValueError("Model attempted to modify frozen documentation or acceptance checks: " + name + ". These are controller-owned. Put app-specific documentation in APP-GUIDE.md.")
            if not isinstance(content, str) or len(content) > 40000:
                raise ValueError("Generated file is too large or not text.")
            if name in state.get("frozen_tests", {}) and hashlib.sha256(content.encode()).hexdigest() != state["frozen_tests"][name]:
                raise ValueError("Existing app tests are trusted regression tests and cannot be rewritten. Add new tests in another file.")
            if content.strip().lower() in {'new file contents', 'complete file contents', 'file contents', 'your code here'}:
                raise ValueError(name + ': Placeholder text is not source code. Return the actual complete file or exact edits.')
            if name.endswith('.py'):
                try:
                    ast.parse(content, filename=name)
                except (SyntaxError, ValueError) as exc:
                    raise ValueError(name + ': Rejected invalid Python before file replacement: ' + str(exc)) from None
            if name.endswith(('.html', '.htm')) and '<html' in content.lower() and re.search(r'<(?:html|meta|link|body|div)\b[^>]*=\\"', content, re.I) and r'\n' in content:
                raise ValueError(name + ': HTML contains double-escaped markup. Return real text, not an encoded string.')
            targets.append((target, content))
        if sum(len(v) for v in (current | files).values()) > 70000:
            raise ValueError("Project exceeds the 70,000-character merged total file limit. Smaller patches alone cannot reduce this total. No files were replaced. Review the existing file budget without dropping approved features.")
        if sum(len(v) for k, v in (current | files).items() if k.lower() not in OWNED) > SOURCE_LIMIT:
            raise ValueError("Implementation exceeds the 36,000-character merged source limit (cloud and local). Smaller patches do not reduce stored project size. No files were replaced. Review scope or explicitly reduce existing source without dropping approved behavior; changing approved scope requires a new proposal.")
        # All names and contents are validated before any file is written.
        if any(path.is_symlink() for path in root.rglob("*")):
            raise ValueError("Remove symbolic links from this project before model file updates.")
        self.checkpoint(state, "Before " + ("repair" if repair else f'task {state["next_task"] + 1}'))
        staging = root.with_name(".source-update-" + uuid.uuid4().hex)
        try:
            shutil.copytree(root, staging)
            for target, content in targets:
                prepared = staging / target.relative_to(root)
                prepared.parent.mkdir(parents=True, exist_ok=True)
                prepared.write_text(content, encoding="utf-8")
            self._swap_source(state["id"], staging)
        finally:
            if staging.exists():
                shutil.rmtree(staging)
        candidate_saved(state,self.context_files(state["id"]))
        self.trace(state, "files_committed", {"changed_files":file_manifest(files),
                   "before_source_sha256":fingerprint({n:t for n,t in current.items() if n.lower() not in OWNED}),
                   "after_source_sha256":fingerprint(self.context_files(state["id"])), "repair":repair})
        state["manual_results"] = {}
        state["verification_fingerprint"] = None
        if response.get("edits"):
            stats = state.setdefault("generation_stats", {})
            stats["exact_edits_applied"] = stats.get("exact_edits_applied", 0) + len(response["edits"])
        self.event(state, str(response.get("summary", "Source files updated."))[:2000], origin="model_report")

    def generate_and_apply(self, state, payload, cancel, repair=False):
        """Bounded response recovery; pooled local models can advance without writes."""
        state.pop("last_task_support",None)
        payload = prepare_context(generation_contract(payload,self.files(state["id"])),self.context_files(state["id"]))
        payload = focused_handoff(payload,self.context_files(state['id']))
        structured=bool(payload.get('task_packet',{}).get('structured'))
        route=state.get('run_model_routes',{}).get('coder',state['coder']) if state.get('active_run_id') else state['coder']
        chain=[route,*route.get('fallbacks',[]),*([route['fallback']] if route.get('fallback') else [])]
        response_attempts=max(2,len(chain)) if all(entry['provider']=='ollama' for entry in chain) else 2
        if structured:response_attempts=max(response_attempts,min(12,2*len(chain)))
        corrections=set();preferred=None;response_rejections=set() if structured else None
        for attempt in range(response_attempts):
            correcting=preferred;preferred=None
            try:
                response = self.call_model(state, "coder", CODE, json.dumps(payload), cancel,only_model=correcting,response_rejections=response_rejections)
                for _ in range(3):
                    expanded=retrieve_context(response,payload,self.context_files(state['id']))
                    if expanded is None:break
                    payload=expanded
                    state.setdefault('generation_stats',{}).setdefault('context_retrievals',0)
                    state['generation_stats']['context_retrievals']+=1
                    self.trace(state,'task_context_expanded',{'included_files':payload['task_context']['included_files'],'remaining':payload['task_context']['retrievals_remaining']})
                    if cancel.is_set():raise InterruptedError('Stopped before context follow-up.')
                    response=self.call_model(state,'coder',CODE,json.dumps(payload),cancel,response_rejections=response_rejections)
                if isinstance(response,dict) and 'request_context' in response:raise ContextRequestError('Task context retrieval limit reached.')
            except ModelError as exc:
                if correcting and attempt+1<response_attempts:
                    if response_rejections is not None:response_rejections.add(correcting)
                    else:state.setdefault('job_model_rejections',{})['/'.join(correcting)]=exc.category
                    self.event(state,'Focused response correction failed on '+ '/'.join(correcting)+': '+str(exc)+'. Advancing to the remaining configured route.')
                    continue
                if exc.category not in {"format", "parse_error"} or attempt:
                    raise
                error = str(exc)
            except ContextRequestError as exc:
                if attempt:raise
                error=str(exc)
            else:
                if cancel.is_set():
                    raise InterruptedError("Stopped. Model output discarded.")
                try:
                    if payload.get('response_mode')=='complete_files' and (not isinstance(response, dict) or response.get("edits")):
                        raise ValueError("Response recovery requires complete changed files, not more exact edits.")
                    support=existing_task_evidence(response,self.files(state["id"]),payload.get("task_packet"))
                    if support:
                        state['last_task_support']=support
                        candidate_saved(state,self.context_files(state['id']),support)
                        self.trace(state,'task_existing_source_supported',support)
                        self.event(state,'Task source references checked; no files changed. Behavioral verification remains pending.')
                        return
                    response,ignored=remove_unchanged_owned_echoes(response,self.files(state["id"]))
                    validate_task_response(response,self.files(state["id"]),payload.get("task_packet"))
                    self.apply(state, response, repair=repair)
                    if ignored:
                        state.setdefault("generation_stats",{}).setdefault("unchanged_owned_echoes",0)
                        state["generation_stats"]["unchanged_owned_echoes"]+=len(ignored)
                        self.trace(state,"unchanged_owned_echoes_ignored",{"files":ignored,"meaning":"Exact protected contents were not replaced; changed protected files are still rejected."})
                        self.save(state)
                    return
                except ValueError as exc:
                    if state.get("model_calls"):
                        record=state["model_calls"][-1]
                        provider,model=record["provider"],record["model"]
                        self.model_status.reject(provider,model)
                        self.trace(state,"code_response_rejected",{"provider":provider,"model":model,"reason":str(exc),"files_replaced":False})
                        identity=(provider,model)
                        if structured and identity not in corrections and any(message in str(exc) for message in ('Rejected invalid Python','Task scope violation','search must match exactly once','Task produced no source changes')):
                            corrections.add(identity);preferred=identity
                        elif response_rejections is not None:
                            response_rejections.add(identity)
                        elif route.get("fallbacks"):
                            state.setdefault("job_model_rejections",{})[provider+"/"+model]="response_rejected"
                    if attempt+1==response_attempts:
                        raise
                    error = str(exc)
            if cancel.is_set():
                raise InterruptedError("Stopped before response correction.")
            recovery_message="one focused correction on "+'/'.join(preferred) if preferred else "trying the next eligible local model" if route.get('fallbacks') and all(entry['provider']=='ollama' for entry in chain) else "requesting one focused correction"
            self.event(state, "Code response rejected before file replacement; "+recovery_message+": " + error)
            stats = state.setdefault("generation_stats", {})
            stats["rejected_responses"] = stats.get("rejected_responses", 0) + 1
            if structured and (preferred is not None or payload.get('response_mode')=='focused_changes'):
                complete_edit='search must match exactly once' in error
                payload={**payload,'response_validation_error':error,'response_mode':'complete_files' if complete_edit else 'focused_changes',
                    'instruction':'The rejected candidate was NOT saved. Implement only the original task using CURRENT supplied source. '
                    +('Return complete corrected contents only for approved changed/new files; do not return edits, because the previous search did not match. ' if complete_edit else 'Return exact edits for existing files, or complete contents only for approved changed/new files. ')+
                    'Preserve task_packet, its file scope, frozen tests and checks. Do not rewrite other files or inline the UI into app.py. '
                    'Use the error as feedback, never as permission to widen scope. Return existing-source evidence only if the original task is already implemented.'}
                continue
            payload = {**payload, "response_validation_error": error, "response_mode": "complete_files",
                       "files": self.context_files(state["id"]),
                       "instruction": "The previous response was rejected and no file was changed. Recover by returning a nonempty files object with COMPLETE changed source files and optional summary. Do not return edits, diffs, ellipses or an empty object. Read the current source supplied here; repair the original reported problem, preserve frozen tests and approved checks. For a structured task already implemented, you may instead return already_satisfied with a reason and exact current-source evidence. Never invent an unnecessary edit. This overrides the earlier preference for edits."}
            if payload.get('task_context'):
                payload['task_context'].update(included_files=sorted(payload['files']),omitted_files=[],retrievals_remaining=0)

    def _inspect_and_repair(self, state, cancel, remaining, complete=True):
        for attempt in range(remaining + 1):
            if cancel.is_set():
                raise InterruptedError("Stopped before static inspection.")
            state["preflight"] = preflight(self.context_files(state["id"]), complete=complete)
            current = self.context_files(state["id"])
            trusted_issues = []
            try:
                actual_checks = json.loads(self.files(state["id"])["CHECKS.json"])
                if json.dumps(actual_checks, sort_keys=True) != json.dumps(state["plan"]["checks"], sort_keys=True):
                    raise ValueError("changed")
            except (KeyError, ValueError):
                trusted_issues.append("Approved acceptance checks were changed or removed. Restore a checkpoint; model repairs cannot replace the approved checks.")
            if state["plan"].get("manual_checks") and self.files(state["id"]).get("MANUAL-CHECKS.md") != manual_document(state["plan"]):
                trusted_issues.append("Approved manual checklist was changed or removed. Restore its checkpoint; user acceptance must match the frozen proposal.")
            if state["plan"].get("browser_checks"):
                try:
                    if json.loads(self.files(state["id"])["BROWSER-CHECKS.json"]) != state["plan"]["browser_checks"]:
                        raise ValueError("changed")
                except (KeyError, ValueError):
                    trusted_issues.append("Approved browser checks were changed or removed. Restore a checkpoint; repairs cannot weaken them.")
            for name, expected in state.get("frozen_tests", {}).items():
                if name not in current or hashlib.sha256(current[name].encode()).hexdigest() != expected:
                    trusted_issues.append("Trusted regression test was changed or removed: " + name + ". Restore its checkpoint before continuing.")
            state["preflight"]["issues"].extend(trusted_issues)
            state["preflight"]["passed"] = not state["preflight"]["issues"]
            self.trace(state, "static_inspection", {"complete":complete, "passed":state["preflight"]["passed"],
                       "issues":state["preflight"]["issues"], "repair_budget_remaining":remaining})
            self.save(state)
            if trusted_issues:
                state["status"] = "needs_attention"
                self.event(state, "\n".join(trusted_issues))
                return None
            if state["preflight"]["passed"]:
                return remaining
            issues = "\n".join(state["preflight"]["issues"])
            if remaining == 0:
                state["status"] = "needs_attention"
                self.event(state, "Static inspection found incomplete code. No code was executed.\n" + issues)
                return None
            state["status"] = "repairing"
            self.event(state, f"Static repair {attempt+1}: correcting syntax/structure or adding missing tests without executing code.\n" + issues)
            repair_payload={"proposal":state['plan'],"files":self.context_files(state['id']),"source_map":source_map(self.context_files(state['id'])),
                "failure":issues,"frozen_tests":list(state.get('frozen_tests',{})),
                "instruction":"Repair only the reported source syntax/structure or missing behavioral tests. Preserve approved checks and frozen tests; do not implement future tasks. Import the real app in tests and make actual requests. Respect the active task packet when supplied."}
            if state.get('pending_task') and state['plan'].get('task_contract_version')==1:
                index=state['pending_task']['cursor']
                repair_payload.update(current_task=state['plan']['tasks'][index],task_packet=task_packet(state['plan'],index,state['next_task']))
                repair_payload['repair_brief']={'schema':1,'reported_defects':list(state['preflight']['issues']),
                    'editable_files':list(repair_payload['task_packet']['files']),
                    'goal':'Correct these static defects in the current saved candidate, preserving the original approved task and earlier behavior. No future features.',
                    'response_rule':'Return {"files":{"approved/path.py":"complete corrected source"}} or {"edits":[{"file":"approved/path.py","search":"unique exact current text","replace":"corrected text"}]}. failure, frozen_tests, instruction, source_map and repair_brief are input metadata, never filenames. A summary alone is not a repair.',
                    'http_test_rule':'Use urllib.request.Request(url, data=body_bytes, headers=headers, method=method), then urllib.request.urlopen(request, timeout=3). Never pass headers or method directly to urlopen. Keep existing frozen tests unchanged.'}
            self.generate_and_apply(state,repair_payload,cancel,repair=True)
            state["repair_count"] += 1
            remaining -= 1

    def _verify_milestone(self, state, task, task_index, options, cancel, remaining_repairs):
        """Verify an approved check prefix before later tasks build on this increment."""
        limit = max(task["check_indexes"]) + 1
        result = self.milestone_verifier(self.directory(state["id"]) / "source", options.get("runtime", "docker"), cancel, state["plan"]["checks"][:limit])
        if cancel.is_set():
            state["next_task"] = task_index
            seal_checkpoint(state,self.context_files(state["id"]))
            raise InterruptedError("Milestone verification stopped. Resume will retry this task.")
        state["milestones"][-1].update(behavior_verified=result["passed"], checks=limit, result=result)
        self.trace(state, "milestone_verified", {"task":task_index+1, "passed":result["passed"], "checks":limit,
                   "source_sha256":fingerprint(self.context_files(state["id"])), "failure_kind":result.get("failure_kind")})
        self.save(state)
        seen = set()
        while not result["passed"]:
            state["checks"] = result
            current_fingerprint = fingerprint(self.context_files(state["id"]))
            if remaining_repairs == 0 or result.get("failure_kind") == "environment" or current_fingerprint in seen:
                # Re-run the incomplete task on resume; do not advance over failed behavior.
                state["next_task"] = task_index
                seal_checkpoint(state,self.context_files(state["id"]))
                state["status"] = "needs_attention"
                self.event(state, "Milestone check failed. Resume will retry this task. " + str(result.get("diagnosis", "")))
                return None
            seen.add(current_fingerprint)
            self.event(state, "Repairing the failed milestone before proceeding.")
            self.generate_and_apply(state, {"proposal": state["plan"], "task": task, "files": self.context_files(state["id"]), "source_map": source_map(self.context_files(state["id"])), "feedback": failure_feedback(result), "failure": result.get("log", "")[-6500:], "frozen_tests": list(state.get("frozen_tests", {}))}, cancel, repair=True)
            state["repair_count"] += 1
            remaining_repairs -= 1
            remaining_repairs = self._inspect_and_repair(state, cancel, remaining_repairs, complete=False)
            if remaining_repairs is None:
                state["next_task"] = task_index
                seal_checkpoint(state,self.context_files(state["id"]))
                self.save(state)
                return None
            result = self.milestone_verifier(self.directory(state["id"]) / "source", options.get("runtime", "docker"), cancel, state["plan"]["checks"][:limit])
            if cancel.is_set():
                state["next_task"] = task_index
                seal_checkpoint(state,self.context_files(state["id"]))
                raise InterruptedError("Milestone verification stopped. Resume will retry this task.")
            state["milestones"][-1].update(behavior_verified=result["passed"], result=result)
            self.trace(state, "milestone_verified", {"task":task_index+1, "passed":result["passed"], "checks":limit,
                       "source_sha256":fingerprint(self.context_files(state["id"])), "failure_kind":result.get("failure_kind")})
            self.save(state)
        evidence={'passed':True,'http_prefix_count':limit,'source_sha256':fingerprint(self.context_files(state['id'])),'meaning':'Executed approved HTTP prefix only; manual/browser acceptance is separate.'}
        for receipt in state.get('task_receipts',[]):
            if receipt['task']==task_index+1:receipt['milestone_evidence']=evidence
        finish_task(state,self.context_files(state['id']))
        state["checks"] = None
        self.save(state)
        return remaining_repairs

    def _job(self, state, action, options, cancel):
        # A rejected/no-op repair must not erase observations about unchanged source.
        retain_failures = action == "repair" or (action == "build" and any(value is False for value in (state.get("manual_results") or {}).get("results", [])))
        previous_evidence = {key: copy.deepcopy(state.get(key)) for key in ("checks", "manual_results", "verification_fingerprint", "verification_manifest")} if retain_failures else None
        state["job_model_rejections"] = {}
        state['job_provider_rejections'] = {}
        state["job_inference_attempts"] = 0
        state["job_max_model_calls"] = options.get("max_model_calls",64)
        job_started = time.monotonic()
        initial_requests = history.totals_for(state)["requests"]
        initial_repairs = state.get("repair_count", 0)
        try:
            for role,route in state.get('run_model_routes',{}).items():
                if route!=state[role]:
                    self.event(state,'Automatic local backups for '+role+': '+' → '.join(entry['model'] for entry in [route,*route.get('fallbacks',[])])+'. Saved primary and preferences kept; detected models are not proven GPU fits.')
            if action == "plan":
                planner_route=state.get('run_model_routes',{}).get('planner',state['planner'])
                state.pop("planner_truncation_ceiling", None)
                prior_model_records = list(state.get("model_calls", []))
                self.event(state, "Planning with " + state["planner"]["provider"] + "/" + state["planner"]["model"])
                revision = options.get("revision", "")
                if not isinstance(revision, str) or len(revision) > 6000:
                    raise ValueError("Revision must be under 6000 characters.")
                state["last_revision"] = revision
                request = {"task_contract_version":1,"idea": state["idea"], "revision": revision, "previous_proposal": state["plan"],
                           'builder_profile':builder_profile(state.get('run_model_routes',{}).get('coder',state['coder']),CapabilityRegistry(self.root.parent/'model-capabilities-v1.json')),
                           "existing_project": state.get("baseline_plan"), "change_request": state.get("change_request"),
                           "implementation_context": planning_context(self.context_files(state["id"]), (state.get("change_request") or "") + " " + revision) if state.get("baseline_plan") else None,
                           "baseline_evidence": {"parent_id": state.get("parent_id"), "note": "The baseline proposal lists required features. It does not prove the copied code implements them. Use current source and the reported bug."} if state.get("baseline_plan") else None,
                           "starter": CATALOG.get(state.get("starter")),
                           "starter_api_contracts": starter_contracts(state.get("starter")),
                           "verification_capabilities": {"http": True, "manual": True, "browser": "optional local Chromium; request browser_checks only when explicitly asked", "browser_starter": state.get("starter") == "arcade"},
                           "required_plan_fields": {"app_kind": "browser", "behavior_evidence": "nonempty manual_checks or browser_checks"} if state.get("starter") == "arcade" else {},
                           "starter_example_plan": json.loads((Path(__file__).with_name("starters") / "arcade" / "proposal.json").read_text(encoding="utf-8")) if state.get("starter") == "arcade" else None,
                           "file_ownership": generation_contract({})["file_ownership"],
                           "scope_priority": "The latest revision overrides conflicting original details. Preserve requested storage: localStorage must not become SQLite. Preserve UI/game requirements; HTTP delivery never proves gameplay.",
                           "instruction": "For changes, preserve original features in order, append new ones, and plan only work needed for the change. Original checks and existing tests must still pass."}
                state['builder_profile']=request['builder_profile']
                profile=request['builder_profile']
                planning_source=self.context_files(state['id']) if state.get('baseline_plan') else starter_files(state['starter']) if state.get('starter') else {}
                profile['available_files']=sorted(planning_source)
                profile['protected_existing_files']=[name for name in planning_source if name=='test_foundation.py']
                request['starter_source']=planning_context(planning_source,state['idea'],budget=4000) if planning_source else None
                self.event(state,'Builder-sized planning: at most '+str(profile['max_editable_files'])+' editable files and '+str(profile['max_feature_indexes'])+' feature per guided task; smallest configured output ceiling '+str(profile['smallest_output_ceiling'])+' tokens. Criteria remain declarations until tested.')
                def evaluate(candidate: dict[str, Any]) -> tuple[dict[str, Any], Review]:
                    if state.get("starter") == "arcade" and isinstance(candidate, dict) and (candidate.get("app_kind") != "browser" or not (candidate.get("manual_checks") or candidate.get("browser_checks"))):
                        raise ValueError('The arcade starter is a browser game. Return app_kind: "browser" and nonempty manual_checks or browser_checks copied/adapted from starter_example_plan. HTTP checks prove delivery only; do not add a fake backend API.')
                    candidate = self.revision_plan(state, candidate)
                    return candidate, require_consistent(candidate, state.get("starter"))

                def report(candidate: dict[str, Any] | None, result: Review) -> None:
                    if state.get('model_calls') and not planner_route.get('fallbacks'):
                        record = state['model_calls'][-1]
                        record['proposal_valid'] = result.passed
                        if not result.passed: record['failure_class'] = 'schema_error'
                        record['review_findings']=history.redact(result.to_dict()['findings'])
                    state["plan_review"] = result.to_dict()
                    state["failed_candidate"] = candidate if not result.passed else None
                    # Preserve a structurally valid failed candidate for direct editor repair.
                    try:
                        validate_plan(candidate)
                    except (ValueError, TypeError, AttributeError):
                        state["plan_is_previous"] = bool(state.get("plan"))
                    else:
                        state["plan_is_previous"] = False
                        state.pop("proposal_source", None)
                        state["plan"] = candidate
                    self.trace(state, "proposal_review", {"passed":result.passed, "findings":result.to_dict()["findings"]})
                    self.save(state)

                def reviewed(candidate: dict[str, Any]) -> tuple[dict[str, Any], Review]:
                    try:
                        normalized, review_result = evaluate(candidate)
                    except ValueError as exc:
                        normalized = candidate
                        review_result = exc.review if isinstance(exc, ProposalError) else Review((Finding("structure", "/", str(exc)),))
                    report(normalized, review_result)
                    return normalized, review_result

                mode=options.get('plan_mode','single');state['planning_mode']=mode
                if mode=='guided':
                    def checkpoint(draft):
                        state['guided_draft']=draft
                        state['planning_progress']={'stage':'outline saved' if not draft['tasks'] else 'task batch saved',
                            'features_planned':draft['next_feature'],'features_total':len(draft['outline']['features']),
                            'tasks':len(draft['tasks']),'meaning':'Unapproved draft only. Final full-proposal review is still required.'}
                        self.trace(state,'guided_plan_checkpoint',state['planning_progress'])
                        self.event(state,'Guided planning: '+str(draft['next_feature'])+'/'+str(len(draft['outline']['features']))+' features assigned to '+str(len(draft['tasks']))+' tasks. Draft saved; not approved.')
                    def generate_stage(system,payload,validate):
                        self.event(state,'Guided planning: '+('define features and acceptance checks' if payload.get('planning_stage')=='outline' else 'plan feature indexes '+str(payload['target_feature_indexes']))+'.')
                        return self.call_model(state,'planner',system,json.dumps(payload),cancel,review_candidate=lambda candidate:stage_review(validate,candidate))
                    candidate=run_guided(request,generate_stage,checkpoint,cancel,state.get('guided_draft'))
                    candidate,review_result=reviewed(candidate)
                    if not review_result.passed:raise ProposalError(review_result)
                    result=PlanningResult(candidate,review_result,state.get('job_inference_attempts',0),any(record.get('fallback') for record in state.get('model_calls',[]) if id(record) not in {id(old) for old in prior_model_records}))
                    state['planning_progress']['stage']='complete proposal ready for review'
                else:
                    result = PlanningEngine().run(
                        request,
                        lambda payload, fallback: self.call_model(state, "planner", PLAN, json.dumps(payload), cancel, fallback=fallback, allow_fallback=bool(planner_route.get("fallbacks")), review_candidate=reviewed if planner_route.get("fallbacks") else None),
                        evaluate, report, lambda message: self.event(state, message), cancel,
                        has_fallback=bool(planner_route.get("fallback")))
                state.update(plan=result.plan, title=result.plan["title"], status="proposed",
                             plan_review=result.review.to_dict(),
                             planning_stats={"mode":mode,"attempts": state.get('job_inference_attempts',result.attempts), "fallback_used": result.fallback_used or any(record.get("fallback") for record in state.get("model_calls", []) if id(record) not in {id(old) for old in prior_model_records})})
                self.event(state, "Proposal ready. Consistency review passed; no generated code has run. Review the scope and acceptance checks before approval.")
                return
            problem=resume_problem(state,self.context_files(state['id']))
            if problem:
                state.update(status='needs_attention',error=problem)
                self.event(state,problem);return
            if state.get("baseline_plan") and "baseline_frozen_tests" not in state:
                state["baseline_frozen_tests"] = copy.deepcopy(state.get("frozen_tests", {}))
            if options.get("execute"):
                require_runtime(options.get("runtime", "docker"))
                require_browser_runtime(self.directory(state["id"]) / "source", options.get("runtime", "docker"))
            if action == "repair" and options["manual_evidence"]["source_sha256"] != fingerprint(self.context_files(state["id"])):
                raise ValueError("Source changed while preparing the repair. Verify and test the current app again.")
            state["checks"] = None
            state["manual_results"] = {}
            state["verification_fingerprint"] = None
            state.pop("verification_manifest", None)
            state["preflight"] = None
            remaining_repairs = options.get("repairs", 2)
            if action == "repair":
                evidence = options["manual_evidence"]
                state.setdefault("repair_history", []).append({"time": self.now(), "evidence": evidence, "execution_requested": bool(options.get("execute"))})
                state["repair_history"] = state["repair_history"][-20:]
                self.event(state, "Repairing saved failed checks directly. The approved plan and regression tests stay frozen; the repaired app must be tested again.")
                before = fingerprint(self.context_files(state["id"]))
                self.generate_and_apply(state, {"proposal": state["plan"], "files": self.context_files(state["id"]),
                    "source_map": source_map(self.context_files(state["id"])), "manual_evidence": evidence,
                    "frozen_tests": list(state.get("frozen_tests", {})),
                    "instruction": "Repair only the reported implementation defects. Use exact edits for small changes. Trace the actual code from input/spawn through update/collision/render/reset. Do not claim observations were reproduced or tests ran. Preserve all approved features and frozen checks/tests."}, cancel, repair=True)
                state["repair_count"] += 1
                remaining_repairs -= 1
                if before == fingerprint(self.context_files(state["id"])):
                    state["status"] = "needs_attention"
                    self.event(state, "Repair returned unchanged source. Stopped without repeating verification. Failure evidence remains in repair history.")
                    return
            remaining_repairs = self._inspect_and_repair(state, cancel, remaining_repairs, complete=False)
            if remaining_repairs is None:
                return
            for index in range(len(state["plan"]["tasks"]) if action == "repair" else state["next_task"], len(state["plan"]["tasks"])):
                if cancel.is_set():
                    raise InterruptedError("Build stopped. You can resume from the next unfinished task.")
                task = state["plan"]["tasks"][index]
                before_task = self.context_files(state["id"])
                self.trace(state, "task_started", {"task":index+1, "title":task["title"]})
                self.event(state, f'Task {index+1}: {task["title"]}')
                recovered=begin_task(state,index,before_task)
                self.save(state)
                if recovered:self.event(state,'Recovered saved task candidate. Rechecking it without another implementation request.')
                else:
                    self.generate_and_apply(state, {"proposal": state["plan"], "current_task": task, "task_packet":task_packet(state["plan"],index,state["next_task"]), "is_final_task": index == len(state["plan"]["tasks"]) - 1, "files": self.context_files(state["id"]), "source_map": source_map(self.context_files(state["id"])), "frozen_tests": list(state.get("frozen_tests", {}))}, cancel)
                if cancel.is_set():raise InterruptedError('Task candidate saved. Resume will inspect it before requesting more implementation.')
                remaining_repairs = self._inspect_and_repair(state, cancel, remaining_repairs, complete=False)
                if remaining_repairs is None:
                    return
                gate=finish_gate(state,index,self.context_files(state['id']))
                self.trace(state,'task_finish_gate',gate)
                state["status"] = "building"
                state.setdefault("milestones", []).append({"task": index + 1, "title": task["title"], "syntax_passed": True, "behavior_verified": False, "time": self.now()})
                state["next_task"] = index + 1
                after_task = self.context_files(state["id"])
                before_manifest=state['pending_task']['before_files'];after_manifest=file_hashes(after_task)
                changed=sorted(n for n in set(before_manifest)|set(after_manifest) if before_manifest.get(n)!=after_manifest.get(n))
                receipt={"task":index+1,"title":task["title"],"time":self.now(),"before_sha256":state["pending_task"]["before_sha256"],"after_sha256":fingerprint(after_task),"changed_files":changed,"source_changed":bool(changed),"syntax_passed":True,"behavior_verified":False,"task_packet":task_packet(state["plan"],index,index),"source_support":state.get("last_task_support"),"disposition":"source_changed" if changed else "existing_source_supported" if state.get("last_task_support") else "no_change"}
                receipt['finish_gate']=gate
                state["task_receipts"]=[r for r in state.get("task_receipts",[]) if r["task"]!=index+1]+[receipt]
                finish_task(state,after_task)
                self.trace(state, "task_saved", receipt)
                if not changed:self.event(state,"Task saved with no source changes. This is not evidence that its requested behavior was implemented.")
                self.save(state)
                if options.get("execute") and options.get("milestones", True) and task.get("check_indexes") and index + 1 < len(state["plan"]["tasks"]):
                    remaining_repairs = self._verify_milestone(state, task, index, options, cancel, remaining_repairs)
                    if remaining_repairs is None:
                        return
            # Repairs here are text-only model calls. No generated code is run.
            remaining_repairs = self._inspect_and_repair(state, cancel, remaining_repairs)
            if remaining_repairs is None:
                return
            if not options.get("execute"):
                state["status"] = "generated"
                self.event(state, "Source and test files generated; static syntax/structure checks passed. The app has NOT run or been verified. Approve execution for behavioral checks.")
                return
            runtime_repairs = remaining_repairs
            checked_sources = set()
            for attempt in range(runtime_repairs + 1):
                if cancel.is_set():
                    raise InterruptedError("Verification stopped.")
                state["status"] = "checking"
                self.event(state, "Running generated tests and frozen HTTP acceptance checks.")
                checked_fingerprint = fingerprint(self.context_files(state["id"]))
                if checked_fingerprint in checked_sources:
                    state["status"] = "needs_attention"
                    self.event(state, "The repair returned unchanged source. Stopped rather than repeating the same failed verification. Try another model or restore a checkpoint.")
                    return
                checked_sources.add(checked_fingerprint)
                self.trace(state, "verification_started", {"source_sha256":checked_fingerprint, "runtime":options.get("runtime", "docker")})
                result = self.verifier(self.directory(state["id"]) / "source", options.get("runtime", "docker"), cancel)
                state["checks"] = result
                self.trace(state, "verification_finished", {"passed":result.get("passed"), "runtime":result.get("runtime"),
                           "failure_kind":result.get("failure_kind"), "source_sha256":checked_fingerprint,
                           "phases":[{k:v for k,v in phase.items() if k in {"phase","passed","behavior_passed","workspace_cleanup","tests_run","http_checks","asset_checks","app_calls","failure_kind","timed_out"}} for phase in result.get("phases", [])]})
                self.save(state)
                if cancel.is_set():
                    raise InterruptedError("Verification stopped.")
                if result["passed"]:
                    state["frozen_tests"] = {name: hashlib.sha256(text.encode()).hexdigest() for name, text in self.context_files(state["id"]).items() if Path(name).name.startswith("test_") and name.endswith(".py")}
                    state["verification_fingerprint"] = fingerprint(self.context_files(state["id"]))
                    state["verification_manifest"] = file_manifest({n:t for n,t in self.files(state["id"]).items() if n.lower() not in {"build-report.json","run-history.json"}})
                    if previous_evidence and previous_evidence.get("verification_fingerprint") == state["verification_fingerprint"] and any(value is False for value in (previous_evidence.get("manual_results") or {}).get("results", [])):
                        state["manual_results"] = previous_evidence["manual_results"]
                        state["status"] = "needs_attention"
                        self.event(state, "Automated checks passed on unchanged source. Your saved failed gameplay checks still need repair; their results and notes are retained.")
                        return
                    state["status"] = "review_required" if state["plan"].get("manual_checks") else "verified"
                    self.event(state, "Automated checks passed. Download the app and complete the manual checklist before marking it accepted." if state["plan"].get("manual_checks") else "Tests and HTTP acceptance checks passed. Download and try the app; review remaining requirements yourself.")
                    return
                if result.get("failure_kind") == "environment":
                    state["status"] = "needs_attention"
                    self.event(state, "Verification environment failed. Fix the runtime/workspace error below before retrying; application code was not sent for repair.")
                    return
                if remaining_repairs == 0:
                    state["status"] = "needs_attention"
                    self.event(state, "Checks failed. Repair limit reached; inspect the output and files.")
                    return
                state["status"] = "repairing"
                self.event(state, f'Repair attempt {attempt+1}; approved checks and trusted regression tests remain frozen. New unverified tests may be corrected.')
                self.generate_and_apply(state, {"proposal": state["plan"], "files": self.context_files(state["id"]), "failure": result["log"][-6500:], "feedback": failure_feedback(result), "source_map": source_map(self.context_files(state["id"])), "diagnosis": result.get("diagnosis"), "frozen_tests": list(state.get("frozen_tests", {})), "instruction": "Repair the application and, if faulty, unverified test files. Never edit frozen_tests or approved checks. Test the actual imported app, send HTTP requests with timeouts, and preserve every approved feature."}, cancel, repair=True)
                state["repair_count"] += 1
                remaining_repairs -= 1
                remaining_repairs = self._inspect_and_repair(state, cancel, remaining_repairs)
                if remaining_repairs is None:
                    return
        except InterruptedError as exc:
            state["status"] = "stopped"
            self.event(state, str(exc))
        except Exception as exc:
            state["status"], state["error"] = "error", str(exc)[:2000]
            self.event(state, "Stopped with error: " + state["error"])
        finally:
            self.trace(state, "job_finished", {"action":action, "status":state["status"],
                       "seconds":round(time.monotonic()-job_started,3), "next_task":state.get("next_task"),
                       "model_attempts":history.totals_for(state)["requests"]-initial_requests,
                       "repairs_used":state.get("repair_count",0)-initial_repairs, "repair_count_total":state.get("repair_count",0)})
            state.pop("active_run_id", None)
            self.save(state)
            if action == "repair" and previous_evidence and previous_evidence.get("verification_fingerprint") and state.get("status") not in {"verified", "review_required"}:
                try:
                    unchanged = fingerprint(self.context_files(state["id"])) == previous_evidence["verification_fingerprint"]
                except (OSError, ValueError):
                    unchanged = False
                if unchanged:
                    state.update(previous_evidence)
                    self.event(state, "No source change was applied. Saved failed-check results and notes are retained; repair is still pending.")
