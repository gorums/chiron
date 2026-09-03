/* ============================ state ============================ */
const KEY = CFG.storageKey;
const DAY = 86400000;
const todayNum = () => Math.floor(Date.now() / DAY);
const BRIDGE_DEFAULT = { url: "http://127.0.0.1:8787", key: "", model: "claude-sonnet-5", route: "direct", mode: "none" };
const MAX_FREEZES = 3;
const blank = () => ({
  progress: {}, cards: {}, mcards: {}, notes: {}, marks: {}, convos: {}, active: {}, biz: "",
  chk: {}, cp: null, cpHist: [], plan: { mode: null, weekly: null, target: null, start: null },
  bookmarks: {}, pos: {}, sheets: {},
  bridge: Object.assign({}, BRIDGE_DEFAULT),
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
function syncUrl() { return `${STUDIO.origin}/api/courses/${STUDIO.id}/progress`; }
function syncBody() {
  const o = Object.assign({}, S);
  delete o.bridge; delete o.ui; delete o.theme;
  return JSON.stringify({ state: o });
}
async function syncPull() {
  if (!STUDIO) return false;
  try {
    const ctrl = new AbortController(); const t = setTimeout(() => ctrl.abort(), 2500);
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
  }, now ? 0 : 1200);
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
  st.seen = st.seen.slice(-400);
  st.frozen = st.frozen.slice(-60);
  save();
}
function earnFreeze() {
  const st = S.streak;
  if ((st.freezes || 0) >= MAX_FREEZES) return false;
  st.freezes = (st.freezes || 0) + 1; save(); return true;
}
