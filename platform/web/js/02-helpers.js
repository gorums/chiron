/* ============================ helpers ============================ */
/* $, esc, toast, ico, fmtH, fmtClock and help() live in 00-dom.js, shared with Studio. */
const MODS = DATA.modules;
const byId = id => MODS.find(m => m.id === id);
const moduleIndex = id => MODS.findIndex(m => m.id === id);

function secTotal(m) {
  return m.sections.length;
}
function secDone(m) {
  const p = progressOf(m.id);
  return m.sections.filter((_, i) => p.secs[i]).length;
}
function modPct(m) {
  const p = progressOf(m.id);
  let n = 0,
    d = 5;
  n += secDone(m) / secTotal(m);
  if (p.predict.trim()) n++;
  if (p.quiz && p.quiz.finished) n++;
  if (Object.values(p.elab).some(v => (v || "").trim())) n++;
  if (p.transfer && (p.transfer.score != null || p.transfer.fb)) n++;
  return Math.min(1, n / d);
}
function isDone(m) {
  return progressOf(m.id).done;
}
function doneCount() {
  return MODS.filter(isDone).length;
}
/* Where to send someone who has finished what they were doing: the first module that is
   not complete, starting after `from` when there is one, else the first anywhere. */
function nextUnfinished(from) {
  const at = from ? moduleIndex(from) : -1;
  return (
    MODS.slice(at + 1).find(m => !isDone(m)) || MODS.find(m => !isDone(m)) || MODS[at + 1] || null
  );
}
function minutesDone() {
  return MODS.filter(isDone).reduce((a, m) => a + m.minutes, 0);
}
function timeSpent() {
  return MODS.reduce((a, m) => a + (progressOf(m.id).time || 0), 0);
}
function quizPct(m) {
  const q = progressOf(m.id).quiz;
  if (!q || !q.finished) return null;
  const t = q.a.filter(Boolean);
  return t.length ? t.filter(x => x.ok).length / t.length : null;
}

/* Calibration pools every answered question: module quizzes and checkpoints alike. */
function quizStats() {
  let right = 0,
    total = 0;
  const conf = { 1: [0, 0], 2: [0, 0], 3: [0, 0] };
  const take = x => {
    if (!x || !x.answered) return;
    total++;
    if (x.ok) right++;
    const c = conf[x.conf] || conf[2];
    c[1]++;
    if (x.ok) c[0]++;
  };
  MODS.forEach(m => {
    const q = progressOf(m.id).quiz;
    if (q && q.a) q.a.forEach(take);
  });
  (STATE.cpHist || []).forEach(h => (h.a || []).forEach(take));
  return { right, total, pct: total ? right / total : 0, conf };
}

/* ---------- cards: authored flashcards plus the mistake queue ---------- */
function cardKey(mid, i) {
  return mid + ":" + i;
}
function mistakeKey(mid, qi) {
  return "mk:" + mid + ":" + qi;
}
function isMistakeKey(k) {
  return k.startsWith("mk:");
}
function cardFor(k) {
  if (isMistakeKey(k)) {
    const mc = STATE.mcards[k];
    return mc ? { mid: mc.mid, c: { front: mc.front, back: mc.back }, mistake: true } : null;
  }
  const [mid, i] = k.split(":");
  const m = byId(mid);
  const c = m && (m.assess.cards || [])[+i];
  return c ? { mid, c, mistake: false } : null;
}
function dueCards() {
  const t = todayNum(),
    out = [];
  Object.keys(STATE.cards).forEach(k => {
    const st = STATE.cards[k];
    if (!st || st.due > t) return;
    const info = cardFor(k);
    if (!info) return;
    const m = byId(info.mid);
    out.push({
      k,
      mid: info.mid,
      mtitle: m ? m.title : info.mid,
      c: info.c,
      st,
      mistake: info.mistake,
    });
  });
  return out;
}
function allCards() {
  return Object.keys(STATE.cards)
    .map(k => {
      const st = STATE.cards[k],
        info = cardFor(k);
      if (!st || !info) return null;
      const m = byId(info.mid);
      return {
        k,
        mid: info.mid,
        mtitle: m ? m.title : info.mid,
        c: info.c,
        st,
        mistake: info.mistake,
      };
    })
    .filter(Boolean);
}
function cardCount() {
  return Object.keys(STATE.cards).length;
}
function mistakeCount() {
  return Object.keys(STATE.cards).filter(isMistakeKey).length;
}
function mistakesDue() {
  return dueCards().filter(c => c.mistake).length;
}
function seedCards(mid) {
  const m = byId(mid);
  let added = 0;
  (m.assess.cards || []).forEach((c, i) => {
    const k = cardKey(mid, i);
    if (!STATE.cards[k]) {
      STATE.cards[k] = { due: todayNum(), ease: 2.4, ivl: 0, reps: 0, lapses: 0 };
      added++;
    }
  });
  save();
  return added;
}
/* A missed question becomes a card due tomorrow. It retires after four clean recalls. */
function addMistake(mid, qi, item, resp) {
  const k = mistakeKey(mid, qi);
  STATE.mcards[k] = {
    mid,
    qi,
    front: mistakeFront(item),
    back: correctText(item) + (item.why ? "\n\n" + item.why : ""),
    made: Date.now(),
  };
  const st = STATE.cards[k];
  if (st) {
    st.due = todayNum() + 1;
    st.ivl = 0;
    st.wins = 0;
    st.lapses++;
  } else STATE.cards[k] = { due: todayNum() + 1, ease: 2.2, ivl: 0, reps: 0, lapses: 0, wins: 0 };
  save();
}
function mistakeFront(item) {
  const t = item.type || "single";
  if (t === "single" || t === "multi")
    return item.q + "\n" + item.options.map((o, i) => "ABCDEFGH"[i] + ". " + o).join("\n");
  if (t === "tf") return "True or false: " + item.q;
  if (t === "match") return item.q + "\n" + item.pairs.map(p => p[0]).join(" · ");
  return item.q;
}
function grade(k, g) {
  const st = STATE.cards[k];
  if (!st) return;
  if (g === 0) {
    st.ease = Math.max(1.3, st.ease - 0.2);
    st.ivl = 0;
    st.lapses++;
    st.due = todayNum();
    st.wins = 0;
  } else if (g === 1) {
    st.ease = Math.max(1.3, st.ease - 0.15);
    st.ivl = st.ivl ? Math.max(1, Math.round(st.ivl * 1.2)) : 1;
    st.due = todayNum() + st.ivl;
  } else if (g === 2) {
    st.ivl = st.ivl === 0 ? 1 : st.ivl === 1 ? 3 : Math.round(st.ivl * st.ease);
    st.due = todayNum() + st.ivl;
    st.wins = (st.wins || 0) + 1;
  } else {
    st.ease = Math.min(2.8, st.ease + 0.12);
    st.ivl = st.ivl === 0 ? 3 : Math.round(st.ivl * st.ease * 1.25);
    st.due = todayNum() + st.ivl;
    st.wins = (st.wins || 0) + 1;
  }
  st.reps++;
  let retired = false;
  if (isMistakeKey(k) && (st.wins || 0) >= 4) {
    delete STATE.cards[k];
    delete STATE.mcards[k];
    retired = true;
  }
  save();
  return retired;
}
function cardStats(mid) {
  const keys = Object.keys(STATE.cards).filter(k => !isMistakeKey(k) && k.startsWith(mid + ":"));
  const n = (byId(mid).assess.cards || []).length;
  const ivls = keys.map(k => STATE.cards[k].ivl || 0);
  return {
    n,
    seeded: keys.length,
    meanIvl: ivls.length ? ivls.reduce((a, b) => a + b, 0) / ivls.length : 0,
  };
}

/* ---------- mastery: what you can still do, not what you once ticked ----------
   0 Not started · 1 Read · 2 Practised (quiz ≥ 70%) · 3 Proficient (held up in a checkpoint)
   · 4 Mastered (proficient, and the cards have settled past three weeks).
   A checkpoint miss drops a module back to Practised until the next checkpoint hit. */
const MASTERY = ["Not started", "Read", "Practised", "Proficient", "Mastered"];
function mastery(m) {
  const p = progressOf(m.id),
    c = STATE.chk[m.id] || {};
  let lvl = 0;
  if (p.done || secDone(m) === secTotal(m)) lvl = 1;
  const qp = quizPct(m);
  if (lvl >= 1 && qp != null && qp >= 0.7) lvl = 2;
  if (lvl >= 2 && c.lastOk === true) lvl = 3;
  if (lvl >= 3) {
    const cs = cardStats(m.id);
    if (cs.n && cs.seeded === cs.n && cs.meanIvl >= 21) lvl = 4;
  }
  if (c.lastOk === false && lvl > 2) lvl = 2;
  return { lvl, name: MASTERY[lvl], dropped: c.lastOk === false && qp != null && qp >= 0.7 };
}
function masteryClass(m) {
  const l = mastery(m).lvl;
  return l ? "l" + l : "";
}
function recordCheck(mid, ok) {
  const c = STATE.chk[mid] || (STATE.chk[mid] = { ok: 0, miss: 0, lastOk: null, at: null });
  if (ok) c.ok++;
  else c.miss++;
  c.lastOk = !!ok;
  c.at = Date.now();
}
function prereqs(m) {
  return (m.requires || [])
    .map(byId)
    .filter(Boolean)
    .map(r => ({ m: r, ms: mastery(r) }));
}
function weakPrereqs(m) {
  return prereqs(m).filter(x => x.ms.lvl < 2);
}

/* ---------- grading, one function per question type ----------
   A response is whatever the UI collected; `ok` is the only thing the rest of the page
   reads. `order` and `match` answer against the item as authored — the UI maps its
   shuffled display back before calling. */
function norm(s) {
  return String(s == null ? "" : s)
    .toLowerCase()
    .replace(/\s+/g, " ")
    .replace(/[.,;:!?"'()]/g, "")
    .trim();
}
function itemOk(item, resp) {
  const t = item.type || "single";
  if (resp == null) return false;
  if (t === "single") return resp === item.answer;
  if (t === "tf") return resp === item.answer;
  if (t === "multi") {
    const a = (item.answer || []).slice().sort().join(","),
      b = (Array.isArray(resp) ? resp : []).slice().sort().join(",");
    return a === b;
  }
  if (t === "numeric") {
    const v = parseFloat(String(resp).replace(/[^\d.\-]/g, ""));
    return !isNaN(v) && Math.abs(v - item.answer) <= (item.tolerance || 0) + 1e-9;
  }
  if (t === "order")
    return (
      Array.isArray(resp) && resp.length === item.options.length && resp.every((v, i) => v === i)
    );
  if (t === "match") return item.pairs.every((_, i) => resp[i] === i);
  if (t === "cloze") {
    const fills = Array.isArray(item.answer) ? item.answer : [item.answer];
    return fills.some(f => norm(f) === norm(resp));
  }
  if (t === "short") return resp === 3 || resp === "correct";
  return false;
}
function correctText(item) {
  const t = item.type || "single";
  if (t === "single") return item.options[item.answer];
  if (t === "tf") return item.answer ? "True" : "False";
  if (t === "multi") return item.answer.map(i => item.options[i]).join(" · ");
  if (t === "numeric")
    return (
      item.answer +
      (item.unit ? " " + item.unit : "") +
      (item.tolerance ? " (±" + item.tolerance + ")" : "")
    );
  if (t === "order") return item.options.map((o, i) => i + 1 + ". " + o).join("  ");
  if (t === "match") return item.pairs.map(p => p[0] + " → " + p[1]).join("  ·  ");
  if (t === "cloze") return Array.isArray(item.answer) ? item.answer[0] : item.answer;
  if (t === "short") return item.model;
  return "";
}
const TYPE_LABEL = {
  single: "Choose one",
  multi: "Choose all that apply",
  tf: "True or false",
  numeric: "Work it out",
  order: "Put in order",
  match: "Match them up",
  cloze: "Fill the blank",
  short: "In your own words",
};

/* deterministic shuffle so a retake shows the same arrangement until the seed changes */
function perm(n, seed) {
  const a = [...Array(n).keys()];
  let x = (seed || 1) * 9301 + 49297;
  for (let i = n - 1; i > 0; i--) {
    x = (x * 9301 + 49297) % 233280;
    const j = Math.floor((x / 233280) * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}
function shuffled(arr) {
  const q = arr.slice();
  for (let i = q.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [q[i], q[j]] = [q[j], q[i]];
  }
  return q;
}

/* seconds → "12m" under an hour, "1.5h" above */
function fmtSpent(sec) {
  const m = Math.round(sec / 60);
  return m < 60 ? m + "m" : fmtH(m);
}
function fmtDay(dayNum) {
  return new Date(dayNum * DAY).toLocaleDateString(undefined, { day: "numeric", month: "short" });
}
function partName(id) {
  const p = DATA.parts.find(x => x.id === id);
  return p ? p.name : "";
}
