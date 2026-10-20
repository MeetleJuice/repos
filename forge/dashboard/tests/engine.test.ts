import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {FlowEngine} from '../src/engine.ts';
import type {GraphRecord, Activity} from '../src/types.ts';
const graph: GraphRecord=JSON.parse(fs.readFileSync(new URL('../src/graph.json',import.meta.url),'utf8'));

test('source-derived scenarios cover every node and edge without invented jumps',()=>{
  const nodes=new Set<string>();const edges=new Set<string>();
  for(const flow of graph.flows)for(let i=0;i<flow.path.length;i++) {
    nodes.add(flow.path[i]);
    if(i){const edge=graph.edges.find(edge=>edge.source===flow.path[i-1] && edge.target===flow.path[i]);assert.ok(edge,flow.id);edges.add(edge.id);}
  }
  assert.deepEqual([...nodes].sort(),graph.nodes.map(node=>node.id).sort());
  assert.deepEqual([...edges].sort(),graph.edges.map(edge=>edge.id).sort());
  assert.equal(nodes.size,graph.nodes.length);assert.ok(graph.nodes.every(node=>node.source && node.line>0 && node.excerpt));
});

test('all simulation paths publish running and terminal states including failure',async()=>{
  const engine=new FlowEngine(graph);const events: Activity[]=[];const unsubscribe=engine.subscribe(event=>events.push(event));
  engine.play(graph.flows,10);
  const deadline=Date.now()+30000;
  while(engine.progress().running && Date.now()<deadline)await new Promise(resolve=>setTimeout(resolve,20));
  assert.equal(engine.progress().running,false);
  assert.equal(new Set(events.filter(event=>event.status==='running').map(event=>event.nodeId)).size,graph.nodes.length);
  assert.ok(events.some(event=>event.status==='failed'));
  assert.ok(events.every(event=>event.mode==='simulation'));
  unsubscribe();engine.dispose();
});

test('pause, resume and stop cannot leave old timers publishing',async()=>{
  const engine=new FlowEngine(graph);const events: Activity[]=[];engine.subscribe(event=>events.push(event));
  engine.play([graph.flows[0]],30);engine.pause();const paused=events.length;
  await new Promise(resolve=>setTimeout(resolve,70));assert.equal(events.length,paused);
  engine.resume();await new Promise(resolve=>setTimeout(resolve,15));engine.stop();const stopped=events.length;
  await new Promise(resolve=>setTimeout(resolve,80));assert.equal(events.length,stopped);
  assert.equal(engine.progress().running,false);engine.dispose();
});

test('pub/sub rejects unknown identifiers and labels external evidence',()=>{
  const engine=new FlowEngine(graph);const events: Activity[]=[];engine.subscribe(event=>events.push(event));
  assert.throws(()=>engine.publish('invented','completed','observed','invalid'));
  engine.publish(graph.nodes[0].id,'completed','observed','Recorded controller event');
  assert.equal(events[0].mode,'observed');engine.dispose();
});
