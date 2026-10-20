import type {Activity, FlowRecord, GraphRecord, Status} from './types.ts';

/** Timed dry-run only. This engine cannot fetch, mutate projects or start jobs. */
export class FlowEngine {
  private listeners = new Set<(event: Activity) => void>();
  private timer: ReturnType<typeof setTimeout> | null = null;
  private queue: {nodeId: string; flow: string; fail: boolean; previous?: string}[] = [];
  private cursor = 0;
  private sequence = 0;
  private generation = 0;
  private delay = 600;
  private active = false;
  private paused = false;
  private graph: GraphRecord;
  constructor(graph: GraphRecord) {this.graph=graph;}
  subscribe(listener: (event: Activity) => void): () => void {
    this.listeners.add(listener);return () => {this.listeners.delete(listener);};
  }
  /** Validated pub/sub entry point for an optional real, read-only event source. */
  publish(nodeId: string, status: Status, mode: 'simulation'|'observed', flow: string, edgeId?: string): void {
    if(!this.graph.nodes.some(node => node.id===nodeId))throw new Error('Unknown graph node: '+nodeId);
    if(!['idle','running','completed','failed'].includes(status))throw new Error('Unknown node status.');
    if(edgeId && !this.graph.edges.some(edge => edge.id===edgeId))throw new Error('Unknown graph edge.');
    const event: Activity={sequence:++this.sequence,nodeId,status,mode,flow,at:Date.now(),edgeId};
    for(const listener of this.listeners)listener(event);
  }
  play(flows: FlowRecord[], delay: number): void {
    this.stop();this.delay=Math.max(10,Math.min(2500,delay));
    this.queue=[];
    for(const flow of flows) {
      for(let index=0;index<flow.path.length;index++) {
        const nodeId=flow.path[index];const previous=flow.path[index-1];
        if(!this.graph.nodes.some(node => node.id===nodeId))throw new Error('Scenario references missing node '+nodeId);
        if(previous && !this.graph.edges.some(edge => edge.source===previous && edge.target===nodeId))throw new Error('Scenario has no source-derived transition '+previous+' → '+nodeId);
        this.queue.push({nodeId,previous,flow:flow.label,fail:flow.failures.includes(nodeId)});
      }
    }
    this.active=true;this.paused=false;this.cursor=0;this.tick(this.generation);
  }
  private tick(generation: number): void {
    if(!this.active || this.paused || generation!==this.generation)return;
    const item=this.queue[this.cursor];
    if(!item){this.active=false;return;}
    const edge=this.graph.edges.find(edge => edge.source===item.previous && edge.target===item.nodeId);
    this.publish(item.nodeId,'running','simulation',item.flow,edge?.id);
    this.timer=setTimeout(() => {
      this.timer=null;if(generation!==this.generation || !this.active)return;
      this.publish(item.nodeId,item.fail?'failed':'completed','simulation',item.flow,edge?.id);
      this.cursor++;this.tick(generation);
    },this.delay);
  }
  pause(): void {
    if(!this.active || this.paused)return;
    this.paused=true;this.generation++;
    if(this.timer!==null)clearTimeout(this.timer);this.timer=null;
  }
  resume(): void {
    if(!this.active || !this.paused)return;
    this.paused=false;this.tick(this.generation);
  }
  stop(): void {
    this.generation++;
    if(this.timer!==null)clearTimeout(this.timer);this.timer=null;
    const item=this.queue[this.cursor];
    if(this.active && item)this.publish(item.nodeId,'idle','simulation',item.flow);
    this.active=false;this.paused=false;
  }
  progress(): {running: boolean; paused: boolean; cursor: number; total: number} {
    return {running:this.active,paused:this.paused,cursor:this.cursor,total:this.queue.length};
  }
  dispose(): void {this.stop();this.listeners.clear();this.queue=[];}
}
