/* ---------- stats ---------- */
function viewStats() {
  const qs = quizStats(),
    t = todayNum();
  const per = MODS.map(m => {
    const q = progressOf(m.id).quiz;
    if (!q || !q.a || !q.a.length) return { m, pct: null, n: 0 };
    const ans = q.a.filter(x => x && x.answered);
    return { m, pct: ans.length ? ans.filter(x => x.ok).length / ans.length : null, n: ans.length };
  });
  const fc = {};
  Object.values(STATE.cards).forEach(c => {
    const d = Math.max(0, c.due - t);
    if (d <= 14) fc[d] = (fc[d] || 0) + 1;
  });
  const maxF = Math.max(1, ...Object.values(fc));
  const spent = Math.round(timeSpent() / 60);
  const dist = [0, 0, 0, 0, 0];
  MODS.forEach(m => dist[mastery(m).lvl]++);

  let h = `<div class="wrap-wide"><h2 class="big">Progress</h2>
  <p class="lede">The numbers that predict whether this actually sticks.</p>`;
  if (!spent && !qs.total && !cardCount() && !doneCount()) {
    const first = MODS[0];
    h += `<div class="card"><h3 class="eyebrow">Nothing to measure yet</h3>
      <p class="lede">Mastery, calibration, the practice forecast and your study days all appear here once you have read a section or answered a question. Finish ${first.id} and this page starts telling you something.</p>
      <a class="btn primary" href="#/m/${first.id}">Open ${first.id} · ${esc(first.short)}</a></div>
      <div class="card gap-top-lg"><h3 class="eyebrow">The honest read</h3><p class="lede">${milestoneCopy(0)}</p></div></div>`;
    $("#view").innerHTML = h;
    return;
  }
  h += `<div class="grid g4 gap-bottom-lg">
    <div class="stat"><div class="n">${doneCount()}/${MODS.length}</div><div class="l">modules complete</div></div>
    <div class="stat"><div class="n">${spent}m</div><div class="l">time actually spent</div></div>
    <div class="stat"><div class="n">${cardCount()}</div><div class="l">cards in deck · ${dueCards().length} due${mistakeCount() ? " · " + mistakeCount() + " mistakes" : ""}</div></div>
    <div class="stat"><div class="n">${qs.total ? Math.round(qs.pct * 100) + "%" : "—"}</div><div class="l">accuracy · ${qs.total} answered</div></div>
  </div>

  <div class="card gap-bottom-lg"><h3 class="eyebrow" data-help="${esc(help("mastery"))}">Mastery — what you can still do</h3>
    <p class="sub gap-bottom">Read is a tick. Practised is a quiz score. Proficient means it held up weeks later in a mixed checkpoint. Mastered means the cards have settled too. Levels drop when a checkpoint says so.</p>
    <div class="mbar">${[4, 3, 2, 1].map(l => (dist[l] ? `<i class="l${l}" style="flex:${dist[l]}" data-help="${MASTERY[l]}: ${dist[l]}"></i>` : "")).join("")}${dist[0] ? `<i class="l0" style="flex:${dist[0]}" data-help="Not started: ${dist[0]}"></i>` : ""}</div>
    <div class="legend flat">${[4, 3, 2, 1, 0].map(l => `<span data-help="${esc(help(MASTERY[l]))}"><i class="dot l${l}"></i>${MASTERY[l]} · ${dist[l]}</span>`).join("")}</div>
  </div>

  <div class="grid g2 gap-bottom-lg">
    <div class="card"><h3 class="eyebrow" data-help="${esc(help("calibration"))}">Calibration — do you know what you know?</h3>
    <p class="sub gap-bottom">The gap between how sure you felt and how right you were, across every quiz and checkpoint. A senior ${esc(CFG.practitioner)}'s real edge is knowing which of their beliefs are load-bearing.</p>`;
  const labels = { 3: "Certain", 2: "Fairly sure", 1: "Guessing" };
  [3, 2, 1].forEach(k => {
    const [r, n] = qs.conf[k];
    const p = n ? Math.round((r / n) * 100) : 0;
    h += `<div class="calrow"><span>${labels[k]}</span>
      <span class="bar"><i class="${k === 3 && n && p < 70 ? "bad" : ""}" style="width:${n ? p : 0}%"></i></span>
      <span class="sub calnum">${n ? p + "% · " + n : "—"}</span></div>`;
  });
  const c3 = qs.conf[3];
  h += `<p class="sub gap-top">${c3[1] >= 5 && c3[0] / c3[1] < 0.8 ? "You are overconfident: when certain, you are right " + Math.round((c3[0] / c3[1]) * 100) + "% of the time. Slow down on the questions that feel obvious." : c3[1] >= 5 ? "Well calibrated. Your confidence is carrying real information." : "Answer more questions to see your calibration."}</p></div>`;

  h += `<div class="card"><h3 class="eyebrow">Practice forecast · next 14 days</h3>
    <p class="sub gap-bottom">Cards coming back at you. Flat and low is healthy; a spike means a heavy day.</p>
    <div class="forecast">`;
  for (let d = 0; d <= 14; d++) {
    const n = fc[d] || 0;
    h += `<div class="fcol" data-help="${n} card(s) in ${d} day(s)">
      <div class="fbar ${d === 0 ? "today" : ""} ${n ? "" : "none"}" style="height:${n ? Math.max(4, (n / maxF) * 88) : 2}px"></div>
      <span class="flabel">${d % 7 === 0 ? d : ""}</span></div>`;
  }
  h += `</div></div></div>`;

  h += `<div class="card gap-bottom-lg"><h3 class="eyebrow">Study days · last 17 weeks</h3>
    <p class="sub gap-bottom" data-help="${esc(help("streak freeze"))}">A day counts once you have read a section, answered a question, reviewed a card or asked the tutor. Streak: <b>${STATE.streak.days}</b> day${STATE.streak.days === 1 ? "" : "s"}${STATE.streak.freezes ? ` · ${STATE.streak.freezes} freeze${STATE.streak.freezes === 1 ? "" : "s"} banked (a missed day spends one; finishing a module earns one)` : " · finish a module to bank a streak freeze"}.</p>
    ${heatmapHtml()}</div>`;

  h += `<div class="card gap-bottom-lg"><h3 class="eyebrow">Module by module</h3>
    <div class="modlist">`;
  per.forEach(x => {
    const pc = Math.round(modPct(x.m) * 100),
      ms = mastery(x.m);
    const band = x.pct == null ? "" : x.pct >= 0.8 ? "ok" : x.pct >= 0.6 ? "warm" : "bad";
    h += `<a class="mrow boxed" href="#/m/${x.m.id}" data-help="${ms.name} — ${esc(help(ms.name))}">
      <span class="dot ${masteryClass(x.m)}"></span>
      <span class="code">${x.m.id}</span><span class="t">${esc(x.m.short)}</span>
      <span class="tag">${ms.name}</span>
      <span class="minibar"><span class="bar"><i style="width:${pc}%"></i></span></span>
      <span class="score ${band}">${x.pct == null ? "—" : Math.round(x.pct * 100) + "%"}</span></a>`;
  });
  h += `</div></div>`;

  h += `<div class="card"><h3 class="eyebrow">The honest read</h3><p class="lede">
    ${milestoneCopy(doneCount())}
    ${qs.total > 20 && qs.pct < 0.7 ? " Your quiz accuracy is under 70% — do not read ahead, retake the ones you missed instead." : ""}
    ${spent > 0 ? " Time logged so far: " + spent + " minutes of the " + plannedMinutes().toLocaleString() + "-minute plan." : ""}
  </p><a class="btn sm" href="#/record">Open your course record</a></div></div>`;
  $("#view").innerHTML = h;
}
/* 17 weeks of days, Monday at the top, today at the far right */
function heatmapHtml() {
  const t = todayNum(),
    seen = new Set(STATE.streak.seen || []),
    frozen = new Set(STATE.streak.frozen || []);
  const dow = (new Date(t * DAY).getUTCDay() + 6) % 7; // 0 = Monday
  const weeks = 17,
    cells = [];
  const start = t - dow - (weeks - 1) * 7;
  let h = `<div class="heat">`;
  for (let w = 0; w < weeks; w++) {
    h += `<div class="hcol">`;
    for (let d = 0; d < 7; d++) {
      const day = start + w * 7 + d;
      const cls = day > t ? "future" : seen.has(day) ? "on" : frozen.has(day) ? "frz" : "";
      h += `<i class="${cls}" data-help="${fmtDay(day)}${seen.has(day) ? " · studied" : frozen.has(day) ? " · freeze used" : ""}"></i>`;
    }
    h += `</div>`;
  }
  h += `</div><div class="legend flat"><span><i class="hk on"></i>studied</span><span data-help="${esc(help("streak freeze"))}"><i class="hk frz"></i>freeze</span><span><i class="hk"></i>missed</span></div>`;
  return h;
}

/* The "honest read" line is course copy, not engine logic: each course ships its own
   milestones in course.json as [{ after: <modules completed>, text }], highest match wins. */
function plannedMinutes() {
  return MODS.reduce((a, m) => a + m.minutes, 0);
}
function milestoneCopy(done) {
  const ms = (CFG.milestones || []).filter(x => done >= x.after).sort((a, b) => a.after - b.after);
  return ms.length ? esc(ms[ms.length - 1].text) : "";
}
