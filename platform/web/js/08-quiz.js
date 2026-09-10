/* ---------- quiz engine ----------
   One renderer for every place questions appear: a module's Retrieve step and the mixed
   checkpoints. `QUIZ` names the quiz being drawn; the handlers read it rather than taking a
   module id, so the keyboard layer and the checkpoint page share the same code path.

   QUIZ = { kind: "m" | "cp", host: css selector, items: [{ mid, qi, it }], qs, onDone }
   qs = { i, a: [], finished, seed }      a[i] = { resp, committed, answered, ok, conf, hinted, self, ai }
*/
let QUIZ = null,
  shortGrading = false;

/* The result card a quiz and a checkpoint both end on: one big percentage, one honest
   sentence, the calibration note when it is earned, and the buttons for what comes next.
   Both used to build their own; they drifted, and one of them carried a subject word. */
function scoreBlock(o) {
  const band = o.pct >= 80 ? "ok" : o.pct >= 60 ? "warm" : "bad";
  const calib = o.overconf
    ? `<div class="hint narrow gap-bottom-lg" title="${esc(help("calibration"))}"><span class="i">Calibration</span>
       You were "certain" and wrong ${o.overconf} time${o.overconf > 1 ? "s" : ""}. That is the most
       valuable signal on this page: a belief you hold confidently and cannot support is the one that
       will catch you out when it matters.</div>`
    : "";
  return `<div class="card centered">
    ${o.eyebrow ? `<h3 class="eyebrow">${esc(o.eyebrow)}</h3>` : ""}
    <div class="bigscore ${band}">${o.pct}%</div>
    <p class="sub gap-bottom">${o.line}</p>
    <p class="lede narrow">${esc(o.verdict)}</p>
    ${calib}
    <div class="rowline center wrapped">${o.actions}</div></div>`;
}

function renderQuiz(m) {
  const p = progressOf(m.id);
  if (!p.quiz) p.quiz = { i: 0, a: [], finished: false, seed: Math.floor(Math.random() * 1e6) };
  if (!p.quiz.seed) p.quiz.seed = 7;
  QUIZ = {
    kind: "m",
    host: "#stepbody",
    mid: m.id,
    qs: p.quiz,
    items: m.assess.quiz.map((it, qi) => ({ mid: m.id, qi, it })),
    onDone: () => {
      renderSidebar();
      quizResults(m);
    },
  };
  drawQuiz();
}
function qState() {
  const qs = QUIZ.qs;
  if (!qs.a[qs.i]) qs.a[qs.i] = { resp: null, committed: false, answered: false, hinted: 0 };
  return qs.a[qs.i];
}
function qItem() {
  return QUIZ.items[QUIZ.qs.i];
}
function qSeed() {
  return (QUIZ.qs.seed || 7) + QUIZ.qs.i * 31;
}

function drawQuiz() {
  const host = $(QUIZ.host);
  if (!host) return;
  const qs = QUIZ.qs;
  if (qs.finished) return QUIZ.onDone();
  const { it, mid } = qItem(),
    st = qState(),
    t = it.type || "single";
  const n = QUIZ.items.length;
  let h = `${qs.i === 0 && QUIZ.kind !== "cp" ? `<p class="hint gap-bottom"><span class="i">Why</span> Pulling an answer out of memory, and being wrong, does more for retention than reading the passage again. Answer before you look anything up: a miss here is worth more than a hit.</p>` : ""}
    <div class="card">
    <div class="qmeta"><span>Question ${qs.i + 1} of ${n}</span>
      <span class="bar"><i style="width:${Math.round((qs.i / n) * 100)}%"></i></span>
      ${QUIZ.kind === "cp" ? `<span class="tag acc">${mid}</span>` : ""}
      <span class="tag">${TYPE_LABEL[t] || ""}</span>
      <span class="pushright">${qs.a.filter(x => x && x.ok).length} correct so far</span></div>
    <h3 class="h-serif qhead">${t === "cloze" ? clozeHtml(it, st) : esc(it.q)}</h3>`;
  h += answerArea(it, st);
  if (!st.answered) {
    const hints = it.hints || [];
    if (st.hinted)
      h += hints
        .slice(0, st.hinted)
        .map((x, i) => `<div class="hintbox"><b>Hint ${i + 1}</b>${esc(x)}</div>`)
        .join("");
    if (!st.committed) {
      h += `<div class="rowline wrapped gap-top">
        ${t !== "single" && t !== "tf" ? `<button class="btn primary" onclick="qCommit()">Lock in answer</button>` : ""}
        ${hints.length && st.hinted < hints.length ? `<button class="btn sm" onclick="qHint()">Hint ${st.hinted + 1} of ${hints.length}</button>` : ""}
        ${st.hinted ? `<span class="sub" title="${esc(help("mistake card"))}">A question answered after a hint becomes a mistake card either way.</span>` : ""}
      </div>`;
    } else {
      h += `<div class="conf"><span class="sub" title="${esc(help("calibration"))}">How sure are you?</span>
        ${[
          ["Guessing", 1],
          ["Fairly sure", 2],
          ["Certain", 3],
        ]
          .map(
            ([l, v], i) =>
              `<button class="btn sm" onclick="qAnswer(${v})"><kbd>${i + 1}</kbd> ${l}</button>`
          )
          .join("")}
        ${t !== "single" && t !== "tf" ? `<button class="btn sm ghost" onclick="qUncommit()">Change answer</button>` : ""}</div>
        <p class="sub gap-top tiny">Rating your confidence trains calibration — knowing what you actually know is most of what separates a good ${esc(CFG.practitioner)} from a confident one.</p>`;
    }
  } else {
    h += verdictHtml(it, st);
    if (st.ok != null)
      h += `<div class="rowline gap-top"><button class="btn primary" onclick="qNext()">${qs.i === n - 1 ? "See results" : "Next question"} <kbd>↵</kbd></button></div>`;
  }
  h += `</div>`;
  host.innerHTML = h;
  const first = host.querySelector("input[type=text],input[type=number]");
  if (first && !st.answered) first.focus();
}

/* ---- the answer area, one shape per type ---- */
function answerArea(it, st) {
  const t = it.type || "single",
    locked = st.committed || st.answered;
  if (t === "single" || t === "tf") {
    const opts = t === "tf" ? ["True", "False"] : it.options;
    const ans = t === "tf" ? (it.answer ? 0 : 1) : it.answer;
    const pick = t === "tf" ? (st.resp === true ? 0 : st.resp === false ? 1 : null) : st.resp;
    return opts
      .map((o, i) => {
        let cls = "";
        if (st.answered) {
          if (i === ans) cls = "right";
          else if (i === pick) cls = "wrong";
        } else if (pick === i) cls = "sel";
        return `<button class="opt ${cls}" ${st.answered ? "disabled" : ""} onclick="qPick(${i})"><span class="k">${"ABCDEFGH"[i]}</span><span>${esc(o)}</span></button>`;
      })
      .join("");
  }
  if (t === "multi") {
    const picks = Array.isArray(st.resp) ? st.resp : [];
    return (
      it.options
        .map((o, i) => {
          let cls = picks.includes(i) ? "sel" : "";
          if (st.answered) {
            const should = it.answer.includes(i);
            cls =
              should && picks.includes(i)
                ? "right"
                : !should && picks.includes(i)
                  ? "wrong"
                  : should
                    ? "missed"
                    : "";
          }
          return `<button class="opt ${cls}" ${locked ? "disabled" : ""} onclick="qToggle(${i})"><span class="k">${picks.includes(i) ? "✓" : "ABCDEFGH"[i]}</span><span>${esc(o)}</span></button>`;
        })
        .join("") +
      (locked
        ? ""
        : `<p class="sub tiny gap-top-sm">Select every option that applies, then lock in.</p>`)
    );
  }
  if (t === "numeric") {
    return `<div class="numrow"><input type="text" inputmode="decimal" id="qin" value="${esc(st.resp == null ? "" : st.resp)}" placeholder="Your figure" ${locked ? "disabled" : ""} oninput="qSet(this.value)" onkeydown="if(event.key==='Enter'){event.preventDefault();qCommit()}">${it.unit ? `<span class="unit">${esc(it.unit)}</span>` : ""}</div>`;
  }
  if (t === "cloze")
    return `<p class="sub">Type the missing word or phrase into the blank above${locked ? "" : ", then lock in"}.</p>`;
  if (t === "short") {
    return `<textarea id="qin" rows="4" placeholder="One or two sentences. Say the thing, do not describe it." ${locked ? "disabled" : ""} oninput="qSet(this.value)">${esc(st.resp || "")}</textarea>`;
  }
  if (t === "order") {
    const order = Array.isArray(st.resp) ? st.resp : perm(it.options.length, qSeed());
    return `<div class="orderlist">${order
      .map(
        (oi, pos) => `<div class="orow ${st.answered ? (oi === pos ? "right" : "wrong") : ""}">
      <span class="k">${pos + 1}</span><span style="flex:1">${esc(it.options[oi])}</span>
      ${locked ? "" : `<button class="iconbtn" ${pos === 0 ? "disabled" : ""} onclick="qMove(${pos},-1)" title="Move “${esc(it.options[oi])}” up" aria-label="Move “${esc(it.options[oi])}” up">${ico("up", 15)}</button><button class="iconbtn" ${pos === order.length - 1 ? "disabled" : ""} onclick="qMove(${pos},1)" title="Move “${esc(it.options[oi])}” down" aria-label="Move “${esc(it.options[oi])}” down">${ico("down", 15)}</button>`}
    </div>`
      )
      .join(
        ""
      )}</div>${locked ? "" : `<p class="sub">Arrange from first to last, then lock in.</p>`}`;
  }
  if (t === "match") {
    const rights = perm(it.pairs.length, qSeed());
    const resp = st.resp || {};
    return `<div class="matchlist">${it.pairs
      .map(
        (p, li) => `<div class="mrow2 ${st.answered ? (resp[li] === li ? "right" : "wrong") : ""}">
      <span class="left">${esc(p[0])}</span><span class="arrow">→</span>
      <select ${locked ? "disabled" : ""} onchange="qMatch(${li},this.value)">
        <option value="">…</option>
        ${rights.map(ri => `<option value="${ri}" ${resp[li] === ri ? "selected" : ""}>${esc(it.pairs[ri][1])}</option>`).join("")}
      </select></div>`
      )
      .join("")}</div>`;
  }
  return "";
}
function clozeHtml(it, st) {
  const parts = it.q.split("___");
  const locked = st.committed || st.answered;
  const cls = st.answered ? (st.ok ? "right" : "wrong") : "";
  return (
    esc(parts[0]) +
    `<input type="text" class="clozein ${cls}" id="qin" value="${esc(st.resp || "")}" ${locked ? "disabled" : ""} oninput="qSet(this.value)" onkeydown="if(event.key==='Enter'){event.preventDefault();qCommit()}" size="${Math.max(6, String(correctText(it)).length)}">` +
    esc(parts.slice(1).join("___"))
  );
}

/* ---- after the answer ---- */
function verdictHtml(it, st) {
  const t = it.type || "single";
  let h = "";
  if (t === "short") {
    h += `<div class="why gap-top"><b class="whyttl">Model answer</b>${esc(it.model)}</div>`;
    if (st.ai)
      h += `<div class="fb ${st.ai.verdict}"><b>${st.ai.verdict === "correct" ? "That covers it" : st.ai.verdict === "partial" ? "Partly there" : "Not yet"}</b>${mdLite(st.ai.text)}</div>`;
    else if (shortGrading) h += `<div class="msg a typing gap-top"><i></i><i></i><i></i></div>`;
    if (st.ok == null && !shortGrading) {
      h += `<div class="conf"><span class="sub">${connMode() === "none" ? "How did yours compare?" : "Or score it yourself:"}</span>
        ${[
          ["Missed it", 1],
          ["Partly there", 2],
          ["Got it", 3],
        ]
          .map(([l, v]) => `<button class="btn sm" onclick="qSelf(${v})">${l}</button>`)
          .join("")}
        ${connMode() !== "none" ? `<button class="btn sm primary" onclick="gradeShortNow()">Ask the tutor to check</button>` : ""}</div>`;
    } else if (st.self)
      h += `<p class="sub gap-top">Self-scored: ${["", "missed it", "partly there", "got it"][st.self]}.</p>`;
    if (st.ok != null) h += `<div class="why"><b class="whyttl">Why</b>${esc(it.why)}</div>`;
    return h;
  }
  const head = st.ok
    ? "Correct" + (st.hinted ? " — with a hint" : "")
    : "Not quite — the answer is " + esc(correctText(it));
  h += `<div class="why"><b style="color:${st.ok ? "var(--ok)" : "var(--bad)"};display:block;margin-bottom:6px">${head}</b>${esc(it.why)}</div>`;
  if (it.feedback && (t === "single" || t === "tf")) {
    const pick = t === "tf" ? (st.resp === true ? 0 : 1) : st.resp,
      ans = t === "tf" ? (it.answer ? 0 : 1) : it.answer;
    if (!st.ok && it.feedback[pick])
      h += `<div class="fbline wrong"><b>Your pick</b>${esc(it.feedback[pick])}</div>`;
    if (it.feedback[ans])
      h += `<div class="fbline right"><b>The answer</b>${esc(it.feedback[ans])}</div>`;
  }
  if (it.feedback && t === "multi") {
    const picks = st.resp || [];
    h += it.options
      .map((o, i) => {
        const should = it.answer.includes(i),
          did = picks.includes(i);
        if (should === did && !should) return "";
        return `<div class="fbline ${should ? "right" : "wrong"}"><b>${should ? (did ? "✓" : "missed") : "✗"} ${esc(o)}</b>${esc(it.feedback[i] || "")}</div>`;
      })
      .join("");
  }
  if (!st.ok || st.hinted)
    h += `<p class="sub gap-top" title="${esc(help("mistake card"))}">Added to your mistakes — it comes back tomorrow as a card.</p>`;
  return h;
}

/* ---- handlers ---- */
function qPick(i) {
  const st = qState(),
    it = qItem().it;
  if (st.answered) return;
  st.resp = it.type === "tf" ? i === 0 : i;
  st.committed = true;
  save();
  drawQuiz();
}
function qToggle(i) {
  const st = qState();
  if (st.committed) return;
  const picks = Array.isArray(st.resp) ? st.resp.slice() : [];
  const at = picks.indexOf(i);
  if (at >= 0) picks.splice(at, 1);
  else picks.push(i);
  st.resp = picks;
  save();
  drawQuiz();
}
function qSet(v) {
  const st = qState();
  if (!st.committed) st.resp = v;
}
function qMove(pos, dir) {
  const st = qState(),
    it = qItem().it;
  const order = Array.isArray(st.resp) ? st.resp.slice() : perm(it.options.length, qSeed());
  const j = pos + dir;
  if (j < 0 || j >= order.length) return;
  [order[pos], order[j]] = [order[j], order[pos]];
  st.resp = order;
  save();
  drawQuiz();
}
function qMatch(li, v) {
  const st = qState();
  const r = Object.assign({}, st.resp || {});
  if (v === "") delete r[li];
  else r[li] = +v;
  st.resp = r;
  save();
}
function qHint() {
  const st = qState();
  st.hinted = (st.hinted || 0) + 1;
  save();
  drawQuiz();
}
function qCommit() {
  const st = qState(),
    it = qItem().it,
    t = it.type || "single";
  if (st.committed || st.answered) return;
  if (t === "order" && !Array.isArray(st.resp)) st.resp = perm(it.options.length, qSeed());
  const empty =
    st.resp == null ||
    (typeof st.resp === "string" && !st.resp.trim()) ||
    (Array.isArray(st.resp) && !st.resp.length && t === "multi") ||
    (t === "match" && Object.keys(st.resp || {}).length < it.pairs.length);
  if (empty) {
    toast(t === "match" ? "Match every item first" : "Give an answer first — a guess is fine");
    return;
  }
  st.committed = true;
  save();
  drawQuiz();
}
function qUncommit() {
  const st = qState();
  if (st.answered) return;
  st.committed = false;
  save();
  drawQuiz();
}
function qAnswer(conf) {
  const st = qState(),
    { it, mid, qi } = qItem(),
    t = it.type || "single";
  if (!st.committed || st.answered) return;
  st.conf = conf;
  st.answered = true;
  st.at = Date.now();
  if (t === "short") {
    st.ok = null;
    save();
    markDay();
    drawQuiz();
    if (connMode() !== "none") gradeShortNow();
    return;
  }
  st.ok = itemOk(it, st.resp);
  settle(mid, qi, it, st);
  save();
  markDay();
  drawQuiz();
}
/* what a graded answer means for the rest of the page: mistakes, mastery, checkpoints */
function settle(mid, qi, it, st) {
  if (!st.ok || st.hinted) addMistake(mid, qi, it, st.resp);
  if (QUIZ.kind === "cp") recordCheck(mid, st.ok && !st.hinted);
}
function qSelf(v) {
  const st = qState(),
    { it, mid, qi } = qItem();
  if (!st.answered || st.ok != null) return;
  st.self = v;
  st.ok = v === 3;
  settle(mid, qi, it, st);
  save();
  drawQuiz();
}
async function gradeShortNow() {
  const st = qState(),
    { it, mid, qi } = qItem();
  if (!st.answered || st.ok != null || shortGrading) return;
  shortGrading = true;
  drawQuiz();
  try {
    const res = await gradeShort(it, st.resp || "");
    st.ai = res;
    st.ok = res.verdict === "correct";
    settle(mid, qi, it, st);
    save();
  } catch (e) {
    toast((e && e.message) || "The tutor did not answer — score it yourself");
  }
  shortGrading = false;
  drawQuiz();
}
function qNext() {
  const qs = QUIZ.qs;
  if (qs.i === QUIZ.items.length - 1) {
    qs.finished = true;
    save();
    drawQuiz();
  } else {
    qs.i++;
    save();
    drawQuiz();
  }
}

/* ---- module results ---- */
function quizResults(m) {
  const q = progressOf(m.id).quiz,
    items = m.assess.quiz;
  const ok = q.a.filter(x => x && x.ok).length,
    tot = items.length;
  const pct = Math.round((ok / tot) * 100);
  const overconf = q.a.filter(x => x && x.conf === 3 && !x.ok).length;
  const queued = q.a.filter(x => x && (!x.ok || x.hinted)).length;
  const verdict =
    pct >= 85
      ? "Strong. The material is in there. The flashcards will keep it there."
      : pct >= 60
        ? "Reasonable first pass. Re-read the sections behind the ones you missed, then retake in a few days — the retake is where the learning happens."
        : "This is a normal first score and it is useful data. Go back to Read, work through the sections behind the misses, and retake. Nobody learns this in one pass.";
  const queuedLine = queued
    ? ` · <span title="${esc(help("mistake card"))}">${queued} added to your mistakes</span>`
    : "";
  let h = scoreBlock({
    eyebrow: "Step 3 · Retrieve",
    pct,
    line: `${ok} of ${tot} correct${queuedLine}`,
    verdict,
    overconf,
    actions: `<button class="btn" onclick="askRetake('${m.id}')">Retake</button>
      <button class="btn" onclick="go(stepHash('${m.id}',1))">Back to reading</button>
      ${queued ? `<button class="btn" onclick="go('#/review/mistakes')">Fix mistakes now</button>` : ""}
      <button class="btn primary" onclick="go(stepHash('${m.id}',3))">Continue to Elaborate</button>`,
  });
  h += `<div class="card gap-top"><h3 class="eyebrow">Every question, with the reasoning</h3>`;
  items.forEach((it, i) => {
    const st = q.a[i] || {};
    h += `<div class="qreview ${i ? "" : "first"}">
      <div class="rowline top">
        <span class="tag ${st.ok ? "ok" : "bad"}">${st.ok ? "✓" : "✗"}</span>
        <div><b class="qtext">${esc(it.q)}</b> <span class="tag">${TYPE_LABEL[it.type || "single"]}</span>
        <div class="qgiven">Correct: ${esc(correctText(it))}${!st.ok && st.resp != null ? " · yours: " + esc(respText(it, st.resp)) : ""}${st.hinted ? " · used " + st.hinted + " hint" + (st.hinted > 1 ? "s" : "") : ""}</div>
        <div class="qwhy">${esc(it.why)}</div></div></div></div>`;
  });
  h += `</div>`;
  $("#stepbody").innerHTML = h;
  maybeRefreshLearner();
}
function respText(it, resp) {
  const t = it.type || "single";
  if (t === "single") return it.options[resp] == null ? "—" : it.options[resp];
  if (t === "tf") return resp ? "True" : "False";
  if (t === "multi") return (resp || []).map(i => it.options[i]).join(" · ") || "nothing";
  if (t === "order") return (resp || []).map(i => it.options[i]).join(" → ");
  if (t === "match")
    return it.pairs
      .map((p, i) => p[0] + " → " + (resp[i] != null ? it.pairs[resp[i]][1] : "?"))
      .join("  ·  ");
  if (t === "short") return String(resp || "").slice(0, 160);
  return String(resp);
}
/* A retake wipes the answers and the confidence ratings that went with them, which is
   the only record of what was misjudged. It asks. */
function askRetake(id) {
  confirmModal(
    "Retake this quiz?",
    "Your current answers and confidence ratings for this module are replaced. Cards already in your mistake queue stay.",
    "Retake it",
    () => retake(id)
  );
}
function retake(id) {
  progressOf(id).quiz = { i: 0, a: [], finished: false, seed: Math.floor(Math.random() * 1e6) };
  save();
  renderQuiz(byId(id));
}
