/* The handful of functions both front ends need: query, escape, toast, icons, dates, and
   the one glossary that explains the platform's own words at the point they are printed.

   The reader inlines this file with the rest of `web/js/`; Studio links it from
   `/ui/shared/00-dom.js` before its own scripts. It therefore may not touch anything but
   the DOM — no STATE, no CFG, no api(). */

const $ = s => document.querySelector(s);
const esc = s =>
  String(s == null ? "" : s).replace(
    /[&<>"]/g,
    c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]
  );

/* ---------- toast ----------
   `kind` says what happened: "ok" (the default), "info", or "bad". A bad one is red and
   stays until it is dismissed, because an error the reader did not see is an error that
   happened twice. The host element carries role="status", so it is announced. */
const TOAST_MS_MIN = 2200;
const TOAST_MS_PER_CHAR = 45;
function toast(message, opts) {
  const el = $("#toast");
  if (!el) return;
  const o = opts || {};
  const kind = o.kind || "ok";
  const sticky = o.sticky != null ? o.sticky : kind === "bad";
  el.className = "toast on" + (kind === "bad" ? " bad" : "") + (sticky ? " sticky" : "");
  el.innerHTML =
    `<span>${esc(message)}</span>` +
    (sticky ? `<button class="dismiss" aria-label="Dismiss" onclick="hideToast()">✕</button>` : "");
  clearTimeout(toast.timer);
  if (!sticky) {
    const ms = Math.min(7000, TOAST_MS_MIN + String(message).length * TOAST_MS_PER_CHAR);
    toast.timer = setTimeout(hideToast, ms);
  }
}
function hideToast() {
  const el = $("#toast");
  if (el) el.classList.remove("on");
}

/* Smooth scrolling is a nice touch and a symptom trigger. Ask before doing it. */
function reducedMotion() {
  try {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  } catch (e) {
    return false;
  }
}
function scrollBehavior() {
  return reducedMotion() ? "auto" : "smooth";
}

/* ---------- dates and durations ---------- */
function fmtH(mins) {
  const h = mins / 60;
  return (h % 1 === 0 ? h : h.toFixed(1)) + "h";
}
/* seconds of elapsed study → "7:05" */
function fmtClock(sec) {
  const m = Math.floor(sec / 60),
    s = Math.floor(sec % 60);
  return m + ":" + String(s).padStart(2, "0");
}
/* an epoch timestamp → the wall clock, for a log line */
function clock(ts) {
  const d = new Date((ts || 0) * 1000);
  const two = n => String(n).padStart(2, "0");
  return two(d.getHours()) + ":" + two(d.getMinutes()) + ":" + two(d.getSeconds());
}
function ago(ts) {
  const mins = Math.round((Date.now() / 1000 - (ts || 0)) / 60);
  if (mins < 1) return "just now";
  if (mins < 60) return mins + " min ago";
  const hours = Math.round(mins / 60);
  if (hours < 24) return hours + "h ago";
  return Math.round(hours / 24) + "d ago";
}
/* "42s", "1m 05s", "1h 12m" — for how long something has been running. */
function fmtDur(seconds) {
  const s = Math.max(0, Math.round(seconds || 0));
  if (s < 60) return s + "s";
  const m = Math.floor(s / 60);
  if (m < 60) return m + "m " + String(s % 60).padStart(2, "0") + "s";
  return Math.floor(m / 60) + "h " + String(m % 60).padStart(2, "0") + "m";
}

/* ---------- icons ----------
   Inline SVG, so a glyph renders the same on every operating system. `ico(name)` returns
   markup; both surfaces draw from this one set. */
const ICON_PATHS = {
  home: "M3 11 12 4l9 7v9a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z",
  review: "M20 12a8 8 0 1 1-2.3-5.7M20 4v5h-5",
  check: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zm0 5a4 4 0 1 0 0 8 4 4 0 0 0 0-8z",
  stats: "M4 20V10M10 20V4M16 20v-7M22 20H2",
  marks: "M4 20h4l10-10-4-4L4 16zM13 7l4 4",
  library: "M4 5h6v14H4zM14 5h6v14h-6z",
  settings:
    "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8zm8 4-1.5-.4.3-1.6-1.4-.8-1 1.2-1.4-.9.4-1.5-1.6-.5-.7 1.4H11l-.7-1.4-1.6.5.4 1.5-1.4.9-1-1.2-1.4.8.3 1.6L4 12l1.5.4-.3 1.6 1.4.8 1-1.2 1.4.9-.4 1.5 1.6.5.7-1.4h2.4l.7 1.4 1.6-.5-.4-1.5 1.4-.9 1 1.2 1.4-.8-.3-1.6z",
  plan: "M4 6h16M4 12h10M4 18h7",
  record: "M6 3h12v18l-6-4-6 4z",
  courses: "M3 7h18v13H3zM3 7l3-4h12l3 4",
  plus: "M12 5v14M5 12h14",
  close: "M6 6l12 12M18 6 6 18",
  trash: "M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13M10 11v6M14 11v6",
  pencil: "M4 20h4L19 9l-4-4L4 16zM13 7l4 4",
  play: "M7 4v16l13-8z",
  pause: "M8 5v14M16 5v14",
  speak: "M4 9v6h4l5 4V5L8 9zM16 9a4 4 0 0 1 0 6M18.5 6.5a8 8 0 0 1 0 11",
  flag: "M5 21V4h11l-1 4 1 4H5",
  ask: "M9 9a3 3 0 1 1 4.5 2.6c-1 .6-1.5 1.2-1.5 2.4M12 18h.01",
  learner: "M12 3a4 4 0 1 0 0 8 4 4 0 0 0 0-8zM4 21a8 8 0 0 1 16 0M15 6h4M17 4v4",
  spark: "M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9z",
  menu: "M4 7h16M4 12h16M4 17h16",
  search: "M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14zM20 20l-4-4",
  theme: "M12 3a9 9 0 1 0 0 18zM12 3a9 9 0 0 1 0 18",
  more: "M6 12h.01M12 12h.01M18 12h.01",
  up: "M6 15l6-6 6 6",
  down: "M6 9l6 6 6-6",
  right: "M9 6l6 6-6 6",
  tick: "M4 12.5 9 17.5 20 6.5",
};
function ico(name, size) {
  const d = ICON_PATHS[name] || "";
  const px = size || 16;
  return `<svg class="ic" width="${px}" height="${px}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="${d}"/></svg>`;
}

/* ---------- one glossary, used wherever a term is printed ----------
   The platform has words of its own — mastery, freeze, patch, curriculum. Each is defined
   once here and shown as a `title` at the point of use, so no one has to go and find the
   page that explains it. `help(term)` returns the sentence, or "" for a term with none. */
const HELP = {
  "not started": "You have not opened this module yet.",
  read: "You have been through every section of this module.",
  practised: "You scored 70% or better on this module's own quiz.",
  proficient: "This module held up in a checkpoint, days after you read it.",
  mastered: "Proficient, and its flashcards have settled past a three-week interval.",
  mastery:
    "How much of this module you can still use: Not started, Read, Practised, Proficient, Mastered.",
  "practice deck":
    "Your flashcards, scheduled so each one comes back just before you would forget it.",
  "mistake card":
    "A question you missed, or only got with a hint, turned into a card. Four clean recalls and it retires.",
  "streak freeze":
    "One earned day off. A freeze is spent automatically to keep a streak alive when you miss a day.",
  checkpoint:
    "A mixed quiz across a finished part, taken days later. It is what raises a module to Proficient — or drops it back.",
  calibration:
    "How well your confidence matches your results. Being sure and wrong is worth knowing about.",
  compact:
    "Replaces a long chat with a summary, so the tutor keeps the thread without re-reading everything.",
  "close the gaps":
    "The sixth step: drill exactly what you got wrong in this module until it is closed.",
  gap: "Something the tutor has seen you get wrong more than once, with the question that would prove it is fixed.",
  anchor: "The one real case you apply every exercise to, named by the course.",
  tutor: "The model, answering about the passage you are looking at.",
  verdict: "A model's read on a module: solid means publishable; needs work and rewrite do not.",
  solid: "Publishable as it stands. Minor findings do not lower this.",
  "needs work": "Usable, but something specific has to be fixed first.",
  rewrite: "The module does not do its job; write it again.",
  stale: "This verdict was given before the module was last edited, so it may no longer hold.",
  patch: "Apply the notes to the module as it is, leaving every other sentence alone.",
  "full rewrite":
    "Regenerate every sentence from the design. It fixes the last review's findings and creates new ones.",
  resume: "Continue a run that died: keep everything already written, write only what is missing.",
  candidate:
    "A model on the list that no source recognised. It stays until one real call is refused.",
  profile: "Whose progress Studio is showing. Each reader has their own copy.",
  practitioner: "The noun for someone who does this subject — what a reader is training to be.",
  curriculum: "The whole outline of a course: its parts, its modules and their minutes.",
  "needs fixing": "This course fails its own validation, so it cannot be built.",
  dirty: "A file changed since the last build. Rebuild to put it in the page.",
};
function help(term) {
  return HELP[String(term || "").toLowerCase()] || "";
}
