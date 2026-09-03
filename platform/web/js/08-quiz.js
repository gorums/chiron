/* ---------- quiz engine ----------
   One renderer for every place questions appear: a module's Retrieve step and the mixed
   checkpoints. `QZ` names the quiz being drawn; the handlers read it rather than taking a
   module id, so the keyboard layer and the checkpoint page share the same code path.

   QZ = { kind: "m" | "cp", host: css selector, items: [{ mid, qi, it }], qs, onDone }
   qs = { i, a: [], finished, seed }      a[i] = { resp, committed, answered, ok, conf, hinted, self, ai }
*/
let QZ = null, shortGrading = false;

function renderQuiz(m) {
  const p = P(m.id);
  if (!p.quiz) p.quiz = { i: 0, a: [], finished: false, seed: Math.floor(Math.random() * 1e6) };
  if (!p.quiz.seed) p.quiz.seed = 7;
  QZ = { kind: "m", host: "#stepbody", mid: m.id, qs: p.quiz,
         items: m.assess.quiz.map((it, qi) => ({ mid: m.id, qi, it })),
         onDone: () => { renderSidebar(); quizResults(m); } };
  drawQuiz();
}
function qState() { const qs = QZ.qs; if (!qs.a[qs.i]) qs.a[qs.i] = { resp: null, committed: false, answered: false, hinted: 0 }; return qs.a[qs.i]; }
function qItem() { return QZ.items[QZ.qs.i]; }
function qSeed() { return (QZ.qs.seed || 7) + QZ.qs.i * 31; }

function drawQuiz() {
  const host = $(QZ.host); if (!host) return;
  const qs = QZ.qs;
  if (qs.finished) return QZ.onDone();
  const { it, mid } = qItem(), st = qState(), t = it.type || "single";
  const n = QZ.items.length;
  let h = `<div class="card">
    <div class="qmeta"><span>Question ${qs.i + 1} of ${n}</span>
      <span class="bar"><i style="width:${Math.round(qs.i / n * 100)}%"></i></span>
      ${QZ.kind === "cp" ? `<span class="tag acc">${mid}</span>` : ""}
      <span class="tag">${TYPE_LABEL[t] || ""}</span>
      <span style="margin-left:auto">${qs.a.filter(x => x && x.ok).length} correct so far</span></div>
    <h3 style="font-family:var(--serif);font-size:21px;line-height:1.35;font-weight:600;margin:0 0 16px">${t === "cloze" ? clozeHtml(it, st) : esc(it.q)}</h3>`;
  h += answerArea(it, st);
  if (!st.answered) {
    const hints = it.hints || [];
    if (st.hinted) h += hints.slice(0, st.hinted).map((x, i) => `<div class="hintbox"><b>Hint ${i + 1}</b>${esc(x)}</div>`).join("");
    if (!st.committed) {
      h += `<div style="display:flex;gap:9px;margin-top:14px;flex-wrap:wrap;align-items:center">
        ${t !== "single" && t !== "tf" ? `<button class="btn primary" onclick="qCommit()">Lock in answer</button>` : ""}
        ${hints.length && st.hinted < hints.length ? `<button class="btn sm ghost" onclick="qHint()">Hint ${st.hinted + 1} of ${hints.length}</button>` : ""}
        ${st.hinted ? `<span class="sub" style="font-size:12px">A question answered after a hint goes into your mistake queue either way.</span>` : ""}
      </div>`;
    } else {
      h += `<div class="conf"><span style="font-size:13px;color:var(--muted)">How sure are you?</span>
        ${[["Guessing", 1], ["Fairly sure", 2], ["Certain", 3]].map(([l, v], i) =>
          `<button class="btn sm" onclick="qAnswer(${v})"><kbd>${i + 1}</kbd> ${l}</button>`).join("")}
        ${t !== "single" && t !== "tf" ? `<button class="btn sm ghost" onclick="qUncommit()">Change answer</button>` : ""}</div>
        <p class="sub" style="margin-top:10px;font-size:12px">Rating your confidence trains calibration — knowing what you actually know is most of what separates a good ${esc(CFG.practitioner)} from a confident one.</p>`;
    }
  } else {
    h += verdictHtml(it, st);
    if (st.ok != null) h += `<div style="display:flex;gap:9px;margin-top:16px"><button class="btn primary" onclick="qNext()">${qs.i === n - 1 ? "See results →" : "Next question →"} <kbd>↵</kbd></button></div>`;
  }
  h += `</div>`;
  host.innerHTML = h;
  const first = host.querySelector("input[type=text],input[type=number]");
  if (first && !st.answered) first.focus();
}

/* ---- the answer area, one shape per type ---- */
function answerArea(it, st) {
  const t = it.type || "single", locked = st.committed || st.answered;
  if (t === "single" || t === "tf") {
    const opts = t === "tf" ? ["True", "False"] : it.options;
    const ans = t === "tf" ? (it.answer ? 0 : 1) : it.answer;
    const pick = t === "tf" ? (st.resp === true ? 0 : st.resp === false ? 1 : null) : st.resp;
    return opts.map((o, i) => {
      let cls = "";
      if (st.answered) { if (i === ans) cls = "right"; else if (i === pick) cls = "wrong"; }
      else if (pick === i) cls = "sel";
      return `<button class="opt ${cls}" ${st.answered ? "disabled" : ""} onclick="qPick(${i})"><span class="k">${"ABCDEFGH"[i]}</span><span>${esc(o)}</span></button>`;
    }).join("");
  }
  if (t === "multi") {
    const picks = Array.isArray(st.resp) ? st.resp : [];
    return it.options.map((o, i) => {
      let cls = picks.includes(i) ? "sel" : "";
      if (st.answered) { const should = it.answer.includes(i); cls = should && picks.includes(i) ? "right" : (!should && picks.includes(i)) ? "wrong" : should ? "missed" : ""; }
      return `<button class="opt ${cls}" ${locked ? "disabled" : ""} onclick="qToggle(${i})"><span class="k">${picks.includes(i) ? "✓" : "ABCDEFGH"[i]}</span><span>${esc(o)}</span></button>`;
    }).join("") + (locked ? "" : `<p class="sub" style="font-size:12px;margin-top:4px">Select every option that applies, then lock in.</p>`);
  }
  if (t === "numeric") {
    return `<div class="numrow"><input type="text" inputmode="decimal" id="qin" value="${esc(st.resp == null ? "" : st.resp)}" placeholder="Your figure" ${locked ? "disabled" : ""} oninput="qSet(this.value)" onkeydown="if(event.key==='Enter'){event.preventDefault();qCommit()}">${it.unit ? `<span class="unit">${esc(it.unit)}</span>` : ""}</div>`;
  }
  if (t === "cloze") return `<p class="sub" style="font-size:12.5px">Type the missing word or phrase into the blank above${locked ? "" : ", then lock in"}.</p>`;
  if (t === "short") {
    return `<textarea id="qin" rows="4" placeholder="One or two sentences. Say the thing, do not describe it." ${locked ? "disabled" : ""} oninput="qSet(this.value)">${esc(st.resp || "")}</textarea>`;
  }
  if (t === "order") {
    const order = Array.isArray(st.resp) ? st.resp : perm(it.options.length, qSeed());
    return `<div class="orderlist">${order.map((oi, pos) => `<div class="orow ${st.answered ? (oi === pos ? "right" : "wrong") : ""}">
      <span class="k">${pos + 1}</span><span style="flex:1">${esc(it.options[oi])}</span>
      ${locked ? "" : `<button class="iconbtn" ${pos === 0 ? "disabled" : ""} onclick="qMove(${pos},-1)" title="Move up">↑</button><button class="iconbtn" ${pos === order.length - 1 ? "disabled" : ""} onclick="qMove(${pos},1)" title="Move down">↓</button>`}
    </div>`).join("")}</div>${locked ? "" : `<p class="sub" style="font-size:12px;margin-top:4px">Arrange from first to last, then lock in.</p>`}`;
  }
  if (t === "match") {
    const rights = perm(it.pairs.length, qSeed());
    const resp = st.resp || {};
    return `<div class="matchlist">${it.pairs.map((p, li) => `<div class="mrow2 ${st.answered ? (resp[li] === li ? "right" : "wrong") : ""}">
      <span class="left">${esc(p[0])}</span><span class="arrow">→</span>
      <select ${locked ? "disabled" : ""} onchange="qMatch(${li},this.value)">
        <option value="">…</option>
        ${rights.map(ri => `<option value="${ri}" ${resp[li] === ri ? "selected" : ""}>${esc(it.pairs[ri][1])}</option>`).join("")}
      </select></div>`).join("")}</div>`;
  }
  return "";
}
function clozeHtml(it, st) {
  const parts = it.q.split("___");
  const locked = st.committed || st.answered;
  const cls = st.answered ? (st.ok ? "right" : "wrong") : "";
  return esc(parts[0]) + `<input type="text" class="clozein ${cls}" id="qin" value="${esc(st.resp || "")}" ${locked ? "disabled" : ""} oninput="qSet(this.value)" onkeydown="if(event.key==='Enter'){event.preventDefault();qCommit()}" size="${Math.max(6, String(correctText(it)).length)}">` + esc(parts.slice(1).join("___"));
}

/* ---- after the answer ---- */
function verdictHtml(it, st) {
  const t = it.type || "single";
  let h = "";
  if (t === "short") {
    h += `<div class="why" style="margin-top:14px"><b style="color:var(--text);display:block;margin-bottom:6px">Model answer</b>${esc(it.model)}</div>`;
    if (st.ai) h += `<div class="fb ${st.ai.verdict}"><b>${st.ai.verdict === "correct" ? "Claude: that covers it" : st.ai.verdict === "partial" ? "Claude: partly there" : "Claude: not yet"}</b>${mdLite(st.ai.text)}</div>`;
    else if (shortGrading) h += `<div class="msg a typing" style="margin-top:12px"><i></i><i></i><i></i></div>`;
    if (st.ok == null && !shortGrading) {
      h += `<div class="conf"><span style="font-size:13px;color:var(--muted)">${connMode() === "none" ? "How did yours compare?" : "Or score it yourself:"}</span>
        ${[["Missed it", 1], ["Partly there", 2], ["Got it", 3]].map(([l, v]) => `<button class="btn sm" onclick="qSelf(${v})">${l}</button>`).join("")}
        ${connMode() !== "none" ? `<button class="btn sm primary" onclick="gradeShortNow()">Ask Claude to check</button>` : ""}</div>`;
    } else if (st.self) h += `<p class="sub" style="margin-top:10px">Self-scored: ${["", "missed it", "partly there", "got it"][st.self]}.</p>`;
    if (st.ok != null) h += `<div class="why"><b style="color:var(--text);display:block;margin-bottom:6px">Why</b>${esc(it.why)}</div>`;
    return h;
  }
  const head = st.ok ? "Correct" + (st.hinted ? " — with a hint" : "") : "Not quite — the answer is " + esc(correctText(it));
  h += `<div class="why"><b style="color:${st.ok ? "var(--ok)" : "var(--bad)"};display:block;margin-bottom:6px">${head}</b>${esc(it.why)}</div>`;
  if (it.feedback && (t === "single" || t === "tf")) {
    const pick = t === "tf" ? (st.resp === true ? 0 : 1) : st.resp, ans = t === "tf" ? (it.answer ? 0 : 1) : it.answer;
    if (!st.ok && it.feedback[pick]) h += `<div class="fbline wrong"><b>Your pick</b>${esc(it.feedback[pick])}</div>`;
    if (it.feedback[ans]) h += `<div class="fbline right"><b>The answer</b>${esc(it.feedback[ans])}</div>`;
  }
  if (it.feedback && t === "multi") {
    const picks = st.resp || [];
    h += it.options.map((o, i) => { const should = it.answer.includes(i), did = picks.includes(i); if (should === did && !should) return ""; return `<div class="fbline ${should ? "right" : "wrong"}"><b>${should ? (did ? "✓" : "missed") : "✗"} ${esc(o)}</b>${esc(it.feedback[i] || "")}</div>`; }).join("");
  }
  if (!st.ok || st.hinted) h += `<p class="sub" style="margin-top:10px;font-size:12px">Added to your mistake queue — it comes back tomorrow as a card.</p>`;
  return h;
}

/* ---- handlers ---- */
function qPick(i) {
  const st = qState(), it = qItem().it;
  if (st.answered) return;
  st.resp = (it.type === "tf") ? (i === 0) : i; st.committed = true; save(); drawQuiz();
}
function qToggle(i) {
  const st = qState(); if (st.committed) return;
  const picks = Array.isArray(st.resp) ? st.resp.slice() : [];
  const at = picks.indexOf(i); if (at >= 0) picks.splice(at, 1); else picks.push(i);
  st.resp = picks; save(); drawQuiz();
}
function qSet(v) { const st = qState(); if (!st.committed) st.resp = v; }
function qMove(pos, dir) {
  const st = qState(), it = qItem().it;
  const order = Array.isArray(st.resp) ? st.resp.slice() : perm(it.options.length, qSeed());
  const j = pos + dir; if (j < 0 || j >= order.length) return;
  [order[pos], order[j]] = [order[j], order[pos]]; st.resp = order; save(); drawQuiz();
}
function qMatch(li, v) { const st = qState(); const r = Object.assign({}, st.resp || {}); if (v === "") delete r[li]; else r[li] = +v; st.resp = r; save(); }
function qHint() { const st = qState(); st.hinted = (st.hinted || 0) + 1; save(); drawQuiz(); }
function qCommit() {
  const st = qState(), it = qItem().it, t = it.type || "single";
  if (st.committed || st.answered) return;
  if (t === "order" && !Array.isArray(st.resp)) st.resp = perm(it.options.length, qSeed());
  const empty = st.resp == null || (typeof st.resp === "string" && !st.resp.trim()) || (Array.isArray(st.resp) && !st.resp.length && t === "multi")
    || (t === "match" && Object.keys(st.resp || {}).length < it.pairs.length);
  if (empty) { toast(t === "match" ? "Match every item first" : "Give an answer first — a guess is fine"); return; }
  st.committed = true; save(); drawQuiz();
}
function qUncommit() { const st = qState(); if (st.answered) return; st.committed = false; save(); drawQuiz(); }
function qAnswer(conf) {
  const st = qState(), { it, mid, qi } = qItem(), t = it.type || "single";
  if (!st.committed || st.answered) return;
  st.conf = conf; st.answered = true;
  if (t === "short") { st.ok = null; save(); markDay(); drawQuiz(); if (connMode() !== "none") gradeShortNow(); return; }
  st.ok = itemOk(it, st.resp);
  settle(mid, qi, it, st);
  save(); markDay(); drawQuiz();
}
/* what a graded answer means for the rest of the page: mistakes, mastery, checkpoints */
function settle(mid, qi, it, st) {
  if (!st.ok || st.hinted) addMistake(mid, qi, it, st.resp);
  if (QZ.kind === "cp") recordCheck(mid, st.ok && !st.hinted);
}
function qSelf(v) {
  const st = qState(), { it, mid, qi } = qItem();
  if (!st.answered || st.ok != null) return;
  st.self = v; st.ok = v === 3; settle(mid, qi, it, st); save(); drawQuiz();
}
async function gradeShortNow() {
  const st = qState(), { it, mid, qi } = qItem();
  if (!st.answered || st.ok != null || shortGrading) return;
  shortGrading = true; drawQuiz();
  try {
    const res = await gradeShort(it, st.resp || "");
    st.ai = res; st.ok = res.verdict === "correct"; settle(mid, qi, it, st); save();
  } catch (e) { toast((e && e.message) || "Could not reach Claude — score it yourself"); }
  shortGrading = false; drawQuiz();
}
function qNext() {
  const qs = QZ.qs;
  if (qs.i === QZ.items.length - 1) { qs.finished = true; save(); drawQuiz(); }
  else { qs.i++; save(); drawQuiz(); }
}

/* ---- module results ---- */
function quizResults(m) {
  const q = P(m.id).quiz, items = m.assess.quiz;
  const ok = q.a.filter(x => x && x.ok).length, tot = items.length;
  const pct = Math.round(ok / tot * 100);
  const overconf = q.a.filter(x => x && x.conf === 3 && !x.ok).length;
  const queued = q.a.filter(x => x && (!x.ok || x.hinted)).length;
  let h = `<div class="card" style="text-align:center">
    <p class="eyebrow">Step 3 · Retrieve</p>
    <div style="font-family:var(--serif);font-size:52px;font-weight:600;line-height:1;margin:8px 0 4px;color:${pct >= 80 ? "var(--ok)" : pct >= 60 ? "var(--warm)" : "var(--bad)"}">${pct}%</div>
    <p class="sub" style="margin-bottom:16px">${ok} of ${tot} correct${queued ? ` · ${queued} in your mistake queue` : ""}</p>
    <p style="max-width:520px;margin:0 auto 18px;color:var(--text-2)">${pct >= 85 ? "Strong. The material is in there. The flashcards will keep it there." : pct >= 60 ? "Reasonable first pass. Re-read the sections behind the ones you missed, then retake in a few days — the retake is where the learning happens." : "This is a normal first score and it is useful data. Go back to Read, work through the sections behind the misses, and retake. Nobody learns this in one pass."}</p>`;
  if (overconf) h += `<div class="hint" style="max-width:520px;margin:0 auto 18px;text-align:left"><span class="i">Calibration</span> You were "certain" and wrong ${overconf} time${overconf > 1 ? "s" : ""}. That is the most valuable signal on this page — those are the beliefs that will cost you money.</div>`;
  h += `<div style="display:flex;gap:9px;justify-content:center;flex-wrap:wrap">
    <button class="btn" onclick="retake('${m.id}')">Retake</button>
    <button class="btn" onclick="go('#/m/${m.id}/1')">Back to reading</button>
    ${queued ? `<button class="btn" onclick="go('#/review/mistakes')">Fix mistakes now</button>` : ""}
    <button class="btn primary" onclick="go('#/m/${m.id}/3')">Continue →</button></div></div>`;
  h += `<div class="card" style="margin-top:16px"><p class="eyebrow">Every question, with the reasoning</p>`;
  items.forEach((it, i) => {
    const st = q.a[i] || {};
    h += `<div style="padding:14px 0;border-top:${i ? "1px solid var(--line)" : "0"}">
      <div style="display:flex;gap:9px;align-items:flex-start">
        <span class="tag ${st.ok ? "ok" : ""}" style="${st.ok ? "" : "background:var(--bad-soft);color:var(--bad)"}">${st.ok ? "✓" : "✗"}</span>
        <div><b style="font-size:15px">${esc(it.q)}</b> <span class="tag">${TYPE_LABEL[it.type || "single"]}</span>
        <div style="font-size:14px;color:var(--muted);margin-top:5px">Correct: ${esc(correctText(it))}${!st.ok && st.resp != null ? " · yours: " + esc(respText(it, st.resp)) : ""}${st.hinted ? " · used " + st.hinted + " hint" + (st.hinted > 1 ? "s" : "") : ""}</div>
        <div style="font-size:14px;color:var(--text-2);margin-top:7px">${esc(it.why)}</div></div></div></div>`;
  });
  h += `</div>`;
  $("#stepbody").innerHTML = h;
}
function respText(it, resp) {
  const t = it.type || "single";
  if (t === "single") return it.options[resp] == null ? "—" : it.options[resp];
  if (t === "tf") return resp ? "True" : "False";
  if (t === "multi") return (resp || []).map(i => it.options[i]).join(" · ") || "nothing";
  if (t === "order") return (resp || []).map(i => it.options[i]).join(" → ");
  if (t === "match") return it.pairs.map((p, i) => p[0] + " → " + (resp[i] != null ? it.pairs[resp[i]][1] : "?")).join("  ·  ");
  if (t === "short") return String(resp || "").slice(0, 160);
  return String(resp);
}
function retake(id) { P(id).quiz = { i: 0, a: [], finished: false, seed: Math.floor(Math.random() * 1e6) }; save(); renderQuiz(byId(id)); }
