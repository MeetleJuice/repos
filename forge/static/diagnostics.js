"use strict";
// Diagnostics observes the controller. Idea generation is an isolated local helper.
let diagBusy = false;
let diagProjectId = null;
let diagReportId = null;
let diagSessionId = null;
let diagTimer;
let ideaHelperBusy = false;
let ideaHelperActiveJobs = false;
let ideaInputRevision = 0;
const diagnosticCheckLabels = {
  private_storage:'Private workspace storage', controller_smoke:'Planning validation checks',
  planning_guards:'Adversarial planning checks', loop_guards:'Repair evidence safeguards',
  stage_harness_guards:'Stage context & API registry safeguards',
  project_execution:'Selected build · evidence audit only', project_plan:'Selected proposal · local review only',
  local_catalogue:'Ollama connection', provider_catalogue:'Provider catalogue · not generation',
  fixed_json_probe:'Model response test · small JSON fixture', planner_stage_probe:'Local planning · acceptance-schema fixture',
  model_probe_setup:'No saved model route available',
};

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
  if (summary.selected_planning_memory?.schema) {
    const memory = summary.selected_planning_memory;
    const detail = document.createElement('p');
    detail.textContent = `Selected project memory: ${memory.accepted_features} features with validated acceptance · ${memory.known_contracts} API contracts · ${memory.check_count} HTTP checks. Prefix identity is included in the ZIP. These are unapproved planning facts, not execution evidence.`;
    $("diag-summary").append(detail);
  }
  if (summary.selected_planning?.available) {
    const run = summary.selected_planning;
    const planning = document.createElement('p');
    planning.textContent = `Latest selected planning run: ${run.recorded_attempts ?? 'unknown'} attempts · ${run.schema_rejections ?? 0} rejected drafts · ${run.budget_rejections ?? 0} budget refusals · ${run.timeout_attempts ?? 0} timeouts · ${run.model_seconds ?? 'unknown'} model seconds. Rules: ${(run.review_codes || []).join(', ') || 'none retained'}. No task execution is implied.`;
    $("diag-summary").append(planning);
  }
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

function renderDiagnosticSession(session) {
  diagSessionId = session.id || null;
  diagBusy = session.status === 'running';
  $("diag-dialog").setAttribute('aria-busy', String(diagBusy));
  $("diag-run").disabled = diagBusy;
  $("diag-stop").disabled = !diagBusy;
  $("diag-progress").hidden = !diagBusy;
  $("diag-export").disabled = !session.download_ready;
  const rows = session.checks?.rows || [];
  $("diag-checks").replaceChildren(...rows.map(row => {
    const line = document.createElement('p');
    line.dataset.status = ['passed','failed','skipped'].includes(row.status) ? row.status : 'unknown';
    line.textContent = `${diagnosticCheckLabels[row.code] || row.code} · ${row.provider || 'this computer'} ${row.model || ''} · ${row.status}${row.failure_class ? ' · ' + row.failure_class : ''}${row.seconds == null ? '' : ' · ' + row.seconds + 's'}`;
    return line;
  }));
  if (session.report) {
    renderDiagnosticReport(session.report);
    diagReportId = session.report.id;
  }
  const state = session.status || 'unknown';
  $("diag-status").textContent = diagBusy
    ? `Diagnostics running · ${session.phase || 'checks'}${session.checks?.active_check ? ' · ' + session.checks.active_check : ''} · ${rows.length} checks recorded. You can close this panel and return.`
    : session.download_ready
      ? `Evidence ready · ${state} · ${session.checks_passed ?? 0} checks passed, ${session.checks_failed ?? 0} failed, ${session.checks_skipped ?? 0} skipped.${session.checks_skipped_reason ? ' Checks not run: ' + session.checks_skipped_reason + '.' : ''} Download this snapshot below. These checks do not verify your generated app.`
      : `Diagnostics ${state}.${session.exception_type ? ' Collection error: ' + session.exception_type + '.' : ''} Rerun to collect a new snapshot.`;
  clearTimeout(diagTimer);
  if (diagBusy && $("diag-dialog").open) diagTimer = setTimeout(pollDiagnosticSession, 1000);
}
async function pollDiagnosticSession() {
  try { renderDiagnosticSession(await api('/api/diagnostics/session/status')); }
  catch (error) {
    $("diag-status").textContent = 'Could not read diagnostic progress: ' + error.message;
    if ($("diag-dialog").open) diagTimer = setTimeout(pollDiagnosticSession, 2000);
  }
}
async function startDiagnosticSession(mode = 'quick') {
  diagBusy = true;
  diagProjectId = current?.id || null;
  diagReportId = null;
  diagSessionId = null;
  clearTimeout(diagTimer);
  $("diag-dialog").setAttribute("aria-busy", "true");
  $("diag-run").disabled = true;
  $("diag-status").textContent = "Starting safe checks and evidence collection…";
  $("diag-summary").replaceChildren();
  $("diag-findings").replaceChildren();
  $("diag-completeness").textContent = "Collection in progress.";
  $("diag-export-status").textContent = "";
  $("diag-export").disabled = true;
  try {
    renderDiagnosticSession(await api('/api/diagnostics/session/start', {
      project_id: diagProjectId, mode, cloud_consent: mode === 'cloud' && $("diag-consent").checked,
    }));
  } catch (error) {
    diagBusy = false;
    $("diag-run").disabled = false;
    $("diag-dialog").setAttribute("aria-busy", "false");
    $("diag-status").textContent = "Diagnostic session did not start: " + error.message;
  }
}
$("diag-button").onclick = async () => {
  if (!$("diag-dialog").open) $("diag-dialog").showModal();
  // The previous completed snapshot must not remain downloadable while this
  // click is selecting/rejoining a session asynchronously.
  diagBusy = true;
  clearTimeout(diagTimer);
  $("diag-dialog").setAttribute('aria-busy', 'true');
  $("diag-run").disabled = true;
  $("diag-export").disabled = true;
  $("diag-status").textContent = 'Checking diagnostic session…';
  try {
    const session = await api('/api/diagnostics/session/status');
    if (session.status === 'running') renderDiagnosticSession(session);
    else await startDiagnosticSession();
  } catch (error) {
    diagBusy = false;
    $("diag-dialog").setAttribute('aria-busy', 'false');
    $("diag-run").disabled = false;
    $("diag-status").textContent = error.message;
  }
};
$("diag-run").onclick = () => startDiagnosticSession($("diag-mode").value);
$("diag-mode").onchange = () => {
  const cloud = $("diag-mode").value === 'cloud';
  $("diag-consent-label").hidden = !cloud;
  if (!cloud) $("diag-consent").checked = false;
};
$("diag-stop").onclick = async () => {
  try { renderDiagnosticSession(await api('/api/diagnostics/session/stop', {})); }
  catch (error) { $("diag-status").textContent = error.message; }
};
$("close-diag").onclick = () => $("diag-dialog").close();
$("diag-dialog").addEventListener('close', () => clearTimeout(diagTimer));
$("diag-export").onclick = async () => {
  $("diag-export").disabled = true;
  $("diag-export-status").textContent = "Preparing a sanitized diagnostic ZIP. Your recorded history is kept.";
  try {
    const response = await fetch("/api/diagnostics/session/export", {
      method: "POST", headers: {"X-Foundry-Token": token, "Content-Type": "application/json"},
      body: JSON.stringify({session_id: diagSessionId}),
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
