/* ============================ state ============================ */
/* The storage key carries the reader profile when Studio is reading as someone other than
   the default, so two readers on one browser never share a state object. */
let KEY = CFG.storageKey,
  PROFILE = "default";
const DAY = 86400000;
const todayNum = () => Math.floor(Date.now() / DAY);
/* Platform settings, injected at build time from platform/settings.json (see
   coursekit.settings.Settings.page). Nothing in this folder carries a default of its own:
   addresses, models, limits and layout sizes all come from here. */
const PLATFORM = CFG.platform;
const TUTOR = PLATFORM.tutor,
  SYNC = PLATFORM.sync,
  STUDY = PLATFORM.study,
  LAYOUT = PLATFORM.ui,
  LEARNER = PLATFORM.learner,
  FIGURES = PLATFORM.figures,
  NOTEBOOKS = PLATFORM.notebooks,
  AUDIO = PLATFORM.audio;
/* The connection block of a fresh state: where the bridge is expected and which model to
   ask for. Whatever the reader changes in Settings is kept on top of this. */
const connDefaults = () => ({
  url: PLATFORM.bridgeUrl,
  key: "",
  model: PLATFORM.defaultModel,
  route: "direct",
  mode: "none",
});
const blank = () => ({
  progress: {},
  cards: {},
  mcards: {},
  notes: {},
  marks: {},
  convos: {},
  active: {}, // no longer read: the rail finds its conversation by place (see 17-convos.js)
  biz: "",
  chk: {},
  cp: null,
  cpHist: [],
  plan: { mode: null, weekly: null, target: null, start: null },
  bookmarks: {},
  pos: {},
  sheets: {},
  bridge: connDefaults(),
  streak: { days: 0, last: null, seen: [], freezes: 0, frozen: [] },
  gone: {}, // id -> when, for conversations and marks deleted on purpose (see mergeStates)
  learner: learnerBlank(), // what the tutor remembers about this reader (see 17c-learner.js)
  theme: null,
  v: 1,
});
let STATE = load();

function load() {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return blank();
    return upgrade(Object.assign(blank(), JSON.parse(raw)));
  } catch (e) {
    return blank();
  }
}
/* Older saves predate some fields; fill them in rather than guarding every read. */
function upgrade(s) {
  const b = blank();
  [
    "mcards",
    "chk",
    "cpHist",
    "bookmarks",
    "pos",
    "sheets",
    "gone",
    "convos",
    "active",
    "marks",
  ].forEach(k => {
    if (!s[k] || typeof s[k] !== "object") s[k] = b[k];
  });
  s.plan = Object.assign({}, b.plan, s.plan || {});
  s.learner = Object.assign(learnerBlank(), s.learner || {});
  s.streak = Object.assign({}, b.streak, s.streak || {});
  if (!Array.isArray(s.streak.frozen)) s.streak.frozen = [];
  if (!Array.isArray(s.streak.seen)) s.streak.seen = [];
  return s;
}
function save() {
  STATE.updatedAt = Date.now();
  try {
    localStorage.setItem(KEY, JSON.stringify(STATE));
  } catch (e) {}
  syncPush();
}

/* ---- merging two copies of the state ----
   Two tabs of one course, or two browsers, each hold a copy and save the whole thing.
   Replacing one copy with the other loses whatever the other did since - a conversation,
   a highlight, a section ticked - which is how chats went missing. So copies are merged:
   every keyed collection is the union of both, a key held by both taking the entry from
   the copy that saved later (a conversation: the one updated later), progress per module
   keeping every section read on either side, and deletions remembered in `gone` so a
   stale copy cannot bring a deleted conversation or mark back. Scalars come from the
   later copy. Device settings (`bridge`, `ui`, `theme`) are the caller's business. */
const MERGED_MAPS = [
  "progress",
  "cards",
  "mcards",
  "notes",
  "marks",
  "convos",
  "active",
  "chk",
  "bookmarks",
  "pos",
  "sheets",
];
function mergeStates(a, b) {
  const [older, newer] = (a.updatedAt || 0) <= (b.updatedAt || 0) ? [a, b] : [b, a];
  const out = Object.assign(blank(), newer);
  const gone = Object.assign({}, older.gone || {}, newer.gone || {});
  out.gone = gone;
  MERGED_MAPS.forEach(k => {
    out[k] = Object.assign({}, older[k] || {}, newer[k] || {});
  });

  Object.keys(out.convos).forEach(id => {
    const x = (older.convos || {})[id],
      y = (newer.convos || {})[id];
    if (gone[id]) delete out.convos[id];
    else if (x && y) out.convos[id] = (x.updated || 0) > (y.updated || 0) ? x : y;
  });
  Object.keys(out.active).forEach(mid => {
    if (!out.convos[out.active[mid]]) delete out.active[mid];
  });

  out.marks = {};
  const mids = new Set([...Object.keys(older.marks || {}), ...Object.keys(newer.marks || {})]);
  mids.forEach(mid => {
    const byId = {};
    [...((older.marks || {})[mid] || []), ...((newer.marks || {})[mid] || [])].forEach(mk => {
      if (mk && mk.id && !gone[mk.id]) byId[mk.id] = mk;
    });
    out.marks[mid] = Object.values(byId);
  });

  Object.keys(out.progress).forEach(mid => {
    const x = (older.progress || {})[mid],
      y = (newer.progress || {})[mid];
    if (!x || !y) return;
    const p = (out.progress[mid] = Object.assign({}, x, y));
    p.secs = Object.assign({}, x.secs || {}, y.secs || {});
    p.elab = Object.assign({}, x.elab || {}, y.elab || {});
    p.elabFb = Object.assign({}, x.elabFb || {}, y.elabFb || {});
    p.gapWork = Object.assign({}, x.gapWork || {}, y.gapWork || {});
    p.gapsAt = Math.max(x.gapsAt || 0, y.gapsAt || 0) || null;
    p.time = Math.max(x.time || 0, y.time || 0);
    p.done = !!(x.done || y.done);
    p.doneAt = y.doneAt || x.doneAt || null;
    p.predict = y.predict || x.predict || "";
    p.transfer = y.transfer || x.transfer || null;
    if (x.quiz && x.quiz.finished && !(y.quiz && y.quiz.finished)) p.quiz = x.quiz;
  });

  out.learner = mergeLearner(older.learner, newer.learner);

  const sa = older.streak || {},
    sb = newer.streak || {};
  out.streak = Object.assign({}, sa, sb);
  out.streak.days = Math.max(sa.days || 0, sb.days || 0);
  out.streak.last = Math.max(sa.last || 0, sb.last || 0) || null;
  out.streak.seen = [...new Set([...(sa.seen || []), ...(sb.seen || [])])].sort((p, q) => p - q);
  out.streak.frozen = [...new Set([...(sa.frozen || []), ...(sb.frozen || [])])].sort(
    (p, q) => p - q
  );

  const seenAt = new Set((newer.cpHist || []).map(h => h.at));
  out.cpHist = [
    ...(newer.cpHist || []),
    ...(older.cpHist || []).filter(h => !seenAt.has(h.at)),
  ].sort((p, q) => (p.at || 0) - (q.at || 0));

  out.updatedAt = Math.max(a.updatedAt || 0, b.updatedAt || 0);
  return out;
}
/* Something deleted on purpose stays deleted when copies merge. */
function forget(id) {
  if (!STATE.gone) STATE.gone = {};
  STATE.gone[id] = Date.now();
}
/* Another tab of this course saved: take in what it did. The rail is redrawn only when
   the reader is not mid-sentence there. */
window.addEventListener("storage", e => {
  if (e.key !== KEY || !e.newValue) return;
  try {
    STATE = upgrade(mergeStates(STATE, JSON.parse(e.newValue)));
  } catch (err) {
    return;
  }
  refreshRailQuietly();
});
function refreshRailQuietly() {
  const inp = document.getElementById("railin");
  if (route.view === "m" && railOpen() && !rail.sending && !(inp && inp.value)) renderRail();
}

/* ---- platform sync ----
   When this page is served by Course Studio (http://…/course/<id>/…) progress is also kept
   on the platform, so Studio can show how far you are and you can carry on from another
   browser. localStorage stays the working copy; the platform copy is the durable one.
   Device settings — the API key, bridge address, theme, reading preferences — never leave
   this browser. */
const STUDIO = (() => {
  if (!/^https?:$/.test(location.protocol)) return null;
  const m = location.pathname.match(/^\/course\/([a-z0-9-]+)\//);
  return m && m[1] === CFG.id ? { origin: location.origin, id: m[1] } : null;
})();
let syncTimer = null,
  syncOn = false,
  syncState = "off";
function syncUrl() {
  return `${STUDIO.origin}/api/courses/${STUDIO.id}/progress?profile=${encodeURIComponent(PROFILE)}`;
}
/* Ask Studio who is reading before anything is loaded. Off disk there is no one to ask. */
async function profileInit() {
  if (!STUDIO) return;
  try {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), SYNC.pullTimeoutMs);
    const r = await fetch(`${STUDIO.origin}/api/profile`, {
      signal: ctrl.signal,
      cache: "no-store",
    });
    clearTimeout(t);
    if (!r.ok) return;
    const j = await r.json();
    const name = String((j && j.profile) || "default");
    if (name !== "default") {
      PROFILE = name;
      KEY = CFG.storageKey + "_" + name;
      STATE = load();
      applyTheme();
    }
  } catch (e) {
    /* off-line or not Studio: the default profile */
  }
}
function syncBody() {
  const o = Object.assign({}, STATE);
  delete o.bridge;
  delete o.ui;
  delete o.theme;
  return JSON.stringify({ state: o });
}
async function syncPull() {
  if (!STUDIO) return false;
  try {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), SYNC.pullTimeoutMs);
    const r = await fetch(syncUrl(), { signal: ctrl.signal, cache: "no-store" });
    clearTimeout(t);
    if (!r.ok) return false;
    const j = await r.json();
    syncOn = true;
    syncState = "on";
    const remote = j && j.state;
    if (!remote) {
      syncPush(true);
      return false;
    }
    // Merge rather than replace: the platform copy may be behind this browser on some
    // things and ahead on others. Whatever this browser had that the platform lacked
    // goes back up straight away.
    const keep = { bridge: STATE.bridge, ui: STATE.ui, theme: STATE.theme };
    const before = JSON.stringify(STATE);
    STATE = upgrade(Object.assign(mergeStates(STATE, remote), keep));
    const changed = JSON.stringify(STATE) !== before;
    try {
      localStorage.setItem(KEY, JSON.stringify(STATE));
    } catch (e) {}
    if (changed || (STATE.updatedAt || 0) > (remote.updatedAt || 0)) syncPush(true);
    return changed;
  } catch (e) {
    syncState = "off";
  }
  return false;
}
/* Coming back to a tab that sat in the background: another browser may have studied since. */
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState !== "visible" || !STUDIO) return;
  syncPull().then(changed => {
    if (changed) refreshRailQuietly();
  });
});
function syncPush(now) {
  if (!STUDIO || !syncOn) return;
  clearTimeout(syncTimer);
  syncTimer = setTimeout(
    async () => {
      try {
        const r = await fetch(syncUrl(), {
          method: "PUT",
          headers: { "content-type": "application/json" },
          body: syncBody(),
        });
        syncState = r.ok ? "on" : "err";
      } catch (e) {
        syncState = "err";
      }
    },
    now ? 0 : SYNC.debounceMs
  );
}
window.addEventListener("pagehide", () => {
  if (!STUDIO || !syncOn) return;
  clearTimeout(syncTimer);
  try {
    navigator.sendBeacon(syncUrl(), new Blob([syncBody()], { type: "application/json" }));
  } catch (e) {}
});
function progressOf(id) {
  if (!STATE.progress[id])
    STATE.progress[id] = {
      secs: {},
      predict: "",
      quiz: null,
      elab: {},
      elabFb: {},
      transfer: null,
      done: false,
      doneAt: null,
      time: 0,
      step: 0,
      gapWork: {}, // item key -> { answer, closed, verdict, text, at } (see 07b-gaps.js)
      gapsAt: null, // when the Close-the-gaps step was first opened
    };
  if (!STATE.progress[id].elabFb) STATE.progress[id].elabFb = {};
  if (!STATE.progress[id].gapWork) STATE.progress[id].gapWork = {};
  return STATE.progress[id];
}
/* A day counts once you have done one real thing: read a section, answered a question,
   reviewed a card, asked the tutor. A single missed day spends a freeze if you have one;
   freezes are earned by finishing modules. */
function markDay() {
  const t = todayNum(),
    st = STATE.streak;
  if (st.last === t) return;
  if (st.last === t - 1) st.days++;
  else if (st.last === t - 2 && (st.freezes || 0) > 0) {
    st.freezes--;
    st.frozen.push(t - 1);
    st.days++;
  } else st.days = 1;
  st.last = t;
  if (!st.seen.includes(t)) st.seen.push(t);
  st.seen = st.seen.slice(-STUDY.seenDays);
  st.frozen = st.frozen.slice(-STUDY.frozenDays);
  save();
}
function earnFreeze() {
  const st = STATE.streak;
  if ((st.freezes || 0) >= STUDY.maxFreezes) return false;
  st.freezes = (st.freezes || 0) + 1;
  save();
  return true;
}
