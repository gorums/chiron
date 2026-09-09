/* ---------- modal / palette ----------
   One dialog host. Whatever is inside it, the rules are the same: it says it is a dialog,
   the focus goes into it and cannot leave by Tab, Escape closes it, and the focus goes back
   to whatever opened it. Everything on the page that used to be a browser confirm() or
   prompt() is one of these. */
let modalReturn = null; // the element to give the focus back to
function modalOpen() {
  return !!$("#modalhost").innerHTML;
}
function showModal(inner, label) {
  modalReturn = document.activeElement;
  $("#modalhost").innerHTML = `<div class="overlay" onclick="if(event.target===this)closeModal()">
       <div class="modal" role="dialog" aria-modal="true" ${label ? `aria-label="${esc(label)}"` : ""}>${inner}</div></div>`;
  setTimeout(() => focusFirst($("#modalhost")), 20);
}
function closeModal() {
  $("#modalhost").innerHTML = "";
  const back = modalReturn;
  modalReturn = null;
  if (back && document.body.contains(back)) back.focus();
}
const FOCUSABLE =
  'a[href], button:not([disabled]), textarea, input:not([type="hidden"]), select, [tabindex]:not([tabindex="-1"])';
function focusables(host) {
  return Array.from(host.querySelectorAll(FOCUSABLE)).filter(el => el.offsetParent !== null);
}
function focusFirst(host) {
  const first = focusables(host)[0];
  if (first) first.focus();
}
/* Tab inside an open dialog wraps around instead of walking off into the page behind it. */
document.addEventListener("keydown", e => {
  if (e.key !== "Tab") return;
  const host = $("#modalhost");
  if (!host || !host.innerHTML) return;
  const items = focusables(host);
  if (!items.length) return;
  const first = items[0],
    last = items[items.length - 1];
  if (e.shiftKey && document.activeElement === first) {
    e.preventDefault();
    last.focus();
  } else if (!e.shiftKey && document.activeElement === last) {
    e.preventDefault();
    first.focus();
  }
});

/* In-page stand-ins for confirm() and prompt(): same look as every other dialog, keyboard
   friendly, and they do not block the page. A dangerous one focuses Cancel, so Enter
   cannot erase anything by reflex. */
let modalCb = null;
function confirmModal(title, body, okLabel, onOk, danger) {
  modalCb = onOk;
  showModal(
    `<h3 class="h-serif">${esc(title)}</h3>
    <p class="sub gap-bottom-lg">${esc(body)}</p>
    <div class="rowline end">
      <button class="btn" id="modalcancel" onclick="closeModal()">Cancel</button>
      <button class="btn ${danger ? "danger" : "primary"}" id="modalok" onclick="modalOk()">${esc(okLabel || "OK")}</button></div>`,
    title
  );
  setTimeout(() => {
    const b = document.getElementById(danger ? "modalcancel" : "modalok");
    if (b) b.focus();
  }, 20);
}
function promptModal(title, value, okLabel, onOk) {
  modalCb = () => onOk(document.getElementById("modalin").value);
  showModal(
    `<h3 class="h-serif">${esc(title)}</h3>
    <label class="visually-hidden" for="modalin">${esc(title)}</label>
    <input type="text" id="modalin" value="${esc(value || "")}" onkeydown="if(event.key==='Enter'){event.preventDefault();modalOk()}">
    <div class="rowline end gap-top">
      <button class="btn" onclick="closeModal()">Cancel</button>
      <button class="btn primary" onclick="modalOk()">${esc(okLabel || "Save")}</button></div>`,
    title
  );
  setTimeout(() => {
    const i = document.getElementById("modalin");
    if (i) {
      i.focus();
      i.select();
    }
  }, 20);
}
function modalOk() {
  const cb = modalCb;
  modalCb = null;
  closeModal();
  if (cb) cb();
}
let paletteIndex = null,
  paletteCursor = 0,
  paletteResults = [];
function buildIndex() {
  paletteIndex = [];
  MODS.forEach(m => {
    paletteIndex.push({
      t: m.id + " · " + m.title,
      c: "Module · " + partName(m.part),
      h: "#/m/" + m.id,
    });
    m.sections.forEach((s, i) =>
      paletteIndex.push({
        t: s.h,
        c: m.id + " · " + m.short,
        act: () => jumpToPassage(m.id, i, null),
        body: s.text,
      })
    );
  });
  DATA.library.glossary.forEach(g =>
    paletteIndex.push({
      t: g.term,
      c: "Glossary · " + g.def.slice(0, 70),
      act: () => openGlossary(g.term),
    })
  );
  DATA.library.models.forEach((m, i) =>
    paletteIndex.push({ t: m.title, c: "Mental model", act: () => openModelCard(i) })
  );
  DATA.library.templates.forEach(t =>
    paletteIndex.push({ t: t.title, c: "Worksheet", h: "#/library/t-" + t.slug })
  );
  paletteIndex.push({ t: "Practice the deck", c: "Spaced repetition", h: "#/review" });
  paletteIndex.push({
    t: "Fix mistakes",
    c: "Questions you missed, as cards",
    h: "#/review/mistakes",
  });
  paletteIndex.push({ t: "Checkpoints", c: "Mixed quizzes across finished modules", h: "#/check" });
  paletteIndex.push({ t: "Progress & stats", c: "Your numbers", h: "#/stats" });
  paletteIndex.push({ t: "Course record", c: "What you can show for the hours", h: "#/record" });
  paletteIndex.push({ t: "Study plan", c: "Hours per week, target date", h: "#/home" });
  paletteIndex.push({
    t: "Marks & questions",
    c: "Highlights, notes, bookmarks, chats",
    h: "#/marks",
  });
  paletteIndex.push({ t: "Settings", c: "The tutor, reading preferences", h: "#/settings" });
  paletteIndex.push({ t: "Your gaps", c: "What the tutor has learned about you", h: "#/learner" });
  paletteIndex.push({ t: "Backup & restore", c: "Export your progress", act: openData });
  paletteIndex.push({
    t: "The plan",
    c: "Curriculum, how to study, the path to expert",
    h: "#/plan/curriculum",
  });
}
function openPalette() {
  if (!paletteIndex) buildIndex();
  modalReturn = document.activeElement;
  $("#modalhost").innerHTML = `<div class="overlay" onclick="if(event.target===this)closeModal()">
    <div class="palette" role="dialog" aria-modal="true" aria-label="Search everything">
    <label class="visually-hidden" for="pq">Search modules, sections and terms</label>
    <input id="pq" type="text" placeholder="Search modules, sections, terms…" autocomplete="off">
    <div class="results" id="pr" role="listbox"></div></div></div>`;
  const q = $("#pq");
  q.addEventListener("input", () => {
    paletteCursor = 0;
    runSearch(q.value);
  });
  q.addEventListener("keydown", e => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      paletteCursor = Math.min(paletteResults.length - 1, paletteCursor + 1);
      paintRes();
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      paletteCursor = Math.max(0, paletteCursor - 1);
      paintRes();
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (paletteResults[paletteCursor]) pickRes(paletteCursor);
    }
  });
  runSearch("");
  setTimeout(() => q.focus(), 30);
}
function pickRes(i) {
  const r = paletteResults[i];
  if (!r) return;
  closeModal();
  if (r.act) r.act();
  else go(r.h);
}
function runSearch(v) {
  const s = v.trim().toLowerCase();
  if (!s) paletteResults = paletteIndex.slice(0, 8);
  else {
    paletteResults = paletteIndex
      .map(x => {
        const t = x.t.toLowerCase(),
          c = (x.c || "").toLowerCase(),
          b = (x.body || "").toLowerCase();
        let sc = 0;
        if (t.startsWith(s)) sc = 100;
        else if (t.includes(s)) sc = 70;
        else if (c.includes(s)) sc = 40;
        else if (b.includes(s)) sc = 20;
        return sc ? { x, sc } : null;
      })
      .filter(Boolean)
      .sort((a, b) => b.sc - a.sc)
      .slice(0, 30)
      .map(o => o.x);
  }
  paintRes();
}
function paintRes() {
  $("#pr").innerHTML = paletteResults.length
    ? paletteResults
        .map(
          (r, i) =>
            `<button class="res ${i === paletteCursor ? "on" : ""}" role="option" aria-selected="${i === paletteCursor}" onclick="pickRes(${i})"><div class="t">${esc(r.t)}</div><div class="c">${esc(r.c || "")}</div></button>`
        )
        .join("")
    : `<div class="nores">Nothing found</div>`;
}
function openHelp() {
  showModal(
    `<h3 class="h-serif">How this course works</h3>
  <p class="lede">${howItWorksHtml()}</p>
  <h3 class="h-serif gap-top-lg">Keyboard shortcuts</h3>
  <div class="keylist">
    ${[
      ["select", "Select text to highlight it or ask about it"],
      ["a", "Show / hide the tutor"],
      ["s", "Show / hide the sidebar"],
      ["i", "Jump to the chat box"],
      ["/", "Search everything"],
      ["j / k", "Next unfinished module / previous module"],
      ["a–h / 1–8", "Pick an option in a quiz"],
      ["1–3", "Rate confidence, then continue"],
      ["1–4", "Grade a flashcard"],
      ["space", "Flip a flashcard"],
      ["Enter", "Lock in an answer / continue"],
      ["⌘/Ctrl+↵", "Send a chat message"],
      ["t", "Cycle theme"],
      ["?", "This panel"],
      ["Esc", "Close"],
    ]
      .map(([k, d]) => `<div class="keyrow"><kbd>${k}</kbd><span>${d}</span></div>`)
      .join("")}
  </div>
  <div class="hint gap-top-lg"><span class="i">Note</span> Progress is stored in this browser. Use Backup &amp; restore, under Settings, to move it or keep a copy.</div>`,
    "How this course works"
  );
}
