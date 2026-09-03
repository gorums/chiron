/* ---------- boot ---------- */
function render() {
  if (route.v !== "m") stopTimer();
  closePanel(); clearSel();
  if (route.v !== "m") pinned = null;
  if (!(route.v === "m" && route.step === 2) && !(route.v === "check" && route.id === "run")) QZ = null;
  renderSidebar();
  const v = route.v;
  if (v === "m") viewModule();
  else if (v === "review") viewReview();
  else if (v === "check") viewCheck();
  else if (v === "stats") viewStats();
  else if (v === "record") viewRecord();
  else if (v === "marks") viewMarks();
  else if (v === "settings") viewSettings();
  else if (v === "library") viewLibrary();
  else if (v === "plan") viewPlan();
  else viewHome();
  $("#sidebar").classList.remove("open");
  applyRail();
  const tg = document.getElementById("railtoggle");
  if (tg) tg.classList.toggle("show", route.v === "m");
  if (route.v === "m" && railOpen()) renderRail();
}
/* the left sidebar: a slide-over on a narrow screen, hideable on a wide one */
function isNarrow() { return window.innerWidth <= 860; }
function applySide() { document.body.classList.toggle("side-off", !!(S.ui && S.ui.sideOff)); applyRail(); }
function toggleSidebar() {
  if (isNarrow()) { $("#sidebar").classList.toggle("open"); return; }
  if (!S.ui) S.ui = {};
  S.ui.sideOff = !S.ui.sideOff; save(); applySide();
}
$("#opensearch").onclick = openPalette;
$("#themebtn").onclick = cycleTheme;
$("#helpbtn").onclick = openHelp;
$("#menubtn").onclick = toggleSidebar;
applySide();
migrateChats();
applyReading();
parseHash();
// Pull the platform copy of progress first, when there is one, so the first paint is right.
syncPull().finally(() => { render(); setTimeout(() => checkBridge(true), 250); setTimeout(notifyDue, 1500); });
