/* ---------- checkpoints: mixed, cumulative, the only score that means anything ----------
   A part checkpoint draws two questions from every module in the part you have finished;
   the course challenge draws from everything. Questions are shuffled across modules so
   nothing is answered by remembering which module you are in. Results feed mastery: a hit
   makes a module Proficient, a miss drops it back to Practised. */
function eligibleFor(kind, pid) {
  return MODS.filter(
    m => (kind === "course" || m.part === pid) && (isDone(m) || quizPct(m) != null)
  );
}
function lastCheck(kind, pid) {
  const hist = (STATE.cpHist || []).filter(
    h => h.kind === kind && (kind === "course" || h.pid === pid)
  );
  return hist.length ? hist[hist.length - 1] : null;
}
function checkOffers() {
  const out = [];
  DATA.parts.forEach(p => {
    const ms = MODS.filter(m => m.part === p.id);
    if (!ms.length || !ms.every(isDone)) return;
    const last = lastCheck("part", p.id);
    if (
      !last ||
      todayNum() - last.day >= STUDY.checkpointGapDays ||
      last.score / last.total < STUDY.checkpointPassPct / 100
    )
      out.push({ kind: "part", pid: p.id, label: "Checkpoint · " + p.name });
  });
  if (MODS.every(isDone)) {
    const last = lastCheck("course");
    if (!last || todayNum() - last.day >= STUDY.checkpointGapDays)
      out.push({ kind: "course", pid: "", label: "Course challenge" });
  }
  return out;
}
function startCheckpoint(kind, pid) {
  const mods = eligibleFor(kind, pid);
  if (mods.length < 2) {
    toast("Finish at least two modules first");
    return;
  }
  const per = kind === "course" ? (mods.length > 15 ? 1 : 2) : 2;
  let items = [];
  mods.forEach(m => {
    const pool = m.assess.quiz
      .map((it, qi) => ({ mid: m.id, qi }))
      .filter(x => (m.assess.quiz[x.qi].type || "single") !== "short");
    items = items.concat(shuffled(pool).slice(0, per));
  });
  items = shuffled(items).slice(0, 40);
  STATE.cp = {
    kind,
    pid,
    items,
    i: 0,
    a: [],
    finished: false,
    seed: Math.floor(Math.random() * 1e6),
    started: Date.now(),
    recorded: false,
  };
  save();
  go("#/check/run");
}
function viewCheck() {
  const v = $("#view");
  if (route.id === "run") {
    if (!STATE.cp) return go("#/check");
    if (STATE.cp.finished) return cpResults();
    const cp = STATE.cp;
    v.innerHTML = `<div class="wrap"><div class="readhead"><div class="crumb">${cp.kind === "course" ? "Course challenge" : "Checkpoint · " + esc(partName(cp.pid))} · ${cp.items.length} questions across ${new Set(cp.items.map(x => x.mid)).size} modules</div>
      <h2>${cp.kind === "course" ? "Everything, mixed" : esc(partName(cp.pid)) + ", mixed"}</h2>
      <p class="sub">No module heading to lean on. Answer from what you actually remember; a hint or a miss drops that module back to Practised.</p></div>
      <div id="cpbody"></div>
      <p class="centered gap-top"><button class="btn sm" onclick="askAbandonCheck()">Abandon this checkpoint</button></p></div>`;
    QUIZ = {
      kind: "cp",
      host: "#cpbody",
      qs: cp,
      items: cp.items.map(x => ({ mid: x.mid, qi: x.qi, it: byId(x.mid).assess.quiz[x.qi] })),
      onDone: cpFinish,
    };
    drawQuiz();
    return;
  }
  // the hub
  let h = `<div class="wrap-wide"><h2 class="big">Checkpoints</h2>
    <p class="lede" data-help="${esc(help("checkpoint"))}">A module quiz measures recognition ten minutes after reading. A checkpoint asks the same questions weeks later, mixed with everything else, and that is the number that predicts whether you can use it. Take one when a part is done, and again every couple of weeks.</p>
    ${STATE.cp && !STATE.cp.finished ? `<div class="card accented gap-bottom"><h3 class="eyebrow">In progress</h3><p class="sub gap-bottom">${STATE.cp.kind === "course" ? "Course challenge" : "Checkpoint · " + esc(partName(STATE.cp.pid))} · question ${STATE.cp.i + 1} of ${STATE.cp.items.length}</p><div class="rowline wrapped"><button class="btn primary" onclick="go('#/check/run')">Continue</button><button class="btn" onclick="askAbandonCheck()">Abandon</button></div></div>` : ""}
    <div class="grid g2">`;
  DATA.parts.forEach(p => {
    const ms = MODS.filter(m => m.part === p.id),
      el = eligibleFor("part", p.id),
      last = lastCheck("part", p.id);
    h += `<div class="card"><h3 class="eyebrow">${esc(p.name)}</h3>
      <p class="sub gap-bottom">${el.length} of ${ms.length} modules ready${last ? ` · last: ${Math.round((last.score / last.total) * 100)}% on ${fmtDay(last.day)}` : " · never taken"}</p>
      <div class="rowline wrapped gap-bottom">${ms.map(m => `<span class="chip lvl l${mastery(m).lvl}" data-help="${mastery(m).name} — ${esc(help(mastery(m).name))}">${m.id}</span>`).join("")}</div>
      <button class="btn ${el.length >= 2 ? "primary" : ""}" ${el.length >= 2 ? "" : 'disabled data-help="Two modules have to be Practised before a checkpoint can mix them"'} onclick="startCheckpoint('part','${p.id}')">Start · ${el.length * 2} questions</button></div>`;
  });
  const elc = eligibleFor("course"),
    lastc = lastCheck("course");
  h += `<div class="card warmcard"><h3 class="eyebrow warnnote">Course challenge</h3>
    <p class="sub gap-bottom">${elc.length} of ${MODS.length} modules ready${lastc ? ` · last: ${Math.round((lastc.score / lastc.total) * 100)}% on ${fmtDay(lastc.day)}` : " · never taken"}</p>
    <p class="sub gap-bottom">One or two questions from every module you have finished, in no order at all. This is the exam the course would set if it could.</p>
    <button class="btn ${elc.length >= 2 ? "primary" : ""}" ${elc.length >= 2 ? "" : 'disabled data-help="Two modules have to be Practised before a course challenge can mix them"'} onclick="startCheckpoint('course','')">Start · ${Math.min(40, elc.length * (elc.length > 15 ? 1 : 2))} questions</button></div>`;
  h += `</div>`;
  const hist = (STATE.cpHist || []).slice().reverse().slice(0, 12);
  if (hist.length) {
    h += `<div class="card gap-top"><h3 class="eyebrow">History</h3>${hist.map(x => `<div class="calrow"><span>${fmtDay(x.day)}</span><span>${x.kind === "course" ? "Course challenge" : esc(partName(x.pid))}</span><span class="score ${x.score / x.total >= 0.8 ? "ok" : x.score / x.total >= 0.6 ? "warm" : "bad"}">${Math.round((x.score / x.total) * 100)}%</span></div>`).join("")}</div>`;
  }
  h += `</div>`;
  v.innerHTML = h;
}
/* Abandoning throws away every answer given so far, and there is no way back to them. */
function askAbandonCheck() {
  confirmModal(
    "Abandon this checkpoint?",
    "The answers you have given are thrown away and nothing is recorded. You can start a fresh one whenever you like.",
    "Abandon it",
    abandonCheck,
    true
  );
}
function abandonCheck() {
  STATE.cp = null;
  save();
  go("#/check");
  toast("Checkpoint abandoned");
}
function cpFinish() {
  const cp = STATE.cp;
  if (!cp.recorded) {
    const a = cp.a.filter(Boolean);
    const byMod = {};
    cp.items.forEach((x, i) => {
      const st = cp.a[i] || {};
      const b = byMod[x.mid] || (byMod[x.mid] = { ok: 0, n: 0 });
      b.n++;
      if (st.ok && !st.hinted) b.ok++;
    });
    STATE.cpHist.push({
      kind: cp.kind,
      pid: cp.pid,
      at: Date.now(),
      day: todayNum(),
      score: a.filter(x => x.ok).length,
      total: cp.items.length,
      a: a.map(x => ({ answered: true, ok: !!x.ok, conf: x.conf })),
      byMod,
    });
    STATE.cpHist = STATE.cpHist.slice(-STUDY.checkpointHistory);
    cp.recorded = true;
    save();
    markDay();
    maybeRefreshLearner();
  }
  cpResults();
}
function cpResults() {
  const cp = STATE.cp,
    hist = STATE.cpHist[STATE.cpHist.length - 1] || { byMod: {}, score: 0, total: 1 };
  const pct = Math.round((hist.score / hist.total) * 100);
  const mods = Object.keys(hist.byMod).map(byId).filter(Boolean);
  const slipped = mods.filter(m => hist.byMod[m.id].ok < hist.byMod[m.id].n);
  const verdict =
    pct >= 80
      ? "That is retention, not recognition. The modules you held are now Proficient."
      : pct >= 60
        ? "Most of it held. The modules that slipped are back to Practised — their cards and mistakes will bring them round."
        : "A lot slipped, which is what a checkpoint is for: better to find out here than the first time you need it. Work the mistakes, then retake in a week.";
  const score = scoreBlock({
    eyebrow: cp.kind === "course" ? "Course challenge" : "Checkpoint · " + partName(cp.pid),
    pct,
    line: `${hist.score} of ${hist.total} · ${mods.length} modules`,
    verdict,
    overconf: (hist.a || []).filter(x => x && x.conf === 3 && !x.ok).length,
    actions: `${mistakeCount() ? `<button class="btn primary" onclick="go('#/review/mistakes')">Fix the mistakes (${mistakeCount()})</button>` : ""}
      <button class="btn" onclick="go('#/check')">Checkpoints</button>
      <button class="btn" onclick="go('#/home')">Dashboard</button>`,
  });
  $("#view").innerHTML = `<div class="wrap">${score}
    <div class="card gap-top"><h3 class="eyebrow">Module by module</h3>
      ${mods
        .map(m => {
          const b = hist.byMod[m.id],
            ms = mastery(m);
          return `<a class="mrow boxed" href="#/m/${m.id}" data-help="${ms.name} — ${esc(help(ms.name))}"><span class="dot ${masteryClass(m)}"></span><span class="code">${m.id}</span><span class="t">${esc(m.short)}</span><span class="score ${b.ok === b.n ? "ok" : "bad"}">${b.ok}/${b.n}</span><span class="tag">${ms.name}</span></a>`;
        })
        .join("")}
      ${slipped.length ? `<p class="sub gap-top">Slipped: ${slipped.map(m => m.id).join(", ")}. Re-read just the section behind each miss, not the whole module.</p>` : ""}
    </div></div>`;
  renderSidebar();
}
