/* ---------- keys ---------- */
document.addEventListener("keydown", e => {
  const tag = (e.target.tagName || "").toLowerCase();
  const typing = tag === "input" || tag === "textarea";
  if (e.key === "Escape") { closeModal(); closePanel(); clearSel(); $("#sidebar").classList.remove("open"); return; }
  if (typing) return;
  if (e.key === "/") { e.preventDefault(); openPalette(); return; }
  if (e.key === "?") { openHelp(); return; }
  if (e.key === "t") { cycleTheme(); return; }
  if (e.key === "a" && route.v === "m") { toggleRail(); return; }
  if (e.key === "i" && route.v === "m") { const el = document.getElementById("railin"); if (el) { el.focus(); e.preventDefault(); } return; }
  if ($("#modalhost").innerHTML) return;
  if (route.v === "review" && session) {
    if (e.key === " ") { e.preventDefault(); if (!session.flipped) flip(); return; }
    if (session.flipped && ["1", "2", "3", "4"].includes(e.key)) { rate(+e.key - 1); return; }
  }
  if (route.v === "m") {
    const m = byId(route.id), p = P(route.id);
    if (route.step === 2 && p.quiz && !p.quiz.finished) {
      const st = p.quiz.a[p.quiz.i];
      if (!st || st.pick == null) {
        const i = "abcd".indexOf(e.key.toLowerCase());
        if (i >= 0 || ["1", "2", "3", "4"].includes(e.key)) { pick(route.id, i >= 0 ? i : +e.key - 1); return; }
      } else if (!st.answered && ["1", "2", "3"].includes(e.key)) { answer(route.id, +e.key); return; }
      else if (st.answered && e.key === "Enter") { nextQ(route.id); return; }
    }
    const i = mIndex(route.id);
    if (e.key === "j" && MODS[i + 1]) go("#/m/" + MODS[i + 1].id);
    if (e.key === "k" && MODS[i - 1]) go("#/m/" + MODS[i - 1].id);
  } else {
    if (e.key === "j" || e.key === "k") go("#/m/" + MODS[0].id);
  }
});
window.addEventListener("scroll", () => {
  const h = document.body.scrollHeight - window.innerHeight;
  $("#readbar").style.width = (h > 0 ? Math.min(100, window.scrollY / h * 100) : 0) + "%";
});
window.addEventListener("beforeunload", save);
document.addEventListener("visibilitychange", () => { if (document.hidden) save(); });
