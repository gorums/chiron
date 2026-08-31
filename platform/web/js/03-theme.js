/* ============================ theme ============================ */
function applyTheme() {
  if (S.theme) document.documentElement.setAttribute("data-theme", S.theme);
  else document.documentElement.removeAttribute("data-theme");
}
function cycleTheme() {
  const cur = S.theme;
  S.theme = cur === null ? "light" : (cur === "light" ? "dark" : null);
  save(); applyTheme();
  toast("Theme: " + (S.theme || "system"));
}
applyTheme();
