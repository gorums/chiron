/* ---- notes on a highlight ---- */
function openNote(mid, id) {
  const m = findMark(mid, id);
  if (!m) return;
  const mod = byId(mid),
    sec = mod.sections[m.sec];
  showModal(`<h3 style="font-family:var(--serif);font-size:20px;margin:0 0 4px;font-weight:600">Note</h3>
    <p class="eyebrow" style="margin-bottom:10px">${mod.id} · ${esc(sec ? sec.h : "")}</p>
    <div class="quote" style="margin-bottom:14px">${esc(m.text)}</div>
    <textarea id="notein" rows="4" placeholder="What do you want to remember about this — or what do you still not get?">${esc(m.note || "")}</textarea>
    <label style="display:flex;gap:8px;align-items:center;margin-top:10px;font-size:13.5px;cursor:pointer"><input type="checkbox" id="noteopen" ${m.status === "open" ? "checked" : ""}> This is a question I still need answered</label>
    ${m.status === "answered" ? `<p class="sub" style="margin-top:6px;font-size:12.5px">Answered — tick the box to reopen it.</p>` : ""}
    <div style="display:flex;gap:9px;margin-top:14px;flex-wrap:wrap">
      <button class="btn primary" onclick="saveNote2('${mid}','${id}')">Save</button>
      <button class="btn" onclick="saveNote2('${mid}','${id}',true)">Ask Claude about it</button>
      <button class="btn ghost" style="margin-left:auto;color:var(--bad)" onclick="delMark('${mid}','${id}')">Delete</button>
    </div>`);
  setTimeout(() => {
    const t = document.getElementById("notein");
    if (t) t.focus();
  }, 40);
}
function saveNote2(mid, id, ask) {
  const m = findMark(mid, id);
  if (!m) return;
  m.note = (document.getElementById("notein") || {}).value || "";
  const open = !!(document.getElementById("noteopen") || {}).checked;
  m.status = open ? "open" : m.status === "answered" ? "answered" : "hl";
  save();
  closeModal();
  if (route.view === "m") renderStep(byId(mid), 1);
  else render();
  toast("Saved");
  if (ask) openPanel(mid, id);
}

/* ---- marks view: highlights, notes, open questions, bookmarks, and every conversation ---- */
let markFilter = "all";
function viewMarks() {
  const all = allMarks(),
    chats = allConvos().filter(c => c.msgs.length || c.summary);
  const qCount = chats.reduce((a, c) => a + c.msgs.filter(x => x.r === "u").length, 0);
  const books = Object.keys(STATE.bookmarks || {})
    .map(k => {
      const [mid, sec] = k.split(":");
      return { mid, sec: +sec, ts: STATE.bookmarks[k] };
    })
    .filter(b => byId(b.mid))
    .sort((a, b) => b.ts - a.ts);
  const f = markFilter;
  let h = `<div class="wrap-wide"><div style="display:flex;gap:10px;align-items:flex-start;flex-wrap:wrap"><div style="flex:1"><h2 class="big">Marks &amp; questions</h2>
  <p class="sub" style="margin-bottom:18px">Everything you highlighted, noted, bookmarked, or asked about — in one place.</p></div>
  <button class="btn sm" onclick="exportNotes()">Export notes as markdown</button></div>
  <div class="chips" style="margin-bottom:18px">
    ${[
      ["all", "All"],
      ["open", "Open questions " + all.filter(m => m.status === "open").length],
      ["chats", "Conversations " + qCount],
      ["notes", "Notes " + all.filter(m => m.note).length],
      ["hl", "Highlights " + all.filter(m => !m.note && m.status !== "open").length],
      ["books", "Bookmarks " + books.length],
    ]
      .map(
        ([k, l]) =>
          `<button class="chip ${f === k ? "on" : ""}" onclick="markFilter='${k}';viewMarks()">${l}</button>`
      )
      .join("")}
  </div>`;

  if (!all.length && !chats.length && !books.length) {
    h += `<div class="empty"><div class="big">Nothing marked yet</div>
      <p style="max-width:540px;margin:0 auto">Open any module. The chat sits on the right and follows you down the page, suggesting questions for whatever section you are reading. Select a sentence to ask about that exact passage, highlight it to keep, or flag it as a question you still need answered.</p>
      <button class="btn primary" style="margin-top:14px" onclick="go('#/m/${MODS[0].id}/1')">Open Module 01</button></div></div>`;
    return void ($("#view").innerHTML = h);
  }

  if (f === "all" || f === "open") {
    all.filter(m => m.status === "open").forEach(m => (h += markRow(m)));
  }
  if (f === "books" || f === "all") {
    books.forEach(b => {
      const mod = byId(b.mid),
        sec = mod.sections[b.sec];
      h += `<div class="markrow book"><div class="meta"><span class="tag acc">${mod.id}</span><span>${esc(mod.short)}</span><span class="tag">bookmark</span><span style="margin-left:auto">${new Date(b.ts).toLocaleDateString()}</span></div>
        <div style="font-size:15px;font-weight:600;margin-bottom:8px">⚑ ${esc(sec ? sec.h : "")}</div>
        <div style="display:flex;gap:8px;flex-wrap:wrap"><button class="btn sm primary" onclick="jumpToPassage('${mod.id}',${b.sec},null)">Go to section</button><button class="btn sm ghost" onclick="toggleBookmark('${mod.id}',${b.sec});viewMarks()">Remove</button></div></div>`;
    });
  }
  if (f === "all" || f === "chats") {
    chats.forEach(c => {
      const mod = byId(c.mid);
      const asked = c.msgs.filter(x => x.r === "u").length;
      h += `<div class="markrow qq">
        <div class="meta"><span class="tag acc">${mod.id}</span><span>${esc(mod.short)}</span>
          <span class="tag">${c.kind === "rp" ? "role-play · " : ""}${asked} turn${asked === 1 ? "" : "s"}</span>
          ${c.parent ? `<span class="tag warn">carried over</span>` : ""}
          <span style="margin-left:auto">${new Date(c.updated).toLocaleDateString()}</span></div>
        <div style="font-size:15px;font-weight:600;margin-bottom:8px">${esc(convoTitle(c))}</div>
        ${c.summary ? `<div class="qbox"><b>Carried over</b>${esc(c.summary.slice(0, 320))}${c.summary.length > 320 ? "…" : ""}</div>` : ""}
        ${c.msgs
          .slice(-2)
          .map(
            x =>
              `<div class="qbox"><b>${x.r === "u" ? (c.kind === "rp" ? "I said" : "I asked") : x.r === "e" ? "Error" : c.kind === "rp" ? "Other side" : "Claude"}</b>${esc(x.t.length > 360 ? x.t.slice(0, 360) + "…" : x.t)}</div>`
          )
          .join("")}
        <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:4px">
          <button class="btn sm primary" onclick="continueConvo('${c.id}')">Continue this chat</button>
          ${c.msgs.length && c.kind !== "rp" ? `<button class="btn sm" onclick="compactFromList('${c.id}')">⤳ Compact into a new chat</button>` : ""}
          <button class="btn sm ghost" onclick="exportChat('${c.id}')">Copy transcript</button>
          <button class="btn sm ghost" onclick="renameConvo('${c.id}')">Rename</button>
          <button class="btn sm ghost" style="color:var(--bad)" onclick="deleteConvo('${c.id}')">Delete</button>
        </div></div>`;
    });
  }
  if (f === "all" || f === "hl" || f === "notes") {
    const list = all.filter(m =>
      f === "notes" ? m.note : f === "hl" ? !m.note && m.status !== "open" : m.status !== "open"
    );
    list.forEach(m => (h += markRow(m)));
  }
  h += `</div>`;
  $("#view").innerHTML = h;
}
function markRow(m) {
  const mod = byId(m.mid),
    sec = mod.sections[m.sec];
  const kind =
    m.status === "open"
      ? "open question"
      : m.status === "answered"
        ? "answered"
        : m.note
          ? "note"
          : "highlight";
  return `<div class="markrow ${m.status === "open" ? "qq" : m.note || m.status === "answered" ? "done" : ""}">
    <div class="meta"><span class="tag acc">${mod.id}</span><span>${esc(sec ? sec.h : "")}</span>
      <span class="tag ${m.status === "open" ? "warn" : m.status === "answered" || m.note ? "ok" : ""}">${kind}</span>
      <span style="margin-left:auto">${new Date(m.ts).toLocaleDateString()}</span></div>
    <div class="txt">${esc(m.text.length > 400 ? m.text.slice(0, 400) + "…" : m.text)}</div>
    ${m.note ? `<div class="qbox"><b>${m.status === "open" ? "My question" : "My note"}</b>${esc(m.note)}</div>` : ""}
    <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:4px">
      <button class="btn sm" onclick="openNote('${m.mid}','${m.id}')">${m.note ? "Edit note" : "Add a note"}</button>
      <button class="btn sm primary" onclick="openPanel('${m.mid}','${m.id}')">Ask about it</button>
      ${m.status === "open" ? `<button class="btn sm" onclick="setMarkStatus('${m.mid}','${m.id}','answered');viewMarks()">✓ Answered</button>` : ""}
      <button class="btn sm ghost" onclick="go('#/m/${m.mid}/1')">Go to passage</button>
    </div></div>`;
}
function continueConvo(id) {
  switchConvo(id);
}
async function compactFromList(id) {
  const c = convos()[id];
  if (!c) return;
  toast("Summarising…");
  const fresh = await compactConvo(id);
  if (fresh) continueConvo(fresh.id);
}
function exportChat(id) {
  const c = convos()[id];
  if (!c) return;
  const mod = byId(c.mid);
  const head = CFG.title + " — " + mod.id + " " + mod.title + "\n" + convoTitle(c) + "\n";
  const carried = c.summary ? "\nCARRIED OVER FROM AN EARLIER CHAT:\n" + c.summary + "\n" : "";
  const txt = c.msgs
    .map(x => (x.r === "u" ? "ME: " : x.r === "e" ? "ERROR: " : "CLAUDE: ") + x.t)
    .join("\n\n");
  toast(clip(head + carried + "\n" + txt) ? "Transcript copied" : "Could not copy");
}
/* every note, highlight and from-memory summary, module by module, as markdown */
function exportNotes() {
  const lines = ["# " + CFG.title + " — notes", ""];
  MODS.forEach(m => {
    const marks = marksOf(m.id),
      memo = (STATE.notes[m.id] || "").trim(),
      p = progressOf(m.id);
    const books = m.sections
      .map((s, i) => (STATE.bookmarks[m.id + ":" + i] ? s.h : null))
      .filter(Boolean);
    const elab = Object.keys(p.elab || {}).filter(k => (p.elab[k] || "").trim());
    if (!marks.length && !memo && !books.length && !elab.length) return;
    lines.push("## " + m.id + " — " + m.title, "");
    if (memo) lines.push("**From memory:** " + memo, "");
    books.forEach(b => lines.push("- ⚑ " + b));
    marks.forEach(k => {
      const sec = m.sections[k.sec];
      lines.push("> " + k.text.replace(/\n/g, " "));
      lines.push("> — " + (sec ? sec.h : "") + (k.status === "open" ? " · OPEN QUESTION" : ""));
      if (k.note) lines.push("", k.note);
      lines.push("");
    });
    elab.forEach(k =>
      lines.push("**" + (m.assess.elaborate[k] || "Elaborate") + "**", "", p.elab[k], "")
    );
  });
  if (lines.length <= 2) {
    toast("Nothing to export yet");
    return;
  }
  toast(clip(lines.join("\n")) ? "Notes copied as markdown" : "Could not copy");
}
function clip(text) {
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text);
      return true;
    }
  } catch (e) {}
  try {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    const ok = document.execCommand("copy");
    ta.remove();
    return ok;
  } catch (e) {
    return false;
  }
}
