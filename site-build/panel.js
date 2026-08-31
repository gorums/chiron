/* ---- ask panel: a real conversation, in the page ---- */
function closePanel() { const p = document.getElementById("panel"); if (p) p.remove(); }
function threadOf(m) {
  if (!m.thread) {
    m.thread = [];
    if (m.q) m.thread.push({ r: "u", t: m.q, ts: m.ts });
    if (m.ans) m.thread.push({ r: "a", t: m.ans, ts: m.ts });
  }
  return m.thread;
}
function statusOf(m) {
  const th = threadOf(m);
  if (th.some(x => x.r === "a")) return "answered";
  if (th.length) return "open";
  return m.q && m.q.trim() ? "open" : "hl";
}
function systemFor(mid, id) {
  const m = findMark(mid, id), mod = byId(mid), sec = mod.sections[m.sec];
  return `You are a sharp, plain-spoken marketing tutor. The person you are helping is a complete beginner working through a 30-hour marketing course, and is currently reading module ${mod.id}, "${mod.title}", section "${sec ? sec.h : ""}".

They marked this passage and want to talk about it:
"""
${m.text}
"""
${S.biz ? `\nTheir practice business, which every example should be aimed at: ${S.biz}` : ""}
${m.note && m.note.trim() ? `\nTheir own note on the passage: ${m.note.trim()}` : ""}

How to answer:
- Be concise. Three short paragraphs is usually plenty; use a short list when it genuinely helps.
- Be concrete. Real numbers, real examples, real first steps beat abstractions.
- Tie it back to the passage they marked.
- If the passage is a simplification, or if you disagree with it, say so and explain where it breaks down.
- Do not flatter them or pad with preamble. Answer the question.`;
}
function openPanel(mid, id, mode) {
  const m = findMark(mid, id); if (!m) return;
  currentPanelMid = mid; currentPanelId = id;
  closePanel();
  const mod = byId(mid), sec = mod.sections[m.sec];
  const host = document.createElement("div");
  host.innerHTML = `<div class="panel" id="panel">
    <header>
      <span class="dotstat ${bridgeOk ? "on" : ""}" id="pdot" title="${bridgeOk ? "Connected to Claude" : "Not connected"}"></span>
      <h3>Ask Claude</h3>
      <button class="iconbtn" title="Settings" onclick="closePanel();go('#/settings')">⚙</button>
      <button class="iconbtn" onclick="closePanel()">✕</button>
    </header>
    <div class="body" id="pbody"></div>
    <div class="chatfoot">
      <div class="row">
        <textarea id="chatin" rows="2" placeholder="Ask anything about this passage…" style="flex:1"></textarea>
        <button class="btn primary" id="sendbtn" onclick="sendMsg()">Send</button>
      </div>
      <div style="display:flex;gap:7px;flex-wrap:wrap;align-items:center">
        <span style="font-size:11.5px;color:var(--muted)">⌘/Ctrl+↵ to send</span>
        <button class="btn sm ghost" onclick="copyQ('${mid}','${id}')">Copy question</button>
        <button class="btn sm ghost" style="margin-left:auto;color:var(--bad)" onclick="delMark('${mid}','${id}')">Delete mark</button>
      </div>
    </div></div>`;
  document.body.appendChild(host.firstElementChild);
  drawThread();
  const ci = document.getElementById("chatin");
  ci.addEventListener("keydown", e => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); sendMsg(); }
  });
  if (mode === "note") { const n = document.getElementById("mnote"); if (n) return n.focus(); }
  ci.focus();
  if (bridgeOk === null) checkBridge(true);
}
function drawThread() {
  const body = document.getElementById("pbody");
  if (!body || !currentPanelId) return;
  const m = findMark(currentPanelMid, currentPanelId); if (!m) return;
  const mod = byId(currentPanelMid), sec = mod.sections[m.sec];
  const th = threadOf(m);
  let h = `<p class="eyebrow">${mod.id} · ${esc(sec ? sec.h : "")}</p>
    <div class="quote">${esc(m.text)}</div>
    <div style="margin:14px 0 4px"><textarea id="mnote" rows="1" placeholder="Your own note on this passage (optional)"
      onchange="saveNoteField()" style="font-size:13px">${esc(m.note || "")}</textarea></div>`;
  if (!bridgeOk) {
    h += `<div class="warnbar"><span>${bridgeChecking ? "Checking for the bridge…" : "Not connected to Claude — answers cannot come back into this page yet."}</span>
      <button class="btn sm" onclick="closePanel();go('#/settings')">Set it up</button>
      <button class="btn sm ghost" onclick="checkBridge()">Retry</button></div>`;
  } else if (BR().echo) {
    h += `<div class="warnbar"><span>Bridge is in ECHO test mode — it repeats your message instead of calling Claude.</span></div>`;
  }
  h += `<div class="thread" id="thread">`;
  if (!th.length) {
    h += `<p class="sub" style="margin-bottom:12px">Ask anything about this passage, or start from one of these:</p>
      <div class="chips">${PRESETS.map((p, i) => `<button class="chip" onclick="usePreset(${i})">${esc(p[0])}</button>`).join("")}</div>`;
  }
  th.forEach((x, i) => {
    h += `<div class="msg ${x.r === "u" ? "u" : x.r === "e" ? "a err" : "a"}">${x.r === "u" ? esc(x.t) : mdLite(x.t)}</div>`;
  });
  h += `</div><div id="pending"></div>`;
  body.innerHTML = h;
  body.scrollTop = body.scrollHeight;
  const d = document.getElementById("pdot");
  if (d) { d.className = "dotstat " + (bridgeChecking ? "busy" : bridgeOk ? "on" : ""); }
}
function saveNoteField() {
  const m = findMark(currentPanelMid, currentPanelId); if (!m) return;
  const n = document.getElementById("mnote");
  if (n) { m.note = n.value; m.status = statusOf(m); save(); }
}
function usePreset(i) {
  const ta = document.getElementById("chatin");
  ta.value = (ta.value.trim() ? ta.value.trim() + " " : "") + PRESETS[i][1];
  ta.focus();
}
async function sendMsg() {
  const m = findMark(currentPanelMid, currentPanelId); if (!m) return;
  const ta = document.getElementById("chatin"), btn = document.getElementById("sendbtn");
  const text = (ta.value || "").trim();
  if (!text) return;
  saveNoteField();
  if (!bridgeOk) {
    const ok = await checkBridge(true);
    if (!ok) { drawThread(); toast("Not connected — open Settings to set up the bridge"); return; }
  }
  const th = threadOf(m);
  th.push({ r: "u", t: text, ts: Date.now() });
  m.q = m.q || text;
  m.status = "open"; save();
  ta.value = ""; drawThread(); renderSidebar();
  btn.disabled = true; ta.disabled = true;
  const pend = document.getElementById("pending");
  if (pend) pend.innerHTML = `<div class="msg a typing"><i></i><i></i><i></i></div>`;
  const body = document.getElementById("pbody"); if (body) body.scrollTop = body.scrollHeight;
  try {
    const msgs = th.filter(x => x.r !== "e").map(x => ({ role: x.r === "u" ? "user" : "assistant", content: x.t }));
    const reply = await askBridge(systemFor(currentPanelMid, currentPanelId), msgs);
    th.push({ r: "a", t: reply, ts: Date.now() });
    m.ans = reply;
  } catch (e) {
    th.push({ r: "e", t: (e && e.message) || "Something went wrong.", ts: Date.now() });
  }
  m.status = statusOf(m); save();
  btn.disabled = false; ta.disabled = false;
  drawThread(); renderSidebar();
  const ci = document.getElementById("chatin"); if (ci) ci.focus();
}
function buildPrompt(mid, id) {
  const m = findMark(mid, id), mod = byId(mid), sec = mod.sections[m.sec];
  const ci = document.getElementById("chatin");
  const q = (ci && ci.value.trim()) || m.q || "Explain this passage in more depth.";
  return `I'm working through my Marketing Mastery course — module ${mod.id}, "${mod.title}", section "${sec ? sec.h : ""}".

Passage I marked:
"""
${m.text}
"""

My question: ${q}
${m.note && m.note.trim() ? "\nMy note on it: " + m.note.trim() + "\n" : ""}
Context: I'm learning marketing from scratch${S.biz ? ` and my practice business is: ${S.biz}` : ""}. Answer concretely, keep it tight, and tie it back to the passage. If the passage is oversimplified, say so.`;
}
function clip(text) {
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) { navigator.clipboard.writeText(text); return true; }
  } catch (e) {}
  try {
    const ta = document.createElement("textarea");
    ta.value = text; ta.style.position = "fixed"; ta.style.opacity = "0";
    document.body.appendChild(ta); ta.select();
    const ok = document.execCommand("copy"); ta.remove(); return ok;
  } catch (e) { return false; }
}
function copyQ(mid, id) {
  const m = findMark(mid, id);
  const p = buildPrompt(mid, id);
  const ci = document.getElementById("chatin");
  if (ci && ci.value.trim() && !m.q) m.q = ci.value.trim();
  m.status = statusOf(m); save(); renderSidebar();
  toast(clip(p) ? "Question copied" : "Could not copy — select the text manually");
}
function savePanel(mid, id) { saveNoteField(); toast("Saved"); }

