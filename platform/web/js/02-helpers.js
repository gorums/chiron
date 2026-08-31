/* ============================ helpers ============================ */
const $ = s => document.querySelector(s);
const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const MODS = DATA.modules;
const byId = id => MODS.find(m => m.id === id);
const mIndex = id => MODS.findIndex(m => m.id === id);

function secTotal(m) { return m.sections.length; }
function secDone(m) { const p = P(m.id); return m.sections.filter((_, i) => p.secs[i]).length; }
function modPct(m) {
  const p = P(m.id);
  let n = 0, d = 5;
  n += secDone(m) / secTotal(m);
  if (p.predict.trim()) n++;
  if (p.quiz && p.quiz.finished) n++;
  if (Object.values(p.elab).some(v => (v || "").trim())) n++;
  if (p.transfer && p.transfer.score != null) n++;
  return Math.min(1, n / d);
}
function isDone(m) { return P(m.id).done; }
function doneCount() { return MODS.filter(isDone).length; }
function minutesDone() { return MODS.filter(isDone).reduce((a, m) => a + m.minutes, 0); }
function timeSpent() { return MODS.reduce((a, m) => a + (P(m.id).time || 0), 0); }

function quizStats() {
  let right = 0, total = 0;
  const conf = { 1: [0, 0], 2: [0, 0], 3: [0, 0] };
  MODS.forEach(m => {
    const q = P(m.id).quiz;
    if (!q || !q.a) return;
    q.a.forEach(x => {
      if (!x) return;
      total++; if (x.ok) right++;
      const c = conf[x.conf] || conf[2];
      c[1]++; if (x.ok) c[0]++;
    });
  });
  return { right, total, pct: total ? right / total : 0, conf };
}
function cardKey(mid, i) { return mid + ":" + i; }
function dueCards() {
  const t = todayNum(), out = [];
  MODS.forEach(m => {
    (m.assess.cards || []).forEach((c, i) => {
      const k = cardKey(m.id, i), st = S.cards[k];
      if (!st) return;
      if (st.due <= t) out.push({ k, mid: m.id, mtitle: m.title, c, st });
    });
  });
  return out;
}
function cardCount() { return Object.keys(S.cards).length; }
function seedCards(mid) {
  const m = byId(mid); let added = 0;
  (m.assess.cards || []).forEach((c, i) => {
    const k = cardKey(mid, i);
    if (!S.cards[k]) { S.cards[k] = { due: todayNum(), ease: 2.4, ivl: 0, reps: 0, lapses: 0 }; added++; }
  });
  save(); return added;
}
function grade(k, g) {
  const st = S.cards[k]; if (!st) return;
  if (g === 0) { st.ease = Math.max(1.3, st.ease - .2); st.ivl = 0; st.lapses++; st.due = todayNum(); }
  else if (g === 1) { st.ease = Math.max(1.3, st.ease - .15); st.ivl = st.ivl ? Math.max(1, Math.round(st.ivl * 1.2)) : 1; st.due = todayNum() + st.ivl; }
  else if (g === 2) { st.ivl = st.ivl === 0 ? 1 : (st.ivl === 1 ? 3 : Math.round(st.ivl * st.ease)); st.due = todayNum() + st.ivl; }
  else { st.ease = Math.min(2.8, st.ease + .12); st.ivl = st.ivl === 0 ? 3 : Math.round(st.ivl * st.ease * 1.25); st.due = todayNum() + st.ivl; }
  st.reps++; save();
}
function toast(msg) {
  const t = $("#toast"); t.textContent = msg; t.classList.add("on");
  clearTimeout(t._x); t._x = setTimeout(() => t.classList.remove("on"), 2100);
}
function fmtH(mins) { const h = mins / 60; return (h % 1 === 0 ? h : h.toFixed(1)) + "h"; }
function fmtClock(sec) {
  const m = Math.floor(sec / 60), s = Math.floor(sec % 60);
  return m + ":" + String(s).padStart(2, "0");
}
