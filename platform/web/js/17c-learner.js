/* ---- the learner memory: what the tutor knows about this reader ----

   A course already keeps everything the reader does: every quiz answer, every graded
   exercise, every question asked in the rail. This file turns that record into something
   the tutor can use. Three layers:

   - evidence: one line per sign of what the reader knows or does not - a missed question
     with what they answered, a grader's Missing / Wrong findings, a card that keeps
     lapsing, a checkpoint miss, a question asked, a passage marked as unclear;
   - weak spots: the modules the evidence points at, scored without a model;
   - the brief: what the tutor writes from the evidence - a paragraph on how this reader
     thinks and what keeps going wrong, plus one gap per misconception with a question
     that would test whether it has closed.

   The brief and the open gaps go into every tutor prompt (`learnerContext`) and ahead of
   the suggested questions in the rail (`gapChips`), so the chat works on the gaps rather
   than repeating the section.

   Stored in STATE.learner, so it syncs to Studio and travels through Backup / restore:
     { brief, strengths, gaps, closed, at, events }
   A gap is { id, mid, topic, why, ask, status, at }: `mid` the module it sits in, `topic`
   the concept, `why` what the evidence shows, `ask` a question that tests it, `status`
   "open" or "closed". `closed` maps a gap id to when the reader dismissed it, so neither a
   merge nor a refresh can bring it back. `events` is how much evidence there was when the
   brief was written, which is how staleness is judged. */
function learnerBlank() {
  return { brief: "", strengths: [], gaps: [], closed: {}, at: null, events: 0 };
}
function learner() {
  if (!STATE.learner) STATE.learner = learnerBlank();
  return STATE.learner;
}
/* Two copies: the brief written later wins, and a gap closed on either side stays closed. */
function mergeLearner(a, b) {
  const x = Object.assign(learnerBlank(), a || {}),
    y = Object.assign(learnerBlank(), b || {});
  const out = Object.assign({}, (x.at || 0) > (y.at || 0) ? x : y);
  out.closed = Object.assign({}, x.closed || {}, y.closed || {});
  out.gaps = (out.gaps || []).map(g =>
    out.closed[g.id] ? Object.assign({}, g, { status: "closed" }) : g
  );
  return out;
}

/* ---- evidence ----
   Each entry is { kind, mid, sec, at, text, weight }. `weight` is how much it says about a
   gap: a "certain" wrong answer weighs more than a guess, a question still open weighs
   more than one the tutor answered. `sec` is the section when it is known (chats and
   marks). A quiz entry also carries `q`, and a graded one `ask`, for the chips. */
function learnerEvidence() {
  const out = [];
  MODS.forEach(m => {
    const p = STATE.progress[m.id];
    if (!p) return;
    quizEvidence(m, p, out);
    gradeEvidence(m, p, out);
  });
  lapseEvidence(out);
  checkpointEvidence(out);
  chatEvidence(out);
  markEvidence(out);
  sheetEvidence(out);
  return out.sort((a, b) => (b.at || 0) - (a.at || 0));
}
function quizEvidence(m, p, out) {
  const q = p.quiz;
  if (!q || !Array.isArray(q.a)) return;
  q.a.forEach((st, i) => {
    const it = m.assess.quiz[i];
    if (!st || !st.answered || !it) return;
    const at = st.at || p.doneAt || 0;
    if (st.ok && !st.hinted) {
      if (st.conf === 1)
        out.push({
          kind: "guess",
          mid: m.id,
          sec: null,
          at,
          weight: 1,
          q: it.q,
          text: `Guessed right on "${it.q}"`,
        });
      return;
    }
    const conf = st.conf === 3 ? "certain" : st.conf === 2 ? "fairly sure" : "guessing";
    const findings = st.ai ? " " + graderFindings(st.ai.text) : "";
    out.push({
      kind: "quiz",
      mid: m.id,
      sec: null,
      at,
      weight: st.ok ? 1 : st.conf === 3 ? 3 : 2,
      q: it.q,
      qi: i,
      answer: correctText(it) + (it.why ? ". " + it.why : ""),
      text: st.ok
        ? `Needed ${st.hinted} hint${st.hinted > 1 ? "s" : ""} on "${it.q}"`
        : `Missed "${it.q}" (${conf}): answered ${respText(it, st.resp)}; correct: ${correctText(it)}.${findings}`,
    });
  });
}
function gradeEvidence(m, p, out) {
  const push = (label, fb, key) => {
    if (!fb || !fb.verdict) return;
    const ok = fb.verdict === "correct";
    out.push({
      kind: "graded",
      mid: m.id,
      sec: null,
      key,
      label,
      verdict: fb.verdict,
      at: fb.at || 0,
      weight: ok ? 0 : fb.verdict === "wrong" ? 3 : 2,
      ask: askYourself(fb.text),
      text: ok ? `${label}: correct` : `${label}: ${fb.verdict}. ${graderFindings(fb.text)}`.trim(),
    });
  };
  Object.keys(p.elabFb || {}).forEach(i => {
    const prompt = (m.assess.elaborate || [])[i] || "Elaborate " + (+i + 1);
    push(`Elaborate "${prompt.slice(0, 80)}"`, p.elabFb[i], "e:" + i);
  });
  if (p.transfer && p.transfer.fb) push("Apply exercise", p.transfer.fb, "t");
  if (p.transfer && p.transfer.rp) push("Role-play", p.transfer.rp, "rp");
}
/* The first miss is already a quiz entry; a card that keeps lapsing in review is a
   second, stronger sign. */
function lapseEvidence(out) {
  Object.keys(STATE.mcards || {}).forEach(k => {
    const mc = STATE.mcards[k],
      st = STATE.cards[k] || {};
    if (!mc || (st.lapses || 0) < 2) return;
    out.push({
      kind: "lapse",
      mid: mc.mid,
      sec: null,
      k,
      answer: String(mc.back || ""),
      at: mc.made || 0,
      weight: 2,
      q: String(mc.front || "").split("\n")[0],
      text: `Still missed in review, ${st.lapses} times: "${String(mc.front || "").split("\n")[0]}"`,
    });
  });
}
function checkpointEvidence(out) {
  (STATE.cpHist || []).forEach(h => {
    Object.keys(h.byMod || {}).forEach(mid => {
      const b = h.byMod[mid];
      if (!b || !b.n || b.ok >= b.n) return;
      out.push({
        kind: "checkpoint",
        mid,
        sec: null,
        at: h.at || 0,
        weight: 2,
        text: `Checkpoint weeks later: ${b.ok} of ${b.n} right on ${mid}`,
      });
    });
  });
}
function chatEvidence(out) {
  Object.values(convos()).forEach(c => {
    if (c.kind === "rp") return;
    (c.msgs || []).forEach(x => {
      if (x.r !== "u" || TOOL_CHIPS.some(t => t[1] === x.t)) return;
      out.push({
        kind: "asked",
        mid: c.mid,
        sec: x.sec != null ? x.sec : c.sec,
        at: x.ts || 0,
        weight: 1,
        text: `Asked: ${String(x.t).slice(0, 200)}`,
      });
    });
  });
}
function markEvidence(out) {
  allMarks().forEach(mk => {
    if (mk.status !== "open") return;
    out.push({
      kind: "open",
      mid: mk.mid,
      sec: mk.sec,
      at: mk.ts || 0,
      weight: 2,
      text: `Marked as unclear: "${String(mk.text || "").slice(0, 120)}"${mk.q ? " - " + mk.q : ""}`,
    });
  });
}
function sheetEvidence(out) {
  const sheets = STATE.sheets || {};
  Object.keys(sheets).forEach(slug => {
    const fb = sheets[slug] && sheets[slug]._fb;
    if (!fb || !fb.verdict || fb.verdict === "correct") return;
    const t = (DATA.library.templates || []).find(x => x.slug === slug);
    out.push({
      kind: "graded",
      mid: t && t.uses && t.uses[0] ? t.uses[0] : null,
      sec: null,
      at: fb.at || 0,
      weight: fb.verdict === "wrong" ? 2 : 1,
      ask: askYourself(fb.text),
      text: `Worksheet "${t ? t.title : slug}": ${fb.verdict}. ${graderFindings(fb.text)}`.trim(),
    });
  });
}
/* The Missing and Wrong lines of a grader reply (see verdictFormat), in one string. */
function graderFindings(text) {
  const pick = label => {
    const m = String(text || "").match(
      new RegExp("\\*\\*" + label + "\\*\\*\\s*[—–-]?\\s*([^\\n]+)", "i")
    );
    const v = m ? m[1].trim() : "";
    return /^nothing\.?$/i.test(v) ? "" : v;
  };
  const missing = pick("Missing"),
    wrong = pick("Wrong");
  return [missing && "Missing: " + missing, wrong && "Wrong: " + wrong].filter(Boolean).join(" ");
}
function askYourself(text) {
  const m = String(text || "").match(/\*\*Ask yourself\*\*\s*[—–-]?\s*([^\n]+)/i);
  return m ? m[1].trim() : "";
}

/* ---- what the evidence says without a model ---- */
function learnerEventCount() {
  return learnerEvidence().length;
}
/* The modules the evidence points at, strongest first: { m, score, lines }. */
function weakSpots() {
  const by = {};
  learnerEvidence().forEach(e => {
    if (!e.mid || !e.weight) return;
    const w = by[e.mid] || (by[e.mid] = { m: byId(e.mid), score: 0, lines: [] });
    w.score += e.weight;
    if (w.lines.length < 4) w.lines.push(e.text);
  });
  return Object.values(by)
    .filter(w => w.m && w.score >= 2)
    .sort((a, b) => b.score - a.score);
}
function openGaps() {
  const L = learner();
  return (L.gaps || []).filter(g => g.status !== "closed" && !L.closed[g.id]);
}
/* The gaps that touch a module: its own, and those of the modules it builds on. */
function gapsFor(mid) {
  const m = byId(mid);
  const near = new Set([mid].concat((m && m.requires) || []));
  return openGaps().filter(g => near.has(g.mid));
}
function closeGap(id) {
  const L = learner();
  const g = (L.gaps || []).find(x => x.id === id);
  if (g) g.status = "closed";
  L.closed[id] = Date.now();
  save();
}
function reopenGap(id) {
  const L = learner();
  const g = (L.gaps || []).find(x => x.id === id);
  if (g) g.status = "open";
  delete L.closed[id];
  save();
}

/* ---- what the tutor is told ---- */
function learnerContext(mid) {
  const L = learner();
  const parts = [];
  if (L.brief) parts.push(L.brief);
  const here = gapsFor(mid),
    rest = openGaps()
      .filter(g => !here.includes(g))
      .slice(0, 3);
  const gapLine = g => `- ${g.topic} (${g.mid}): ${g.why}`;
  if (here.length) parts.push("Gaps that touch this module:\n" + here.map(gapLine).join("\n"));
  if (rest.length) parts.push("Other open gaps:\n" + rest.map(gapLine).join("\n"));
  const recent = learnerEvidence()
    .filter(e => e.mid === mid && e.weight >= 2)
    .slice(0, 4);
  if (recent.length)
    parts.push("What went wrong in this module:\n" + recent.map(e => "- " + e.text).join("\n"));
  if (!parts.length) return "";
  return `
What you know about this learner from their work so far:
"""
${parts.join("\n\n").slice(0, LEARNER.promptChars)}
"""
Use it. When a question touches a gap, close the gap rather than only answering: name the misconception, correct it, and end with one short question that checks it landed. Never recite this record back to them.`;
}
/* ---- gap items: what a module's "Close the gaps" step drills ----
   One item per thing the record says went wrong in this module, each with a question:
   { key, source, topic, why, ask, answer? }. `key` is stable across renders and saves -
   a brief gap's id, "q:<index>" for a quiz miss, "l:<card>" for a lapsing card, the
   grader key for an exercise - so progressOf(mid).gapWork can hold the reader's answer
   and whether it is closed. `answer` is what the grader may judge against. */
function gapItems(mid) {
  const out = [];
  const seen = new Set();
  const add = it => {
    if (!it.ask || seen.has(it.key)) return;
    seen.add(it.key);
    out.push(it);
  };
  const short = q => (q.length > 70 ? q.slice(0, 70) + "…" : q);
  (learner().gaps || [])
    .filter(g => g.mid === mid)
    .forEach(g =>
      add({ key: g.id, source: "brief", topic: g.topic, why: g.why, ask: g.ask, gap: g })
    );
  learnerEvidence()
    .filter(e => e.mid === mid)
    .forEach(e => {
      if (e.kind === "quiz" && e.q)
        add({
          key: "q:" + e.qi,
          source: "quiz",
          topic: short(e.q),
          why: e.text,
          ask: `${e.q} Give the answer and say why it is right.`,
          answer: e.answer,
        });
      else if (e.kind === "lapse" && e.q)
        add({
          key: "l:" + e.k,
          source: "lapse",
          topic: short(e.q),
          why: e.text,
          ask: `${e.q} Answer from memory, then explain it a different way than the course does.`,
          answer: e.answer,
        });
      else if (e.kind === "graded" && e.key && e.ask && e.verdict !== "correct")
        add({
          key: e.key,
          source: "graded",
          topic: e.label,
          why: e.text,
          ask: e.ask,
          verdict: e.verdict,
        });
    });
  return out;
}
function gapWorkOf(mid, key) {
  const p = progressOf(mid);
  if (!p.gapWork[key]) p.gapWork[key] = { answer: "", closed: false };
  return p.gapWork[key];
}
function gapItemClosed(mid, it) {
  if (it.source === "brief" && it.gap && (it.gap.status === "closed" || learner().closed[it.key]))
    return true;
  const w = progressOf(mid).gapWork[it.key];
  return !!(w && w.closed);
}
function openGapItems(mid) {
  return gapItems(mid).filter(it => !gapItemClosed(mid, it));
}
function closeGapItem(mid, it, how) {
  const w = gapWorkOf(mid, it.key);
  w.closed = true;
  w.closedAt = Date.now();
  w.how = how;
  if (it.source === "brief") closeGap(it.key);
  else save();
}
function reopenGapItem(mid, key) {
  const w = gapWorkOf(mid, key);
  w.closed = false;
  const it = gapItems(mid).find(x => x.key === key);
  if (it && it.source === "brief") reopenGap(key);
  else save();
  if (route.view === "m" && route.id === mid) renderStep(byId(mid), 5);
}
/* Suggested questions that come from the open gaps, ahead of the section's own. */
function gapChips(mid) {
  const out = [];
  openGapItems(mid).forEach(it => {
    const q =
      it.source === "quiz"
        ? `I got this wrong: "${it.topic}". Where did my thinking go astray?`
        : it.source === "lapse"
          ? `I keep missing this in review: "${it.topic}". Explain it a different way.`
          : it.ask;
    if (!out.some(x => x.toLowerCase() === q.toLowerCase())) out.push(q);
  });
  return out.slice(0, LEARNER.gapChips);
}

/* ---- the brief: the tutor rewrites the memory from the evidence ---- */
const learnerRun = {
  busy: false, // a brief is being written
};
function learnerStale() {
  const L = learner(),
    n = learnerEventCount();
  if (!n) return false;
  if (!L.at) return n >= LEARNER.refreshAfterEvents;
  const grown = n - (L.events || 0) >= LEARNER.refreshAfterEvents;
  return grown && Date.now() - L.at >= LEARNER.refreshMinutes * 60000;
}
/* Called after a quiz, a grade or a checkpoint: a refresh only when enough has happened. */
function maybeRefreshLearner() {
  if (learnerRun.busy || connMode() === "none" || !learnerStale()) return;
  refreshLearner(true);
}
function learnerSystem() {
  return `${CFG.tutorPersona} You keep the memory of one ${CFG.audience} working through a ${CFG.hours}-hour ${CFG.subject} course: what they understand, what they get wrong, and how they think. You are given the record of their work - missed questions with what they answered, what a grader found missing, the questions they asked - and the memory as it stands. Rewrite the memory.

Reply with JSON only, no fences, in exactly this shape:
{"brief": "...", "strengths": ["..."], "gaps": [{"id": "g1", "mid": "M03", "topic": "...", "why": "...", "ask": "..."}], "closed": ["g2"]}

brief: under 120 words of plain prose for the tutor who reads it before every answer: what this reader has grasped, the misconceptions that keep showing, how they tend to answer (guessing, overconfident, terse, thorough). No praise, no advice to the reader, no module ids.
strengths: up to 4 short lines, only what the evidence shows.
gaps: up to ${LEARNER.maxGaps}, most important first. Each names the concept (not the module), says in one sentence what the evidence shows, and gives one question under 100 characters that a tutor could ask to test whether the gap has closed. mid is the id of the module the gap sits in, from the list given. Keep the id of an existing gap that is still open; give a new one a fresh id.
closed: ids of existing gaps the recent evidence shows are now closed. A gap you leave out of "gaps" counts as closed too.`;
}
function learnerRecord() {
  const L = learner();
  const mods = MODS.map(m => `${m.id} ${m.title}`).join("\n");
  const memory = L.brief
    ? `Memory as it stands:\n${L.brief}\n\nOpen gaps:\n${
        openGaps()
          .map(g => `${g.id} [${g.mid}] ${g.topic}: ${g.why}`)
          .join("\n") || "none"
      }`
    : "No memory yet: this is the first time.";
  const lines = learnerEvidence()
    .slice(0, LEARNER.recentEvidence)
    .map(
      e =>
        `[${e.mid || "-"}${e.at ? " " + new Date(e.at).toISOString().slice(0, 10) : ""}] ${e.text}`
    )
    .join("\n");
  const anchor = STATE.biz ? `\n${(CFG.anchor || {}).label}: ${STATE.biz}\n` : "";
  return `Modules:\n${mods}\n${anchor}\n${memory}\n\nThe record, newest first:\n${lines}`.slice(
    0,
    LEARNER.evidenceChars
  );
}
/* Model output is trusted for prose and distrusted for structure: every field is checked. */
function parseLearnerReply(text) {
  const raw = String(text || "");
  const start = raw.indexOf("{"),
    end = raw.lastIndexOf("}");
  if (start < 0 || end <= start) return null;
  let j;
  try {
    j = JSON.parse(raw.slice(start, end + 1));
  } catch (e) {
    return null;
  }
  if (!j || typeof j !== "object") return null;
  const str = v => (typeof v === "string" ? v.trim() : "");
  const list = v => (Array.isArray(v) ? v : []);
  const gaps = list(j.gaps)
    .map((g, i) => ({
      id: str(g && g.id) || "g" + Date.now().toString(36) + i,
      mid: str(g && g.mid),
      topic: str(g && g.topic).slice(0, 90),
      why: str(g && g.why).slice(0, 300),
      ask: str(g && g.ask).slice(0, 160),
    }))
    .filter(g => g.topic && byId(g.mid))
    .slice(0, LEARNER.maxGaps);
  return {
    brief: str(j.brief).slice(0, 1200),
    strengths: list(j.strengths).map(str).filter(Boolean).slice(0, 4),
    gaps,
    closed: list(j.closed).map(str).filter(Boolean),
  };
}
function applyLearnerReply(reply) {
  const L = learner(),
    now = Date.now();
  const before = {};
  (L.gaps || []).forEach(g => (before[g.id] = g));
  const kept = new Set(reply.gaps.map(g => g.id));
  const gaps = reply.gaps.map(g => {
    const old = before[g.id];
    const closed = !!L.closed[g.id];
    return Object.assign({}, g, { status: closed ? "closed" : "open", at: old ? old.at : now });
  });
  Object.values(before).forEach(g => {
    if (kept.has(g.id)) return;
    gaps.push(Object.assign({}, g, { status: "closed" }));
  });
  reply.closed.forEach(id => {
    const g = gaps.find(x => x.id === id);
    if (g) g.status = "closed";
  });
  L.brief = reply.brief || L.brief;
  L.strengths = reply.strengths;
  L.gaps = gaps.slice(0, LEARNER.maxGaps * 3);
  L.at = now;
  L.events = learnerEventCount();
  save();
}
async function refreshLearner(quiet) {
  if (learnerRun.busy) return false;
  if (connMode() === "none") {
    if (!quiet) toast("Not connected — open Settings");
    return false;
  }
  if (!learnerEventCount()) {
    if (!quiet) toast("Nothing to learn from yet — answer a quiz or ask a question first");
    return false;
  }
  learnerRun.busy = true;
  if (route.view === "learner") viewLearner();
  let ok = false;
  try {
    const text = await askBridge(learnerSystem(), [{ role: "user", content: learnerRecord() }]);
    const reply = parseLearnerReply(text);
    if (reply) {
      applyLearnerReply(reply);
      ok = true;
      if (!quiet) toast("Your profile is up to date");
    } else if (!quiet) toast("Could not read the reply — try again");
  } catch (e) {
    if (!quiet) toast((e && e.message) || "The tutor did not answer");
  }
  learnerRun.busy = false;
  if (route.view === "learner") viewLearner();
  else if (route.view === "home") viewHome();
  else if (route.view === "m" && railOpen()) renderSuggest();
  return ok;
}
