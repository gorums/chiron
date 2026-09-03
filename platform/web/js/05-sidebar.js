/* ============================ sidebar ============================ */
function renderSidebar() {
  const pct = doneCount() / MODS.length;
  const due = dueCards().length, mdue = mistakesDue();
  const R = 20, C = 2 * Math.PI * R;
  let h = `<div class="brand"><h1>${esc(CFG.title)}</h1><p>${esc(CFG.tagline)}</p></div>
  <button class="ringwrap" onclick="go('#/stats')">
    <svg class="ring" viewBox="0 0 46 46"><circle cx="23" cy="23" r="${R}" fill="none" stroke="var(--surface-3)" stroke-width="4"/>
    <circle cx="23" cy="23" r="${R}" fill="none" stroke="var(--accent)" stroke-width="4" stroke-linecap="round"
      stroke-dasharray="${C}" stroke-dashoffset="${C * (1 - pct)}" transform="rotate(-90 23 23)"/></svg>
    <span class="ringtxt"><b>${doneCount()} of ${MODS.length} modules</b>${timeSpent() ? fmtSpent(timeSpent()) + " studied · " : ""}${fmtH(CFG.hours * 60)} course${PROFILE !== "default" ? `<br>Reading as <b style="display:inline;font-size:12px">${esc(PROFILE)}</b>` : ""}</span>
  </button>
  <div class="navsec">
    ${STUDIO ? `<a class="navlink" href="${STUDIO.origin}/#/course/${STUDIO.id}" style="text-decoration:none"><span class="ico">${ico("courses")}</span>All courses${syncState === "on" ? `<span class="dotstat on" title="Progress is saved on the platform" style="margin-left:auto"></span>` : ""}</a>` : ""}
    <button class="navlink ${route.v === "home" ? "active" : ""}" onclick="go('#/home')"><span class="ico">${ico("home")}</span>Dashboard</button>
    <button class="navlink ${route.v === "review" ? "active" : ""}" onclick="go('#/review')"><span class="ico">${ico("review")}</span>Review${due ? `<span class="pill" title="${mdue ? mdue + " of these are mistakes to fix" : ""}">${due}</span>` : ""}</button>
    <button class="navlink ${route.v === "check" ? "active" : ""}" onclick="go('#/check')"><span class="ico">${ico("check")}</span>Checkpoints${checkOffers().length ? `<span class="pill">${checkOffers().length}</span>` : ""}</button>
    <button class="navlink ${route.v === "marks" ? "active" : ""}" onclick="go('#/marks')"><span class="ico">${ico("marks")}</span>Marks &amp; questions${openQs() ? `<span class="pill">${openQs()}</span>` : ""}</button>
    <button class="navlink ${route.v === "stats" || route.v === "record" ? "active" : ""}" onclick="go('#/stats')"><span class="ico">${ico("stats")}</span>Progress</button>
    <button class="navlink ${route.v === "library" || route.v === "plan" ? "active" : ""}" onclick="go('#/library')"><span class="ico">${ico("library")}</span>Library</button>
  </div>
  <div class="legend">${[1, 2, 3, 4].map(l => `<span><i class="dot l${l}"></i>${MASTERY[l]}</span>`).join("")}</div>`;
  DATA.parts.forEach(p => {
    const ms = MODS.filter(m => m.part === p.id);
    h += `<div class="partgroup"><div class="parthead"><span class="pn">${esc(p.name)}</span><span class="ph">${p.hours}h</span></div>`;
    ms.forEach(m => {
      const ms_ = mastery(m);
      h += `<button class="mrow ${route.v === "m" && route.id === m.id ? "active" : ""}" onclick="go('#/m/${m.id}')" title="${ms_.name}">
        <span class="dot ${masteryClass(m)}"></span>
        <span class="code">${m.id}</span><span class="t">${esc(m.short)}</span>${S.bookmarks && Object.keys(S.bookmarks).some(k => k.startsWith(m.id + ":")) ? `<span class="bm" title="Bookmarked">${ico("flag", 11)}</span>` : ""}</button>`;
    });
    h += `</div>`;
  });
  h += `<div class="navsec" style="border-top:1px solid var(--line);margin-top:10px">
    <button class="navlink ${route.v === "settings" ? "active" : ""}" onclick="go('#/settings')"><span class="ico">${ico("settings")}</span>Settings<span class="dotstat ${bridgeChecking ? "busy" : connMode() !== "none" ? "on" : ""}" style="margin-left:auto" title="${connMode() !== "none" ? "Claude connected" : "Claude not connected"}"></span></button>
  </div>
  <div style="height:24px"></div>`;
  $("#sidebar").innerHTML = h;
  const rb = $("#reviewbtn");
  if (due) { rb.style.display = ""; rb.innerHTML = `${ico("review", 13)} ${due} due`; rb.onclick = () => go("#/review"); }
  else rb.style.display = "none";
}
