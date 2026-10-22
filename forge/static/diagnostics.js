"use strict";
// Diagnostics observes the controller. Idea generation is an isolated local helper.
let diagBusy = false;
let diagProjectId = null;
let diagReportId = null;
let ideaHelperBusy = false;
let ideaHelperActiveJobs = false;
let ideaInputRevision = 0;

function refreshIdeaHelper(projects) {
  ideaHelperActiveJobs = projects.some((project) => activeStatuses.has(project.status));
  $("generate-idea").disabled = ideaHelperBusy;
  $("generate-idea").title = ideaHelperActiveJobs
    ? "Finish or stop the running job before using the local idea helper."
    : "Ask your local Ollama model for a small project prompt";
}

function renderDiagnosticReport(report) {
  const summary = report.summary || {};
  $("diag-summary").replaceChildren();
  if (summary.headline) {
    const headline = document.createElement("strong");
    headline.textContent = summary.headline;
    $("diag-summary").append(headline);
  }
  const facts = document.createElement("p");
  const failures = summary.confirmed_failures ?? summary.confirmed_failure ?? 0;
  const warnings = summary.warnings ?? summary.warning ?? 0;
  facts.textContent = `${failures} recorded failure finding(s) across workspace history · ${warnings} warning(s) · ${summary.missing_evidence ?? 0} evidence gap(s). These totals can include older projects; they are not a count of currently broken providers.`;
  $("diag-summary").append(facts);
  const coverage = document.createElement("p");
  coverage.textContent = `${summary.detailed_project_count ?? "Unknown"} detailed projects · ${summary.history_records ?? "Unknown"} controller events · ${summary.recorder_records ?? "Unknown"} recorder events. Includes planning structure, validation rule codes and retained attempt metrics.`;
  $("diag-summary").append(coverage);
  if (summary.selected_execution?.available) {
    const run = summary.selected_execution;
    const execution = document.createElement('p');
    execution.textContent = `Latest selected build: ${run.status || 'no terminal record'} · ${run.tasks_saved} task saves · ${run.attempts} retained model attempts · ${(run.repairs || []).length} repairs. ${run.unattributed_attempts || 0} older attempts lack task/stage attribution. Historical outcomes; check source freshness in the ZIP.`;
    $("diag-summary").append(execution);
    if (run.pending_requests?.length) {
      const pending = document.createElement('p');
      pending.textContent = `${run.pending_requests.length} request start(s) have no retained completion. They may be active, interrupted, or missing history; this alone does not prove a provider outage.`;
      $("diag-summary").append(pending);
    }
    for (const repair of run.repairs || []) {
      const detail = document.createElement('p');
      detail.textContent = `Repair ${repair.repair_id} · ${repair.stage || 'unknown stage'} · ${repair.status} · later matching-source check: ${repair.validation}.`;
      $("diag-summary").append(detail);
    }
    if (!run.coverage?.run_start_retained || !run.coverage?.run_end_retained || run.coverage?.history_gaps) {
      const gap = document.createElement('p');
      gap.textContent = 'This run has missing boundary records or a history coverage gap. An unfinished record may mean active work or interruption; it does not establish the cause.';
      $("diag-summary").append(gap);
    }
  }
  if (summary.selected_project_review?.available) {
    const review = document.createElement('p');
    const result = summary.selected_project_review;
    review.textContent = `Selected proposal · current local review: ${result.passed ? 'passed' : 'needs attention'}${result.review_codes?.length ? ' · ' + result.review_codes.join(', ') : ''}. No app code executed; stored approvals were kept.`;
    $("diag-summary").append(review);
  }
  if (summary.latest_test?.status) {
    const tests = document.createElement("p");
    tests.textContent = `Latest Test: ${summary.latest_test.status} · ${summary.latest_test.results} results · ${summary.latest_test.failed} failed. Detailed results are included in the ZIP.`;
    $("diag-summary").append(tests);
  }
  const classifications = {
    confirmed_failure: "Confirmed failure",
    warning: "Warning",
    healthy: "Healthy check",
    missing_evidence: "Missing evidence",
    hypothesis: "Possible cause · unconfirmed",
  };
  $("diag-findings").replaceChildren(...(report.findings || []).map((finding) => {
    const article = document.createElement("article");
    article.className = "diag-finding";
    const classification = Object.hasOwn(classifications, finding.classification) ? finding.classification : "missing_evidence";
    article.dataset.classification = classification;
    const label = document.createElement("small");
    label.textContent = classifications[classification];
    const heading = document.createElement("strong");
    heading.textContent = finding.component || "Diagnostic check";
    const message = document.createElement("p");
    message.textContent = finding.message || "No description was recorded.";
    article.append(label, heading, message);
    const references = finding.event_ids || finding.evidence_ids || [];
    if (references.length) {
      const evidence = document.createElement("small");
      evidence.className = "diag-evidence";
      evidence.textContent = "Evidence: " + references.join(", ");
      article.append(evidence);
    }
    return article;
  }));
  if (!(report.findings || []).length) {
    const missing = document.createElement("p");
    missing.textContent = "No findings were returned. This does not establish that every component is healthy.";
    $("diag-findings").append(missing);
  }
  $("diag-completeness").textContent = JSON.stringify(report.completeness || {missing: ["Coverage was not recorded."]}, null, 2);
  $("diag-status").textContent = `Collected ${report.created_at || "at an unrecorded time"}. Download the ZIP for the event records and evidence manifest.`;
}

$("diag-button").onclick = async () => {
  if (!$("diag-dialog").open) $("diag-dialog").showModal();
  if (diagBusy) return;
  diagBusy = true;
  diagProjectId = current?.id || null;
  diagReportId = null;
  $("diag-dialog").setAttribute("aria-busy", "true");
  $("diag-status").textContent = "Inspecting local evidence, environment, and Ollama availability…";
  $("diag-summary").replaceChildren();
  $("diag-findings").replaceChildren();
  $("diag-completeness").textContent = "Collection in progress.";
  $("diag-export-status").textContent = "";
  $("diag-export").disabled = true;
  try {
    const report = await api("/api/diagnostics", {project_id: diagProjectId});
    renderDiagnosticReport(report);
    diagReportId = report.id || null;
  } catch (error) {
    $("diag-status").textContent = "Diagnostic collection did not finish: " + error.message;
    $("diag-completeness").textContent = "The investigation is incomplete. You can still try exporting the evidence available to the server.";
  } finally {
    diagBusy = false;
    $("diag-dialog").setAttribute("aria-busy", "false");
    $("diag-export").disabled = false;
  }
};
$("close-diag").onclick = () => $("diag-dialog").close();
$("diag-export").onclick = async () => {
  $("diag-export").disabled = true;
  $("diag-export-status").textContent = "Preparing a sanitized diagnostic ZIP. Your recorded history is kept.";
  try {
    const response = await fetch("/api/diagnostics/export", {
      method: "POST", headers: {"X-Foundry-Token": token, "Content-Type": "application/json"},
      body: JSON.stringify({project_id: diagProjectId, report_id: diagReportId}),
    });
    if (!response.ok) {
      const result = await response.json();
      throw new Error(result.error || "Diagnostic export failed.");
    }
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "Idea-Foundry-Diagnostics.zip";
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    $("diag-export-status").textContent = "Download prepared. Open START_HERE.md in the ZIP, review it, then attach the ZIP to our conversation. Nothing was uploaded.";
  } catch (error) {
    $("diag-export-status").textContent = error.message;
  } finally {
    $("diag-export").disabled = false;
  }
};

$("idea").addEventListener("input", () => { ideaInputRevision++; });
$("generate-idea").onclick = async () => {
  if (ideaHelperBusy) return;
  if (ideaHelperActiveJobs) {
    ideaHelperBusy = true;
    $("generate-idea").disabled = true;
    try {
      refreshIdeaHelper(await api("/api/projects"));
    } catch (error) {
      $("idea-generation-status").textContent = error.message;
      return;
    } finally {
      ideaHelperBusy = false;
      $("generate-idea").disabled = false;
    }
    if (ideaHelperActiveJobs) {
      $("idea-generation-status").textContent = "Finish or stop the running job before asking Ollama for an idea. Your text was kept.";
      return;
    }
  }
  const original = $("idea").value;
  if (original.trim() && !window.confirm("Replace the idea currently in this field with a fresh local suggestion? Your current text stays if generation fails.")) return;
  const revision = ideaInputRevision;
  const projectId = current?.id || null;
  ideaHelperBusy = true;
  $("generate-idea").disabled = true;
  $("idea-generation-status").textContent = "Asking your local Ollama model for a small, doable project. You can keep editing while it works…";
  try {
    const selections = selectedModels();
    const result = await api("/api/ideas/generate", {project_id: projectId,
      profiles: [selections.planner, selections.coder]});
    if (typeof result.idea !== "string" || !result.idea.trim() || result.idea.length > 12000) throw new Error("The local model did not return a usable project prompt. Your text was kept.");
    if ($("idea").value !== original || revision !== ideaInputRevision || (current?.id || null) !== projectId) {
      $("idea-generation-status").textContent = "Your newer text or project selection was kept. The suggestion was not inserted. Click Generate Idea again when ready.";
      return;
    }
    $("idea").value = result.idea.trim();
    $("idea").dispatchEvent(new Event("input", {bubbles: true}));
    $("idea").focus();
    $("idea-generation-status").textContent = `Suggested by local Ollama${result.model ? " / " + result.model : ""}. Review and edit this prompt, then choose how to plan. No project was started.`;
  } catch (error) {
    $("idea-generation-status").textContent = error.message;
  } finally {
    ideaHelperBusy = false;
    $("generate-idea").disabled = false;
  }
};
