"use strict";
let systemTestTimer;
function renderSystemTests(report) {
  const running = report.status === "running";
  $("system-test-start").disabled = running;
  $("system-test-stop").disabled = !running;
  $("system-test-status").textContent = report.available
    ? `Run ${report.status}. ${(report.rows || []).length} results recorded. Open Diag after the run to collect its evidence. A passing probe does not prove an app can be built.`
    : "Choose your checks, then click Run checks. No inference runs merely by opening this panel.";
  if (report.generation_requested && report.planned_probes === 0) $("system-test-status").textContent += " No saved model route was available, so no inference was tested. Choose a project or configure studio defaults first.";
  $("system-test-results").replaceChildren(...(report.rows || []).map(row => {
    const labels = {private_storage:"Private workspace storage", controller_smoke:"Planning validation checks", planning_guards:"Adversarial planning checks", project_plan:"Selected proposal · local review only", local_catalogue:"Ollama connection", provider_catalogue:"Provider catalogue · not generation", fixed_json_probe:"Model response test · small JSON fixture", model_probe_setup:"No saved model route available"};
    const failures = {quota:"Credits or quota required", rate_limit:"Rate limit reached", auth:"Authentication or access refused", provider:"Provider service error", transport:"Connection or timeout error", format:"Unexpected response format", truncated_output:"Output budget exhausted · provider replied", probe_assertion:"The response did not match the fixed test"};
    const article = document.createElement("article"); article.className = "diag-finding";
    const title = document.createElement("strong"); title.textContent = `${labels[row.code] || row.code} · ${row.provider || "this computer"} ${row.model || ""}`;
    const timing = row.seconds == null ? "timing recorded for catalogue sweep" : `${row.seconds} seconds`;
    const result = document.createElement("p"); result.textContent = `${row.status} · ${timing}${row.failure_class ? " · " + (failures[row.failure_class] || row.failure_class) : ""}${row.http_status ? " · HTTP " + row.http_status : ""}${row.category ? " · " + row.category : ""}`;
    article.append(title, result);
    if (row.response_received === true && row.response_accepted === false) {
      const received = document.createElement('p');
      received.textContent = 'A reply was received, but the fixed JSON test did not pass. This is not evidence that the provider is offline.';
      article.append(received);
    }
    if (row.review_codes?.length || row.case_count) {
      const details = document.createElement('p');
      details.textContent = row.review_codes?.length ? 'Review findings: ' + row.review_codes.join(', ') : `${row.case_count} fixed guard scenarios. This does not execute your app or prove model quality.`;
      article.append(details);
    }
    return article;
  }));
  clearTimeout(systemTestTimer);
  if (running && $("system-test-dialog").open) systemTestTimer = setTimeout(pollSystemTests, 1000);
}
async function pollSystemTests() {
  try { renderSystemTests(await api("/api/system-tests/status")); }
  catch (error) { $("system-test-status").textContent = "Could not read test status: " + error.message; }
}
$("system-test-button").onclick = () => { $("system-test-dialog").showModal(); pollSystemTests(); };
$("system-test-close").onclick = () => $("system-test-dialog").close();
$("system-test-dialog").addEventListener("close", () => clearTimeout(systemTestTimer));
$("system-test-mode").onchange = () => {
  const cloud = $("system-test-mode").value === "cloud";
  $("system-test-consent-label").hidden = !cloud;
  if (!cloud) $("system-test-consent").checked = false;
};
$("system-test-start").onclick = async () => {
  $("system-test-start").disabled = true;
  try {
    renderSystemTests(await api("/api/system-tests/start", {
      mode: $("system-test-mode").value, project_id: current?.id || null,
      cloud_consent: $("system-test-consent").checked,
    }));
  } catch (error) { $("system-test-status").textContent = error.message; $("system-test-start").disabled = false; }
};
$("system-test-stop").onclick = async () => {
  try { renderSystemTests(await api("/api/system-tests/stop", {})); }
  catch (error) { $("system-test-status").textContent = error.message; }
};
