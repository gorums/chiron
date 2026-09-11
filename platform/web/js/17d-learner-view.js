/* ---- the learner memory on screen: the profile page and the gaps card ----
   The model is in 17c-learner.js. This file draws it: `#/learner`, the card on the
   dashboard, and the one action both share - asking the tutor about a gap, which opens
   the module with the question already sent. */

/* Open the module with the rail up and send `q` as the reader's question. The rail is
   drawn by the route change, so the question waits in `rail.pendingAsk` until then. */
function askAbout(mid, q) {
  if (!byId(mid)) return;
  showRail();
  rail.pendingAsk = q;
  if (route.view === "m" && route.id === mid) renderRail();
  else go(stepHash(mid, 1));
}
function drillGap(id) {
  const g = (learner().gaps || []).find(x => x.id === id);
  if (!g) return;
  askAbout(
    g.mid,
    `Quiz me on ${g.topic}. Ask ONE question at a time that tests whether I can use the idea, wait for my answer, grade it honestly in a line or two, then ask the next. Three questions, then tell me whether this gap has closed.`
  );
}
function dismissGap(id) {
  closeGap(id);
  toast("Marked as closed — it stays out of the tutor's prompts");
  render();
}
function restoreGap(id) {
  reopenGap(id);
  render();
}
function learnerUpdatedLabel() {
  const L = learner();
  if (!L.at) return "";
  const grown = learnerEventCount() - (L.events || 0);
  return `Written ${new Date(L.at).toLocaleDateString(undefined, { day: "numeric", month: "short" })}${grown > 0 ? ` · ${grown} new thing${grown > 1 ? "s" : ""} since` : ""}`;
}
function gapRow(g) {
  const m = byId(g.mid);
  const closed = g.status === "closed";
  return `<div class="gaprow ${closed ? "closed" : ""}">
    <div class="gaphead"><b>${esc(g.topic)}</b>
      ${m ? `<a class="tag acc" href="#/m/${m.id}" data-help="${esc(m.title)}">${m.id}</a>` : ""}
      ${closed ? `<span class="tag">closed</span>` : ""}</div>
    <p class="gapwhy">${esc(g.why)}</p>
    ${g.ask && !closed ? `<p class="gapask">${esc(g.ask)}</p>` : ""}
    <div class="gapacts">
      ${
        closed
          ? `<button class="btn sm" onclick="restoreGap('${esc(g.id)}')">Reopen</button>`
          : `${m && g.ask ? `<button class="btn sm primary" onclick="askAbout('${m.id}', this.dataset.q)" data-q="${esc(g.ask)}">Ask the tutor</button>` : ""}
             ${m ? `<button class="btn sm" onclick="drillGap('${esc(g.id)}')">Drill me on it</button>` : ""}
             <button class="btn sm" onclick="dismissGap('${esc(g.id)}')">Mark closed</button>`
      }
    </div>
  </div>`;
}
function briefCard() {
  const L = learner();
  const connected = connMode() !== "none";
  const busy = learnerRun.busy;
  const n = learnerEventCount();
  const button = `<button class="btn ${L.brief ? "" : "primary"}" onclick="refreshLearner()" ${busy || !connected || !n ? "disabled" : ""}>${busy ? "Reading your work…" : L.brief ? "Update from my work" : "Find my gaps"}</button>`;
  let body;
  if (L.brief) body = `<div class="brief">${mdLite(L.brief)}</div>`;
  else if (!n)
    body = `<p class="sub">Nothing to learn from yet. Answer a quiz, have an exercise checked, or ask the tutor something, and this page starts to fill in.</p>`;
  else if (!connected)
    body = `<p class="sub">There are ${n} things on record to learn from, but the tutor is not connected. <a href="#/settings">Connect it</a> to have the brief written; the evidence below works without it.</p>`;
  else
    body = `<p class="sub">${n} thing${n > 1 ? "s" : ""} on record. The tutor reads them and writes what it should know before every answer.</p>`;
  return `<div class="card gap-bottom">
    <div class="rowline wrapped baseline">
      <h3 class="eyebrow">The brief</h3>
      <span class="sub pushright">${learnerUpdatedLabel()}${learnerStale() && L.brief ? " · out of date" : ""}</span></div>
    ${body}
    <div class="rowline wrapped gap-top">${button}
      ${(L.strengths || []).length ? "" : `<span class="sub">The tutor reads this before every reply.</span>`}</div>
    ${(L.strengths || []).length ? `<h3 class="eyebrow gap-top">What holds up</h3><ul class="strengths">${L.strengths.map(s => `<li>${esc(s)}</li>`).join("")}</ul>` : ""}
  </div>`;
}
function gapsCard() {
  const open = openGaps(),
    closed = (learner().gaps || []).filter(g => g.status === "closed");
  let h = `<div class="card gap-bottom"><h3 class="eyebrow" data-help="${esc(help("gap"))}">Gaps</h3>`;
  if (!open.length)
    h += `<p class="sub">${learner().brief ? "No open gaps. Keep answering; new ones show here as the evidence comes in." : "Gaps appear here once the brief is written. Each one comes with a question the tutor can use to check whether it has closed."}</p>`;
  else
    h += `<p class="sub gap-bottom">Each gap goes into the tutor's prompt and ahead of the suggested questions in the modules it touches. Close one yourself when you know it is fixed; the next update closes the rest.</p>${open.map(gapRow).join("")}`;
  if (closed.length)
    h += `<details class="gap-top"><summary class="sub">${closed.length} closed</summary>${closed.map(gapRow).join("")}</details>`;
  return h + `</div>`;
}
function weakSpotsCard() {
  const spots = weakSpots().slice(0, 8);
  if (!spots.length) return "";
  const max = Math.max(1, spots[0].score);
  const rows = spots
    .map(
      w => `<div class="spot">
      <a class="mrow flat" href="#/m/${w.m.id}"><span class="dot ${masteryClass(w.m)}"></span><span class="code">${w.m.id}</span><span class="t">${esc(w.m.short)}</span></a>
      <span class="bar"><i style="width:${Math.round((w.score / max) * 100)}%"></i></span>
      <ul>${w.lines.map(l => `<li>${esc(l)}</li>`).join("")}</ul></div>`
    )
    .join("");
  return `<div class="card gap-bottom"><h3 class="eyebrow">Where the evidence points</h3>
    <p class="sub gap-bottom">Counted from your record, no model involved: missed questions weigh by how sure you were, cards that keep lapsing and checkpoint misses count twice.</p>${rows}</div>`;
}
function askedCard() {
  const asked = learnerEvidence()
    .filter(e => e.kind === "asked")
    .slice(0, LEARNER.recentEvidence);
  if (!asked.length) return "";
  const rows = asked
    .map(e => {
      const m = byId(e.mid);
      const sec = m && e.sec != null && m.sections[e.sec];
      return `<div class="askedrow"><a class="tag" href="${stepHash(e.mid, 1)}">${esc(e.mid)}${sec ? " · " + esc(sec.h) : ""}</a><span>${esc(e.text.replace(/^Asked: /, ""))}</span></div>`;
    })
    .join("");
  return `<div class="card"><h3 class="eyebrow">What you asked</h3>
    <p class="sub gap-bottom">Your questions, newest first. They tell the tutor which ideas needed a second explanation.</p>${rows}</div>`;
}
function viewLearner() {
  const h = `<div class="wrap-wide">
  <h2 class="big">Your gaps</h2>
  <p class="lede">What the tutor has learned about you: built from your quiz answers, the exercises it graded, the cards you keep missing and the questions you asked — in this course only. It reads this before every reply, and the suggested questions in the chat lean on it.</p>
  ${briefCard()}${gapsCard()}${weakSpotsCard()}${askedCard()}</div>`;
  $("#view").innerHTML = h;
}
/* The dashboard card: the top gaps, or the way to get them. Empty until there is evidence. */
function renderGapCard() {
  const open = openGaps().slice(0, 3);
  const n = learnerEventCount();
  if (!n) return "";
  if (!open.length) {
    const spots = weakSpots().slice(0, 3);
    if (!spots.length && !learnerStale()) return "";
    return `<div class="card gap-bottom">
      <h3 class="eyebrow">Your gaps</h3>
      <p class="lede">${spots.length ? "The evidence points at " + spots.map(w => w.m.id).join(", ") + ". " : ""}${connMode() !== "none" ? "Have the tutor read your work and name the gaps; it then works on them in every chat." : "Connect the tutor to have the gaps named; it then works on them in every chat."}</p>
      <div class="rowline wrapped">
        ${connMode() !== "none" ? `<button class="btn primary" onclick="refreshLearner()" ${learnerRun.busy ? "disabled" : ""}>${learnerRun.busy ? "Reading your work…" : "Find my gaps"}</button>` : ""}
        <a class="btn" href="#/learner">See the evidence</a></div></div>`;
  }
  return `<div class="card accented gap-bottom">
    <h3 class="eyebrow accent-ink" data-help="${esc(help("gap"))}">Gaps the tutor is working on</h3>
    <p class="lede">From your answers and questions. Ask about one and the tutor picks it up where you left it.</p>
    <div class="rowline wrapped">
    ${open
      .map(
        g =>
          `<button class="btn sm" onclick="${g.ask ? `askAbout('${g.mid}', this.dataset.q)` : `go('#/m/${g.mid}')`}" data-q="${esc(g.ask || "")}" data-help="${esc(g.why)}">${esc(g.mid)} · ${esc(g.topic)}</button>`
      )
      .join("")}
    <a class="btn sm" href="#/learner">All gaps${learnerStale() && connMode() !== "none" ? " · update" : ""}</a>
    </div>
  </div>`;
}
