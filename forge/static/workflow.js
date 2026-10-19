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
    const signature = id + JSON.stringify(data);
    if (signature === workflowSignature) return;
    workflowSignature = signature;
    $("workflow-summary").textContent = data.next_step;
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
