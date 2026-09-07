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
  else go("#/m/" + mid + "/1");
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
      ${m ? `<button class="tag acc" onclick="go('#/m/${m.id}')" title="${esc(m.title)}">${m.id}</button>` : ""}
      ${closed ? `<span class="tag">closed</span>` : ""}</div>
    <p class="gapwhy">${esc(g.why)}</p>
    ${g.ask && !closed ? `<p class="gapask">${esc(g.ask)}</p>` : ""}
    <div class="gapacts">
      ${
        closed
          ? `<button class="btn sm ghost" onclick="restoreGap('${esc(g.id)}')">Reopen</button>`
          : `${m && g.ask ? `<button class="btn sm primary" onclick="askAbout('${m.id}', this.dataset.q)" data-q="${esc(g.ask)}">Ask the tutor</button>` : ""}
             ${m ? `<button class="btn sm" onclick="drillGap('${esc(g.id)}')">Drill me on it</button>` : ""}
             <button class="btn sm ghost" onclick="dismissGap('${esc(g.id)}')">Mark closed</button>`
      }
    </div>
  </div>`;
}
function briefCard() {
  const L = learner();
  const connected = connMode() !== "none";
  const busy = learnerRun.busy;
  const n = learnerEventCount();
  const button = `<button class="btn ${L.brief ? "" : "primary"}" onclick="refreshLearner()" ${busy || !connected || !n ? "disabled" : ""}>${busy ? "Reading your work…" : L.brief ? "Update from my work" : "Build my profile"}</button>`;
  let body;
  if (L.brief) body = `<div class="brief">${mdLite(L.brief)}</div>`;
  else if (!n)
    body = `<p class="sub">Nothing to learn from yet. Answer a quiz, have an exercise checked, or ask the tutor something, and this page starts to fill in.</p>`;
  else if (!connected)
    body = `<p class="sub">There are ${n} things on record to learn from, but Claude is not connected. <a href="#/settings">Connect</a> to have the brief written; the evidence below works without it.</p>`;
  else
    body = `<p class="sub">${n} thing${n > 1 ? "s" : ""} on record. Claude reads them and writes what the tutor should know before every answer.</p>`;
  return `<div class="card" style="margin-bottom:18px">
    <div style="display:flex;gap:10px;align-items:baseline;flex-wrap:wrap">
      <p class="eyebrow" style="margin:0">The brief</p>
      <span class="sub" style="font-size:12px;margin-left:auto">${learnerUpdatedLabel()}${learnerStale() && L.brief ? " · out of date" : ""}</span></div>
    ${body}
    <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:12px;align-items:center">${button}
      ${(L.strengths || []).length ? "" : `<span class="sub" style="font-size:12px">The tutor reads this before every reply.</span>`}</div>
    ${(L.strengths || []).length ? `<p class="eyebrow" style="margin-top:16px">What holds up</p><ul class="strengths">${L.strengths.map(s => `<li>${esc(s)}</li>`).join("")}</ul>` : ""}
  </div>`;
}
function gapsCard() {
  const open = openGaps(),
    closed = (learner().gaps || []).filter(g => g.status === "closed");
  let h = `<div class="card" style="margin-bottom:18px"><p class="eyebrow">Gaps</p>`;
  if (!open.length)
    h += `<p class="sub">${learner().brief ? "No open gaps. Keep answering; new ones show here as the evidence comes in." : "Gaps appear here once the brief is written. Each one comes with a question the tutor can use to check whether it has closed."}</p>`;
  else
    h += `<p class="sub" style="margin-bottom:12px">Each gap goes into the tutor's prompt and ahead of the suggested questions in the modules it touches. Close one yourself when you know it is fixed; the next update closes the rest.</p>${open.map(gapRow).join("")}`;
  if (closed.length)
    h += `<details style="margin-top:12px"><summary class="sub" style="cursor:pointer">${closed.length} closed</summary>${closed.map(gapRow).join("")}</details>`;
  return h + `</div>`;
}
function weakSpotsCard() {
  const spots = weakSpots().slice(0, 8);
  if (!spots.length) return "";
  const max = Math.max(1, spots[0].score);
  const rows = spots
    .map(
      w => `<div class="spot">
      <button class="mrow" style="padding-left:0" onclick="go('#/m/${w.m.id}')"><span class="dot ${masteryClass(w.m)}"></span><span class="code">${w.m.id}</span><span class="t">${esc(w.m.short)}</span></button>
      <span class="bar"><i style="width:${Math.round((w.score / max) * 100)}%"></i></span>
      <ul>${w.lines.map(l => `<li>${esc(l)}</li>`).join("")}</ul></div>`
    )
    .join("");
  return `<div class="card" style="margin-bottom:18px"><p class="eyebrow">Where the evidence points</p>
    <p class="sub" style="margin-bottom:12px">Counted from your record, no model involved: missed questions weigh by how sure you were, cards that keep lapsing and checkpoint misses count twice.</p>${rows}</div>`;
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
      return `<div class="askedrow"><button class="tag" onclick="go('#/m/${e.mid}/1')">${esc(e.mid)}${sec ? " · " + esc(sec.h) : ""}</button><span>${esc(e.text.replace(/^Asked: /, ""))}</span></div>`;
    })
    .join("");
  return `<div class="card"><p class="eyebrow">What you asked</p>
    <p class="sub" style="margin-bottom:12px">Your questions, newest first. They tell the tutor which ideas needed a second explanation.</p>${rows}</div>`;
}
function viewLearner() {
  const h = `<div class="wrap-wide">
  <h2 class="big">What the tutor knows about you</h2>
  <p class="sub" style="margin-bottom:22px">Built from your quiz answers, the exercises Claude graded, the cards you keep missing and the questions you asked - in this course only. The tutor reads it before every reply, and the suggested questions in the chat lean on it.</p>
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
    return `<div class="card" style="margin-bottom:18px">
      <p class="eyebrow">What the tutor knows about you</p>
      <p class="sub" style="color:var(--text-2);margin-bottom:12px">${spots.length ? "The evidence points at " + spots.map(w => w.m.id).join(", ") + ". " : ""}${connMode() !== "none" ? "Have Claude read your work and name the gaps; the tutor then works on them in every chat." : "Connect Claude to have the gaps named; the tutor then works on them in every chat."}</p>
      <div style="display:flex;gap:8px;flex-wrap:wrap">
        ${connMode() !== "none" ? `<button class="btn primary" onclick="refreshLearner()" ${learnerRun.busy ? "disabled" : ""}>${learnerRun.busy ? "Reading your work…" : "Build my profile"}</button>` : ""}
        <button class="btn" onclick="go('#/learner')">See the evidence</button></div></div>`;
  }
  return `<div class="card" style="margin-bottom:18px;border-color:var(--accent)">
    <p class="eyebrow" style="color:var(--accent-ink)">Gaps the tutor is working on</p>
    <p class="sub" style="color:var(--text-2);margin-bottom:12px">From your answers and questions. Ask about one and the tutor picks it up where you left it.</p>
    ${open
      .map(
        g =>
          `<button class="btn sm" style="margin:0 8px 8px 0" onclick="${g.ask ? `askAbout('${g.mid}', this.dataset.q)` : `go('#/m/${g.mid}')`}" data-q="${esc(g.ask || "")}" title="${esc(g.why)}">${esc(g.mid)} · ${esc(g.topic)}</button>`
      )
      .join("")}
    <button class="btn sm ghost" style="margin:0 8px 8px 0" onclick="go('#/learner')">All gaps${learnerStale() && connMode() !== "none" ? " · update" : ""}</button>
  </div>`;
}
