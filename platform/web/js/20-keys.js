/* ---------- keys ---------- */
document.addEventListener("keydown", e => {
  const tag = (e.target.tagName || "").toLowerCase();
  const typing = tag === "input" || tag === "textarea" || tag === "select";
  if (e.key === "Escape") {
    closeModal();
    closePanel();
    clearSel();
    $("#sidebar").classList.remove("open");
    return;
  }
  if (typing) return;
  if (e.key === "/") {
    e.preventDefault();
    openPalette();
    return;
  }
  if (e.key === "?") {
    openHelp();
    return;
  }
  if (e.key === "t") {
    cycleTheme();
    return;
  }
  if (e.key === "s") {
    toggleSidebar();
    return;
  }
  if (e.key === "a" && route.view === "m") {
    toggleRail();
    return;
  }
  if (e.key === "i" && route.view === "m") {
    const el = document.getElementById("railin");
    if (el) {
      el.focus();
      e.preventDefault();
    }
    return;
  }
  if ($("#modalhost").innerHTML) return;
  if (route.view === "review" && session) {
    if (e.key === " ") {
      e.preventDefault();
      if (!session.flipped) flip();
      return;
    }
    if (session.flipped && ["1", "2", "3", "4"].includes(e.key)) {
      rate(+e.key - 1);
      return;
    }
  }
  // a quiz is on screen: the module's Retrieve step or a checkpoint
  const quizLive =
    QUIZ &&
    !QUIZ.qs.finished &&
    ((route.view === "m" && route.step === 2) || (route.view === "check" && route.id === "run"));
  if (quizLive) {
    const st = QUIZ.qs.a[QUIZ.qs.i],
      it = QUIZ.items[QUIZ.qs.i].it,
      t = it.type || "single";
    if (!st || !st.committed) {
      if (t === "single" || t === "tf") {
        const n = t === "tf" ? 2 : it.options.length;
        const i = "abcdefgh".indexOf(e.key.toLowerCase());
        if (i >= 0 && i < n) {
          qPick(i);
          return;
        }
        if (/^[1-8]$/.test(e.key) && +e.key - 1 < n) {
          qPick(+e.key - 1);
          return;
        }
      }
      if (e.key === "Enter") {
        qCommit();
        return;
      }
    } else if (!st.answered && ["1", "2", "3"].includes(e.key)) {
      qAnswer(+e.key);
      return;
    } else if (st.answered && st.ok != null && e.key === "Enter") {
      qNext();
      return;
    } else if (st.answered && st.ok == null && ["1", "2", "3"].includes(e.key) && !shortGrading) {
      qSelf(+e.key);
      return;
    }
  }
  if (route.view === "m") {
    const i = moduleIndex(route.id);
    if (e.key === "j" && MODS[i + 1]) go("#/m/" + MODS[i + 1].id);
    if (e.key === "k" && MODS[i - 1]) go("#/m/" + MODS[i - 1].id);
  } else if (route.view !== "check") {
    if (e.key === "j" || e.key === "k") go("#/m/" + MODS[0].id);
  }
});
window.addEventListener("scroll", () => {
  const h = document.body.scrollHeight - window.innerHeight;
  $("#readbar").style.width = (h > 0 ? Math.min(100, (window.scrollY / h) * 100) : 0) + "%";
});
window.addEventListener("beforeunload", save);
document.addEventListener("visibilitychange", () => {
  if (document.hidden) save();
});
