"use strict";
// Presentation preferences stay in this browser. No credentials or project source.
const studioDefaults = {accent: "cyan", sounds: false, volume: 25};
let studioPreferences = {...studioDefaults};
try {
  const saved = JSON.parse(localStorage.getItem("foundry-studio-v1") || "null");
  if (saved && typeof saved === "object") {
    if (["cyan", "violet", "mint"].includes(saved.accent)) studioPreferences.accent = saved.accent;
    if (typeof saved.sounds === "boolean") studioPreferences.sounds = saved.sounds;
    if (Number.isFinite(saved.volume)) studioPreferences.volume = Math.min(100, Math.max(0, saved.volume));
  }
} catch (_) { /* A blocked or damaged browser preference must not block Foundry. */ }
let studioAudio = null;
let studioRouteSignature = "";
const studioObservedJobs = new Map();
function saveStudioPreferences() {
  try { localStorage.setItem("foundry-studio-v1", JSON.stringify(studioPreferences)); } catch (_) {}
  renderStudioPreferences();
}
function renderStudioPreferences() {
  document.documentElement.dataset.studioAccent = studioPreferences.accent;
  $("studio-accent").value = studioPreferences.accent;
  $("studio-sounds").checked = studioPreferences.sounds;
  $("studio-volume").value = studioPreferences.volume;
  $("sound-toggle").textContent = studioPreferences.sounds ? "Sound on" : "Sound off";
  $("sound-toggle").setAttribute("aria-pressed", String(studioPreferences.sounds));
  $("studio-sound-status").textContent = studioPreferences.sounds
    ? "Sounds enabled for observed job transitions. Browser playback needs a click after opening a new tab."
    : "Sounds are off. No downloads, microphone, or cloud connection.";
}
async function unlockStudioAudio() {
  if (!studioPreferences.sounds) return false;
  const Audio = window.AudioContext || window.webkitAudioContext;
  if (!Audio) {
    $("studio-sound-status").textContent = "Sound is unavailable in this browser. Visual job status still works.";
    return false;
  }
  try {
    if (!studioAudio || studioAudio.state === "closed") studioAudio = new Audio();
    if (studioAudio.state === "suspended") await studioAudio.resume();
    return studioAudio.state === "running";
  } catch (_) {
    $("studio-sound-status").textContent = "Playback was blocked. Use Try sound to enable it; visual job status still works.";
    return false;
  }
}
function playStudioCue(kind = "complete") {
  // No autoplay/resume attempt from polling. A user gesture must unlock audio first.
  if (!studioPreferences.sounds || !studioAudio || studioAudio.state !== "running" || studioPreferences.volume === 0) return false;
  try {
    const notes = kind === "attention" ? [392, 330] : [523.25, 659.25];
    for (const [i, frequency] of notes.entries()) {
      const oscillator = studioAudio.createOscillator(), gain = studioAudio.createGain();
      const start = studioAudio.currentTime + i * 0.12;
      oscillator.type = "sine";
      oscillator.frequency.value = frequency;
      gain.gain.setValueAtTime(0, start);
      gain.gain.linearRampToValueAtTime(studioPreferences.volume / 100 * 0.12, start + 0.015);
      gain.gain.exponentialRampToValueAtTime(0.0001, start + 0.17);
      oscillator.connect(gain); gain.connect(studioAudio.destination);
      oscillator.onended = () => {oscillator.disconnect(); gain.disconnect();};
      oscillator.start(start); oscillator.stop(start + 0.18);
    }
    return true;
  } catch (_) { return false; }
}
function observeStudioJob(project) {
  const previous = studioObservedJobs.get(project.id);
  studioObservedJobs.set(project.id, project.status);
  // Opening old history is silent; polling a terminal state twice is silent.
  if (previous && activeStatuses.has(previous) && !activeStatuses.has(project.status))
    playStudioCue(["error", "interrupted", "stopped"].includes(project.status) ? "attention" : "complete");
  if (studioObservedJobs.size > 100) studioObservedJobs.delete(studioObservedJobs.keys().next().value);
}
function studioRouteCard(title, profile) {
  const card = document.createElement("article");
  card.className = "studio-route-card";
  const heading = document.createElement("h4"); heading.textContent = title; card.append(heading);
  for (const [role, label] of [["planner", "Plans your idea"], ["coder", "Builds & repairs"]]) {
    const line = document.createElement("div"), name = document.createElement("strong"), primary = document.createElement("p"), fallbacks = document.createElement("small");
    name.textContent = label;
    const config = profile[role];
    primary.textContent = config?.model ? `${config.provider === "ollama" ? "This PC" : config.provider} · ${config.model}` : "Choose a model";
    const alternatives = config?.fallbacks || (config?.fallback ? [config.fallback] : []);
    fallbacks.textContent = alternatives.length ? "Then: " + alternatives.map(c => `${c.provider === "ollama" ? "This PC" : c.provider} / ${c.model}`).join(" → ") : "No fallback configured";
    line.append(name, primary, fallbacks); card.append(line);
  }
  return card;
}
function refreshStudio() {
  const defaults = selectedModels(), profile = current || defaults;
  const localOnly = !cloudModel(profile.planner) && !cloudModel(profile.coder);
  $("studio-route-title").textContent = localOnly ? "Local-only workspace" : "Cloud-enabled routing";
  $("studio-route-note").textContent = (current ? "Open project: " + current.title + ". " : "New project defaults. ") +
    (localOnly ? "No cloud fallback configured. Local context limits still apply." : "Cloud use needs consent. Provider catalogues do not prove remaining quota.");
  $("studio-scope").textContent = "New projects use the saved defaults below. Existing projects keep their own routes until you apply a change.";
  const signature = JSON.stringify([defaults, current?.id, current?.title, current?.planner, current?.coder]);
  if (signature !== studioRouteSignature) {
    studioRouteSignature = signature;
    $("studio-route-cards").replaceChildren(studioRouteCard("New projects", defaults));
    if (current) $("studio-route-cards").append(studioRouteCard("This project · " + current.title, current));
  }
  const hasLocal = (lastConnectionInfo?.providers?.ollama?.models || []).some(m => !/embed|vision|vl:/i.test(m));
  $("studio-route-warning").textContent = lastConnectionInfo && !hasLocal
    ? "For local-only work, start Ollama with an installed text/chat or coding model, then Check again."
    : localOnly ? "Local-only automatic setup chooses up to two installed models per role, tried in sequence. Installed does not prove model capacity or GPU fit." : !cloudModel(profile.coder) ? "Planning can use cloud providers; coding has no cloud fallback. Local model preference is not a measured quality ranking. Cloud consent and execution approval stay separate." : "Out of cloud quota? Just this computer applies a local-only route to new projects and the open idle project.";
}
$("studio-settings").onclick = () => $("connections-button").click();
$("studio-local").onclick = cloudHandle(async () => {$("connections").showModal(); await setupAutomaticModels("local_only");});
$("preset-local").onclick = cloudHandle(() => setupAutomaticModels("local_only"));
$("preset-hybrid").onclick = cloudHandle(() => setupAutomaticModels("hybrid"));
$("preset-orchestrated").onclick = cloudHandle(() => setupAutomaticModels("orchestrated"));
$("studio-accent").onchange = () => {studioPreferences.accent = $("studio-accent").value; saveStudioPreferences();};
async function setStudioSounds(enabled) {
  studioPreferences.sounds = enabled; saveStudioPreferences();
  if (enabled) {await unlockStudioAudio(); playStudioCue();}
  else if (studioAudio?.state === "running") {try {await studioAudio.suspend();} catch (_) {}}
}
$("sound-toggle").onclick = () => setStudioSounds(!studioPreferences.sounds);
$("studio-sounds").onchange = () => setStudioSounds($("studio-sounds").checked);
$("studio-volume").oninput = () => {studioPreferences.volume = Number($("studio-volume").value); saveStudioPreferences();};
$("studio-sound-test").onclick = async () => {
  if (!studioPreferences.sounds) {$("studio-sound-status").textContent = "Enable sounds first; volume and mute are always yours to control."; return;}
  await unlockStudioAudio(); playStudioCue();
};
document.addEventListener("pointerdown", () => {if (studioPreferences.sounds && studioAudio?.state !== "running") void unlockStudioAudio();});
renderStudioPreferences();
refreshStudio();
