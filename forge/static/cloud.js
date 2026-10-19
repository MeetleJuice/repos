"use strict";
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
  const credentials = info.credentials || {};
  const present = Object.values(credentials.keys || {}).filter(Boolean).length;
  $("cloud-env-status").textContent =
    `${present}/3 API keys detected. Preferred private file: ${credentials.path || "not available"}.` +
    ` Loaded files: ${(credentials.loaded_files || []).join("; ") || "none (process environment or no keys)"}.` +
    (credentials.txt_warning
      ? " A .env.txt file was found; use the file picker to import it."
      : "") +
    " " +
    (credentials.warnings || []).join(" ");
  $("cloud-providers").replaceChildren();
  let available = 0;
  for (const provider of ["gemini", "groq", "openrouter"]) {
    const status = info.cloud?.[provider];
    const card = document.createElement("div");
    card.className = "connection-item";
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
    limitLabel.textContent = "Maximum output tokens";
    const limit = document.createElement("select");
    limit.id = "cloud-limit-" + provider;
    for (const n of [1024, 2048, 4096, 8192]) {
      const option = document.createElement("option");
      option.value = n;
      option.textContent = n;
      limit.append(option);
    }
    limit.value =
      info.cloud_limits?.[provider] || (provider === "groq" ? 4096 : 8192);
    limitLabel.append(limit);
    card.append(title, detail, select, limitLabel);
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
    ["gemini", "groq", "openrouter"].map((p) => [
      p,
      $("cloud-model-" + p).value,
    ]),
  );
  const limits = Object.fromEntries(
    ["gemini", "groq", "openrouter"].map((p) => [
      p,
      Number($("cloud-limit-" + p).value),
    ]),
  );
  const profile = await api("/api/cloud/select", { models, limits });
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
    `Cloud route applied: ${routeLabel(profile.coder)}. No generation started. Approve cloud use when starting the job.`;
}
$("cloud-new").onclick = cloudHandle(() => applyCloud(false));
$("cloud-project").onclick = cloudHandle(() => applyCloud(true));
window.addEventListener("DOMContentLoaded", () => {
  if (lastConnectionInfo) renderCloudSetup(lastConnectionInfo);
});
