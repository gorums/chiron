/* ---------- review ---------- */
let session = null;
function viewReview() {
  const v = $("#view");
  const mode = route.id === "mistakes" ? "mistakes" : "due";
  if (!cardCount()) {
    v.innerHTML = `<div class="wrap"><div class="empty"><h2 class="big">Your practice deck is empty</h2>
      <p>Complete a module and its flashcards drop into this deck automatically. They then come back on a schedule tuned to the moment just before you would forget them. Questions you miss in a quiz join the deck too.</p>
      <button class="btn primary gap-top" onclick="go('#/home')">Back to dashboard</button></div></div>`;
    return;
  }
  if (session && session.mode !== mode) session = null;
  if (!session || !session.queue.length) {
    if (mode === "mistakes") {
      const all = allCards().filter(c => c.mistake);
      if (!all.length) {
        v.innerHTML = `<div class="wrap"><div class="empty"><h2 class="big">No mistakes waiting</h2>
          <p>Every question you get wrong, or only get with a hint, becomes a card here. Four clean recalls and it retires.</p>
          <button class="btn primary gap-top" onclick="go('#/review')">Practice the deck</button></div></div>`;
        return;
      }
      startSession(all, "mistakes");
    } else {
      const due = dueCards();
      if (!due.length) {
        const upcoming = forecast();
        v.innerHTML = `<div class="wrap"><div class="empty"><h2 class="big">Nothing due today</h2>
          <p>${cardCount()} cards in the deck. Next batch: ${upcoming.next ? upcoming.next + " card(s) in " + upcoming.days + " day(s)" : "none scheduled"}.</p>
          <p class="narrow gap-top">Practising early feels productive and is mostly wasted effort — the schedule is doing the work. Spend the time on a new module instead.</p>
          <button class="btn primary gap-top-sm" onclick="go('#/home')">Dashboard</button>
          ${mistakeCount() ? `<button class="btn gap-top-sm" onclick="go('#/review/mistakes')">Fix mistakes (${mistakeCount()})</button>` : ""}
          <button class="btn gap-top-sm" onclick="cramAll()">Practise everything anyway</button></div></div>`;
        return;
      }
      startSession(due, "due");
    }
  }
  drawCard();
}
function startSession(cards, mode) {
  session = {
    queue: shuffled(cards),
    total: cards.length,
    done: 0,
    flipped: false,
    mode: mode || "due",
    retired: 0,
  };
}
function cramAll() {
  startSession(allCards(), "due");
  drawCard();
}
function drawCard() {
  const v = $("#view");
  if (!session || !session.queue.length) {
    const n = session ? session.done : 0,
      r = session ? session.retired : 0;
    session = null;
    const nextMod = nextUnfinished();
    const mDue = mistakesDue();
    v.innerHTML = `<div class="wrap"><div class="empty"><h2 class="big">Session complete</h2>
      <p>${n} card${n === 1 ? "" : "s"} practised. Each one is now scheduled further out.${r ? ` ${r} mistake${r === 1 ? "" : "s"} retired for good.` : ""}</p>
      <div class="rowline center gap-top wrapped">
        ${nextMod ? `<button class="btn primary" onclick="go('#/m/${nextMod.id}')">Next module · ${nextMod.id} ${esc(nextMod.short)}</button>` : ""}
        ${mDue ? `<button class="btn" onclick="go('#/review/mistakes')">Fix mistakes (${mDue})</button>` : ""}
        <button class="btn${nextMod ? "" : " primary"}" onclick="go('#/home')">Dashboard</button>
      </div></div></div>`;
    renderSidebar();
    return;
  }
  markDay();
  const cur = session.queue[0];
  const pct = Math.round((session.done / session.total) * 100);
  const wins = cur.st.wins || 0;
  v.innerHTML = `<div class="wrap">
    <div class="qmeta gap-bottom-lg"><span>${session.mode === "mistakes" ? "Fixing mistakes" : "Practice · interleaved"}</span><span class="bar"><i style="width:${pct}%"></i></span>
      <span class="pushright">${session.queue.length} left</span></div>
    <button class="flash ${cur.mistake ? "mistake" : ""}" onclick="flip()" aria-label="${session.flipped ? "Card answer shown" : "Show the answer"}">
      <span class="tag ${cur.mistake ? "warn" : "acc"}" style="margin-bottom:16px" title="${cur.mistake ? help("mistake card") : ""}">${cur.mistake ? "mistake · " + wins + "/4 clean · " : ""}${cur.mid} · ${esc(cur.mtitle)}</span>
      <div class="front">${esc(cur.c.front)}</div>
      ${session.flipped ? `<div class="back">${esc(cur.c.back)}</div>` : `<div class="back empty-back">Answer out loud, then click or press <kbd>space</kbd></div>`}
    </button>
    ${
      session.flipped
        ? `<div class="gradebar">
      ${[
        ["Again", 0],
        ["Hard", 1],
        ["Good", 2],
        ["Easy", 3],
      ]
        .map(
          ([l, g]) =>
            `<button onclick="rate(${g})">${l}<small>${predictIvl(cur.k, g)}</small></button>`
        )
        .join("")}
    </div><p class="sub centered gap-top tiny">Be honest. Marking "Good" on a card you fumbled is how a review deck becomes decoration. Keys <kbd>1</kbd>–<kbd>4</kbd>.</p>`
        : `<div class="centered gap-top"><button class="btn primary" onclick="flip()">Show answer <kbd>space</kbd></button></div>`
    }
  </div>`;
}
function predictIvl(k, g) {
  const st = STATE.cards[k];
  if (!st) return "";
  let ivl;
  if (g === 0) ivl = 0;
  else if (g === 1) ivl = st.ivl ? Math.max(1, Math.round(st.ivl * 1.2)) : 1;
  else if (g === 2) ivl = st.ivl === 0 ? 1 : st.ivl === 1 ? 3 : Math.round(st.ivl * st.ease);
  else ivl = st.ivl === 0 ? 3 : Math.round(st.ivl * st.ease * 1.25);
  if (isMistakeKey(k) && g >= 2 && (st.wins || 0) + 1 >= 4) return "retire";
  return ivl === 0
    ? "today"
    : ivl === 1
      ? "1 day"
      : ivl < 30
        ? ivl + " days"
        : Math.round(ivl / 30) + " mo";
}
function flip() {
  if (session) {
    session.flipped = true;
    drawCard();
  }
}
function rate(g) {
  if (!session || !session.flipped) return;
  const cur = session.queue.shift();
  const retired = grade(cur.k, g);
  if (retired) {
    session.retired++;
    session.done++;
    toast("Retired — four clean recalls");
  } else if (g === 0) session.queue.push(cur);
  else session.done++;
  session.flipped = false;
  drawCard();
}
function forecast() {
  const t = todayNum();
  let best = null;
  Object.values(STATE.cards).forEach(c => {
    if (c.due > t && (best === null || c.due < best)) best = c.due;
  });
  if (best === null) return { next: 0, days: 0 };
  const n = Object.values(STATE.cards).filter(c => c.due === best).length;
  return { next: n, days: best - t };
}
