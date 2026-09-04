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
/* A chat is either about one section of its module (`sec` is the section index) or about
   the module as a whole (`sec` is null: older chats, "New chat", role-plays). Section
   chats follow the reader down the page; module-wide chats stay put. */
function secConvo(mid, i) { return Object.values(CV()).find(c => c.mid === mid && c.sec === i && c.kind !== "rp") || null; }
function chatSec(c) { return c && c.sec != null ? c.sec : curSec; }
/* section chats are made as the reader scrolls, so the empty ones are dropped again */
function pruneEmpty(mid, keepId) {
  Object.values(CV()).forEach(c => {
    if (c.mid !== mid || c.id === keepId || c.msgs.length || c.summary || c.kind === "rp") return;
    delete CV()[c.id];
    if (ACT()[mid] === c.id) delete ACT()[mid];
  });
}
function convoTitle(c) {
  if (c.title) return c.title;
  if (c.sec != null) { const m = byId(c.mid), s = m && m.sections[c.sec]; if (s) return s.h; }
  const first = (c.msgs || []).find(m => m.r === "u");
  if (first) return first.t.length > 46 ? first.t.slice(0, 46) + "…" : first.t;
  return c.summary ? "Continued conversation" : "New chat";
}
function activeConvo(mid, create) {
  const id = ACT()[mid];
  if (id && CV()[id]) return CV()[id];
  // nothing chosen yet: the chat about the section in view, when that module is open
  const sec = route.v === "m" && route.id === mid ? curSec : null;
  const own = sec != null ? secConvo(mid, sec) : null;
  if (own) { ACT()[mid] = own.id; return own; }
  const existing = convosFor(mid)[0];
  if (existing) { ACT()[mid] = existing.id; return existing; }
  if (create === false) return null;
  return newConvo(mid, sec != null ? { sec } : null);
}
/* the reader scrolled to section i: a section chat moves with them, unless a reply is
   on its way or the section was just picked from the menu (the smooth scroll passes
   through the sections in between) */
let secLock = 0;
function followSection(mid, i) {
  if (sending || Date.now() < secLock) return false;
  const c = activeConvo(mid, false);
  if (c && (c.sec == null || c.sec === i)) return false;
  const next = secConvo(mid, i) || newConvo(mid, { sec: i });
  ACT()[mid] = next.id; pruneEmpty(mid, next.id); save();
  return true;
}
/* from the menu at the top of the rail: that section's chat, and the page scrolled to it */
function pickSection(mid, i) {
  const next = secConvo(mid, i) || newConvo(mid, { sec: i });
  ACT()[mid] = next.id; pruneEmpty(mid, next.id); save();
  secLock = Date.now() + 1500;
  menuOpen = false; pinned = null; pinnedQs = null;
  document.querySelectorAll(".prose .picked").forEach(n => n.classList.remove("picked"));
  renderRail();
  jumpToPassage(mid, i, null);
}
function newConvo(mid, opts) {
  const id = newId();
  CV()[id] = { id, mid, msgs: [], created: Date.now(), updated: Date.now(),
               parent: (opts && opts.parent) || null, summary: (opts && opts.summary) || "",
               title: (opts && opts.title) || "", sec: opts && opts.sec != null ? opts.sec : null };
  ACT()[mid] = id; save();
  return CV()[id];
}
function switchConvo(id) {
  const c = CV()[id]; if (!c) return;
  ACT()[c.mid] = id; pruneEmpty(c.mid, id); save(); menuOpen = false; renderRail();
}
function deleteConvo(id) {
  const c = CV()[id]; if (!c) return;
  confirmModal("Delete this conversation?", "It cannot be undone.", "Delete", () => {
    const mid = c.mid;
    delete CV()[id];
    if (ACT()[mid] === id) delete ACT()[mid];
    save(); menuOpen = false;
    if (route.v === "m") renderRail(); else render();
    toast("Conversation deleted");
  }, true);
}
function renameConvo(id) {
  const c = CV()[id]; if (!c) return;
  promptModal("Name this conversation", convoTitle(c), "Save", t => {
    c.title = t.trim().slice(0, 70); save();
    if (route.v === "m") renderRail(); else render();
  });
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
    const sys = "You compress a tutoring conversation into a handover brief for the next conversation, written for the tutor who picks it up. Under 180 words. Cover: what was actually settled, the learner's own situation as revealed, any conclusion or decision reached, and what is still open or confusing. No preamble, no headings, plain prose. Do not repeat explanations — record outcomes.";
    const summary = await askBridge(sys, [{ role: "user", content: transcript.slice(-TUTOR.summaryChars) }]);
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
let curSec = 0, pinned = null, pinnedQs = null, genning = false, menuOpen = false, sending = false;

function railOpen() { if (!S.ui) S.ui = { rail: true }; return S.ui.rail !== false; }
function toggleRail() {
  if (!S.ui) S.ui = {};
  S.ui.rail = !railOpen(); save();
  applyRail(); if (railOpen()) renderRail();
}
const DOCKS = [["right", "", "Dock right"], ["bottom", "", "Dock along the bottom"]];
function railPos() { const p = S.ui && S.ui.railPos; return DOCKS.some(d => d[0] === p) ? p : "right"; }
/* Sizes come from the platform's `page.ui` settings (LAYOUT). The rail is never wider
   than leaves `readMin` pixels for the text beside it. */
function railWidth() {
  const side = (S.ui && S.ui.sideOff) ? 0 : LAYOUT.sideWidth;
  const cap = Math.max(LAYOUT.railMin, window.innerWidth - side - LAYOUT.readMin);
  return Math.max(LAYOUT.railMin, Math.min((S.ui && S.ui.railW) || LAYOUT.railDefault, cap));
}
function railHeight() { return Math.max(LAYOUT.railHeightMin, Math.min((S.ui && S.ui.railH) || LAYOUT.railHeightDefault, Math.floor(window.innerHeight * .8))); }
function setRailPos(p) { if (!S.ui) S.ui = {}; S.ui.railPos = p; save(); applyRail(); if (route.v === "m" && railOpen()) renderRail(); if (route.v === "settings") viewSettings(); }
/* Lays the page out: which columns the #app grid has, and where the rail sits in them.
   Everything is recomputed from state, so a drag, a dock change, a hidden sidebar and a
   window resize all go through here. */
function applyRail() {
  const show = route.v === "m" && railOpen();
  const pos = railPos(), side = !(S.ui && S.ui.sideOff), narrow = window.innerWidth <= 860;
  const root = document.documentElement.style;
  root.setProperty("--railw", railWidth() + "px");
  root.setProperty("--railh", railHeight() + "px");
  root.setProperty("--sidew", (side && !narrow ? LAYOUT.sideWidth : 0) + "px");
  document.body.classList.toggle("rail-on", show);
  ["rail-right", "rail-bottom"].forEach(c => document.body.classList.remove(c));
  document.body.classList.add("rail-" + pos);
  const app = document.getElementById("app"), main = document.getElementById("main"), sb = document.getElementById("sidebar");
  const el = document.getElementById("rail");
  if (el) { el.classList.toggle("hidden", route.v !== "m"); el.classList.toggle("shut", !railOpen()); }
  // grid columns: [sidebar] [main] [rail]  — the rail docks right, or along the bottom
  const cols = [], place = (node, col) => { if (node) node.style.gridColumn = String(col); };
  let col = 1;
  if (side && !narrow) { cols.push(LAYOUT.sideWidth + "px"); place(sb, col++); } else place(sb, "");
  const inGrid = show && !narrow && pos !== "bottom";
  cols.push("1fr"); place(main, col++);
  if (inGrid) { cols.push("var(--railw)"); place(el, col++); } else place(el, "");
  if (app) app.style.gridTemplateColumns = narrow ? "" : cols.join(" ");
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
  qs.push(`How would I apply this to ${S.biz || (CFG.anchor || {}).noun || "my own case"}?`);
  qs.push("When does this stop being true?");
  return qs.slice(0, 5);
}
async function genQuestions() {
  if (!pinned || genning) return;
  if (connMode() === "none") { toast("Not connected — open Settings"); return; }
  genning = true; renderSuggest();
  try {
    const sys = "You write study questions. Given a passage from a " + CFG.subject + " course, return the 5 questions a smart beginner should be asking about it. One per line, no numbering, no preamble, each under 90 characters, each answerable from thinking about this passage. Make them specific to this passage's actual content, not generic.";
    const reply = await askBridge(sys, [{ role: "user", content: pinned.text + (S.biz ? "\n\n(" + (CFG.anchor || {}).label + ": " + S.biz + ")" : "") }]);
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
  if (route.v !== "m" || !route.id) return;
  S.pos[route.id] = i;      // picked up on the next save
  if (!pinned && followSection(route.id, i)) { menuOpen = false; if (railOpen()) renderRail(); return; }
  if (railOpen() && !pinned) { renderRailHead(); renderSuggest(); }
}
function pinQuote(text, sec, hints, markId) {
  pinned = { text: text, sec: sec, markId: markId || null };
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
  const s = m.sections[chatSec(activeConvo(m.id, false))];
  return s ? s.h : m.title;
}
function railSuggestions() {
  if (pinned) return pinnedQs || localQuestions(pinned.text);
  const m = byId(route.id); if (!m) return [];
  const set = (m.suggest && m.suggest[chatSec(activeConvo(m.id, false))]) || [];
  const extra = S.biz ? ["How does this apply to " + S.biz + "?"] : ["How would I apply this to " + ((CFG.anchor || {}).noun || "my own case") + "?"];
  return set.concat(extra);
}
/* the tutor as a tool on the section in view, not just a question box */
const TOOL_CHIPS = [
  ["Summarise this section", "Summarise this section in five short bullets, then one sentence on what I should now be able to do that I could not before."],
  ["Quiz me on this section", "Quiz me on this section. Ask ONE question at a time that tests whether I can use the idea, wait for my answer, grade it honestly in a line or two, then ask the next. Three questions, then tell me what I have and have not got."],
  ["Explain it more simply", "Explain this section again more simply, as if to someone smart who has never worked in this field, with one concrete example."]
];
function activeIsRoleplay() { const c = activeConvo(route.id, false); return !!(c && c.kind === "rp"); }
function systemForRail() {
  const m = byId(route.id);
  const c = activeConvo(m.id);
  const sec = m.sections[pinned ? pinned.sec : chatSec(c)];
  const quote = pinned ? pinned.text : (sec ? sec.text.slice(0, 1200) : "");
  if (c && c.kind === "rp" && m.assess.roleplay) return roleplaySystem(m, m.assess.roleplay);
  return `${CFG.tutorPersona} The person is ${CFG.audience} working through a ${CFG.hours}-hour ${CFG.subject} course. Right now they are in module ${m.id}, "${m.title}", reading the section "${sec ? sec.h : ""}".

${pinned ? "They selected this passage and are asking about it:" : "The part of the text they are looking at:"}
"""
${quote}
"""
${S.biz ? `\n${(CFG.anchor || {}).label}, which examples should be aimed at: ${S.biz}` : ""}
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
    <div class="railgrip" id="railgrip" title="Drag to resize"></div>
    <div class="railhead" id="railhead"></div>
    <div class="railbody" id="railbody"></div>
    <div class="chatmenu hidden" id="chatmenu"></div>
    <div class="railfoot">
      <div class="row">
        <textarea id="railin" rows="1" placeholder="${c.kind === "rp" ? "Say what you would actually say…" : "Ask about this section…"}"></textarea>
        <button class="btn primary" id="railsend" onclick="railSend()" aria-label="Send">↑</button>
      </div>
      <div style="display:flex;gap:8px;align-items:center;margin-top:7px">
        <span style="font-size:11px;color:var(--muted)">${connMode() === "none" ? "not connected" : "⌘/Ctrl+↵ to send"}</span>
        ${c.msgs.length ? `<button class="btn sm ghost" style="margin-left:auto;font-size:11.5px" onclick="compactConvo('${c.id}')" title="Summarise this chat and continue in a fresh one">Compact</button>` : ""}
      </div>
    </div>`;
  renderRailHead(); renderRailBody();
  bindRailGrip();
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
      <button class="convobtn" onclick="toggleChatMenu()" title="Chats in this module — one per section">
        <span class="ct">${c.sec != null ? `<span class="secno">§${c.sec + 1}</span> ` : ""}${esc(convoTitle(c))}</span><span class="cv">▾</span>
      </button>
      <button class="iconbtn" style="width:28px;height:28px" title="New chat" aria-label="New chat" onclick="startNew()">${ico("plus", 15)}</button>
      <button class="iconbtn" style="width:28px;height:28px" title="Hide (a)" aria-label="Hide the tutor" onclick="toggleRail()">${ico("close", 14)}</button>
    </div>
    <div class="railctx">
      ${c.kind === "rp" ? `<div class="rpbar"><span class="tag warn">role-play</span><span style="flex:1;font-size:12.5px;color:var(--text-2)">${c.finished ? "Finished — feedback below" : "Claude is the other side"}</span>${c.finished ? "" : `<button class="btn sm primary" onclick="finishRoleplay('${m.id}')">Finish &amp; get feedback</button>`}</div>` : ""}
      ${pinned
        ? `<div class="pinned"><span class="tag acc">selection</span>
             <button class="iconbtn" style="width:22px;height:22px" title="Unpin" aria-label="Unpin the selection" onclick="unpin()">${ico("close", 12)}</button>
             <div class="ptext">${esc(pinned.text.length > 220 ? pinned.text.slice(0, 220) + "…" : pinned.text)}</div></div>`
        : `<div class="ctxline">${c.sec != null ? "About" : "Reading"} · <b>${esc(railCtxLabel())}</b>${n > 1 ? ` · ${n} chats here` : ""}</div>`}
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
      <button class="iconbtn" style="width:24px;height:24px" title="Rename" aria-label="Rename" onclick="renameConvo('${c.id}')">${ico("pencil", 12)}</button>
      <button class="iconbtn" style="width:24px;height:24px" title="Delete" aria-label="Delete" onclick="deleteConvo('${c.id}')">${ico("trash", 12)}</button>
    </div>`;
  const wide = mine.filter(c => c.sec == null);
  const secRow = (s, i) => {
    const c = secConvo(m.id, i), n = c ? c.msgs.filter(x => x.r === "u").length : 0;
    return `<div class="crow ${c && c.id === cur.id ? "on" : ""}">
      <button class="cmain" onclick="pickSection('${m.id}',${i})" title="Open this section and its chat">
        <span class="t"><span class="secno">§${i + 1}</span> ${esc(s.h)}</span>
        <span class="s">${n ? `${n} question${n === 1 ? "" : "s"}` : "no questions yet"}${i === curSec ? " · in view" : ""}</span>
      </button>
      ${c ? `<button class="iconbtn" style="width:24px;height:24px" title="Delete" aria-label="Delete" onclick="deleteConvo('${c.id}')">${ico("trash", 12)}</button>` : ""}
    </div>`;
  };
  el.innerHTML = `
    <div class="cmhead">${m.id} · ${esc(m.short || m.title)} — by section</div>
    ${m.sections.map(secRow).join("")}
    ${wide.length ? `<div class="cmhead">Whole module</div>` + wide.map(row).join("") : ""}
    ${others.length ? `<div class="cmhead">Other modules</div>` + others.map(row).join("") : ""}
    <div class="cmfoot">
      <button class="btn sm" onclick="startNew()">${ico("plus", 13)} New chat</button>
      ${cur.msgs.length ? `<button class="btn sm" onclick="compactConvo('${cur.id}')">Compact into a new chat</button>` : ""}
      <button class="btn sm ghost" onclick="go('#/marks')">All conversations</button>
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
  h += `<div class="thread" id="railthread">`;
  if (compacting) h += `<div class="msg a typing"><i></i><i></i><i></i></div>`;
  c.msgs.forEach(x => {
    h += `<div class="msg ${x.r === "u" ? "u" : x.r === "e" ? "a err" : "a"}">
      ${x.r === "u" && x.sec != null && m.sections[x.sec] ? `<button class="msgctx" onclick="jumpToPassage('${m.id}',${x.sec},${x.mark ? "'" + esc(x.mark) + "'" : "null"})" title="Go to this part of the module">${esc(m.sections[x.sec].h)}${x.quote ? " · selection" : ""} ↗</button>` : ""}
      ${x.r === "u" ? esc(x.t) : mdLite(x.t)}</div>`;
  });
  h += `<div id="railpending"></div></div>`;
  h += `<div class="suggest"><div id="raillead2"></div><div id="railsuggest"></div></div>`;
  b.innerHTML = h;
  renderSuggest();
  const th = document.getElementById("railthread");
  if (railPos() === "bottom" && th) th.scrollTop = th.scrollHeight; else b.scrollTop = b.scrollHeight;
  const d = document.getElementById("railhead");
  if (d) { const dot = d.querySelector(".dotstat"); if (dot) dot.className = "dotstat " + (bridgeChecking ? "busy" : connMode() !== "none" ? "on" : ""); }
}
function renderSuggest() {
  const box = document.getElementById("railsuggest");
  if (box) {
    box.innerHTML = railSuggestions().map(q =>
      `<button class="chip" onclick="askThis(this)" data-q="${esc(q)}">${esc(q)}</button>`).join("")
      + (pinned ? `<button class="chip gen" onclick="genQuestions()" ${genning ? "disabled" : ""}>
          ${genning ? "Thinking of better questions…" : "✦ Ask Claude for sharper questions"}</button>`
        : `<div class="toolchips">${TOOL_CHIPS.map(([l, q]) => `<button class="chip tool" onclick="askThis(this)" data-q="${esc(q)}">${l}</button>`).join("")}</div>`);
    if (activeIsRoleplay()) box.innerHTML = "";
  }
  const lead = document.getElementById("raillead2");
  if (lead) lead.innerHTML = activeIsRoleplay()
    ? `<p class="sub" style="font-size:12px;margin:0 0 8px">In character. Write "pause" to step out. When you are done, press <b>Finish &amp; get feedback</b> above.</p>`
    : `<p class="sub" style="font-size:12px;margin:0 0 8px">${pinned
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
  const markId = pinned ? pinned.markId : null;
  c.msgs.push({ r: "u", t: text, ts: Date.now(), sec: pinned ? pinned.sec : chatSec(c), quote: pinned ? pinned.text : "", mark: markId });
  c.updated = Date.now();
  save(); markDay();
  inp.value = ""; inp.style.height = "auto";
  menuOpen = false;
  renderRailBody(); renderSidebar();
  btn.disabled = true; inp.disabled = true; sending = true;
  const pend = document.getElementById("railpending");
  if (pend) pend.innerHTML = `<div class="msg a typing"><i></i><i></i><i></i></div>`;
  const body = document.getElementById("railbody"); if (body) body.scrollTop = body.scrollHeight;
  try {
    const msgs = c.msgs.filter(x => x.r !== "e").slice(-TUTOR.railTurns).map(x => ({ role: x.r === "u" ? "user" : "assistant", content: x.t }));
    const reply = await askBridge(systemForRail(), msgs);
    c.msgs.push({ r: "a", t: reply, ts: Date.now() });
    if (markId) { const mk = findMark(m.id, markId); if (mk && mk.status === "open") setMarkStatus(m.id, markId, "answered"); }
  } catch (e) {
    c.msgs.push({ r: "e", t: (e && e.message) || "Something went wrong.", ts: Date.now() });
  }
  c.updated = Date.now(); save(); sending = false;
  btn.disabled = false; inp.disabled = false;
  renderRail();
  const i2 = document.getElementById("railin"); if (i2) i2.focus();
}

/* opening a mark's passage just pins it into the rail */
function closePanel() { const p = document.getElementById("panel"); if (p) p.remove(); }
function openPanel(mid, id) {
  const m = findMark(mid, id); if (!m) return;
  if (route.id !== mid || route.step !== 1) { go("#/m/" + mid + "/1"); setTimeout(() => pinQuote(m.text, m.sec, null, id), 260); return; }
  pinQuote(m.text, m.sec, null, id);
}
/* the "?" beside a section heading: the whole section becomes the subject */
function askSection(mid, i) {
  const m = byId(mid), sec = m && m.sections[i]; if (!sec) return;
  const txt = sec.text.length > 1500 ? sec.text.slice(0, 1500) + "…" : sec.text;
  const hints = [sec.h];
  pinQuote(txt, i, hints);
  document.querySelectorAll(".prose .picked").forEach(n => n.classList.remove("picked"));
}

/* the rail is resizable: drag its inner edge. Width (or height, docked at the bottom) is
   kept per device in S.ui and saved as you drag, so a reload keeps it. */
let railSaveTimer = null;
function bindRailGrip() {
  const g = document.getElementById("railgrip"); if (!g) return;
  g.addEventListener("mousedown", e => {
    e.preventDefault();
    if (!S.ui) S.ui = {};
    document.body.classList.add("raildrag");
    const pos = railPos();
    const move = ev => {
      if (pos === "bottom") S.ui.railH = Math.round(window.innerHeight - ev.clientY);
      else S.ui.railW = Math.round(window.innerWidth - ev.clientX);
      applyRail();
      clearTimeout(railSaveTimer); railSaveTimer = setTimeout(save, 300);
    };
    const up = () => {
      document.body.classList.remove("raildrag");
      window.removeEventListener("mousemove", move); window.removeEventListener("mouseup", up);
      if (pos === "bottom") S.ui.railH = railHeight(); else S.ui.railW = railWidth();
      save();
    };
    window.addEventListener("mousemove", move); window.addEventListener("mouseup", up);
  });
  g.addEventListener("dblclick", () => { if (!S.ui) S.ui = {}; if (railPos() === "bottom") S.ui.railH = LAYOUT.railHeightDefault; else S.ui.railW = LAYOUT.railDefault; save(); applyRail(); toast("Chat size reset"); });
}
window.addEventListener("resize", () => { applyRail(); });
