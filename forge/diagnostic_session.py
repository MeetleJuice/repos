"""One bounded diagnostic session: checks, immutable report, exact export.

No generated code is imported or executed. Optional inference is explicit, fixed,
serialized by SystemTests, and never changes routing or project state.
"""
from __future__ import annotations
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import threading
import time
from typing import Any, Callable
import uuid
from .credentials import atomic_text
from .diagnostic_report import collect_report, export_report
from .system_tests import SystemTests
from .providers import LOCAL_PROVIDERS


def stamp() -> str:
    return datetime.now(timezone.utc).isoformat()


class DiagnosticSession:
    def __init__(self, bench: Any, program_root: Path, runner: SystemTests, updater: Any=None,
                 collector: Callable[...,dict[str,Any]]=collect_report) -> None:
        self.bench,self.root,self.runner,self.updater=bench,program_root,runner,updater
        self.collector=collector
        self.directory=bench.root.parent/'diagnostics'
        self.lock=threading.RLock();self.cancel=threading.Event()
        self.worker: threading.Thread | None=None
        self.state: dict[str,Any]={'available':False,'status':'idle'}
        self.report: dict[str,Any] | None=None
        try:
            path=self.directory/'session-v1.json'
            if not self.directory.is_symlink() and not path.is_symlink() and path.stat().st_size<200000:
                saved=json.loads(path.read_text(encoding='utf-8'))
                if isinstance(saved,dict) and saved.get('schema')==1:
                    self.state=saved
                    if saved.get('status')=='running':self.state.update(status='interrupted',phase='interrupted',download_ready=False)
                    report_path=self.directory/'session-report-v1.json'
                    if not report_path.is_symlink() and report_path.stat().st_size<=24100000:
                        report=json.loads(report_path.read_text(encoding='utf-8'))
                        evidence=report.get('evidence') if isinstance(report,dict) else None
                        completed=evidence.get('diagnostic_session') if isinstance(evidence,dict) else None
                        if isinstance(completed,dict) and completed.get('id')==saved.get('id') and completed.get('download_ready') is True:
                            self.report=report;self.state=copy.deepcopy(completed)
        except (OSError,ValueError,TypeError):pass

    def _persist(self) -> None:
        self.directory.mkdir(parents=True,exist_ok=True)
        if self.directory.is_symlink():raise OSError('Diagnostic directory is a symbolic link.')
        path=self.directory/'session-v1.json'
        if path.is_symlink():raise OSError('Diagnostic session path is a symbolic link.')
        atomic_text(path,json.dumps(self.state,indent=2)+'\n')

    def status(self) -> dict[str,Any]:
        with self.lock:
            result=copy.deepcopy(self.state)
            if result.get('download_ready') and self.report:
                result['report']={key:copy.deepcopy(self.report.get(key)) for key in ('id','created_at','summary','findings','completeness')}
                tests=self.report.get('evidence',{}).get('system_tests',{})
                result['checks']={key:copy.deepcopy(tests.get(key)) for key in ('id','status','rows')}
        test_id=result.get('test_report_id')
        current=self.runner.status()
        if result.get('status')=='running' and current.get('id')==test_id:
            result['checks']={key:current.get(key) for key in ('id','status','active_check','rows','planned_probes','completed_probes')}
        return result

    def start(self, project_id: str | None, profiles: list[dict[str,Any]], mode: str='quick', cloud_consent: bool=False) -> dict[str,Any]:
        if mode not in {'quick','local','planning','cloud'}:raise ValueError('Choose quick, local, planning or cloud diagnostics.')
        if mode=='cloud' and not cloud_consent:raise ValueError('Explicitly allow fixed cloud probes. Charges may apply; no project content is sent.')
        if mode in {'local','planning'}:
            from .system_tests import probe_targets
            profiles=[entry for entry in probe_targets(profiles) if entry['provider'] in LOCAL_PROVIDERS]
        if project_id:self.bench.load(project_id)
        with self.lock:
            if self.worker and self.worker.is_alive():raise ValueError('Diagnostics are already running. Stop or wait for this session.')
            self.cancel.clear();self.report=None
            self.state={'schema':1,'available':True,'id':uuid.uuid4().hex,'project_id':project_id,'mode':mode,
                        'status':'running','phase':'checks','started':stamp(),'finished':None,'download_ready':False,
                        'test_report_id':None,'checks_skipped_reason':None,'generated_code_executed':False,
                        'project_content_sent':False,'routes_changed':False,'cloud_consent':cloud_consent}
            self._persist()
            self.worker=threading.Thread(target=self._run,args=(copy.deepcopy(profiles),),daemon=True)
            try:self.worker.start()
            except RuntimeError:
                self.state.update(status='failed',phase='failed',finished=stamp());self._persist();raise
        return self.status()

    def stop(self) -> dict[str,Any]:
        with self.lock:
            self.cancel.set();ident=self.state.get('test_report_id')
        if self.runner.status().get('id')==ident:self.runner.stop()
        return self.status()

    def _run(self, profiles: list[dict[str,Any]]) -> None:
        started=time.monotonic();tests: dict[str,Any]={'available':False,'rows':[]}
        ident=self.state['id'];project_id=self.state['project_id'];mode=self.state['mode']
        self.bench.diagnostics.record('diagnostic_session_started',{'session_id':ident,'mode':mode},project_id=project_id)
        try:
            with self.bench.lock:
                busy=bool(self.bench.maintenance or getattr(self.bench,'idea_busy',False) or getattr(self.bench,'test_busy',False)
                          or any(t.is_alive() for t,_ in self.bench.jobs.values()))
            if busy:
                with self.lock:self.state['checks_skipped_reason']='workbench_busy'
            elif self.cancel.is_set():
                with self.lock:self.state['checks_skipped_reason']='stopped_before_checks'
            elif not self.cancel.is_set():
                try:
                    result=self.runner.start(profiles,mode!='quick',self.state['cloud_consent'],project_id,
                                             planning=mode=='planning',session_id=ident)
                except ValueError:
                    with self.lock:self.state['checks_skipped_reason']='workbench_became_busy'
                else:
                    with self.lock:self.state['test_report_id']=result['id'];self._persist()
                    worker=self.runner.worker
                    if worker is not None:
                        while worker.is_alive():
                            if self.cancel.is_set() and self.runner.status().get('id')==result['id']:self.runner.stop()
                            worker.join(0.1)
                    tests=self.runner.result(result['id'])
                    if not tests:raise ValueError('The owned test report is unavailable.')
            with self.lock:
                self.state['phase']='collecting';self._persist()
            # Snapshot is supplied explicitly: a newer independent Test run must
            # never be substituted for the checks owned by this session.
            report=self.collector(self.bench,self.root,self.updater,project_id,test_snapshot=tests)
            with self.lock:
                outcome='stopped' if self.cancel.is_set() else 'partial' if self.state['checks_skipped_reason'] or tests.get('status')!='finished' or tests.get('exception_type') or tests.get('persistence_failed') else 'finished'
                self.state.update(status=outcome,phase='ready',finished=stamp(),seconds=round(time.monotonic()-started,3),
                                  report_id=report['id'],download_ready=True,
                                  checks_passed=sum(r.get('status')=='passed' for r in tests.get('rows',[])),
                                  checks_failed=sum(r.get('status')=='failed' for r in tests.get('rows',[])),
                                  checks_skipped=sum(r.get('status')=='skipped' for r in tests.get('rows',[])))
                session=copy.deepcopy(self.state)
                report['evidence']['diagnostic_session']=session
                report['summary']['diagnostic_session']={key:session[key] for key in (
                    'id','status','mode','test_report_id','checks_skipped_reason','checks_passed','checks_failed','checks_skipped')}
                if outcome!='finished':
                    report['completeness']['complete']=False
                    report['completeness']['omissions'].append('Diagnostic checks were interrupted or skipped; see diagnostic_session.')
                path=self.directory/'session-report-v1.json'
                if path.is_symlink():raise OSError('Diagnostic report path is a symbolic link.')
                atomic_text(path,json.dumps(report,ensure_ascii=False,indent=2)+'\n')
                self.report=report;self._persist()
        except Exception as exc:
            with self.lock:
                self.state.update(status='failed',phase='failed',finished=stamp(),exception_type=type(exc).__name__,download_ready=False)
                try:self._persist()
                except OSError:pass
        finally:
            self.bench.diagnostics.record('diagnostic_session_finished',{'session_id':ident,'status':self.state['status'],
                'report_id':self.state.get('report_id'),'seconds':round(time.monotonic()-started,3)},project_id=project_id)

    def export(self, ident: str) -> bytes:
        with self.lock:
            if ident!=self.state.get('id') or not self.state.get('download_ready') or not self.report:
                raise ValueError('This diagnostic snapshot is unavailable. Finish or rerun diagnostics before downloading.')
            return export_report(self.report)
