/* ============================ theme ============================
   The theme is a device setting, not progress, so it never syncs. It is kept under the one
   platform key, which Studio writes too: opening a course from a dark Studio must not hand
   the reader a light page. `STATE.theme` is still read for a page opened off disk, and for
   saves made before the shared key existed. */
const THEME_KEY = "platform_theme";
const THEME_NAMES = { dark: "dark", light: "light", "": "your system's setting" };
function savedTheme() {
  try {
    const shared = localStorage.getItem(THEME_KEY);
    if (shared !== null) return shared || null;
  } catch (e) {
    /* private mode */
  }
  return STATE.theme || null;
}
function applyTheme() {
  const t = savedTheme();
  if (t) document.documentElement.setAttribute("data-theme", t);
  else document.documentElement.removeAttribute("data-theme");
  const b = document.getElementById("themebtn");
  if (b) {
    const hint = "Theme: " + THEME_NAMES[t || ""] + ". Click for the next one (t)";
    b.setAttribute("data-help", hint);
    b.setAttribute("aria-label", hint);
  }
}
function cycleTheme() {
  const cur = savedTheme();
  STATE.theme = cur === null ? "light" : cur === "light" ? "dark" : null;
  try {
    localStorage.setItem(THEME_KEY, STATE.theme || "");
  } catch (e) {
    /* private mode */
  }
  save();
  applyTheme();
  toast("Theme: " + THEME_NAMES[STATE.theme || ""]);
}
applyTheme();
