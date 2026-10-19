"use strict";
// Proposal review and model settings are independent from source generation.
const routePools = {};
let reviewedProposal = null;
let proposalReviewTimer = null;
let proposalReviewSequence = 0;

function modelConfig(role, prefix = "") {
  const id = prefix + role;
  const config = {
    provider: document.getElementById(id + "-provider").value,
    model: document.getElementById(id + "-model").value,
  };
  const context = document.getElementById(id + "-context");
  if (context)
    config.options = {
      num_ctx: Number(context.value),
      num_predict: Number(document.getElementById(id + "-output").value),
      structured_outputs: document.getElementById(id + "-structured").checked,
    };
  const fallback = document.getElementById(id + "-fallback-provider");
  if (fallback?.value)
    config.fallback = {
      provider: fallback.value,
      model: document.getElementById(id + "-fallback-model").value,
    };
  if (routePools[id]?.length) {
    config.fallbacks = routePools[id];
    delete config.fallback;
  }
  return config;
}

function cloudModel(config) {
  return (
    config.provider !== "ollama" ||
    !!(config.fallback && cloudModel(config.fallback)) ||
    (config.fallbacks || []).some(cloudModel)
  );
}

function fillModelSettings(role, prefix, config) {
  const id = prefix + role;
  routePools[id] = config.fallbacks || [];
  showPool(id);
  const context = document.getElementById(id + "-context");
  if (!context) return;
  context.value = config.options?.num_ctx || 16384;
  context.dispatchEvent(new Event("change"));
  document.getElementById(id + "-output").value =
    config.options?.num_predict || Math.min(8192, Number(context.value) / 2);
  document.getElementById(id + "-structured").checked =
    config.options?.structured_outputs !== false;
  document.getElementById(id + "-fallback-provider").value =
    config.fallback?.provider || "";
  document.getElementById(id + "-fallback-model").value =
    config.fallback?.model || "";
  document
    .getElementById(id + "-fallback-provider")
    .dispatchEvent(new Event("change"));
}

function renderProposalReview(project) {
  const panel = document.getElementById("proposal-review");
  const editor = document.getElementById("plan-editor");
  const local =
    reviewedProposal?.id === project.id &&
    reviewedProposal.text === editor.value;
  const edited =
    project.plan && editor.value !== JSON.stringify(project.plan, null, 2);
  const result = local
    ? reviewedProposal.result
    : edited
      ? {
          passed: false,
          findings: [
            {
              severity: "error",
              path: "/",
              message: "Checking the edited proposal…",
            },
          ],
        }
      : project.plan_review;
  panel.hidden = !result;
  if (!result) {
    if (
      project.plan &&
      !project.approved &&
      !activeStatuses.has(project.status)
    ) {
      document.getElementById("approve").disabled = true;
      clearTimeout(proposalReviewTimer);
      proposalReviewTimer = setTimeout(reviewEditor, 0);
    }
    return;
  }
  document.getElementById("proposal-review-status").textContent = result.passed
    ? "Proposal consistency checks passed" +
      (project.proposal_source?.kind === "reviewed_starter" && !edited
        ? " · reviewed standard starter plan"
        : "") +
      (project.planning_stats?.attempts > 1
        ? ` · recovered in ${project.planning_stats.attempts} requests${project.planning_stats.fallback_used ? " using configured fallback" : ""}`
        : "")
    : "Resolve proposal contradictions before approval";
  panel.classList.toggle("review-failed", !result.passed);
  const items = document.getElementById("proposal-findings");
  items.replaceChildren();
  for (const finding of result.findings || []) {
    const item = document.createElement("li");
    item.textContent = `${finding.severity === "error" ? "Fix" : "Review"} ${finding.path}: ${finding.message}`;
    items.append(item);
  }
  if (!project.approved && !result.passed)
    document.getElementById("approve").disabled = true;
}

async function reviewEditor() {
  if (!current || current.approved || activeStatuses.has(current.status))
    return;
  const id = current.id;
  const text = document.getElementById("plan-editor").value;
  const sequence = ++proposalReviewSequence;
  document.getElementById("approve").disabled = true;
  let result;
  try {
    const plan = JSON.parse(text);
    result = await api(`/api/projects/${id}/review`, { plan });
  } catch (error) {
    result = {
      passed: false,
      findings: [{ severity: "error", path: "/", message: error.message }],
    };
  }
  if (
    sequence !== proposalReviewSequence ||
    current?.id !== id ||
    activeStatuses.has(current.status) ||
    document.getElementById("plan-editor").value !== text
  )
    return;
  reviewedProposal = { id, text, result };
  document.getElementById("approve").disabled = !result.passed;
  renderProposalReview(current);
}

window.addEventListener("DOMContentLoaded", () => {
  for (const prefix of ["", "project-"]) {
    for (const role of ["planner", "coder"]) {
      const id = prefix + role;
      const details = document.createElement("details");
      details.className = "model-advanced";
      const summary = document.createElement("summary");
      summary.textContent = "Output settings & routing";
      details.append(summary);
      // This markup contains fixed application strings only, never project/model input.
      const controls = document.createElement("div");
      controls.className = "model-settings";
      controls.innerHTML = `
        <label for="${id}-context">Ollama context (uses RAM/VRAM)</label>
        <select id="${id}-context"><option>4096</option><option>8192</option><option selected>16384</option><option>32768</option></select>
        <label for="${id}-output">Maximum output tokens</label><select id="${id}-output"></select>
        <label class="check-line"><input id="${id}-structured" type="checkbox" checked>Use native Ollama JSON schema</label>
        <p id="${id}-pool-label" class="muted"></p><button type="button" id="${id}-clear-pool" hidden>Use manual model settings</button>
        <label for="${id}-fallback-provider">Fallback provider · optional</label>
        <select id="${id}-fallback-provider">
          <option value="">None · use primary only</option>
          <option value="ollama">Ollama</option>
          <option value="groq">Groq</option>
          <option value="gemini">Gemini</option>
          <option value="openrouter">OpenRouter</option>
        </select>
        <label for="${id}-fallback-model">Fallback model ID</label>
        <input id="${id}-fallback-model" disabled placeholder="Choose a provider first">
        <p class="muted">Manual mode supports one fallback. Cloud-first mode supports two fallbacks. Cloud calls require your consent. Smaller contexts use less memory; they may not fit larger tasks.</p>`;
      details.append(controls);
      document
        .getElementById(id + "-model")
        .closest("fieldset")
        .append(details);
      const context = document.getElementById(id + "-context");
      context.onchange = () => {
        const output = document.getElementById(id + "-output");
        const previous = Number(output.value);
        output.replaceChildren();
        for (const size of [1024, 2048, 4096, 8192]) {
          if (size >= Number(context.value)) continue;
          const option = document.createElement("option");
          option.value = size;
          option.textContent = size;
          output.append(option);
        }
        output.value =
          previous && previous < Number(context.value)
            ? previous
            : Math.min(8192, Number(context.value) / 2);
      };
      context.dispatchEvent(new Event("change"));
      document.getElementById(id + "-clear-pool").onclick = () => {
        routePools[id] = [];
        showPool(id);
        if (!prefix) updateCloud();
      };
      document.getElementById(id + "-fallback-provider").onchange = () => {
        const enabled = !!document.getElementById(id + "-fallback-provider")
          .value;
        document.getElementById(id + "-fallback-model").disabled = !enabled;
        document.getElementById(id + "-fallback-model").required = enabled;
        if (!prefix) updateCloud();
      };
    }
  }
  try {
    const saved = JSON.parse(localStorage.getItem("foundry-models") || "null");
    if (saved)
      for (const role of ["planner", "coder"])
        fillModelSettings(role, "", saved[role]);
  } catch (_) {
    /* Keep defaults when saved browser settings are invalid. */
  }
  updateCloud();
  document.getElementById("plan-editor").addEventListener("input", () => {
    clearTimeout(proposalReviewTimer);
    document.getElementById("approve").disabled = true;
    proposalReviewTimer = setTimeout(reviewEditor, 500);
  });
  document.getElementById("review-proposal-button").onclick = handle(
    async () => {
      await reviewEditor();
      if (current && reviewedProposal?.id === current.id) {
        document.getElementById("proposal-edit-feedback").textContent =
          reviewedProposal.result.passed
            ? "Checked: valid. Save edited proposal to update the plan cards, or approve when ready. No model request."
            : "Check found errors. Resolve the findings above before saving or approving.";
      }
    },
  );
});

function showPool(id) {
  const label = document.getElementById(id + "-pool-label");
  if (!label) return;
  label.textContent = routePools[id]?.length
    ? "Automatic service failover → " +
      routePools[id].map((c) => c.provider + "/" + c.model).join(" → ")
    : "";
  document.getElementById(id + "-clear-pool").hidden = !routePools[id]?.length;
}
function routeLabel(config) {
  return [
    config,
    ...(config.fallbacks || (config.fallback ? [config.fallback] : [])),
  ]
    .map((c) => c.provider + "/" + c.model)
    .join(" → ");
}
