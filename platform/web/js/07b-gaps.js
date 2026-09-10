/* ---- step 6 of a module: close the gaps ----
   The last step of the cycle drills what the module's own record says went wrong: the
   gaps named for this module, the quiz questions missed, the cards that keep
   lapsing, the exercises a grader marked partial or wrong (`gapItems` in 17c-learner.js).
   Each one is a question; the reader answers in writing, the tutor grades it against the
   module text and the original miss, and a correct answer closes the item. With no tutor
   the reader scores themselves. Answers and verdicts live in `progressOf(mid).gapWork`
   keyed by the item, so a closed item stays closed and the chips in the rail skip it. */
function renderGapStep(m) {
  const p = progressOf(m.id),
    b = $("#stepbody");
  const items = gapItems(m.id),
    open = items.filter(it => !gapItemClosed(m.id, it)),
    closed = items.filter(it => gapItemClosed(m.id, it));
  if (!p.gapsAt) {
    p.gapsAt = Date.now();
    save();
  }
  let s = `<div class="card"><h3 class="eyebrow">Step 6 · Close the gaps</h3>
    <p class="hint gap-bottom"><span class="i">Why</span> A quiz tells you what you missed; it does not fix it. Each item below is one thing this module's record says went wrong, turned into a question. Answer it in writing and have it checked - the gap closes only when the explanation is right, not when the answer is recognised.</p>`;
  if (!items.length) {
    s += `<p class="lede">Nothing to close here${learnerEventCount() ? "" : " yet"}. ${
      learnerEventCount()
        ? "The quiz, the exercises and your questions in this module left no gap on record."
        : "Gaps come from the quiz, the graded exercises and what you ask the tutor - do those first."
    }</p>`;
  } else if (!open.length) {
    s += `<p class="oknote gap-bottom"><b>All ${items.length} closed.</b> ${connMode() !== "none" && learnerStale() ? "Update your profile so the tutor stops working on them." : "The tutor stops leading with them."}</p>`;
  } else {
    s += `<p class="sub gap-bottom-sm">${open.length} open${closed.length ? ` · ${closed.length} closed` : ""}</p>`;
  }
  s += gapRefreshOffer(m);
  s += `</div>`;
  open.forEach(it => (s += gapDrillCard(m, it)));
  if (closed.length)
    s += `<details class="gap-top"><summary class="sub padded">${closed.length} closed - open to see or reopen</summary>${closed.map(it => gapDrillCard(m, it)).join("")}</details>`;
  if (!isDone(m))
    s += `<div class="card gap-top centered"><p class="sub gap-bottom">${open.length ? "You can mark the module complete now and come back to the open gaps; they stay in the tutor's prompt until closed." : "Finished all six steps?"}</p><button class="btn primary" onclick="toggleDone('${m.id}')">Mark ${m.id} complete and unlock its flashcards</button></div>`;
  b.innerHTML = s;
}
/* The tutor can name gaps this module's record only hints at: offered when connected and the
   brief is behind the evidence. */
function gapRefreshOffer(m) {
  if (connMode() === "none" || !learnerStale()) return "";
  const busy = learnerRun.busy;
  return `<div class="rowline wrapped">
    <button class="btn sm" onclick="refreshLearner().then(() => renderStep(byId('${m.id}'), 5))" ${busy ? "disabled" : ""}>${busy ? "Reading your work…" : "Have the tutor name the gaps from my work"}</button>
    <span class="sub tiny">Your profile is behind what you have done since.</span></div>`;
}
function gapDrillCard(m, it) {
  const work = gapWorkOf(m.id, it.key),
    closed = gapItemClosed(m.id, it);
  const source =
    {
      brief: "named by the tutor",
      quiz: "missed in the quiz",
      lapse: "keeps lapsing in review",
      graded: "graded " + (it.verdict || "partial"),
    }[it.source] || "";
  const fb = work.verdict
    ? `<div class="fb ${work.verdict}"><b>The tutor's read · ${work.verdict}</b>${mdLite(work.text || "")}</div>`
    : "";
  const actions = closed
    ? `<button class="btn sm" onclick="reopenGapItem('${m.id}','${esc(it.key)}')">Reopen</button>`
    : `${connMode() !== "none" ? `<button class="btn primary" id="gapck-${esc(it.key)}" onclick="checkGapAnswer('${m.id}','${esc(it.key)}')">Check my answer</button>` : ""}
       <button class="btn ${connMode() === "none" ? "primary" : ""}" onclick="selfScoreGap('${m.id}','${esc(it.key)}',true)">${connMode() !== "none" ? "I have got it, close it" : "I have got it"}</button>
       <button class="btn" onclick="selfScoreGap('${m.id}','${esc(it.key)}',false)">Still shaky, save</button>
       <button class="btn" onclick="askAbout('${m.id}', this.dataset.q)" data-q="${esc(it.ask)}">Ask the tutor</button>`;
  return `<div class="card gapdrill gap-top ${closed ? "closed" : ""}">
    <div class="gaphead"><b>${esc(it.topic)}</b><span class="tag">${source}</span>${closed ? `<span class="tag ok">closed</span>` : ""}</div>
    <p class="gapwhy">${esc(it.why)}</p>
    <h3 class="h-serif drillq">${esc(it.ask)}</h3>
    ${closed ? `${work.answer ? `<div class="quote">${esc(work.answer)}</div>` : ""}` : `<textarea id="gapin-${esc(it.key)}" rows="4" placeholder="Answer in your own words, and say why - the why is what is being checked.">${esc(work.answer || "")}</textarea>`}
    <div class="rowline wrapped gap-top">${actions}</div>
    <div id="gapfb-${esc(it.key)}">${fb}</div>
  </div>`;
}
function gapAnswerText(mid, key) {
  const ta = document.getElementById("gapin-" + key);
  return ta ? ta.value.trim() : (gapWorkOf(mid, key).answer || "").trim();
}
async function checkGapAnswer(mid, key) {
  const m = byId(mid),
    it = gapItems(mid).find(x => x.key === key);
  if (!m || !it) return;
  const text = gapAnswerText(mid, key);
  if (!text) {
    toast("Write your answer first");
    const ta = document.getElementById("gapin-" + key);
    if (ta) ta.focus();
    return;
  }
  const work = gapWorkOf(mid, key);
  work.answer = text;
  save();
  const btn = document.getElementById("gapck-" + key),
    box = document.getElementById("gapfb-" + key);
  graderStart(btn, "Checking…");
  try {
    const sys =
      graderPersona() +
      `\n\nThe reader is closing a gap in module ${m.id}, "${m.title}". What the record says went wrong: ${it.why}${it.answer ? `\nThe right answer to the original question, and why: ${it.answer}` : ""}\n\nThe course text it draws on:\n"""\n${sectionContext(m, 5000)}\n"""\n\n` +
      verdictFormat() +
      '\nMark "correct" only if the explanation shows the misconception is gone - a right answer with the wrong reasoning is "partial".';
    const fb = parseVerdict(
      await askBridge(sys, [
        { role: "user", content: `Question: ${it.ask}\n\nThe reader wrote:\n"""\n${text}\n"""` },
      ])
    );
    Object.assign(work, fb);
    if (fb.verdict === "correct") closeGapItem(mid, it, "drill");
    save();
    markDay();
    maybeRefreshLearner();
    if (fb.verdict === "correct") {
      toast("Gap closed");
      renderStep(m, 5);
      renderSidebar();
      return;
    }
    if (box)
      box.innerHTML = `<div class="fb ${fb.verdict}"><b>The tutor's read · ${fb.verdict}</b>${mdLite(fb.text)}</div>`;
    graderDone(btn, "Check again");
  } catch (e) {
    graderFailed(btn, box, e, `checkGapAnswer('${mid}','${esc(key)}')`);
  }
}
/* No connection, or the reader's own word: what they wrote is kept either way. */
function selfScoreGap(mid, key, got) {
  const it = gapItems(mid).find(x => x.key === key);
  if (!it) return;
  const work = gapWorkOf(mid, key);
  work.answer = gapAnswerText(mid, key);
  work.self = got ? 3 : 1;
  work.at = Date.now();
  if (got) closeGapItem(mid, it, "self");
  save();
  markDay();
  toast(got ? "Closed - it stays out of the tutor's prompts" : "Saved - it stays open");
  renderStep(byId(mid), 5);
  renderSidebar();
}
