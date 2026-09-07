/* ---------- module ---------- */
const STEPS = [
  { k: "predict", n: "Predict", d: "Guess before you read" },
  { k: "read", n: "Read", d: "Work through the module" },
  { k: "quiz", n: "Retrieve", d: "Test yourself" },
  { k: "elab", n: "Elaborate", d: "Put it in your own words" },
  { k: "apply", n: "Apply", d: "Transfer to a real case" },
  { k: "gaps", n: "Close gaps", d: "Drill what went wrong" },
];
let timer = null,
  tickCount = 0,
  lastActive = Date.now();
/* The clock only runs while the tab is visible and the reader has done something lately.
   A page left open over lunch should not log lunch. */
["pointerdown", "pointermove", "keydown", "scroll", "touchstart"].forEach(ev =>
  window.addEventListener(
    ev,
    () => {
      lastActive = Date.now();
    },
    { passive: true, capture: true }
  )
);
function isIdle() {
  return Date.now() - lastActive > (STUDY.idleSeconds || 180) * 1000;
}
function startTimer(mid) {
  stopTimer();
  timer = setInterval(() => {
    if (document.hidden || isIdle()) return;
    progressOf(mid).time = (progressOf(mid).time || 0) + 1;
    tickCount++;
    if (tickCount % 20 === 0) save();
    const el = $("#clock");
    if (el) el.textContent = fmtClock(progressOf(mid).time);
  }, 1000);
}
function stopTimer() {
  if (timer) {
    clearInterval(timer);
    timer = null;
    save();
  }
}

function viewModule() {
  const m = byId(route.id);
  if (!m) return go("#/home");
  const p = progressOf(m.id),
    step = Math.max(0, Math.min(STEPS.length - 1, route.step || 0));
  markDay();
  startTimer(m.id);
  const idx = moduleIndex(m.id);
  const prev = MODS[idx - 1],
    next = MODS[idx + 1];
  // where the reader left off; landOn() corrects it once the Read step is on screen
  rail.section = Math.max(0, Math.min(STATE.pos[m.id] || 0, m.sections.length - 1));
  const ms = mastery(m),
    pre = prereqs(m);

  let h = `<div class="wrap"><div class="readhead">
    <div class="crumb">${esc(partName(m.part))} · Module ${m.num} of ${MODS.length} · <span id="clock">${fmtClock(p.time || 0)}</span> spent of ${m.minutes}m planned · <span class="mlvl l${ms.lvl}" title="Mastery">${ms.name}${ms.dropped ? " (slipped)" : ""}</span></div>
    <h2>${esc(m.title)}</h2>
    <p class="sub">${esc(m.meta)}</p>
    ${pre.length ? `<div class="prereqs">Builds on ${pre.map(x => `<button class="chip ${x.ms.lvl < 2 ? "weak" : ""}" onclick="go('#/m/${x.m.id}')" title="${x.ms.name}">${x.m.id} · ${esc(x.m.short)}${x.ms.lvl < 2 ? " · " + x.ms.name.toLowerCase() : ""}</button>`).join("")}${weakPrereqs(m).length ? `<span class="sub" style="font-size:12px;color:var(--warm)">— a weak prerequisite is the usual reason a module feels harder than it is.</span>` : ""}</div>` : ""}
    <div class="steps">`;
  STEPS.forEach((s, i) => {
    const did = stepDone(m, i);
    h += `<button class="step ${i === step ? "on" : ""} ${did ? "did" : ""}" onclick="go('#/m/${m.id}/${i}')"><span class="num">${did && i !== step ? "✓" : i + 1}</span>${s.n}</button>`;
  });
  h += `</div></div><div id="stepbody"></div>`;

  h += `<div class="footnav">
    ${prev ? `<button class="btn" onclick="go('#/m/${prev.id}')">← ${prev.id}</button>` : `<button class="btn" onclick="go('#/home')">← Dashboard</button>`}
    <button class="btn ${isDone(m) ? "" : "primary"}" onclick="toggleDone('${m.id}')">${isDone(m) ? "✓ Completed — undo" : "Mark module complete"}</button>
    ${next ? `<button class="btn" onclick="go('#/m/${next.id}')">${next.id} →</button>` : `<button class="btn" onclick="go('#/record')">Course record</button>`}
  </div>`;
  // Served by Studio: the course can grow from right here. A missing topic becomes a new
  // module; a section that stops short becomes a rewrite with direction.
  if (STUDIO)
    h += `<p class="sub" style="text-align:center;margin-top:16px;font-size:13px">Something missing here?
    <a href="#" onclick="return studioGo('add','${m.id}')">Ask Studio to add a module</a> ·
    <a href="#" onclick="return studioGo('rewrite','${m.id}')">have this one rewritten</a></p>`;
  h += `</div>`;
  $("#view").innerHTML = h;
  renderStep(m, step);
}
/* The link carries the section being read, so the brief in Studio can name it. Built at
   click time because the place follows the scroll position. */
function studioGo(kind, mid) {
  const m = byId(mid),
    place = placeNow();
  const sec =
    m && place && place.step === "read" && m.sections[place.sec] ? m.sections[place.sec].h : "";
  const base = `${STUDIO.origin}/#/course/${STUDIO.id}`;
  location.href =
    kind === "add"
      ? `${base}?tab=add&from=${mid}${sec ? "&sec=" + encodeURIComponent(sec) : ""}`
      : `${base}?tab=modules&rewrite=${mid}${sec ? "&q=" + encodeURIComponent('The section "' + sec + '" stops short. ') : ""}`;
  return false;
}
function stepDone(m, i) {
  const p = progressOf(m.id);
  if (i === 0) return !!p.predict.trim();
  if (i === 1) return secDone(m) === secTotal(m);
  if (i === 2) return !!(p.quiz && p.quiz.finished);
  if (i === 3) return Object.values(p.elab).some(v => (v || "").trim());
  if (i === 4) return !!(p.transfer && (p.transfer.score != null || p.transfer.fb));
  return !!p.gapsAt && !openGapItems(m.id).length;
}
function toggleDone(id) {
  const p = progressOf(id);
  p.done = !p.done;
  p.doneAt = p.done ? Date.now() : null;
  if (p.done) {
    const n = seedCards(id);
    markDay();
    const froze = earnFreeze();
    toast(
      (n ? n + " flashcards added to your review deck" : "Module marked complete") +
        (froze ? " · +1 streak freeze" : "")
    );
  }
  save();
  render();
}
function renderStep(m, step) {
  const p = progressOf(m.id),
    b = $("#stepbody");
  if (step === 5) return renderGapStep(m);
  if (step === 0) {
    b.innerHTML = `<div class="card">
      <p class="eyebrow">Step 1 · Predict</p>
      <p class="hint" style="margin-bottom:16px"><span class="i">Why</span> Guessing before you read makes the reading stick harder — even when the guess is wrong. This costs 60 seconds and measurably improves retention. Do not look ahead.</p>
      <h3 style="font-family:var(--serif);font-size:21px;font-weight:600;margin:0 0 12px">${esc(m.assess.predict)}</h3>
      <textarea id="predin" rows="3" placeholder="One sentence. A guess is fine — that is the point.">${esc(p.predict)}</textarea>
      <div style="display:flex;gap:9px;margin-top:12px">
        <button class="btn primary" onclick="savePredict('${m.id}')">Save and read</button>
      </div>
    </div>`;
  } else if (step === 1) {
    let s = `<div class="readgrid"><div>`;
    s += `<div class="card tight" style="margin-bottom:18px;display:flex;align-items:center;gap:14px">
      <div style="flex:1"><div style="font-size:12.5px;color:var(--muted);margin-bottom:5px" id="readcount">${readCountText(m)}</div>
      <div class="bar"><i id="readbar" style="width:${readPercent(m)}%"></i></div></div>
      <button class="btn sm" onclick="allSecs('${m.id}',${secDone(m) === secTotal(m) ? "false" : "true"})">${secDone(m) === secTotal(m) ? "Uncheck all" : "Check all"}</button></div>
    <div class="audiobar" id="audiobar">${audioBarHtml(m)}</div>
    <div class="hint" style="margin-bottom:18px"><span class="i">Tip</span><span><b>Select any sentence</b> to highlight it, attach a note, or ask Claude about that exact passage. Everything you mark collects under <em>Marks &amp; questions</em>.</span></div>`;
    m.sections.forEach((sec, i) => {
      const on = !!p.secs[i],
        bk = !!STATE.bookmarks[m.id + ":" + i];
      s += `<div class="sec ${on ? "done" : ""}" id="sec${i}">
        <div class="sechead">
          <button class="check ${on ? "on" : ""}" onclick="tickSec('${m.id}',${i})" title="Mark section read">
            <svg viewBox="0 0 12 12" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M1.5 6.2 4.4 9 10.5 2.8"/></svg></button>
          <h3>${esc(sec.h)}</h3>
          <button class="askbtn ${bk ? "has on" : ""}" title="${bk ? "Remove bookmark" : "Bookmark this section"}" aria-label="Bookmark this section" onclick="toggleBookmark('${m.id}',${i})">${ico("flag", 13)}</button>
          <button class="askbtn ${marksOf(m.id).some(k => k.sec === i) ? "has" : ""}" title="Ask Claude about this section" aria-label="Ask Claude about this section" onclick="askSection('${m.id}',${i})">${ico("ask", 14)}</button>
          ${sectionSpeakButton(m.id, i)}
        </div>
        <div class="prose">${sec.html}</div>
      </div>`;
    });
    s += `<div class="card" style="margin-top:22px;border-color:var(--accent)">
      <p class="eyebrow">Before you move on</p>
      <p style="margin:0 0 12px;color:var(--text-2)">Close this and write, from memory, the three things you want to keep from this module. Retrieval beats re-reading by roughly two to one per minute spent.</p>
      <textarea id="noteIn" rows="4" placeholder="From memory…">${esc(STATE.notes[m.id] || "")}</textarea>
      <div style="display:flex;gap:9px;margin-top:12px"><button class="btn primary" onclick="saveNote('${m.id}')">Save notes and test yourself</button></div>
    </div>`;
    s += `</div><div><div class="toc" id="toc">${m.sections.map((sec, i) => `<a href="#sec${i}" onclick="jump(event,${i})">${esc(sec.h)}</a>`).join("")}</div></div></div>`;
    b.innerHTML = s;
    setupToc();
    setupFigures();
    setupNotebooks();
    applyMarks(m.id);
    attachParaButtons(m.id);
    landOn(m);
  } else if (step === 2) {
    renderQuiz(m);
  } else if (step === 3) {
    let s = `<div class="card"><p class="eyebrow">Step 4 · Elaborate</p>
      <p class="hint" style="margin-bottom:18px"><span class="i">Why</span> Explaining an idea in your own words, connected to something you already know, is what converts a fact you recognise into a tool you can use. Write badly and quickly — then let Claude tell you what you left out.</p>`;
    m.assess.elaborate.forEach((q, i) => {
      const fb = p.elabFb[i];
      s += `<div style="margin-bottom:22px"><h3 style="font-size:16px;font-weight:650;margin:0 0 9px">${esc(q)}</h3>
      <textarea data-el="${i}" rows="3" placeholder="${esc(STATE.biz || (CFG.anchor || {}).label || "")}…">${esc(p.elab[i] || "")}</textarea>
      <div style="display:flex;gap:8px;margin-top:8px;align-items:center;flex-wrap:wrap">
        ${connMode() !== "none" ? `<button class="btn sm" id="elabck${i}" onclick="checkElab('${m.id}',${i})">Check my answer</button>` : `<span class="sub" style="font-size:12px">Connect Claude in Settings to have this checked.</span>`}
        ${fb ? `<span class="sub" style="font-size:12px">Checked ${new Date(fb.at).toLocaleDateString()}</span>` : ""}
      </div>
      <div id="elabfb${i}">${fb ? `<div class="fb ${fb.verdict || ""}"><b>What Claude saw</b>${mdLite(fb.text)}</div>` : ""}</div></div>`;
    });
    s += `<div style="display:flex;gap:9px"><button class="btn primary" onclick="saveElab('${m.id}')">Save and continue</button></div></div>`;
    b.innerHTML = s;
  } else {
    const t = m.assess.transfer,
      st = p.transfer || {},
      rp = m.assess.roleplay;
    const sheets = DATA.library.templates.filter(x => (x.uses || []).includes(m.id));
    let s = `<div class="card"><p class="eyebrow">Step 5 · Apply</p>
      <p class="hint" style="margin-bottom:16px"><span class="i">Why</span> The gap between knowing and doing closes only under transfer: a new situation you have not seen, with the framework not named for you. Write your answer before you open the model answer, or the exercise is worthless.</p>
      <div style="background:var(--surface-2);border-radius:11px;padding:16px;margin-bottom:16px;font-size:15.5px;line-height:1.65">${esc(t.scenario)}</div>
      <h3 style="font-family:var(--serif);font-size:20px;font-weight:600;margin:0 0 12px">${esc(t.prompt)}</h3>
      <textarea id="trin" rows="6" placeholder="Your answer. Reason it through — the reasoning is what is being trained.">${esc(st.answer || "")}</textarea>
      <div style="display:flex;gap:9px;margin-top:12px;flex-wrap:wrap">
        <button class="btn" onclick="saveTransfer('${m.id}',null)">Save draft</button>
        ${connMode() !== "none" ? `<button class="btn" id="trck" onclick="checkTransfer('${m.id}')">Have Claude grade it</button>` : ""}
        <button class="btn primary" onclick="revealModel('${m.id}')">Compare with model answer</button>
      </div>
      <div id="trfb">${st.fb ? `<div class="fb ${st.fb.verdict || ""}"><b>Claude's read${st.fb.verdict ? " · " + st.fb.verdict : ""}</b>${mdLite(st.fb.text)}</div>` : ""}</div>
      <div id="modelbox" class="${st.revealed ? "" : "hidden"}">
        <div class="why" style="margin-top:18px"><b style="color:var(--text);display:block;margin-bottom:6px">Model answer</b>${esc(t.model)}</div>
        <div class="conf"><span style="font-size:13px;color:var(--muted)">How did yours compare?</span>
          ${[
            ["Missed it", 1],
            ["Partly there", 2],
            ["Got it", 3],
          ]
            .map(
              ([l, v]) =>
                `<button class="btn sm ${st.score === v ? "primary" : ""}" onclick="saveTransfer('${m.id}',${v})">${l}</button>`
            )
            .join("")}
        </div>
        ${st.score ? `<p class="sub" style="margin-top:14px">Scored. ${st.score === 3 ? `Now try to explain it to someone who is not a ${esc(CFG.practitioner)} — that is the real test.` : "Re-read the sections this draws on, then come back in a few days and retry from memory."}</p>` : ""}
      </div></div>`;
    if (rp) {
      const done = st.rp;
      s += `<div class="card" style="margin-top:16px;border-color:var(--accent)"><p class="eyebrow" style="color:var(--accent-ink)">Practise it live</p>
        <p style="margin:0 0 10px;color:var(--text-2);font-size:15px">${esc(rp.situation)}</p>
        <p style="margin:0 0 12px"><b>Your goal:</b> ${esc(rp.goal)}</p>
        <p class="sub" style="margin-bottom:12px">Claude plays the other side and stays in character. When you are done, ask for feedback: you are judged on ${rp.rubric.map(r => "<i>" + esc(r) + "</i>").join(", ")}.</p>
        <div style="display:flex;gap:9px;flex-wrap:wrap">
          ${connMode() !== "none" ? `<button class="btn primary" onclick="startRoleplay('${m.id}')">${done ? "Play it again" : "Start the conversation"}</button>` : `<button class="btn" onclick="go('#/settings')">Connect Claude to practise live</button>`}
        </div>
        ${done ? `<div class="fb ${done.verdict || ""}" style="margin-top:14px"><b>Feedback from your last run · ${new Date(done.at).toLocaleDateString()}</b>${mdLite(done.text)}</div>` : ""}</div>`;
    }
    if (sheets.length) {
      s += `<div class="card" style="margin-top:16px"><p class="eyebrow">Worksheets for this module</p>
        <p class="sub" style="margin-bottom:10px">The exercise produces something. Fill it in here; it stays with your progress.</p>
        ${sheets.map(x => `<button class="btn sm" style="margin:0 8px 8px 0" onclick="go('#/library/t-${x.slug}')">${esc(x.title)}${sheetFilled(x.slug) ? ` · ${sheetFilled(x.slug)}/${x.fields}` : ""}</button>`).join("")}</div>`;
    }
    const openGaps = openGapItems(m.id).length;
    const gapLine = openGaps
      ? `One step left: ${openGaps} gap${openGaps > 1 ? "s" : ""} from this module's quiz, exercises and questions to close.`
      : "One step left: check whether anything in this module is still a gap.";
    s += `<div class="card" style="margin-top:16px;text-align:center"><p class="sub" style="margin-bottom:12px">${gapLine}</p><button class="btn primary" onclick="go('#/m/${m.id}/5')">Close the gaps →</button></div>`;
    b.innerHTML = s;
  }
}
/* ---- landing on a section ----
   Every way of getting to a passage goes through jumpToPassage: a TOC link, a message's
   label in the chat, the chat menu, a bookmark, a mark opened from Marks & questions.
   On the Read step it scrolls there now; from anywhere else it remembers the target and
   changes the route, and landOn() scrolls once the step is drawn. Jumps are instant, not
   smooth, so the sections in between are never "in view" on the way. */
let jumpTarget = null; // { sec, markId } to land on when the Read step is next drawn
let resumeGuard = ""; // the module whose resume position was already used this visit
function jumpToPassage(mid, sec, markId) {
  const here = route.view === "m" && route.id === mid && (route.step || 0) === 1;
  if (here) {
    scrollToPassage(sec, markId, true);
    if (sectionScrollHandler) sectionScrollHandler();
    return;
  }
  jumpTarget = { sec, markId };
  go(`#/m/${mid}/1`);
}
function jump(e, i) {
  e.preventDefault();
  jumpToPassage(route.id, i, null);
}
function scrollToPassage(sec, markId, flash) {
  const mk = markId ? document.querySelector(`mark.hl[data-k="${markId}"]`) : null;
  const el = mk || document.getElementById("sec" + sec);
  if (!el) return;
  rail.section = sec;
  el.scrollIntoView({ block: mk ? "center" : "start" });
  if (!flash) return;
  el.classList.add("flash");
  setTimeout(() => el.classList.remove("flash"), 1600);
}
/* The Read step was just drawn. After the route change has scrolled the window to the
   top: land on the jump target, or on the last section seen (once per module visit), and
   then settle which section is in view. */
function landOn(m) {
  const target = jumpTarget;
  jumpTarget = null;
  setTimeout(() => {
    if (!(route.view === "m" && route.id === m.id && (route.step || 0) === 1)) return;
    const pos = STATE.pos[m.id] || 0;
    if (target) scrollToPassage(target.sec, target.markId, true);
    else if (resumeGuard !== m.id && pos > 0 && m.sections[pos]) {
      scrollToPassage(pos, null, false);
      toast("Resumed at “" + m.sections[pos].h + "”");
    }
    resumeGuard = m.id;
    if (sectionScrollHandler) sectionScrollHandler();
  }, 80);
}
/* Which section is being read. The reading band runs from under the sticky topbar to a
   fixed fraction of the viewport (`page.ui.readLine`). The current section keeps its place
   for as long as any of it is inside that band - so a short section stays current while
   the reader is on it - and when it has left, the section under the band's lower edge takes
   over. Recomputed on every scroll, so exactly one section is current however short it is
   (an intersection observer reported two when a short section and its neighbour both
   touched the band). When the section changes the rail is told (railPlaceChanged). */
const SCROLL_THROTTLE_MS = 40;
let sectionScrollHandler = null;
function setupToc() {
  const links = [...document.querySelectorAll("#toc a")];
  const secs = [...document.querySelectorAll(".sec")];
  if (sectionScrollHandler) window.removeEventListener("scroll", sectionScrollHandler);
  if (!secs.length) return;
  const highlight = i => links.forEach((l, j) => l.classList.toggle("on", j === i));
  let queued = false;
  // A timer, not requestAnimationFrame: frames stop while a tab is hidden or the
  // renderer is paused, and a throttle that waits for one would then never run again.
  sectionScrollHandler = () => {
    if (queued) return;
    queued = true;
    setTimeout(() => {
      queued = false;
      if (route.view !== "m" || (route.step || 0) !== 1) return;
      const i = sectionInView(secs, rail.section);
      highlight(i);
      if (i === rail.section) return;
      rail.section = i;
      STATE.pos[route.id] = i; // picked up on the next save
      railPlaceChanged();
    }, SCROLL_THROTTLE_MS);
  };
  window.addEventListener("scroll", sectionScrollHandler, { passive: true });
  highlight(rail.section);
}
function sectionInView(secs, current) {
  const bar = document.querySelector(".topbar");
  const bandTop = bar ? bar.getBoundingClientRect().bottom : 0;
  const bandBottom = window.innerHeight * LAYOUT.readLine;
  const held = secs[current] && secs[current].getBoundingClientRect();
  if (held && held.bottom > bandTop && held.top < bandBottom) return current;
  let found = 0;
  secs.forEach((el, i) => {
    if (el.getBoundingClientRect().top <= bandBottom) found = i;
  });
  return found;
}
function toggleBookmark(mid, i) {
  const k = mid + ":" + i;
  if (STATE.bookmarks[k]) {
    delete STATE.bookmarks[k];
    toast("Bookmark removed");
  } else {
    STATE.bookmarks[k] = Date.now();
    toast("Bookmarked");
  }
  save();
  renderStep(byId(mid), 1);
  renderSidebar();
}
function savePredict(id) {
  progressOf(id).predict = $("#predin").value;
  save();
  go("#/m/" + id + "/1");
}
function saveNote(id) {
  STATE.notes[id] = $("#noteIn").value;
  save();
  toast("Notes saved");
  go("#/m/" + id + "/2");
}
function saveElab(id) {
  const p = progressOf(id);
  document.querySelectorAll("[data-el]").forEach(t => (p.elab[t.dataset.el] = t.value));
  save();
  toast("Saved");
  go("#/m/" + id + "/4");
}
function saveTransfer(id, score) {
  const p = progressOf(id);
  const ta = $("#trin");
  p.transfer = Object.assign({}, p.transfer, {
    answer: ta ? ta.value : (p.transfer || {}).answer || "",
  });
  if (score != null) p.transfer.score = score;
  save();
  toast("Saved");
  if (score != null) renderStep(byId(id), 4);
}
function revealModel(id) {
  const p = progressOf(id);
  const ta = $("#trin");
  if (ta && !ta.value.trim()) {
    toast("Write your own answer first — that is the whole exercise.");
    ta.focus();
    return;
  }
  p.transfer = Object.assign({}, p.transfer, { answer: ta.value, revealed: true });
  save();
  $("#modelbox").classList.remove("hidden");
  $("#modelbox").scrollIntoView({ behavior: "smooth", block: "center" });
}
/* The reading-progress line at the top of the Read step, redrawn without the step when a
   section is ticked by the audio reader. */
function readCountText(m) {
  return `Reading progress · ${secDone(m)} of ${secTotal(m)} sections`;
}
function readPercent(m) {
  return Math.round((secDone(m) / secTotal(m)) * 100);
}
function refreshReadProgress(m) {
  const count = document.getElementById("readcount");
  if (count) count.textContent = readCountText(m);
  const bar = document.getElementById("readbar");
  if (bar) bar.style.width = readPercent(m) + "%";
}
function tickSec(id, i) {
  const p = progressOf(id);
  p.secs[i] = !p.secs[i];
  save();
  markDay();
  renderStep(byId(id), 1);
  renderSidebar();
}
function allSecs(id, on) {
  const m = byId(id),
    p = progressOf(id);
  m.sections.forEach((_, i) => (p.secs[i] = on));
  save();
  renderStep(m, 1);
  renderSidebar();
}
