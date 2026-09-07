/* ---- the chat rail: always there, always about what you are looking at ----

   The rule is one sentence: the rail shows the conversation at the place the reader is
   looking at (`placeNow()` in 17a-place.js, `convoAt` in 17-convos.js), and follows them
   when they move. The two exceptions are explicit: a conversation the reader picked by
   hand (`rail.showing`) stays until they move somewhere else, and a passage they pinned
   (`rail.pinned`) fixes the place until they unpin it. Nothing is tracked on scroll but
   `rail.section`, which 07-module.js keeps; nothing is created until a message is sent. */

/* Everything the rail keeps between renders. Nothing here is saved: the conversations
   themselves live in STATE.convos (see 17-convos.js). */
const rail = {
  section: 0, // the section under the reading line on the Read step (07-module.js sets it)
  showing: null, // a conversation the reader chose by hand, by id; null = the one at the place
  pinned: null, // a passage pinned as the question's context: { mid, sec, text, markId }
  pinnedQuestions: null, // suggested questions for the pinned passage
  pendingPin: null, // a passage to pin once the module is drawn (see openPanel)
  pendingAsk: null, // a question to send once the rail is drawn (see askAbout)
  generating: false, // asking the tutor for question suggestions
  menuOpen: false, // the conversation menu is showing
  sending: false, // a reply is on its way
  compacting: false, // a conversation is being summarised into a fresh one
};

/* ---- which conversation the rail draws ---- */
function convoShown() {
  const place = placeNow();
  if (!place) return null;
  const chosen = rail.showing ? convos()[rail.showing] : null;
  if (chosen && chosen.mid === place.mid) return chosen;
  rail.showing = null;
  return convoAt(place);
}
/* The reader moved to another section: the rail follows, unless it is answering or the
   conversation on show was picked by hand for this very place. */
function railPlaceChanged() {
  if (rail.sending) return;
  const chosen = rail.showing ? convos()[rail.showing] : null;
  if (chosen && hasPlace(chosen) && !samePlace(placeOf(chosen), placeNow())) rail.showing = null;
  if (railOpen()) renderRail();
}
/* The route changed: a pin belongs to one module's Read step, and a hand-picked
   conversation to one module. Called by render() once the view is drawn. */
function railRouteChanged() {
  const place = placeNow();
  if (rail.pinned && !(place && place.mid === rail.pinned.mid && (route.step || 0) === 1))
    unpin(false);
  rail.menuOpen = false;
  if (!place) {
    rail.showing = null;
    return;
  }
  railPlaceChanged();
}
/* Go to a place and show a conversation there (the newest one, or `convoId`). A Read
   place scrolls the page to its section; any other place is a step of the module; no
   place at all means the module, wherever the reader is in it. */
function openPlace(place, convoId) {
  rail.showing = convoId || null;
  rail.menuOpen = false;
  unpin(false);
  showRail();
  const inModule = route.view === "m" && route.id === place.mid;
  if (place.step === "read") {
    STATE.pos[place.mid] = place.sec;
    rail.section = place.sec;
    save();
    jumpToPassage(place.mid, place.sec, null);
    if (inModule && (route.step || 0) === 1) renderRail();
    return;
  }
  const stepIndex = place.step ? stepIndexOf(place.step) : route.step || 0;
  if (inModule && (place.step == null || (route.step || 0) === stepIndex)) renderRail();
  else go(`#/m/${place.mid}/${stepIndex}`);
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
  qs.push(anchorQuestion());
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
      unpick();
      el.classList.add("picked");
    });
    el.appendChild(b);
  });
}

/* ---- a pinned passage: the question's context, until unpinned ---- */
function pinQuote(text, sec, hints, markId) {
  rail.pinned = { mid: route.id, sec, text, markId: markId || null };
  rail.pinnedQuestions = localQuestions(text, hints);
  rail.showing = null;
  showRail();
  renderRail();
  const inp = document.getElementById("railin");
  if (inp) inp.focus();
}
function unpin(redraw) {
  rail.pinned = null;
  rail.pinnedQuestions = null;
  unpick();
  if (redraw !== false) renderRail();
}
function unpick() {
  document.querySelectorAll(".prose .picked").forEach(n => n.classList.remove("picked"));
}
/* the "?" beside a section heading: the whole section becomes the subject */
function askSection(mid, i) {
  const m = byId(mid),
    sec = m && m.sections[i];
  if (!sec) return;
  const txt = sec.text.length > 1500 ? sec.text.slice(0, 1500) + "…" : sec.text;
  pinQuote(txt, i, [sec.h]);
}
/* a mark (highlight, note, open question) opened from the text or from Marks & questions:
   its passage is pinned and the page lands on it */
function closePanel() {
  const p = document.getElementById("panel");
  if (p) p.remove();
}
function openPanel(mid, id) {
  const mk = findMark(mid, id);
  if (!mk) return;
  showRail();
  if (route.view === "m" && route.id === mid && (route.step || 0) === 1) {
    pinQuote(mk.text, mk.sec, null, id);
    jumpToPassage(mid, mk.sec, id);
    return;
  }
  rail.pendingPin = { mid, sec: mk.sec, text: mk.text, markId: id };
  jumpToPassage(mid, mk.sec, id);
}

/* ---------- render ---------- */
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
function isRoleplay(c) {
  return !!(c && c.kind === "rp");
}
function renderRail() {
  const el = document.getElementById("rail");
  if (!el || route.view !== "m") return;
  const m = byId(route.id);
  if (!m) return;
  if (rail.pendingPin && rail.pendingPin.mid === m.id) {
    rail.pinned = rail.pendingPin;
    rail.pinnedQuestions = localQuestions(rail.pinned.text);
    rail.showing = null;
  }
  rail.pendingPin = null;
  const c = convoShown();
  const old = document.getElementById("railin");
  const draft = old ? old.value : "";
  const placeholder = isRoleplay(c)
    ? "Say what you would actually say…"
    : placeNow().step === "read"
      ? "Ask about this section…"
      : "Ask about this step…";
  el.innerHTML = `
    <div class="railgrip" id="railgrip" title="Drag to resize"></div>
    <div class="railhead" id="railhead"></div>
    <div class="railbody" id="railbody"></div>
    <div class="chatmenu hidden" id="chatmenu"></div>
    <div class="railfoot">
      <div class="row">
        <textarea id="railin" rows="1" placeholder="${placeholder}"></textarea>
        <button class="btn primary" id="railsend" onclick="railSend()" aria-label="Send">↑</button>
      </div>
      <div style="display:flex;gap:8px;align-items:center;margin-top:7px">
        <span style="font-size:11px;color:var(--muted)">${connMode() === "none" ? "not connected" : "⌘/Ctrl+↵ to send"}</span>
        ${c && c.msgs.length ? `<button class="btn sm ghost" style="margin-left:auto;font-size:11.5px" onclick="compactConvo('${c.id}')" title="Summarise this chat and continue in a fresh one">Compact</button>` : ""}
      </div>
    </div>`;
  renderRailHead();
  renderRailBody();
  bindRailGrip();
  const inp = document.getElementById("railin");
  inp.value = draft;
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
  const place = placeNow(),
    c = convoShown();
  const title = c ? convoTitle(c) : placeLabel(place);
  const secNo = c ? (placeOf(c).step === "read" ? placeOf(c).sec : null) : place.sec;
  const where = c && !hasPlace(c) ? "Whole module" : place.step === "read" ? "Reading" : "Step";
  const others = convosFor(m.id).length;
  h.innerHTML = `
    <div class="railtop">
      <span class="dotstat ${connMode() !== "none" ? "on" : ""}" title="${connMode() !== "none" ? "Connected" : "Not connected"}"></span>
      <button class="convobtn" onclick="toggleChatMenu()" title="Chats in this module — one per section and per step">
        <span class="ct">${secNo != null ? `<span class="secno">§${secNo + 1}</span> ` : ""}${esc(title)}</span><span class="cv">▾</span>
      </button>
      <button class="iconbtn" style="width:28px;height:28px" title="New chat here" aria-label="New chat" onclick="startNew()">${ico("plus", 15)}</button>
      <button class="iconbtn" style="width:28px;height:28px" title="Hide (a)" aria-label="Hide the tutor" onclick="toggleRail()">${ico("close", 14)}</button>
    </div>
    <div class="railctx">
      ${isRoleplay(c) ? `<div class="rpbar"><span class="tag warn">role-play</span><span style="flex:1;font-size:12.5px;color:var(--text-2)">${c.finished ? "Finished — feedback below" : "Claude is the other side"}</span>${c.finished ? "" : `<button class="btn sm primary" onclick="finishRoleplay('${m.id}')">Finish &amp; get feedback</button>`}</div>` : ""}
      ${
        rail.pinned
          ? `<div class="pinned"><span class="tag acc">selection</span>
             <button class="iconbtn" style="width:22px;height:22px" title="Unpin" aria-label="Unpin the selection" onclick="unpin()">${ico("close", 12)}</button>
             <div class="ptext">${esc(rail.pinned.text.length > 220 ? rail.pinned.text.slice(0, 220) + "…" : rail.pinned.text)}</div></div>`
          : `<div class="ctxline">${where} · <b>${esc(placeLabel(place))}</b>${others > 1 ? ` · ${others} chats in this module` : ""}</div>`
      }
    </div>`;
}
function toggleChatMenu() {
  rail.menuOpen = !rail.menuOpen;
  renderChatMenu();
}
/* The menu: this module's sections and steps, each with its chat, then the chats that
   belong to no place, then the newest chats of other modules. Picking a row goes there. */
function renderChatMenu() {
  const el = document.getElementById("chatmenu");
  if (!el) return;
  el.classList.toggle("hidden", !rail.menuOpen);
  if (!rail.menuOpen) return;
  const m = byId(route.id);
  const cur = convoShown(),
    place = placeNow();
  const asked = c => (c ? c.msgs.filter(x => x.r === "u").length : 0);
  const count = c =>
    asked(c) ? `${asked(c)} question${asked(c) === 1 ? "" : "s"}` : "no questions yet";
  const del = c =>
    c
      ? `<button class="iconbtn" style="width:24px;height:24px" title="Delete" aria-label="Delete" onclick="deleteConvo('${c.id}')">${ico("trash", 12)}</button>`
      : "";
  const placeRow = (p, label, here) => {
    const c = convoAt(p);
    const on = cur ? c && c.id === cur.id : samePlace(p, place);
    return `<div class="crow ${on ? "on" : ""}">
      <button class="cmain" onclick="openPlace(${esc(JSON.stringify(p))})" title="Open this and its chat">
        <span class="t">${label}</span>
        <span class="s">${count(c)}${here ? " · in view" : ""}</span>
      </button>${del(c)}</div>`;
  };
  const secRows = m.sections
    .map((s, i) =>
      placeRow(
        { mid: m.id, step: "read", sec: i },
        `<span class="secno">§${i + 1}</span> ${esc(s.h)}`,
        place.step === "read" && place.sec === i
      )
    )
    .join("");
  const stepRows = STEPS.filter(
    s => s.k !== "read" && (s.k === place.step || convoAt({ mid: m.id, step: s.k, sec: null }))
  )
    .map(s => placeRow({ mid: m.id, step: s.k, sec: null }, esc(s.n), s.k === place.step))
    .join("");
  const convoRow = c => `<div class="crow ${cur && c.id === cur.id ? "on" : ""}">
      <button class="cmain" onclick="switchConvo('${c.id}')">
        <span class="t">${c.mid !== m.id ? `<span class="secno">${c.mid}</span> ` : ""}${esc(convoTitle(c))}</span>
        <span class="s">${count(c)} · ${new Date(c.updated).toLocaleDateString()}${c.parent ? " · carried over" : ""}</span>
      </button>
      <button class="iconbtn" style="width:24px;height:24px" title="Rename" aria-label="Rename" onclick="renameConvo('${c.id}')">${ico("pencil", 12)}</button>
      ${del(c)}</div>`;
  const loose = convosFor(m.id).filter(c => !hasPlace(c));
  const others = allConvos()
    .filter(c => c.mid !== m.id && (c.msgs.length || c.summary))
    .slice(0, 8);
  el.innerHTML = `
    <div class="cmhead">${m.id} · ${esc(m.short || m.title)} — by section</div>
    ${secRows}
    ${stepRows ? `<div class="cmhead">By step</div>` + stepRows : ""}
    ${loose.length ? `<div class="cmhead">Whole module</div>` + loose.map(convoRow).join("") : ""}
    ${others.length ? `<div class="cmhead">Other modules</div>` + others.map(convoRow).join("") : ""}
    <div class="cmfoot">
      <button class="btn sm" onclick="startNew()">${ico("plus", 13)} New chat here</button>
      ${cur && cur.msgs.length ? `<button class="btn sm" onclick="compactConvo('${cur.id}')">Compact into a new chat</button>` : ""}
      <button class="btn sm ghost" onclick="go('#/marks')">All conversations</button>
    </div>`;
}
/* a conversation picked from the menu or the Marks page: go to its place and show it */
function switchConvo(id) {
  const c = convos()[id];
  if (!c) return;
  openPlace(placeOf(c), id);
}
/* a fresh conversation at this place; the one it replaces stays in the menu */
function startNew() {
  const cur = convoShown();
  rail.menuOpen = false;
  if (!cur || (!cur.msgs.length && !cur.summary)) {
    renderRail();
    toast("This chat is already empty");
    return;
  }
  const c = newConvo(placeNow());
  rail.showing = c.id;
  renderRail();
  toast("New chat");
}
function renderRailBody() {
  const b = document.getElementById("railbody");
  if (!b) return;
  const m = byId(route.id);
  if (!m) return;
  const c = convoShown();
  let h = "";
  if (connMode() === "none") {
    h += `<div class="warnbar" style="margin:0 0 12px"><span>Not connected to Claude.</span>
      <button class="btn sm" onclick="go('#/settings')">Connect</button></div>`;
  }
  if (c && c.summary) {
    h += `<div class="carried"><b>Carried over${c.parent && convos()[c.parent] ? " from “" + esc(convoTitle(convos()[c.parent])) + "”" : ""}</b>
      <div>${esc(c.summary)}</div></div>`;
  }
  h += `<div class="thread" id="railthread">`;
  if (rail.compacting) h += `<div class="msg a typing"><i></i><i></i><i></i></div>`;
  (c ? c.msgs : []).forEach((x, i) => {
    h += `<div class="msg ${x.r === "u" ? "u" : x.r === "e" ? "a err" : "a"}">
      ${x.r === "u" && messageLabel(m, x) ? `<button class="msgctx" onclick="jumpToMessage('${c.id}',${i})" title="Go to this part of the module">${esc(messageLabel(m, x))}${x.quote ? " · selection" : ""} ↗</button>` : ""}
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
/* where a message was asked from, for the label above it */
function messageLabel(m, x) {
  if (x.sec != null && m.sections[x.sec]) return m.sections[x.sec].h;
  if (x.step && x.step !== "read") return stepNamed(x.step);
  return "";
}
function jumpToMessage(cid, i) {
  const c = convos()[cid],
    x = c && c.msgs[i];
  if (!x) return;
  if (x.sec != null) jumpToPassage(c.mid, x.sec, x.mark || null);
  else if (x.step) openPlace({ mid: c.mid, step: x.step, sec: null }, c.id);
}
function renderSuggest() {
  const box = document.getElementById("railsuggest");
  const m = byId(route.id);
  if (!m) return;
  const place = placeNow(),
    c = convoShown();
  if (box) {
    const gaps = rail.pinned ? [] : gapChips(m.id);
    const chip = (q, cls, title) =>
      `<button class="chip ${cls}" onclick="askThis(this)" data-q="${esc(q)}" ${title ? `title="${title}"` : ""}>${esc(q)}</button>`;
    const tools = rail.pinned
      ? `<button class="chip gen" onclick="genQuestions()" ${rail.generating ? "disabled" : ""}>
          ${rail.generating ? "Thinking of better questions…" : "✦ Ask Claude for sharper questions"}</button>`
      : place.step === "read"
        ? `<div class="toolchips">${TOOL_CHIPS.map(([l, q]) => `<button class="chip tool" onclick="askThis(this)" data-q="${esc(q)}">${l}</button>`).join("")}</div>`
        : "";
    box.innerHTML = isRoleplay(c)
      ? ""
      : gaps.map(q => chip(q, "gap", "From what you missed or asked before")).join("") +
        placeSuggestions(m, place)
          .map(q => chip(q, ""))
          .join("") +
        tools;
  }
  const lead = document.getElementById("raillead2");
  if (lead)
    lead.innerHTML = isRoleplay(c)
      ? `<p class="sub" style="font-size:12px;margin:0 0 8px">In character. Write "pause" to step out. When you are done, press <b>Finish &amp; get feedback</b> above.</p>`
      : `<p class="sub" style="font-size:12px;margin:0 0 8px">${
          rail.pinned
            ? "Questions about <b>the passage you picked</b>:"
            : "Questions worth asking about <b>" + esc(placeLabel(place)) + "</b>:"
        }</p>`;
}
function askThis(el) {
  const inp = document.getElementById("railin");
  inp.value = el.dataset.q;
  railSend();
}
/* Send what is in the box. The conversation is the one on show, or a new one at this
   place; the tutor's instructions are built for this place at this moment. */
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
  const place = placeNow();
  const c = convoShown() || newConvo(place);
  rail.showing = c.id;
  const markId = rail.pinned ? rail.pinned.markId : null;
  c.msgs.push({
    r: "u",
    t: text,
    ts: Date.now(),
    step: place.step,
    sec: place.sec,
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
    const reply = await askBridge(systemForRail(m, c, place), msgs);
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
  if (route.view !== "m") return;
  renderRail();
  if (convoShown() !== c) toast("Claude replied in “" + convoTitle(c) + "”");
  const i2 = document.getElementById("railin");
  if (i2) i2.focus();
}
