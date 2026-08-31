/* ---------- quiz ---------- */
function renderQuiz(m) {
  const p = P(m.id);
  if (!p.quiz) p.quiz = { i: 0, a: [], finished: false };
  const q = p.quiz, b = $("#stepbody");
  if (q.finished) return quizResults(m);
  const item = m.assess.quiz[q.i];
  const state = q.a[q.i];
  let h = `<div class="card">
    <div class="qmeta"><span>Question ${q.i + 1} of ${m.assess.quiz.length}</span>
      <span class="bar"><i style="width:${Math.round(q.i / m.assess.quiz.length * 100)}%"></i></span>
      <span style="margin-left:auto">${q.a.filter(x => x && x.ok).length} correct so far</span></div>
    <h3 style="font-family:var(--serif);font-size:21px;line-height:1.35;font-weight:600;margin:0 0 16px">${esc(item.q)}</h3>`;
  item.options.forEach((o, i) => {
    let cls = "";
    if (state && state.answered) {
      if (i === item.answer) cls = "right";
      else if (i === state.pick) cls = "wrong";
    } else if (state && state.pick === i) cls = "sel";
    h += `<button class="opt ${cls}" ${state && state.answered ? "disabled" : ""} onclick="pick('${m.id}',${i})">
      <span class="k">${"ABCD"[i]}</span><span>${esc(o)}</span></button>`;
  });
  if (state && state.pick != null && !state.answered) {
    h += `<div class="conf"><span style="font-size:13px;color:var(--muted)">How sure are you?</span>
      ${[["Guessing", 1], ["Fairly sure", 2], ["Certain", 3]].map(([l, v], i) =>
        `<button class="btn sm" onclick="answer('${m.id}',${v})"><kbd>${i + 1}</kbd> ${l}</button>`).join("")}</div>
      <p class="sub" style="margin-top:10px;font-size:12px">Rating your confidence trains calibration — knowing what you actually know is most of what separates a good ${CFG.practitioner} from a confident one.</p>`;
  }
  if (state && state.answered) {
    h += `<div class="why"><b style="color:${state.ok ? "var(--ok)" : "var(--bad)"};display:block;margin-bottom:6px">${state.ok ? "Correct" : "Not quite — the answer is " + "ABCD"[item.answer]}</b>${esc(item.why)}</div>
    <div style="display:flex;gap:9px;margin-top:16px"><button class="btn primary" onclick="nextQ('${m.id}')">${q.i === m.assess.quiz.length - 1 ? "See results →" : "Next question →"} <kbd>↵</kbd></button></div>`;
  }
  h += `</div>`;
  b.innerHTML = h;
}
function pick(id, i) {
  const q = P(id).quiz;
  if (q.a[q.i] && q.a[q.i].answered) return;
  q.a[q.i] = { pick: i, answered: false }; save(); renderQuiz(byId(id));
}
function answer(id, conf) {
  const m = byId(id), q = P(id).quiz, st = q.a[q.i];
  if (!st || st.pick == null || st.answered) return;
  st.conf = conf; st.answered = true; st.ok = st.pick === m.assess.quiz[q.i].answer;
  save(); markDay(); renderQuiz(m);
}
function nextQ(id) {
  const m = byId(id), q = P(id).quiz;
  if (q.i === m.assess.quiz.length - 1) { q.finished = true; save(); renderSidebar(); quizResults(m); }
  else { q.i++; save(); renderQuiz(m); }
}
function quizResults(m) {
  const q = P(m.id).quiz, items = m.assess.quiz;
  const ok = q.a.filter(x => x && x.ok).length, tot = items.length;
  const pct = Math.round(ok / tot * 100);
  const overconf = q.a.filter((x, i) => x && x.conf === 3 && !x.ok).length;
  let h = `<div class="card" style="text-align:center">
    <p class="eyebrow">Step 3 · Retrieve</p>
    <div style="font-family:var(--serif);font-size:52px;font-weight:600;line-height:1;margin:8px 0 4px;color:${pct >= 80 ? "var(--ok)" : pct >= 60 ? "var(--warm)" : "var(--bad)"}">${pct}%</div>
    <p class="sub" style="margin-bottom:16px">${ok} of ${tot} correct</p>
    <p style="max-width:520px;margin:0 auto 18px;color:var(--text-2)">${pct >= 85 ? "Strong. The material is in there. The flashcards will keep it there." : pct >= 60 ? "Reasonable first pass. Re-read the sections behind the ones you missed, then retake in a few days — the retake is where the learning happens." : "This is a normal first score and it is useful data. Go back to Read, work through the sections behind the misses, and retake. Nobody learns this in one pass."}</p>`;
  if (overconf) h += `<div class="hint" style="max-width:520px;margin:0 auto 18px;text-align:left"><span class="i">Calibration</span> You were "certain" and wrong ${overconf} time${overconf > 1 ? "s" : ""}. That is the most valuable signal on this page — those are the beliefs that will cost you money.</div>`;
  h += `<div style="display:flex;gap:9px;justify-content:center;flex-wrap:wrap">
    <button class="btn" onclick="retake('${m.id}')">Retake</button>
    <button class="btn" onclick="go('#/m/${m.id}/1')">Back to reading</button>
    <button class="btn primary" onclick="go('#/m/${m.id}/3')">Continue →</button></div></div>`;
  h += `<div class="card" style="margin-top:16px"><p class="eyebrow">Every question, with the reasoning</p>`;
  items.forEach((it, i) => {
    const st = q.a[i] || {};
    h += `<div style="padding:14px 0;border-top:${i ? "1px solid var(--line)" : "0"}">
      <div style="display:flex;gap:9px;align-items:flex-start">
        <span class="tag ${st.ok ? "ok" : ""}" style="${st.ok ? "" : "background:var(--bad-soft);color:var(--bad)"}">${st.ok ? "✓" : "✗"}</span>
        <div><b style="font-size:15px">${esc(it.q)}</b>
        <div style="font-size:14px;color:var(--muted);margin-top:5px">Correct: ${esc(it.options[it.answer])}${st.pick != null && !st.ok ? " · you chose: " + esc(it.options[st.pick]) : ""}</div>
        <div style="font-size:14px;color:var(--text-2);margin-top:7px">${esc(it.why)}</div></div></div></div>`;
  });
  h += `</div>`;
  $("#stepbody").innerHTML = h;
}
function retake(id) { P(id).quiz = { i: 0, a: [], finished: false }; save(); renderQuiz(byId(id)); }
