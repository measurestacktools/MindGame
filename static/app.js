const $ = (id) => document.getElementById(id);
const TOTAL = 6;
let scenarios = [];
let current = 0;
let lastResult = null;

async function refreshStatus() {
  try {
    const r = await fetch("/api/status");
    const j = await r.json();
    const badge = $("keyBadge");
    if (j.has_key) { badge.textContent = "Key ✓ (" + j.source + ")"; badge.className = "badge on"; $("homeHint").textContent = "Key ready. Tap Start Game!"; }
    else { badge.textContent = "No key"; badge.className = "badge off"; $("homeHint").textContent = "Add your Groq key in Settings to play with live AI."; }
  } catch { /* offline */ }
}
function show(id) { $(id).classList.remove("hidden"); }
function hide(id) { $(id).classList.add("hidden"); }
function setLoading(on, text) {
  $("loading").classList.toggle("hidden", !on);
  if (text) $("loadingText").textContent = text;
}
function err(el, msg) { const e = $(el); if (!msg) { e.classList.add("hidden"); e.textContent = ""; } else { e.textContent = msg; e.classList.remove("hidden"); } }

function showScreen(name) {
  ["homeScreen", "gameScreen", "revealScreen", "resultScreen"].forEach((s) => hide(s));
  show(name);
}

function renderQuestion() {
  const sc = scenarios[current];
  $("qLabel").textContent = `Q${current + 1}/${TOTAL}`;
  $("pctLabel").textContent = Math.round((current / TOTAL) * 100) + "%";
  $("progressBar").style.width = (current / TOTAL) * 100 + "%";
  $("scenarioText").textContent = sc.scenario;
  // re-trigger animation
  $("scenarioText").style.animation = "none"; void $("scenarioText").offsetWidth;
  $("scenarioText").style.animation = "";
  const grid = $("choicesGrid"); grid.innerHTML = "";
  const keys = ["A", "B", "C", "D"];
  sc.choices.forEach((c, i) => {
    const b = document.createElement("button");
    b.className = "choice";
    b.innerHTML = `<span class="k">${keys[i]}</span><br/>${escapeHtml(c)}`;
    b.onclick = () => pick(i);
    grid.appendChild(b);
  });
}
function escapeHtml(s) { return String(s).replace(/[&<>"']/g, (m) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[m])); }

async function startGame() {
  err("gameError", ""); setLoading(true, "Summoning scenarios…");
  try {
    const r = await fetch("/api/start", { method: "POST" });
    const j = await r.json();
    if (!r.ok) { showScreen("homeScreen"); setLoading(false); alert(j.error || "Could not start. Try again."); return; }
    scenarios = j.scenarios; current = 0;
    setLoading(false); showScreen("gameScreen"); renderQuestion();
  } catch { setLoading(false); alert("Could not reach the server. Is it running?"); }
}

async function pick(i) {
  err("gameError", "");
  // optimistic lock: disable cards
  document.querySelectorAll(".choice").forEach((b) => (b.disabled = true));
  try {
    const r = await fetch("/api/choice", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ index: i }) });
    const j = await r.json();
    if (!r.ok) { err("gameError", j.error || "Invalid pick."); return; }
    current++;
    $("progressBar").style.width = (j.recorded / TOTAL) * 100 + "%";
    $("pctLabel").textContent = Math.round((j.recorded / TOTAL) * 100) + "%";
    if (j.done) { showScreen("revealScreen"); }
    else { renderQuestion(); }
  } catch { err("gameError", "Network hiccup — tap a card again."); document.querySelectorAll(".choice").forEach((b) => (b.disabled = false)); }
}

async function reveal() {
  err("revealError", ""); setLoading(true, "Reading your mind…");
  try {
    const r = await fetch("/api/reveal", { method: "POST" });
    const j = await r.json();
    if (!r.ok) { setLoading(false); err("revealError", j.error || "Reveal failed."); return; }
    lastResult = j; setLoading(false); renderResult(j); showScreen("resultScreen");
    window.scrollTo({ top: 0, behavior: "smooth" });
  } catch { setLoading(false); err("revealError", "Network hiccup — try Reveal again."); }
}

function renderResult(j) {
  $("rArchetype").textContent = j.archetype || "Mystery Mind";
  $("rTitle").textContent = j.title || "";
  $("rDesc").textContent = j.character_description || "";
  $("rStrengths").innerHTML = (j.strengths || []).map((s) => `<li>${escapeHtml(s)}</li>`).join("");
  $("rWeak").innerHTML = (j.fun_weaknesses || []).map((s) => `<li>${escapeHtml(s)}</li>`).join("");
  $("rDecision").textContent = j.decision_style || "";
  $("rProblem").textContent = j.problem_solving || "";
  $("rComm").textContent = j.communication || "";
  $("rTraits").innerHTML = (j.signature_traits || []).map((s) => `<span class="pill">${escapeHtml(s)}</span>`).join("");
}

function resultText() {
  if (!lastResult) return "";
  const j = lastResult;
  return `🧠 My MindGame Archetype: ${j.archetype}\n${j.title}\n\n${j.character_description}\n\n💪 Strengths: ${(j.strengths || []).join(", ")}\n😅 Fun weaknesses: ${(j.fun_weaknesses || []).join(", ")}\n🧭 Decision style: ${j.decision_style}\n🧩 Problem solving: ${j.problem_solving}\n💬 Communication: ${j.communication}\n🌟 Traits: ${(j.signature_traits || []).join(", ")}\n\n🎪 MindGame — just for fun, not psychology.`;
}

$("startBtn").onclick = startGame;
$("revealBtn").onclick = reveal;
$("howBtn").onclick = () => $("howBox").classList.toggle("hidden");
$("againBtn").onclick = () => { showScreen("homeScreen"); lastResult = null; refreshStatus(); };
$("copyBtn").onclick = async () => {
  try { await navigator.clipboard.writeText(resultText()); $("copyMsg").classList.remove("hidden"); setTimeout(() => $("copyMsg").classList.add("hidden"), 2000); }
  catch { alert("Copy blocked by browser — select the text manually."); }
};
// Settings modal — frontend NEVER stores or sends keys except posting to /api/key for verification.
$("settingsBtn").onclick = () => { show("settingsModal"); $("keyError").classList.add("hidden"); $("keyOk").classList.add("hidden"); };
$("closeSettingsBtn").onclick = () => hide("settingsModal");
$("saveKeyBtn").onclick = async () => {
  const v = $("keyInput").value.trim();
  $("keyError").classList.add("hidden"); $("keyOk").classList.add("hidden");
  if (!v) { const e = $("keyError"); e.textContent = "Paste a key first."; e.classList.remove("hidden"); return; }
  try {
    const r = await fetch("/api/key", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ key: v }) });
    const j = await r.json();
    if (!r.ok) { const e = $("keyError"); e.textContent = j.error || "Key rejected."; e.classList.remove("hidden"); return; }
    $("keyInput").value = ""; // never keep key in the page
    const o = $("keyOk"); o.textContent = "Key verified & saved in server memory ✓"; o.classList.remove("hidden");
    refreshStatus(); setTimeout(() => hide("settingsModal"), 900);
  } catch { const e = $("keyError"); e.textContent = "Could not reach server."; e.classList.remove("hidden"); }
};
$("clearKeyBtn").onclick = async () => {
  await fetch("/api/key", { method: "DELETE" });
  $("keyInput").value = ""; refreshStatus();
  const o = $("keyOk"); o.textContent = "Server memory cleared."; o.classList.remove("hidden");
};
refreshStatus();
