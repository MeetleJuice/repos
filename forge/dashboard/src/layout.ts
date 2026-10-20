import ELK from 'elkjs/lib/elk-api.js';
import type {ElkNode} from 'elkjs/lib/elk-api.js';
import type {GraphRecord} from './types.ts';

export const WIDTH=260;
export const HEIGHT=108;
export interface Point {x: number; y: number}
export interface Layout {positions: Record<string,Point>; routes: Record<string,Point[]>}

/** ELK runs in a feature-owned worker, never on the inference/runtime thread. */
export async function layoutGraph(graph: GraphRecord, signal: AbortSignal): Promise<Layout> {
  const elk=new ELK({workerFactory:()=>new Worker('/dashboard/assets/elk-worker.js')});
  let rejectLayout:(reason:Error)=>void=()=>{};
  const cancelled=new Promise<never>((_,reject)=>{rejectLayout=reject;});
  const abort=()=>{elk.terminateWorker();rejectLayout(new Error('Layout cancelled.'));};
  signal.addEventListener('abort',abort,{once:true});
  const deadline=setTimeout(()=>{elk.terminateWorker();rejectLayout(new Error('Layout exceeded its 20-second budget.'));},20000);
  try {
    if(signal.aborted)throw new Error('Layout cancelled.');
    const result=await Promise.race([cancelled,elk.layout<ElkNode>({id:'foundry-flow',layoutOptions:{
      'elk.algorithm':'layered','elk.direction':'DOWN','elk.edgeRouting':'ORTHOGONAL',
      'elk.spacing.nodeNode':'38','elk.layered.spacing.nodeNodeBetweenLayers':'80',
      'elk.layered.considerModelOrder.strategy':'NODES_AND_EDGES',
      'elk.layered.crossingMinimization.strategy':'LAYER_SWEEP'
    },children:graph.nodes.map(node=>({id:node.id,width:WIDTH,height:HEIGHT,
      layoutOptions:{'elk.portConstraints':'FIXED_POS'},
      ports:[{id:node.id+'.in',width:0,height:0,x:WIDTH/2,y:0},{id:node.id+'.out',width:0,height:0,x:WIDTH/2,y:HEIGHT}]})),
      edges:graph.edges.map(edge=>({id:edge.id,sources:[edge.source+'.out'],targets:[edge.target+'.in']}))})]);
    if(signal.aborted)throw new Error('Layout cancelled.');
    const positions: Layout['positions']={};const routes: Layout['routes']={};
    for(const child of result.children||[])positions[child.id]={x:child.x||0,y:child.y||0};
    for(const edge of result.edges||[]) {
      const section=edge.sections?.[0];
      if(section)routes[edge.id]=[section.startPoint,...(section.bendPoints||[]),section.endPoint];
    }
    return {positions,routes};
  }finally {clearTimeout(deadline);signal.removeEventListener('abort',abort);elk.terminateWorker();}
}
