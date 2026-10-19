"use strict";
const $ = (id) => document.getElementById(id);
const token = document.querySelector('meta[name="foundry-token"]').content;
const activeStatuses = new Set([
  "planning",
  "building",
  "checking",
  "repairing",
  "queued",
]);
let runtimeStatus = null;
let lastConnectionInfo = null;
let connectionSequence = 0;
let current = null,
  lastPlan = "",
  fileCache = {},
  polling = false;
const defaults = {
  ollama: "qwen3.5:9b",
  groq: "",
  openrouter: "",
  gemini: "gemini-2.5-flash",
};

async function api(path, body) {
  const response = await fetch(path, {
    method: body === undefined ? "GET" : "POST",
    headers: { "X-Foundry-Token": token, "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    const result = await response.json();
    throw new Error(result.error || "Request failed.");
  }
  return response.json();
}
function notice(message) {
  $("notice").textContent = message;
  $("notice").hidden = !message;
}
function handle(fn) {
  return async (event) => {
    if (event) event.preventDefault();
    try {
      notice("");
      await fn(event);
    } catch (error) {
      notice(error.message);
    }
  };
}
function button(text, fn, className = "quiet") {
  const b = document.createElement("button");
  b.textContent = text;
  b.className = className;
  b.type = "button";
  b.onclick = handle(fn);
  return b;
}
function cloudConsent() {
  return (
    $("project-cloud-consent").checked || $("change-cloud-consent").checked
  );
}
function statusLabel(status) {
  return status === "generated"
    ? "Files ready · not tested"
    : status === "review_required"
      ? "Automated checks passed · try the app"
      : status.replaceAll("_", " ");
}
function selectedModels() {
  return { planner: modelConfig("planner"), coder: modelConfig("coder") };
}
function updateCloud() {
  const models = selectedModels();
  document.querySelector(".cloud-option").hidden =
    !Object.values(models).some(cloudModel);
}
function tab(name) {
  document.querySelectorAll("[data-tab]").forEach((b) => {
    const selected = b.dataset.tab === name;
    b.classList.toggle("selected", selected);
    b.setAttribute("aria-selected", String(selected));
  });
  ["proposal", "build", "files"].forEach(
    (t) => ($("panel-" + t).hidden = t !== name),
  );
  if (name === "files" && current && !activeStatuses.has(current.status))
    loadFiles().catch((e) => notice(e.message));
}
async function listProjects() {
  const projects = await api("/api/projects");
  $("projects").replaceChildren();
  $("workspace-project-count").textContent =
    projects.length + " saved projects";
  const calls = projects.flatMap((p) => p.model_calls || []);
  $("workspace-call-count").textContent =
    calls.length +
    " model requests · " +
    calls.reduce((n, c) => n + c.seconds, 0).toFixed(1) +
    "s";
  if (!projects.length) {
    const p = document.createElement("p");
    p.className = "muted";
    p.textContent = "Your ideas will live here.";
    $("projects").append(p);
  }
  for (const p of projects) {
    if (
      $("project-search").value &&
      !p.title.toLowerCase().includes($("project-search").value.toLowerCase())
    )
      continue;
    const b = button(
      "",
      () => openProject(p.id),
      "project-link" + (current?.id === p.id ? " selected" : ""),
    );
    const title = document.createElement("strong");
    title.textContent = p.title + (p.parent_id ? " · improvement" : "");
    const status = document.createElement("small");
    status.textContent = statusLabel(p.status);
    b.append(title, status);
    $("projects").append(b);
  }
}
async function openProject(id) {
  current = await api("/api/projects/" + id);
  lastPlan = "";
  $("revision").value = "";
  $("project-cloud-consent").checked = false;
  $("change-cloud-consent").checked = false;
  $("execution-consent").checked = false;
  $("create-view").hidden = true;
  $("project-view").hidden = false;
  render();
  tab(current.approved ? "build" : "proposal");
  await listProjects();
}
function fillList(id, items) {
  $(id).replaceChildren(
    ...items.map((text) => {
      const li = document.createElement("li");
      li.textContent = text;
      return li;
    }),
  );
}
function render() {
  if (!current) return;
  const p = current,
    busy = activeStatuses.has(p.status);
  $("breadcrumb").textContent = p.title;
  $("project-title").textContent = p.title;
  $("project-summary").textContent = p.plan?.summary || p.idea;
  $("project-status").textContent = statusLabel(p.status);
  $("project-status").className = "badge " + p.status;
  $("step-plan").classList.toggle("done", !!p.plan);
  $("step-approve").classList.toggle("done", p.approved);
  $("step-build").classList.toggle(
    "done",
    !!p.plan &&
      p.next_task === p.plan.tasks.length &&
      p.preflight?.passed === true,
  );
  $("step-check").classList.toggle("done", p.status === "verified");
  $("proposal-loading").hidden = !!p.plan;
  $("proposal-loading").textContent =
    p.status === "error"
      ? "Planning stopped: " + p.error + " — retry below."
      : "Your planner is shaping the idea. Local models may take a few minutes.";
  if (!p.plan && !busy) {
    $("proposal-loading").replaceChildren(
      document.createTextNode(p.error || "No proposal yet."),
      button("Retry proposal", () => job("plan", {}), "secondary"),
    );
  }
  $("proposal-history-notice").hidden =
    !p.plan_is_previous || p.status !== "error";
  $("proposal-history-notice").textContent =
    "The latest revision failed validation. You are viewing the previous saved proposal, not a successful revision. Review the error before retrying.";
  $("standard-plan-recovery").hidden =
    p.starter !== "arcade" || p.approved || !!p.parent_id || !!p.baseline_plan;
  $("recover-standard-game").disabled = busy;
  $("proposal-edit-tools").hidden = p.approved;
  $("proposal-import").disabled = busy;
  $("save-proposal-edits").disabled = busy || !p.plan;
  $("proposal-content").hidden = !p.plan;
  if (p.plan) {
    fillList("features", p.plan.features);
    fillList("limits", [
      ...p.plan.out_of_scope.map((x) => "Later: " + x),
      ...p.plan.risks.map((x) => "Consider: " + x),
    ]);
    $("tasks").replaceChildren(
      ...p.plan.tasks.map((t, i) => {
        const li = document.createElement("li");
        li.textContent = (i < p.next_task ? "✓ " : "") + t.title;
        const small = document.createElement("small");
        small.textContent =
          t.instructions +
          (t.check_indexes?.length
            ? " · Milestone checks: " +
              t.check_indexes.map((n) => p.plan.checks[n]?.name || n).join(", ")
            : "");
        li.append(small);
        return li;
      }),
    );
    $("acceptance").textContent = JSON.stringify(
      {
        http: p.plan.checks,
        browser: p.plan.browser_checks || [],
        manual: p.plan.manual_checks || [],
      },
      null,
      2,
    );
    const serialized = JSON.stringify(p.plan, null, 2);
    if (lastPlan !== serialized) {
      $("plan-editor").value = serialized;
      lastPlan = serialized;
    }
  }
  renderGuidance(p);
  renderChecks(p);
  renderManual(p);
  $("build-activity").textContent = busy
    ? "Working · " + (p.events.at(-1)?.message || p.status)
    : p.status === "generated"
      ? "Files inspected. Behavioral testing is the next step."
      : p.status === "verified"
        ? "Required checks passed. Your app is ready to download."
        : p.events.at(-1)?.message || "Ready for the next step.";
  $("build-activity").classList.toggle("busy", busy);
  $("plan-editor").disabled = p.approved || busy;
  $("proposal-actions").hidden = p.approved;
  $("approve").disabled = busy;
  renderProposalReview(p);
  $("revise").disabled = busy;
  $("generate").disabled = busy || !p.approved;
  $("verify").disabled = busy || !p.approved;
  $("stop").disabled = !busy;
  updateRuntime();
  $("download").disabled = busy || !p.approved;
  $("refresh-files").disabled = busy;
  $("progress-text").textContent =
    `${p.next_task} of ${p.plan?.tasks.length || 0} tasks saved. ${p.repair_count} repairs applied in total.`;
  $("edit-models").disabled = busy;
  $("improve-panel").hidden = !p.approved;
  $("request-change").disabled = busy;
  $("project-lineage").hidden = !p.parent_id;
  $("project-lineage").replaceChildren();
  if (p.parent_id) {
    $("project-lineage").append(
      document.createTextNode("Improvement of " + p.parent_title + " · "),
      button("Open original", () => openProject(p.parent_id)),
    );
  }
  $("model-usage").textContent =
    `${(p.model_calls || []).length} model requests · ${(p.model_calls || []).reduce((n, c) => n + c.seconds, 0).toFixed(1)} seconds of model response time. One request runs at a time.`;
  if (p.generation_stats?.exact_edits_applied)
    $("model-usage").textContent +=
      ` ${p.generation_stats.exact_edits_applied} exact edits applied.`;
  const lastResponse = (p.model_calls || []).filter((c) => c.success).at(-1);
  if (lastResponse)
    $("model-usage").textContent +=
      ` Last response: ${lastResponse.provider}/${lastResponse.model}.`;
  const lastRequest = (p.model_calls || []).at(-1);
  if (Number.isInteger(lastRequest?.input_characters))
    $("model-usage").textContent +=
      ` Last request size: ${lastRequest.input_characters.toLocaleString()} characters (not tokens).`;
  if (Number.isInteger(lastRequest?.requested_max_output_tokens))
    $("model-usage").textContent +=
      ` Output reservation: ${lastRequest.requested_max_output_tokens} tokens; recovery: ${lastRequest.recovery_path || "initial"}; finish: ${lastRequest.finish_reason || "not reported"}.`;
  const measured = (p.model_calls || []).filter(
    (c) =>
      Number.isInteger(c.prompt_tokens) ||
      Number.isInteger(c.completion_tokens),
  );
  if (measured.length)
    $("model-usage").textContent +=
      ` Reported tokens: ${measured.reduce((n, c) => n + (c.prompt_tokens || 0), 0)} input / ${measured.reduce((n, c) => n + (c.completion_tokens || 0), 0)} output from ${measured.length} requests.`;
  document.querySelector(".change-cloud").hidden = ![p.planner, p.coder].some(
    cloudModel,
  );
  $("model-label").textContent =
    `Planner: ${routeLabel(p.planner)} · Builder: ${routeLabel(p.coder)}`;
  document.querySelector(".project-cloud").hidden = ![p.planner, p.coder].some(
    cloudModel,
  );
  $("test-badge").textContent = p.checks
    ? p.checks.passed
      ? "Checks passed"
      : p.checks.failure_kind === "environment"
        ? "Verification blocked"
        : "Checks failed"
    : "Not verified";
  $("test-badge").className =
    "badge " + (p.checks?.passed ? "verified" : p.checks ? "error" : "");
  $("test-output").textContent = p.checks
    ? `Runtime: ${p.checks.runtime} · Exit: ${p.checks.exit_code}\n\n${p.checks.log}`
    : p.preflight
      ? p.preflight.passed
        ? "Static syntax/structure checks passed. No generated code has run. Behavioral verification still requires execution approval."
        : "Static inspection found problems (no code executed):\n\n" +
          p.preflight.issues.join("\n")
      : "No checks have run yet.";
  const phases = p.checks?.phases || [];
  $("phase-list").hidden = !phases.length;
  $("phase-list").replaceChildren();
  for (const [name, label] of [
    ["acceptance", "Approved behavior & assets"],
    ["tests", "Tests of the actual app"],
    ["launch", "Launch command"],
    ...(p.plan?.browser_checks?.length
      ? [["browser", "Real browser interactions"]]
      : []),
  ]) {
    const phase = phases.find((x) => x.phase === name);
    const card = document.createElement("div");
    card.className = "phase-card";
    const title = document.createElement("strong");
    title.textContent = label;
    const status = document.createElement("span");
    status.textContent = phase
      ? phase.behavior_passed && phase.workspace_cleanup === "failed"
        ? "Checks passed · cleanup failed"
        : phase.passed
          ? "Passed"
          : phase.failure_kind === "environment"
            ? "Environment blocked"
            : "Failed"
      : "Not run";
    status.className = phase
      ? phase.passed
        ? "phase-pass"
        : "phase-fail"
      : "muted";
    card.append(title, status);
    if (phase) {
      const details = document.createElement("small");
      const counts = [];
      if (Number.isInteger(phase.http_checks))
        counts.push(`${phase.http_checks} HTTP checks`);
      if (Number.isInteger(phase.tests_run))
        counts.push(`${phase.tests_run} tests`);
      if (Number.isInteger(phase.asset_checks))
        counts.push(`${phase.asset_checks} assets`);
      if (phase.workspace_cleanup)
        counts.push(`Workspace cleanup: ${phase.workspace_cleanup}`);
      details.textContent = counts.join(" · ");
      card.append(details);
    }
    $("phase-list").append(card);
  }
  $("events").replaceChildren(
    ...p.events.map((e) => {
      const d = document.createElement("div");
      d.className = "event";
      const time = document.createElement("time");
      time.textContent = new Date(e.time).toLocaleTimeString();
      d.append(time, document.createTextNode(e.message));
      return d;
    }),
  );
  $("snapshots").replaceChildren(
    ...p.snapshots
      .slice()
      .reverse()
      .map((s) => {
        const b = button(
          s.label,
          async () => {
            if (
              !confirm(
                "Restore this checkpoint? Current files will be backed up first.",
              )
            )
              return;
            current = await api(`/api/projects/${p.id}/restore`, {
              snapshot: s.id,
            });
            render();
            await loadFiles();
          },
          "secondary",
        );
        b.disabled = busy;
        return b;
      }),
  );
}
async function job(action, options) {
  if (!current) return;
  if (["build", "repair"].includes(action) && !options.execute)
    $("execution-consent").checked = false;
  current = await api(`/api/projects/${current.id}/${action}`, {
    ...options,
    cloud_consent: cloudConsent(),
  });
  render();
  await listProjects();
}
async function loadFiles() {
  fileCache = await api(`/api/projects/${current.id}/files`);
  $("file-list").replaceChildren();
  for (const [name, content] of Object.entries(fileCache)) {
    const b = button(name, () => {
      $("file-content").textContent = content;
      document
        .querySelectorAll("#file-list button")
        .forEach((x) => x.classList.toggle("selected", x === b));
    });
    $("file-list").append(b);
  }
  const first =
    Object.keys(fileCache).find((n) => n === "app.py") ||
    Object.keys(fileCache)[0];
  $("file-content").textContent = first
    ? fileCache[first]
    : "No generated files yet.";
}
async function connections() {
  const sequence = ++connectionSequence;
  document
    .querySelectorAll("#cloud-providers select, #cloud-local-model")
    .forEach((control) => {
      control.disabled = true;
    });
  $("cloud-new").disabled = true;
  $("cloud-project").disabled = true;
  $("connection-list").textContent = "Checking connections…";
  const info = await api("/api/connections");
  if (sequence !== connectionSequence) return;
  lastConnectionInfo = info;
  if (typeof renderCloudSetup === "function") renderCloudSetup(info);
  runtimeStatus = info.docker;
  updateRuntime();
  $("connection-list").replaceChildren();
  $("ollama-models").replaceChildren();
  for (const [name, p] of Object.entries(info.providers)) {
    const div = document.createElement("div");
    div.className = "connection-item";
    const strong = document.createElement("strong");
    strong.textContent = name;
    const text = document.createElement("p");
    text.textContent =
      name === "ollama"
        ? p.connected
          ? "Connected · " + p.models.join(", ")
          : "Not connected. Start Ollama, then check again."
        : p.configured
          ? info.cloud?.[name]?.status === "catalogue_available"
            ? "API key present · model catalogue access confirmed. Generation quota is checked when you run a job."
            : info.cloud?.[name]
              ? "API key present · last check: " + info.cloud[name].status
              : "API key present · connection not yet tested"
          : `Optional · add ${p.key_variable} to .env`;
    div.append(strong, text);
    $("connection-list").append(div);
    if (name === "ollama")
      for (const m of p.models) {
        const o = document.createElement("option");
        o.value = m;
        $("ollama-models").append(o);
      }
  }
  const d = document.createElement("p");
  d.className = "muted";
  d.textContent = info.docker?.image_ready
    ? "Docker is ready for isolated verification."
    : info.docker?.running
      ? "Docker is running. Prepare its image with: docker pull python:3.12-slim"
      : info.docker_installed
        ? "Docker is installed but not running. Start Docker Desktop."
        : "Docker not installed. Code generation works without it; isolated verification needs Docker Desktop.";
  $("connection-list").append(d);
  const browserStatus = document.createElement("p");
  browserStatus.textContent =
    "Optional browser automation: " +
    (info.browser?.available
      ? "Chromium available for trusted local verification."
      : info.browser?.detail ||
        "Not installed. Explicit manual checks still work.");
  $("connection-list").append(browserStatus);
}
$("idea-form").onsubmit = handle(async () => {
  const models = selectedModels();
  $("propose").disabled = true;
  try {
    const p = await api("/api/projects", {
      idea: $("idea").value,
      starter: $("starter").value || null,
      ...models,
      cloud_consent: $("create-cloud").checked,
    });
    localStorage.setItem("foundry-models", JSON.stringify(models));
    await openProject(p.id);
  } finally {
    $("propose").disabled = false;
  }
});
$("new-project").onclick = handle(async () => {
  current = null;
  lastPlan = "";
  $("create-view").hidden = false;
  $("project-view").hidden = true;
  $("breadcrumb").textContent = "A new beginning";
  await listProjects();
});
document.querySelectorAll("[data-idea]").forEach(
  (b) =>
    (b.onclick = () => {
      $("idea").value = b.dataset.idea;
      $("idea").focus();
    }),
);
document
  .querySelectorAll("[data-tab]")
  .forEach((b) => (b.onclick = () => tab(b.dataset.tab)));
["planner", "coder"].forEach(
  (role) =>
    ($(role + "-provider").onchange = () => {
      $(role + "-model").value =
        $(role + "-provider").value === "ollama"
          ? role === "coder"
            ? "qwen2.5-coder:7b"
            : "qwen3.5:9b"
          : defaults[$(role + "-provider").value];
      updateCloud();
    }),
);
$("revise").onclick = handle(() =>
  job("plan", { revision: $("revision").value }),
);
$("approve").onclick = handle(async () => {
  current = await api(`/api/projects/${current.id}/approve`, {
    plan: JSON.parse($("plan-editor").value),
  });
  render();
  tab("build");
  await listProjects();
});
$("generate").onclick = handle(() =>
  job("build", { execute: false, repairs: Number($("repairs").value) }),
);
$("verify").onclick = handle(async () => {
  if (!$("execution-consent").checked)
    throw new Error(
      "Review the execution settings and check the approval box first.",
    );
  await job("build", {
    execute: true,
    consent: true,
    runtime: $("runtime").value,
    milestones: $("milestone-checks").checked,
    repairs: Number($("repairs").value),
  });
});
$("stop").onclick = handle(async () => {
  const result = await api(`/api/projects/${current.id}/stop`, {});
  notice(result.message);
});
function updateRuntime() {
  const local = $("runtime").value === "local";
  const ready = runtimeStatus?.running && runtimeStatus?.image_ready;
  $("runtime-readiness").textContent = local
    ? "Local execution selected · review the generated code first"
    : runtimeStatus === null
      ? "Checking Docker availability…"
      : ready
        ? "Docker is ready for isolated checks"
        : !runtimeStatus.installed
          ? "Docker is not installed. You can generate and download files without it."
          : !runtimeStatus.running
            ? "Docker is installed but stopped. Start Docker Desktop to use isolated checks."
            : "Docker needs its Python image: docker pull python:3.12-slim";
  $("runtime-note").textContent = local
    ? "Generated code runs with your account permissions, including access to files and network. This option is not a sandbox. Choose it only after reviewing and trusting the code."
    : "Docker runs checks without network or host API keys. Local execution is an explicit alternative in the menu above; Foundry never switches automatically.";
  if (current)
    $("verify").disabled =
      activeStatuses.has(current.status) ||
      !current.approved ||
      (!local && !ready);
}
$("runtime").onchange = () => {
  $("execution-consent").checked = false;
  updateRuntime();
};
$("project-search").oninput = handle(listProjects);
const starterDescriptions = {
  arcade:
    "A playable Neon Dodge game with keyboard/touch controls, pause/restart and local high score. The plan adapts it; gameplay checks are explicit.",
  web: "A working server and protected foundation check. Your models add the approved features.",
  notes:
    "Starts with the reviewed Notes App and its tests. Your proposal explains the requested changes.",
  tasks:
    "Starts with the reviewed Task Tracker and its tests. Your proposal explains the requested changes.",
  "": "Your model creates every source file. Best for unusual small projects.",
};
$("starter").onchange = () => {
  $("standard-plan-create").hidden = $("starter").value !== "arcade";
  $("starter-description").textContent =
    starterDescriptions[$("starter").value];
};
$("refresh-files").onclick = handle(loadFiles);
$("download").onclick = handle(async () => {
  const response = await fetch(`/api/projects/${current.id}/download`, {
    headers: { "X-Foundry-Token": token },
  });
  if (!response.ok) {
    const result = await response.json();
    throw new Error(result.error);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "generated-app.zip";
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});
$("connections-button").onclick = handle(async () => {
  $("connections").showModal();
  await connections();
});
$("close-connections").onclick = () => $("connections").close();
$("refresh-connections").onclick = handle(connections);
try {
  const saved = JSON.parse(localStorage.getItem("foundry-models") || "null");
  if (saved)
    for (const role of ["planner", "coder"]) {
      $(role + "-provider").value = saved[role].provider;
      $(role + "-model").value = saved[role].model;
    }
} catch (_) {}
updateCloud();
listProjects().catch((e) => notice(e.message));
connections().catch(() => {});
setInterval(async () => {
  if (polling || !current || !activeStatuses.has(current.status)) return;
  polling = true;
  try {
    const id = current.id;
    const p = await api("/api/projects/" + id);
    if (current?.id !== id) return;
    current = p;
    render();
    if (!activeStatuses.has(p.status)) await listProjects();
  } catch (e) {
    notice(e.message);
  } finally {
    polling = false;
  }
}, 1800);

function renderChecks(p) {
  $("check-cards").replaceChildren();
  if (!p.plan) return;
  for (const check of p.plan.checks) {
    const card = document.createElement("div");
    card.className = "check-card";
    const title = document.createElement("strong");
    title.textContent = check.name;
    const detail = document.createElement("code");
    detail.textContent = `${check.restart_before ? "Restart server → " : ""}${check.method} ${check.path} → HTTP ${check.status}`;
    const covers = document.createElement("small");
    covers.textContent = (check.feature_indexes || [])
      .map((i) => p.plan.features[i])
      .filter(Boolean)
      .join(" · ");
    card.append(title, detail, covers);
    $("check-cards").append(card);
  }
  for (const [kind, checks] of [
    ["Browser automation", p.plan.browser_checks || []],
    ["Manual · not automated", p.plan.manual_checks || []],
  ]) {
    for (const check of checks) {
      const card = document.createElement("div");
      card.className = "check-card";
      const title = document.createElement("strong");
      title.textContent = check.name;
      const detail = document.createElement("small");
      detail.textContent =
        kind +
        (check.expected
          ? " · " + check.expected
          : " · Actual Chromium actions and assertions");
      card.append(title, detail);
      $("check-cards").append(card);
    }
  }
}
function renderManual(p) {
  const checks = p.plan?.manual_checks || [];
  const panel = $("manual-panel");
  panel.hidden = !checks.length || !p.approved;
  if (panel.hidden) return;
  const container = $("manual-checklist");
  // Preserve unsaved choices during polling of the same verified source.
  const key = p.id + ":" + (p.verification_fingerprint || "pending");
  if (container.dataset.key !== key) {
    container.replaceChildren();
    container.dataset.key = key;
    checks.forEach((check, i) => {
      const card = document.createElement("div");
      card.className = "manual-card";
      const title = document.createElement("strong");
      title.textContent = check.name;
      const steps = document.createElement("ol");
      check.steps.forEach((text) => {
        const li = document.createElement("li");
        li.textContent = text;
        steps.append(li);
      });
      const expected = document.createElement("p");
      expected.textContent = "Expected: " + check.expected;
      const label = document.createElement("label");
      label.textContent = "Your result ";
      const select = document.createElement("select");
      select.id = "manual-" + i;
      for (const [value, text] of [
        ["", "Not tested yet"],
        ["pass", "Passed when I tried it"],
        ["fail", "Failed when I tried it"],
      ]) {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = text;
        select.append(option);
      }
      const saved = p.manual_results?.results?.[i];
      select.value = saved === true ? "pass" : saved === false ? "fail" : "";
      label.append(select);
      const notesLabel = document.createElement("label");
      notesLabel.textContent =
        "What happened? (Required for a repair when this check fails)";
      const notes = document.createElement("textarea");
      notes.id = "manual-note-" + i;
      notes.maxLength = 2000;
      notes.rows = 2;
      notes.placeholder =
        "Example: I collected the shield, hit one obstacle, and the game ended a frame later.";
      notes.value = p.manual_results?.notes?.[i] || "";
      notesLabel.append(notes);
      card.append(title, steps, expected, label, notesLabel);
      container.append(card);
    });
  }
  const ready =
    p.checks?.passed &&
    !activeStatuses.has(p.status) &&
    !!p.verification_fingerprint;
  $("save-manual").disabled = !ready;
  const failed = p.manual_results?.results?.some((v) => v === false);
  $("repair-manual").disabled = !ready || !failed;
  $("repair-retest").disabled = !ready || !failed;
  $("repair-history").textContent = p.repair_history?.length
    ? p.repair_history.length +
      " recorded repair request(s). Earlier failure notes are included in the downloaded build report."
    : "";
  $("manual-result").textContent = p.manual_results?.time
    ? "Recorded " +
      new Date(p.manual_results.time).toLocaleString() +
      " · User-reported observations"
    : ready
      ? "Automated checks passed. Download and try the app, then record your results."
      : "Run automated verification before recording results.";
}
$("save-manual").onclick = handle(async () => {
  const values = (current.plan.manual_checks || []).map(
    (_, i) => $("manual-" + i).value,
  );
  if (values.some((v) => !v))
    throw new Error(
      "Choose passed or failed for every manual check after trying the app.",
    );
  current = await api(`/api/projects/${current.id}/manual`, {
    results: values.map((v) => v === "pass"),
    notes: values.map((_, i) => $("manual-note-" + i).value),
  });
  render();
  await listProjects();
});
async function repairManual(execute) {
  if (execute && !$("execution-consent").checked)
    throw new Error(
      "Review execution settings and check the approval box under Build & results first.",
    );
  if (Number($("repairs").value) < 1)
    throw new Error(
      "Choose at least one repair attempt under Build & results.",
    );
  await job("repair", {
    execute,
    consent: execute,
    runtime: $("runtime").value,
    repairs: Number($("repairs").value),
  });
  tab("build");
}
$("repair-manual").onclick = handle(() => repairManual(false));
$("repair-retest").onclick = handle(() => repairManual(true));
$("arcade-example").onclick = () => {
  $("starter").value = "arcade";
  $("starter").dispatchEvent(new Event("change"));
  $("idea").value =
    "Build Neon Dodge from the arcade starter. Keep keyboard and touch movement, falling obstacles and collisions, scoring, bounded difficulty, start/game-over screens, pause/resume, restart, and localStorage high scores. Use local assets, no database or score API. Keep an explicit manual gameplay checklist; HTTP checks prove delivery only.";
  $("idea").focus();
};

function renderGuidance(p) {
  const busy = activeStatuses.has(p.status);
  let title,
    description,
    action = "View progress",
    target = p.approved ? "build" : "proposal";
  if (busy) {
    title =
      p.status === "queued"
        ? "Waiting for a model"
        : "Your project is moving forward";
    description =
      p.events.at(-1)?.message || "Your work is saved as each task completes.";
  } else if (!p.approved && p.plan) {
    title = "Review the plan before we build";
    description =
      "Check the features, scope, and expected behavior below. Revise anything that does not match your idea.";
    action = "Review proposal";
  } else if (!p.approved) {
    title = "Let’s get your proposal ready";
    description =
      p.error ||
      "Your planner can retry or take a new direction. You can also change the selected models.";
    action = "Retry proposal";
  } else if (p.status === "review_required") {
    title = "Automated checks passed. Now play-test it.";
    description =
      "Download and run the app. Record the approved manual checks below; automated server tests do not prove gameplay works.";
    action = "Open project files";
    target = "files";
  } else if (p.status === "verified") {
    title = "Your app passed its checks";
    description =
      "Download it, follow its README, and try the workflows yourself. Describe the next improvement below when you’re ready.";
    action = "Get my app";
    target = "files";
  } else if (p.status === "generated") {
    title = "Files are ready. Now test the app.";
    description =
      runtimeStatus && !runtimeStatus.running
        ? "Files passed static inspection. Docker is unavailable on this computer. Review the files before considering trusted local execution, or set up Docker for isolated tests."
        : "Code has been inspected without running it. Choose an execution option and approve it to run real behavioral checks.";
    action = "Go to verification";
  } else if (
    ["error", "needs_attention", "stopped", "interrupted"].includes(p.status)
  ) {
    title = "Your work is saved. Let’s resolve the next step.";
    description =
      p.error ||
      (p.preflight?.passed === false ? p.preflight.issues.join(" ") : "") ||
      p.checks?.diagnosis ||
      (p.manual_results?.results?.some((v) => v === false)
        ? "You reported a failed check. Add what happened beside that check, save your results, then choose Repair files only or Repair & retest."
        : "") ||
      "Review the verification output, switch models if needed, and resume. Existing checkpoints remain available.";
    action = p.manual_results?.results?.some((v) => v === false)
      ? "Review failed checks"
      : "Review and resume";
  } else {
    title = "Your plan is approved. Let’s build.";
    description =
      "Generate the files first, or approve execution to build and test in one run. Your code stays in its own project.";
    action = "Choose build options";
  }
  $("next-title").textContent = title;
  $("next-description").textContent = description.slice(0, 450);
  $("next-action").textContent = action;
  $("next-models").hidden = busy;
  $("next-models").onclick = () => $("edit-models").click();
  $("next-action").onclick = handle(async () => {
    if (!busy && p.manual_results?.results?.some((v) => v === false)) {
      $("manual-panel").scrollIntoView({ behavior: "smooth", block: "start" });
      return;
    }
    if (!p.approved && !p.plan && !busy) {
      await job("plan", {});
      return;
    }
    tab(target);
    $("panel-" + target).scrollIntoView({ behavior: "smooth", block: "start" });
  });
  const failed =
    !!p.error ||
    p.preflight?.passed === false ||
    p.checks?.passed === false ||
    p.manual_results?.results?.some((v) => v === false);
  $("build-diagnosis").hidden = !failed;
  $("build-diagnosis").replaceChildren();
  if (failed) {
    const h = document.createElement("strong");
    h.textContent = "What needs attention";
    const text = document.createElement("p");
    text.textContent =
      (p.manual_results?.results?.some((v) => v === false)
        ? "A manual acceptance check failed. Automated checks passed, but your observations show the app needs more work. Add failure notes in the checklist, save them, then repair the failed checks directly."
        : "") ||
      p.error ||
      (p.preflight?.passed === false
        ? p.preflight.issues.join(" ")
        : p.checks?.diagnosis ||
          "The app did not pass its behavioral checks. The output below shows the failing test or request. You can retry with another model or restore a checkpoint.");
    $("build-diagnosis").append(h, text);
    $("test-details").open = true;
  }
}
async function workspaceInfo() {
  const info = await api("/api/info");
  const insights = await api("/api/insights");
  $("model-insights").replaceChildren();
  for (const model of insights.models) {
    const p = document.createElement("p");
    p.textContent = `${model.model}: ${model.verified}/${model.projects} projects currently verified · ${model.calls} builder requests · ${model.seconds}s`;
    $("model-insights").append(p);
  }
  const explanation = document.createElement("p");
  explanation.className = "muted";
  explanation.textContent = insights.explanation;
  $("model-insights").append(explanation);
  $("workspace-version").textContent = "IDEA FOUNDRY " + info.version;
  $("workspace-project-count").textContent = info.projects + " saved projects";
  $("workspace-call-count").textContent =
    info.model_calls + " model requests · " + info.model_seconds + "s";
  $("workspace-details").textContent =
    "Version " +
    info.version +
    " · Projects: " +
    info.projects +
    " · Data folder: " +
    info.data_folder;
  $("workspace-warnings").textContent = info.warnings.join(" ");
  return info;
}
async function saveDownload(path, name) {
  const response = await fetch(path, { headers: { "X-Foundry-Token": token } });
  if (!response.ok) {
    const result = await response.json();
    throw new Error(result.error);
  }
  const url = URL.createObjectURL(await response.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
$("workspace-button").onclick = handle(async () => {
  $("workspace-dialog").showModal();
  await workspaceInfo();
});
$("close-workspace").onclick = () => $("workspace-dialog").close();
$("backup-workspace").onclick = handle(() =>
  saveDownload("/api/backup", "Idea-Foundry-workspace-backup.zip"),
);
$("edit-models").onclick = handle(() => {
  for (const role of ["planner", "coder"]) {
    $("project-" + role + "-provider").value = current[role].provider;
    $("project-" + role + "-model").value = current[role].model;
    fillModelSettings(role, "project-", current[role]);
  }
  $("models-dialog").showModal();
});
$("project-route-setup").onclick = handle(async () => {
  $("models-dialog").close();
  $("connections").showModal();
  await connections();
});
$("close-models").onclick = () => $("models-dialog").close();
$("model-form").onsubmit = handle(async () => {
  const models = {
    planner: modelConfig("planner", "project-"),
    coder: modelConfig("coder", "project-"),
  };
  current = await api("/api/projects/" + current.id + "/models", models);
  $("models-dialog").close();
  $("project-cloud-consent").checked = false;
  $("change-cloud-consent").checked = false;
  render();
});
$("request-change").onclick = handle(async () => {
  const b = $("request-change");
  b.disabled = true;
  try {
    const next = await api("/api/projects/" + current.id + "/change", {
      request: $("change-request").value,
      cloud_consent: cloudConsent(),
    });
    $("change-request").value = "";
    await openProject(next.id);
  } finally {
    b.disabled = false;
  }
});
$("review-diff").onclick = handle(async () => {
  const files = await api("/api/projects/" + current.id + "/diff");
  $("diff-list").replaceChildren();
  if (!files.length)
    $("diff-list").textContent = "No source changes since the last checkpoint.";
  for (const file of files) {
    const d = document.createElement("details");
    const title = document.createElement("summary");
    title.textContent = file.kind + " · " + file.name;
    const pre = document.createElement("pre");
    pre.textContent = file.diff;
    d.append(title, pre);
    $("diff-list").append(d);
  }
});
workspaceInfo().catch(() => {});

$("recover-standard-game").onclick = handle(async () => {
  const id = current.id;
  current = await api(`/api/projects/${id}/starter-plan`, {});
  reviewedProposal = null;
  lastPlan = "";
  render();
  tab("proposal");
  await listProjects();
});
$("create-standard-game").onclick = handle(async () => {
  const models = selectedModels();
  $("create-standard-game").disabled = true;
  try {
    const project = await api("/api/projects", {
      idea: "Use the standard reviewed Neon Dodge game with localStorage and its manual gameplay checklist.",
      starter: "arcade",
      use_reviewed_plan: true,
      ...models,
      cloud_consent: $("create-cloud").checked,
    });
    await openProject(project.id);
  } finally {
    $("create-standard-game").disabled = false;
  }
});

async function saveReviewedProposal(plan) {
  const id = current.id;
  const saved = await api(`/api/projects/${id}/proposal`, { plan });
  if (current?.id !== id) return;
  current = saved;
  reviewedProposal = null;
  lastPlan = "";
  render();
  $("proposal-edit-feedback").textContent =
    `Saved ${saved.plan.tasks.length} tasks. No model request. Review the updated plan below before approving.`;
  await listProjects();
}
$("save-proposal-edits").onclick = handle(async () => {
  await saveReviewedProposal(JSON.parse($("plan-editor").value));
});
$("proposal-import").onchange = handle(async () => {
  const file = $("proposal-import").files[0];
  const projectId = current?.id;
  if (!file || !projectId) return;
  if (file.size > 50000)
    throw new Error("Proposal JSON is too large (maximum file size 50 KB).");
  const plan = JSON.parse(await file.text());
  if (current?.id !== projectId)
    throw new Error(
      "Project changed. Select the proposal file again for the intended project.",
    );
  await saveReviewedProposal(plan);
  $("proposal-import").value = "";
});
