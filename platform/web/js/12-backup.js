/* ---------- data backup ---------- */
function openData() {
  const json = JSON.stringify(S);
  showModal(`<h3 style="font-family:var(--serif);font-size:22px;margin:0 0 8px;font-weight:600">Backup &amp; restore</h3>
  <p class="sub" style="margin-bottom:14px">Your progress lives in this browser only. Copy this text somewhere safe if you care about it, or paste a previous backup in to restore.</p>
  <textarea id="dumpta" rows="6" style="font-family:var(--mono);font-size:11px">${esc(json)}</textarea>
  <div style="display:flex;gap:9px;margin-top:12px;flex-wrap:wrap">
    <button class="btn" onclick="copyDump()">Copy backup</button>
    <button class="btn" onclick="restore()">Restore from pasted text</button>
    <button class="btn ghost" style="margin-left:auto;color:var(--bad)" onclick="wipe()">Erase all progress</button>
  </div>`);
}
function copyDump() {
  const ta = $("#dumpta"); ta.select();
  try { navigator.clipboard.writeText(ta.value); toast("Copied"); }
  catch (e) { try { document.execCommand("copy"); toast("Copied"); } catch (e2) { toast("Select the text and copy manually"); } }
}
function restore() {
  try {
    const o = JSON.parse($("#dumpta").value);
    if (!o || typeof o !== "object") throw 0;
    S = Object.assign(blank(), o); save(); closeModal(); applyTheme(); render(); toast("Progress restored");
  } catch (e) { toast("That is not valid backup text"); }
}
function wipe() {
  if (!confirm("Erase all progress, notes, answers and flashcard scheduling? This cannot be undone.")) return;
  S = blank(); save(); closeModal(); render(); toast("Everything reset");
}
