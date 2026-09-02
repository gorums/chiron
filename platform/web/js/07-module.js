/* ---------- module ---------- */
const STEPS = [
  { k: "predict", n: "Predict", d: "Guess before you read" },
  { k: "read", n: "Read", d: "Work through the module" },
  { k: "quiz", n: "Retrieve", d: "Test yourself" },
  { k: "elab", n: "Elaborate", d: "Put it in your own words" },
  { k: "apply", n: "Apply", d: "Transfer to a real case" }
];
let timer = null, tickCount = 0;
function startTimer(mid) {
  stopTimer();
  timer = setInterval(() => {
    if (document.hidden) return;
    P(mid).time = (P(mid).time || 0) + 1;
    tickCount++;
    if (tickCount % 20 === 0) save();
    const el = $("#clock"); if (el) el.textContent = fmtClock(P(mid).time);
  }, 1000);
}
function stopTimer() { if (timer) { clearInterval(timer); timer = null; save(); } }

function viewModule() {
  const m = byId(route.id);
  if (!m) return go("#/home");
  const p = P(m.id), step = Math.max(0, Math.min(4, route.step || 0));
  markDay(); startTimer(m.id);
  const idx = mIndex(m.id);
  const prev = MODS[idx - 1], next = MODS[idx + 1];
  if (curSec >= m.sections.length) curSec = 0;

  let h = `<div class="wrap"><div class="readhead">
    <div class="crumb">${esc(partName(m.part))} · Module ${m.num} of ${MODS.length} · <span id="clock">${fmtClock(p.time || 0)}</span> spent of ${m.minutes}m planned</div>
    <h2>${esc(m.title)}</h2>
    <p class="sub">${esc(m.meta)}</p>
    <div class="steps">`;
  STEPS.forEach((s, i) => {
    const did = stepDone(m, i);
    h += `<button class="step ${i === step ? "on" : ""} ${did ? "did" : ""}" onclick="go('#/m/${m.id}/${i}')"><span class="num">${did && i !== step ? "✓" : i + 1}</span>${s.n}</button>`;
  });
  h += `</div></div><div id="stepbody"></div>`;

  h += `<div class="footnav">
    ${prev ? `<button class="btn" onclick="go('#/m/${prev.id}')">← ${prev.id}</button>` : `<button class="btn" onclick="go('#/home')">← Dashboard</button>`}
    <button class="btn ${isDone(m) ? "" : "primary"}" onclick="toggleDone('${m.id}')">${isDone(m) ? "✓ Completed — undo" : "Mark module complete"}</button>
    ${next ? `<button class="btn" onclick="go('#/m/${next.id}')">${next.id} →</button>` : `<button class="btn" onclick="go('#/stats')">Stats →</button>`}
  </div>`;
  // Served by Studio: the course can grow from right here. A missing topic becomes a new
  // module; a section that stops short becomes a rewrite with direction.
  if (STUDIO) h += `<p class="sub" style="text-align:center;margin-top:16px;font-size:13px">Something missing here?
    <a href="#" onclick="return studioGo('add','${m.id}')">Ask Studio to add a module</a> ·
    <a href="#" onclick="return studioGo('rewrite','${m.id}')">have this one rewritten</a></p>`;
  h += `</div>`;
  $("#view").innerHTML = h;
  renderStep(m, step);
}
/* The link carries the section being read, so the brief in Studio can name it. Built at
   click time because curSec follows the scroll position. */
function studioGo(kind, mid) {
  const m = byId(mid), sec = m && m.sections[curSec] ? m.sections[curSec].h : "";
  const base = `${STUDIO.origin}/#/course/${STUDIO.id}`;
  location.href = kind === "add"
    ? `${base}?tab=add&from=${mid}${sec ? "&sec=" + encodeURIComponent(sec) : ""}`
    : `${base}?tab=modules&rewrite=${mid}${sec ? "&q=" + encodeURIComponent('The section "' + sec + '" stops short. ') : ""}`;
  return false;
}
function stepDone(m, i) {
  const p = P(m.id);
  if (i === 0) return !!p.predict.trim();
  if (i === 1) return secDone(m) === secTotal(m);
  if (i === 2) return !!(p.quiz && p.quiz.finished);
  if (i === 3) return Object.values(p.elab).some(v => (v || "").trim());
  return !!(p.transfer && p.transfer.score != null);
}
function toggleDone(id) {
  const p = P(id); p.done = !p.done; p.doneAt = p.done ? Date.now() : null;
  if (p.done) { const n = seedCards(id); markDay(); toast(n ? n + " flashcards added to your review deck" : "Module marked complete"); }
  save(); render();
}
function renderStep(m, step) {
  const p = P(m.id), b = $("#stepbody");
  if (step === 0) {
    b.innerHTML = `<div class="card">
      <p class="eyebrow">Step 1 · Predict</p>
      <p class="hint" style="margin-bottom:16px"><span class="i">Why</span> Guessing before you read makes the reading stick harder — even when the guess is wrong. This costs 60 seconds and measurably improves retention. Do not look ahead.</p>
      <h3 style="font-family:var(--serif);font-size:21px;font-weight:600;margin:0 0 12px">${esc(m.assess.predict)}</h3>
      <textarea id="predin" rows="3" placeholder="One sentence. A guess is fine — that is the point.">${esc(p.predict)}</textarea>
      <div style="display:flex;gap:9px;margin-top:12px">
        <button class="btn primary" onclick="savePredict('${m.id}')">Save and read →</button>
      </div>
    </div>`;
  } else if (step === 1) {
    let s = `<div style="display:grid;grid-template-columns:1fr 190px;gap:26px"><div>`;
    s += `<div class="card tight" style="margin-bottom:18px;display:flex;align-items:center;gap:14px">
      <div style="flex:1"><div style="font-size:12.5px;color:var(--muted);margin-bottom:5px">Reading progress · ${secDone(m)} of ${secTotal(m)} sections</div>
      <div class="bar"><i style="width:${Math.round(secDone(m) / secTotal(m) * 100)}%"></i></div></div>
      <button class="btn sm" onclick="allSecs('${m.id}',${secDone(m) === secTotal(m) ? "false" : "true"})">${secDone(m) === secTotal(m) ? "Uncheck all" : "Check all"}</button></div>
    <div class="hint" style="margin-bottom:18px"><span class="i">Tip</span> <b>Select any sentence</b> with your mouse and a bar appears — highlight it, attach a note, or turn it into a question for Claude. Or use the <b>?</b> beside any section heading. Everything you mark collects under <em>Marks &amp; questions</em>.</div>`;
    m.sections.forEach((sec, i) => {
      const on = !!p.secs[i];
      s += `<div class="sec ${on ? "done" : ""}" id="sec${i}">
        <div class="sechead">
          <button class="check ${on ? "on" : ""}" onclick="tickSec('${m.id}',${i})" title="Mark section read">
            <svg viewBox="0 0 12 12" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M1.5 6.2 4.4 9 10.5 2.8"/></svg></button>
          <h3>${esc(sec.h)}</h3>
          <button class="askbtn ${marksOf(m.id).some(k => k.sec === i) ? "has" : ""}" title="Ask Claude about this section" onclick="askSection('${m.id}',${i})">?</button>
        </div>
        <div class="prose">${sec.html}</div>
      </div>`;
    });
    s += `<div class="card" style="margin-top:22px;border-color:var(--accent)">
      <p class="eyebrow">Before you move on</p>
      <p style="margin:0 0 12px;color:var(--text-2)">Close this and write, from memory, the three things you want to keep from this module. Retrieval beats re-reading by roughly two to one per minute spent.</p>
      <textarea id="noteIn" rows="4" placeholder="From memory…">${esc(S.notes[m.id] || "")}</textarea>
      <div style="display:flex;gap:9px;margin-top:12px"><button class="btn primary" onclick="saveNote('${m.id}')">Save notes and test yourself →</button></div>
    </div>`;
    s += `</div><div><div class="toc" id="toc">${m.sections.map((sec, i) => `<a href="#sec${i}" onclick="jump(event,${i})">${esc(sec.h)}</a>`).join("")}</div></div></div>`;
    b.innerHTML = s;
    setupToc(); applyMarks(m.id); attachParaButtons(m.id);
  } else if (step === 2) {
    renderQuiz(m);
  } else if (step === 3) {
    let s = `<div class="card"><p class="eyebrow">Step 4 · Elaborate</p>
      <p class="hint" style="margin-bottom:18px"><span class="i">Why</span> Explaining an idea in your own words, connected to something you already know, is what converts a fact you recognise into a tool you can use. Write badly and quickly — nobody reads this but you.</p>`;
    m.assess.elaborate.forEach((q, i) => {
      s += `<div style="margin-bottom:18px"><h3 style="font-size:16px;font-weight:650;margin:0 0 9px">${esc(q)}</h3>
      <textarea data-el="${i}" rows="3" placeholder="${S.biz ? esc(S.biz) + "…" : "Your business…"}">${esc(p.elab[i] || "")}</textarea></div>`;
    });
    s += `<div style="display:flex;gap:9px"><button class="btn primary" onclick="saveElab('${m.id}')">Save and continue →</button></div></div>`;
    b.innerHTML = s;
  } else {
    const t = m.assess.transfer, st = p.transfer || {};
    let s = `<div class="card"><p class="eyebrow">Step 5 · Apply</p>
      <p class="hint" style="margin-bottom:16px"><span class="i">Why</span> The gap between knowing and doing closes only under transfer: a new situation you have not seen, with the framework not named for you. Write your answer before you open the model answer, or the exercise is worthless.</p>
      <div style="background:var(--surface-2);border-radius:11px;padding:16px;margin-bottom:16px;font-size:15.5px;line-height:1.65">${esc(t.scenario)}</div>
      <h3 style="font-family:var(--serif);font-size:20px;font-weight:600;margin:0 0 12px">${esc(t.prompt)}</h3>
      <textarea id="trin" rows="6" placeholder="Your answer. Reason it through — the reasoning is what is being trained.">${esc(st.answer || "")}</textarea>
      <div style="display:flex;gap:9px;margin-top:12px;flex-wrap:wrap">
        <button class="btn" onclick="saveTransfer('${m.id}',null)">Save draft</button>
        <button class="btn primary" onclick="revealModel('${m.id}')">Compare with model answer</button>
      </div>
      <div id="modelbox" class="${st.revealed ? "" : "hidden"}">
        <div class="why" style="margin-top:18px"><b style="color:var(--text);display:block;margin-bottom:6px">Model answer</b>${esc(t.model)}</div>
        <div class="conf"><span style="font-size:13px;color:var(--muted)">How did yours compare?</span>
          ${[["Missed it", 1], ["Partly there", 2], ["Got it", 3]].map(([l, v]) =>
            `<button class="btn sm ${st.score === v ? "primary" : ""}" onclick="saveTransfer('${m.id}',${v})">${l}</button>`).join("")}
        </div>
        ${st.score ? `<p class="sub" style="margin-top:14px">Scored. ${st.score === 3 ? `Now try to explain it to someone who is not a ${CFG.practitioner} — that is the real test.` : "Re-read the sections this draws on, then come back in a few days and retry from memory."}</p>` : ""}
      </div></div>`;
    if (!isDone(m)) s += `<div class="card" style="margin-top:16px;text-align:center"><p class="sub" style="margin-bottom:12px">Finished all five steps?</p><button class="btn primary" onclick="toggleDone('${m.id}')">Mark ${m.id} complete and unlock its flashcards</button></div>`;
    b.innerHTML = s;
  }
}
function jump(e, i) { e.preventDefault(); document.getElementById("sec" + i).scrollIntoView({ behavior: "smooth", block: "start" }); }
function setupToc() {
  const links = [...document.querySelectorAll("#toc a")];
  const secs = [...document.querySelectorAll(".sec")];
  if (!("IntersectionObserver" in window)) return;
  const io = new IntersectionObserver(ents => {
    ents.forEach(en => {
      if (en.isIntersecting) {
        const i = secs.indexOf(en.target);
        links.forEach((l, j) => l.classList.toggle("on", j === i));
        if (i >= 0) setCurSec(i);
      }
    });
  }, { rootMargin: "-80px 0px -70% 0px" });
  secs.forEach(s => io.observe(s));
}
function savePredict(id) { P(id).predict = $("#predin").value; save(); go("#/m/" + id + "/1"); }
function saveNote(id) { S.notes[id] = $("#noteIn").value; save(); toast("Notes saved"); go("#/m/" + id + "/2"); }
function saveElab(id) {
  const p = P(id);
  document.querySelectorAll("[data-el]").forEach(t => p.elab[t.dataset.el] = t.value);
  save(); toast("Saved"); go("#/m/" + id + "/4");
}
function saveTransfer(id, score) {
  const p = P(id); const ta = $("#trin");
  p.transfer = Object.assign({}, p.transfer, { answer: ta ? ta.value : (p.transfer || {}).answer || "" });
  if (score != null) p.transfer.score = score;
  save(); toast("Saved");
  if (score != null) renderStep(byId(id), 4);
}
function revealModel(id) {
  const p = P(id); const ta = $("#trin");
  if (ta && !ta.value.trim()) { toast("Write your own answer first — that is the whole exercise."); ta.focus(); return; }
  p.transfer = Object.assign({}, p.transfer, { answer: ta.value, revealed: true }); save();
  $("#modelbox").classList.remove("hidden");
  $("#modelbox").scrollIntoView({ behavior: "smooth", block: "center" });
}
function tickSec(id, i) {
  const p = P(id); p.secs[i] = !p.secs[i]; save(); markDay();
  renderStep(byId(id), 1); renderSidebar();
}
function allSecs(id, on) {
  const m = byId(id), p = P(id);
  m.sections.forEach((_, i) => p.secs[i] = on);
  save(); renderStep(m, 1); renderSidebar();
}
