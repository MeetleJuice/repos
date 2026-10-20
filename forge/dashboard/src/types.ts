export type Status = 'idle' | 'running' | 'completed' | 'failed';
export type Kind = 'lifecycle' | 'action' | 'api' | 'process' | 'state';
export interface ProcessRecord {
  id: string; label: string; kind: Kind; category: string;
  source: string; line: number; excerpt: string; description: string;
}
export interface LinkRecord {id: string; source: string; target: string; label: string}
export interface FlowRecord {id: string; label: string; category: string; path: string[]; failures: string[]}
export interface GraphRecord {schema: number; baseline: string; nodes: ProcessRecord[]; edges: LinkRecord[]; flows: FlowRecord[]}
export interface Activity {
  sequence: number; nodeId: string; status: Status; mode: 'simulation' | 'observed';
  flow: string; at: number; edgeId?: string;
}
