"use strict";
let statusPolling = false;
let lastStatusSignature = "";
let streamProject = null;
const brandEmblem = $("brand-emblem");
const brandMotion = $("brand-motion");
let flameMotion = true;
try { flameMotion = localStorage.getItem("foundry-flame-motion") !== "off"; } catch (_) { /* Storage is optional. */ }
function renderFlameMotion() {
  brandEmblem.dataset.motion = String(flameMotion);
  brandEmblem.dataset.hidden = String(document.hidden);
  brandMotion.setAttribute("aria-pressed", String(flameMotion));
  brandMotion.textContent = "Flame motion: " + (flameMotion ? "on" : "off");
}
brandMotion.onclick = () => {
  flameMotion = !flameMotion;
  try { localStorage.setItem("foundry-flame-motion", flameMotion ? "on" : "off"); } catch (_) { /* Keep the control usable without storage. */ }
  renderFlameMotion();
};
document.addEventListener("visibilitychange", renderFlameMotion);
renderFlameMotion();
async function refreshModelStatus() {
  if (statusPolling || document.hidden) return;
  statusPolling = true;
  try {
    const snapshot = await api("/api/model-status");
    brandEmblem.dataset.working = String(snapshot.items.some(item => item.state === "working"));
    const stream=snapshot.stream;
    streamProject=stream?.project || null;
    $("live-local").hidden=!stream;
    if (stream) {
      $("live-local-label").textContent=`${stream.provider === "ollama" ? "Ollama" : "Local server"} · ${stream.model} · ${stream.characters} characters received · unvalidated`;
      $("live-local-preview").textContent=stream.preview;
      $("live-local-stop").disabled=!current || stream.project!==current.id || !activeStatuses.has(current.status);
    } else {$("live-local-preview").textContent="";}
    const signature = JSON.stringify(snapshot.items);
    if (signature === lastStatusSignature) return;
    lastStatusSignature = signature;
    const icons = $("model-status-icons");
    const marks = {gemini:"G",groq:"Gq",cloudflare:"Cf",openrouter:"Or",nvidia:"Nv",requesty:"Rq",huggingface:"Hf"};
    icons.replaceChildren();
    let localNumber = 0;
    for (const item of snapshot.items) {
      const badge = document.createElement("button");
      badge.className = "model-state";
      badge.dataset.state = item.state;
      badge.dataset.modelId = item.id;
      const text = item.label + ": " + item.state.replaceAll("_", " ") + (item.model && item.model !== item.label ? " · " + item.model : "") + (item.observed_at ? " · observed " + new Date(item.observed_at * 1000).toLocaleTimeString() : "");
      badge.title = text;
      badge.setAttribute("aria-label",text);
      badge.textContent = marks[item.id] || ((item.state === "embedding" ? "E" : "L") + (++localNumber));
      badge.onclick = () => { $("connections-button").click(); };
      icons.append(badge);
    }
    $("model-status-panel").title = snapshot.note;
  } catch (_) {
    brandEmblem.dataset.working = "false";
    streamProject=null;
    $("live-local").hidden=true;
    $("live-local-preview").textContent="";
    lastStatusSignature = "";
    for (const badge of document.querySelectorAll(".model-state")) {
      badge.dataset.state = "unknown";
      badge.setAttribute("aria-label", "Status unavailable; refresh pending");
      badge.title = "Status unavailable; refresh pending";
    }
  } finally { statusPolling = false; }
}
refreshModelStatus();
setInterval(refreshModelStatus, 1000);
$("live-local-stop").onclick=()=>{
  if (streamProject && current?.id===streamProject) $("stop").click();
  else notice("Open the project with the streaming request before stopping it.");
};


