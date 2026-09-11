/* ---- where the chat rail sits: open or shut, docked right or along the bottom, how wide ----
   All of it is a device setting under STATE.ui, which never leaves the browser. The rail's
   contents are tutor/rail.js. */
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
/* open the rail if it is shut, without redrawing it: the caller draws */
function showRail() {
  if (railOpen()) return;
  if (!STATE.ui) STATE.ui = {};
  STATE.ui.rail = true;
  save();
  applyRail();
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
  // On a narrow screen the rail covers the page, so it needs the same scrim the sidebar
  // gets: something to tap to get out of, and the page behind held still.
  if (narrow && show && pos !== "bottom") showScrim(toggleRail);
  else if (!$("#sidebar").classList.contains("open")) hideScrim();
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

/* the rail is resizable: drag its inner edge. Width (or height, docked at the bottom) is
   kept per device in STATE.ui and saved as you drag, so a reload keeps it. */
let railSaveTimer = null;
function bindRailGrip() {
  const g = document.getElementById("railgrip");
  if (!g) return;
  g.setAttribute("role", "separator");
  g.setAttribute("tabindex", "0");
  g.setAttribute("aria-label", "Resize the tutor panel");
  g.setAttribute("aria-orientation", railPos() === "bottom" ? "horizontal" : "vertical");
  // Arrow keys resize it too, and Home puts it back: a drag handle that only answers a
  // mouse is a control a keyboard or a touch screen cannot reach.
  g.addEventListener("keydown", e => {
    const step = e.shiftKey ? 60 : 20;
    const bottom = railPos() === "bottom";
    const grow = bottom ? e.key === "ArrowUp" : e.key === "ArrowLeft";
    const shrink = bottom ? e.key === "ArrowDown" : e.key === "ArrowRight";
    if (!grow && !shrink && e.key !== "Home") return;
    e.preventDefault();
    if (!STATE.ui) STATE.ui = {};
    if (e.key === "Home") {
      STATE.ui.railW = LAYOUT.railDefault;
      STATE.ui.railH = LAYOUT.railHeightDefault;
    } else if (bottom) STATE.ui.railH = railHeight() + (grow ? step : -step);
    else STATE.ui.railW = railWidth() + (grow ? step : -step);
    applyRail();
    save();
  });
  g.addEventListener("touchmove", e => {
    if (!e.touches.length) return;
    if (!STATE.ui) STATE.ui = {};
    const t = e.touches[0];
    if (railPos() === "bottom") STATE.ui.railH = Math.round(window.innerHeight - t.clientY);
    else STATE.ui.railW = Math.round(window.innerWidth - t.clientX);
    applyRail();
    clearTimeout(railSaveTimer);
    railSaveTimer = setTimeout(save, 300);
  });
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
