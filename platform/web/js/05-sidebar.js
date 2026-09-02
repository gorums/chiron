/* ============================ sidebar ============================ */
const ICONS = {
  home: "◈", review: "↻", stats: "◔", library: "▤", plan: "✦"
};
function renderSidebar() {
  const pct = doneCount() / MODS.length;
  const due = dueCards().length;
  const R = 20, C = 2 * Math.PI * R;
  let h = `<div class="brand"><h1>${esc(CFG.title)}</h1><p>${esc(CFG.tagline)}</p></div>
  <button class="ringwrap" onclick="go('#/stats')">
    <svg class="ring" viewBox="0 0 46 46"><circle cx="23" cy="23" r="${R}" fill="none" stroke="var(--surface-3)" stroke-width="4"/>
    <circle cx="23" cy="23" r="${R}" fill="none" stroke="var(--accent)" stroke-width="4" stroke-linecap="round"
      stroke-dasharray="${C}" stroke-dashoffset="${C * (1 - pct)}" transform="rotate(-90 23 23)"/></svg>
    <span class="ringtxt"><b>${doneCount()} of ${MODS.length} modules</b>${fmtH(minutesDone())} of ${fmtH(CFG.hours * 60)} · ${Math.round(pct * 100)}%</span>
  </button>
  <div class="navsec">
    ${STUDIO ? `<a class="navlink" href="${STUDIO.origin}/#/course/${STUDIO.id}" style="text-decoration:none"><span class="ico">⌂</span>All courses${syncState === "on" ? `<span class="dotstat on" title="Progress is saved on the platform" style="margin-left:auto"></span>` : ""}</a>` : ""}
    <button class="navlink ${route.v === "home" ? "active" : ""}" onclick="go('#/home')"><span class="ico">${ICONS.home}</span>Dashboard</button>
    <button class="navlink ${route.v === "review" ? "active" : ""}" onclick="go('#/review')"><span class="ico">${ICONS.review}</span>Review${due ? `<span class="pill">${due}</span>` : ""}</button>
    <button class="navlink ${route.v === "stats" ? "active" : ""}" onclick="go('#/stats')"><span class="ico">${ICONS.stats}</span>Progress &amp; stats</button>
    <button class="navlink ${route.v === "marks" ? "active" : ""}" onclick="go('#/marks')"><span class="ico">✎</span>Marks &amp; questions${openQs() ? `<span class="pill">${openQs()}</span>` : ""}</button>
    <button class="navlink ${route.v === "library" ? "active" : ""}" onclick="go('#/library')"><span class="ico">${ICONS.library}</span>Library</button>
  </div>`;
  DATA.parts.forEach(p => {
    const ms = MODS.filter(m => m.part === p.id);
    h += `<div class="partgroup"><div class="parthead"><span class="pn">${esc(p.name)}</span><span class="ph">${p.hours}h</span></div>`;
    ms.forEach(m => {
      const pc = modPct(m), dn = isDone(m);
      h += `<button class="mrow ${route.v === "m" && route.id === m.id ? "active" : ""}" onclick="go('#/m/${m.id}')">
        <span class="dot ${dn ? "done" : (pc > 0 ? "part" : "")}"></span>
        <span class="code">${m.id}</span><span class="t">${esc(m.short)}</span></button>`;
    });
    h += `</div>`;
  });
  h += `<div class="navsec" style="border-top:1px solid var(--line);margin-top:10px">
    <button class="navlink ${route.v === "settings" ? "active" : ""}" onclick="go('#/settings')"><span class="ico">⚙</span>Settings<span class="dotstat ${bridgeChecking ? "busy" : connMode() !== "none" ? "on" : ""}" style="margin-left:auto"></span></button>
    <button class="navlink" onclick="go('#/plan/curriculum')"><span class="ico">${ICONS.plan}</span>The plan</button>
    <button class="navlink" onclick="openData()"><span class="ico">⇅</span>Backup / restore</button>
  </div><div style="height:24px"></div>`;
  $("#sidebar").innerHTML = h;
  const rb = $("#reviewbtn");
  if (due) { rb.style.display = ""; rb.innerHTML = `↻ ${due} due`; rb.onclick = () => go("#/review"); }
  else rb.style.display = "none";
}
