/* ============================ sidebar ============================
   Real links in a real <nav>: every item has an address, so it can be opened in a new tab,
   read out as a list, and marked as the current page. */
function navItem(view, hash, icon, label, badge) {
  const on = (Array.isArray(view) ? view : [view]).includes(route.view);
  return `<a class="navlink" href="${hash}" ${on ? 'aria-current="page"' : ""}><span class="ico">${ico(icon)}</span>${label}${badge || ""}</a>`;
}
function renderSidebar() {
  const pct = doneCount() / MODS.length;
  const due = dueCards().length,
    mdue = mistakesDue();
  const R = 20,
    C = 2 * Math.PI * R;
  const spent = timeSpent() ? fmtSpent(timeSpent()) + " studied · " : "";
  const who = PROFILE !== "default" ? `<br>Reading as <b class="who">${esc(PROFILE)}</b>` : "";
  let h = `<div class="brand"><h1>${esc(CFG.title)}</h1><p>${esc(CFG.tagline)}</p></div>
  <button class="ringwrap" onclick="go('#/stats')">
    <svg class="ring" viewBox="0 0 46 46" aria-hidden="true"><circle cx="23" cy="23" r="${R}" fill="none" stroke="var(--surface-3)" stroke-width="4"/>
    <circle cx="23" cy="23" r="${R}" fill="none" stroke="var(--accent)" stroke-width="4" stroke-linecap="round"
      stroke-dasharray="${C}" stroke-dashoffset="${C * (1 - pct)}" transform="rotate(-90 23 23)"/></svg>
    <span class="ringtxt"><b>${doneCount()} of ${MODS.length} modules</b>${spent}${fmtH(CFG.hours * 60)} course${who}</span>
  </button>
  <nav class="navsec" aria-label="Course">
    ${STUDIO ? `<a class="navlink" href="${STUDIO.origin}/#/course/${STUDIO.id}"><span class="ico">${ico("courses")}</span>All courses${syncState === "on" ? `<span class="dotstat on" data-help="Your progress is being saved on the platform"></span>` : ""}</a>` : ""}
    ${navItem("home", "#/home", "home", "Dashboard")}
    ${navItem("review", "#/review", "review", "Practice", due ? `<span class="badge" data-help="${esc(mdue ? mdue + " of these are mistakes to fix. " + help("mistake card") : help("practice deck"))}">${due}</span>` : "")}
    ${navItem("check", "#/check", "check", "Checkpoints", checkOffers().length ? `<span class="badge" data-help="${esc(help("checkpoint"))}">${checkOffers().length}</span>` : "")}
    ${navItem("marks", "#/marks", "marks", "Marks &amp; questions", openQs() ? `<span class="badge" data-help="Questions you marked and have not closed">${openQs()}</span>` : "")}
    ${navItem(["stats", "record"], "#/stats", "stats", "Progress")}
    ${navItem("learner", "#/learner", "learner", "Your gaps", openGaps().length ? `<span class="badge" data-help="${esc(help("gap"))}">${openGaps().length}</span>` : "")}
    ${navItem(["library", "plan"], "#/library", "library", "Library")}
  </nav>
  <div class="legend">${[1, 2, 3, 4].map(l => `<span data-help="${esc(help(MASTERY[l]))}"><i class="dot l${l}"></i>${MASTERY[l]}</span>`).join("")}</div>`;
  DATA.parts.forEach(p => {
    const ms = MODS.filter(m => m.part === p.id);
    h += `<div class="partgroup"><div class="parthead"><span class="pn">${esc(p.name)}</span><span class="ph">${p.hours}h</span></div>`;
    ms.forEach(m => {
      const level = mastery(m);
      const here = route.view === "m" && route.id === m.id;
      const marked =
        STATE.bookmarks && Object.keys(STATE.bookmarks).some(k => k.startsWith(m.id + ":"));
      h += `<a class="mrow" href="#/m/${m.id}" ${here ? 'aria-current="page"' : ""} data-help="${level.name} — ${esc(help(level.name))}">
        <span class="dot ${masteryClass(m)}"></span>
        <span class="code">${m.id}</span><span class="t">${esc(m.short)}</span>${marked ? `<span class="bm" data-help="You bookmarked something in this module">${ico("flag", 11)}</span>` : ""}</a>`;
    });
    h += `</div>`;
  });
  const connected = connMode() !== "none";
  h += `<nav class="navsec foot" aria-label="This device">
    ${navItem("settings", "#/settings", "settings", "Settings", `<span class="dotstat ${bridgeChecking ? "busy" : connected ? "on" : ""}" data-help="${connected ? "The tutor is connected" : "The tutor is not connected"}"></span>`)}
  </nav>
  <div class="sidefoot"></div>`;
  $("#sidebar").innerHTML = h;
  const rb = $("#reviewbtn");
  if (due) {
    rb.style.display = "";
    rb.innerHTML = `${ico("review", 13)} ${due} due`;
    rb.setAttribute("data-help", "Flashcards due today. " + help("practice deck"));
    rb.onclick = () => go("#/review");
  } else rb.style.display = "none";
}
