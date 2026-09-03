/* ---------- modal / palette ---------- */
function showModal(inner) {
  $("#modalhost").innerHTML = `<div class="overlay" onclick="if(event.target===this)closeModal()"><div class="modal">${inner}</div></div>`;
}
function closeModal() { $("#modalhost").innerHTML = ""; }
let idx = null, pi = 0, pres = [];
function buildIndex() {
  idx = [];
  MODS.forEach(m => {
    idx.push({ t: m.id + " · " + m.title, c: "Module · " + partName(m.part), h: "#/m/" + m.id });
    m.sections.forEach((s, i) => idx.push({ t: s.h, c: m.id + " · " + m.short, h: "#/m/" + m.id + "/1", body: s.text }));
  });
  DATA.library.glossary.forEach(g => idx.push({ t: g.term, c: "Glossary · " + g.def.slice(0, 70), h: "#/library/glossary" }));
  DATA.library.models.forEach((m, i) => idx.push({ t: m.title, c: "Mental model", h: "#/library/models" }));
  DATA.library.templates.forEach(t => idx.push({ t: t.title, c: "Worksheet", h: "#/library/t-" + t.slug }));
  idx.push({ t: "Review due cards", c: "Spaced repetition", h: "#/review" });
  idx.push({ t: "Fix mistakes", c: "Questions you missed, as cards", h: "#/review/mistakes" });
  idx.push({ t: "Checkpoints", c: "Mixed quizzes across finished modules", h: "#/check" });
  idx.push({ t: "Progress & stats", c: "Your numbers", h: "#/stats" });
  idx.push({ t: "Course record", c: "What you can show for the hours", h: "#/record" });
  idx.push({ t: "Study plan", c: "Hours per week, target date", h: "#/home" });
  idx.push({ t: "Marks & questions", c: "Highlights, notes, bookmarks, chats", h: "#/marks" });
  idx.push({ t: "Settings", c: "Claude, reading preferences", h: "#/settings" });
  idx.push({ t: "Backup & restore", c: "Export your progress", act: openData });
}
function openPalette() {
  if (!idx) buildIndex();
  $("#modalhost").innerHTML = `<div class="overlay" onclick="if(event.target===this)closeModal()">
    <div class="palette"><input id="pq" type="text" placeholder="Search modules, sections, terms…" autocomplete="off">
    <div class="results" id="pr"></div></div></div>`;
  const q = $("#pq");
  q.addEventListener("input", () => { pi = 0; runSearch(q.value); });
  q.addEventListener("keydown", e => {
    if (e.key === "ArrowDown") { e.preventDefault(); pi = Math.min(pres.length - 1, pi + 1); paintRes(); }
    else if (e.key === "ArrowUp") { e.preventDefault(); pi = Math.max(0, pi - 1); paintRes(); }
    else if (e.key === "Enter") { e.preventDefault(); if (pres[pi]) pickRes(pi); }
  });
  runSearch("");
  setTimeout(() => q.focus(), 30);
}
function pickRes(i) {
  const r = pres[i]; if (!r) return;
  closeModal();
  if (r.act) r.act(); else go(r.h);
}
function runSearch(v) {
  const s = v.trim().toLowerCase();
  if (!s) pres = idx.slice(0, 8);
  else {
    pres = idx.map(x => {
      const t = x.t.toLowerCase(), c = (x.c || "").toLowerCase(), b = (x.body || "").toLowerCase();
      let sc = 0;
      if (t.startsWith(s)) sc = 100; else if (t.includes(s)) sc = 70;
      else if (c.includes(s)) sc = 40; else if (b.includes(s)) sc = 20;
      return sc ? { x, sc } : null;
    }).filter(Boolean).sort((a, b) => b.sc - a.sc).slice(0, 30).map(o => o.x);
  }
  paintRes();
}
function paintRes() {
  $("#pr").innerHTML = pres.length ? pres.map((r, i) =>
    `<button class="res ${i === pi ? "on" : ""}" onclick="pickRes(${i})"><div class="t">${esc(r.t)}</div><div class="c">${esc(r.c || "")}</div></button>`).join("")
    : `<div style="padding:22px;text-align:center;color:var(--muted);font-size:13.5px">Nothing found</div>`;
}
function openHelp() {
  showModal(`<h3 style="font-family:var(--serif);font-size:22px;margin:0 0 14px;font-weight:600">Keyboard shortcuts</h3>
  <div style="display:grid;gap:9px;font-size:14px">
    ${[["select", "Select text to highlight it or ask about it"], ["a", "Show / hide the chat rail"], ["s", "Show / hide the sidebar"], ["i", "Jump to the chat box"], ["/", "Search everything"], ["j / k", "Next / previous module"], ["a–h / 1–8", "Pick an option in a quiz"], ["1–3", "Rate confidence, then continue"], ["1–4", "Grade a flashcard"], ["space", "Flip a flashcard"], ["Enter", "Lock in an answer / continue"], ["⌘/Ctrl+↵", "Send a chat message"], ["t", "Cycle theme"], ["?", "This panel"], ["Esc", "Close"]]
      .map(([k, d]) => `<div style="display:flex;gap:12px"><kbd style="min-width:52px;text-align:center">${k}</kbd><span style="color:var(--text-2)">${d}</span></div>`).join("")}
  </div>
  <div class="hint" style="margin-top:18px"><span class="i">Note</span> Progress is stored in this browser. Use Backup &amp; restore in the sidebar to move it or keep a copy.</div>`);
}
