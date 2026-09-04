/* Course Studio — the whole client.

   Hash-routed, so every screen has an address and the back button works:

     #/                            the library: every course, with the reader's progress
     #/new                         the brief for a new course
     #/course/<id>                 one course: modules, progress, add a module, files
     #/course/<id>?tab=add&from=M07   the same page, opened from inside a course
     #/course/<id>/edit?path=...   a file of the course, in an editor
     #/job/<id>                    a running job
     #/search?q=...                every course, searched at once

   A job screen is driven entirely by the server's event stream, so reloading the page
   mid-generation reattaches instead of losing the run — the stream replays from the last
   event index the client saw. */

const $ = s => document.querySelector(s);
const esc = s =>
  String(s == null ? "" : s).replace(
    /[&<>"]/g,
    c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]
  );

let STATE = { courses: [], claude: { available: false }, jobs: [] };
let route = { name: "library", id: null, query: {} };
let job = null; // the job screen's state, while one is showing
let stream = null;
let courseCache = {}; // id -> detail, refreshed on every visit
const FINISHED = ["done", "failed", "cancelled"];

/* ---------- plumbing ---------- */

async function api(path, body, method) {
  const res = await fetch(
    path,
    body === undefined
      ? {}
      : {
          method: method || "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }
  );
  const data = await res.json().catch(() => ({ error: "The server sent something unreadable." }));
  if (!res.ok) throw new Error(data.error || "Request failed (" + res.status + ")");
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
  return (
    String(d.getHours()).padStart(2, "0") +
    ":" +
    String(d.getMinutes()).padStart(2, "0") +
    ":" +
    String(d.getSeconds()).padStart(2, "0")
  );
}

function ago(ts) {
  const mins = Math.round((Date.now() / 1000 - (ts || 0)) / 60);
  if (mins < 1) return "just now";
  if (mins < 60) return mins + " min ago";
  const hours = Math.round(mins / 60);
  if (hours < 24) return hours + "h ago";
  return Math.round(hours / 24) + "d ago";
}

function fmtH(mins) {
  const h = mins / 60;
  return (h % 1 === 0 ? h : h.toFixed(1)) + "h";
}

/* "42s", "1m 05s", "1h 12m" — for how long something has been running. */
function fmtDur(seconds) {
  const s = Math.max(0, Math.round(seconds || 0));
  if (s < 60) return s + "s";
  const m = Math.floor(s / 60);
  if (m < 60) return m + "m " + String(s % 60).padStart(2, "0") + "s";
  return Math.floor(m / 60) + "h " + String(m % 60).padStart(2, "0") + "m";
}

/* A spinner with a ticking clock, for the synchronous operations (Check, Build, an
   import) that used to show a static "Building…". Returns a stop() that also reports how
   long it took; `lock` names a container whose buttons are disabled meanwhile. */
function busy(out, label, lock) {
  const start = Date.now();
  const buttons = lock
    ? Array.from(document.querySelectorAll(lock + " button, " + lock + " .btn"))
    : [];
  buttons.forEach(b => {
    b.disabled = true;
    b.classList.add("disabled");
  });
  const paint = () => {
    if (out)
      out.innerHTML = `<p class="sub busy" style="margin:12px 0 0"><span class="spin"></span><span>${esc(label)}</span><span class="mono">${fmtDur((Date.now() - start) / 1000)}</span></p>`;
  };
  paint();
  const timer = setInterval(paint, 1000);
  const stop = () => {
    clearInterval(timer);
    buttons.forEach(b => {
      b.disabled = false;
      b.classList.remove("disabled");
    });
  };
  stop.took = () => {
    const s = (Date.now() - start) / 1000;
    return s < 1 ? "under a second" : fmtDur(s);
  };
  return stop;
}

/* One line for a job in the listing: what it is doing right now, not just its kind. */
function jobLabel(j) {
  if (!j) return "";
  const p = j.progress || {};
  const where = p.total ? ` ${p.done}/${p.total}` : "";
  if (j.status === "waiting") return "waiting for your approval";
  return (p.label || (j.kind === "generate" ? "designing the curriculum" : j.kind)) + where;
}

function courseUrl(c, hash) {
  return `/course/${encodeURIComponent(c.id)}/${encodeURIComponent(c.localFile)}${hash || "#/home"}`;
}

async function refresh() {
  STATE = await api("/api/state");
  paintProfilePicker();
  const pill = $("#claudestate");
  pill.textContent = STATE.claude.available ? "Claude Code connected" : "Claude Code not found";
  pill.className = "pill " + (STATE.claude.available ? "on" : "off");
  paintLiveJobs();
  return STATE;
}

/* ---------- what is running, visible from every screen ---------- */

/* The header pill, and every card or button that names a live job, are updated in place:
   a poll must not repaint a screen the person may be typing on. */
function paintLiveJobs() {
  const live = (STATE.jobs || []).filter(j => !FINISHED.includes(j.status));
  const pill = $("#jobstate");
  if (pill) {
    if (live.length) {
      const j = live[0];
      const m = j.meta || {};
      const who = m.course || m.theme || "";
      pill.textContent = jobLabel(j) + (live.length > 1 ? ` (+${live.length - 1} more)` : "");
      pill.title = (who ? who + " · " : "") + jobLabel(j) + " — click to watch";
      pill.href = "#/job/" + j.id;
      pill.classList.remove("hidden");
    } else {
      pill.classList.add("hidden");
    }
  }
  document.querySelectorAll("[data-jobof]").forEach(el => {
    const j = live.find(x => (x.meta || {}).course === el.dataset.jobof);
    if (j) el.textContent = jobLabel(j) + (el.classList.contains("btn") ? " — view" : "");
  });
}

let hadLive = false;
setInterval(async () => {
  if (route.name === "job") return; // that screen streams its own job
  const live = (STATE.jobs || []).some(j => !FINISHED.includes(j.status));
  if (!live && !hadLive) return;
  try {
    await refresh();
  } catch (e) {
    return;
  }
  const still = (STATE.jobs || []).some(j => !FINISHED.includes(j.status));
  if (hadLive && !still) {
    courseCache = {};
    render();
  } // buttons come back, cards update
  hadLive = still;
}, 4000);

/* ---------- reader profiles ---------- */

function paintProfilePicker() {
  const sel = $("#profilesel");
  if (!sel) return;
  const names = STATE.profiles || ["default"],
    active = STATE.profile || "default";
  sel.innerHTML =
    names
      .map(n => `<option value="${esc(n)}" ${n === active ? "selected" : ""}>${esc(n)}</option>`)
      .join("") + `<option value="__manage">Manage profiles…</option>`;
  sel.onchange = async () => {
    if (sel.value === "__manage") {
      sel.value = active;
      location.hash = "#/settings";
      return;
    }
    await switchProfile(sel.value);
  };
}

async function switchProfile(name) {
  try {
    await api("/api/profiles", { action: "switch", name });
    toast("Reading as " + name);
    courseCache = {};
    await refresh();
    render();
  } catch (err) {
    toast(err.message);
  }
}

async function addProfile() {
  const input = $("#newprofile");
  if (!input) return;
  const name = input.value.trim().toLowerCase();
  if (!name) {
    input.focus();
    return;
  }
  try {
    await api("/api/profiles", { action: "add", name });
    toast("Profile " + name + " created — reading as them now");
    courseCache = {};
    await refresh();
    render();
  } catch (err) {
    toast(err.message);
  }
}

async function removeProfile(name) {
  try {
    await api("/api/profiles", { action: "remove", name });
    toast("Profile " + name + " moved to trash");
    courseCache = {};
    await refresh();
    render();
  } catch (err) {
    toast(err.message);
  }
}

/* ---------- theme ---------- */

function cycleTheme() {
  const now = document.documentElement.getAttribute("data-theme");
  const next = now === "dark" ? "light" : now === "light" ? "" : "dark";
  if (next) document.documentElement.setAttribute("data-theme", next);
  else document.documentElement.removeAttribute("data-theme");
  try {
    localStorage.setItem("studio_theme", next);
  } catch (e) {
    /* private mode */
  }
}
try {
  const saved = localStorage.getItem("studio_theme");
  if (saved) document.documentElement.setAttribute("data-theme", saved);
} catch (e) {
  /* private mode */
}
