/* ---------- the study plan, the "today" block, and the course record ----------
   The course knows its hour budget and every module's minutes; the plan turns that into
   a week and a date. Two ways in: hours per week, or a target date. Either one gives a
   projected finish, this week's modules, and whether you are ahead or behind. */
function remainingMinutes() {
  return MODS.filter(m => !isDone(m)).reduce((a, m) => a + m.minutes, 0);
}
function planInfo() {
  const pl = STATE.plan || {},
    t = todayNum(),
    rem = remainingMinutes();
  const out = {
    mode: pl.mode,
    rem,
    weekly: null,
    weeksLeft: null,
    finishDay: null,
    targetDay: null,
    needWeekly: null,
    thisWeek: [],
    behind: 0,
  };
  if (pl.mode === "date" && pl.target) {
    const td = Math.floor(Date.parse(pl.target + "T12:00:00") / DAY);
    if (!isNaN(td)) {
      out.targetDay = td;
      const weeks = Math.max(0.15, (td - t) / 7);
      out.needWeekly = rem / 60 / weeks;
      out.weekly = out.needWeekly;
      out.weeksLeft = weeks;
      out.finishDay = td;
    }
  } else if (pl.mode === "weekly" && pl.weekly > 0) {
    out.weekly = +pl.weekly;
    out.weeksLeft = rem / 60 / out.weekly;
    out.finishDay = t + Math.ceil(out.weeksLeft * 7);
  }
  if (out.weekly) {
    let budget = out.weekly * 60;
    for (const m of MODS) {
      if (isDone(m)) continue;
      if (out.thisWeek.length && budget < m.minutes) break;
      out.thisWeek.push(m);
      budget -= m.minutes;
    }
    if (pl.start != null) {
      const elapsedWeeks = Math.max(0, (t - pl.start) / 7);
      const expected = elapsedWeeks * out.weekly * 60;
      const achieved = Math.max(0, minutesDone() - (pl.baseline || 0));
      out.behind = Math.round(((expected - achieved) / 60) * 10) / 10; // hours; negative = ahead
    }
  }
  return out;
}
function renderToday(cont) {
  const due = dueCards().length,
    md = mistakesDue(),
    offers = checkOffers(),
    pi = planInfo();
  const rows = [];
  if (due)
    rows.push(
      `<button class="trow" onclick="go('#/review')" data-help="${esc(help("practice deck"))}"><span class="ico">${ico("review", 14)}</span><span>Practise <b>${due}</b> card${due > 1 ? "s" : ""}${md ? ` · ${md} mistake${md > 1 ? "s" : ""}` : ""}</span><span class="t">~${Math.max(1, Math.round(due * 0.4))} min</span></button>`
    );
  else if (mistakeCount())
    rows.push(
      `<button class="trow" onclick="go('#/review/mistakes')" data-help="${esc(help("mistake card"))}"><span class="ico">${ico("close", 13)}</span><span>Fix <b>${mistakeCount()}</b> mistake${mistakeCount() > 1 ? "s" : ""}</span><span class="t">~${Math.max(1, Math.round(mistakeCount() * 0.5))} min</span></button>`
    );
  let next = "";
  if (cont) {
    const stepAt = resumeStepIndex(cont),
      name = STEPS[stepAt].n,
      started = modPct(cont) > 0;
    const weak = weakPrereqs(cont);
    next = `<div class="nextmod">
      <h3>${cont.id} · ${esc(cont.title)}</h3>
      <p class="sub">${cont.minutes} minutes · ${esc(partName(cont.part))}${started ? resumeLabel(cont) || " · " + name.toLowerCase() : ""}</p>
      ${started ? `<div class="bar nextbar"><i style="width:${Math.round(modPct(cont) * 100)}%"></i></div>` : ""}
      ${weak.length ? `<p class="sub warnnote gap-bottom">Builds on ${weak.map(x => x.m.id + " (" + x.ms.name.toLowerCase() + ")").join(", ")} — worth a look first.</p>` : ""}
      <a class="btn primary" href="${resumeHash(cont)}">${started ? "Resume" : "Begin"} ${cont.id}</a>
    </div>`;
  }
  offers
    .slice(0, 1)
    .forEach(o =>
      rows.push(
        `<button class="trow" onclick="startCheckpoint('${o.kind}','${o.pid || ""}')"><span class="ico">${ico("check", 14)}</span><span>${esc(o.label)}</span><span class="t">~10 min</span></button>`
      )
    );
  if (openQs())
    rows.push(
      `<button class="trow" onclick="markFilter='open';go('#/marks')" data-help="Passages you marked with a question and have not closed"><span class="ico">${ico("ask", 14)}</span><span>Close <b>${openQs()}</b> open question${openQs() > 1 ? "s" : ""}</span><span class="t">~5 min</span></button>`
    );
  const streakLine =
    STATE.streak.last === todayNum()
      ? `Studied today · streak <b>${STATE.streak.days}</b>`
      : STATE.streak.days
        ? `Streak <b>${STATE.streak.days}</b> — nothing yet today`
        : "No streak yet — one section, one card or one question starts it";
  const freezes = STATE.streak.freezes
    ? ` · <span data-help="${esc(help("streak freeze"))}">❄ ${STATE.streak.freezes} freeze${STATE.streak.freezes > 1 ? "s" : ""}</span>`
    : "";
  return `<div class="card today raised"><h3 class="eyebrow">${cont && modPct(cont) > 0 ? "Continue" : "Next"}</h3>
    ${next}
    ${rows.length ? `<h3 class="eyebrow gap-top">Also today</h3><div class="trows">${rows.join("")}</div>` : ""}
    <p class="sub gap-top">${streakLine}${freezes}${pi.weekly && pi.thisWeek.length ? ` · this week: ${pi.thisWeek.map(m => m.id).join(", ")}` : ""}</p></div>`;
}
function renderPlanCard() {
  const pl = STATE.plan || {},
    pi = planInfo(),
    rem = pi.rem;
  const iso = d => new Date(d * DAY).toISOString().slice(0, 10);
  let line = "";
  if (pi.mode === "weekly" && pi.weekly)
    line = `At <b>${pi.weekly}h a week</b> you finish around <b>${fmtDay(pi.finishDay)}</b> (${Math.ceil(pi.weeksLeft)} week${Math.ceil(pi.weeksLeft) === 1 ? "" : "s"}).`;
  else if (pi.mode === "date" && pi.targetDay)
    line =
      pi.targetDay <= todayNum()
        ? `The target date has passed. Set a new one or switch to hours per week.`
        : `To finish by <b>${fmtDay(pi.targetDay)}</b> you need <b>${Math.round(pi.needWeekly * 10) / 10}h a week</b>.`;
  else
    line = `${fmtH(rem)} of study left. Tell the plan how much time you have and it will say when you finish.`;
  if (pi.weekly && pl.start != null) {
    if (pi.behind >= 1)
      line += ` You are about <b>${pi.behind}h behind</b> — shift the plan rather than cram.`;
    else if (pi.behind <= -1) line += ` You are about <b>${-pi.behind}h ahead</b>.`;
    else line += ` On track.`;
  }
  return `<div class="card"><h3 class="eyebrow">Study plan</h3>
    <p class="lede">${line}</p>
    <div class="planrow">
      <label class="visually-hidden" for="planmode">How you want to plan</label>
      <select id="planmode"><option value="" ${!pl.mode ? "selected" : ""}>No plan</option><option value="weekly" ${pl.mode === "weekly" ? "selected" : ""}>Hours per week</option><option value="date" ${pl.mode === "date" ? "selected" : ""}>Target date</option></select>
      <label class="visually-hidden" for="planweekly">Hours per week</label>
      <input type="number" id="planweekly" min="0.5" step="0.5" value="${pl.weekly || ""}" placeholder="hours / week" class="${pl.mode === "weekly" ? "" : "hidden"}">
      <label class="visually-hidden" for="plandate">Target date</label>
      <input type="date" id="plandate" value="${pl.target || ""}" min="${iso(todayNum() + 1)}" class="${pl.mode === "date" ? "" : "hidden"}">
      <button class="btn sm primary" onclick="savePlan()">Save</button>
      ${pl.mode ? `<button class="btn sm" onclick="shiftPlan()" data-help="Start counting from today">Shift to today</button>` : ""}
    </div>
    ${pi.weekly && pi.thisWeek.length ? `<p class="sub gap-top">This week: ${pi.thisWeek.map(m => `<a class="chip sm" href="#/m/${m.id}">${m.id} · ${esc(m.short)}</a>`).join(" ")}</p>` : ""}
    ${STUDIO && "Notification" in window ? `<p class="sub gap-top"><label class="radio"><input type="checkbox" id="plannotify" ${STATE.ui && STATE.ui.notify ? "checked" : ""}> Remind me in this browser when cards are due</label></p>` : ""}
  </div>`;
}
function bindPlanCard() {
  const mode = $("#planmode");
  if (!mode) return;
  mode.addEventListener("change", () => {
    $("#planweekly").classList.toggle("hidden", mode.value !== "weekly");
    $("#plandate").classList.toggle("hidden", mode.value !== "date");
  });
  const n = $("#plannotify");
  if (n)
    n.addEventListener("change", async () => {
      if (!STATE.ui) STATE.ui = {};
      if (n.checked) {
        const perm = await Notification.requestPermission();
        STATE.ui.notify = perm === "granted";
        if (!STATE.ui.notify) {
          n.checked = false;
          toast("Notifications were not allowed");
        }
      } else STATE.ui.notify = false;
      save();
    });
}
function savePlan() {
  const mode = $("#planmode").value;
  const pl = (STATE.plan = Object.assign({ start: null, baseline: 0 }, STATE.plan || {}));
  pl.mode = mode || null;
  pl.weekly = mode === "weekly" ? parseFloat($("#planweekly").value) || null : pl.weekly;
  pl.target = mode === "date" ? $("#plandate").value || null : pl.target;
  if (mode && pl.start == null) {
    pl.start = todayNum();
    pl.baseline = minutesDone();
  }
  if (!mode) {
    pl.start = null;
  }
  save();
  toast(mode ? "Plan saved" : "Plan cleared");
  viewHome();
}
function shiftPlan() {
  STATE.plan.start = todayNum();
  STATE.plan.baseline = minutesDone();
  save();
  toast("Counting from today");
  viewHome();
}
function notifyDue() {
  if (
    !STUDIO ||
    !(STATE.ui && STATE.ui.notify) ||
    !("Notification" in window) ||
    Notification.permission !== "granted"
  )
    return;
  const due = dueCards().length;
  if (!due) return;
  try {
    new Notification(CFG.title, {
      body: due + " card" + (due > 1 ? "s" : "") + " due today. Five minutes keeps them.",
    });
  } catch (e) {}
}

/* ---------- the course record: what you can show for the hours ---------- */
function viewRecord() {
  const qs = quizStats(),
    spent = Math.round(timeSpent() / 60),
    done = doneCount();
  const last = MODS[MODS.length - 1],
    cap = progressOf(last.id).transfer || {};
  const lastc = lastCheck("course");
  const sheets = DATA.library.templates.map(t => ({ t, n: sheetFilled(t.slug) })).filter(x => x.n);
  const dist = [0, 0, 0, 0, 0];
  MODS.forEach(m => dist[mastery(m).lvl]++);
  let h = `<div class="wrap"><div class="readhead"><div class="crumb"><a href="#/stats">Progress</a> · course record</div>
    <h2>${done === MODS.length ? "Completed" : done + " of " + MODS.length + " modules"}</h2>
    <p class="sub">${milestoneCopy(done)}</p></div>
    <div class="grid g4 gap-bottom">
      <div class="stat"><div class="n">${fmtH(minutesDone())}</div><div class="l">of ${fmtH(CFG.hours * 60)} curriculum</div></div>
      <div class="stat"><div class="n">${spent}m</div><div class="l">logged on the page</div></div>
      <div class="stat"><div class="n">${qs.total ? Math.round(qs.pct * 100) + "%" : "—"}</div><div class="l">accuracy · ${qs.total} answered</div></div>
      <div class="stat"><div class="n">${lastc ? Math.round((lastc.score / lastc.total) * 100) + "%" : "—"}</div><div class="l">${lastc ? "course challenge · " + fmtDay(lastc.day) : "no course challenge yet"}</div></div>
    </div>
    <div class="card gap-bottom"><h3 class="eyebrow">Mastery by part</h3>`;
  DATA.parts.forEach(p => {
    const ms = MODS.filter(m => m.part === p.id);
    h += `<div class="partrow"><div class="rowline mapttl"><b>${esc(p.name)}</b><span class="sub">${ms.filter(m => mastery(m).lvl >= 3).length} of ${ms.length} proficient or better</span></div>
      <div class="rowline wrapped">${ms.map(m => `<a class="chip lvl l${mastery(m).lvl}" href="#/m/${m.id}" data-help="${mastery(m).name} — ${esc(help(mastery(m).name))}">${m.id}</a>`).join("")}</div></div>`;
  });
  h += `<div class="legend flat">${[4, 3, 2, 1].map(l => `<span data-help="${esc(help(MASTERY[l]))}"><i class="dot l${l}"></i>${MASTERY[l]} · ${dist[l]}</span>`).join("")}</div></div>`;
  const openByModule = MODS.map(m => ({ m, n: openGapItems(m.id).length })).filter(x => x.n);
  if (openByModule.length)
    h += `<div class="card warmcard gap-bottom"><h3 class="eyebrow warnnote">Gaps still open</h3>
    <p class="sub gap-bottom">The course is not closed while these are. Each module's last step drills them.</p>
    <div class="rowline wrapped">${openByModule.map(x => `<button class="btn sm" onclick="go(stepHash('${x.m.id}',5))">${x.m.id} · ${x.n} open</button>`).join("")}</div></div>`;
  if (cap.answer)
    h += `<div class="card gap-bottom"><h3 class="eyebrow">Capstone · ${last.id} ${esc(last.title)}</h3>
    <div class="quote full gap-bottom">${esc(cap.answer)}</div>
    ${cap.fb ? `<div class="fb ${cap.fb.verdict || ""}"><b>The tutor's read</b>${mdLite(cap.fb.text)}</div>` : ""}
    ${cap.score ? `<p class="sub">Self-scored: ${["", "missed it", "partly there", "got it"][cap.score]}.</p>` : ""}</div>`;
  if (sheets.length)
    h += `<div class="card gap-bottom"><h3 class="eyebrow">Worksheets you filled in</h3><div class="rowline wrapped">${sheets.map(x => `<button class="btn sm" onclick="go('#/library/t-${x.t.slug}')">${esc(x.t.title)} · ${x.n}/${x.t.fields}</button>`).join("")}</div></div>`;
  const c3 = qs.conf[3];
  h += `<div class="card gap-bottom"><h3 class="eyebrow" data-help="${esc(help("calibration"))}">Calibration</h3><p class="lede">${c3[1] >= 5 ? `When certain, right ${Math.round((c3[0] / c3[1]) * 100)}% of the time over ${c3[1]} answers.` : "Not enough confident answers to say yet."}</p></div>
    <div class="rowline wrapped"><button class="btn primary" onclick="copyRecord()">Copy as text</button><button class="btn" onclick="window.print()">Print</button><button class="btn" onclick="go('#/stats')">Progress</button></div></div>`;
  $("#view").innerHTML = h;
}
function copyRecord() {
  const qs = quizStats(),
    lastc = lastCheck("course");
  const lines = [
    CFG.title + " — course record",
    new Date().toLocaleDateString(),
    "",
    doneCount() +
      " of " +
      MODS.length +
      " modules complete · " +
      fmtH(minutesDone()) +
      " of " +
      fmtH(CFG.hours * 60),
    "Accuracy " + (qs.total ? Math.round(qs.pct * 100) + "% over " + qs.total + " answers" : "—"),
    lastc
      ? "Course challenge " +
        Math.round((lastc.score / lastc.total) * 100) +
        "% on " +
        fmtDay(lastc.day)
      : "",
    "",
  ];
  DATA.parts.forEach(p => {
    lines.push(p.name);
    MODS.filter(m => m.part === p.id).forEach(m =>
      lines.push("  " + m.id + "  " + m.short + " — " + mastery(m).name)
    );
    lines.push("");
  });
  toast(clip(lines.filter(l => l != null).join("\n")) ? "Record copied" : "Could not copy");
}
