/* ---- notes on a highlight ---- */
function openNote(mid, id) {
  const m = findMark(mid, id); if (!m) return;
  const mod = byId(mid), sec = mod.sections[m.sec];
  showModal(`<h3 style="font-family:var(--serif);font-size:20px;margin:0 0 4px;font-weight:600">Note</h3>
    <p class="eyebrow" style="margin-bottom:10px">${mod.id} · ${esc(sec ? sec.h : "")}</p>
    <div class="quote" style="margin-bottom:14px">${esc(m.text)}</div>
    <textarea id="notein" rows="4" placeholder="What do you want to remember about this?">${esc(m.note || "")}</textarea>
    <div style="display:flex;gap:9px;margin-top:14px;flex-wrap:wrap">
      <button class="btn primary" onclick="saveNote2('${mid}','${id}')">Save</button>
      <button class="btn" onclick="closeModal();openPanel('${mid}','${id}')">Ask Claude about it</button>
      <button class="btn ghost" style="margin-left:auto;color:var(--bad)" onclick="delMark('${mid}','${id}')">Delete</button>
    </div>`);
  setTimeout(() => { const t = document.getElementById("notein"); if (t) t.focus(); }, 40);
}
function saveNote2(mid, id) {
  const m = findMark(mid, id); if (!m) return;
  m.note = (document.getElementById("notein") || {}).value || "";
  save(); closeModal();
  if (route.v === "m") renderStep(byId(mid), 1); else render();
  toast("Saved");
}

/* ---- marks view: highlights, notes, and every conversation ---- */
let markFilter = "all";
function viewMarks() {
  const all = allMarks(), chats = allConvos().filter(c => c.msgs.length || c.summary);
  const qCount = chats.reduce((a, c) => a + c.msgs.filter(x => x.r === "u").length, 0);
  const f = markFilter;
  let h = `<div class="wrap-wide"><h2 class="big">Marks &amp; questions</h2>
  <p class="sub" style="margin-bottom:18px">Everything you highlighted, noted, or asked about — in one place.</p>
  <div class="chips" style="margin-bottom:18px">
    ${[["all", "All"], ["chats", "Conversations " + qCount], ["hl", "Highlights " + all.filter(m => !m.note).length], ["notes", "Notes " + all.filter(m => m.note).length]]
      .map(([k, l]) => `<button class="chip ${f === k ? "on" : ""}" onclick="markFilter='${k}';viewMarks()">${l}</button>`).join("")}
  </div>`;

  if (!all.length && !chats.length) {
    h += `<div class="empty"><div class="big">Nothing marked yet</div>
      <p style="max-width:540px;margin:0 auto">Open any module. The chat sits on the right and follows you down the page, suggesting questions for whatever section you are reading. Select a sentence to ask about that exact passage, or highlight it to keep.</p>
      <button class="btn primary" style="margin-top:14px" onclick="go('#/m/${MODS[0].id}/1')">Open Module 01</button></div></div>`;
    return void ($("#view").innerHTML = h);
  }

  if (f === "all" || f === "chats") {
    chats.forEach(c => {
      const mod = byId(c.mid);
      const asked = c.msgs.filter(x => x.r === "u").length;
      h += `<div class="markrow qq">
        <div class="meta"><span class="tag acc">${mod.id}</span><span>${esc(mod.short)}</span>
          <span class="tag">${asked} question${asked === 1 ? "" : "s"}</span>
          ${c.parent ? `<span class="tag warn">carried over</span>` : ""}
          <span style="margin-left:auto">${new Date(c.updated).toLocaleDateString()}</span></div>
        <div style="font-size:15px;font-weight:600;margin-bottom:8px">${esc(convoTitle(c))}</div>
        ${c.summary ? `<div class="qbox"><b>Carried over</b>${esc(c.summary.slice(0, 320))}${c.summary.length > 320 ? "…" : ""}</div>` : ""}
        ${c.msgs.slice(-2).map(x => `<div class="qbox"><b>${x.r === "u" ? "I asked" : x.r === "e" ? "Error" : "Claude"}</b>${esc(x.t.length > 360 ? x.t.slice(0, 360) + "…" : x.t)}</div>`).join("")}
        <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:4px">
          <button class="btn sm primary" onclick="continueConvo('${c.id}')">Continue this chat →</button>
          ${c.msgs.length ? `<button class="btn sm" onclick="compactFromList('${c.id}')">⤳ Compact into a new chat</button>` : ""}
          <button class="btn sm ghost" onclick="exportChat('${c.id}')">Copy transcript</button>
          <button class="btn sm ghost" onclick="renameConvo('${c.id}')">Rename</button>
          <button class="btn sm ghost" style="color:var(--bad)" onclick="deleteConvo('${c.id}')">Delete</button>
        </div></div>`;
    });
  }
  if (f === "all" || f === "hl" || f === "notes") {
    const list = all.filter(m => f === "notes" ? m.note : f === "hl" ? !m.note : true);
    list.forEach(m => {
      const mod = byId(m.mid), sec = mod.sections[m.sec];
      h += `<div class="markrow ${m.note ? "done" : ""}">
        <div class="meta"><span class="tag acc">${mod.id}</span><span>${esc(sec ? sec.h : "")}</span>
          <span class="tag ${m.note ? "ok" : ""}">${m.note ? "note" : "highlight"}</span>
          <span style="margin-left:auto">${new Date(m.ts).toLocaleDateString()}</span></div>
        <div class="txt">${esc(m.text.length > 400 ? m.text.slice(0, 400) + "…" : m.text)}</div>
        ${m.note ? `<div class="qbox"><b>My note</b>${esc(m.note)}</div>` : ""}
        <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:4px">
          <button class="btn sm" onclick="openNote('${m.mid}','${m.id}')">${m.note ? "Edit note" : "Add a note"}</button>
          <button class="btn sm primary" onclick="openPanel('${m.mid}','${m.id}')">Ask about it</button>
          <button class="btn sm ghost" onclick="go('#/m/${m.mid}/1')">Go to passage →</button>
        </div></div>`;
    });
  }
  h += `</div>`;
  $("#view").innerHTML = h;
}
function continueConvo(id) {
  const c = CV()[id]; if (!c) return;
  ACT()[c.mid] = id; save();
  if (!S.ui) S.ui = {}; S.ui.rail = true; save();
  go("#/m/" + c.mid + "/1");
}
async function compactFromList(id) {
  const c = CV()[id]; if (!c) return;
  toast("Summarising…");
  const fresh = await compactConvo(id);
  if (fresh) continueConvo(fresh.id);
}
function exportChat(id) {
  const c = CV()[id]; if (!c) return;
  const mod = byId(c.mid);
  const head = "Marketing Mastery — " + mod.id + " " + mod.title + "\n" + convoTitle(c) + "\n";
  const carried = c.summary ? "\nCARRIED OVER FROM AN EARLIER CHAT:\n" + c.summary + "\n" : "";
  const txt = c.msgs.map(x => (x.r === "u" ? "ME: " : x.r === "e" ? "ERROR: " : "CLAUDE: ") + x.t).join("\n\n");
  toast(clip(head + carried + "\n" + txt) ? "Transcript copied" : "Could not copy");
}
function clip(text) {
  try { if (navigator.clipboard && navigator.clipboard.writeText) { navigator.clipboard.writeText(text); return true; } } catch (e) {}
  try {
    const ta = document.createElement("textarea");
    ta.value = text; ta.style.position = "fixed"; ta.style.opacity = "0";
    document.body.appendChild(ta); ta.select();
    const ok = document.execCommand("copy"); ta.remove(); return ok;
  } catch (e) { return false; }
}

