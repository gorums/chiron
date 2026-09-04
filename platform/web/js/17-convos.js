/* ---- conversations with the tutor: the model behind the chat rail ----

   Every conversation is stored in STATE.convos[id]:
     { id, mid, sec, kind, msgs, created, updated, parent, summary, title }
   `mid` is the module it belongs to; `sec` the section index it follows (null for a
   module-wide chat); `kind` is "rp" for a role-play. STATE.active[mid] names the
   conversation the rail shows for that module.

   A message is { r, t, ts }: `r` is the role ("u" the reader, "a" the tutor, "e" an
   error), `t` the text, `ts` when. These short keys are a stored contract - old saves
   carry them - so they are not renamed here. */
function convos() {
  if (!STATE.convos) STATE.convos = {};
  return STATE.convos;
}
function activeConvoIds() {
  if (!STATE.active) STATE.active = {};
  return STATE.active;
}
function migrateChats() {
  if (!STATE.chats || STATE._migrated) return;
  Object.keys(STATE.chats).forEach(mid => {
    const msgs = STATE.chats[mid] || [];
    if (!msgs.length) return;
    const id = newId();
    convos()[id] = {
      id,
      mid,
      msgs,
      created: msgs[0].ts || Date.now(),
      updated: msgs[msgs.length - 1].ts || Date.now(),
      parent: null,
      summary: "",
      title: "",
    };
    activeConvoIds()[mid] = id;
  });
  STATE._migrated = true;
  save();
}
function newId() {
  return "c" + Date.now().toString(36) + Math.floor(Math.random() * 1e4).toString(36);
}
function convosFor(mid) {
  return Object.values(convos())
    .filter(c => c.mid === mid)
    .sort((a, b) => b.updated - a.updated);
}
function allConvos() {
  return Object.values(convos()).sort((a, b) => b.updated - a.updated);
}
/* A chat is either about one section of its module (`sec` is the section index) or about
   the module as a whole (`sec` is null: older chats, "New chat", role-plays). Section
   chats follow the reader down the page; module-wide chats stay put. */
function secConvo(mid, i) {
  return Object.values(convos()).find(c => c.mid === mid && c.sec === i && c.kind !== "rp") || null;
}
function chatSec(c) {
  return c && c.sec != null ? c.sec : rail.section;
}
/* section chats are made as the reader scrolls, so the empty ones are dropped again */
function pruneEmpty(mid, keepId) {
  Object.values(convos()).forEach(c => {
    if (c.mid !== mid || c.id === keepId || c.msgs.length || c.summary || c.kind === "rp") return;
    delete convos()[c.id];
    if (activeConvoIds()[mid] === c.id) delete activeConvoIds()[mid];
  });
}
function convoTitle(c) {
  if (c.title) return c.title;
  if (c.sec != null) {
    const m = byId(c.mid),
      s = m && m.sections[c.sec];
    if (s) return s.h;
  }
  const first = (c.msgs || []).find(m => m.r === "u");
  if (first) return first.t.length > 46 ? first.t.slice(0, 46) + "…" : first.t;
  return c.summary ? "Continued conversation" : "New chat";
}
function activeConvo(mid, create) {
  const id = activeConvoIds()[mid];
  if (id && convos()[id]) return convos()[id];
  // nothing chosen yet: the chat about the section in view, when that module is open
  const sec = route.view === "m" && route.id === mid ? rail.section : null;
  const own = sec != null ? secConvo(mid, sec) : null;
  if (own) {
    activeConvoIds()[mid] = own.id;
    return own;
  }
  const existing = convosFor(mid)[0];
  if (existing) {
    activeConvoIds()[mid] = existing.id;
    return existing;
  }
  if (create === false) return null;
  return newConvo(mid, sec != null ? { sec } : null);
}
/* the reader scrolled to section i: a section chat moves with them, unless a reply is
   on its way or the section was just picked from the menu (the smooth scroll passes
   through the sections in between) */
function followSection(mid, i) {
  if (rail.sending || Date.now() < rail.sectionLockUntil) return false;
  const c = activeConvo(mid, false);
  if (c && (c.sec == null || c.sec === i)) return false;
  const next = secConvo(mid, i) || newConvo(mid, { sec: i });
  activeConvoIds()[mid] = next.id;
  pruneEmpty(mid, next.id);
  save();
  return true;
}
/* from the menu at the top of the rail: that section's chat, and the page scrolled to it */
function pickSection(mid, i) {
  const next = secConvo(mid, i) || newConvo(mid, { sec: i });
  activeConvoIds()[mid] = next.id;
  pruneEmpty(mid, next.id);
  save();
  rail.section = i;
  lockSectionFollowing();
  rail.menuOpen = false;
  rail.pinned = null;
  rail.pinnedQuestions = null;
  document.querySelectorAll(".prose .picked").forEach(n => n.classList.remove("picked"));
  renderRail();
  jumpToPassage(mid, i, null);
}
function newConvo(mid, opts) {
  const id = newId();
  convos()[id] = {
    id,
    mid,
    msgs: [],
    created: Date.now(),
    updated: Date.now(),
    parent: (opts && opts.parent) || null,
    summary: (opts && opts.summary) || "",
    title: (opts && opts.title) || "",
    sec: opts && opts.sec != null ? opts.sec : null,
  };
  activeConvoIds()[mid] = id;
  save();
  return convos()[id];
}
function switchConvo(id) {
  const c = convos()[id];
  if (!c) return;
  activeConvoIds()[c.mid] = id;
  pruneEmpty(c.mid, id);
  save();
  rail.menuOpen = false;
  renderRail();
}
function deleteConvo(id) {
  const c = convos()[id];
  if (!c) return;
  confirmModal(
    "Delete this conversation?",
    "It cannot be undone.",
    "Delete",
    () => {
      const mid = c.mid;
      delete convos()[id];
      forget(id);
      if (activeConvoIds()[mid] === id) delete activeConvoIds()[mid];
      save();
      rail.menuOpen = false;
      if (route.view === "m") renderRail();
      else render();
      toast("Conversation deleted");
    },
    true
  );
}
function renameConvo(id) {
  const c = convos()[id];
  if (!c) return;
  promptModal("Name this conversation", convoTitle(c), "Save", t => {
    c.title = t.trim().slice(0, 70);
    save();
    if (route.view === "m") renderRail();
    else render();
  });
}

/* compaction: carry the substance forward into a fresh conversation */
async function compactConvo(id) {
  const c = convos()[id] || activeConvo(route.id, false);
  if (!c || !c.msgs.length || rail.compacting) return;
  if (connMode() === "none") {
    toast("Not connected — open Settings");
    return;
  }
  rail.compacting = true;
  rail.menuOpen = false;
  renderRail();
  try {
    const transcript = c.msgs
      .filter(m => m.r !== "e")
      .map(m => (m.r === "u" ? "LEARNER: " : "TUTOR: ") + m.t)
      .join("\n\n");
    const sys =
      "You compress a tutoring conversation into a handover brief for the next conversation, written for the tutor who picks it up. Under 180 words. Cover: what was actually settled, the learner's own situation as revealed, any conclusion or decision reached, and what is still open or confusing. No preamble, no headings, plain prose. Do not repeat explanations — record outcomes.";
    const summary = await askBridge(sys, [
      { role: "user", content: transcript.slice(-TUTOR.summaryChars) },
    ]);
    const fresh = newConvo(c.mid, {
      parent: c.id,
      summary: summary.trim(),
      title: "Continued: " + convoTitle(c).slice(0, 40),
    });
    rail.compacting = false;
    renderRail();
    toast("Carried the important parts into a new chat");
    return fresh;
  } catch (e) {
    rail.compacting = false;
    renderRail();
    toast((e && e.message) || "Could not compact this conversation");
  }
}
