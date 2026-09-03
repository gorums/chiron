/* ---------- checkpoints: mixed, cumulative, the only score that means anything ----------
   A part checkpoint draws two questions from every module in the part you have finished;
   the course challenge draws from everything. Questions are shuffled across modules so
   nothing is answered by remembering which module you are in. Results feed mastery: a hit
   makes a module Proficient, a miss drops it back to Practised. */
const CHECK_GAP_DAYS = 14;
function eligibleFor(kind, pid) {
  return MODS.filter(m => (kind === "course" || m.part === pid) && (isDone(m) || quizPct(m) != null));
}
function lastCheck(kind, pid) {
  const hist = (S.cpHist || []).filter(h => h.kind === kind && (kind === "course" || h.pid === pid));
  return hist.length ? hist[hist.length - 1] : null;
}
function checkOffers() {
  const out = [];
  DATA.parts.forEach(p => {
    const ms = MODS.filter(m => m.part === p.id);
    if (!ms.length || !ms.every(isDone)) return;
    const last = lastCheck("part", p.id);
    if (!last || todayNum() - last.day >= CHECK_GAP_DAYS || last.score / last.total < .8) out.push({ kind: "part", pid: p.id, label: "Checkpoint · " + p.name });
  });
  if (MODS.every(isDone)) {
    const last = lastCheck("course");
    if (!last || todayNum() - last.day >= CHECK_GAP_DAYS) out.push({ kind: "course", pid: "", label: "Course challenge" });
  }
  return out;
}
function startCheckpoint(kind, pid) {
  const mods = eligibleFor(kind, pid);
  if (mods.length < 2) { toast("Finish at least two modules first"); return; }
  const per = kind === "course" ? (mods.length > 15 ? 1 : 2) : 2;
  let items = [];
  mods.forEach(m => {
    const pool = m.assess.quiz.map((it, qi) => ({ mid: m.id, qi })).filter(x => (m.assess.quiz[x.qi].type || "single") !== "short");
    items = items.concat(shuffled(pool).slice(0, per));
  });
  items = shuffled(items).slice(0, 40);
  S.cp = { kind, pid, items, i: 0, a: [], finished: false, seed: Math.floor(Math.random() * 1e6), started: Date.now(), recorded: false };
  save(); go("#/check/run");
}
function viewCheck() {
  const v = $("#view");
  if (route.id === "run") {
    if (!S.cp) return go("#/check");
    if (S.cp.finished) return cpResults();
    const cp = S.cp;
    v.innerHTML = `<div class="wrap"><div class="readhead"><div class="crumb">${cp.kind === "course" ? "Course challenge" : "Checkpoint · " + esc(partName(cp.pid))} · ${cp.items.length} questions across ${new Set(cp.items.map(x => x.mid)).size} modules</div>
      <h2>${cp.kind === "course" ? "Everything, mixed" : esc(partName(cp.pid)) + ", mixed"}</h2>
      <p class="sub">No module heading to lean on. Answer from what you actually remember; a hint or a miss drops that module back to Practised.</p></div>
      <div id="cpbody"></div>
      <p style="text-align:center;margin-top:18px"><button class="btn ghost sm" onclick="abandonCheck()">Abandon this checkpoint</button></p></div>`;
    QZ = { kind: "cp", host: "#cpbody", qs: cp,
           items: cp.items.map(x => ({ mid: x.mid, qi: x.qi, it: byId(x.mid).assess.quiz[x.qi] })),
           onDone: cpFinish };
    drawQuiz();
    return;
  }
  // the hub
  let h = `<div class="wrap-wide"><h2 class="big">Checkpoints</h2>
    <p class="sub" style="margin-bottom:22px">A module quiz measures recognition ten minutes after reading. A checkpoint asks the same questions weeks later, mixed with everything else, and that is the number that predicts whether you can use it. Take one when a part is done, and again every couple of weeks.</p>
    ${S.cp && !S.cp.finished ? `<div class="card" style="margin-bottom:18px;border-color:var(--accent)"><p class="eyebrow">In progress</p><p class="sub" style="margin-bottom:10px">${S.cp.kind === "course" ? "Course challenge" : "Checkpoint · " + esc(partName(S.cp.pid))} · question ${S.cp.i + 1} of ${S.cp.items.length}</p><button class="btn primary" onclick="go('#/check/run')">Continue →</button> <button class="btn ghost" onclick="abandonCheck()">Abandon</button></div>` : ""}
    <div class="grid g2">`;
  DATA.parts.forEach(p => {
    const ms = MODS.filter(m => m.part === p.id), el = eligibleFor("part", p.id), last = lastCheck("part", p.id);
    h += `<div class="card"><p class="eyebrow">${esc(p.name)}</p>
      <p class="sub" style="margin-bottom:10px">${el.length} of ${ms.length} modules ready${last ? ` · last: ${Math.round(last.score / last.total * 100)}% on ${fmtDay(last.day)}` : " · never taken"}</p>
      <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:12px">${ms.map(m => `<span class="chip lvl l${mastery(m).lvl}" title="${mastery(m).name}">${m.id}</span>`).join("")}</div>
      <button class="btn ${el.length >= 2 ? "primary" : ""}" ${el.length >= 2 ? "" : "disabled"} onclick="startCheckpoint('part','${p.id}')">Start · ${el.length * 2} questions</button></div>`;
  });
  const elc = eligibleFor("course"), lastc = lastCheck("course");
  h += `<div class="card" style="border-color:var(--warm)"><p class="eyebrow" style="color:var(--warm)">Course challenge</p>
    <p class="sub" style="margin-bottom:10px">${elc.length} of ${MODS.length} modules ready${lastc ? ` · last: ${Math.round(lastc.score / lastc.total * 100)}% on ${fmtDay(lastc.day)}` : " · never taken"}</p>
    <p class="sub" style="margin-bottom:12px">One or two questions from every module you have finished, in no order at all. This is the exam the course would set if it could.</p>
    <button class="btn ${elc.length >= 2 ? "primary" : ""}" ${elc.length >= 2 ? "" : "disabled"} onclick="startCheckpoint('course','')">Start · ${Math.min(40, elc.length * (elc.length > 15 ? 1 : 2))} questions</button></div>`;
  h += `</div>`;
  const hist = (S.cpHist || []).slice().reverse().slice(0, 12);
  if (hist.length) {
    h += `<div class="card" style="margin-top:18px"><p class="eyebrow">History</p>${hist.map(x => `<div class="calrow"><span>${fmtDay(x.day)}</span><span>${x.kind === "course" ? "Course challenge" : esc(partName(x.pid))}</span><span style="text-align:right;color:${x.score / x.total >= .8 ? "var(--ok)" : x.score / x.total >= .6 ? "var(--warm)" : "var(--bad)"}">${Math.round(x.score / x.total * 100)}%</span></div>`).join("")}</div>`;
  }
  h += `</div>`;
  v.innerHTML = h;
}
function abandonCheck() { S.cp = null; save(); go("#/check"); toast("Checkpoint abandoned"); }
function cpFinish() {
  const cp = S.cp;
  if (!cp.recorded) {
    const a = cp.a.filter(Boolean);
    const byMod = {};
    cp.items.forEach((x, i) => { const st = cp.a[i] || {}; const b = byMod[x.mid] || (byMod[x.mid] = { ok: 0, n: 0 }); b.n++; if (st.ok && !st.hinted) b.ok++; });
    S.cpHist.push({ kind: cp.kind, pid: cp.pid, at: Date.now(), day: todayNum(), score: a.filter(x => x.ok).length, total: cp.items.length,
                    a: a.map(x => ({ answered: true, ok: !!x.ok, conf: x.conf })), byMod });
    S.cpHist = S.cpHist.slice(-60);
    cp.recorded = true; save(); markDay();
  }
  cpResults();
}
function cpResults() {
  const cp = S.cp, hist = S.cpHist[S.cpHist.length - 1] || { byMod: {}, score: 0, total: 1 };
  const pct = Math.round(hist.score / hist.total * 100);
  const mods = Object.keys(hist.byMod).map(byId).filter(Boolean);
  const slipped = mods.filter(m => hist.byMod[m.id].ok < hist.byMod[m.id].n);
  $("#view").innerHTML = `<div class="wrap"><div class="card" style="text-align:center">
    <p class="eyebrow">${cp.kind === "course" ? "Course challenge" : "Checkpoint · " + esc(partName(cp.pid))}</p>
    <div style="font-family:var(--serif);font-size:52px;font-weight:600;line-height:1;margin:8px 0 4px;color:${pct >= 80 ? "var(--ok)" : pct >= 60 ? "var(--warm)" : "var(--bad)"}">${pct}%</div>
    <p class="sub" style="margin-bottom:16px">${hist.score} of ${hist.total} · ${mods.length} modules</p>
    <p style="max-width:520px;margin:0 auto 18px;color:var(--text-2)">${pct >= 80 ? "That is retention, not recognition. The modules you held are now Proficient." : pct >= 60 ? "Most of it held. The modules that slipped are back to Practised — their cards and mistakes will bring them round." : "A lot slipped, which is what checkpoints are for: better to find out here than in front of a client. Work the mistake queue, then retake in a week."}</p>
    <div style="display:flex;gap:9px;justify-content:center;flex-wrap:wrap">
      ${mistakeCount() ? `<button class="btn primary" onclick="go('#/review/mistakes')">Fix the mistakes (${mistakeCount()})</button>` : ""}
      <button class="btn" onclick="go('#/check')">Checkpoints</button>
      <button class="btn" onclick="go('#/home')">Dashboard</button></div></div>
    <div class="card" style="margin-top:16px"><p class="eyebrow">Module by module</p>
      ${mods.map(m => { const b = hist.byMod[m.id], ms = mastery(m); return `<button class="mrow" style="padding:8px 10px;border-left:0;border-radius:8px" onclick="go('#/m/${m.id}')"><span class="dot ${masteryClass(m)}"></span><span class="code">${m.id}</span><span class="t">${esc(m.short)}</span><span style="font-size:12px;color:${b.ok === b.n ? "var(--ok)" : "var(--bad)"}">${b.ok}/${b.n}</span><span class="tag" style="margin-left:8px">${ms.name}</span></button>`; }).join("")}
      ${slipped.length ? `<p class="sub" style="margin-top:12px">Slipped: ${slipped.map(m => m.id).join(", ")}. Re-read just the section behind each miss, not the whole module.</p>` : ""}
    </div></div>`;
  renderSidebar();
}
