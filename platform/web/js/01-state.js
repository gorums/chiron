/* ============================ state ============================ */
const KEY = CFG.storageKey;
const DAY = 86400000;
const todayNum = () => Math.floor(Date.now() / DAY);
const BRIDGE_DEFAULT = { url: "http://127.0.0.1:8787", key: "", model: "claude-sonnet-5", route: "direct", mode: "none" };
const blank = () => ({
  progress: {}, cards: {}, notes: {}, marks: {}, convos: {}, active: {}, biz: "",
  bridge: Object.assign({}, BRIDGE_DEFAULT),
  streak: { days: 0, last: null, seen: [] },
  theme: null, v: 1
});
let S = load();

function load() {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return blank();
    return Object.assign(blank(), JSON.parse(raw));
  } catch (e) { return blank(); }
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
   Device settings — the API key, bridge address, theme — never leave this browser. */
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
      S = Object.assign(blank(), remote, keep);
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
  if (!S.progress[id]) S.progress[id] = { secs: {}, predict: "", quiz: null, elab: {}, transfer: null, done: false, doneAt: null, time: 0, step: 0 };
  return S.progress[id];
}
function markDay() {
  const t = todayNum();
  if (S.streak.last === t) return;
  S.streak.days = (S.streak.last === t - 1) ? S.streak.days + 1 : 1;
  S.streak.last = t;
  if (!S.streak.seen.includes(t)) S.streak.seen.push(t);
  S.streak.seen = S.streak.seen.slice(-120);
  save();
}
