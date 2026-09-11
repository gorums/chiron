/* ---------- the command palette ----------
   Everything on this page is one Ctrl+K away: a module, a section, a mark, a screen. The
   dialog it opens is the shared one from core/dom.js. */
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
