/* ---- the tutor as grader ----
   Every written answer on the page can be checked: a quiz short answer, an Elaborate
   prompt, the Apply exercise, a filled worksheet, a role-play transcript. One prompt shape
   for all of them: the course text it draws on, what was asked, the model answer where one
   exists, what the reader wrote — and a reply that opens with a one-word verdict so the
   page can act on it, followed by what was covered, what was missing, what was wrong, and
   one follow-up question. Nothing here works without a connection; every caller degrades
   to self-scoring. */
function graderPersona() {
  return `${CFG.tutorPersona} You are checking a ${CFG.audience}'s written work in a ${CFG.subject} course. Be exact and brief. Praise nothing that was not earned.`;
}
function verdictFormat() {
  return `Reply in this exact shape:
VERDICT: correct | partial | wrong
**Covered** — what the answer gets right, in one or two lines.
**Missing** — what a good answer needed that this one lacks. Say "nothing" if nothing.
**Wrong** — anything stated that is false or muddled. Say "nothing" if nothing.
**Ask yourself** — one question that would push this answer further.
Under 160 words after the verdict line. No preamble.`;
}
function parseVerdict(reply) {
  const m = String(reply).match(/VERDICT:\s*(correct|partial|wrong)/i);
  const verdict = m ? m[1].toLowerCase() : "partial";
  const text =
    String(reply)
      .replace(/^[\s\STATE]*?VERDICT:[^\n]*\n?/i, "")
      .trim() || reply;
  return { verdict, text, at: Date.now() };
}
function sectionContext(m, limit) {
  return m.sections
    .map(
      s =>
        s.h + ": " + s.text.slice(0, Math.floor((limit || 6000) / Math.max(1, m.sections.length)))
    )
    .join("\n");
}
async function gradeShort(it, answer) {
  const m =
    byId(route.view === "m" ? route.id : QUIZ && QUIZ.kind === "cp" ? qItem().mid : route.id) ||
    MODS[0];
  const sys =
    graderPersona() +
    "\n\nThe question comes from module " +
    m.id +
    ', "' +
    m.title +
    '".\n\n' +
    verdictFormat();
  const user = `Question: ${it.q}\n\nWhat a good answer contains: ${it.model}\n\nThe reader wrote:\n"""\n${answer}\n"""\n\nMark "correct" only if the reader's answer carries the substance of the model answer in their own words; "partial" if it has some of it; "wrong" if it misses the point or asserts something false.`;
  return parseVerdict(await askBridge(sys, [{ role: "user", content: user }]));
}
/* One way of running a graded call: the button says what it is doing and goes back to
   what it said before, and a failure lands in the reply box with a Retry — not in a toast
   that is gone in two seconds while the box sits empty. */
function graderStart(btn, working) {
  if (!btn) return "";
  const was = btn.dataset.label || btn.textContent;
  btn.dataset.label = was;
  btn.disabled = true;
  btn.textContent = working;
  return was;
}
function graderDone(btn, doneLabel) {
  if (!btn) return;
  btn.disabled = false;
  btn.textContent = doneLabel;
  btn.dataset.label = doneLabel;
}
function graderFailed(btn, box, err, retry) {
  const message = (err && err.message) || "The tutor did not answer.";
  if (btn) {
    btn.disabled = false;
    btn.textContent = btn.dataset.label || btn.textContent;
  }
  // An account that is out until three has nothing to fix in Settings, so it is not offered.
  const settings = worthCheckingSettings(troubleOf(err))
    ? `<a class="btn sm ghost" href="#/settings">Check the connection</a>`
    : "";
  if (box)
    box.innerHTML = `<div class="fb wrong"><b>Nothing came back</b>
      <p>${esc(message)}</p>
      <div class="rowline wrapped gap-top">
        <button class="btn sm" onclick="${retry}">Try again</button>${settings}
      </div></div>`;
  else toast(message, { kind: "bad" });
}

async function checkElab(mid, i) {
  const m = byId(mid),
    p = progressOf(mid),
    ta = document.querySelector(`[data-el="${i}"]`);
  const text = ta ? ta.value.trim() : (p.elab[i] || "").trim();
  if (!text) {
    toast("Write something first");
    if (ta) ta.focus();
    return;
  }
  p.elab[i] = text;
  save();
  const btn = document.getElementById("elabck" + i),
    box = document.getElementById("elabfb" + i);
  graderStart(btn, "Checking…");
  try {
    const sys =
      graderPersona() +
      "\n\nThe reader is explaining an idea from module " +
      m.id +
      ', "' +
      m.title +
      '", in their own words. The course text it draws on:\n"""\n' +
      sectionContext(m, 5000) +
      '\n"""\n' +
      (STATE.biz ? "\n" + (CFG.anchor || {}).label + ": " + STATE.biz + "\n" : "") +
      "\n" +
      verdictFormat();
    const fb = parseVerdict(
      await askBridge(sys, [
        {
          role: "user",
          content: `Prompt: ${m.assess.elaborate[i]}\n\nThe reader wrote:\n"""\n${text}\n"""`,
        },
      ])
    );
    p.elabFb[i] = fb;
    save();
    markDay();
    maybeRefreshLearner();
    if (box)
      box.innerHTML = `<div class="fb ${fb.verdict}"><b>What the tutor saw</b>${mdLite(fb.text)}</div>`;
    graderDone(btn, "Check again");
  } catch (e) {
    graderFailed(btn, box, e, `checkElab('${mid}',${i})`);
  }
}
async function checkTransfer(mid) {
  const m = byId(mid),
    p = progressOf(mid),
    ta = document.getElementById("trin");
  const text = ta ? ta.value.trim() : ((p.transfer || {}).answer || "").trim();
  if (!text) {
    toast("Write your answer first — that is the whole exercise");
    if (ta) ta.focus();
    return;
  }
  p.transfer = Object.assign({}, p.transfer, { answer: text });
  save();
  const btn = document.getElementById("trck"),
    box = document.getElementById("trfb"),
    t = m.assess.transfer;
  graderStart(btn, "Grading…");
  try {
    const sys =
      graderPersona() +
      "\n\nThe reader is applying module " +
      m.id +
      ', "' +
      m.title +
      '", to a situation the module never discussed. The course text it draws on:\n"""\n' +
      sectionContext(m, 5000) +
      '\n"""\n\n' +
      verdictFormat();
    const fb = parseVerdict(
      await askBridge(sys, [
        {
          role: "user",
          content: `Scenario: ${t.scenario}\n\nTask: ${t.prompt}\n\nModel answer (the reader has NOT seen this yet — do not quote it back, use it to judge):\n"""\n${t.model}\n"""\n\nThe reader wrote:\n"""\n${text}\n"""`,
        },
      ])
    );
    p.transfer.fb = fb;
    save();
    markDay();
    maybeRefreshLearner();
    if (box)
      box.innerHTML = `<div class="fb ${fb.verdict}"><b>The tutor's read · ${fb.verdict}</b>${mdLite(fb.text)}</div>`;
    renderSidebar();
    graderDone(btn, "Grade it again");
  } catch (e) {
    graderFailed(btn, box, e, `checkTransfer('${mid}')`);
  }
}

/* ---- role-play: the tutor plays the other side ---- */
function startRoleplay(mid) {
  const m = byId(mid),
    rp = m.assess.roleplay;
  if (!rp) return;
  const c = newConvo(
    { mid, step: null, sec: null },
    { title: "Role-play: " + rp.goal.slice(0, 50), kind: "rp" }
  );
  c.msgs.push({
    r: "a",
    t: rp.situation + "\n\n_You speak first. Say what you would actually say._",
    ts: Date.now(),
  });
  save();
  rail.showing = c.id;
  showRail();
  renderRail();
  const inp = document.getElementById("railin");
  if (inp) inp.focus();
  toast("In character — the tutor stays the other side until you finish");
}
function roleplaySystem(m, rp) {
  return `${rp.persona} Stay in character for the whole conversation: you are not a tutor and you do not coach, explain the course, or break character unless the reader writes "pause". Respond the way this person really would — with their own concerns, doubts and pushback — in one to four sentences per turn. The situation: ${rp.situation}${STATE.biz ? ` ${(CFG.anchor || {}).label}: ${STATE.biz}.` : ""} Do not make it easy; do not make it impossible.`;
}
async function finishRoleplay(mid) {
  const m = byId(mid),
    rp = m.assess.roleplay,
    c = convoShown();
  if (!rp || !c || c.kind !== "rp" || c.mid !== mid) return;
  const turns = c.msgs.filter(x => x.r === "u").length;
  if (turns < 2) {
    toast("Have at least a couple of exchanges first");
    return;
  }
  if (rail.finishing) return;
  rail.finishing = true;
  const fbtn = document.getElementById("rpfinish");
  graderStart(fbtn, "Getting feedback…");
  try {
    const transcript = c.msgs
      .filter(x => x.r !== "e")
      .map(x => (x.r === "u" ? "READER: " : "OTHER SIDE: ") + x.t)
      .join("\n\n");
    const sys =
      graderPersona() +
      `\n\nThe reader just practised a conversation from module ${m.id}, "${m.title}". They played themselves; the other side was played by a model. Judge the reader's lines only, against this rubric:\n${rp.rubric.map((r, i) => i + 1 + ". " + r).join("\n")}\n\nGoal they were given: ${rp.goal}\n\nReply in this exact shape:\nVERDICT: correct | partial | wrong   (correct = goal reached and rubric met; partial = some of it; wrong = neither)\nThen one line per rubric item, quoting the reader's own words where they helped or hurt.\nThen **Say it instead** — the single line they should have said at the moment that mattered most.\nUnder 200 words after the verdict line.`;
    const fb = parseVerdict(
      await askBridge(sys, [{ role: "user", content: transcript.slice(-TUTOR.gradeChars) }])
    );
    const p = progressOf(mid);
    p.transfer = Object.assign({}, p.transfer, { rp: fb });
    save();
    markDay();
    c.msgs.push({ r: "a", t: "**Feedback**\n\n" + fb.text, ts: Date.now() });
    c.updated = Date.now();
    c.finished = true;
    save();
    maybeRefreshLearner();
    renderRail();
    if (route.view === "m" && route.step === 4) renderStep(m, 4);
  } catch (e) {
    toast((e && e.message) || "The tutor did not answer.", { kind: "bad" });
    graderDone(fbtn, "Finish & get feedback");
  }
  rail.finishing = false;
}

/* ---- a filled worksheet ---- */
async function reviewSheet(slug) {
  const t = DATA.library.templates.find(x => x.slug === slug);
  if (!t) return;
  if (!sheetFilled(slug)) {
    toast("Fill something in first");
    return;
  }
  const btn = document.getElementById("sheetreview"),
    box = document.getElementById("sheetfb");
  graderStart(btn, "Reviewing…");
  try {
    const mods = (t.uses || []).map(byId).filter(Boolean);
    const ctx = mods
      .map(m => "Module " + m.id + " " + m.title + ":\n" + sectionContext(m, 3000))
      .join("\n\n");
    const sys =
      graderPersona() +
      `\n\nThe reader filled in a worksheet called "${t.title}" from the course.${ctx ? ' The modules it comes from:\n"""\n' + ctx + '\n"""' : ""}${STATE.biz ? "\n" + (CFG.anchor || {}).label + ": " + STATE.biz : ""}\n\nJudge whether what they wrote is specific, internally consistent, and usable — not whether it is complete. Blank fields shown as ____ are fine to mention once, not to list.\n\n` +
      verdictFormat().replace("Under 160", "Under 220");
    const fb = parseVerdict(
      await askBridge(sys, [{ role: "user", content: sheetText(t).slice(0, 12000) }])
    );
    sheetVals(slug)._fb = fb;
    save();
    markDay();
    maybeRefreshLearner();
    if (box)
      box.innerHTML = `<div class="fb ${fb.verdict}"><b>The tutor's review</b>${mdLite(fb.text)}</div>`;
    graderDone(btn, "Review again");
  } catch (e) {
    graderFailed(btn, box, e, `reviewSheet('${slug}')`);
  }
}
