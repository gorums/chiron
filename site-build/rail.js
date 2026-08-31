/* ---- the chat rail: always there, always about what you are looking at ---- */

/* ---------- conversations ---------- */
function CV() { if (!S.convos) S.convos = {}; return S.convos; }
function ACT() { if (!S.active) S.active = {}; return S.active; }
function migrateChats() {
  if (!S.chats || S._migrated) return;
  Object.keys(S.chats).forEach(mid => {
    const msgs = S.chats[mid] || [];
    if (!msgs.length) return;
    const id = newId();
    CV()[id] = { id, mid, msgs, created: msgs[0].ts || Date.now(),
                 updated: msgs[msgs.length - 1].ts || Date.now(), parent: null, summary: "", title: "" };
    ACT()[mid] = id;
  });
  S._migrated = true; save();
}
function newId() { return "c" + Date.now().toString(36) + Math.floor(Math.random() * 1e4).toString(36); }
function convosFor(mid) {
  return Object.values(CV()).filter(c => c.mid === mid).sort((a, b) => b.updated - a.updated);
}
function allConvos() { return Object.values(CV()).sort((a, b) => b.updated - a.updated); }
function convoTitle(c) {
  if (c.title) return c.title;
  const first = (c.msgs || []).find(m => m.r === "u");
  if (first) return first.t.length > 46 ? first.t.slice(0, 46) + "…" : first.t;
  return c.summary ? "Continued conversation" : "New chat";
}
function activeConvo(mid, create) {
  const id = ACT()[mid];
  if (id && CV()[id]) return CV()[id];
  const existing = convosFor(mid)[0];
  if (existing) { ACT()[mid] = existing.id; return existing; }
  if (create === false) return null;
  return newConvo(mid);
}
function newConvo(mid, opts) {
  const id = newId();
  CV()[id] = { id, mid, msgs: [], created: Date.now(), updated: Date.now(),
               parent: (opts && opts.parent) || null, summary: (opts && opts.summary) || "",
               title: (opts && opts.title) || "" };
  ACT()[mid] = id; save();
  return CV()[id];
}
function switchConvo(id) {
  const c = CV()[id]; if (!c) return;
  ACT()[c.mid] = id; save(); menuOpen = false; renderRail();
}
function deleteConvo(id) {
  const c = CV()[id]; if (!c) return;
  if (!confirm("Delete this conversation? It cannot be undone.")) return;
  const mid = c.mid;
  delete CV()[id];
  if (ACT()[mid] === id) delete ACT()[mid];
  save(); menuOpen = false;
  if (route.v === "m") renderRail(); else render();
  toast("Conversation deleted");
}
function renameConvo(id) {
  const c = CV()[id]; if (!c) return;
  const t = prompt("Name this conversation:", convoTitle(c));
  if (t === null) return;
  c.title = t.trim().slice(0, 70); save();
  if (route.v === "m") renderRail(); else render();
}

/* compaction: carry the substance forward into a fresh conversation */
let compacting = false;
async function compactConvo(id) {
  const c = CV()[id] || activeConvo(route.id, false);
  if (!c || !c.msgs.length || compacting) return;
  if (connMode() === "none") { toast("Not connected — open Settings"); return; }
  compacting = true; menuOpen = false; renderRail();
  try {
    const transcript = c.msgs.filter(m => m.r !== "e")
      .map(m => (m.r === "u" ? "LEARNER: " : "TUTOR: ") + m.t).join("\n\n");
    const sys = "You compress a tutoring conversation into a handover brief for the next conversation, written for the tutor who picks it up. Under 180 words. Cover: what was actually settled, the learner's situation and business as revealed, any conclusion or decision reached, and what is still open or confusing. No preamble, no headings, plain prose. Do not repeat explanations — record outcomes.";
    const summary = await askBridge(sys, [{ role: "user", content: transcript.slice(-12000) }]);
    const fresh = newConvo(c.mid, { parent: c.id, summary: summary.trim(),
                                    title: "Continued: " + convoTitle(c).slice(0, 40) });
    compacting = false; renderRail();
    toast("Carried the important parts into a new chat");
    return fresh;
  } catch (e) {
    compacting = false; renderRail();
    toast((e && e.message) || "Could not compact this conversation");
  }
}

/* ---------- rail state ---------- */
let curSec = 0, pinned = null, pinnedQs = null, genning = false, menuOpen = false;

function railOpen() { if (!S.ui) S.ui = { rail: true }; return S.ui.rail !== false; }
function toggleRail() {
  if (!S.ui) S.ui = {};
  S.ui.rail = !railOpen(); save();
  applyRail(); if (railOpen()) renderRail();
}
function applyRail() {
  const show = route.v === "m" && railOpen();
  document.body.classList.toggle("rail-on", show);
  const el = document.getElementById("rail");
  if (el) { el.classList.toggle("hidden", route.v !== "m"); el.classList.toggle("shut", !railOpen()); }
  const t = document.getElementById("railtoggle");
  if (t) t.classList.toggle("hidden", route.v !== "m");
}

/* ---- questions built from the passage itself, instantly and for free ---- */
function termsIn(text) {
  const low = " " + text.toLowerCase().replace(/[^a-z0-9%$€£. ]+/g, " ") + " ";
  const hits = [];
  (DATA.library.glossary || []).forEach(g => {
    const t = g.term.toLowerCase().replace(/\s*\(.*?\)\s*/g, " ").trim();
    if (t.length < 4 || t.length > 34) return;
    if (low.indexOf(" " + t + " ") >= 0 || low.indexOf(" " + t + "s ") >= 0)
      hits.push({ t: g.term.replace(/\s*\(.*?\)\s*/g, "").trim(), star: g.star, len: t.length });
  });
  hits.sort((a, b) => (b.star - a.star) || (b.len - a.len));
  const out = [];
  hits.forEach(h => { if (!out.some(o => o.toLowerCase().includes(h.t.toLowerCase()) || h.t.toLowerCase().includes(o.toLowerCase()))) out.push(h.t); });
  return out.slice(0, 3);
}
function localQuestions(text, hints) {
  const seen = [];
  (hints || []).forEach(hStr => {
    const h = String(hStr).replace(/[.,;:]$/, "").trim();
    if (h.length >= 4 && h.length <= 44 && !seen.some(x => x.toLowerCase() === h.toLowerCase())) seen.push(h);
  });
  termsIn(text).forEach(t => { if (!seen.some(x => x.toLowerCase().includes(t.toLowerCase()))) seen.push(t); });
  const terms = seen.slice(0, 3);
  const num = (text.match(/\b\d+(\.\d+)?\s?(%|x\b|:1\b)|[$€£]\s?\d[\d,.]*/) || [])[0];
  const qs = [];
  qs.push(terms[0] ? `What does "${terms[0]}" actually mean here?` : "Say this back to me in plain language.");
  if (terms[1]) qs.push(`How is ${terms[1]} different from ${terms[0]}?`);
  else qs.push("Give me a concrete example of this.");
  if (num) qs.push(`Where does the ${num} come from?`);
  qs.push(`How would I apply this to ${S.biz || "my own business"}?`);
  qs.push("When does this stop being true?");
  return qs.slice(0, 5);
}
async function genQuestions() {
  if (!pinned || genning) return;
  if (connMode() === "none") { toast("Not connected — open Settings"); return; }
  genning = true; renderSuggest();
  try {
    const sys = "You write study questions. Given a passage from a marketing course, return the 5 questions a smart beginner should be asking about it. One per line, no numbering, no preamble, each under 90 characters, each answerable from thinking about this passage. Make them specific to this passage's actual content, not generic.";
    const reply = await askBridge(sys, [{ role: "user", content: pinned.text + (S.biz ? "\n\n(The reader's practice business: " + S.biz + ")" : "") }]);
    const lines = reply.split("\n").map(l => l.replace(/^\s*[-*\d.)]+\s*/, "").trim())
      .filter(l => l.length > 12 && l.length < 140 && l.indexOf("?") > 0).slice(0, 6);
    if (lines.length) { pinnedQs = lines; toast("Questions generated"); }
    else toast("Could not read the reply — keeping the current suggestions");
  } catch (e) { toast((e && e.message) || "Could not generate questions"); }
  genning = false; renderSuggest();
}

/* ---- a hover button on every paragraph, list, quote and table ---- */
function attachParaButtons(mid) {
  const blocks = document.querySelectorAll(".sec .prose > p, .sec .prose > ul, .sec .prose > ol, .sec .prose > blockquote, .sec .prose > table, .sec .prose > pre");
  blocks.forEach(el => {
    if (el.dataset.pb) return;
    const txt = (el.innerText || el.textContent || "").trim();
    if (txt.length < 40) return;
    el.dataset.pb = "1";
    el.classList.add("askable");
    const sec = el.closest(".sec");
    const i = sec ? +sec.id.replace("sec", "") : 0;
    const b = document.createElement("button");
    b.className = "parask"; b.type = "button";
    b.title = "Ask Claude about this paragraph"; b.textContent = "?";
    b.addEventListener("click", ev => {
      ev.stopPropagation();
      const hints = [...el.querySelectorAll("strong,b,code,em")].map(n => n.textContent.trim()).slice(0, 4);
      pinQuote(txt.length > 1500 ? txt.slice(0, 1500) + "…" : txt, i, hints);
      document.querySelectorAll(".prose .picked").forEach(n => n.classList.remove("picked"));
      el.classList.add("picked");
    });
    el.appendChild(b);
  });
}

/* ---------- context ---------- */
function setCurSec(i) {
  if (i === curSec) return;
  curSec = i;
  if (route.v === "m" && railOpen() && !pinned) { renderRailHead(); renderSuggest(); }
}
function pinQuote(text, sec, hints) {
  pinned = { text: text, sec: sec };
  pinnedQs = localQuestions(text, hints);
  if (!railOpen()) { S.ui = S.ui || {}; S.ui.rail = true; save(); applyRail(); }
  renderRail();
  const inp = document.getElementById("railin"); if (inp) inp.focus();
}
function unpin() {
  pinned = null; pinnedQs = null;
  document.querySelectorAll(".prose .picked").forEach(n => n.classList.remove("picked"));
  renderRail();
}
function railCtxLabel() {
  const m = byId(route.id); if (!m) return "";
  if (pinned) return "your selection";
  const s = m.sections[curSec];
  return s ? s.h : m.title;
}
function railSuggestions() {
  if (pinned) return pinnedQs || localQuestions(pinned.text);
  const m = byId(route.id); if (!m) return [];
  const set = (m.suggest && m.suggest[curSec]) || [];
  const extra = S.biz ? ["How does this apply to " + S.biz + "?"] : ["How would I apply this to my own business?"];
  return set.concat(extra);
}
function systemForRail() {
  const m = byId(route.id);
  const sec = m.sections[pinned ? pinned.sec : curSec];
  const quote = pinned ? pinned.text : (sec ? sec.text.slice(0, 1200) : "");
  const c = activeConvo(m.id);
  return `You are a sharp, plain-spoken marketing tutor. The person is a complete beginner working through a 30-hour marketing course. Right now they are in module ${m.id}, "${m.title}", reading the section "${sec ? sec.h : ""}".

${pinned ? "They selected this passage and are asking about it:" : "The part of the text they are looking at:"}
"""
${quote}
"""
${S.biz ? `\nTheir practice business, which examples should be aimed at: ${S.biz}` : ""}
${c && c.summary ? `\nWhat happened in your earlier conversation with them, carried over. Do not repeat it; build on it:\n"""\n${c.summary}\n"""` : ""}

How to answer:
- Be concise. Two or three short paragraphs is plenty; a short list only when it genuinely helps.
- Be concrete: real numbers, real examples, a real first step.
- Tie it back to what they are reading.
- If the course text is a simplification, or you disagree with it, say so and explain where it breaks down.
- No preamble, no flattery. Answer the question.`;
}

/* ---------- render ---------- */
function renderRail() {
  const el = document.getElementById("rail");
  if (!el || route.v !== "m") return;
  const m = byId(route.id); if (!m) return;
  const c = activeConvo(m.id);
  el.innerHTML = `
    <div class="railhead" id="railhead"></div>
    <div class="railbody" id="railbody"></div>
    <div class="chatmenu hidden" id="chatmenu"></div>
    <div class="railfoot">
      <div class="row">
        <textarea id="railin" rows="1" placeholder="Ask about this section…"></textarea>
        <button class="btn primary" id="railsend" onclick="railSend()">↑</button>
      </div>
      <div style="display:flex;gap:8px;align-items:center;margin-top:7px">
        <span style="font-size:11px;color:var(--muted)">${connMode() === "none" ? "not connected" : "⌘/Ctrl+↵ to send"}</span>
        ${c.msgs.length ? `<button class="btn sm ghost" style="margin-left:auto;font-size:11.5px" onclick="compactConvo('${c.id}')" title="Summarise this chat and continue in a fresh one">⤳ Compact</button>` : ""}
      </div>
    </div>`;
  renderRailHead(); renderRailBody();
  const inp = document.getElementById("railin");
  inp.addEventListener("keydown", e => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey || !e.shiftKey)) { e.preventDefault(); railSend(); }
  });
  inp.addEventListener("input", () => { inp.style.height = "auto"; inp.style.height = Math.min(120, inp.scrollHeight) + "px"; });
}
function renderRailHead() {
  const h = document.getElementById("railhead"); if (!h) return;
  const m = byId(route.id); if (!m) return;
  const c = activeConvo(m.id);
  const n = convosFor(m.id).length;
  h.innerHTML = `
    <div class="railtop">
      <span class="dotstat ${connMode() !== "none" ? "on" : ""}" title="${connMode() !== "none" ? "Connected" : "Not connected"}"></span>
      <button class="convobtn" onclick="toggleChatMenu()" title="Your conversations">
        <span class="ct">${esc(convoTitle(c))}</span><span class="cv">▾</span>
      </button>
      <button class="iconbtn" style="width:28px;height:28px" title="New chat" onclick="startNew()">＋</button>
      <button class="iconbtn" style="width:28px;height:28px" title="Hide (a)" onclick="toggleRail()">→</button>
    </div>
    <div class="railctx">
      ${pinned
        ? `<div class="pinned"><span class="tag acc">selection</span>
             <button class="iconbtn" style="width:22px;height:22px;font-size:12px" title="Unpin" onclick="unpin()">✕</button>
             <div class="ptext">${esc(pinned.text.length > 220 ? pinned.text.slice(0, 220) + "…" : pinned.text)}</div></div>`
        : `<div class="ctxline">Reading · <b>${esc(railCtxLabel())}</b>${n > 1 ? ` · ${n} chats here` : ""}</div>`}
    </div>`;
}
function toggleChatMenu() { menuOpen = !menuOpen; renderChatMenu(); }
function renderChatMenu() {
  const el = document.getElementById("chatmenu"); if (!el) return;
  el.classList.toggle("hidden", !menuOpen);
  if (!menuOpen) return;
  const m = byId(route.id);
  const cur = activeConvo(m.id);
  const mine = convosFor(m.id), others = allConvos().filter(c => c.mid !== m.id).slice(0, 8);
  const row = c => `<div class="crow ${c.id === cur.id ? "on" : ""}">
      <button class="cmain" onclick="switchConvo('${c.id}')">
        <span class="t">${esc(convoTitle(c))}</span>
        <span class="s">${byId(c.mid).id} · ${c.msgs.filter(x => x.r === "u").length} question${c.msgs.filter(x => x.r === "u").length === 1 ? "" : "s"} · ${new Date(c.updated).toLocaleDateString()}${c.parent ? " · carried over" : ""}</span>
      </button>
      <button class="iconbtn" style="width:24px;height:24px;font-size:11px" title="Rename" onclick="renameConvo('${c.id}')">✎</button>
      <button class="iconbtn" style="width:24px;height:24px;font-size:11px" title="Delete" onclick="deleteConvo('${c.id}')">🗑</button>
    </div>`;
  el.innerHTML = `
    <div class="cmhead">This module</div>
    ${mine.length ? mine.map(row).join("") : `<div class="cmempty">No chats here yet</div>`}
    ${others.length ? `<div class="cmhead">Other modules</div>` + others.map(row).join("") : ""}
    <div class="cmfoot">
      <button class="btn sm" onclick="startNew()">＋ New chat</button>
      ${cur.msgs.length ? `<button class="btn sm" onclick="compactConvo('${cur.id}')">⤳ Compact into a new chat</button>` : ""}
      <button class="btn sm ghost" onclick="go('#/marks')">All conversations →</button>
    </div>`;
}
function startNew() { newConvo(route.id); menuOpen = false; renderRail(); toast("New chat"); }
function renderRailBody() {
  const b = document.getElementById("railbody"); if (!b) return;
  const m = byId(route.id); if (!m) return;
  const c = activeConvo(m.id);
  let h = "";
  if (connMode() === "none") {
    h += `<div class="warnbar" style="margin:0 0 12px"><span>Not connected to Claude.</span>
      <button class="btn sm" onclick="go('#/settings')">Connect</button></div>`;
  }
  if (c.summary) {
    h += `<div class="carried"><b>Carried over${c.parent && CV()[c.parent] ? " from “" + esc(convoTitle(CV()[c.parent])) + "”" : ""}</b>
      <div>${esc(c.summary)}</div></div>`;
  }
  if (compacting) h += `<div class="msg a typing"><i></i><i></i><i></i></div>`;
  c.msgs.forEach(x => {
    h += `<div class="msg ${x.r === "u" ? "u" : x.r === "e" ? "a err" : "a"}">
      ${x.r === "u" && x.sec != null && m.sections[x.sec] ? `<div class="msgctx">${esc(m.sections[x.sec].h)}${x.quote ? " · selection" : ""}</div>` : ""}
      ${x.r === "u" ? esc(x.t) : mdLite(x.t)}</div>`;
  });
  h += `<div id="railpending"></div>`;
  h += `<div class="suggest"><div id="raillead2"></div><div id="railsuggest"></div></div>`;
  b.innerHTML = h;
  renderSuggest();
  b.scrollTop = b.scrollHeight;
  const d = document.getElementById("railhead");
  if (d) { const dot = d.querySelector(".dotstat"); if (dot) dot.className = "dotstat " + (bridgeChecking ? "busy" : connMode() !== "none" ? "on" : ""); }
}
function renderSuggest() {
  const box = document.getElementById("railsuggest");
  if (box) {
    box.innerHTML = railSuggestions().map(q =>
      `<button class="chip" onclick="askThis(this)" data-q="${esc(q)}">${esc(q)}</button>`).join("")
      + (pinned ? `<button class="chip gen" onclick="genQuestions()" ${genning ? "disabled" : ""}>
          ${genning ? "Thinking of better questions…" : "✦ Ask Claude for sharper questions"}</button>` : "");
  }
  const lead = document.getElementById("raillead2");
  if (lead) lead.innerHTML = `<p class="sub" style="font-size:12px;margin:0 0 8px">${pinned
    ? "Questions about <b>the passage you picked</b>:"
    : "Questions worth asking about <b>" + esc(railCtxLabel()) + "</b>:"}</p>`;
}
function askThis(el) {
  const inp = document.getElementById("railin");
  inp.value = el.dataset.q;
  railSend();
}
async function railSend() {
  const m = byId(route.id); if (!m) return;
  const inp = document.getElementById("railin"), btn = document.getElementById("railsend");
  const text = (inp.value || "").trim();
  if (!text) return;
  if (connMode() === "none") {
    const ok = await checkBridge(true);
    if (!ok) { toast("Not connected — open Settings"); go("#/settings"); return; }
  }
  const c = activeConvo(m.id);
  c.msgs.push({ r: "u", t: text, ts: Date.now(), sec: pinned ? pinned.sec : curSec, quote: pinned ? pinned.text : "" });
  c.updated = Date.now();
  save(); markDay();
  inp.value = ""; inp.style.height = "auto";
  menuOpen = false;
  renderRailBody(); renderSidebar();
  btn.disabled = true; inp.disabled = true;
  const pend = document.getElementById("railpending");
  if (pend) pend.innerHTML = `<div class="msg a typing"><i></i><i></i><i></i></div>`;
  const body = document.getElementById("railbody"); if (body) body.scrollTop = body.scrollHeight;
  try {
    const msgs = c.msgs.filter(x => x.r !== "e").slice(-12).map(x => ({ role: x.r === "u" ? "user" : "assistant", content: x.t }));
    const reply = await askBridge(systemForRail(), msgs);
    c.msgs.push({ r: "a", t: reply, ts: Date.now() });
  } catch (e) {
    c.msgs.push({ r: "e", t: (e && e.message) || "Something went wrong.", ts: Date.now() });
  }
  c.updated = Date.now(); save();
  btn.disabled = false; inp.disabled = false;
  renderRail();
  const i2 = document.getElementById("railin"); if (i2) i2.focus();
}

/* opening a mark's passage just pins it into the rail */
function closePanel() { const p = document.getElementById("panel"); if (p) p.remove(); }
function openPanel(mid, id) {
  const m = findMark(mid, id); if (!m) return;
  if (route.id !== mid) { go("#/m/" + mid + "/1"); setTimeout(() => pinQuote(m.text, m.sec), 260); return; }
  pinQuote(m.text, m.sec);
}
function statusOf(m) { return m.note && m.note.trim() ? "note" : "hl"; }

