/* Course Studio — the whole client.

   Hash-routed, so every screen has an address and the back button works:

     #/                            the library: every course, with the reader's progress
     #/new                         the brief for a new course
     #/course/<id>                 one course: modules, progress, add a module, files
     #/course/<id>?tab=add&from=M07   the same page, opened from inside a course
     #/course/<id>/edit?path=...   a file of the course, in an editor
     #/job/<id>                    a running job

   A job screen is driven entirely by the server's event stream, so reloading the page
   mid-generation reattaches instead of losing the run — the stream replays from the last
   event index the client saw. */

const $ = s => document.querySelector(s);
const esc = s => String(s == null ? "" : s).replace(/[&<>"]/g, c =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

let STATE = { courses: [], claude: { available: false }, jobs: [] };
let route = { name: "library", id: null, query: {} };
let job = null;          // the job screen's state, while one is showing
let stream = null;
let courseCache = {};    // id -> detail, refreshed on every visit
const FINISHED = ["done", "failed", "cancelled"];

/* ---------- plumbing ---------- */

async function api(path, body, method) {
  const res = await fetch(path, body === undefined ? {} : {
    method: method || "POST",
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

function fmtH(mins) { const h = mins / 60; return (h % 1 === 0 ? h : h.toFixed(1)) + "h"; }

function courseUrl(c, hash) {
  return `/course/${encodeURIComponent(c.id)}/${encodeURIComponent(c.localFile)}${hash || "#/home"}`;
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

function progressLine(c) {
  const p = c.progress || {};
  if (!p.modules) return "";
  const bits = [`${p.done} of ${p.modules} modules`];
  if (p.minutes) bits.push(`${p.minutes} min studied`);
  if (p.due) bits.push(`${p.due} card${p.due === 1 ? "" : "s"} due`);
  if (p.updatedAt) bits.push("last studied " + ago(p.updatedAt / 1000));
  return bits.join(" · ");
}

function courseCard(c) {
  const p = c.progress || {};
  const pct = Math.round((p.pct || 0) * 100);
  const status = c.error
    ? `<span class="pill off">broken</span>`
    : c.job && !FINISHED.includes(c.job.status)
      ? `<span class="pill">${esc(c.job.kind)} · ${esc(c.job.status)}</span>`
      : c.built ? "" : `<span class="pill">not built</span>`;
  const primary = c.built
    ? (p.done ? `<a class="btn sm" href="${courseUrl(c, "#/m/" + (p.next || ""))}">Continue ${esc(p.next || "")} →</a>`
              : `<a class="btn sm" href="${courseUrl(c)}">Start →</a>`)
    : `<button class="btn sm" onclick="buildFromCard('${c.id}')" ${c.error ? "disabled" : ""}>Build</button>`;
  return `<div class="coursecard">
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">
      <span class="pct">${p.modules ? pct + "%" : ""}</span><span class="spacer"></span>${status}
    </div>
    <h3><a href="#/course/${encodeURIComponent(c.id)}" style="text-decoration:none;color:inherit">${esc(c.title)}</a></h3>
    <p class="tagline">${esc(c.tagline || "")}</p>
    <div class="bar-track" style="margin:0 0 8px"><div class="bar-fill" style="width:${pct}%"></div></div>
    <p class="facts">${esc(progressLine(c) || `${c.modules} module${c.modules === 1 ? "" : "s"} · ${esc(c.hours)}h`)}${c.error ? " · " + esc(c.error) : ""}</p>
    <div class="actions">
      ${primary}
      <a class="btn sm ghost" href="#/course/${encodeURIComponent(c.id)}">Manage</a>
    </div>
    <div id="out-${c.id}"></div>
  </div>`;
}

function todayStrip() {
  // Across every course: what is due and what is half-done. The "open the app and know
  // what to do" moment a learning platform owes its reader.
  const items = [];
  STATE.courses.forEach(c => {
    const p = c.progress || {};
    if (!c.built || !p.modules) return;
    if (p.due) items.push(`<a class="today" href="${courseUrl(c, "#/review")}"><b>${p.due}</b> card${p.due === 1 ? "" : "s"} due · ${esc(c.title)}</a>`);
    if (p.started) items.push(`<a class="today" href="${courseUrl(c, "#/m/" + (p.next || ""))}"><b>${esc(p.next || "")}</b> in progress · ${esc(c.title)}</a>`);
  });
  if (!items.length) return "";
  return `<div class="todaystrip"><span class="eyebrow" style="margin:0 6px 0 0">Today</span>${items.join("")}</div>`;
}

function viewLibrary() {
  const cards = STATE.courses.map(courseCard).join("");
  const newCard = `<div class="coursecard new">
    <h3>New course</h3>
    <p>Name a subject and an hour budget. Claude designs the curriculum, you approve it, then it writes every module.</p>
    <a class="btn" href="#/new" ${STATE.claude.available ? "" : 'style="pointer-events:none;opacity:.45"'}>+ Write a course</a>
    ${STATE.claude.available ? "" : `<p style="font-size:12.5px;margin-top:10px">Needs the <span class="mono">claude</span> command on this machine's PATH.</p>`}
  </div>`;
  $("#view").innerHTML = `
    <h2 class="big">Your courses</h2>
    <p class="sub">Progress is kept here when a course is opened from Studio, so you can pick up where you left off. Each course is a folder of markdown - its own repository - in the courses directory shown under Settings.</p>
    ${todayStrip()}
    <div class="cards">${cards}${newCard}</div>`;
}

async function buildFromCard(id) {
  const out = $("#out-" + id);
  out.innerHTML = `<p class="sub" style="margin:8px 0 0;font-size:13px">Building…</p>`;
  try {
    const data = await api(`/api/courses/${encodeURIComponent(id)}/build`, {});
    if (!data.built) {
      out.innerHTML = `<div class="problems"><b>Not built — ${data.problems.length} problem${data.problems.length === 1 ? "" : "s"}</b><ul>${data.problems.slice(0, 6).map(p => `<li>${esc(p)}</li>`).join("")}</ul><a href="#/course/${encodeURIComponent(id)}">Open the course page to fix them</a></div>`;
      return;
    }
    toast("Built " + id);
    await refresh(); render();
  } catch (err) { out.innerHTML = `<div class="problems">${esc(err.message)}</div>`; }
}

/* ---------- new course ---------- */

function viewNew() {
  $("#view").innerHTML = `
    <p class="crumb"><a href="#/">Courses</a> › New course</p>
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
        <a class="btn ghost" href="#/">Cancel</a>
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
    const { job: j } = await api("/api/generate", {
      theme,
      hours: Number($("#f-hours").value) || 20,
      practitioner: $("#f-practitioner").value.trim(),
      audience: $("#f-audience").value.trim(),
      notes: $("#f-notes").value.trim()
    });
    location.hash = "#/job/" + j.id;
  } catch (err) {
    toast(err.message);
    btn.disabled = false;
    btn.textContent = "Plan the course →";
  }
}

/* ---------- one course ---------- */

async function viewCourse() {
  const id = route.id;
  $("#view").innerHTML = `<p class="crumb"><a href="#/">Courses</a> › ${esc(id)}</p><p class="sub">Loading…</p>`;
  let c;
  try { c = await api(`/api/courses/${encodeURIComponent(id)}`); }
  catch (err) { $("#view").innerHTML = `<div class="card"><h3>Cannot open ${esc(id)}</h3><p class="sub">${esc(err.message)}</p></div>`; return; }
  courseCache[id] = c;
  if (route.id !== id) return;                // navigated away while loading
  paintCourse(c);
}

function paintCourse(c) {
  const p = c.progress || {};
  const pct = Math.round((p.pct || 0) * 100);
  const tab = route.query.tab || "modules";
  const live = c.job && !FINISHED.includes(c.job.status);
  const head = `
    <p class="crumb"><a href="#/">Courses</a> › ${esc(c.title)}</p>
    <div class="card"><div class="hero">
      <div>
        <h2 class="big" style="margin:0">${esc(c.title)}</h2>
        <p class="sub" style="margin:2px 0 0">${esc(c.tagline || "")}${c.audience ? " · for " + esc(c.audience) : ""}</p>
        <div class="bar-track" style="margin:14px 0 6px;max-width:520px"><div class="bar-fill" style="width:${pct}%"></div></div>
        <div class="stats">
          <div class="stat"><b>${pct}%</b><span>complete</span></div>
          <div class="stat"><b>${p.done || 0}<span style="font-size:13px;color:var(--muted)">/${c.modules}</span></b><span>modules done</span></div>
          <div class="stat"><b>${p.minutes || 0}m</b><span>studied</span></div>
          <div class="stat"><b>${p.cards || 0}</b><span>cards · ${p.due || 0} due</span></div>
          <div class="stat"><b>${esc(fmtH((c.hours || 0) * 60))}</b><span>planned</span></div>
        </div>
      </div>
      <div class="actions" style="flex-direction:column;align-items:stretch;min-width:180px">
        ${c.built
          ? `<a class="btn" href="${courseUrl(c, p.done || p.started ? "#/m/" + (p.next || "") : "#/home")}">${p.done || p.started ? "Continue at " + esc(p.next || "") : "Start the course"} →</a>
             <a class="btn ghost" href="${courseUrl(c)}">Open the course</a>`
          : `<span class="pill" style="text-align:center">not built yet</span>`}
        ${live ? `<a class="btn ghost" href="#/job/${c.job.id}">${esc(c.job.kind)} running — view</a>`
               : `${c.resumable ? `<button class="btn" style="background:var(--warm)" onclick="resumeCourse('${c.id}')">Resume the run →</button>` : ""}
                  <button class="btn ghost" onclick="checkCourse('${c.id}')">Check</button>
                  <button class="btn ghost" onclick="buildCourse('${c.id}')">${c.built ? "Rebuild" : "Build"}</button>`}
      </div>
    </div>
    <div id="courseout"></div>
    ${c.error ? `<div class="problems">${esc(c.error)}</div>` : ""}
    ${c.resumable && !live ? `<div class="note" style="margin-top:12px">This course's generation run did not finish — the saved curriculum is still here. <b>Resume the run</b> keeps every module and study-data entry already on disk and writes only what is missing, then builds. See <a href="#/settings">Settings &amp; logs</a> for why it stopped.</div>` : ""}
    ${c.built ? `<p class="sub" style="margin:12px 0 0;font-size:12.5px">Built ${esc(ago(c.builtAt))}. A rebuild keeps your progress — it lives with the platform, not the page.</p>` : ""}
    </div>
    <div class="tabs">
      ${[["modules", "Modules"], ["add", "Add a module"],
         ["questions", "Questions" + ((c.questions || []).length ? ` <span class="count">${c.questions.length}</span>` : "")],
         ["files", "Files"], ["settings", "Settings"]].map(([k, l]) =>
        `<button class="tab ${tab === k ? "active" : ""}" onclick="setTab('${k}')">${l}</button>`).join("")}
    </div>
    <div id="tabbody"></div>`;
  $("#view").innerHTML = head;
  if (tab === "add") paintAdd(c);
  else if (tab === "files") paintFiles(c);
  else if (tab === "questions") paintQuestions(c);
  else if (tab === "settings") paintSettings(c);
  else paintModules(c);
}

function setTab(tab) {
  const q = Object.assign({}, route.query, { tab });
  delete q.rewrite; delete q.from; delete q.sec; delete q.q;
  location.hash = `#/course/${encodeURIComponent(route.id)}?` + new URLSearchParams(q).toString();
}

function paintModules(c) {
  const mp = c.moduleProgress || {};
  const parts = (c.parts || []).map(part => {
    const mods = (c.moduleList || []).filter(m => m.part === part.id);
    const rows = mods.map(m => {
      const st = mp[m.id] || {};
      const dot = st.done ? "done" : (st.read || st.minutes || st.quiz) ? "part" : "";
      const state = st.done ? "completed" : st.read ? `${st.read}/${m.sections} sections read${st.quiz ? " · quiz done" : ""}` : "";
      const open = c.built ? `<a class="btn sm ghost" href="${courseUrl(c, "#/m/" + m.id)}">Read</a>` : "";
      const rewriting = route.query.rewrite === m.id;
      return `<div class="modrow" id="mod-${m.id}">
        <span class="dot ${dot}" title="${esc(state)}"></span>
        <span class="mid">${esc(m.id)}</span>
        <span class="title">${esc(m.title)}<small>${m.minutes} min · ${m.sections} sections${state ? " · " + esc(state) : ""}</small></span>
        <span class="state"></span>
        <span class="actions">${open}
          <a class="btn sm ghost" href="#/course/${encodeURIComponent(c.id)}/edit?path=${encodeURIComponent(m.path)}">Edit</a>
          <button class="btn sm ghost" onclick="toggleRewrite('${m.id}')">Rewrite…</button>
          <button class="btn sm ghost" title="Remove this module" onclick="toggleRemove('${m.id}')">×</button></span>
      </div>
      <div class="inlineform ${rewriting ? "" : "hidden"}" id="rw-${m.id}">
        <label for="rwn-${m.id}">What should change in ${esc(m.id)}?</label>
        <textarea id="rwn-${m.id}" rows="3" placeholder="Go much deeper on the worked example in Core concepts; the current version stops before the arithmetic. Keep the exercise.">${esc(route.query.rewrite === m.id && route.query.q ? route.query.q : "")}</textarea>
        <div class="actions" style="margin-top:10px">
          <button class="btn sm" onclick="rewriteModule('${c.id}','${m.id}')">Rewrite ${esc(m.id)} →</button>
          <button class="btn sm ghost" onclick="toggleRewrite('${m.id}')">Cancel</button>
          <span class="sub" style="font-size:12px;margin:0 0 0 6px">Keeps the id and position. Your progress for it stays; section ticks may shift.</span>
        </div>
      </div>
      <div class="inlineform hidden" id="rm-${m.id}" style="border-color:var(--bad);background:var(--bad-soft)">
        <b>Remove ${esc(m.id)} · ${esc(m.title)}?</b>
        <p class="sub" style="margin:4px 0 10px;font-size:13px">The file moves to <span class="mono">state/trash/</span>, its quiz, cards and questions are dropped, and the id is never reused. Rebuild afterwards.</p>
        <div class="actions">
          <button class="btn sm danger" onclick="removeModule('${c.id}','${m.id}')">Yes, remove it</button>
          <button class="btn sm ghost" onclick="toggleRemove('${m.id}')">Keep it</button>
        </div>
      </div>`;
    }).join("");
    return `<div class="partblock">
      <div class="parttitle"><h3>${esc(part.name)}</h3><span class="tag">${esc(part.hours)}h</span><span class="tag">${mods.length} module${mods.length === 1 ? "" : "s"}</span></div>
      ${part.blurb ? `<p class="blurb">${esc(part.blurb)}</p>` : ""}
      ${rows || `<p class="sub" style="font-size:13px">No modules in this part yet.</p>`}
    </div>`;
  }).join("");
  $("#tabbody").innerHTML = parts || `<div class="card"><p class="sub" style="margin:0">This course has no readable modules yet.</p></div>`;
  if (route.query.rewrite) {
    const el = document.getElementById("rwn-" + route.query.rewrite);
    if (el) { el.scrollIntoView({ block: "center" }); el.focus(); }
  }
}

function toggleRewrite(mid) {
  const el = document.getElementById("rw-" + mid);
  if (!el) return;
  el.classList.toggle("hidden");
  if (!el.classList.contains("hidden")) document.getElementById("rwn-" + mid).focus();
}

function toggleRemove(mid) {
  const el = document.getElementById("rm-" + mid);
  if (el) el.classList.toggle("hidden");
}

async function removeModule(id, mid) {
  try {
    const r = await api(`/api/courses/${encodeURIComponent(id)}/modules/${encodeURIComponent(mid)}/remove`, {});
    toast(`${mid} removed`);
    await refresh();
    await viewCourse();
    const out = $("#courseout");
    if (out) out.innerHTML = r.problems && r.problems.length
      ? `<div class="problems"><b>${mid} removed, but the course now has ${r.problems.length} problem${r.problems.length === 1 ? "" : "s"}</b><ul>${r.problems.map(p => `<li>${esc(p)}</li>`).join("")}</ul></div>`
      : `<p class="sub ok-text" style="margin:12px 0 0">${mid} removed — its file is in <span class="mono">${esc(r.trash || "state/trash/")}</span>. Rebuild to publish the change.</p>`;
  } catch (err) { toast(err.message); }
}

/* ---- questions: what the reader marked while studying ---- */

function paintQuestions(c) {
  const qs = c.questions || [];
  if (!qs.length) {
    $("#tabbody").innerHTML = `<div class="card"><p class="eyebrow">Open questions</p>
      <p class="sub" style="margin:0">Nothing marked yet. While reading, select a sentence and turn it into a question — every one collects here, where it can become a new module or a rewrite.</p></div>`;
    return;
  }
  const rows = qs.map(q => {
    const brief = q.q || q.note || q.text;
    const topic = encodeURIComponent((q.q || q.text || "").slice(0, 140));
    const notes = encodeURIComponent(`From ${q.mid} (${q.title})${q.sec != null ? ", section " + (q.sec + 1) : ""}: "${(q.text || "").slice(0, 300)}"${q.q ? "\nThe reader asked: " + q.q : ""}`);
    return `<div class="qrow">
      <div class="qmeta"><span class="mid">${esc(q.mid)}</span> ${esc(q.title)} <span class="pill ${q.status === "answered" ? "on" : ""}" style="margin-left:6px">${esc(q.status)}</span></div>
      <blockquote>${esc(q.text)}</blockquote>
      ${q.q ? `<p class="qask">${esc(q.q)}</p>` : ""}${q.note && q.note !== brief ? `<p class="qask">${esc(q.note)}</p>` : ""}
      <div class="actions">
        <a class="btn sm" href="#/course/${encodeURIComponent(c.id)}?tab=add&from=${encodeURIComponent(q.mid)}&q=${topic}&notes=${notes}">Make this a module</a>
        <a class="btn sm ghost" href="#/course/${encodeURIComponent(c.id)}?tab=modules&rewrite=${encodeURIComponent(q.mid)}&q=${notes}">Rewrite ${esc(q.mid)} with this</a>
        ${c.built ? `<a class="btn sm ghost" href="${courseUrl(c, "#/m/" + q.mid + "/1")}">Open the passage</a>` : ""}
      </div>
    </div>`;
  }).join("");
  $("#tabbody").innerHTML = `<div class="card">
    <p class="eyebrow">Open questions</p>
    <p class="sub" style="font-size:13.5px">The passages you marked with a question while reading. They are the most honest map of where this course stops short — turn one into a brief.</p>
    ${rows}</div>`;
}

/* ---- settings: the presentation fields of course.json, as a form ---- */

function paintSettings(c) {
  const s = c.settings || {};
  const milestones = (s.milestones || []).map((m, i) => milestoneRow(m, i)).join("");
  const parts = (s.parts || []).map(p => `<div class="row" style="grid-template-columns:1fr 90px 2fr;margin-bottom:8px" data-part="${esc(p.id)}">
      <input type="text" class="p-name" value="${esc(p.name)}" aria-label="Part name">
      <input type="number" class="p-hours" value="${esc(p.hours)}" min="0" step="0.5" aria-label="Hours">
      <input type="text" class="p-blurb" value="${esc(p.blurb || "")}" placeholder="One line on what this part is for" aria-label="Blurb">
    </div>`).join("");
  $("#tabbody").innerHTML = `<div class="card">
    <p class="eyebrow">Settings</p>
    <p class="sub" style="font-size:13.5px">Everything here is presentation and prompt — it changes what the page says and how the tutor speaks. The id <span class="mono">${esc(s.id)}</span> is locked: it is the key your progress is stored under.</p>
    <div class="row" style="grid-template-columns:2fr 2fr">
      <div class="field"><label for="s-title">Title</label><input type="text" id="s-title" value="${esc(s.title)}"></div>
      <div class="field"><label for="s-tagline">Tagline</label><input type="text" id="s-tagline" value="${esc(s.tagline)}"></div>
    </div>
    <div class="row" style="grid-template-columns:2fr 2fr">
      <div class="field"><label for="s-audience">Who is studying</label><input type="text" id="s-audience" value="${esc(s.audience)}"></div>
      <div class="field"><label for="s-practitioner">Practitioner <span class="hint">what one is called</span></label><input type="text" id="s-practitioner" value="${esc(s.practitioner)}"></div>
    </div>
    <div class="field"><label for="s-persona">Tutor persona <span class="hint">the system prompt fragment; ends with a period</span></label><textarea id="s-persona" rows="2">${esc(s.tutorPersona)}</textarea></div>
    <label>Parts <span class="hint">name, hours, blurb — the course total follows the sum</span></label>
    ${parts}
    <label style="margin-top:14px">Milestones <span class="hint">the honest-read line on the stats page: after N modules, say this</span></label>
    <div id="milestones">${milestones}</div>
    <button class="btn sm ghost" onclick="addMilestone()" style="margin:6px 0 16px">+ Milestone</button>
    <div class="actions">
      <button class="btn" id="savesettings" onclick="saveSettings('${c.id}')">Save settings</button>
      <span class="sub" style="font-size:12.5px;margin:0 0 0 6px">Then Rebuild, so the page picks it up. The model Studio writes with, and the log of every run, are under <a href="#/settings">Settings &amp; logs</a>.</span>
    </div>
    <div id="settingsout"></div>
  </div>

  <div class="card">
    <p class="eyebrow">Progress backup</p>
    <p class="sub" style="font-size:13.5px">The platform's copy of your progress for this course — completion, quiz answers, flashcard schedule, notes, highlights and conversations. Download it to keep, or paste a backup (from here, or from the course page's own Backup / restore) to replace it.</p>
    <div class="actions">
      <button class="btn sm ghost" onclick="downloadProgress('${c.id}')">Download progress</button>
      <button class="btn sm ghost" onclick="toggleEl('restorebox')">Restore from a backup…</button>
    </div>
    <div id="restorebox" class="hidden" style="margin-top:12px">
      <textarea id="restoretext" rows="5" placeholder='Paste the backup JSON here. Either the raw state ({"progress": …}) or a download from this page.' style="font-family:var(--mono);font-size:12px"></textarea>
      <div class="actions" style="margin-top:8px"><button class="btn sm danger" onclick="restoreProgress('${c.id}')">Replace the platform copy</button></div>
    </div>
  </div>

  <div class="card" style="border-color:var(--bad)">
    <p class="eyebrow" style="color:var(--bad)">Delete this course</p>
    <p class="sub" style="font-size:13.5px">Moves the <span class="mono">${esc(c.id)}</span> folder (the whole course repository, if it is one) and its build to <span class="mono">state/trash/</span> and forgets the platform copy of your progress. Nothing is erased; you can move it back by hand. Type the id to confirm.</p>
    <div class="actions"><input type="text" id="delconfirm" placeholder="${esc(c.id)}" style="max-width:240px" autocomplete="off">
      <button class="btn sm danger" onclick="deleteCourse('${c.id}')">Delete course</button></div>
  </div>`;
}

function milestoneRow(m, i) {
  return `<div class="row" style="grid-template-columns:90px 1fr 36px;margin-bottom:8px" data-ms="${i}">
    <input type="number" class="ms-after" value="${esc(m.after)}" min="0" aria-label="After how many modules">
    <input type="text" class="ms-text" value="${esc(m.text)}" aria-label="Text">
    <button class="btn sm ghost" onclick="this.parentNode.remove()" title="Remove">×</button>
  </div>`;
}

function addMilestone() {
  $("#milestones").insertAdjacentHTML("beforeend", milestoneRow({ after: 0, text: "" }, Date.now()));
}

async function saveSettings(id) {
  const body = {
    title: $("#s-title").value, tagline: $("#s-tagline").value, audience: $("#s-audience").value,
    practitioner: $("#s-practitioner").value, tutorPersona: $("#s-persona").value,
    milestones: [...document.querySelectorAll("[data-ms]")].map(el => ({
      after: Number(el.querySelector(".ms-after").value) || 0, text: el.querySelector(".ms-text").value })),
    parts: [...document.querySelectorAll("[data-part]")].map(el => ({
      id: el.dataset.part, name: el.querySelector(".p-name").value,
      hours: Number(el.querySelector(".p-hours").value) || 0, blurb: el.querySelector(".p-blurb").value }))
  };
  const out = $("#settingsout");
  try {
    await api(`/api/courses/${encodeURIComponent(id)}/settings`, body);
    toast("Settings saved");
    await refresh();
    await viewCourse();
  } catch (err) { if (out) out.innerHTML = `<div class="problems">${esc(err.message)}</div>`; }
}

function toggleEl(id) { const el = document.getElementById(id); if (el) el.classList.toggle("hidden"); }

async function downloadProgress(id) {
  try {
    const r = await api(`/api/courses/${encodeURIComponent(id)}/progress`);
    if (!r.state) { toast("No progress stored yet for this course"); return; }
    const blob = new Blob([JSON.stringify(r.state, null, 1)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${id}-progress-${new Date().toISOString().slice(0, 10)}.json`;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  } catch (err) { toast(err.message); }
}

async function restoreProgress(id) {
  let obj;
  try { obj = JSON.parse($("#restoretext").value); } catch (e) { toast("That is not valid JSON"); return; }
  if (obj && obj.state && typeof obj.state === "object") obj = obj.state;
  if (!obj || typeof obj !== "object" || Array.isArray(obj)) { toast("That is not a progress backup"); return; }
  obj.updatedAt = Date.now();          // it must win over whatever a course page still holds
  try {
    await api(`/api/courses/${encodeURIComponent(id)}/progress`, { state: obj }, "PUT");
    toast("Progress replaced");
    await refresh(); await viewCourse();
  } catch (err) { toast(err.message); }
}

async function deleteCourse(id) {
  const typed = ($("#delconfirm").value || "").trim();
  if (typed !== id) { toast("Type the course id exactly to confirm"); $("#delconfirm").focus(); return; }
  try {
    const r = await api(`/api/courses/${encodeURIComponent(id)}/delete`, { confirm: typed });
    toast(`${id} moved to trash`);
    delete courseCache[id];
    await refresh();
    location.hash = "#/";
    setTimeout(() => toast(`It is in ${r.trash}`), 1200);
  } catch (err) { toast(err.message); }
}

async function rewriteModule(id, mid) {
  const notes = (document.getElementById("rwn-" + mid) || {}).value || "";
  try {
    const { job: j } = await api(`/api/courses/${encodeURIComponent(id)}/modules/${encodeURIComponent(mid)}/rewrite`, { notes: notes.trim() });
    location.hash = "#/job/" + j.id;
  } catch (err) { toast(err.message); }
}

function paintAdd(c) {
  const from = (c.moduleList || []).find(m => m.id === route.query.from);
  const defaultPart = from ? from.part : (c.parts.length ? c.parts[c.parts.length - 1].id : "");
  const sec = route.query.sec || "";
  const seed = route.query.q || "";
  const seedNotes = route.query.notes
    || (from ? "Requested after " + (sec ? 'the section "' + sec + '" of ' : "finishing ") + from.id + " (" + from.title + ")." : "");
  $("#tabbody").innerHTML = `<div class="card">
    <p class="eyebrow">Add a module</p>
    <p class="sub">Describe what the course should go further on. Claude designs one module that fits the existing curriculum — building on what is there, not repeating it — writes it, adds its quiz and flashcards, and rebuilds. It is appended to the part you choose and your progress elsewhere is untouched.</p>
    ${from ? `<div class="note" style="margin-bottom:16px">Coming from <b>${esc(from.id)} · ${esc(from.title)}</b>${sec ? `, section <b>${esc(sec)}</b>` : ""}. Say what that ${sec ? "section" : "module"} left you wanting.</div>` : ""}
    <div class="field">
      <label for="x-topic">What should the new module cover?</label>
      <input type="text" id="x-topic" value="${esc(seed)}" placeholder="${from ? "e.g. the part of " + esc(from.title) + " that needs a whole session" : "e.g. reading a failed loaf backwards"}" autocomplete="off">
    </div>
    <div class="row">
      <div class="field">
        <label for="x-part">Append to part</label>
        <select id="x-part">${(c.parts || []).map(p => `<option value="${esc(p.id)}" ${p.id === defaultPart ? "selected" : ""}>${esc(p.name)}</option>`).join("")}</select>
      </div>
      <div class="field">
        <label for="x-min">Minutes</label>
        <input type="number" id="x-min" value="60" min="15" max="240" step="15">
      </div>
      <div class="field"></div>
    </div>
    <div class="field">
      <label for="x-notes">Direction <span class="hint">optional</span></label>
      <textarea id="x-notes" placeholder="What confused you, what you want it to assume you already know, what to avoid.">${esc(seedNotes)}</textarea>
    </div>
    <div class="actions">
      <button class="btn" id="extendbtn" onclick="extendCourse('${c.id}')" ${STATE.claude.available ? "" : "disabled"}>Design and write it →</button>
    </div>
  </div>`;
  $("#x-topic").focus();
}

async function extendCourse(id) {
  const topic = $("#x-topic").value.trim();
  if (!topic) { toast("Say what it should cover"); $("#x-topic").focus(); return; }
  const btn = $("#extendbtn");
  btn.disabled = true; btn.textContent = "Starting…";
  try {
    const { job: j } = await api(`/api/courses/${encodeURIComponent(id)}/extend`, {
      topic, part: $("#x-part").value, minutes: Number($("#x-min").value) || 60,
      notes: $("#x-notes").value.trim()
    });
    location.hash = "#/job/" + j.id;
  } catch (err) {
    toast(err.message);
    btn.disabled = false; btn.textContent = "Design and write it →";
  }
}

function paintFiles(c) {
  const groups = {};
  (c.files || []).forEach(f => {
    const dir = f.includes("/") ? f.slice(0, f.lastIndexOf("/")) : "course";
    (groups[dir] = groups[dir] || []).push(f);
  });
  const html = Object.keys(groups).sort().map(dir => `<div class="filegroup"><h4>${esc(dir)}</h4><div class="filelist">
    ${groups[dir].map(f => `<a href="#/course/${encodeURIComponent(c.id)}/edit?path=${encodeURIComponent(f)}" title="${esc(f)}">${esc(f.slice(f.lastIndexOf("/") + 1))}</a>`).join("")}
  </div></div>`).join("");
  $("#tabbody").innerHTML = `<div class="card">
    <p class="eyebrow">Every file of the course</p>
    <p class="sub" style="font-size:13.5px">A course is markdown and JSON, nothing else. Edit anything here, then Check and Build. The format is a contract: <span class="mono">## </span> headings are sections, and each module's suggestion list needs one entry per section.</p>
    ${html}</div>`;
}

async function resumeCourse(id) {
  try {
    const { job: j } = await api(`/api/courses/${encodeURIComponent(id)}/resume`, {});
    location.hash = "#/job/" + j.id;
  } catch (err) { toast(err.message); }
}

async function checkCourse(id) {
  const out = $("#courseout");
  out.innerHTML = `<p class="sub" style="margin:12px 0 0">Checking…</p>`;
  try {
    const { problems } = await api(`/api/courses/${encodeURIComponent(id)}/check`, {});
    out.innerHTML = problems.length
      ? `<div class="problems"><b>${problems.length} problem${problems.length === 1 ? "" : "s"}</b><ul>${problems.map(p => `<li>${esc(p)}</li>`).join("")}</ul></div>`
      : `<p class="sub ok-text" style="margin:12px 0 0">Consistent — ready to build.</p>`;
  } catch (err) { out.innerHTML = `<div class="problems">${esc(err.message)}</div>`; }
}

async function buildCourse(id) {
  const out = $("#courseout");
  out.innerHTML = `<p class="sub" style="margin:12px 0 0">Building…</p>`;
  try {
    const data = await api(`/api/courses/${encodeURIComponent(id)}/build`, {});
    if (!data.built) {
      out.innerHTML = `<div class="problems"><b>Not built — fix these first</b><ul>${data.problems.map(p => `<li>${esc(p)}</li>`).join("")}</ul></div>`;
      return;
    }
    const r = data.result;
    toast("Built " + id);
    await refresh();
    await viewCourse();
    const o = $("#courseout");
    if (o) o.innerHTML = `<p class="sub ok-text" style="margin:12px 0 0">Built: ${r.modules} modules · ${r.sections} sections · ${r.quiz} quiz items · ${r.cards} cards · ${r.kb} KB</p>`;
  } catch (err) { out.innerHTML = `<div class="problems">${esc(err.message)}</div>`; }
}

/* ---------- Studio settings & logs ---------- */

let logTimer = null;

async function viewSettingsPage() {
  let s;
  try { s = await api("/api/settings"); }
  catch (err) { $("#view").innerHTML = `<div class="problems">${esc(err.message)}</div>`; return; }
  if (route.name !== "settings") return;
  const models = (s.models || []).map(m =>
    `<label class="radio"><input type="radio" name="model" value="${esc(m.id)}" ${s.model === m.id ? "checked" : ""} onchange="saveStudioSettings()"> <b>${esc(m.name)}</b> <span class="sub" style="margin:0">— ${esc(m.note)}</span></label>`).join("");
  $("#view").innerHTML = `
    <p class="crumb"><a href="#/">Courses</a> › Settings &amp; logs</p>
    <h2 class="big">Settings &amp; logs</h2>
    <p class="sub">What Studio uses for every generation and tutor call, and what it has been doing.</p>

    <div class="card">
      <p class="eyebrow">Model</p>
      <p class="sub" style="font-size:13.5px">Every call to Claude Code names its model explicitly. Without that the CLI inherits whatever you last picked interactively, and some of those (a <span class="mono">[1m]</span> context variant, say) are refused headless — which is how a run dies mid-module with <span class="mono">unrecognized_model</span>. If the chosen model fails, Studio falls back to Sonnet before giving up.</p>
      <div class="radios">${models}</div>
      <div id="settingsmsg"></div>
    </div>

    <div class="card">
      <p class="eyebrow">Claude Code</p>
      <p style="margin:0 0 6px">${s.claude.available ? `<span class="pill on">found</span> <span class="mono">${esc(s.claude.path)}</span>` : `<span class="pill off">not found on PATH</span> — generation and the tutor are disabled until it is installed and signed in.`}</p>
      <p class="sub" style="font-size:12.5px;margin:8px 0 0">Environment overrides: ${["STUDIO_MODEL", "STUDIO_LOG_LEVEL", "STUDIO_HOST"].map(k => `<span class="mono">${k}=${esc(s.env[k] || "")}</span>`).join(" · ")}</p>
    </div>

    <div class="card">
      <p class="eyebrow">Where things are</p>
      <table class="paths">${Object.entries(s.paths).map(([k, v]) => `<tr><td>${esc(k)}</td><td class="mono">${esc(v || "—")}</td></tr>`).join("")}</table>
    </div>

    <div class="card">
      <div class="editbar" style="margin-bottom:10px">
        <p class="eyebrow" style="margin:0">Log</p>
        <span class="spacer"></span>
        <select id="loglevel" onchange="loadLogs()" style="width:auto">
          ${["DEBUG", "INFO", "WARNING", "ERROR"].map(l => `<option ${l === "INFO" ? "selected" : ""}>${l}</option>`).join("")}
        </select>
        <input type="text" id="logq" placeholder="filter…" style="width:180px" oninput="loadLogs()">
        <label class="radio" style="margin:0"><input type="checkbox" id="logfollow" checked onchange="followLogs()"> follow</label>
        <button class="btn sm ghost" onclick="loadLogs()">Refresh</button>
        <button class="btn sm ghost" onclick="clearLogs()">Clear view</button>
      </div>
      <pre class="logbox" id="logbox">loading…</pre>
      <p class="sub" style="font-size:12px;margin:8px 0 0">The full file is <span class="mono">${esc(s.paths.log || "console only")}</span>, rotating at 2 MB. Every Claude call is one line: model, time taken, prompt and reply size, and the CLI's stderr when it fails.</p>
    </div>`;
  loadLogs();
  followLogs();
}

async function saveStudioSettings() {
  const model = (document.querySelector("input[name=model]:checked") || {}).value;
  const msg = $("#settingsmsg");
  try {
    await api("/api/settings", { model });
    toast("Default model: " + model);
    await refresh();
  } catch (err) { if (msg) msg.innerHTML = `<div class="problems">${esc(err.message)}</div>`; }
}

async function loadLogs() {
  const box = $("#logbox");
  if (!box || route.name !== "settings") return;
  const level = ($("#loglevel") || {}).value || "INFO";
  const q = ($("#logq") || {}).value || "";
  try {
    const { lines } = await api(`/api/logs?limit=500&level=${encodeURIComponent(level)}&q=${encodeURIComponent(q)}`);
    const atBottom = box.scrollHeight - box.scrollTop - box.clientHeight < 40;
    box.innerHTML = lines.length
      ? lines.map(l => `<div class="ll ${esc(l.level)}"><span class="lt">${esc(clock(l.t))}</span><span class="lv">${esc(l.level.slice(0, 4))}</span><span class="lm">${esc(l.msg)}</span></div>`).join("")
      : `<div class="ll INFO"><span class="lm">Nothing yet at this level.</span></div>`;
    if (atBottom || ($("#logfollow") || {}).checked) box.scrollTop = box.scrollHeight;
  } catch (err) { box.textContent = err.message; }
}

function followLogs() {
  clearInterval(logTimer);
  if (($("#logfollow") || {}).checked) logTimer = setInterval(loadLogs, 3000);
}

async function clearLogs() {
  try { await api("/api/logs/clear", {}); loadLogs(); } catch (err) { toast(err.message); }
}

/* ---------- the editor ---------- */

async function viewEdit() {
  const id = route.id, path = route.query.path || "";
  $("#view").innerHTML = `<p class="crumb"><a href="#/">Courses</a> › <a href="#/course/${encodeURIComponent(id)}">${esc(id)}</a> › ${esc(path)}</p><p class="sub">Loading…</p>`;
  let file;
  try { file = await api(`/api/courses/${encodeURIComponent(id)}/files?path=${encodeURIComponent(path)}`); }
  catch (err) { $("#view").innerHTML += `<div class="problems">${esc(err.message)}</div>`; return; }
  $("#view").innerHTML = `
    <p class="crumb"><a href="#/">Courses</a> › <a href="#/course/${encodeURIComponent(id)}?tab=files">${esc(id)}</a> › ${esc(path)}</p>
    <div class="editbar">
      <span class="path">${esc(path)}</span>
      <button class="btn sm" id="savebtn" onclick="saveFile('${id}')">Save</button>
      <button class="btn sm ghost" onclick="saveFile('${id}', true)">Save and check</button>
      <a class="btn sm ghost" href="#/course/${encodeURIComponent(id)}">Back to course</a>
    </div>
    <textarea class="editor" id="editor" spellcheck="false"></textarea>
    <div id="editout"></div>
    <p class="sub" style="font-size:12.5px;margin-top:10px">Ctrl+S saves. A module's first line must be <span class="mono"># M07 — Title</span>; every <span class="mono">## </span> heading with content is one section, and the suggestion file for the module needs exactly that many entries.</p>`;
  const ta = $("#editor");
  ta.value = file.text;
  ta.addEventListener("keydown", e => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") { e.preventDefault(); saveFile(id); }
    if (e.key === "Tab") { e.preventDefault(); const s = ta.selectionStart; ta.setRangeText("  ", s, ta.selectionEnd, "end"); }
  });
  ta.focus();
}

async function saveFile(id, check) {
  const path = route.query.path || "";
  const out = $("#editout");
  try {
    await api(`/api/courses/${encodeURIComponent(id)}/files?path=${encodeURIComponent(path)}`, { text: $("#editor").value }, "PUT");
    toast("Saved " + path.slice(path.lastIndexOf("/") + 1));
    if (!check) { out.innerHTML = ""; return; }
    const { problems } = await api(`/api/courses/${encodeURIComponent(id)}/check`, {});
    out.innerHTML = problems.length
      ? `<div class="problems"><b>${problems.length} problem${problems.length === 1 ? "" : "s"}</b><ul>${problems.map(p => `<li>${esc(p)}</li>`).join("")}</ul></div>`
      : `<p class="sub ok-text" style="margin:12px 0 0">Consistent — <a href="#/course/${encodeURIComponent(id)}">build it from the course page</a>.</p>`;
  } catch (err) { out.innerHTML = `<div class="problems">${esc(err.message)}</div>`; }
}

/* ---------- a running job ---------- */

function viewJob() {
  const jobId = route.id;
  if (job && job.id === jobId) { paintJob(true); return; }
  job = { id: jobId, events: [], plan: null, awaiting: null, meta: {},
          progress: { done: 0, total: 0, label: "" }, status: "running", result: null };
  const known = (STATE.jobs || []).find(j => j.id === jobId);
  if (known) { job.meta = known.meta || {}; job.kind = known.kind; }
  paintJob(true);
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
    if (route.name === "job" && route.id === jobId && !FINISHED.includes(job.status)) {
      setTimeout(() => connect(jobId, job.events.length ? job.events[job.events.length - 1].i + 1 : 0), 1200);
    }
  };
}

function absorb(event) {
  job.events.push(event);
  if (event.kind === "started") job.kind = event.job;
  if (event.kind === "progress") job.progress = { done: event.done, total: event.total, label: event.label };
  if (event.kind === "plan") job.plan = event.plan;
  if (event.kind === "await") { job.awaiting = event; job.status = "waiting"; }
  if (event.kind === "resumed") { job.awaiting = null; job.status = "running"; }
  if (event.kind === "done") job.result = event.result;
  if (event.kind === "end") {
    job.status = event.status;
    refresh().then(() => {
      const known = (STATE.jobs || []).find(j => j.id === job.id);
      if (known) job.meta = known.meta || {};
      if (route.name === "job") paintJob();
    });
  }
}

function stepLine(e) {
  if (e.kind === "log") return { text: e.message };
  if (e.kind === "spec") return { text: `${e.id} designed — "${e.title}", ${e.minutes} minutes`, cls: "ok" };
  if (e.kind === "module") return { text: `${e.id} written — ${e.sections} sections, ${e.words} words`, cls: "ok" };
  if (e.kind === "studydata") return { text: `${e.id} study data — ${e.quiz} quiz, ${e.cards} cards, ${e.sections} question sets`, cls: "ok" };
  if (e.kind === "worksheet") return { text: `Worksheet: ${e.name}`, cls: "ok" };
  if (e.kind === "plan") return { text: `Curriculum proposed — ${e.plan.modules.length} modules` };
  if (e.kind === "await") return { text: "Waiting for you to approve the curriculum" };
  if (e.kind === "built") return { text: `Built — ${e.modules} modules, ${e.sections} sections, ${e.kb} KB`, cls: "ok" };
  if (e.kind === "failed") return { text: e.error, cls: "bad" };
  if (e.kind === "cancelled") return { text: "Stopped.", cls: "bad" };
  return null;   // progress is shown by the bar, not the log
}

function jobTitle() {
  const m = job.meta || {};
  if (job.kind === "extend") return `Adding a module to ${m.course || ""}`;
  if (job.kind === "rewrite") return `Rewriting ${m.module || ""} in ${m.course || ""}`;
  return m.theme ? `Writing ${m.theme}` : "Working";
}

function paintJob(full) {
  if (route.name !== "job" || !job) return;
  if (full || !$("#jobwrap")) {
    $("#view").innerHTML = `<p class="crumb"><a href="#/">Courses</a> › ${esc(jobTitle())}</p><div id="jobwrap"></div>`;
  }
  const p = job.progress;
  const pct = p.total ? Math.round(p.done / p.total * 100) : 0;
  const finished = FINISHED.includes(job.status);
  const courseId = (job.meta || {}).course || (job.result || {}).course || "";
  const back = courseId
    ? `<a class="btn ghost" href="#/course/${encodeURIComponent(courseId)}">Back to the course</a>`
    : `<a class="btn ghost" href="#/">Back to courses</a>`;

  // Keep each line paired with its own event: stepLine() drops some events, so the
  // filtered index no longer lines up with job.events.
  const lines = job.events
    .map(e => { const l = stepLine(e); return l && Object.assign({ at: e.at }, l); })
    .filter(Boolean).slice(-200);
  const log = lines.map(l =>
    `<div class="step ${l.cls || ""}"><span class="when">${esc(clock(l.at))}</span><span class="what">${esc(l.text)}</span></div>`).join("");

  let head;
  if (job.status === "waiting" && job.awaiting) head = reviewPlanHTML();
  else if (job.status === "done") head = doneHTML(back);
  else if (finished) head = `<div class="card"><h3>${job.status === "cancelled" ? "Stopped" : "It did not finish"}</h3>
      <p class="sub" style="margin:6px 0 0">${esc(lines.filter(l => l.cls === "bad").map(l => l.text).join(" ") || "")}</p>
      <p class="sub" style="margin:10px 0 0">Anything written before this point is still on disk under <span class="mono">courses/</span>.${job.kind === "generate" && courseId ? " The curriculum is saved, so the run can be resumed: it keeps what is written and does only the rest." : ""} The <a href="#/settings">log</a> has the CLI's own error.</p>
      <div class="actions">${job.kind === "generate" && courseId ? `<button class="btn" style="background:var(--warm)" onclick="resumeCourse('${esc(courseId)}')">Resume the run →</button>` : ""}${back}</div></div>`;
  else head = `<div class="card">
      <p class="eyebrow">${esc(job.status)} · ${esc(jobTitle())}</p>
      <h3>${esc(p.label || "Working…")}</h3>
      <div class="bar-track"><div class="bar-fill" style="width:${pct}%"></div></div>
      <p class="sub" style="margin:0;font-size:13px">${p.total ? `step ${p.done} of ${p.total}` : "starting"}</p>
      <div class="actions" style="margin-top:12px"><button class="btn danger sm" onclick="cancelJob()">Stop</button></div>
    </div>`;

  $("#jobwrap").innerHTML = head + `<div class="card"><p class="eyebrow">Activity</p><div class="steps" id="steps">${log}</div></div>`;
  const box = $("#steps");
  if (box) box.scrollTop = box.scrollHeight;
}

function doneHTML(back) {
  const r = job.result || {};
  const id = r.course || "";
  const c = (STATE.courses || []).find(x => x.id === id);
  const target = r.module ? "#/m/" + r.module : "#/home";
  const open = c && c.built
    ? `<a class="btn" href="${courseUrl(c, target)}">${r.module ? "Read " + esc(r.module) : "Open the course"} ↗</a>`
    : "";
  const what = job.kind === "extend" ? `${esc(r.module || "A module")} was added to ${esc(id)}`
    : job.kind === "rewrite" ? `${esc(r.module || "The module")} was rewritten`
    : `${esc(id)} is built`;
  return `<div class="card">
    <p class="eyebrow" style="color:var(--ok)">Finished</p>
    <h3>${what}</h3>
    <p class="sub" style="margin:4px 0 0">${r.modules} modules · ${r.sections} sections · ${r.quiz} quiz items · ${r.cards} flashcards · ${r.glossary} glossary terms · ${r.kb} KB</p>
    <div class="actions" style="margin-top:14px">${open}${back}</div>
    <p class="sub" style="margin:14px 0 0;font-size:13px">Opened from here, the course keeps its progress on the platform and asks its questions through Studio — no key, no bridge, no disk copy needed.</p>
  </div>`;
}

/* ---------- the approval gate ---------- */

function reviewPlanHTML() {
  const plan = job.plan || {};
  const parts = (plan.parts || []).map(part => {
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
  job.plan.modules = job.plan.modules.filter(m => m.id !== id);
  paintJob(true);
}

function harvestPlan() {
  const plan = JSON.parse(JSON.stringify(job.plan));
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
    await api(`/api/jobs/${encodeURIComponent(job.id)}/answer`, { plan });
    job.awaiting = null;
    job.status = "running";
    paintJob(true);
  } catch (err) { toast(err.message); }
}

async function cancelJob() {
  try { await api(`/api/jobs/${encodeURIComponent(job.id)}/cancel`, {}); toast("Stopping…"); }
  catch (err) { toast(err.message); }
}

/* ---------- routing ---------- */

function parseRoute() {
  const raw = (location.hash || "#/").slice(1);
  const [path, qs] = raw.split("?");
  const query = {};
  new URLSearchParams(qs || "").forEach((v, k) => { query[k] = v; });
  const bits = path.split("/").filter(Boolean);
  if (bits[0] === "new") return { name: "new", id: null, query };
  if (bits[0] === "settings") return { name: "settings", id: null, query };
  if (bits[0] === "job" && bits[1]) return { name: "job", id: bits[1], query };
  if (bits[0] === "course" && bits[1]) {
    return { name: bits[2] === "edit" ? "edit" : "course", id: decodeURIComponent(bits[1]), query };
  }
  return { name: "library", id: null, query };
}

function render() {
  route = parseRoute();
  if (route.name !== "job" && stream) { stream.close(); stream = null; }
  if (route.name !== "settings") clearInterval(logTimer);
  document.querySelectorAll(".topnav a").forEach(a => a.classList.toggle("active",
    (route.name === "library" && a.id === "nav-library") || (route.name === "new" && a.id === "nav-new")
    || (route.name === "settings" && a.id === "nav-settings")));
  window.scrollTo(0, 0);
  if (route.name === "new") return viewNew();
  if (route.name === "settings") return viewSettingsPage();
  if (route.name === "job") return viewJob();
  if (route.name === "course") return viewCourse();
  if (route.name === "edit") return viewEdit();
  return viewLibrary();
}

window.addEventListener("hashchange", () => { refresh().then(render).catch(render); });
$("#themebtn").onclick = cycleTheme;

refresh().then(() => {
  // Reattach to a run that is still going, so closing the tab is not the same as stopping.
  const live = (STATE.jobs || []).find(j => !FINISHED.includes(j.status));
  if (live && (!location.hash || location.hash === "#/" || location.hash === "#")) {
    location.hash = "#/job/" + live.id;
    return;
  }
  render();
}).catch(err => {
  $("#view").innerHTML = `<div class="card"><h3>Cannot reach the Studio server</h3><p class="sub">${esc(err.message)}</p></div>`;
});
