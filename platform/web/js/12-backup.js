/* ---------- data backup ---------- */
function openData() {
  const json = JSON.stringify(STATE);
  showModal(`<h3 class="h-serif">Backup &amp; restore</h3>
  <p class="sub gap-bottom">${STUDIO ? "Progress is kept on the platform while Studio serves this page. A backup is how you move it to a page opened off disk, or keep a copy of your own." : "Your progress lives in this browser only. Copy this text somewhere safe if you care about it, or paste a previous backup in to restore."}</p>
  <label class="visually-hidden" for="dumpta">Backup text</label>
  <textarea id="dumpta" class="mono dump" rows="6">${esc(json)}</textarea>
  <div class="rowline wrapped gap-top">
    <button class="btn primary" onclick="copyDump()">Copy backup</button>
    <button class="btn" onclick="askRestore()">Restore from pasted text</button>
    <button class="btn danger pushright" onclick="wipe()">Erase all progress</button>
  </div>`);
}
function copyDump() {
  const ta = $("#dumpta");
  ta.select();
  try {
    navigator.clipboard.writeText(ta.value);
    toast("Copied");
  } catch (e) {
    try {
      document.execCommand("copy");
      toast("Copied");
    } catch (e2) {
      toast("Select the text and copy manually", { kind: "bad" });
    }
  }
}
/* Restoring replaces everything, silently, and there is no undo — so it asks first, with
   what is about to be thrown away named. */
function askRestore() {
  let o;
  try {
    o = JSON.parse($("#dumpta").value);
    if (!o || typeof o !== "object" || Array.isArray(o)) throw 0;
  } catch (e) {
    toast("That is not valid backup text", { kind: "bad" });
    return;
  }
  const mods = Object.keys(o.progress || {}).length;
  confirmModal(
    "Replace your progress with this backup?",
    `Everything on this device — completion, answers, highlights, notes, conversations and card scheduling — is replaced by the pasted backup${mods ? ` (${mods} module${mods === 1 ? "" : "s"})` : ""}. There is no undo.`,
    "Replace it",
    () => restore(o),
    true
  );
}
function restore(parsed) {
  try {
    const o = parsed || JSON.parse($("#dumpta").value);
    if (!o || typeof o !== "object") throw 0;
    STATE = Object.assign(blank(), o);
    save();
    closeModal();
    applyTheme();
    render();
    toast("Progress restored");
  } catch (e) {
    toast("That is not valid backup text", { kind: "bad" });
  }
}
function wipe() {
  confirmModal(
    "Erase all progress?",
    "Notes, answers, highlights, conversations and flashcard scheduling go with it. This cannot be undone.",
    "Erase everything",
    () => {
      STATE = blank();
      save();
      render();
      toast("Everything reset");
    },
    true
  );
}
