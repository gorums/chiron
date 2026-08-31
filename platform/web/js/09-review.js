/* ---------- review ---------- */
let session = null;
function viewReview() {
  const v = $("#view");
  if (!cardCount()) {
    v.innerHTML = `<div class="wrap"><div class="empty"><div class="big">Your review deck is empty</div>
      <p>Complete a module and its flashcards drop into this deck automatically. They then come back on a schedule tuned to the moment just before you would forget them.</p>
      <button class="btn primary" style="margin-top:12px" onclick="go('#/home')">Back to dashboard</button></div></div>`;
    return;
  }
  if (!session || !session.queue.length) {
    const due = dueCards();
    if (!due.length) {
      const upcoming = forecast();
      v.innerHTML = `<div class="wrap"><div class="empty"><div class="big">Nothing due today</div>
        <p>${cardCount()} cards in the deck. Next batch: ${upcoming.next ? upcoming.next + " card(s) in " + upcoming.days + " day(s)" : "none scheduled"}.</p>
        <p style="max-width:460px;margin:12px auto">Reviewing early feels productive and is mostly wasted effort — the schedule is doing the work. Spend the time on a new module instead.</p>
        <button class="btn primary" style="margin-top:6px" onclick="go('#/home')">Dashboard</button>
        <button class="btn" style="margin-top:6px" onclick="cramAll()">Review everything anyway</button></div></div>`;
      return;
    }
    startSession(due);
  }
  drawCard();
}
function startSession(cards) {
  const q = cards.slice();
  for (let i = q.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1));[q[i], q[j]] = [q[j], q[i]]; }
  session = { queue: q, total: q.length, done: 0, flipped: false };
}
function cramAll() {
  const all = [];
  MODS.forEach(m => (m.assess.cards || []).forEach((c, i) => {
    const k = cardKey(m.id, i); if (S.cards[k]) all.push({ k, mid: m.id, mtitle: m.title, c, st: S.cards[k] });
  }));
  startSession(all); drawCard();
}
function drawCard() {
  const v = $("#view");
  if (!session || !session.queue.length) {
    const n = session ? session.done : 0; session = null;
    v.innerHTML = `<div class="wrap"><div class="empty"><div class="big">Session complete</div>
      <p>${n} card${n === 1 ? "" : "s"} reviewed. Each one is now scheduled further out.</p>
      <button class="btn primary" style="margin-top:12px" onclick="go('#/home')">Dashboard</button></div></div>`;
    renderSidebar(); return;
  }
  markDay();
  const cur = session.queue[0];
  const pct = Math.round(session.done / session.total * 100);
  v.innerHTML = `<div class="wrap">
    <div class="qmeta" style="margin-bottom:18px"><span>Review · interleaved</span><span class="bar"><i style="width:${pct}%"></i></span>
      <span style="margin-left:auto">${session.queue.length} left</span></div>
    <div class="flash" onclick="flip()">
      <span class="tag acc" style="margin-bottom:16px">${cur.mid} · ${esc(cur.mtitle)}</span>
      <div class="front">${esc(cur.c.front)}</div>
      ${session.flipped ? `<div class="back">${esc(cur.c.back)}</div>` : `<div class="back" style="border:0;color:var(--muted);font-size:13.5px">Answer out loud, then click or press <kbd>space</kbd></div>`}
    </div>
    ${session.flipped ? `<div class="gradebar">
      ${[["Again", "<1d", 0], ["Hard", "", 1], ["Good", "", 2], ["Easy", "", 3]].map(([l, s, g], i) =>
        `<button onclick="rate(${g})">${l}<small>${predictIvl(cur.k, g)}</small></button>`).join("")}
    </div><p class="sub" style="text-align:center;margin-top:12px;font-size:12px">Be honest. Marking "Good" on a card you fumbled is how a review deck becomes decoration. Keys <kbd>1</kbd>–<kbd>4</kbd>.</p>`
      : `<div style="text-align:center;margin-top:16px"><button class="btn primary" onclick="flip()">Show answer <kbd>space</kbd></button></div>`}
  </div>`;
}
function predictIvl(k, g) {
  const st = S.cards[k]; if (!st) return "";
  const save0 = JSON.stringify(st);
  let ivl;
  if (g === 0) ivl = 0;
  else if (g === 1) ivl = st.ivl ? Math.max(1, Math.round(st.ivl * 1.2)) : 1;
  else if (g === 2) ivl = st.ivl === 0 ? 1 : (st.ivl === 1 ? 3 : Math.round(st.ivl * st.ease));
  else ivl = st.ivl === 0 ? 3 : Math.round(st.ivl * st.ease * 1.25);
  JSON.parse(save0);
  return ivl === 0 ? "today" : ivl === 1 ? "1 day" : ivl < 30 ? ivl + " days" : Math.round(ivl / 30) + " mo";
}
function flip() { if (session) { session.flipped = true; drawCard(); } }
function rate(g) {
  if (!session || !session.flipped) return;
  const cur = session.queue.shift();
  grade(cur.k, g);
  if (g === 0) session.queue.push(cur); else session.done++;
  session.flipped = false; drawCard();
}
function forecast() {
  const t = todayNum(); let best = null;
  Object.values(S.cards).forEach(c => { if (c.due > t && (best === null || c.due < best)) best = c.due; });
  if (best === null) return { next: 0, days: 0 };
  const n = Object.values(S.cards).filter(c => c.due === best).length;
  return { next: n, days: best - t };
}
