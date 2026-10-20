"use strict";
let workflowRequest = 0;
let workflowPending = null;
let workflowSignature = "";
async function refreshWorkflow(id) {
  if (workflowPending?.id === id) return;
  workflowPending?.controller.abort();
  const controller = new AbortController();
  workflowPending = {id,controller};
  const sequence = ++workflowRequest;
  try {
    const response = await fetch("/api/projects/"+id+"/workflow",{headers:{"X-Foundry-Token":token},signal:controller.signal});
    if (!response.ok) throw new Error("Could not load workflow facts (HTTP "+response.status+").");
    const data = await response.json();
    if (sequence !== workflowRequest || current?.id !== id) return;
    const signature = id + current.status + JSON.stringify(data);
    if (signature === workflowSignature) return;
    workflowSignature = signature;
    $("workflow-summary").textContent = data.next_step;
    const board=data.task_board;
    if (data.model_budget) $("orchestration-progress").textContent="Latest run: "+(data.model_budget.used ?? "unknown")+" / "+(data.model_budget.limit ?? "allowance not recorded")+" model invocations. "+data.next_step+". Source saves and related checks are not completion proof.";
    if (board) {
      $("task-board-summary").textContent="Context: "+(board.context_policy==="focused_v1"?"approved focused packets with bounded source reads":"full source")+". "+board.meaning;
      $("resume-warning").textContent=board.resume_problem || (board.candidate_waiting?"A saved task candidate is ready for inspection on resume.":"");
      $("adopt-resume").hidden=!board.adopt_allowed;
      $("adopt-resume").disabled=activeStatuses.has(current.status);
      $("task-board-list").replaceChildren();
      for (const task of board.tasks) {
        const li=document.createElement("li"),title=document.createElement("strong"),detail=document.createElement("small");
        title.textContent=task.title+" — "+task.state;
        detail.textContent=(task.files.length?"Files: "+task.files.join(", ")+". ":"")+(task.blocked_by.length?"Needs saved tasks "+task.blocked_by.join(", ")+". ":"")+(task.milestone_current?"Current approved HTTP prefix passed. ":task.milestone_evidence?"Historical milestone evidence; current checks may be pending. ":"");
        if (task.finish_gate?.passed) detail.textContent+=" Finish gate: approval, scope and saved source checked; behavior evidence remains separate.";
        const outcome=document.createElement("p");outcome.textContent="Outcome: "+task.outcome;
        const label=document.createElement("small");label.textContent="Declared completion criteria · not individually verified";
        const criteria=document.createElement("ul");criteria.className="task-criteria";
        for (const criterion of task.criteria) {const item=document.createElement("li");item.textContent=criterion;criteria.append(item);}
        const checks=document.createElement("small");checks.textContent="Related approved checks (feature overlap): "+(task.related_checks.map(c=>(c.kind==="checks"?"HTTP":c.kind==="browser_checks"?"Browser":"Manual")+" #"+c.number+" "+c.name).join("; ")||"none mapped");
        li.append(title,outcome,detail,label,criteria,checks);$("task-board-list").append(li);
      }
    }
    $("workflow-categories").replaceChildren();
    for (const category of data.categories) {
      const card=document.createElement("article"); card.className="workflow-card";
      const title=document.createElement("h4");title.textContent=category.name;
      const state=document.createElement("strong");state.textContent=category.state;
      const detail=document.createElement("p");detail.textContent=category.detail;
      const action=document.createElement("button");action.className="quiet";action.textContent="Open";
      action.setAttribute("aria-label","Open "+category.name);
      action.onclick=()=>category.action==="models" ? $("connections-button").click() : tab(category.action);
      card.append(title,state,detail,action);$("workflow-categories").append(card);
    }
    $("workflow-coverage").replaceChildren();
    for (const row of data.coverage) {
      const item=document.createElement("li");
      item.textContent=row.feature+" — tasks "+(row.tasks.join(", ")||"missing")+"; HTTP "+row.checks.length+", browser "+row.browser_checks.length+", manual "+row.manual_checks.length+" declared checks";
      $("workflow-coverage").append(item);
    }
    $("workflow-warnings").textContent=data.ownership_warnings.map(w=>"Task "+w.task+": "+w.files.join(", ")+". "+w.message).join("\n") || "No protected file references found in task text.";
    $("workflow-receipts").replaceChildren();
    for (const receipt of data.task_receipts) {
      const item=document.createElement("li");item.textContent="Task "+receipt.task+": "+(receipt.disposition === "existing_source_supported" ? "existing source cited; verification pending" : (receipt.changed_files.join(", ")||"no source changes"))+". Behavioral verification is separate.";
      $("workflow-receipts").append(item);
    }
  } catch (error) {
    if (error.name === "AbortError") return;
    workflowSignature = "";
    if (sequence===workflowRequest && current?.id===id) $("workflow-summary").textContent="Workflow facts unavailable: "+error.message;
  } finally {
    if (workflowPending?.controller === controller) workflowPending = null;
  }
}

window.addEventListener("DOMContentLoaded",()=>{
  $("adopt-resume").onclick=handle(async()=>{
    if (!current || activeStatuses.has(current.status)) return;
    await api("/api/projects/"+current.id+"/resume-baseline",{confirm:true});
    workflowSignature="";
    await openProject(current.id);
  });
});
