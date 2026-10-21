import type {GraphRecord} from './types.ts';
import {FlowEngine} from './engine.ts';

interface Project {id: string; title: string; status: string}
interface HistoryRecord {id: string; kind: string; time: string; data: Record<string,unknown>}
export class ReadOnlyObserver {
  private token='';
  private controller: AbortController | null=null;
  private seen=new Set<string>();
  private timer: ReturnType<typeof setTimeout> | null=null;
  private activeNode='';
  constructor(private engine: FlowEngine,private graph: GraphRecord) {}
  private async get(path: string,signal: AbortSignal): Promise<unknown> {
    const response=await fetch(path,{headers:{'X-Foundry-Token':this.token},cache:'no-store',signal});
    if(!response.ok)throw new Error('Read-only observation returned HTTP '+response.status+'. Reconnect to refresh the session.');
    const text=await response.text();if(text.length>4000000)throw new Error('History exceeds the dashboard observation budget. No records were silently truncated.');
    return JSON.parse(text) as unknown;
  }
  async projects(): Promise<Project[]> {
    this.stop();const controller=new AbortController();this.controller=controller;
    const response=await fetch('/',{cache:'no-store',signal:controller.signal});
    if(!response.ok)throw new Error('Could not read the local session.');
    const doc=new DOMParser().parseFromString(await response.text(),'text/html');
    this.token=doc.querySelector('meta[name="foundry-token"]')?.getAttribute('content')||'';
    if(!this.token)throw new Error('Local session token was not found.');
    const result=await this.get('/api/projects',controller.signal);
    if(!Array.isArray(result))throw new Error('Unexpected project catalogue.');
    return result.filter((item): item is Project=>Boolean(item&&typeof item==='object'&&typeof item.id==='string'&&typeof item.title==='string'));
  }
  watch(id: string,onStatus: (value: string)=>void,onError:(value: string)=>void): void {
    this.stop();this.seen.clear();const controller=new AbortController();this.controller=controller;
    let first=true;
    const poll=async()=>{
      if(controller.signal.aborted)return;
      try {
        const state=await this.get('/api/projects/'+encodeURIComponent(id),controller.signal) as Project;
        const history=await this.get('/api/projects/'+encodeURIComponent(id)+'/history',controller.signal) as {records:HistoryRecord[]};
        if(controller.signal.aborted)return;
        onStatus(state.status);
        // Retained history seeds the cursor. Connecting never replays old completions as live.
        for(const record of history.records||[]) {
          if(this.seen.has(record.id))continue;this.seen.add(record.id);
          if(first)continue;
          const byKind: Record<string,string>={model_attempt:'ModelClient.complete()',proposal_review:'require_consistent()',
            static_inspection:'Workbench._inspect_and_repair()',checkpoint_saved:'Workbench.checkpoint()',
            task_saved:'finish_task()',verification_finished:'verify()',job_finished:'Workbench._job()',
            code_response_rejected:'Workbench.generate_and_apply()'};
          const label=byKind[record.kind];const node=this.graph.nodes.find(node=>node.label===label);
          if(node)this.engine.publish(node.id,record.kind==='code_response_rejected'||record.data.passed===false||record.data.success===false||record.data.status==='error'?'failed':'completed','observed',record.kind+' · '+String(record.data.reason||record.time).slice(0,500));
        }
        first=false;
        if(this.seen.size>10000)throw new Error('Observation session reached 10,000 retained event IDs. Reconnect to begin a fresh cursor.');
        // A snapshot proves only the reported controller state, not missing internal transitions.
        const active=this.graph.nodes.find(node=>node.id==='state-'+state.status.replaceAll('_','-'));
        const next=active && ['planning','building','checking','repairing','queued'].includes(state.status)?active.id:'';
        if(next!==this.activeNode) {
          if(this.activeNode)this.engine.publish(this.activeNode,'idle','observed','Controller left this active state; intermediate transitions are unknown');
          this.activeNode=next;
          if(next)this.engine.publish(next,'running','observed','Current controller snapshot');
        }
      }catch(error) {
        if(controller.signal.aborted)return;
        onError(error instanceof Error?error.message:'Observation unavailable.');this.stop();return;
      }
      if(!controller.signal.aborted)this.timer=setTimeout(()=>{void poll();},1500);
    };
    void poll();
  }
  stop(): void {
    this.controller?.abort();this.controller=null;
    if(this.timer!==null)clearTimeout(this.timer);this.timer=null;
    if(this.activeNode)this.engine.publish(this.activeNode,'idle','observed','Observation stopped');
    this.activeNode='';
  }
}
