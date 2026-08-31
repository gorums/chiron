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
  try { localStorage.setItem(KEY, JSON.stringify(S)); } catch (e) {}
}
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
