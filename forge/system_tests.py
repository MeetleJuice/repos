"""Explicit bounded Test runs; no project source, shell commands or automatic routing."""
from __future__ import annotations
import copy
from functools import partial
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
from typing import Any, Callable
import uuid
from .credentials import atomic_text
from .diagnostics import sanitize_event_data
from .models import ModelClient, ModelError
from .providers import LOCAL_PROVIDERS

MAX_PROBES = 9


def read_tests(path: Path, active: bool | None = None) -> dict[str, Any]:
    try:
        if path.parent.is_symlink() or path.is_symlink() or path.stat().st_size>200000:return {'available':False,'failure_class':'invalid_test_report'}
        value=json.loads(path.read_text(encoding='utf-8'))
        if isinstance(value,dict) and value.get('schema')==1:
            rows=value.get('rows',[])
            if not isinstance(rows,list) or not all(isinstance(row,dict) and row.get('status') in ('passed','failed','skipped') for row in rows):
                return {'available':False,'failure_class':'invalid_test_report'}
            if active is False and value.get('status')=='running':
                value={**value,'status':'interrupted','interrupted_before_completion':True}
            return sanitize_event_data('system_tests',value)
    except (OSError,ValueError):pass
    return {'available':False}


def probe_targets(profiles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One saved model per cloud provider and up to two saved local models."""
    cloud: dict[str,dict[str,Any]]={};local: dict[tuple[str,str],dict[str,Any]]={}
    for profile in profiles:
        if profile.get('provider') in LOCAL_PROVIDERS and isinstance(profile.get('model'),str):
            local.setdefault((profile['provider'],profile['model']),profile)
    for profile in profiles:
        for entry in [profile,*profile.get('fallbacks',[]),*([profile['fallback']] if profile.get('fallback') else [])]:
            if not isinstance(entry,dict) or not isinstance(entry.get('model'),str):continue
            provider=entry.get('provider')
            if provider in LOCAL_PROVIDERS:
                if len(local)<2:local.setdefault((provider,entry['model']),entry)
            elif isinstance(provider,str):cloud.setdefault(provider,entry)
    return copy.deepcopy([*cloud.values(),*local.values()][:MAX_PROBES])


def catalogue_result(provider: str, result: dict[str, Any]) -> dict[str, Any]:
    return {'provider':provider,
        'status':'passed' if result.get('status')=='catalogue_available' else 'skipped' if result.get('status') in {'missing_key','missing_configuration'} else 'failed',
        'category':result.get('status'),'models_count':len(result.get('models',[])),'generation_tested':False,'seconds':None}


class SystemTests:
    def __init__(self, bench: Any, catalogues: Callable[[], dict[str, Any]], local: Callable[[], dict[str, Any]]) -> None:
        self.bench=bench;self.catalogues=catalogues;self.local=local
        self.path=bench.root.parent/'diagnostics'/'system-tests-v1.json'
        self.lock=threading.RLock();self.cancel=threading.Event();self.worker: threading.Thread | None=None
        self.report=read_tests(self.path)
        self.completed: dict[str, dict[str,Any]] = {}
        if self.report.get('status')=='running':self.report['status']='interrupted'

    def status(self) -> dict[str, Any]:
        with self.lock:return copy.deepcopy(self.report)

    def result(self, ident: str) -> dict[str,Any]:
        with self.lock:return copy.deepcopy(self.completed.get(ident, {}))

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True,exist_ok=True)
        if self.path.parent.is_symlink():raise OSError('Diagnostic directory is a symbolic link.')
        atomic_text(self.path,json.dumps(sanitize_event_data('system_tests',self.report),indent=2)+'\n')

    def stop(self) -> dict[str, Any]:
        self.cancel.set();return self.status()

    def start(self, profiles: list[dict[str, Any]], generation: bool=False, cloud_consent: bool=False, project_id: str | None=None, planning: bool=False, session_id: str | None=None) -> dict[str, Any]:
        targets=probe_targets(profiles) if generation else []
        if any(target['provider'] not in LOCAL_PROVIDERS for target in targets) and not cloud_consent:
            raise ValueError('Allow the fixed cloud model probes explicitly. Charges may apply; no project content is sent.')
        with self.bench.lock:
            if self.bench.maintenance or getattr(self.bench,'idea_busy',False) or getattr(self.bench,'test_busy',False) or any(t.is_alive() for t,_ in self.bench.jobs.values()):
                raise ValueError('Finish or stop active work before running system tests.')
            self.project_snapshot=copy.deepcopy(self.bench.load(project_id)) if project_id else None
            if not self.bench.inference_lock.acquire(blocking=False):raise ValueError('A model request is already running.')
            self.bench.test_busy=True
        with self.lock:
            self.cancel.clear()
            self.report={'schema':1,'available':True,'id':uuid.uuid4().hex,'status':'running',
                'session_id':session_id,'planning_probe_requested':planning,
                'started':datetime.now(timezone.utc).isoformat(),'generation_requested':generation,
                'cloud_consent':cloud_consent,'planned_probes':len(targets),'probe_limit':MAX_PROBES,'rows':[],
                'generated_code_executed':False,'project_content_sent':False,'routes_changed':False}
        self.worker=threading.Thread(target=self._run,args=(targets,),daemon=True)
        try:self.worker.start()
        except RuntimeError:
            with self.bench.lock:self.bench.test_busy=False;self.bench.inference_lock.release()
            with self.lock:self.report['status']='failed'
            raise
        return self.status()

    def _row(self, code: str, operation: Callable[[], dict[str, Any]]) -> None:
        if self.cancel.is_set():return
        started=time.monotonic()
        with self.lock:self.report['active_check']=code
        try:result=operation();row={'code':code,**result}
        except Exception as exc:
            row={'code':code,'status':'failed','exception_type':type(exc).__name__,
                 'failure_class':getattr(exc,'category','test_error')}
            if isinstance(exc,ModelError):row['http_status']=exc.http_status;row['transport_kind']=exc.transport_kind
        row.setdefault('seconds',round(time.monotonic()-started,3));row['report_id']=self.report['id']
        with self.lock:
            self.report['active_check']=None
            self.report['rows'].append(sanitize_event_data('system_test_result',row));self._save()
        self.bench.diagnostics.record('system_test_result',row)

    def _storage(self) -> dict[str, Any]:
        with tempfile.TemporaryDirectory(prefix='system-test-',dir=self.path.parent) as temp:
            path=Path(temp)/'probe.sqlite3'
            connection=sqlite3.connect(path)
            try:connection.execute('CREATE TABLE probe (value INTEGER)');connection.execute('INSERT INTO probe VALUES (7)');connection.commit()
            finally:connection.close()
            connection=sqlite3.connect(path)
            try:passed=connection.execute('SELECT value FROM probe').fetchone()==(7,)
            finally:connection.close()
        return {'status':'passed' if passed else 'failed','restart_read':passed}

    def _controller(self) -> dict[str, Any]:
        from .planning_diagnostics import classify_finding
        from .outline_planning import validate_scope
        validate_scope({'title':'Test','summary':'Fixed scope fixture','features':['Save records'],'out_of_scope':[],
            'risks':[],'app_kind':'server','context_policy':'focused_v1','task_contract_version':1})
        actual=classify_finding('guided_contract','/','Every check needs contains, nonempty json_contains, or json_equals.')
        return {'status':'passed' if actual==('assertion_required','/checks') else 'failed','cases':2}

    def _probe(self, target: dict[str, Any]) -> dict[str, Any]:
        provider,model=target['provider'],target['model'];client=self.bench.client_factory(provider,model)
        if isinstance(client,ModelClient):client.options={'num_ctx':4096,'num_predict':1024,'structured_outputs':True,'timeout_seconds':120 if provider in LOCAL_PROVIDERS else 30}
        self.bench.model_status.start(provider,model,'system_test')
        outcome='failed'
        try:
            result=client.complete('Return JSON only. Fixed diagnostic fixture; no project or tools. Return exactly {"answer":7}.','{"numbers":[2,5],"operation":"add"}')
            passed=result=={'answer':7};outcome='responded' if passed else 'schema_error'
            return {'provider':provider,'model':model,'status':'passed' if passed else 'failed',
                'failure_class':None if passed else 'probe_assertion','response_received':True,
                'response_accepted':passed,'http_response_received':True,
                **getattr(client,'last_usage',{}),**{key:value for key,value in getattr(client,'last_metadata',{}).items()
                    if key in {'http_status','transport_attempted','ollama_tokens_per_second','ollama_load_seconds','ollama_eval_seconds','finish_reason',
                               'configured_num_ctx','requested_max_output_tokens','timeout_seconds','structured_outputs_requested','observed_output_tokens','response_format_mode','response_model','response_provider','api_family'}}}
        except ModelError as exc:
            outcome=exc.category
            metadata=getattr(client,'last_metadata',{})
            received=metadata.get('finish_reason') is not None or metadata.get('observed_output_tokens') is not None or exc.category in {'truncated_output','format','parse_error','schema_error'}
            return {'provider':provider,'model':model,'status':'failed','failure_class':exc.category,
                'http_status':exc.http_status or metadata.get('http_status'),'transport_kind':exc.transport_kind,'response_received':received,
                'response_accepted':False,'http_response_received':exc.http_status is not None or metadata.get('http_status') is not None or received,
                **{key:value for key,value in getattr(client,'last_metadata',{}).items() if key in {
                    'configured_num_ctx','requested_max_output_tokens','timeout_seconds','structured_outputs_requested','observed_output_tokens','transport_attempted','finish_reason','response_format_mode','response_model','response_provider','api_family'}}}
        finally:self.bench.model_status.finish(provider,model,outcome,remember=False)

    def _project_review(self) -> dict[str, Any]:
        from .coherence import audit_plan
        state=self.project_snapshot
        if not state or not isinstance(state.get('plan'),dict):return {'status':'skipped','failure_class':'no_selected_proposal','executed':False}
        result=audit_plan(state['plan'],state.get('starter'))
        return {'status':'passed' if result['passed'] else 'failed','project_id':state['id'],**result}

    def _planning_probe(self, target: dict[str,Any]) -> dict[str,Any]:
        from .planner_probe import run_probe
        provider,model=target['provider'],target['model']
        client=self.bench.client_factory(provider,model)
        self.bench.model_status.start(provider,model,'system_test')
        outcome='failed'
        try:
            result=run_probe(client,provider,model,target,self.bench.root.parent/'model-capabilities-v1.json',version=2)
            outcome='responded' if result['response_accepted'] else 'schema_error'
            return result
        except ModelError as exc:
            outcome=exc.category
            metadata=getattr(client,'last_metadata',{})
            return {'provider':provider,'model':model,'status':'failed','failure_class':exc.category,
                    'http_status':exc.http_status,'transport_kind':exc.transport_kind,'response_accepted':False,
                    'response_received':metadata.get('finish_reason') is not None or metadata.get('observed_output_tokens') is not None,
                    **{key:value for key,value in getattr(client,'last_metadata',{}).items() if key in {
                        'configured_num_ctx','requested_max_output_tokens','observed_output_tokens','finish_reason',
                        'timeout_seconds','transport_attempted','schema_sha256','schema_version','response_format_mode',
                        'required_context_tokens','context_shortfall_tokens','effective_context_tokens','input_estimate_tokens','reserved_text_output_tokens'}}}
        finally:self.bench.model_status.finish(provider,model,outcome,remember=False)

    def _project_execution(self) -> dict[str, Any]:
        from .run_diagnostics import latest_execution
        from .diagnostic_report import _safe_history
        state = self.project_snapshot
        if not state:
            return {'status': 'skipped', 'failure_class': 'no_selected_project', 'executed': False}
        history = _safe_history(self.bench.directory(state['id']))
        result = latest_execution(history.get('records', []), history.get('coverage'))
        if not result['available']:
            return {'status': 'skipped', 'failure_class': 'no_execution_history', 'executed': False}
        # An audit succeeded; the recorded project outcome is separate.
        return {**result, 'recorded_status': result.get('status'), 'status': 'passed', 'executed': False}

    def _run(self, targets: list[dict[str, Any]]) -> None:
        try:
            self.path.parent.mkdir(parents=True,exist_ok=True)
            if self.path.parent.is_symlink():raise OSError('Diagnostic directory is a symbolic link.')
            self.bench.diagnostics.record('system_tests_started',{'report_id':self.report['id'],'planned_probes':len(targets)})
            self._row('private_storage',self._storage);self._row('controller_smoke',self._controller)
            from .coherence import guard_probes
            self._row('planning_guards',guard_probes);self._row('project_plan',self._project_review)
            from .stage_context import guard_probes as stage_guards
            self._row('stage_harness_guards',stage_guards)
            from .run_diagnostics import loop_guards
            self._row('loop_guards',loop_guards);self._row('project_execution',self._project_execution)
            self._row('local_catalogue',lambda:{'status':'passed' if self.local().get('connected') else 'failed','generation_tested':False})
            if not self.cancel.is_set():
                catalogue_started=time.monotonic();catalogues=self.catalogues()
                with self.lock:self.report['catalogue_sweep_seconds']=round(time.monotonic()-catalogue_started,3)
                for provider,result in catalogues.items():
                    self._row('provider_catalogue',partial(catalogue_result,provider,result))
            for target in targets:
                self._row('planner_stage_probe' if self.report.get('planning_probe_requested') else 'fixed_json_probe',
                          partial(self._planning_probe if self.report.get('planning_probe_requested') else self._probe,target))
            if self.report['generation_requested'] and not targets:
                self._row('model_probe_setup',lambda:{'status':'skipped','failure_class':'no_saved_models','inference_tested':False})
        except Exception as exc:
            with self.lock:self.report['exception_type']=type(exc).__name__
        finally:
            with self.lock:
                self.report.update(status='stopped' if self.cancel.is_set() else 'finished',finished=datetime.now(timezone.utc).isoformat(),
                    completed_probes=sum(row['code'] in {'fixed_json_probe','planner_stage_probe'} for row in self.report['rows']),
                    not_attempted_probes=max(0,len(targets)-sum(row['code'] in {'fixed_json_probe','planner_stage_probe'} for row in self.report['rows'])),
                    passed=not self.cancel.is_set() and not self.report.get('exception_type') and all(row['status'] in {'passed','skipped'} for row in self.report['rows']))
                try:self._save()
                except OSError:self.report['persistence_failed']=True
                self.completed[self.report['id']]=copy.deepcopy(self.report)
                while len(self.completed)>3:self.completed.pop(next(iter(self.completed)))
            self.bench.diagnostics.record('system_tests_finished',{'report_id':self.report['id'],'status':self.report['status'],'passed':self.report['passed'],'rows':len(self.report['rows'])})
            with self.bench.lock:self.bench.test_busy=False;self.bench.inference_lock.release()
