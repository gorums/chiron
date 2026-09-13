/* ---------- boot ---------- */
function render() {
  if (route.view !== "m") stopTimer();
  audioRouteChanged();
  notebookRouteChanged();
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
  closeSidebar();
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
/* On a narrow screen the sidebar covers the page, so it gets a scrim: something to tap to
   get out of, and a locked body so the page behind does not scroll away underneath. */
function openSidebar() {
  $("#sidebar").classList.add("open");
  $("#menubtn").setAttribute("aria-expanded", "true");
  showScrim(closeSidebar);
}
function closeSidebar() {
  const bar = $("#sidebar");
  if (bar) bar.classList.remove("open");
  const btn = $("#menubtn");
  if (btn) btn.setAttribute("aria-expanded", String(!isNarrow() && !(STATE.ui || {}).sideOff));
  hideScrim();
}
function toggleSidebar() {
  if (isNarrow()) {
    if ($("#sidebar").classList.contains("open")) closeSidebar();
    else openSidebar();
    return;
  }
  if (!STATE.ui) STATE.ui = {};
  STATE.ui.sideOff = !STATE.ui.sideOff;
  save();
  applySide();
  $("#menubtn").setAttribute("aria-expanded", String(!STATE.ui.sideOff));
}
/* One scrim, shared by the sidebar and the rail. `onTap` is what closes whatever it is
   covering; Escape does the same through the key handler. */
let scrimClose = null;
function showScrim(onTap) {
  scrimClose = onTap;
  let el = document.getElementById("scrim");
  if (!el) {
    el = document.createElement("button");
    el.id = "scrim";
    el.className = "scrim";
    el.setAttribute("aria-label", "Close");
    el.onclick = () => {
      if (scrimClose) scrimClose();
    };
    document.body.appendChild(el);
  }
  document.body.classList.add("locked");
}
function hideScrim() {
  const el = document.getElementById("scrim");
  if (el) el.remove();
  scrimClose = null;
  document.body.classList.remove("locked");
}
$("#opensearch").onclick = openPalette;
$("#themebtn").onclick = cycleTheme;
$("#helpbtn").onclick = openHelp;
$("#menubtn").onclick = toggleSidebar;
$("#menubtn").innerHTML = ico("menu", 18);
$("#themebtn").innerHTML = ico("theme", 17);
applyTheme();
/* Something to look at while the profile and the platform's copy of the progress arrive.
   Without it the page is blank for as long as that takes. */
function bootSkeleton() {
  $("#view").innerHTML = `<div class="wrap"><div class="skeleton">
    <div class="sk sk-title"></div><div class="sk sk-line"></div><div class="sk sk-line short"></div>
    <div class="sk sk-card"></div><div class="sk sk-card"></div></div>
    <p class="sub centered">Loading your progress…</p></div>`;
}
parseHash();
bootSkeleton();
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
