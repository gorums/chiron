/* ---------- modal / palette ---------- */
function showModal(inner) {
  $("#modalhost").innerHTML =
    `<div class="overlay" onclick="if(event.target===this)closeModal()"><div class="modal">${inner}</div></div>`;
}
function closeModal() {
  $("#modalhost").innerHTML = "";
}
/* In-page stand-ins for confirm() and prompt(): same look as every other modal, keyboard
   friendly (Enter confirms, Esc cancels), and they do not block the page. */
let modalCb = null;
function confirmModal(title, body, okLabel, onOk, danger) {
  modalCb = onOk;
  showModal(`<h3 style="font-family:var(--serif);font-size:21px;margin:0 0 8px;font-weight:600">${esc(title)}</h3>
    <p class="sub" style="margin:0 0 18px;font-size:14px">${esc(body)}</p>
    <div style="display:flex;gap:9px;justify-content:flex-end">
      <button class="btn" onclick="closeModal()">Cancel</button>
      <button class="btn primary" id="modalok" ${danger ? 'style="background:var(--bad);border-color:var(--bad);color:#fff"' : ""} onclick="modalOk()">${esc(okLabel || "OK")}</button></div>`);
  setTimeout(() => {
    const b = document.getElementById("modalok");
    if (b) b.focus();
  }, 20);
}
function promptModal(title, value, okLabel, onOk) {
  modalCb = () => onOk(document.getElementById("modalin").value);
  showModal(`<h3 style="font-family:var(--serif);font-size:21px;margin:0 0 12px;font-weight:600">${esc(title)}</h3>
    <input type="text" id="modalin" value="${esc(value || "")}" onkeydown="if(event.key==='Enter'){event.preventDefault();modalOk()}">
    <div style="display:flex;gap:9px;justify-content:flex-end;margin-top:14px">
      <button class="btn" onclick="closeModal()">Cancel</button>
      <button class="btn primary" onclick="modalOk()">${esc(okLabel || "Save")}</button></div>`);
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
        h: "#/m/" + m.id + "/1",
        body: s.text,
      })
    );
  });
  DATA.library.glossary.forEach(g =>
    paletteIndex.push({ t: g.term, c: "Glossary · " + g.def.slice(0, 70), h: "#/library/glossary" })
  );
  DATA.library.models.forEach((m, i) =>
    paletteIndex.push({ t: m.title, c: "Mental model", h: "#/library/models" })
  );
  DATA.library.templates.forEach(t =>
    paletteIndex.push({ t: t.title, c: "Worksheet", h: "#/library/t-" + t.slug })
  );
  paletteIndex.push({ t: "Review due cards", c: "Spaced repetition", h: "#/review" });
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
  paletteIndex.push({ t: "Settings", c: "Claude, reading preferences", h: "#/settings" });
  paletteIndex.push({ t: "Backup & restore", c: "Export your progress", act: openData });
  paletteIndex.push({
    t: "The plan",
    c: "Curriculum, how to study, the path to expert",
    h: "#/plan/curriculum",
  });
}
function openPalette() {
  if (!paletteIndex) buildIndex();
  $("#modalhost").innerHTML = `<div class="overlay" onclick="if(event.target===this)closeModal()">
    <div class="palette"><input id="pq" type="text" placeholder="Search modules, sections, terms…" autocomplete="off">
    <div class="results" id="pr"></div></div></div>`;
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
            `<button class="res ${i === paletteCursor ? "on" : ""}" onclick="pickRes(${i})"><div class="t">${esc(r.t)}</div><div class="c">${esc(r.c || "")}</div></button>`
        )
        .join("")
    : `<div style="padding:22px;text-align:center;color:var(--muted);font-size:13.5px">Nothing found</div>`;
}
function openHelp() {
  showModal(`<h3 style="font-family:var(--serif);font-size:22px;margin:0 0 14px;font-weight:600">Keyboard shortcuts</h3>
  <div style="display:grid;gap:9px;font-size:14px">
    ${[
      ["select", "Select text to highlight it or ask about it"],
      ["a", "Show / hide the chat rail"],
      ["s", "Show / hide the sidebar"],
      ["i", "Jump to the chat box"],
      ["/", "Search everything"],
      ["j / k", "Next / previous module"],
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
      .map(
        ([k, d]) =>
          `<div style="display:flex;gap:12px"><kbd style="min-width:52px;text-align:center">${k}</kbd><span style="color:var(--text-2)">${d}</span></div>`
      )
      .join("")}
  </div>
  <div class="hint" style="margin-top:18px"><span class="i">Note</span> Progress is stored in this browser. Use Backup &amp; restore, under Settings, to move it or keep a copy.</div>`);
}
