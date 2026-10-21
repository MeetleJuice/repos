"use strict";
let cloudProviderOrder = [
  "gemini",
  "groq",
  "cloudflare",
  "openrouter",
  "nvidia",
  "requesty",
  "huggingface",
];
function cloudHandle(fn) {
  return handle(async (...args) => {
    $("cloud-feedback").textContent = "Working…";
    try {
      await fn(...args);
    } catch (error) {
      $("cloud-feedback").textContent = error.message;
      throw error;
    }
  });
}
function renderCloudSetup(info) {
  const limitList=$("model-limit-list");limitList.replaceChildren();
  for (const row of info.model_limits || []) {
    const item=document.createElement('p');
    const context=row.model_context_limit==null?'unknown model context':`${row.model_context_limit.toLocaleString()} model context tokens`;
    const output=row.model_output_limit==null?'unknown model output ceiling':`${row.model_output_limit.toLocaleString()} model output ceiling`;
    item.textContent=`${row.provider}/${row.model} · ${row.profile_scope} · ${row.generation_eligible ? `${context}; ${output}. Configured output setting ${row.configured_output_tokens.toLocaleString()} (planner floor / builder cap); effective ceiling ${row.effective_output_ceiling.toLocaleString()}, context ${row.effective_context.toLocaleString()}.` : 'Embedding model; not an app builder.'} ${row.estimated ? 'Includes estimates.' : 'Published limits.'}`;
    item.title=row.source;limitList.append(item);
  }
  if (!limitList.childNodes.length) limitList.textContent='Check connections and cloud catalogues to list model limits. No generation is performed.';
  const credentials = info.credentials || {};
  const calibrationSelect=$("calibration-model"),previousModel=calibrationSelect.value;
  calibrationSelect.replaceChildren();
  for (const model of info.providers?.ollama?.models || []) if (!model.toLowerCase().includes("embed")) calibrationSelect.add(new Option(model,model));
  if ([...calibrationSelect.options].some(o=>o.value===previousModel)) calibrationSelect.value=previousModel;
  $("calibrate-local").disabled=!calibrationSelect.options.length;
  const measurement=info.local_calibration;
  if (measurement?.cases) $("calibration-feedback").textContent=measurement.model+": "+measurement.cases.map(c=>c.name+" "+(c.passed?"passed":"failed")+" ("+c.seconds+"s)").join("; ")+". Fixed 4K cases only; project capacity and GPU fit remain unproven.";

  if (info.routing_mode) $("routing-mode").value=info.routing_mode === "manual" ? "hybrid" : info.routing_mode;
  const present = Object.values(credentials.keys || {}).filter(Boolean).length;
  $("cloud-env-status").textContent =
    `${present}/${Object.keys(credentials.keys || {}).length || 7} API keys detected. Preferred private file: ${credentials.path || "not available"}.` +
    ` Loaded files: ${(credentials.loaded_files || []).join("; ") || "none (process environment or no keys)"}.` +
    (credentials.txt_warning
      ? " A .env.txt file was found; use the file picker to import it."
      : "") +
    " " +
    (credentials.warnings || []).join(" ");
  $("cloud-providers").replaceChildren();
  const local = $("cloud-local-model");
  local.replaceChildren(new Option("Disabled — cloud providers only", ""));
  for (const name of info.providers?.ollama?.models || []) {
    if (!name.toLowerCase().includes("embed"))
      local.append(new Option(name, name));
  }
  local.value = info.cloud_local_model || "";
  local.disabled = !info.providers?.ollama?.connected;
  let available = 0;
  cloudProviderOrder = info.cloud_order || cloudProviderOrder;
  for (const provider of cloudProviderOrder) {
    const status = info.cloud?.[provider];
    const card = document.createElement("div");
    card.className = "connection-item cloud-provider-card";
    card.dataset.provider = provider;
    const title = document.createElement("strong");
    title.textContent = provider;
    const detail = document.createElement("p");
    detail.textContent = status
      ? status.status +
        ": " +
        (status.detail || "Add the key, then check again.")
      : "Not checked yet.";
    const select = document.createElement("select");
    select.id = "cloud-model-" + provider;
    select.setAttribute("aria-label", provider + " model");
    const empty = document.createElement("option");
    empty.value = "";
    empty.textContent = "Skip this provider";
    select.append(empty);
    for (const id of status?.models || []) {
      const option = document.createElement("option");
      option.value = id;
      option.textContent = id;
      select.append(option);
    }
    select.value = status?.selected || "";
    select.disabled = status?.status !== "catalogue_available";
    if (!select.disabled) available++;
    const limitLabel = document.createElement("label");
    limitLabel.textContent = "Builder output cap / planner output floor";
    const limit = document.createElement("select");
    limit.id = "cloud-limit-" + provider;
    for (const n of [1024, 2048, 4096, 8192, 16384]) {
      const option = document.createElement("option");
      option.value = n;
      option.textContent = n;
      limit.append(option);
    }
    limit.value =
      info.cloud_limits?.[provider] || (provider === "groq" ? 4096 : 8192);
    limitLabel.append(limit);
    const timeoutLabel = document.createElement("label");
    timeoutLabel.textContent = "Socket timeout before failover";
    const timeout = document.createElement("select");
    timeout.id = "cloud-timeout-" + provider;
    for (const n of [15, 30, 60, 120])
      timeout.append(new Option(n + " seconds", n));
    timeout.value = info.cloud_timeouts?.[provider] || 60;
    timeoutLabel.append(timeout);
    const formatLabel = document.createElement("label");
    formatLabel.className = "check-line";
    const format = document.createElement("input");
    format.type = "checkbox";
    format.id = "cloud-json-" + provider;
    format.checked = info.cloud_structured?.[provider] !== false;
    formatLabel.append(
      format,
      document.createTextNode(
        "Request native JSON output (model support varies)",
      ),
    );
    const orderButtons = document.createElement("div");
    orderButtons.className = "cloud-order-buttons";
    const earlier = document.createElement("button");
    earlier.className = "secondary";
    earlier.textContent = "↑ Earlier";
    earlier.setAttribute("aria-label", "Move " + provider + " earlier");
    earlier.onclick = () => {
      if (card.previousElementSibling)
        card.parentNode.insertBefore(card, card.previousElementSibling);
    };
    const later = document.createElement("button");
    later.className = "secondary";
    later.textContent = "↓ Later";
    later.setAttribute("aria-label", "Move " + provider + " later");
    later.onclick = () => {
      if (card.nextElementSibling)
        card.parentNode.insertBefore(card.nextElementSibling, card);
    };
    orderButtons.append(earlier, later);
    card.append(
      title,
      orderButtons,
      detail,
      select,
      limitLabel,
      timeoutLabel,
      formatLabel,
    );
    $("cloud-providers").append(card);
  }
  $("cloud-new").disabled = !available;
  $("cloud-project").disabled =
    !available || !current || activeStatuses.has(current.status);
}
$("cloud-env-file").onchange = cloudHandle(async () => {
  const file = $("cloud-env-file").files[0];
  if (!file) return;
  try {
    if (file.size > 32768)
      throw new Error("Choose a plain-text .env file smaller than 32 KB.");
    const bytes = new Uint8Array(await file.arrayBuffer());
    const encoding =
      bytes[0] === 255 && bytes[1] === 254
        ? "utf-16le"
        : bytes[0] === 254 && bytes[1] === 255
          ? "utf-16be"
          : "utf-8";
    await api("/api/cloud/import", {
      text: new TextDecoder(encoding, { fatal: true }).decode(bytes),
    });
    $("cloud-feedback").textContent =
      "Key file copied locally. Click Check cloud providers next. No inference request was made.";
    await connections();
  } finally {
    $("cloud-env-file").value = "";
  }
});
$("cloud-reload").onclick = cloudHandle(async () => {
  await api("/api/cloud/reload", {});
  await connections();
  $("cloud-feedback").textContent =
    "Reloaded local keys. Check cloud providers again to refresh availability.";
});
$("cloud-check").onclick = cloudHandle(async () => {
  $("cloud-check").disabled = true;
  $("cloud-feedback").textContent =
    "Checking configured providers and available model IDs…";
  try {
    await api("/api/cloud/check", {});
    await connections();
    $("cloud-feedback").textContent =
      "Checks complete. Select models and apply the route. Generation still requires cloud consent.";
  } finally {
    $("cloud-check").disabled = false;
  }
});
async function applyCloud(project) {
  const ident = current?.id;
  const models = Object.fromEntries(
    cloudProviderOrder.map((p) => [p, $("cloud-model-" + p).value]),
  );
  const limits = Object.fromEntries(
    cloudProviderOrder.map((p) => [p, Number($("cloud-limit-" + p).value)]),
  );
  const profile = await api("/api/cloud/select", {
    models,
    limits,
    local_model: $("cloud-local-model").value,
    order: [...document.querySelectorAll(".cloud-provider-card")].map(
      (card) => card.dataset.provider,
    ),
    timeouts: Object.fromEntries(
      cloudProviderOrder.map((p) => [p, Number($("cloud-timeout-" + p).value)]),
    ),
    structured: Object.fromEntries(
      cloudProviderOrder.map((p) => [p, $("cloud-json-" + p).checked]),
    ),
  });
  await applyCloudProfile(profile, project, ident);
}
async function applyCloudProfile(profile, project, ident = current?.id) {
  if (project) {
    if (!ident || current?.id !== ident)
      throw new Error("Open the intended project and apply again.");
    current = await api(`/api/projects/${ident}/models`, profile);
    $("project-cloud-consent").checked = false;
    $("change-cloud-consent").checked = false;
    render();
  } else {
    for (const role of ["planner", "coder"]) {
      $(role + "-provider").value = profile[role].provider;
      $(role + "-model").value = profile[role].model;
      fillModelSettings(role, "", profile[role]);
    }
    localStorage.setItem("foundry-models", JSON.stringify(profile));
    updateCloud();
    $("create-cloud").checked = false;
  }
  $("cloud-feedback").textContent =
    `Route applied: ${routeLabel(profile.coder)}. No generation started. Cloud use requires separate consent.`;
  if (typeof refreshStudio === "function") refreshStudio();
}
$("cloud-new").onclick = cloudHandle(() => applyCloud(false));
$("cloud-project").onclick = cloudHandle(() => applyCloud(true));
$("compatible-apply").onclick=cloudHandle(async()=>{
  const ident=current?.id;
  $("compatible-apply").disabled=true;
  try {
    const profile=await api('/api/local/setup',{planner:$("compatible-planner").value,coder:$("compatible-coder").value});
    await applyCloudProfile(profile,false);
    if (ident && current?.id===ident && !activeStatuses.has(current.status)) await applyCloudProfile(profile,true,ident);
    await connections();
    $("cloud-feedback").textContent="Local server route applied. No cloud fallback or generation. Check the server's loaded context before building.";
  } finally {$("compatible-apply").disabled=false;}
});
window.addEventListener("DOMContentLoaded", () => {
  if (lastConnectionInfo) renderCloudSetup(lastConnectionInfo);
});

let studioSetupRunning = false;
async function setupAutomaticModels(mode) {
  if (studioSetupRunning) return;
  studioSetupRunning = true;
  const ident = current?.id;
  for (const id of ["cloud-auto", "preset-local", "preset-hybrid", "preset-orchestrated", "studio-local"]) $(id).disabled = true;
  try {
    $("cloud-feedback").textContent = mode === "local_only"
      ? "Finding installed Ollama models. No cloud catalogue or generation requests…"
      : "Discovering model IDs and preparing planner and builder routes. No generation requests…";
    const profile = await api("/api/cloud/automatic", {mode});
    await applyCloudProfile(profile, false);
    let applied = false;
    if (ident && current?.id === ident && !activeStatuses.has(current.status)) {
      await applyCloudProfile(profile, true, ident);
      applied = true;
    }
    await connections();
    const scope = applied ? " and this project" : "";
    $("cloud-feedback").textContent = "Automatic routes ready for new projects" + scope + ". " +
      (mode === "local_only" ? "Local only: no cloud fallback or cloud generation. Context limits still apply." : mode === "orchestrated" ? (cloudModel(profile.planner) ? "Cloud providers plan in order before local fallback. Coding is local only. Cloud planning requires consent; paid models may incur charges. A hanging request must time out first. Local ranking is a preference, not a benchmark." : "No eligible cloud planning routes were found; planning and coding are local only. Review provider status if you expected cloud planning. Local ranking is a preference, not a benchmark.") : "Cloud generation still requires consent; paid models may incur charges. Catalogue access does not prove quota.") +
      (ident && !applied ? " The open project was not changed; apply again while it is idle." : "");
    if (typeof refreshStudio === "function") refreshStudio();
  } finally {
    studioSetupRunning = false;
    for (const id of ["cloud-auto", "preset-local", "preset-hybrid", "preset-orchestrated", "studio-local"]) $(id).disabled = false;
  }
}
$("cloud-auto").onclick = cloudHandle(() => setupAutomaticModels($("routing-mode").value));

$("calibrate-local").onclick=cloudHandle(async()=>{
  $("calibrate-local").disabled=true;
  $("calibration-feedback").textContent="Running fixed local checks. No project source is sent; the model may need to load.";
  try {
    const report=await api("/api/local/calibrate",{model:$("calibration-model").value});
    $("calibration-feedback").textContent=report.model+": "+report.cases.map(c=>c.name+" "+(c.passed?"passed":"failed")+" ("+c.seconds+"s)").join("; ")+". These checks do not verify an app or GPU fit. Routes unchanged.";
  } catch(error) { $("calibration-feedback").textContent=error.message;throw error; }
  finally { $("calibrate-local").disabled=false; }
});
