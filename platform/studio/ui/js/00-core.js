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

/* $, esc, toast, ico, clock, ago, fmtH, fmtDur and help() come from the shared
   /ui/shared/00-dom.js, the same file the course page inlines. */

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

/* A spinner with a ticking clock, for the synchronous operations (Check, Build, an
   import) that used to show a static "Building…". Returns a stop() that also reports how
   long it took; `lock` names a container whose buttons are disabled meanwhile — or a
   single element, so one button can lock itself. */
function busy(out, label, lock) {
  const start = Date.now();
  const buttons = !lock
    ? []
    : typeof lock === "string"
      ? Array.from(document.querySelectorAll(lock + " button, " + lock + " .btn"))
      : [lock];
  buttons.forEach(b => {
    b.disabled = true;
    b.classList.add("disabled");
    b.setAttribute("aria-disabled", "true");
  });
  const paint = () => {
    if (out)
      out.innerHTML = `<p class="sub busy result"><span class="spin"></span><span>${esc(label)}</span><span class="mono">${fmtDur((Date.now() - start) / 1000)}</span></p>`;
  };
  paint();
  const timer = setInterval(paint, 1000);
  const stop = () => {
    clearInterval(timer);
    buttons.forEach(b => {
      b.disabled = false;
      b.classList.remove("disabled");
      b.removeAttribute("aria-disabled");
    });
  };
  stop.took = () => {
    const s = (Date.now() - start) / 1000;
    return s < 1 ? "under a second" : fmtDur(s);
  };
  return stop;
}

/* What a job of each kind is called, so no screen ever prints a raw kind. */
const KIND_LABELS = {
  generate: "writing the course",
  extend: "adding a module",
  rewrite: "rewriting a module",
  review: "reviewing a module",
  figures: "drawing figures",
  notebooks: "writing notebooks",
  resume: "finishing an unfinished run",
};
function kindLabel(kind) {
  return KIND_LABELS[kind] || kind || "working";
}
/* One line for a job in the listing: what it is doing right now, not just its kind. */
function jobLabel(j) {
  if (!j) return "";
  const p = j.progress || {};
  const where = p.total ? ` ${p.done}/${p.total}` : "";
  if (j.status === "waiting") return "waiting for your approval";
  const base = p.label || (j.kind === "generate" ? "designing the curriculum" : kindLabel(j.kind));
  return base + where;
}
/* The most recent finished run, for the "Last run" line on the library hero. */
function lastFinishedJob() {
  const done = (STATE.jobs || []).filter(j => FINISHED.includes(j.status));
  done.sort((a, b) => (b.finished || b.started || 0) - (a.finished || a.started || 0));
  return done[0] || null;
}
function liveJobs() {
  return (STATE.jobs || []).filter(j => !FINISHED.includes(j.status));
}
/* A run is going somewhere else: say so and offer the way there, rather than hijacking
   the screen the person asked for. */
function liveJobBanner() {
  const live = liveJobs();
  if (!live.length) return "";
  const j = live[0];
  const who = (j.meta || {}).course || (j.meta || {}).theme || "";
  const more = live.length > 1 ? ` (+${live.length - 1} more)` : "";
  return `<div class="banner"><span class="pulse"></span><span class="grow">${esc(who ? who + " · " : "")}${esc(jobLabel(j))}${more}</span>
    <a class="btn sm" href="#/job/${esc(j.id)}">Watch it</a></div>`;
}
/* Every screen that needs Claude says once, in words, why its buttons are off. */
function claudeReady() {
  return !!(STATE.claude && STATE.claude.available);
}
function claudeGate() {
  if (claudeReady()) return "";
  return `<div class="note gap-top">Claude Code is not answering, so everything that writes or reviews is off.
    Install it and run <span class="mono">claude login</span>, then <a href="#/settings">check the status</a>.</div>`;
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
  pill.title = STATE.claude.available
    ? "The installed Claude Code CLI is answering. Open Settings & logs."
    : "Studio cannot reach the Claude Code CLI. Open Settings & logs to see what to do.";
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
      pill.classList.toggle("waiting", j.status === "waiting");
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
  // The picker only picks. Adding and removing readers lives on the settings page, behind
  // the link beside it — a <select> option that navigates is a trap.
  sel.innerHTML = names
    .map(n => `<option value="${esc(n)}" ${n === active ? "selected" : ""}>${esc(n)}</option>`)
    .join("");
  sel.onchange = () => switchProfile(sel.value);
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

/* Removing a profile trashes a reader's progress, so it asks first — inline, on the row,
   the way removing a module does. */
function askRemoveProfile(name) {
  const slot = document.getElementById("prm-" + name);
  if (!slot) return removeProfile(name);
  slot.innerHTML =
    `<span class="sub">Move this reader's progress to the trash?</span>` +
    `<button class="btn sm danger" onclick="removeProfile('${esc(name)}')">Remove ${esc(name)}</button>` +
    `<button class="btn sm" onclick="viewSettingsPage()">Keep it</button>`;
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

/* ---------- theme ----------
   One key for the whole platform: a course page served by Studio reads the same value, so
   a dark Studio never opens a light course page. */
const THEME_KEY = "platform_theme";
const THEME_NAMES = { dark: "dark", light: "light", "": "your system's setting" };
function cycleTheme() {
  const now = document.documentElement.getAttribute("data-theme");
  const next = now === "dark" ? "light" : now === "light" ? "" : "dark";
  if (next) document.documentElement.setAttribute("data-theme", next);
  else document.documentElement.removeAttribute("data-theme");
  try {
    localStorage.setItem(THEME_KEY, next);
  } catch (e) {
    /* private mode */
  }
  paintThemeButton();
}
function paintThemeButton() {
  const b = $("#themebtn");
  if (!b) return;
  const now = document.documentElement.getAttribute("data-theme") || "";
  b.innerHTML = ico("theme", 17);
  b.title = "Theme: " + THEME_NAMES[now] + ". Click for the next one.";
  b.setAttribute("aria-label", b.title);
}
try {
  const saved = localStorage.getItem(THEME_KEY) || localStorage.getItem("studio_theme");
  if (saved) document.documentElement.setAttribute("data-theme", saved);
} catch (e) {
  /* private mode */
}

/* ---------- the narrow-screen menu ----------
   Under 720px the nav row does not fit, so it collapses into this. Without it, New course
   and Settings were simply unreachable on a phone. */
function toggleNavMenu() {
  const menu = $("#navmenu"),
    btn = $("#navmenubtn");
  const opening = menu.classList.contains("hidden");
  menu.classList.toggle("hidden", !opening);
  btn.setAttribute("aria-expanded", String(opening));
  if (opening) menu.querySelector("[role=menuitem]").focus();
}
function closeNavMenu() {
  const menu = $("#navmenu");
  if (!menu || menu.classList.contains("hidden")) return;
  menu.classList.add("hidden");
  $("#navmenubtn").setAttribute("aria-expanded", "false");
}
document.addEventListener("keydown", e => {
  if (e.key === "Escape") closeNavMenu();
});
document.addEventListener("click", e => {
  if (!e.target.closest("#navmenu") && !e.target.closest("#navmenubtn")) closeNavMenu();
});

/* The header's icons come from the shared set, drawn once the scripts are up. */
function paintChrome() {
  const menu = $("#navmenubtn");
  if (menu) menu.innerHTML = ico("menu", 18);
  const jump = document.querySelector(".searchjump");
  if (jump) jump.innerHTML = ico("search", 17);
  const profiles = $("#profilelink");
  if (profiles) profiles.innerHTML = ico("learner", 17);
  paintThemeButton();
}
paintChrome();
