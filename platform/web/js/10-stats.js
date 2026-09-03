/* ---------- stats ---------- */
function viewStats() {
  const qs = quizStats(), t = todayNum();
  const per = MODS.map(m => {
    const q = P(m.id).quiz;
    if (!q || !q.a || !q.a.length) return { m, pct: null, n: 0 };
    const ans = q.a.filter(x => x && x.answered);
    return { m, pct: ans.length ? ans.filter(x => x.ok).length / ans.length : null, n: ans.length };
  });
  const fc = {};
  Object.values(S.cards).forEach(c => { const d = Math.max(0, c.due - t); if (d <= 14) fc[d] = (fc[d] || 0) + 1; });
  const maxF = Math.max(1, ...Object.values(fc));
  const spent = Math.round(timeSpent() / 60);
  const dist = [0, 0, 0, 0, 0]; MODS.forEach(m => dist[mastery(m).lvl]++);

  let h = `<div class="wrap-wide"><h2 class="big">Progress &amp; stats</h2>
  <p class="sub" style="margin-bottom:22px">The numbers that predict whether this actually sticks.</p>
  <div class="grid g4" style="margin-bottom:22px">
    <div class="stat"><div class="n">${doneCount()}/${MODS.length}</div><div class="l">modules complete</div></div>
    <div class="stat"><div class="n">${spent}m</div><div class="l">time actually spent</div></div>
    <div class="stat"><div class="n">${cardCount()}</div><div class="l">cards in deck · ${dueCards().length} due${mistakeCount() ? " · " + mistakeCount() + " mistakes" : ""}</div></div>
    <div class="stat"><div class="n">${qs.total ? Math.round(qs.pct * 100) + "%" : "—"}</div><div class="l">accuracy · ${qs.total} answered</div></div>
  </div>

  <div class="card" style="margin-bottom:22px"><p class="eyebrow">Mastery — what you can still do</p>
    <p class="sub" style="margin-bottom:12px">Read is a tick. Practised is a quiz score. Proficient means it held up weeks later in a mixed checkpoint. Mastered means the cards have settled too. Levels drop when a checkpoint says so.</p>
    <div class="mbar">${[4, 3, 2, 1].map(l => dist[l] ? `<i class="l${l}" style="flex:${dist[l]}" title="${MASTERY[l]}: ${dist[l]}"></i>` : "").join("")}${dist[0] ? `<i class="l0" style="flex:${dist[0]}" title="Not started: ${dist[0]}"></i>` : ""}</div>
    <div class="legend" style="padding:8px 0 0">${[4, 3, 2, 1, 0].map(l => `<span><i class="dot l${l}"></i>${MASTERY[l]} · ${dist[l]}</span>`).join("")}</div>
  </div>

  <div class="grid g2" style="margin-bottom:22px">
    <div class="card"><p class="eyebrow">Calibration — do you know what you know?</p>
    <p class="sub" style="margin-bottom:14px">The gap between how sure you felt and how right you were, across every quiz and checkpoint. A senior ${esc(CFG.practitioner)}'s real edge is knowing which of their beliefs are load-bearing.</p>`;
  const labels = { 3: "Certain", 2: "Fairly sure", 1: "Guessing" };
  [3, 2, 1].forEach(k => {
    const [r, n] = qs.conf[k];
    const p = n ? Math.round(r / n * 100) : 0;
    h += `<div class="calrow"><span>${labels[k]}</span>
      <span class="bar"><i style="width:${n ? p : 0}%;background:${k === 3 && n && p < 70 ? "var(--bad)" : "var(--accent)"}"></i></span>
      <span style="text-align:right;color:var(--muted);font-size:12.5px">${n ? p + "% · " + n : "—"}</span></div>`;
  });
  const c3 = qs.conf[3];
  h += `<p class="sub" style="margin-top:12px;font-size:12.5px">${c3[1] >= 5 && c3[0] / c3[1] < .8 ? "You are overconfident: when certain, you are right " + Math.round(c3[0] / c3[1] * 100) + "% of the time. Slow down on the questions that feel obvious." : c3[1] >= 5 ? "Well calibrated. Your confidence is carrying real information." : "Answer more questions to see your calibration."}</p></div>`;

  h += `<div class="card"><p class="eyebrow">Review forecast · next 14 days</p>
    <p class="sub" style="margin-bottom:14px">Cards coming back at you. Flat and low is healthy; a spike means a heavy day.</p>
    <div style="display:flex;align-items:flex-end;gap:4px;height:110px">`;
  for (let d = 0; d <= 14; d++) {
    const n = fc[d] || 0;
    h += `<div style="flex:1;display:flex;flex-direction:column;justify-content:flex-end;align-items:center;height:100%" title="${n} card(s) in ${d} day(s)">
      <div style="width:100%;background:${d === 0 ? "var(--warm)" : "var(--accent)"};height:${n ? Math.max(4, n / maxF * 88) : 2}px;border-radius:3px;opacity:${n ? 1 : .25}"></div>
      <span style="font-size:9px;color:var(--muted);margin-top:4px">${d % 7 === 0 ? d : ""}</span></div>`;
  }
  h += `</div></div></div>`;

  h += `<div class="card" style="margin-bottom:22px"><p class="eyebrow">Study days · last 17 weeks</p>
    <p class="sub" style="margin-bottom:12px">A day counts once you have read a section, answered a question, reviewed a card or asked the tutor. Streak: <b>${S.streak.days}</b> day${S.streak.days === 1 ? "" : "s"}${S.streak.freezes ? ` · ${S.streak.freezes} freeze${S.streak.freezes === 1 ? "" : "s"} banked (a missed day spends one; finishing a module earns one)` : " · finish a module to bank a streak freeze"}.</p>
    ${heatmapHtml()}</div>`;

  h += `<div class="card" style="margin-bottom:22px"><p class="eyebrow">Module by module</p>
    <div style="display:grid;gap:2px;margin-top:10px">`;
  per.forEach(x => {
    const pc = Math.round(modPct(x.m) * 100), ms = mastery(x.m);
    h += `<button class="mrow" style="padding:8px 10px;border-radius:8px;border-left:0" onclick="go('#/m/${x.m.id}')" title="${ms.name}">
      <span class="dot ${masteryClass(x.m)}"></span>
      <span class="code">${x.m.id}</span><span class="t">${esc(x.m.short)}</span>
      <span class="tag" style="margin-right:8px">${ms.name}</span>
      <span style="width:90px"><span class="bar"><i style="width:${pc}%"></i></span></span>
      <span style="width:56px;text-align:right;font-size:12px;color:${x.pct == null ? "var(--muted)" : x.pct >= .8 ? "var(--ok)" : x.pct >= .6 ? "var(--warm)" : "var(--bad)"}">${x.pct == null ? "—" : Math.round(x.pct * 100) + "%"}</span></button>`;
  });
  h += `</div></div>`;

  h += `<div class="card"><p class="eyebrow">The honest read</p><p style="color:var(--text-2);margin:0 0 12px">
    ${milestoneCopy(doneCount())}
    ${qs.total > 20 && qs.pct < .7 ? " Your quiz accuracy is under 70% — do not read ahead, retake the ones you missed instead." : ""}
    ${spent > 0 ? " Time logged so far: " + spent + " minutes of the " + plannedMinutes().toLocaleString() + "-minute plan." : ""}
  </p><button class="btn sm" onclick="go('#/record')">Open your course record →</button></div></div>`;
  $("#view").innerHTML = h;
}
/* 17 weeks of days, Monday at the top, today at the far right */
function heatmapHtml() {
  const t = todayNum(), seen = new Set(S.streak.seen || []), frozen = new Set(S.streak.frozen || []);
  const dow = (new Date(t * DAY).getUTCDay() + 6) % 7;          // 0 = Monday
  const weeks = 17, cells = [];
  const start = t - dow - (weeks - 1) * 7;
  let h = `<div class="heat">`;
  for (let w = 0; w < weeks; w++) {
    h += `<div class="hcol">`;
    for (let d = 0; d < 7; d++) {
      const day = start + w * 7 + d;
      const cls = day > t ? "future" : seen.has(day) ? "on" : frozen.has(day) ? "frz" : "";
      h += `<i class="${cls}" title="${fmtDay(day)}${seen.has(day) ? " · studied" : frozen.has(day) ? " · freeze used" : ""}"></i>`;
    }
    h += `</div>`;
  }
  h += `</div><div class="legend" style="padding:8px 0 0"><span><i class="hk on"></i>studied</span><span><i class="hk frz"></i>freeze</span><span><i class="hk"></i>missed</span></div>`;
  return h;
}

/* The "honest read" line is course copy, not engine logic: each course ships its own
   milestones in course.json as [{ after: <modules completed>, text }], highest match wins. */
function plannedMinutes() { return MODS.reduce((a, m) => a + m.minutes, 0); }
function milestoneCopy(done) {
  const ms = (CFG.milestones || []).filter(x => done >= x.after).sort((a, b) => a.after - b.after);
  return ms.length ? esc(ms[ms.length - 1].text) : "";
}
