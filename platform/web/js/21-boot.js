/* ---------- boot ---------- */
function render() {
  if (route.view !== "m") stopTimer();
  closePanel();
  clearSel();
  if (!(route.view === "m" && route.step === 2) && !(route.view === "check" && route.id === "run"))
    QUIZ = null;
  renderSidebar();
  const v = route.view;
  if (v === "m") viewModule();
  else if (v === "review") viewReview();
  else if (v === "check") viewCheck();
  else if (v === "stats") viewStats();
  else if (v === "record") viewRecord();
  else if (v === "learner") viewLearner();
  else if (v === "marks") viewMarks();
  else if (v === "settings") viewSettings();
  else if (v === "library") viewLibrary();
  else if (v === "plan") viewPlan();
  else viewHome();
  $("#sidebar").classList.remove("open");
  applyRail();
  const tg = document.getElementById("railtoggle");
  if (tg) tg.classList.toggle("show", route.view === "m");
  railRouteChanged();
}
/* the left sidebar: a slide-over on a narrow screen, hideable on a wide one */
function isNarrow() {
  return window.innerWidth <= 860;
}
function applySide() {
  document.body.classList.toggle("side-off", !!(STATE.ui && STATE.ui.sideOff));
  applyRail();
}
function toggleSidebar() {
  if (isNarrow()) {
    $("#sidebar").classList.toggle("open");
    return;
  }
  if (!STATE.ui) STATE.ui = {};
  STATE.ui.sideOff = !STATE.ui.sideOff;
  save();
  applySide();
}
$("#opensearch").onclick = openPalette;
$("#themebtn").onclick = cycleTheme;
$("#helpbtn").onclick = openHelp;
$("#menubtn").onclick = toggleSidebar;
parseHash();
// Who is reading (Studio may have switched profiles), then the platform copy of their
// progress, so the first paint is right. Device settings are applied once STATE is final.
profileInit()
  .then(() => {
    applySide();
    migrateChats();
    applyReading();
    return syncPull();
  })
  .finally(() => {
    render();
    setTimeout(() => checkBridge(true), 250);
    setTimeout(notifyDue, 1500);
  });
