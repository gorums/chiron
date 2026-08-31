/* ---------- boot ---------- */
function render() {
  if (route.v !== "m") stopTimer();
  closePanel(); clearSel();
  if (route.v !== "m") pinned = null;
  renderSidebar();
  const v = route.v;
  if (v === "m") viewModule();
  else if (v === "review") viewReview();
  else if (v === "stats") viewStats();
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
$("#opensearch").onclick = openPalette;
$("#themebtn").onclick = cycleTheme;
$("#helpbtn").onclick = openHelp;
$("#menubtn").onclick = () => $("#sidebar").classList.toggle("open");
migrateChats();
parseHash(); render();
setTimeout(() => checkBridge(true), 250);
