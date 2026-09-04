/* ---- selection toolbar ---- */
let selCtx = null,
  currentPanelMid = null,
  currentPanelId = null;
function killBar() {
  const b = document.getElementById("selbar");
  if (b) b.remove();
}
function clearSel() {
  killBar();
  selCtx = null;
}
function handleSel() {
  if (route.view !== "m" || route.step !== 1) return;
  const s = window.getSelection();
  if (!s || s.isCollapsed) return clearSel();
  const text = s.toString().replace(/\s+/g, " ").trim();
  if (text.length < 4 || text.length > 900) return clearSel();
  const r = s.getRangeAt(0);
  let host = r.commonAncestorContainer;
  if (host.nodeType === 3) host = host.parentElement;
  const sec = host.closest ? host.closest(".sec") : null;
  if (!sec) return clearSel();
  const secIdx = +sec.id.replace("sec", "");
  const raw = s.toString();
  killBar();
  selCtx = { mid: route.id, sec: secIdx, text: raw.trim() };
  const rect = (r.getBoundingClientRect ? r.getBoundingClientRect() : null) || {
    left: 0,
    top: 0,
    width: 0,
  };
  const bar = document.createElement("div");
  bar.className = "selbar";
  bar.id = "selbar";
  bar.style.left = rect.left + rect.width / 2 + window.scrollX + "px";
  bar.style.top = rect.top + window.scrollY - 10 + "px";
  bar.innerHTML = `<button onclick="doMark('hl')">★ Highlight</button>
    <span class="div"></span><button onclick="doMark('note')">✎ Note</button>
    <span class="div"></span><button onclick="doMark('q')">⚑ Open question</button>
    <span class="div"></span><button onclick="doMark('ask')">? Ask Claude</button>`;
  document.body.appendChild(bar);
}
function doMark(kind) {
  if (!selCtx) return;
  const { mid, sec, text } = selCtx;
  try {
    const s = window.getSelection();
    if (s) s.removeAllRanges();
  } catch (e) {}
  killBar();
  if (kind === "ask") {
    // straight into the rail, no clutter saved
    selCtx = null;
    pinQuote(text, sec);
    return;
  }
  const m = addMark(mid, sec, text, kind === "q" ? "open" : "hl");
  selCtx = null;
  renderStep(byId(mid), 1);
  renderSidebar();
  if (kind === "hl") toast("Highlighted");
  else if (kind === "q") {
    toast("Marked as an open question");
    openNote(mid, m.id);
  } else openNote(mid, m.id);
}
document.addEventListener("mouseup", e => {
  if (e.target.closest && e.target.closest(".selbar")) return;
  setTimeout(handleSel, 10);
});
document.addEventListener("touchend", () => setTimeout(handleSel, 60));
document.addEventListener("mousedown", e => {
  if (!(e.target.closest && e.target.closest(".selbar"))) clearSel();
});
document.addEventListener("click", e => {
  if (
    rail.menuOpen &&
    e.target.closest &&
    !e.target.closest(".chatmenu") &&
    !e.target.closest(".convobtn")
  ) {
    rail.menuOpen = false;
    renderChatMenu();
  }
  const mk = e.target.closest && e.target.closest("mark.hl");
  if (mk && mk.dataset.k) openPanel(route.id, mk.dataset.k, "ask");
});
