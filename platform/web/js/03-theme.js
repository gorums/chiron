/* ============================ theme ============================ */
function applyTheme() {
  if (STATE.theme) document.documentElement.setAttribute("data-theme", STATE.theme);
  else document.documentElement.removeAttribute("data-theme");
}
function cycleTheme() {
  const cur = STATE.theme;
  STATE.theme = cur === null ? "light" : cur === "light" ? "dark" : null;
  save();
  applyTheme();
  toast("Theme: " + (STATE.theme || "system"));
}
applyTheme();
