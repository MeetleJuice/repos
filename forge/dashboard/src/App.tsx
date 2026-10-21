import {StrictMode,useCallback,useEffect,useMemo,useRef,useState} from 'react';
import {createRoot} from 'react-dom/client';
import {ReactFlow,ReactFlowProvider,Background,BackgroundVariant,Controls,MiniMap,Handle,Position,MarkerType,BaseEdge,getSmoothStepPath,useReactFlow} from '@xyflow/react';
import type {Node,Edge,NodeProps,EdgeProps,NodeTypes,EdgeTypes} from '@xyflow/react';
import graphData from './graph.json';
import {FlowEngine} from './engine.ts';
import {ReadOnlyObserver} from './observer.ts';
import {layoutGraph,WIDTH,HEIGHT} from './layout.ts';
import type {Layout,Point} from './layout.ts';
import type {Activity,GraphRecord,ProcessRecord,Status} from './types.ts';

const graph=graphData as GraphRecord;
const categories=['All processes','Workbench & session','Planning & approval','Build & verification','Models & routing','Delivery & recovery'];
type ProcessData=Record<string,unknown>&{record:ProcessRecord;status:Status;selected?:boolean};
type ProcessNode=Node<ProcessData>;
type ProcessEdge=Edge<{points?:Point[];status:Status}>;

function ProcessCard({data}:NodeProps<ProcessNode>) {
  return <div className={'ifd-node ifd-'+data.status} data-status={data.status}>
    <div className="ifd-node-top"><span className={'ifd-kind ifd-kind-'+data.record.kind}>{data.record.kind}</span><span className="ifd-node-status">{data.status==='running'?'◉':data.status==='completed'?'✓':data.status==='failed'?'!':'○'} {data.status}</span></div>
    <strong title={data.record.label}>{data.record.label}</strong>
    <small>{data.record.source.replace('forge/','')}:{data.record.line}</small>
    <Handle type="target" position={Position.Top}/><Handle type="source" position={Position.Bottom}/>
  </div>;
}
function TraceEdge(props:EdgeProps<ProcessEdge>) {
  const points=props.data?.points;
  const fallback=getSmoothStepPath(props)[0];
  const path=points?.length?'M '+points.map(point=>`${point.x},${point.y}`).join(' L '):fallback;
  return <BaseEdge id={props.id} path={path} markerEnd={props.markerEnd} className={'ifd-edge ifd-edge-'+(props.data?.status||'idle')}/>;
}
const nodeTypes:NodeTypes={process:ProcessCard};const edgeTypes:EdgeTypes={trace:TraceEdge};

function Dashboard() {
  const [scenario,setScenario]=useState('project-build');
  const [category,setCategory]=useState('All processes');
  const [query,setQuery]=useState('');const [fullMap,setFullMap]=useState(false);
  const [selected,setSelected]=useState<ProcessRecord|null>(null);
  const [statuses,setStatuses]=useState<Record<string,Status>>({});
  const [events,setEvents]=useState<Activity[]>([]);const [phase,setPhase]=useState<'idle'|'running'|'paused'|'done'>('idle');
  const [layout,setLayout]=useState<Layout|null>(null);const [error,setError]=useState('');
  const [speed,setSpeed]=useState(600);const [follow,setFollow]=useState(true);
  const [followTarget,setFollowTarget]=useState<Activity|null>(null);
  const [mode,setMode]=useState<'simulation'|'observed'>('simulation');
  const [projects,setProjects]=useState<{id:string;title:string;status:string}[]>([]);
  const [project,setProject]=useState('');const [observedState,setObservedState]=useState('Not connected');
  const [detailOpen,setDetailOpen]=useState(false);
  const engine=useMemo(()=>new FlowEngine(graph),[]);
  const observer=useMemo(()=>new ReadOnlyObserver(engine,graph),[engine]);
  const searchRef=useRef<HTMLInputElement>(null);
  const selectedRef=useRef(selected);selectedRef.current=selected;
  const followRef=useRef(follow);followRef.current=follow;
  const targetRef=useRef(followTarget);targetRef.current=followTarget;
  const {fitView,setCenter}=useReactFlow<ProcessNode,ProcessEdge>();
  const selectedFlow=graph.flows.find(flow=>flow.id===scenario)||graph.flows[0];
  const tour=scenario==='all';
  const visibleIds=useMemo(()=>new Set(fullMap||tour||mode==='observed'?graph.nodes.map(node=>node.id):selectedFlow.path),[fullMap,tour,mode,selectedFlow]);
  const filteredNodes=useMemo(()=>graph.nodes.filter(node=>visibleIds.has(node.id)),[visibleIds]);
  const filteredEdges=useMemo(()=>graph.edges.filter(edge=>visibleIds.has(edge.source)&&visibleIds.has(edge.target)&&
    (fullMap||tour||mode==='observed'||selectedFlow.path.some((id,index)=>id===edge.source&&selectedFlow.path[index+1]===edge.target))),[visibleIds,fullMap,tour,mode,selectedFlow]);

  useEffect(()=>{
    const controller=new AbortController();let centerTimer:ReturnType<typeof setTimeout>|undefined;setLayout(null);setError('');
    void layoutGraph({...graph,nodes:filteredNodes,edges:filteredEdges},controller.signal).then(result=>{
      if(!controller.signal.aborted){setLayout(result);const first=result.positions[selectedRef.current?.id||selectedFlow.path[0]]||Object.values(result.positions)[0];if(first)centerTimer=setTimeout(()=>{if(followRef.current&&targetRef.current&&result.positions[targetRef.current.nodeId])return;void setCenter(first.x+WIDTH/2,first.y+HEIGHT/2,{zoom:0.9,duration:0});},50);}
    }).catch(reason=>{if(!controller.signal.aborted)setError('Layout unavailable: '+String(reason));});
    return ()=>{controller.abort();clearTimeout(centerTimer);};
  },[filteredNodes,filteredEdges,selectedFlow,setCenter]);

  useEffect(()=>{
    const unsubscribe=engine.subscribe(event=>{
      setStatuses(current=>{
        const next={...current};
        if(event.status==='running')for(const [id,status] of Object.entries(next))if(status==='running')next[id]='idle';
        next[event.nodeId]=event.status;return next;
      });
      setEvents(current=>[event,...current].slice(0,60));
      if(event.status==='running'||event.mode==='observed'&&event.status!=='idle')setFollowTarget(event);
    });
    const timer=setInterval(()=>{const progress=engine.progress();setPhase(current=>current==='running'&&!progress.running?'done':current);},120);
    return ()=>{unsubscribe();clearInterval(timer);engine.dispose();observer.stop();};
  },[engine,observer,setCenter]);

  useEffect(()=>{
    const at=followTarget?layout?.positions[followTarget.nodeId]:undefined;
    if(follow&&at)void setCenter(at.x+WIDTH/2,at.y+HEIGHT/2,{zoom:0.96,duration:matchMedia('(prefers-reduced-motion: reduce)').matches?0:260});
  },[follow,followTarget,layout,setCenter]);

  useEffect(()=>{
    engine.stop();observer.stop();setPhase('idle');setStatuses({});setEvents([]);setFollowTarget(null);setError('');
    setProject('');setObservedState('Not connected');
    let cancelled=false;
    if(mode==='observed')void observer.projects().then(items=>{if(!cancelled)setProjects(items);}).catch(reason=>{if(!cancelled)setError(String(reason));});
    return ()=>{cancelled=true;observer.stop();};
  },[mode,engine,observer]);

  useEffect(()=>{
    const shortcut=(event:KeyboardEvent)=>{if(event.key==='/'&&!event.ctrlKey&&!event.altKey&&!event.metaKey&&!(event.target instanceof HTMLInputElement)&&!(event.target instanceof HTMLTextAreaElement)&&!(event.target instanceof HTMLSelectElement)){event.preventDefault();searchRef.current?.focus();}};
    document.addEventListener('keydown',shortcut);return ()=>document.removeEventListener('keydown',shortcut);
  },[]);

  const nodes:ProcessNode[]=filteredNodes.map(record=>({id:record.id,type:'process',position:layout?.positions[record.id]||{x:0,y:0},
    width:WIDTH,height:HEIGHT,style:{width:WIDTH,height:HEIGHT},data:{record,status:statuses[record.id]||'idle'},
    selected:selected?.id===record.id,ariaLabel:record.label+' · '+(statuses[record.id]||'idle')}));
  const edges:ProcessEdge[]=filteredEdges.map(edge=>({...edge,type:'trace',markerEnd:{type:MarkerType.ArrowClosed,width:18,height:18,color:'#6f9ab1'},data:{points:layout?.routes[edge.id],status:
    statuses[edge.source]==='running'||statuses[edge.target]==='running'?'running':
      statuses[edge.source]==='failed'||statuses[edge.target]==='failed'?'failed':
        statuses[edge.source]==='completed'&&statuses[edge.target]==='completed'?'completed':'idle'}}));
  const matching=graph.nodes.filter(node=>(category==='All processes'||node.category===category)&&(!query||[node.label,node.source,node.category].join(' ').toLowerCase().includes(query.toLowerCase())));
  const running=Object.values(statuses).filter(status=>status==='running').length;
  const completed=Object.values(statuses).filter(status=>status==='completed').length;
  const failures=Object.values(statuses).filter(status=>status==='failed').length;
  const focus=useCallback((record:ProcessRecord)=>{
    setSelected(record);setDetailOpen(true);
    const point=layout?.positions[record.id];
    if(point)void setCenter(point.x+WIDTH/2,point.y+HEIGHT/2,{zoom:1,duration:matchMedia('(prefers-reduced-motion: reduce)').matches?0:250});
    else {setFullMap(true);}
  },[layout,setCenter]);
  function play() {
    setError('');setStatuses({});setEvents([]);setFollowTarget(null);setPhase('running');
    engine.play(tour?graph.flows:[selectedFlow],speed);
  }
  function stop() {engine.stop();observer.stop();setFollowTarget(null);setPhase('idle');setProject('');setObservedState('Stopped · choose a project to reconnect');setStatuses(current=>Object.fromEntries(Object.entries(current).map(([id,status])=>[id,status==='running'?'idle':status])));}
  const last=events[0];const currentNode=graph.nodes.find(node=>node.id===last?.nodeId);

  return <div className="ifd-shell" data-mode={mode} data-layout={layout?'ready':'loading'}>
    <header className="ifd-header">
      <a href="/" className="ifd-brand"><img src="/icon.png" alt="Blue flame goat mascot"/><span>idea foundry<small>EXECUTION OBSERVATORY</small></span></a>
      <nav aria-label="Dashboard navigation"><a href="/">Workbench <span>↗</span></a><span aria-current="page">Dashboard</span></nav>
      <div className="ifd-private"><span/>Local & independent <b>01 / FLOW STUDIO</b></div>
    </header>
    <section className="ifd-command">
      <div><div className="ifd-eyebrow">FROM INTENT TO EVIDENCE</div><h1>See the work <em>taking shape.</em></h1><p>A source-mapped view of Foundry’s execution. Every glow has a named step.</p></div>
      <div className="ifd-mode" role="group" aria-label="Evidence source"><button aria-pressed={mode==='simulation'} onClick={()=>setMode('simulation')}>◇ Simulation</button><button aria-pressed={mode==='observed'} onClick={()=>setMode('observed')}>◉ Observe workspace</button></div>
    </section>
    <section className="ifd-evidence" aria-label="Evidence boundary">
      <span className={'ifd-source '+(mode==='observed'?'ifd-source-live':'')}>{mode==='simulation'?'SIMULATION · NO JOBS RUN':'OBSERVED · READ-ONLY POLLING'}</span>
      <p>{mode==='simulation'?'Playback follows named source paths. It sends no API mutations and proves no generated app works.':'Existing controller history + current project snapshots. Old history is not replayed; unrecorded internal calls remain unknown.'}</p>
      <a href="/dashboard/map" target="_blank" rel="noopener">Read execution map ↗</a>
    </section>
    <main className="ifd-workspace">
      <aside className="ifd-library">
        <div className="ifd-section-heading"><span>PROCESS LIBRARY</span><b>{graph.nodes.length}</b></div>
        <label className="ifd-search"><span>⌕</span><input ref={searchRef} aria-label="Find a process" placeholder="Find a process or endpoint…" value={query} onChange={event=>setQuery(event.target.value)}/><kbd>/</kbd></label>
        <label className="ifd-filter-label" htmlFor="ifd-category">Functional area</label><select id="ifd-category" value={category} onChange={event=>setCategory(event.target.value)}>{categories.map(name=><option key={name}>{name}</option>)}</select>
        <div className="ifd-library-list" aria-label="Source process list">{matching.slice(0,250).map(node=><button key={node.id} className={selected?.id===node.id?'ifd-library-selected':''} onClick={()=>focus(node)}><i className={'ifd-dot ifd-dot-'+(statuses[node.id]||'idle')}/><span>{node.label}<small>{node.kind} · {node.source.replace('forge/','')}</small></span></button>)}</div>
        <div className="ifd-baseline"><strong>Mapped, not imagined.</strong><p>{graph.edges.length} directed transitions · {graph.flows.length} dry-run scenarios.<br/>Baseline {graph.baseline}.</p></div>
      </aside>
      <section className="ifd-stage" aria-label="Interactive execution graph">
        <div className="ifd-toolbar">
          {mode==='simulation'?<><label htmlFor="ifd-scenario" className="ifd-sr">Execution scenario</label><select id="ifd-scenario" value={scenario} disabled={phase==='running'||phase==='paused'} onChange={event=>{stop();setScenario(event.target.value);setStatuses({});setEvents([]);}}>
            <optgroup label="Core journeys">{['project-plan','guided-plan','project-build','project-verify','manual-review','repair-loop','failed-job','stop-job'].map(id=>graph.flows.find(flow=>flow.id===id)).filter(flow=>!!flow).map(flow=><option key={flow.id} value={flow.id}>{flow.label}</option>)}</optgroup>
            <option value="all">All workflows · complete source tour</option>
            <optgroup label="Individual routes and branches">{graph.flows.filter(flow=>!['project-plan','guided-plan','project-build','project-verify','manual-review','repair-loop','failed-job','stop-job'].includes(flow.id)).map(flow=><option key={flow.id} value={flow.id}>{flow.label}</option>)}</optgroup>
          </select><button className="ifd-play" onClick={play} disabled={!layout||phase==='running'||phase==='paused'}>▶ Play simulation</button>
          <button className="ifd-icon-button" aria-label={phase==='paused'?'Resume simulation':'Pause simulation'} disabled={!['running','paused'].includes(phase)} onClick={()=>{if(phase==='paused'){engine.resume();setPhase('running');}else{engine.pause();setPhase('paused');}}}>{phase==='paused'?'▶':'Ⅱ'}</button></>
            :<><label htmlFor="ifd-project" className="ifd-sr">Project to observe</label><select id="ifd-project" value={project} onChange={event=>{setProject(event.target.value);setObservedState(event.target.value?'Connecting…':'Not connected');setStatuses({});setEvents([]);setFollowTarget(null);if(event.target.value)observer.watch(event.target.value,setObservedState,setError);else observer.stop();}}><option value="">Choose a saved project…</option>{projects.map(item=><option key={item.id} value={item.id}>{item.title}</option>)}</select><span className="ifd-observed-status" title={observedState}>{observedState}</span></>}
          <button className="ifd-stop" onClick={stop}>■ Stop</button>
          <button className="ifd-icon-button" aria-label="Fit graph to view" onClick={()=>void fitView({padding:0.15,duration:0})}>⌖</button>
        </div>
        <div className="ifd-view-options"><label><input type="checkbox" checked={follow} onChange={event=>setFollow(event.target.checked)}/>Follow activity</label><label><input type="checkbox" checked={fullMap} disabled={phase==='running'||phase==='paused'} onChange={event=>setFullMap(event.target.checked)}/>Full map</label><label>Tempo <select aria-label="Playback tempo" value={speed} disabled={phase==='running'||phase==='paused'} onChange={event=>setSpeed(Number(event.target.value))}><option value="1200">Unhurried</option><option value="600">Normal</option><option value="80">Fast</option></select></label><span>{filteredNodes.length} nodes in view</span></div>
        <div className="ifd-canvas">
          {!layout&&!error&&<div className="ifd-layout-loading" role="status">Arranging the source map with ELK…</div>}
          {layout&&<ReactFlow<ProcessNode,ProcessEdge> nodes={nodes} edges={edges} nodeTypes={nodeTypes} edgeTypes={edgeTypes}
            onNodeClick={(_,node)=>focus(node.data.record)} nodesDraggable={false} nodesConnectable={false} minZoom={0.035} maxZoom={1.8}
            onlyRenderVisibleElements={false} colorMode="dark" proOptions={{hideAttribution:false}}>
            <Background variant={BackgroundVariant.Dots} gap={24} size={1} color="#263648"/><Controls showInteractive={false}/>
            <MiniMap pannable zoomable nodeColor={node=>node.data.status==='running'?'#61dcf5':node.data.status==='failed'?'#ff7986':node.data.status==='completed'?'#65d9a0':'#30445a'} maskColor="#080d14b8"/>
          </ReactFlow>}
          <div className="ifd-legend" aria-label="Status legend"><span><i className="ifd-dot ifd-dot-idle"/>Idle</span><span><i className="ifd-dot ifd-dot-running"/>Running</span><span><i className="ifd-dot ifd-dot-completed"/>Step completed</span><span><i className="ifd-dot ifd-dot-failed"/>Failed</span><small>Green is step progress, not project verification.</small></div>
          <div className="ifd-map-stamp">ELK LAYERED / TOP → BOTTOM <span>HTML + SVG · {mode==='simulation'?'DRY RUN':'OBSERVED'}</span></div>
        </div>
        <div className="ifd-timeline">
          <div className="ifd-timeline-heading"><span>ACTIVITY JOURNAL <b>{mode==='simulation'?'SIMULATED':'OBSERVED'}</b></span><strong aria-live="polite">{phase==='paused'?'Paused':currentNode?currentNode.label:'Ready when you are.'}</strong></div>
          <div className="ifd-events" aria-label="Recent activity">{events.length?events.slice(0,16).map(event=><button key={event.sequence} title={event.flow} onClick={()=>{const node=graph.nodes.find(node=>node.id===event.nodeId);if(node)focus(node);}}><i className={'ifd-dot ifd-dot-'+event.status}/><time>{new Date(event.at).toLocaleTimeString()}</time><span>{graph.nodes.find(node=>node.id===event.nodeId)?.label}</span><small>{event.status} · {event.mode}</small></button>):<p>Choose a journey and press Play. The journal will keep the last 60 emitted events in memory.</p>}</div>
        </div>
      </section>
      <aside className={'ifd-inspector '+(detailOpen?'ifd-inspector-open':'')}>
        <div className="ifd-section-heading"><span>STEP INSPECTOR</span><button aria-label="Close step inspector" onClick={()=>setDetailOpen(false)}>×</button></div>
        {selected?<><span className={'ifd-kind ifd-kind-'+selected.kind}>{selected.kind}</span><h2>{selected.label}</h2><p>{selected.description||'A named call, state or lifecycle point extracted from the application source. Intermediate calls can be elided in journey segments.'}</p><div className="ifd-source-card"><small>SOURCE REFERENCE</small><strong>{selected.source}:{selected.line}</strong><pre>{selected.excerpt}</pre></div><dl><dt>Area</dt><dd>{selected.category}</dd><dt>Status</dt><dd>{statuses[selected.id]||'idle'}</dd><dt>Evidence source</dt><dd>{mode==='simulation'?'Timer-driven scenario':'Read-only controller records'}</dd></dl></>:<div className="ifd-empty-inspector"><span>◎</span><h2>Every step has a source.</h2><p>Select a node or search the library to see its real function, endpoint, state and source location.</p></div>}
        <div className="ifd-inspector-note"><b>Understand the boundary</b><p>Simulation never executes a project. Observation does not instrument every call. Missing transitions stay unknown.</p></div>
      </aside>
    </main>
    {error&&<div className="ifd-error" role="alert"><strong>Dashboard needs attention</strong><span>{error}</span><button onClick={()=>setError('')}>Dismiss</button></div>}
    <footer className="ifd-footer"><span><i className="ifd-dot ifd-dot-running"/>{running} active <i className="ifd-dot ifd-dot-completed"/>{completed} completed <i className="ifd-dot ifd-dot-failed"/>{failures} failed</span><span>Dashboard 1.0 · isolated module · no project mutations</span><span>{phase==='done'?'Scenario complete':phase==='paused'?'Simulation paused':mode==='simulation'?'SOURCE-DRIVEN SIMULATION':'READ-ONLY OBSERVATION'}</span></footer>
  </div>;
}

function App(){return <ReactFlowProvider><Dashboard/></ReactFlowProvider>;}
const target=document.getElementById('ifd-root');if(target)createRoot(target).render(<StrictMode><App/></StrictMode>);
