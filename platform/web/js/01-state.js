/* ============================ state ============================ */
/* The storage key carries the reader profile when Studio is reading as someone other than
   the default, so two readers on one browser never share a state object. */
let KEY = CFG.storageKey, PROFILE = "default";
const DAY = 86400000;
const todayNum = () => Math.floor(Date.now() / DAY);
/* Platform settings, injected at build time from platform/settings.json (see
   coursekit.settings.Settings.page). Nothing in this folder carries a default of its own:
   addresses, models, limits and layout sizes all come from here. */
const PLATFORM = CFG.platform;
const TUTOR = PLATFORM.tutor, SYNC = PLATFORM.sync, STUDY = PLATFORM.study, LAYOUT = PLATFORM.ui;
/* The connection block of a fresh state: where the bridge is expected and which model to
   ask for. Whatever the reader changes in Settings is kept on top of this. */
const connDefaults = () => ({ url: PLATFORM.bridgeUrl, key: "", model: PLATFORM.defaultModel, route: "direct", mode: "none" });
const blank = () => ({
  progress: {}, cards: {}, mcards: {}, notes: {}, marks: {}, convos: {}, active: {}, biz: "",
  chk: {}, cp: null, cpHist: [], plan: { mode: null, weekly: null, target: null, start: null },
  bookmarks: {}, pos: {}, sheets: {},
  bridge: connDefaults(),
  streak: { days: 0, last: null, seen: [], freezes: 0, frozen: [] },
  theme: null, v: 1
});
let S = load();

function load() {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return blank();
    return upgrade(Object.assign(blank(), JSON.parse(raw)));
  } catch (e) { return blank(); }
}
/* Older saves predate some fields; fill them in rather than guarding every read. */
function upgrade(s) {
  const b = blank();
  ["mcards", "chk", "cpHist", "bookmarks", "pos", "sheets"].forEach(k => { if (!s[k] || typeof s[k] !== "object") s[k] = b[k]; });
  s.plan = Object.assign({}, b.plan, s.plan || {});
  s.streak = Object.assign({}, b.streak, s.streak || {});
  if (!Array.isArray(s.streak.frozen)) s.streak.frozen = [];
  if (!Array.isArray(s.streak.seen)) s.streak.seen = [];
  return s;
}
function save() {
  S.updatedAt = Date.now();
  try { localStorage.setItem(KEY, JSON.stringify(S)); } catch (e) {}
  syncPush();
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
let syncTimer = null, syncOn = false, syncState = "off";
function syncUrl() { return `${STUDIO.origin}/api/courses/${STUDIO.id}/progress?profile=${encodeURIComponent(PROFILE)}`; }
/* Ask Studio who is reading before anything is loaded. Off disk there is no one to ask. */
async function profileInit() {
  if (!STUDIO) return;
  try {
    const ctrl = new AbortController(); const t = setTimeout(() => ctrl.abort(), SYNC.pullTimeoutMs);
    const r = await fetch(`${STUDIO.origin}/api/profile`, { signal: ctrl.signal, cache: "no-store" });
    clearTimeout(t);
    if (!r.ok) return;
    const j = await r.json();
    const name = String((j && j.profile) || "default");
    if (name !== "default") { PROFILE = name; KEY = CFG.storageKey + "_" + name; S = load(); applyTheme(); }
  } catch (e) { /* off-line or not Studio: the default profile */ }
}
function syncBody() {
  const o = Object.assign({}, S);
  delete o.bridge; delete o.ui; delete o.theme;
  return JSON.stringify({ state: o });
}
async function syncPull() {
  if (!STUDIO) return false;
  try {
    const ctrl = new AbortController(); const t = setTimeout(() => ctrl.abort(), SYNC.pullTimeoutMs);
    const r = await fetch(syncUrl(), { signal: ctrl.signal, cache: "no-store" });
    clearTimeout(t);
    if (!r.ok) return false;
    const j = await r.json();
    syncOn = true; syncState = "on";
    const remote = j && j.state;
    if (remote && (remote.updatedAt || 0) > (S.updatedAt || 0)) {
      const keep = { bridge: S.bridge, ui: S.ui, theme: S.theme };
      S = upgrade(Object.assign(blank(), remote, keep));
      try { localStorage.setItem(KEY, JSON.stringify(S)); } catch (e) {}
      return true;
    }
    if (!remote || (S.updatedAt || 0) > (remote.updatedAt || 0)) syncPush(true);
  } catch (e) { syncState = "off"; }
  return false;
}
function syncPush(now) {
  if (!STUDIO || !syncOn) return;
  clearTimeout(syncTimer);
  syncTimer = setTimeout(async () => {
    try {
      const r = await fetch(syncUrl(), { method: "PUT", headers: { "content-type": "application/json" }, body: syncBody() });
      syncState = r.ok ? "on" : "err";
    } catch (e) { syncState = "err"; }
  }, now ? 0 : SYNC.debounceMs);
}
window.addEventListener("pagehide", () => {
  if (!STUDIO || !syncOn) return;
  clearTimeout(syncTimer);
  try { navigator.sendBeacon(syncUrl(), new Blob([syncBody()], { type: "application/json" })); } catch (e) {}
});
function P(id) {
  if (!S.progress[id]) S.progress[id] = { secs: {}, predict: "", quiz: null, elab: {}, elabFb: {}, transfer: null, done: false, doneAt: null, time: 0, step: 0 };
  if (!S.progress[id].elabFb) S.progress[id].elabFb = {};
  return S.progress[id];
}
/* A day counts once you have done one real thing: read a section, answered a question,
   reviewed a card, asked the tutor. A single missed day spends a freeze if you have one;
   freezes are earned by finishing modules. */
function markDay() {
  const t = todayNum(), st = S.streak;
  if (st.last === t) return;
  if (st.last === t - 1) st.days++;
  else if (st.last === t - 2 && (st.freezes || 0) > 0) { st.freezes--; st.frozen.push(t - 1); st.days++; }
  else st.days = 1;
  st.last = t;
  if (!st.seen.includes(t)) st.seen.push(t);
  st.seen = st.seen.slice(-STUDY.seenDays);
  st.frozen = st.frozen.slice(-STUDY.frozenDays);
  save();
}
function earnFreeze() {
  const st = S.streak;
  if ((st.freezes || 0) >= STUDY.maxFreezes) return false;
  st.freezes = (st.freezes || 0) + 1; save(); return true;
}
