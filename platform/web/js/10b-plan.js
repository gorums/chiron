/* ---------- the study plan, the "today" block, and the course record ----------
   The course knows its hour budget and every module's minutes; the plan turns that into
   a week and a date. Two ways in: hours per week, or a target date. Either one gives a
   projected finish, this week's modules, and whether you are ahead or behind. */
function remainingMinutes() { return MODS.filter(m => !isDone(m)).reduce((a, m) => a + m.minutes, 0); }
function planInfo() {
  const pl = S.plan || {}, t = todayNum(), rem = remainingMinutes();
  const out = { mode: pl.mode, rem, weekly: null, weeksLeft: null, finishDay: null, targetDay: null, needWeekly: null, thisWeek: [], behind: 0 };
  if (pl.mode === "date" && pl.target) {
    const td = Math.floor(Date.parse(pl.target + "T12:00:00") / DAY);
    if (!isNaN(td)) {
      out.targetDay = td;
      const weeks = Math.max(.15, (td - t) / 7);
      out.needWeekly = rem / 60 / weeks; out.weekly = out.needWeekly; out.weeksLeft = weeks; out.finishDay = td;
    }
  } else if (pl.mode === "weekly" && pl.weekly > 0) {
    out.weekly = +pl.weekly; out.weeksLeft = rem / 60 / out.weekly; out.finishDay = t + Math.ceil(out.weeksLeft * 7);
  }
  if (out.weekly) {
    let budget = out.weekly * 60;
    for (const m of MODS) { if (isDone(m)) continue; if (out.thisWeek.length && budget < m.minutes) break; out.thisWeek.push(m); budget -= m.minutes; }
    if (pl.start != null) {
      const elapsedWeeks = Math.max(0, (t - pl.start) / 7);
      const expected = elapsedWeeks * out.weekly * 60;
      const achieved = Math.max(0, minutesDone() - (pl.baseline || 0));
      out.behind = Math.round((expected - achieved) / 60 * 10) / 10;   // hours; negative = ahead
    }
  }
  return out;
}
function renderToday(cont) {
  const due = dueCards().length, md = mistakesDue(), offers = checkOffers(), pi = planInfo();
  const rows = [];
  if (due) rows.push(`<button class="trow" onclick="go('#/review')"><span class="ico">↻</span><span>Review <b>${due}</b> card${due > 1 ? "s" : ""}${md ? ` · ${md} mistake${md > 1 ? "s" : ""}` : ""}</span><span class="t">~${Math.max(1, Math.round(due * .4))} min</span></button>`);
  else if (mistakeCount()) rows.push(`<button class="trow" onclick="go('#/review/mistakes')"><span class="ico">✗</span><span>Fix <b>${mistakeCount()}</b> queued mistake${mistakeCount() > 1 ? "s" : ""}</span><span class="t">~${Math.max(1, Math.round(mistakeCount() * .5))} min</span></button>`);
  if (cont) {
    const step = resumeStep(cont), name = STEPS[+(step.slice(1) || 0)].n;
    rows.push(`<button class="trow" onclick="go('#/m/${cont.id}${step}')"><span class="ico">▶</span><span>${modPct(cont) > 0 ? "Continue" : "Start"} <b>${cont.id}</b> · ${esc(cont.short)} — ${name}</span><span class="t">${cont.minutes} min</span></button>`);
  }
  offers.slice(0, 1).forEach(o => rows.push(`<button class="trow" onclick="startCheckpoint('${o.kind}','${o.pid || ""}')"><span class="ico">◎</span><span>${esc(o.label)}</span><span class="t">~10 min</span></button>`));
  if (openQs()) rows.push(`<button class="trow" onclick="markFilter='open';go('#/marks')"><span class="ico">?</span><span>Close <b>${openQs()}</b> open question${openQs() > 1 ? "s" : ""}</span><span class="t">~5 min</span></button>`);
  const streakLine = S.streak.last === todayNum() ? `Studied today · streak <b>${S.streak.days}</b>` : S.streak.days ? `Streak <b>${S.streak.days}</b> — nothing yet today` : "No streak yet — one section, one card or one question starts it";
  return `<div class="card today"><p class="eyebrow">Today</p>
    <div class="trows">${rows.join("") || `<p class="sub">Nothing queued. Open the next module.</p>`}</div>
    <p class="sub" style="margin-top:12px;font-size:12.5px">${streakLine}${S.streak.freezes ? ` · ❄ ${S.streak.freezes} freeze${S.streak.freezes > 1 ? "s" : ""}` : ""}${pi.weekly && pi.thisWeek.length ? ` · this week: ${pi.thisWeek.map(m => m.id).join(", ")}` : ""}</p></div>`;
}
function renderPlanCard() {
  const pl = S.plan || {}, pi = planInfo(), rem = pi.rem;
  const iso = d => new Date(d * DAY).toISOString().slice(0, 10);
  let line = "";
  if (pi.mode === "weekly" && pi.weekly) line = `At <b>${pi.weekly}h a week</b> you finish around <b>${fmtDay(pi.finishDay)}</b> (${Math.ceil(pi.weeksLeft)} week${Math.ceil(pi.weeksLeft) === 1 ? "" : "s"}).`;
  else if (pi.mode === "date" && pi.targetDay) line = pi.targetDay <= todayNum() ? `The target date has passed. Set a new one or switch to hours per week.` : `To finish by <b>${fmtDay(pi.targetDay)}</b> you need <b>${Math.round(pi.needWeekly * 10) / 10}h a week</b>.`;
  else line = `${fmtH(rem)} of study left. Tell the plan how much time you have and it will say when you finish.`;
  if (pi.weekly && pl.start != null) {
    if (pi.behind >= 1) line += ` You are about <b>${pi.behind}h behind</b> — shift the plan rather than cram.`;
    else if (pi.behind <= -1) line += ` You are about <b>${-pi.behind}h ahead</b>.`;
    else line += ` On track.`;
  }
  return `<div class="card"><p class="eyebrow">Study plan</p>
    <p style="margin:0 0 12px;color:var(--text-2);font-size:14.5px">${line}</p>
    <div class="planrow">
      <select id="planmode"><option value="" ${!pl.mode ? "selected" : ""}>No plan</option><option value="weekly" ${pl.mode === "weekly" ? "selected" : ""}>Hours per week</option><option value="date" ${pl.mode === "date" ? "selected" : ""}>Target date</option></select>
      <input type="number" id="planweekly" min="0.5" step="0.5" value="${pl.weekly || ""}" placeholder="hours / week" class="${pl.mode === "weekly" ? "" : "hidden"}">
      <input type="date" id="plandate" value="${pl.target || ""}" min="${iso(todayNum() + 1)}" class="${pl.mode === "date" ? "" : "hidden"}">
      <button class="btn sm primary" onclick="savePlan()">Save</button>
      ${pl.mode ? `<button class="btn sm ghost" onclick="shiftPlan()" title="Start counting from today">Shift to today</button>` : ""}
    </div>
    ${pi.weekly && pi.thisWeek.length ? `<p class="sub" style="margin-top:10px;font-size:12.5px">This week: ${pi.thisWeek.map(m => `<button class="chip" style="font-size:11.5px;padding:3px 8px" onclick="go('#/m/${m.id}')">${m.id} · ${esc(m.short)}</button>`).join(" ")}</p>` : ""}
    ${STUDIO && "Notification" in window ? `<p class="sub" style="margin-top:10px;font-size:12px"><label style="display:flex;gap:6px;align-items:center;cursor:pointer"><input type="checkbox" id="plannotify" ${S.ui && S.ui.notify ? "checked" : ""}> Remind me in this browser when cards are due</label></p>` : ""}
  </div>`;
}
function bindPlanCard() {
  const mode = $("#planmode"); if (!mode) return;
  mode.addEventListener("change", () => {
    $("#planweekly").classList.toggle("hidden", mode.value !== "weekly");
    $("#plandate").classList.toggle("hidden", mode.value !== "date");
  });
  const n = $("#plannotify");
  if (n) n.addEventListener("change", async () => {
    if (!S.ui) S.ui = {};
    if (n.checked) { const perm = await Notification.requestPermission(); S.ui.notify = perm === "granted"; if (!S.ui.notify) { n.checked = false; toast("Notifications were not allowed"); } }
    else S.ui.notify = false;
    save();
  });
}
function savePlan() {
  const mode = $("#planmode").value;
  const pl = S.plan = Object.assign({ start: null, baseline: 0 }, S.plan || {});
  pl.mode = mode || null;
  pl.weekly = mode === "weekly" ? parseFloat($("#planweekly").value) || null : pl.weekly;
  pl.target = mode === "date" ? ($("#plandate").value || null) : pl.target;
  if (mode && pl.start == null) { pl.start = todayNum(); pl.baseline = minutesDone(); }
  if (!mode) { pl.start = null; }
  save(); toast(mode ? "Plan saved" : "Plan cleared"); viewHome();
}
function shiftPlan() { S.plan.start = todayNum(); S.plan.baseline = minutesDone(); save(); toast("Counting from today"); viewHome(); }
function notifyDue() {
  if (!STUDIO || !(S.ui && S.ui.notify) || !("Notification" in window) || Notification.permission !== "granted") return;
  const due = dueCards().length; if (!due) return;
  try { new Notification(CFG.title, { body: due + " card" + (due > 1 ? "s" : "") + " due today. Five minutes keeps them." }); } catch (e) {}
}

/* ---------- the course record: what you can show for the hours ---------- */
function viewRecord() {
  const qs = quizStats(), spent = Math.round(timeSpent() / 60), done = doneCount();
  const last = MODS[MODS.length - 1], cap = P(last.id).transfer || {};
  const lastc = lastCheck("course");
  const sheets = DATA.library.templates.map(t => ({ t, n: sheetFilled(t.slug) })).filter(x => x.n);
  const dist = [0, 0, 0, 0, 0]; MODS.forEach(m => dist[mastery(m).lvl]++);
  let h = `<div class="wrap"><div class="readhead"><div class="crumb">${esc(CFG.title)} · course record</div>
    <h2>${done === MODS.length ? "Completed" : done + " of " + MODS.length + " modules"}</h2>
    <p class="sub">${milestoneCopy(done)}</p></div>
    <div class="grid g4" style="margin-bottom:18px">
      <div class="stat"><div class="n">${fmtH(minutesDone())}</div><div class="l">of ${fmtH(CFG.hours * 60)} curriculum</div></div>
      <div class="stat"><div class="n">${spent}m</div><div class="l">logged on the page</div></div>
      <div class="stat"><div class="n">${qs.total ? Math.round(qs.pct * 100) + "%" : "—"}</div><div class="l">accuracy · ${qs.total} answered</div></div>
      <div class="stat"><div class="n">${lastc ? Math.round(lastc.score / lastc.total * 100) + "%" : "—"}</div><div class="l">${lastc ? "course challenge · " + fmtDay(lastc.day) : "no course challenge yet"}</div></div>
    </div>
    <div class="card" style="margin-bottom:16px"><p class="eyebrow">Mastery by part</p>`;
  DATA.parts.forEach(p => {
    const ms = MODS.filter(m => m.part === p.id);
    h += `<div style="margin:10px 0"><div style="display:flex;gap:8px;align-items:baseline;margin-bottom:6px"><b style="font-size:14px">${esc(p.name)}</b><span class="sub" style="font-size:12px">${ms.filter(m => mastery(m).lvl >= 3).length} of ${ms.length} proficient or better</span></div>
      <div style="display:flex;gap:6px;flex-wrap:wrap">${ms.map(m => `<span class="chip lvl l${mastery(m).lvl}" title="${mastery(m).name}" onclick="go('#/m/${m.id}')">${m.id}</span>`).join("")}</div></div>`;
  });
  h += `<div class="legend" style="padding:8px 0 0">${[4, 3, 2, 1].map(l => `<span><i class="dot l${l}"></i>${MASTERY[l]} · ${dist[l]}</span>`).join("")}</div></div>`;
  if (cap.answer) h += `<div class="card" style="margin-bottom:16px"><p class="eyebrow">Capstone · ${last.id} ${esc(last.title)}</p>
    <div class="quote" style="max-height:none;margin-bottom:10px">${esc(cap.answer)}</div>
    ${cap.fb ? `<div class="fb ${cap.fb.verdict || ""}"><b>Claude's read</b>${mdLite(cap.fb.text)}</div>` : ""}
    ${cap.score ? `<p class="sub">Self-scored: ${["", "missed it", "partly there", "got it"][cap.score]}.</p>` : ""}</div>`;
  if (sheets.length) h += `<div class="card" style="margin-bottom:16px"><p class="eyebrow">Worksheets you filled in</p>${sheets.map(x => `<button class="btn sm" style="margin:0 8px 8px 0" onclick="go('#/library/t-${x.t.slug}')">${esc(x.t.title)} · ${x.n}/${x.t.fields}</button>`).join("")}</div>`;
  const c3 = qs.conf[3];
  h += `<div class="card" style="margin-bottom:16px"><p class="eyebrow">Calibration</p><p style="margin:0;color:var(--text-2)">${c3[1] >= 5 ? `When certain, right ${Math.round(c3[0] / c3[1] * 100)}% of the time over ${c3[1]} answers.` : "Not enough confident answers to say yet."}</p></div>
    <div style="display:flex;gap:9px;flex-wrap:wrap"><button class="btn" onclick="copyRecord()">Copy as text</button><button class="btn" onclick="window.print()">Print</button><button class="btn ghost" onclick="go('#/stats')">Stats</button></div></div>`;
  $("#view").innerHTML = h;
}
function copyRecord() {
  const qs = quizStats(), lastc = lastCheck("course");
  const lines = [CFG.title + " — course record", new Date().toLocaleDateString(), "",
    doneCount() + " of " + MODS.length + " modules complete · " + fmtH(minutesDone()) + " of " + fmtH(CFG.hours * 60),
    "Accuracy " + (qs.total ? Math.round(qs.pct * 100) + "% over " + qs.total + " answers" : "—"),
    lastc ? "Course challenge " + Math.round(lastc.score / lastc.total * 100) + "% on " + fmtDay(lastc.day) : "",
    ""];
  DATA.parts.forEach(p => { lines.push(p.name); MODS.filter(m => m.part === p.id).forEach(m => lines.push("  " + m.id + "  " + m.short + " — " + mastery(m).name)); lines.push(""); });
  toast(clip(lines.filter(l => l != null).join("\n")) ? "Record copied" : "Could not copy");
}
