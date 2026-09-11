/* ---- conversations with the tutor: the model behind the chat rail ----

   Every conversation is stored in STATE.convos[id]:
     { id, mid, step, sec, kind, msgs, created, updated, parent, summary, title }
   `mid` is the module it belongs to. `step` and `sec` are its *place*: the step key from
   STEPS ("read", "elab", ...) and, on the Read step, the section index. A chat with no
   place (`step` null: role-plays, chats carried over from before places existed, a
   compacted whole-module chat) belongs to the module as a whole. `kind` is "rp" for a
   role-play.

   A message is { r, t, ts }: `r` is the role ("u" the reader, "a" the tutor, "e" an
   error), `t` the text, `ts` when. A reader's message also records where it was asked
   (`step`, `sec`, and `quote` + `mark` when it came from a selected passage). These short
   keys are a stored contract - old saves carry them - so they are not renamed here.

   There is no stored "active" conversation. The rail shows the newest conversation at
   the place the reader is looking at (`convoAt`), and a conversation the reader picked
   by hand (`rail.showing`) only until they move somewhere else. An `active` map that old
   saves still carry is ignored and no longer maintained. */
function convos() {
  if (!STATE.convos) STATE.convos = {};
  return STATE.convos;
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

/* ---- places ----
   A place is { mid, step, sec }: `step` a STEPS key, `sec` a section index on the Read
   step and null elsewhere. `step` null means "nowhere in particular": the module as a
   whole. */
function placeOf(c) {
  const step = c.step || (c.sec != null ? "read" : null);
  return { mid: c.mid, step, sec: c.sec != null ? c.sec : null };
}
function samePlace(a, b) {
  return !!a && !!b && a.mid === b.mid && a.step === b.step && a.sec === b.sec;
}
function hasPlace(c) {
  return c.kind !== "rp" && placeOf(c).step != null;
}
/* the newest ordinary conversation at a place, or null: an empty chat is never stored */
function convoAt(place) {
  const here = Object.values(convos()).filter(c => c.kind !== "rp" && samePlace(placeOf(c), place));
  here.sort((a, b) => b.updated - a.updated);
  return here[0] || null;
}
function convoTitle(c) {
  if (c.title) return c.title;
  const place = placeOf(c);
  if (place.step) return placeLabel(place);
  const first = (c.msgs || []).find(m => m.r === "u");
  if (first) return first.t.length > 46 ? first.t.slice(0, 46) + "…" : first.t;
  return c.summary ? "Continued conversation" : "New chat";
}
function newConvo(place, opts) {
  const id = newId();
  const c = {
    id,
    mid: place.mid,
    step: place.step || null,
    sec: place.sec != null ? place.sec : null,
    msgs: [],
    created: Date.now(),
    updated: Date.now(),
    parent: (opts && opts.parent) || null,
    summary: (opts && opts.summary) || "",
    title: (opts && opts.title) || "",
  };
  if (opts && opts.kind) c.kind = opts.kind;
  convos()[id] = c;
  save();
  return c;
}
function deleteConvo(id) {
  const c = convos()[id];
  if (!c) return;
  confirmModal(
    "Delete this conversation?",
    "It cannot be undone.",
    "Delete",
    () => {
      delete convos()[id];
      forget(id);
      if (rail.showing === id) rail.showing = null;
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

/* compaction: carry the substance forward into a fresh conversation at the same place */
async function compactConvo(id) {
  const c = convos()[id] || convoShown();
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
    const fresh = newConvo(placeOf(c), {
      parent: c.id,
      summary: summary.trim(),
      title: "Continued: " + convoTitle(c).slice(0, 40),
    });
    rail.showing = fresh.id;
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
