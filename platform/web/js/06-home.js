/* ============================ dashboard ============================ */
function viewHome() {
  const done = doneCount(), due = dueCards().length, qs = quizStats();
  const next = MODS.find(m => !isDone(m)) || MODS[MODS.length - 1];
  const inprog = MODS.filter(m => !isDone(m) && modPct(m) > 0);
  const cont = inprog[0] || next;
  const weak = MODS.map(m => ({ m, pct: quizPct(m) })).filter(x => x.pct != null && x.pct < .7).sort((a, b) => a.pct - b.pct).slice(0, 3);
  const dropped = MODS.filter(m => mastery(m).dropped).slice(0, 3);
  const offers = checkOffers();

  let h = `<div class="wrap-wide">
  <p class="eyebrow">${greeting()}</p>
  <h2 class="big">${done === 0 ? "Start with Module 01." : done === MODS.length ? `You finished all ${MODS.length} modules.` : `You are ${Math.round(done / MODS.length * 100)}% through the course.`}</h2>
  <p class="sub" style="margin-bottom:22px">${S.biz ? "Working business: <b>" + esc(S.biz) + "</b>" : "Set your practice business below — every exercise applies to it."}</p>

  <div class="grid g4" style="margin-bottom:18px">
    <div class="stat"><div class="n">${done}<span style="font-size:15px;color:var(--muted)">/${MODS.length}</span></div><div class="l">modules complete</div></div>
    <div class="stat"><div class="n">${fmtH(minutesDone())}</div><div class="l">of ${fmtH(CFG.hours * 60)} curriculum</div></div>
    <div class="stat"><div class="n">${qs.total ? Math.round(qs.pct * 100) + "%" : "—"}</div><div class="l">quiz accuracy (${qs.total} answered)</div></div>
    <div class="stat"><div class="n">${S.streak.days}${S.streak.freezes ? `<span style="font-size:13px;color:var(--muted)" title="Streak freezes">  ❄${S.streak.freezes}</span>` : ""}</div><div class="l">day streak</div></div>
  </div>`;

  h += `<div class="grid g2" style="margin-bottom:18px">${renderToday(cont)}${renderPlanCard()}</div>`;

  h += `<div class="grid g2" style="margin-bottom:18px">
    <div class="card">
      <p class="eyebrow">${inprog.length ? "Continue" : "Next up"}</p>
      <h3 style="font-family:var(--serif);font-size:22px;margin:0 0 6px;font-weight:600">${cont.id} · ${esc(cont.title)}</h3>
      <p class="sub" style="margin-bottom:14px">${cont.minutes} minutes · ${esc(partName(cont.part))}${resumeLabel(cont)}</p>
      <div class="bar" style="margin-bottom:14px"><i style="width:${Math.round(modPct(cont) * 100)}%"></i></div>
      ${weakPrereqs(cont).length ? `<p class="sub" style="margin-bottom:12px;color:var(--warm)">Builds on ${weakPrereqs(cont).map(x => x.m.id + " (" + x.ms.name.toLowerCase() + ")").join(", ")} — worth a look first.</p>` : ""}
      <button class="btn primary" onclick="go('#/m/${cont.id}${resumeStep(cont)}')">${modPct(cont) > 0 ? "Resume" : "Begin"} →</button>
    </div>
    <div class="card">
      <p class="eyebrow">Retrieval practice</p>
      <h3 style="font-family:var(--serif);font-size:22px;margin:0 0 6px;font-weight:600">${due ? due + " card" + (due > 1 ? "s" : "") + " due today" : cardCount() ? "Nothing due today" : "No cards yet"}</h3>
      <p class="sub" style="margin-bottom:14px">${cardCount() ? cardCount() + " cards in your deck" + (mistakeCount() ? ", " + mistakeCount() + " of them mistakes waiting to be fixed" : "") + ". Spaced repetition schedules each one for the day you are about to forget it." : "Cards unlock as you complete modules. They are the single highest-return 5 minutes in this course."}</p>
      <div style="display:flex;gap:8px;flex-wrap:wrap">
        <button class="btn ${due ? "primary" : ""}" ${due ? "" : "disabled"} onclick="go('#/review')">Review now →</button>
        ${mistakeCount() ? `<button class="btn" onclick="go('#/review/mistakes')">Fix mistakes (${mistakeCount()})</button>` : ""}
      </div>
    </div>
  </div>`;

  if (offers.length) {
    h += `<div class="card" style="margin-bottom:18px;border-color:var(--accent)">
      <p class="eyebrow" style="color:var(--accent-ink)">Checkpoint ready</p>
      <p class="sub" style="color:var(--text-2);margin-bottom:12px">A mixed quiz across everything you finished. This is the only score that says whether it stuck — module quizzes measure recognition ten minutes after reading.</p>
      ${offers.map(o => `<button class="btn sm primary" style="margin:0 8px 8px 0" onclick="startCheckpoint('${o.kind}','${o.pid || ""}')">${esc(o.label)} →</button>`).join("")}
    </div>`;
  }
  if (connMode() === "none") {
    h += `<div class="card" style="margin-bottom:18px;display:flex;gap:16px;align-items:center;flex-wrap:wrap">
      <div style="flex:1;min-width:260px">
        <p class="eyebrow">Ask questions while you read</p>
        <p style="color:var(--text-2);margin:0">Connect Claude once and you can select any sentence in any module and talk about it, have your written answers checked, and practise live conversations. Answers arrive in the page, next to the passage, and stay saved with it.</p>
      </div>
      <button class="btn primary" onclick="go('#/settings')">Connect Claude →</button></div>`;
  }
  if (openQs()) {
    h += `<div class="card" style="margin-bottom:18px">
      <p class="eyebrow">Open questions</p>
      <p class="sub" style="color:var(--text-2);margin-bottom:12px">You have <b>${openQs()}</b> passage${openQs() > 1 ? "s" : ""} marked with a question you have not answered yet. These are the edges of what you understand — the highest-value thing you can spend ten minutes on.</p>
      <button class="btn primary" onclick="markFilter='open';go('#/marks')">Open the question list →</button></div>`;
  }
  if (weak.length || dropped.length) {
    h += `<div class="card" style="margin-bottom:18px;border-color:var(--warm)">
      <p class="eyebrow" style="color:var(--warm)">Worth revisiting</p>
      <p class="sub" style="color:var(--text-2);margin-bottom:12px">${weak.length ? "You scored below 70% on these. " : ""}${dropped.length ? "Some slipped in a checkpoint. " : ""}Low scores are information, not failure — re-read just the relevant section and retake.</p>
      ${weak.map(w => `<button class="btn sm" style="margin:0 8px 8px 0" onclick="go('#/m/${w.m.id}/2')">${w.m.id} · ${esc(w.m.short)} — ${Math.round(w.pct * 100)}%</button>`).join("")}
      ${dropped.filter(m => !weak.some(w => w.m === m)).map(m => `<button class="btn sm" style="margin:0 8px 8px 0" onclick="go('#/m/${m.id}/2')">${m.id} · ${esc(m.short)} — slipped</button>`).join("")}
    </div>`;
  }

  h += `<div class="card" style="margin-bottom:18px">
    <p class="eyebrow">Your practice business</p>
    <p class="sub" style="margin-bottom:10px">Every exercise in this course applies to one real business. Abstraction is where learning dies.</p>
    <input type="text" id="bizin" value="${esc(S.biz)}" placeholder="e.g. My sister's physiotherapy clinic in Valencia">
  </div>`;

  h += `<p class="eyebrow" style="margin-top:26px">The map</p><div class="grid g3">`;
  DATA.parts.forEach(p => {
    const ms = MODS.filter(m => m.part === p.id), d = ms.filter(isDone).length;
    h += `<div class="card tight">
      <div style="display:flex;align-items:baseline;gap:8px;margin-bottom:8px"><b style="font-size:14px">${esc(p.name)}</b><span class="tag">${p.hours}h</span><span style="margin-left:auto;font-size:12px;color:var(--muted)">${d}/${ms.length}</span></div>
      <div class="bar" style="margin-bottom:10px"><i style="width:${Math.round(d / ms.length * 100)}%"></i></div>
      <p class="sub" style="font-size:12.5px;margin-bottom:10px">${esc(p.blurb)}</p>
      ${ms.map(m => `<button class="mrow" style="padding-left:0;font-size:12.5px" onclick="go('#/m/${m.id}')" title="${mastery(m).name}"><span class="dot ${masteryClass(m)}"></span><span class="code">${m.id}</span><span class="t">${esc(m.short)}</span>${(m.requires || []).length ? `<span class="req" title="Builds on ${m.requires.join(", ")}">← ${m.requires.join(" ")}</span>` : ""}</button>`).join("")}
    </div>`;
  });
  h += `</div></div>`;
  $("#view").innerHTML = h;
  const bi = $("#bizin");
  if (bi) bi.addEventListener("change", e => { S.biz = e.target.value; save(); toast("Saved"); });
  bindPlanCard();
}
function greeting() {
  const hr = new Date().getHours();
  return hr < 12 ? "Good morning" : hr < 18 ? "Good afternoon" : "Good evening";
}
/* Where a module was left: the furthest step with anything in it, and the last section read. */
function resumeStep(m) {
  const p = P(m.id);
  if (p.transfer && (p.transfer.answer || "").trim()) return "/4";
  if (Object.values(p.elab).some(v => (v || "").trim())) return "/3";
  if (p.quiz && !p.quiz.finished && p.quiz.a.length) return "/2";
  if (secDone(m) > 0 || (S.pos[m.id] || 0) > 0) return "/1";
  if (p.predict.trim()) return "/1";
  return "";
}
function resumeLabel(m) {
  const s = resumeStep(m), pos = S.pos[m.id] || 0;
  if (s === "/1" && pos > 0 && m.sections[pos]) return " · at “" + esc(m.sections[pos].h) + "”";
  if (s === "/2") return " · in the quiz";
  if (s === "/3") return " · elaborating";
  if (s === "/4") return " · applying";
  return "";
}
