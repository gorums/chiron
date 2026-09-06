/* ---- the chat rail: always there, always about what you are looking at ---- */

/* Everything the rail keeps between renders. Nothing here is saved: the conversations
   themselves live in STATE.convos (see 17-convos.js). */
const rail = {
  section: 0, // the section the reader is looking at
  pinned: null, // a passage pinned as the question's context, or null
  pinnedQuestions: null, // suggested questions for the pinned passage
  generating: false, // asking the tutor for question suggestions
  menuOpen: false, // the conversation menu is showing
  sending: false, // a reply is on its way
  sectionLockUntil: 0, // no section-following until this time (a jump scrolls past sections)
  compacting: false, // a conversation is being summarised into a fresh one
  pendingAsk: null, // a question to send as soon as the rail is drawn (see askAbout)
};

function railOpen() {
  if (!STATE.ui) STATE.ui = { rail: true };
  return STATE.ui.rail !== false;
}
function toggleRail() {
  if (!STATE.ui) STATE.ui = {};
  STATE.ui.rail = !railOpen();
  save();
  applyRail();
  if (railOpen()) renderRail();
}
const DOCKS = [
  ["right", "", "Dock right"],
  ["bottom", "", "Dock along the bottom"],
];
function railPos() {
  const p = STATE.ui && STATE.ui.railPos;
  return DOCKS.some(d => d[0] === p) ? p : "right";
}
/* Sizes come from the platform's `page.ui` settings (LAYOUT). The rail is never wider
   than leaves `readMin` pixels for the text beside it. */
function railWidth() {
  const side = STATE.ui && STATE.ui.sideOff ? 0 : LAYOUT.sideWidth;
  const cap = Math.max(LAYOUT.railMin, window.innerWidth - side - LAYOUT.readMin);
  return Math.max(
    LAYOUT.railMin,
    Math.min((STATE.ui && STATE.ui.railW) || LAYOUT.railDefault, cap)
  );
}
function railHeight() {
  return Math.max(
    LAYOUT.railHeightMin,
    Math.min(
      (STATE.ui && STATE.ui.railH) || LAYOUT.railHeightDefault,
      Math.floor(window.innerHeight * 0.8)
    )
  );
}
function setRailPos(p) {
  if (!STATE.ui) STATE.ui = {};
  STATE.ui.railPos = p;
  save();
  applyRail();
  if (route.view === "m" && railOpen()) renderRail();
  if (route.view === "settings") viewSettings();
}
/* Lays the page out: which columns the #app grid has, and where the rail sits in them.
   Everything is recomputed from state, so a drag, a dock change, a hidden sidebar and a
   window resize all go through here. */
function applyRail() {
  const show = route.view === "m" && railOpen();
  const pos = railPos(),
    side = !(STATE.ui && STATE.ui.sideOff),
    narrow = window.innerWidth <= 860;
  const root = document.documentElement.style;
  root.setProperty("--railw", railWidth() + "px");
  root.setProperty("--railh", railHeight() + "px");
  root.setProperty("--sidew", (side && !narrow ? LAYOUT.sideWidth : 0) + "px");
  document.body.classList.toggle("rail-on", show);
  ["rail-right", "rail-bottom"].forEach(c => document.body.classList.remove(c));
  document.body.classList.add("rail-" + pos);
  const app = document.getElementById("app"),
    main = document.getElementById("main"),
    sb = document.getElementById("sidebar");
  const el = document.getElementById("rail");
  if (el) {
    el.classList.toggle("hidden", route.view !== "m");
    el.classList.toggle("shut", !railOpen());
  }
  // grid columns: [sidebar] [main] [rail]  — the rail docks right, or along the bottom
  const cols = [],
    place = (node, col) => {
      if (node) node.style.gridColumn = String(col);
    };
  let col = 1;
  if (side && !narrow) {
    cols.push(LAYOUT.sideWidth + "px");
    place(sb, col++);
  } else place(sb, "");
  const inGrid = show && !narrow && pos !== "bottom";
  cols.push("1fr");
  place(main, col++);
  if (inGrid) {
    cols.push("var(--railw)");
    place(el, col++);
  } else place(el, "");
  if (app) app.style.gridTemplateColumns = narrow ? "" : cols.join(" ");
  const t = document.getElementById("railtoggle");
  if (t) t.classList.toggle("hidden", route.view !== "m");
}

/* ---- questions built from the passage itself, instantly and for free ---- */
function termsIn(text) {
  const low = " " + text.toLowerCase().replace(/[^a-z0-9%$€£. ]+/g, " ") + " ";
  const hits = [];
  (DATA.library.glossary || []).forEach(g => {
    const t = g.term
      .toLowerCase()
      .replace(/\s*\(.*?\)\s*/g, " ")
      .trim();
    if (t.length < 4 || t.length > 34) return;
    if (low.indexOf(" " + t + " ") >= 0 || low.indexOf(" " + t + "s ") >= 0)
      hits.push({ t: g.term.replace(/\s*\(.*?\)\s*/g, "").trim(), star: g.star, len: t.length });
  });
  hits.sort((a, b) => b.star - a.star || b.len - a.len);
  const out = [];
  hits.forEach(h => {
    if (
      !out.some(
        o =>
          o.toLowerCase().includes(h.t.toLowerCase()) || h.t.toLowerCase().includes(o.toLowerCase())
      )
    )
      out.push(h.t);
  });
  return out.slice(0, 3);
}
function localQuestions(text, hints) {
  const seen = [];
  (hints || []).forEach(hStr => {
    const h = String(hStr)
      .replace(/[.,;:]$/, "")
      .trim();
    if (h.length >= 4 && h.length <= 44 && !seen.some(x => x.toLowerCase() === h.toLowerCase()))
      seen.push(h);
  });
  termsIn(text).forEach(t => {
    if (!seen.some(x => x.toLowerCase().includes(t.toLowerCase()))) seen.push(t);
  });
  const terms = seen.slice(0, 3);
  const num = (text.match(/\b\d+(\.\d+)?\s?(%|x\b|:1\b)|[$€£]\s?\d[\d,.]*/) || [])[0];
  const qs = [];
  qs.push(
    terms[0]
      ? `What does "${terms[0]}" actually mean here?`
      : "Say this back to me in plain language."
  );
  if (terms[1]) qs.push(`How is ${terms[1]} different from ${terms[0]}?`);
  else qs.push("Give me a concrete example of this.");
  if (num) qs.push(`Where does the ${num} come from?`);
  qs.push(`How would I apply this to ${STATE.biz || (CFG.anchor || {}).noun || "my own case"}?`);
  qs.push("When does this stop being true?");
  return qs.slice(0, 5);
}
async function genQuestions() {
  if (!rail.pinned || rail.generating) return;
  if (connMode() === "none") {
    toast("Not connected — open Settings");
    return;
  }
  rail.generating = true;
  renderSuggest();
  try {
    const sys =
      "You write study questions. Given a passage from a " +
      CFG.subject +
      " course, return the 5 questions a smart beginner should be asking about it. One per line, no numbering, no preamble, each under 90 characters, each answerable from thinking about this passage. Make them specific to this passage's actual content, not generic.";
    const reply = await askBridge(sys, [
      {
        role: "user",
        content:
          rail.pinned.text +
          (STATE.biz ? "\n\n(" + (CFG.anchor || {}).label + ": " + STATE.biz + ")" : ""),
      },
    ]);
    const lines = reply
      .split("\n")
      .map(l => l.replace(/^\s*[-*\d.)]+\s*/, "").trim())
      .filter(l => l.length > 12 && l.length < 140 && l.indexOf("?") > 0)
      .slice(0, 6);
    if (lines.length) {
      rail.pinnedQuestions = lines;
      toast("Questions generated");
    } else toast("Could not read the reply — keeping the current suggestions");
  } catch (e) {
    toast((e && e.message) || "Could not generate questions");
  }
  rail.generating = false;
  renderSuggest();
}

/* ---- a hover button on every paragraph, list, quote and table ---- */
function attachParaButtons(mid) {
  const blocks = document.querySelectorAll(
    ".sec .prose > p, .sec .prose > ul, .sec .prose > ol, .sec .prose > blockquote, .sec .prose > table, .sec .prose > pre"
  );
  blocks.forEach(el => {
    if (el.dataset.pb) return;
    const txt = (el.innerText || el.textContent || "").trim();
    if (txt.length < 40) return;
    el.dataset.pb = "1";
    el.classList.add("askable");
    const sec = el.closest(".sec");
    const i = sec ? +sec.id.replace("sec", "") : 0;
    const b = document.createElement("button");
    b.className = "parask";
    b.type = "button";
    b.title = "Ask Claude about this paragraph";
    b.textContent = "?";
    b.addEventListener("click", ev => {
      ev.stopPropagation();
      const hints = [...el.querySelectorAll("strong,b,code,em")]
        .map(n => n.textContent.trim())
        .slice(0, 4);
      pinQuote(txt.length > 1500 ? txt.slice(0, 1500) + "…" : txt, i, hints);
      document.querySelectorAll(".prose .picked").forEach(n => n.classList.remove("picked"));
      el.classList.add("picked");
    });
    el.appendChild(b);
  });
}

/* ---------- context ---------- */
/* How long after the last scroll event a jump counts as finished. */
const SCROLL_SETTLE_MS = 250;
/* How often, at most, the section under the reading line is recomputed while scrolling. */
const SCROLL_THROTTLE_MS = 40;
/* A jump is starting: the sections the smooth scroll passes through must not steal the
   chat. The scroll handler in 07-module.js keeps the lock alive while scrolling lasts. */
function lockSectionFollowing() {
  rail.sectionLockUntil = Date.now() + 1500;
}
function setCurSec(i) {
  if (i === rail.section) return;
  rail.section = i;
  if (route.view !== "m" || !route.id) return;
  STATE.pos[route.id] = i; // picked up on the next save
  if (!rail.pinned && followSection(route.id, i)) {
    rail.menuOpen = false;
    if (railOpen()) renderRail();
    return;
  }
  if (railOpen() && !rail.pinned) {
    renderRailHead();
    renderSuggest();
  }
}
function pinQuote(text, sec, hints, markId) {
  rail.pinned = { text: text, sec: sec, markId: markId || null };
  rail.pinnedQuestions = localQuestions(text, hints);
  if (!railOpen()) {
    STATE.ui = STATE.ui || {};
    STATE.ui.rail = true;
    save();
    applyRail();
  }
  renderRail();
  const inp = document.getElementById("railin");
  if (inp) inp.focus();
}
function unpin() {
  rail.pinned = null;
  rail.pinnedQuestions = null;
  document.querySelectorAll(".prose .picked").forEach(n => n.classList.remove("picked"));
  renderRail();
}
function railCtxLabel() {
  const m = byId(route.id);
  if (!m) return "";
  if (rail.pinned) return "your selection";
  const s = m.sections[chatSec(activeConvo(m.id, false))];
  return s ? s.h : m.title;
}
function railSuggestions() {
  if (rail.pinned) return rail.pinnedQuestions || localQuestions(rail.pinned.text);
  const m = byId(route.id);
  if (!m) return [];
  const set = (m.suggest && m.suggest[chatSec(activeConvo(m.id, false))]) || [];
  const extra = STATE.biz
    ? ["How does this apply to " + STATE.biz + "?"]
    : ["How would I apply this to " + ((CFG.anchor || {}).noun || "my own case") + "?"];
  return set.concat(extra);
}
/* the tutor as a tool on the section in view, not just a question box */
const TOOL_CHIPS = [
  [
    "Summarise this section",
    "Summarise this section in five short bullets, then one sentence on what I should now be able to do that I could not before.",
  ],
  [
    "Quiz me on this section",
    "Quiz me on this section. Ask ONE question at a time that tests whether I can use the idea, wait for my answer, grade it honestly in a line or two, then ask the next. Three questions, then tell me what I have and have not got.",
  ],
  [
    "Explain it more simply",
    "Explain this section again more simply, as if to someone smart who has never worked in this field, with one concrete example.",
  ],
];
function activeIsRoleplay() {
  const c = activeConvo(route.id, false);
  return !!(c && c.kind === "rp");
}
function systemForRail() {
  const m = byId(route.id);
  const c = activeConvo(m.id);
  const sec = m.sections[rail.pinned ? rail.pinned.sec : chatSec(c)];
  const quote = rail.pinned ? rail.pinned.text : sec ? sec.text.slice(0, 1200) : "";
  if (c && c.kind === "rp" && m.assess.roleplay) return roleplaySystem(m, m.assess.roleplay);
  return `${CFG.tutorPersona} The person is ${CFG.audience} working through a ${CFG.hours}-hour ${CFG.subject} course. Right now they are in module ${m.id}, "${m.title}", reading the section "${sec ? sec.h : ""}".

${rail.pinned ? "They selected this passage and are asking about it:" : "The part of the text they are looking at:"}
"""
${quote}
"""
${STATE.biz ? `\n${(CFG.anchor || {}).label}, which examples should be aimed at: ${STATE.biz}` : ""}
${c && c.summary ? `\nWhat happened in your earlier conversation with them, carried over. Do not repeat it; build on it:\n"""\n${c.summary}\n"""` : ""}

How to answer:
- Be concise. Two or three short paragraphs is plenty; a short list only when it genuinely helps.
- Be concrete: real numbers, real examples, a real first step.
- Tie it back to what they are reading.
- If the course text is a simplification, or you disagree with it, say so and explain where it breaks down.
- No preamble, no flattery. Answer the question.
${learnerContext(m.id)}`;
}

/* ---------- render ---------- */
function renderRail() {
  const el = document.getElementById("rail");
  if (!el || route.view !== "m") return;
  const m = byId(route.id);
  if (!m) return;
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
  renderRailHead();
  renderRailBody();
  bindRailGrip();
  const inp = document.getElementById("railin");
  inp.addEventListener("keydown", e => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey || !e.shiftKey)) {
      e.preventDefault();
      railSend();
    }
  });
  inp.addEventListener("input", () => {
    inp.style.height = "auto";
    inp.style.height = Math.min(120, inp.scrollHeight) + "px";
  });
  if (rail.pendingAsk) {
    inp.value = rail.pendingAsk;
    rail.pendingAsk = null;
    railSend();
  }
}
function renderRailHead() {
  const h = document.getElementById("railhead");
  if (!h) return;
  const m = byId(route.id);
  if (!m) return;
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
      ${
        rail.pinned
          ? `<div class="pinned"><span class="tag acc">selection</span>
             <button class="iconbtn" style="width:22px;height:22px" title="Unpin" aria-label="Unpin the selection" onclick="unpin()">${ico("close", 12)}</button>
             <div class="ptext">${esc(rail.pinned.text.length > 220 ? rail.pinned.text.slice(0, 220) + "…" : rail.pinned.text)}</div></div>`
          : `<div class="ctxline">${c.sec != null ? "About" : "Reading"} · <b>${esc(railCtxLabel())}</b>${n > 1 ? ` · ${n} chats here` : ""}</div>`
      }
    </div>`;
}
function toggleChatMenu() {
  rail.menuOpen = !rail.menuOpen;
  renderChatMenu();
}
function renderChatMenu() {
  const el = document.getElementById("chatmenu");
  if (!el) return;
  el.classList.toggle("hidden", !rail.menuOpen);
  if (!rail.menuOpen) return;
  const m = byId(route.id);
  const cur = activeConvo(m.id);
  const mine = convosFor(m.id),
    others = allConvos()
      .filter(c => c.mid !== m.id)
      .slice(0, 8);
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
    const c = secConvo(m.id, i),
      n = c ? c.msgs.filter(x => x.r === "u").length : 0;
    return `<div class="crow ${c && c.id === cur.id ? "on" : ""}">
      <button class="cmain" onclick="pickSection('${m.id}',${i})" title="Open this section and its chat">
        <span class="t"><span class="secno">§${i + 1}</span> ${esc(s.h)}</span>
        <span class="s">${n ? `${n} question${n === 1 ? "" : "s"}` : "no questions yet"}${i === rail.section ? " · in view" : ""}</span>
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
function startNew() {
  newConvo(route.id);
  rail.menuOpen = false;
  renderRail();
  toast("New chat");
}
function renderRailBody() {
  const b = document.getElementById("railbody");
  if (!b) return;
  const m = byId(route.id);
  if (!m) return;
  const c = activeConvo(m.id);
  let h = "";
  if (connMode() === "none") {
    h += `<div class="warnbar" style="margin:0 0 12px"><span>Not connected to Claude.</span>
      <button class="btn sm" onclick="go('#/settings')">Connect</button></div>`;
  }
  if (c.summary) {
    h += `<div class="carried"><b>Carried over${c.parent && convos()[c.parent] ? " from “" + esc(convoTitle(convos()[c.parent])) + "”" : ""}</b>
      <div>${esc(c.summary)}</div></div>`;
  }
  h += `<div class="thread" id="railthread">`;
  if (rail.compacting) h += `<div class="msg a typing"><i></i><i></i><i></i></div>`;
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
  if (railPos() === "bottom" && th) th.scrollTop = th.scrollHeight;
  else b.scrollTop = b.scrollHeight;
  const d = document.getElementById("railhead");
  if (d) {
    const dot = d.querySelector(".dotstat");
    if (dot)
      dot.className = "dotstat " + (bridgeChecking ? "busy" : connMode() !== "none" ? "on" : "");
  }
}
function renderSuggest() {
  const box = document.getElementById("railsuggest");
  if (box) {
    const gaps = rail.pinned ? [] : gapChips(route.id);
    box.innerHTML =
      gaps
        .map(
          q =>
            `<button class="chip gap" onclick="askThis(this)" data-q="${esc(q)}" title="From what you missed or asked before">${esc(q)}</button>`
        )
        .join("") +
      railSuggestions()
        .map(
          q => `<button class="chip" onclick="askThis(this)" data-q="${esc(q)}">${esc(q)}</button>`
        )
        .join("") +
      (rail.pinned
        ? `<button class="chip gen" onclick="genQuestions()" ${rail.generating ? "disabled" : ""}>
          ${rail.generating ? "Thinking of better questions…" : "✦ Ask Claude for sharper questions"}</button>`
        : `<div class="toolchips">${TOOL_CHIPS.map(([l, q]) => `<button class="chip tool" onclick="askThis(this)" data-q="${esc(q)}">${l}</button>`).join("")}</div>`);
    if (activeIsRoleplay()) box.innerHTML = "";
  }
  const lead = document.getElementById("raillead2");
  if (lead)
    lead.innerHTML = activeIsRoleplay()
      ? `<p class="sub" style="font-size:12px;margin:0 0 8px">In character. Write "pause" to step out. When you are done, press <b>Finish &amp; get feedback</b> above.</p>`
      : `<p class="sub" style="font-size:12px;margin:0 0 8px">${
          rail.pinned
            ? "Questions about <b>the passage you picked</b>:"
            : "Questions worth asking about <b>" + esc(railCtxLabel()) + "</b>:"
        }</p>`;
}
function askThis(el) {
  const inp = document.getElementById("railin");
  inp.value = el.dataset.q;
  railSend();
}
async function railSend() {
  const m = byId(route.id);
  if (!m) return;
  const inp = document.getElementById("railin"),
    btn = document.getElementById("railsend");
  const text = (inp.value || "").trim();
  if (!text) return;
  if (connMode() === "none") {
    const ok = await checkBridge(true);
    if (!ok) {
      toast("Not connected — open Settings");
      go("#/settings");
      return;
    }
  }
  const c = activeConvo(m.id);
  const markId = rail.pinned ? rail.pinned.markId : null;
  c.msgs.push({
    r: "u",
    t: text,
    ts: Date.now(),
    sec: rail.pinned ? rail.pinned.sec : chatSec(c),
    quote: rail.pinned ? rail.pinned.text : "",
    mark: markId,
  });
  c.updated = Date.now();
  save();
  markDay();
  inp.value = "";
  inp.style.height = "auto";
  rail.menuOpen = false;
  renderRailBody();
  renderSidebar();
  btn.disabled = true;
  inp.disabled = true;
  rail.sending = true;
  const pend = document.getElementById("railpending");
  if (pend) pend.innerHTML = `<div class="msg a typing"><i></i><i></i><i></i></div>`;
  const body = document.getElementById("railbody");
  if (body) body.scrollTop = body.scrollHeight;
  try {
    const msgs = c.msgs
      .filter(x => x.r !== "e")
      .slice(-TUTOR.railTurns)
      .map(x => ({ role: x.r === "u" ? "user" : "assistant", content: x.t }));
    const reply = await askBridge(systemForRail(), msgs);
    c.msgs.push({ r: "a", t: reply, ts: Date.now() });
    if (markId) {
      const mk = findMark(m.id, markId);
      if (mk && mk.status === "open") setMarkStatus(m.id, markId, "answered");
    }
  } catch (e) {
    c.msgs.push({ r: "e", t: (e && e.message) || "Something went wrong.", ts: Date.now() });
  }
  c.updated = Date.now();
  save();
  rail.sending = false;
  btn.disabled = false;
  inp.disabled = false;
  renderRail();
  const i2 = document.getElementById("railin");
  if (i2) i2.focus();
}

/* opening a mark's passage just pins it into the rail */
function closePanel() {
  const p = document.getElementById("panel");
  if (p) p.remove();
}
function openPanel(mid, id) {
  const m = findMark(mid, id);
  if (!m) return;
  if (route.id !== mid || route.step !== 1) {
    go("#/m/" + mid + "/1");
    setTimeout(() => pinQuote(m.text, m.sec, null, id), 260);
    return;
  }
  pinQuote(m.text, m.sec, null, id);
}
/* the "?" beside a section heading: the whole section becomes the subject */
function askSection(mid, i) {
  const m = byId(mid),
    sec = m && m.sections[i];
  if (!sec) return;
  const txt = sec.text.length > 1500 ? sec.text.slice(0, 1500) + "…" : sec.text;
  const hints = [sec.h];
  pinQuote(txt, i, hints);
  document.querySelectorAll(".prose .picked").forEach(n => n.classList.remove("picked"));
}

/* the rail is resizable: drag its inner edge. Width (or height, docked at the bottom) is
   kept per device in STATE.ui and saved as you drag, so a reload keeps it. */
let railSaveTimer = null;
function bindRailGrip() {
  const g = document.getElementById("railgrip");
  if (!g) return;
  g.addEventListener("mousedown", e => {
    e.preventDefault();
    if (!STATE.ui) STATE.ui = {};
    document.body.classList.add("raildrag");
    const pos = railPos();
    const move = ev => {
      if (pos === "bottom") STATE.ui.railH = Math.round(window.innerHeight - ev.clientY);
      else STATE.ui.railW = Math.round(window.innerWidth - ev.clientX);
      applyRail();
      clearTimeout(railSaveTimer);
      railSaveTimer = setTimeout(save, 300);
    };
    const up = () => {
      document.body.classList.remove("raildrag");
      window.removeEventListener("mousemove", move);
      window.removeEventListener("mouseup", up);
      if (pos === "bottom") STATE.ui.railH = railHeight();
      else STATE.ui.railW = railWidth();
      save();
    };
    window.addEventListener("mousemove", move);
    window.addEventListener("mouseup", up);
  });
  g.addEventListener("dblclick", () => {
    if (!STATE.ui) STATE.ui = {};
    if (railPos() === "bottom") STATE.ui.railH = LAYOUT.railHeightDefault;
    else STATE.ui.railW = LAYOUT.railDefault;
    save();
    applyRail();
    toast("Chat size reset");
  });
}
window.addEventListener("resize", () => {
  applyRail();
});
