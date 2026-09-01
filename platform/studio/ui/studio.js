/* Course Studio — the whole client.

   Three screens, chosen by state rather than by routing: the course library, the new-course
   brief, and a running job. A job screen is driven entirely by the server's event stream, so
   reloading the page mid-generation reattaches instead of losing the run — the stream replays
   from the last event index the client saw. */

const $ = s => document.querySelector(s);
const esc = s => String(s == null ? "" : s).replace(/[&<>"]/g, c =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

let STATE = { courses: [], claude: { available: false }, jobs: [] };
let screen = { name: "library" };
let stream = null;

/* ---------- plumbing ---------- */

async function api(path, body) {
  const res = await fetch(path, body === undefined ? {} : {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
  const data = await res.json().catch(() => ({ error: "The server sent something unreadable." }));
  if (!res.ok) throw new Error(data.error || ("Request failed (" + res.status + ")"));
  return data;
}

function toast(message) {
  const el = $("#toast");
  el.textContent = message;
  el.classList.add("show");
  clearTimeout(toast.t);
  toast.t = setTimeout(() => el.classList.remove("show"), 2600);
}

function clock(ts) {
  const d = new Date((ts || 0) * 1000);
  return String(d.getHours()).padStart(2, "0") + ":" + String(d.getMinutes()).padStart(2, "0")
    + ":" + String(d.getSeconds()).padStart(2, "0");
}

function ago(ts) {
  const mins = Math.round((Date.now() / 1000 - (ts || 0)) / 60);
  if (mins < 1) return "just now";
  if (mins < 60) return mins + " min ago";
  const hours = Math.round(mins / 60);
  if (hours < 24) return hours + "h ago";
  return Math.round(hours / 24) + "d ago";
}

async function refresh() {
  STATE = await api("/api/state");
  $("#rootpath").textContent = STATE.root || "";
  const pill = $("#claudestate");
  pill.textContent = STATE.claude.available ? "Claude Code connected" : "Claude Code not found";
  pill.className = "pill " + (STATE.claude.available ? "on" : "off");
  return STATE;
}

/* ---------- theme ---------- */

function cycleTheme() {
  const now = document.documentElement.getAttribute("data-theme");
  const next = now === "dark" ? "light" : now === "light" ? "" : "dark";
  if (next) document.documentElement.setAttribute("data-theme", next);
  else document.documentElement.removeAttribute("data-theme");
  try { localStorage.setItem("studio_theme", next); } catch (e) { /* private mode */ }
}
try {
  const saved = localStorage.getItem("studio_theme");
  if (saved) document.documentElement.setAttribute("data-theme", saved);
} catch (e) { /* private mode */ }

/* ---------- library ---------- */

function viewLibrary() {
  const rows = STATE.courses.map(c => {
    const status = c.error
      ? `<span class="pill off">broken</span>`
      : c.job
        ? `<span class="pill">${esc(c.job.status)}</span>`
        : c.built
          ? `<span class="pill on">built ${esc(ago(c.builtAt))}</span>`
          : `<span class="pill">not built</span>`;
    const open = c.built
      ? `<a class="btn sm ghost" href="/course/${encodeURIComponent(c.id)}/${encodeURIComponent(c.localFile)}" target="_blank" rel="noopener">Open ↗</a>`
      : "";
    const resume = c.job && c.job.status !== "done"
      ? `<button class="btn sm" onclick="watch('${c.job.id}')">View job</button>` : "";
    return `<div class="courserow">
      <div class="meta">
        <h3>${esc(c.title)}</h3>
        <p class="sub">${esc(c.id)} · ${c.modules} module${c.modules === 1 ? "" : "s"}${c.hours ? " · " + esc(c.hours) + "h" : ""}${c.error ? " · " + esc(c.error) : ""}</p>
      </div>
      ${status}
      <div class="actions">
        ${resume}
        <button class="btn sm ghost" onclick="checkCourse('${c.id}')">Check</button>
        <button class="btn sm ghost" onclick="buildCourse('${c.id}')">Build</button>
        ${open}
      </div>
    </div>
    <div id="out-${c.id}"></div>`;
  }).join("");

  $("#view").innerHTML = `
    <h2 class="big">Your courses</h2>
    <p class="sub">Each one is a folder of markdown under <span class="mono">courses/</span>, built into a single page you can study offline.</p>
    ${rows || `<div class="card"><p class="sub" style="margin:0">No courses yet. Write your first one below.</p></div>`}
    <div style="margin-top:26px">
      <button class="btn" onclick="go('new')" ${STATE.claude.available ? "" : "disabled"}>+ New course</button>
      ${STATE.claude.available ? "" : `<p class="sub" style="margin-top:10px">Generation needs the <span class="mono">claude</span> command on your PATH. Install Claude Code, or write a course by hand and use Check and Build above.</p>`}
    </div>`;
}

async function checkCourse(id) {
  const out = $("#out-" + id);
  out.innerHTML = `<p class="sub">Checking…</p>`;
  try {
    const { problems } = await api(`/api/courses/${encodeURIComponent(id)}/check`, {});
    out.innerHTML = problems.length
      ? `<div class="problems"><b>${problems.length} problem${problems.length === 1 ? "" : "s"}</b><ul>${problems.map(p => `<li>${esc(p)}</li>`).join("")}</ul></div>`
      : `<p class="sub" style="color:var(--ok)">Consistent — ready to build.</p>`;
  } catch (err) { out.innerHTML = `<div class="problems">${esc(err.message)}</div>`; }
}

async function buildCourse(id) {
  const out = $("#out-" + id);
  out.innerHTML = `<p class="sub">Building…</p>`;
  try {
    const data = await api(`/api/courses/${encodeURIComponent(id)}/build`, {});
    if (!data.built) {
      out.innerHTML = `<div class="problems"><b>Not built — fix these first</b><ul>${data.problems.map(p => `<li>${esc(p)}</li>`).join("")}</ul></div>`;
      return;
    }
    const r = data.result;
    out.innerHTML = `<p class="sub" style="color:var(--ok)">Built: ${r.modules} modules · ${r.sections} sections · ${r.quiz} quiz items · ${r.cards} cards · ${r.kb} KB</p>`;
    toast("Built " + id);
    await refresh(); render();
  } catch (err) { out.innerHTML = `<div class="problems">${esc(err.message)}</div>`; }
}

/* ---------- new course ---------- */

function viewNew() {
  $("#view").innerHTML = `
    <h2 class="big">New course</h2>
    <p class="sub">Claude will design the curriculum first and show it to you. Nothing is written until you approve it.</p>
    <div class="card">
      <div class="row">
        <div class="field">
          <label for="f-theme">Theme</label>
          <input type="text" id="f-theme" placeholder="negotiation" autocomplete="off">
        </div>
        <div class="field">
          <label for="f-hours">Hours</label>
          <input type="number" id="f-hours" value="20" min="3" max="200" step="1">
        </div>
        <div class="field">
          <label for="f-practitioner">Practitioner <span class="hint">what one is called</span></label>
          <input type="text" id="f-practitioner" placeholder="negotiator" autocomplete="off">
        </div>
      </div>
      <div class="field">
        <label for="f-audience">Who is studying</label>
        <input type="text" id="f-audience" value="a complete beginner" autocomplete="off">
      </div>
      <div class="field">
        <label for="f-notes">Anything else it should cover or avoid <span class="hint">optional</span></label>
        <textarea id="f-notes" placeholder="Weighted toward salary and contract talks. Skip hostage-negotiation material."></textarea>
      </div>
      <div class="actions" style="margin-top:6px">
        <button class="btn" id="planbtn">Plan the course →</button>
        <button class="btn ghost" onclick="go('library')">Cancel</button>
      </div>
      <p class="sub" style="margin:14px 0 0;font-size:13px">A 20-hour course is about 20 modules. Writing them all takes a while — the progress view shows each one as it lands, and you can stop at any point.</p>
    </div>`;
  $("#f-theme").focus();
  $("#planbtn").onclick = startGeneration;
}

async function startGeneration() {
  const theme = $("#f-theme").value.trim();
  if (!theme) { toast("Give it a theme first"); $("#f-theme").focus(); return; }
  const btn = $("#planbtn");
  btn.disabled = true;
  btn.textContent = "Designing the curriculum…";
  try {
    const { job } = await api("/api/generate", {
      theme,
      hours: Number($("#f-hours").value) || 20,
      practitioner: $("#f-practitioner").value.trim(),
      audience: $("#f-audience").value.trim(),
      notes: $("#f-notes").value.trim()
    });
    watch(job.id);
  } catch (err) {
    toast(err.message);
    btn.disabled = false;
    btn.textContent = "Plan the course →";
  }
}

/* ---------- a running job ---------- */

function watch(jobId) {
  screen = { name: "job", jobId, events: [], plan: null, awaiting: null,
             progress: { done: 0, total: 0, label: "" }, status: "running", result: null };
  render();
  connect(jobId, 0);
}

function connect(jobId, from) {
  if (stream) stream.close();
  stream = new EventSource(`/api/jobs/${encodeURIComponent(jobId)}/events?from=${from}`);
  stream.onmessage = ev => {
    let event;
    try { event = JSON.parse(ev.data); } catch (e) { return; }
    absorb(event);
    paintJob();
  };
  stream.onerror = () => {
    stream.close();
    // The server closes the stream when the job ends; only reconnect if it has not.
    if (screen.name === "job" && !["done", "failed", "cancelled"].includes(screen.status)) {
      setTimeout(() => connect(jobId, screen.events.length ? screen.events[screen.events.length - 1].i + 1 : 0), 1200);
    }
  };
}

function absorb(event) {
  screen.events.push(event);
  if (event.kind === "progress") screen.progress = { done: event.done, total: event.total, label: event.label };
  if (event.kind === "plan") screen.plan = event.plan;
  if (event.kind === "await") { screen.awaiting = event; screen.status = "waiting"; }
  if (event.kind === "resumed") { screen.awaiting = null; screen.status = "running"; }
  if (event.kind === "end") {
    screen.status = event.status;
    refresh().then(() => { if (screen.name === "job") paintJob(); });
  }
  if (event.kind === "done") screen.result = event.result;
}

function stepLine(e) {
  if (e.kind === "log") return { text: e.message };
  if (e.kind === "module") return { text: `${e.id} written — ${e.sections} sections, ${e.words} words`, cls: "ok" };
  if (e.kind === "studydata") return { text: `${e.id} study data — ${e.quiz} quiz, ${e.cards} cards, ${e.sections} question sets`, cls: "ok" };
  if (e.kind === "worksheet") return { text: `Worksheet: ${e.name}`, cls: "ok" };
  if (e.kind === "plan") return { text: `Curriculum proposed — ${e.plan.modules.length} modules` };
  if (e.kind === "await") return { text: "Waiting for you to approve the curriculum" };
  if (e.kind === "built") return { text: `Built — ${e.modules} modules, ${e.sections} sections, ${e.kb} KB`, cls: "ok" };
  if (e.kind === "failed") return { text: e.error, cls: "bad" };
  if (e.kind === "cancelled") return { text: "Stopped.", cls: "bad" };
  if (e.kind === "progress") return null;   // shown by the bar, not the log
  return null;
}

function viewJob() { paintJob(true); }

function paintJob(full) {
  if (screen.name !== "job") return;
  if (full || !$("#jobwrap")) {
    $("#view").innerHTML = `<div id="jobwrap"></div>`;
  }
  const p = screen.progress;
  const pct = p.total ? Math.round(p.done / p.total * 100) : 0;
  const finished = ["done", "failed", "cancelled"].includes(screen.status);

  // Keep each line paired with its own event: stepLine() drops some events, so the
  // filtered index no longer lines up with screen.events.
  const lines = screen.events
    .map(e => { const l = stepLine(e); return l && Object.assign({ at: e.at }, l); })
    .filter(Boolean).slice(-200);
  const log = lines.map(l =>
    `<div class="step ${l.cls || ""}"><span class="when">${esc(clock(l.at))}</span><span class="what">${esc(l.text)}</span></div>`).join("");

  let head;
  if (screen.status === "waiting" && screen.awaiting) head = reviewPlanHTML();
  else if (screen.status === "done") head = doneHTML();
  else if (finished) head = `<div class="card"><h3>${screen.status === "cancelled" ? "Stopped" : "It did not finish"}</h3>
      <p class="sub" style="margin:6px 0 0">${esc(lines.filter(l => l.cls === "bad").map(l => l.text).join(" ") || "")}</p>
      <p class="sub" style="margin:10px 0 0">Anything written before this point is still on disk under <span class="mono">courses/</span>.</p>
      <div class="actions"><button class="btn ghost" onclick="go('library')">Back to courses</button></div></div>`;
  else head = `<div class="card">
      <p class="eyebrow">${esc(screen.status)}</p>
      <h3>${esc(p.label || "Working…")}</h3>
      <div class="bar-track"><div class="bar-fill" style="width:${pct}%"></div></div>
      <p class="sub" style="margin:0;font-size:13px">${p.total ? `step ${p.done} of ${p.total}` : "starting"}</p>
      <div class="actions" style="margin-top:12px"><button class="btn danger sm" onclick="cancelJob()">Stop</button></div>
    </div>`;

  $("#jobwrap").innerHTML = head + `<div class="card"><p class="eyebrow">Activity</p><div class="steps" id="steps">${log}</div></div>`;
  const box = $("#steps");
  if (box) box.scrollTop = box.scrollHeight;
}

function doneHTML() {
  const r = screen.result || {};
  const id = r.course || "";
  const open = r.local
    ? `<a class="btn" href="/course/${encodeURIComponent(id)}/${encodeURIComponent(r.local.split(/[\\/]/).pop())}" target="_blank" rel="noopener">Open the course ↗</a>`
    : "";
  return `<div class="card">
    <p class="eyebrow" style="color:var(--ok)">Finished</p>
    <h3>${esc(id)} is built</h3>
    <p class="sub" style="margin:4px 0 0">${r.modules} modules · ${r.sections} sections · ${r.quiz} quiz items · ${r.cards} flashcards · ${r.glossary} glossary terms · ${r.kb} KB</p>
    <div class="actions" style="margin-top:14px">${open}<button class="btn ghost" onclick="go('library')">Back to courses</button></div>
    <p class="sub" style="margin:14px 0 0;font-size:13px">The tutor sidebar needs the copy opened straight off disk — <span class="mono">dist/${esc(id)}/</span> — because a served page is not allowed to call Anthropic.</p>
  </div>`;
}

/* ---------- the approval gate ---------- */

function reviewPlanHTML() {
  const plan = screen.plan || {};
  const parts = (plan.parts || []).map((part, pi) => {
    const mods = (plan.modules || []).filter(m => m.part === part.id).map(m => `
      <div class="mod" data-id="${esc(m.id)}">
        <span class="mid">${esc(m.id)}</span>
        <input class="mtitle" type="text" value="${esc(m.title)}" aria-label="Module title">
        <input class="mmin" type="number" value="${m.minutes}" min="15" step="15" aria-label="Minutes">
        <button class="drop" title="Remove this module" onclick="dropModule('${esc(m.id)}')">×</button>
      </div>`).join("");
    return `<div class="part" data-part="${esc(part.id)}">
      <div class="parthead">
        <input class="pname" type="text" value="${esc(part.name)}" aria-label="Part name">
        <input class="phours" type="number" value="${part.hours}" min="0" step="1" aria-label="Hours">
        <span class="tag">hours</span>
      </div>${mods}</div>`;
  }).join("");

  const total = (plan.modules || []).length;
  return `<div class="card">
    <p class="eyebrow">Review before it writes anything</p>
    <h3 style="font-size:24px">${esc(plan.title || "")}</h3>
    <p class="sub" style="margin:2px 0 16px">${esc(plan.tagline || "")}</p>
    <div class="note">Edit titles, minutes and part names in place, or drop modules you do not want. Writing ${total} modules takes a while, so it is worth a minute here.</div>
    <div style="margin-top:16px">${parts}</div>
    <div class="actions" style="margin-top:16px">
      <button class="btn" onclick="approvePlan()">Write all ${total} modules →</button>
      <button class="btn danger" onclick="cancelJob()">Stop</button>
    </div>
  </div>`;
}

function dropModule(id) {
  screen.plan.modules = screen.plan.modules.filter(m => m.id !== id);
  paintJob(true);
}

function harvestPlan() {
  const plan = JSON.parse(JSON.stringify(screen.plan));
  document.querySelectorAll(".part").forEach(el => {
    const part = plan.parts.find(p => p.id === el.dataset.part);
    if (!part) return;
    part.name = el.querySelector(".pname").value.trim() || part.name;
    part.hours = Number(el.querySelector(".phours").value) || part.hours;
  });
  document.querySelectorAll(".mod").forEach(el => {
    const mod = plan.modules.find(m => m.id === el.dataset.id);
    if (!mod) return;
    mod.title = el.querySelector(".mtitle").value.trim() || mod.title;
    mod.minutes = Number(el.querySelector(".mmin").value) || mod.minutes;
  });
  return plan;
}

async function approvePlan() {
  const plan = harvestPlan();
  if (!plan.modules.length) { toast("There are no modules left to write"); return; }
  try {
    await api(`/api/jobs/${encodeURIComponent(screen.jobId)}/answer`, { plan });
    screen.awaiting = null;
    screen.status = "running";
    paintJob(true);
  } catch (err) { toast(err.message); }
}

async function cancelJob() {
  try { await api(`/api/jobs/${encodeURIComponent(screen.jobId)}/cancel`, {}); toast("Stopping…"); }
  catch (err) { toast(err.message); }
}

/* ---------- routing ---------- */

function go(name) {
  if (stream) { stream.close(); stream = null; }
  screen = { name };
  refresh().then(render);
}

function render() {
  if (screen.name === "new") return viewNew();
  if (screen.name === "job") return viewJob();
  return viewLibrary();
}

$("#themebtn").onclick = cycleTheme;

refresh().then(() => {
  // Reattach to a run that is still going, so closing the tab is not the same as stopping.
  const live = (STATE.jobs || []).find(j => !["done", "failed", "cancelled"].includes(j.status));
  if (live) watch(live.id); else render();
}).catch(err => {
  $("#view").innerHTML = `<div class="card"><h3>Cannot reach the Studio server</h3><p class="sub">${esc(err.message)}</p></div>`;
});
