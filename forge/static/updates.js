"use strict";
// Update UI is independent of project rendering; it survives changing projects.
let updateTimer = null;
let reconnectTimer = null;
let updateInstalling = false;
let reconnectAttempts = 0;
let originalBoot = null;

function renderUpdate(state) {
  $("update-status").textContent = state.message;
  $("update-notes").hidden = !state.release?.notes;
  $("update-notes").textContent = state.release?.notes || "";
  const busy = ["checking", "installing", "restarting"].includes(state.status);
  $("check-update").disabled = busy;
  $("install-update").hidden = state.status !== "available";
  $("install-update").disabled = busy || !state.supervised;
  $("close-update").disabled = busy;
  $("update-history").textContent = state.last_result?.message || "";
  if (state.status === "available" && !state.supervised) {
    $("update-history").textContent =
      "Restart Foundry using Start-Foundry.bat to enable managed updates.";
  }
  if (state.status === "installing" || state.status === "restarting") {
    updateInstalling = true;
    $("update-button").textContent = "↻ Updating…";
  }
  if (state.status === "restarting") reconnect();
  if (state.status === "error" || state.status === "current") {
    updateInstalling = false;
    $("update-button").textContent = "↻ Update";
  }
}

function reconnect() {
  clearInterval(updateTimer);
  updateTimer = null;
  if (reconnectTimer) return;
  $("update-status").textContent =
    "Restarting Foundry. Keep this page and the terminal open…";
  reconnectTimer = setInterval(async () => {
    reconnectAttempts++;
    try {
      const response = await fetch("/health", { cache: "no-store" });
      const health = await response.json();
      if (
        health.status === "ok" &&
        originalBoot !== null &&
        health.boot !== originalBoot
      ) {
        // New server has a different session token. Reload to receive it.
        location.reload();
        return;
      }
    } catch (_) {
      /* The server is intentionally offline during restart. */
    }
    if (reconnectAttempts >= 60) {
      clearInterval(reconnectTimer);
      reconnectTimer = null;
      $("update-status").textContent =
        "Restart is taking longer than expected. Check the Foundry terminal, then refresh this page. Your original program folder remains available.";
      $("close-update").disabled = false;
    }
  }, 1000);
}

async function pollUpdate() {
  try {
    renderUpdate(await api("/api/updates"));
  } catch (error) {
    if (updateInstalling) reconnect();
    else notice(error.message);
  }
}

$("update-button").onclick = handle(async () => {
  $("update-dialog").showModal();
  const info = await api("/api/info");
  originalBoot = (await (await fetch("/health", { cache: "no-store" })).json())
    .boot;
  $("update-current").textContent =
    "Installed version " + info.version + " · MeetleJuice/repos";
  await pollUpdate();
  if (!updateTimer) updateTimer = setInterval(pollUpdate, 1200);
});
$("close-update").onclick = () => {
  $("update-dialog").close();
  clearInterval(updateTimer);
  updateTimer = null;
};
$("update-dialog").addEventListener("cancel", (event) => {
  if (updateInstalling) event.preventDefault();
  else {
    clearInterval(updateTimer);
    updateTimer = null;
  }
});
$("check-update").onclick = handle(async () => {
  $("check-update").disabled = true;
  $("update-status").textContent = "Checking published releases…";
  try {
    renderUpdate(await api("/api/updates/check", {}));
  } finally {
    $("check-update").disabled = false;
  }
});
$("install-update").onclick = handle(async () => {
  $("install-update").disabled = true;
  updateInstalling = true;
  try {
    renderUpdate(await api("/api/updates/install", {}));
  } catch (error) {
    updateInstalling = false;
    $("install-update").disabled = false;
    throw error;
  }
});

api("/api/updates")
  .then((state) => {
    if (!state.last_result) return;
    const key = JSON.stringify(state.last_result);
    if (localStorage.getItem("foundry-last-update") !== key) {
      notice(state.last_result.message);
      localStorage.setItem("foundry-last-update", key);
    }
  })
  .catch(() => {});
