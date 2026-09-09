/* ============================ dashboard ============================ */
function viewHome() {
  const done = doneCount(),
    due = dueCards().length;
  const next = MODS.find(m => !isDone(m)) || MODS[MODS.length - 1];
  const inprog = MODS.filter(m => !isDone(m) && modPct(m) > 0);
  const cont = inprog[0] || next;
  const weak = MODS.map(m => ({ m, pct: quizPct(m) }))
    .filter(x => x.pct != null && x.pct < 0.7)
    .sort((a, b) => a.pct - b.pct)
    .slice(0, 3);
  const dropped = MODS.filter(m => mastery(m).dropped).slice(0, 3);
  const offers = checkOffers();

  const anchor = CFG.anchor || {};
  const headline =
    done === 0
      ? "Start with Module 01."
      : done === MODS.length
        ? `You finished all ${MODS.length} modules.`
        : `You are ${Math.round((done / MODS.length) * 100)}% through the course.`;
  const anchorLine = STATE.biz
    ? `${esc(anchor.label)}: <b>${esc(STATE.biz)}</b> · <a href="#/settings">change</a>`
    : `${esc(anchor.label)} is not set yet — <a href="#/settings">name it in Settings</a> so every exercise aims at something real.`;
  let h = `<div class="wrap-wide">
  <p class="eyebrow">${greeting()}</p>
  <h2 class="big">${headline}</h2>
  <p class="lede">${anchorLine}</p>`;

  h += introCard();
  h += `<div class="grid g2 gap-bottom">${renderToday(cont)}${renderPlanCard()}</div>`;

  const deckTitle = due
    ? due + " card" + (due > 1 ? "s" : "") + " due today"
    : cardCount()
      ? "Nothing due today"
      : "No cards yet";
  const deckLine = cardCount()
    ? `${cardCount()} cards in your deck${mistakeCount() ? ", " + mistakeCount() + " of them mistakes waiting to be fixed" : ""}. Spaced repetition schedules each one for the day you are about to forget it.`
    : "Cards unlock as you complete modules. They are the single highest-return 5 minutes in this course.";
  h += `<div class="grid ${connMode() === "none" ? "g2" : ""} gap-bottom">
    <div class="card">
      <h3 class="eyebrow" title="${esc(help("practice deck"))}">Practice</h3>
      <h3 class="h-serif">${deckTitle}</h3>
      <p class="sub gap-bottom">${deckLine}</p>
      <div class="rowline wrapped">
        <button class="btn ${due ? "primary" : ""}" ${due ? "" : "disabled"} onclick="go('#/review')">Practise now</button>
        ${mistakeCount() ? `<button class="btn" title="${esc(help("mistake card"))}" onclick="go('#/review/mistakes')">Fix mistakes (${mistakeCount()})</button>` : ""}
      </div>
    </div>
    ${
      connMode() === "none"
        ? `<div class="card">
      <h3 class="eyebrow">Ask questions while you read</h3>
      <p class="lede">Connect the tutor once and you can select any sentence in any module and talk about it, have your written answers checked, and practise live conversations.</p>
      <button class="btn" onclick="go('#/settings')">Connect the tutor</button></div>`
        : ""
    }
  </div>`;

  if (offers.length) {
    h += `<div class="card accented gap-bottom">
      <h3 class="eyebrow accent-ink" title="${esc(help("checkpoint"))}">Checkpoint ready</h3>
      <p class="lede">A mixed quiz across everything you finished. This is the only score that says whether it stuck — module quizzes measure recognition ten minutes after reading.</p>
      <div class="rowline wrapped">${offers.map(o => `<button class="btn sm" onclick="startCheckpoint('${o.kind}','${o.pid || ""}')">${esc(o.label)}</button>`).join("")}</div>
    </div>`;
  }
  if (openQs()) {
    h += `<div class="card gap-bottom">
      <h3 class="eyebrow">Open questions</h3>
      <p class="lede">You have <b>${openQs()}</b> passage${openQs() > 1 ? "s" : ""} marked with a question you have not answered yet. These are the edges of what you understand — the highest-value thing you can spend ten minutes on.</p>
      <button class="btn" onclick="markFilter='open';go('#/marks')">Open the question list</button></div>`;
  }
  h += renderGapCard();
  if (weak.length || dropped.length) {
    h += `<div class="card warmcard gap-bottom">
      <h3 class="eyebrow warnnote">Worth revisiting</h3>
      <p class="lede">${weak.length ? "You scored below 70% on these. " : ""}${dropped.length ? "Some slipped in a checkpoint. " : ""}Low scores are information, not failure — re-read just the relevant section and retake.</p>
      <div class="rowline wrapped">
      ${weak.map(w => `<button class="btn sm" onclick="go(stepHash('${w.m.id}',2))">${w.m.id} · ${esc(w.m.short)} — ${Math.round(w.pct * 100)}%</button>`).join("")}
      ${dropped
        .filter(m => !weak.some(w => w.m === m))
        .map(
          m =>
            `<button class="btn sm" onclick="go(stepHash('${m.id}',2))">${m.id} · ${esc(m.short)} — slipped</button>`
        )
        .join("")}
      </div>
    </div>`;
  }

  h += `<h3 class="eyebrow gap-top-lg">The map</h3><div class="grid g3">`;
  DATA.parts.forEach(p => {
    const ms = MODS.filter(m => m.part === p.id),
      d = ms.filter(isDone).length;
    h += `<div class="card tight">
      <div class="rowline mapttl"><b>${esc(p.name)}</b><span class="tag">${p.hours}h</span><span class="sub mapcount">${d}/${ms.length}</span></div>
      <div class="bar gap-bottom"><i style="width:${Math.round((d / ms.length) * 100)}%"></i></div>
      <p class="sub gap-bottom">${esc(p.blurb)}</p>
      ${ms.map(m => `<a class="mrow flat" href="#/m/${m.id}" title="${mastery(m).name} — ${esc(help(mastery(m).name))}"><span class="dot ${masteryClass(m)}"></span><span class="code">${m.id}</span><span class="t">${esc(m.short)}</span>${(m.requires || []).length ? `<span class="req" title="Builds on ${m.requires.join(", ")}">← ${m.requires.join(" ")}</span>` : ""}</a>`).join("")}
    </div>`;
  });
  h += `</div></div>`;
  $("#view").innerHTML = h;
  bindPlanCard();
}

/* First visit: what this page is and how it is meant to be used. It is dismissed once and
   then lives in the ? panel, because an explainer nobody can get rid of is furniture. */
function introCard() {
  if ((STATE.ui || {}).introSeen) return "";
  return `<div class="card raised gap-bottom" id="introcard">
    <h3 class="eyebrow">How this course works</h3>
    <p class="lede">${howItWorksHtml()}</p>
    <div class="rowline wrapped">
      <button class="btn primary" onclick="dismissIntro()">Got it</button>
      <button class="btn" onclick="openHelp()">See the shortcuts too</button>
    </div>
  </div>`;
}
function howItWorksHtml() {
  return `Every module runs the same six steps: <b>Predict</b> a guess before you read,
    <b>Read</b> the sections, <b>Retrieve</b> what you can in a quiz, <b>Elaborate</b> in your
    own words, <b>Apply</b> it to a case you have not seen, and <b>Close the gaps</b> the rest
    turned up. Finishing a module drops its flashcards into your practice deck, which brings
    each one back just before you would forget it. A question you miss becomes a card of its
    own. Days later, a checkpoint mixes questions across a whole part — that score, not the
    module quiz, is what says the material stuck.`;
}
function dismissIntro() {
  if (!STATE.ui) STATE.ui = {};
  STATE.ui.introSeen = true;
  save();
  const el = document.getElementById("introcard");
  if (el) el.remove();
}

function greeting() {
  const hr = new Date().getHours();
  return hr < 12 ? "Good morning" : hr < 18 ? "Good afternoon" : "Good evening";
}
/* Where a module was left: the furthest step with anything in it, and the last section read. */
function resumeStepIndex(m) {
  const p = progressOf(m.id);
  if (p.gapsAt && openGapItems(m.id).length) return 5;
  if (p.transfer && (p.transfer.answer || "").trim()) return 4;
  if (Object.values(p.elab).some(v => (v || "").trim())) return 3;
  if (p.quiz && !p.quiz.finished && p.quiz.a.length) return 2;
  if (secDone(m) > 0 || (STATE.pos[m.id] || 0) > 0) return 1;
  if (p.predict.trim()) return 1;
  return 0;
}
function resumeHash(m) {
  return stepHash(m.id, resumeStepIndex(m));
}
function resumeLabel(m) {
  const s = resumeStepIndex(m),
    pos = STATE.pos[m.id] || 0;
  if (s === 1 && pos > 0 && m.sections[pos]) return " · at “" + esc(m.sections[pos].h) + "”";
  if (s === 2) return " · in the quiz";
  if (s === 3) return " · elaborating";
  if (s === 4) return " · applying";
  if (s === 5) return " · closing gaps";
  return "";
}
