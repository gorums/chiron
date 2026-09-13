/* ---------- one course ---------- */

const TABS = [
  ["modules", "Modules"],
  ["add", "Add a module"],
  ["questions", "Questions"],
  ["files", "Files"],
  ["settings", "Settings"],
];

async function viewCourse() {
  const id = route.id;
  // Paint what we already know first, so a tab switch does not flash "Loading…"; the fresh
  // copy repaints underneath when it arrives.
  if (courseCache[id]) paintCourse(courseCache[id]);
  else
    $("#view").innerHTML =
      `<p class="crumb"><a href="#/">Courses</a> › ${esc(id)}</p><p class="sub">Loading…</p>`;
  let c;
  try {
    c = await api(`/api/courses/${encodeURIComponent(id)}`);
  } catch (err) {
    $("#view").innerHTML = `<p class="crumb"><a href="#/">Courses</a> › ${esc(id)}</p>
      <div class="card"><h3>Cannot open ${esc(id)}</h3><p class="sub">${esc(err.message)}</p>
      <div class="rowline gap-top"><button class="btn primary" onclick="viewCourse()">Try again</button>
      <a class="btn" href="#/">Back to courses</a></div></div>`;
    return;
  }
  courseCache[id] = c;
  if (route.id !== id) return; // navigated away while loading
  paintCourse(c);
}

/* The one action bar for a course. Exactly one primary: the next thing to do — build it
   if it was never built, rebuild it if a file changed since, otherwise read it. */
function courseOps(c) {
  const p = c.progress || {};
  const live = c.job && !FINISHED.includes(c.job.status);
  const exportBtn = `<a class="btn" href="/api/courses/${encodeURIComponent(c.id)}/export" download="${esc(c.id)}.zip" data-help="The course folder as a zip, without .git">Export .zip</a>`;
  if (live)
    return `<a class="btn primary" data-jobof="${esc(c.id)}" href="#/job/${c.job.id}">${esc(jobLabel(c.job))} — view</a>
      <button class="btn" disabled data-help="A run is writing this course. Check and Build come back when it finishes.">Check</button>
      <button class="btn" disabled data-help="A run is writing this course. Check and Build come back when it finishes.">Rebuild</button>
      ${exportBtn}`;
  const rebuildPrimary = !c.built || c.dirty;
  const read = c.built
    ? `<a class="btn ${rebuildPrimary ? "" : "primary"}" href="${courseUrl(c, p.done || p.started ? "#/m/" + (p.next || "") : "#/home")}">${p.done || p.started ? "Continue at " + esc(p.next || "") : "Start the course"}</a>
       <a class="btn" href="${courseUrl(c)}">Open the course</a>`
    : `<span class="pill">not built yet</span>`;
  return `${read}
    ${c.resumable ? `<button class="btn warm" onclick="toggleResume('${c.id}')" data-help="${esc(help("resume"))}">Resume the run…</button>` : ""}
    <button class="btn" onclick="checkCourse('${c.id}')" data-help="Validate every module, quiz and suggestion file without writing anything">Check</button>
    <button class="btn ${rebuildPrimary ? "primary" : ""}" onclick="buildCourse('${c.id}')">${c.built ? "Rebuild" : "Build"}</button>
    ${exportBtn}`;
}

function paintCourse(c) {
  const p = c.progress || {};
  const pct = Math.round((p.pct || 0) * 100);
  const tab = route.query.tab || "modules";
  const live = c.job && !FINISHED.includes(c.job.status);
  const counts = { questions: (c.questions || []).length };
  const head = `
    <p class="crumb"><a href="#/">Courses</a> › ${esc(c.title)}</p>
    <div class="card"><div class="hero">
      <div>
        <h2 class="big">${esc(c.title)}</h2>
        <p class="sub">${esc(c.tagline || "")}${c.audience ? " · for " + esc(c.audience) : ""}</p>
        <div class="bar-track herobar"><div class="bar-fill" style="width:${pct}%"></div></div>
        <div class="stats">
          <div class="stat"><b>${pct}%</b><span>complete</span></div>
          <div class="stat"><b>${p.done || 0}<small>/${c.modules}</small></b><span>modules done</span></div>
          <div class="stat"><b>${p.minutes || 0}m</b><span>studied</span></div>
          <div class="stat"><b>${p.cards || 0}</b><span>cards · ${p.due || 0} due</span></div>
          <div class="stat"><b>${esc(fmtH((c.hours || 0) * 60))}</b><span>planned</span></div>
        </div>
      </div>
      <div class="actions courseops" id="courseops">${courseOps(c)}</div>
    </div>
    <div id="courseout"></div>
    <div id="resumeout"></div>
    ${c.error ? `<div class="problems">${problemList(c, [c.error])}</div>` : ""}
    ${c.resumable && !live ? `<div class="note gap-top">This course's generation run did not finish — the saved curriculum is still here. <b>Resume the run</b> keeps every module and study-data entry already on disk and writes only what is missing, then builds. See <a href="#/settings">Settings &amp; logs</a> for why it stopped.</div>` : ""}
    ${c.built && c.dirty ? `<p class="sub result"><span class="tag warn" data-help="${esc(help("dirty"))}">changed since the build</span> A file has been edited since ${esc(ago(c.builtAt))}. Rebuild to put it in the page.</p>` : ""}
    ${c.built && !c.dirty ? `<p class="sub result">Built ${esc(ago(c.builtAt))}. A rebuild keeps your progress — it lives with the platform, not the page.</p>` : ""}
    ${providerGate()}
    </div>
    <div class="tabs" role="tablist" aria-label="Course">
      ${TABS.map(
        ([k, l]) =>
          `<button class="tab" role="tab" id="tab-${k}" aria-selected="${tab === k}" aria-controls="tabbody" tabindex="${tab === k ? 0 : -1}" onclick="setTab('${k}')" onkeydown="tabKeys(event,'${k}')">${esc(l)}${counts[k] ? ` <span class="count">${counts[k]}</span>` : ""}</button>`
      ).join("")}
    </div>
    <div id="tabbody" role="tabpanel" aria-labelledby="tab-${tab}"></div>`;
  $("#view").innerHTML = head;
  if (tab === "add") paintAdd(c);
  else if (tab === "files") paintFiles(c);
  else if (tab === "questions") paintQuestions(c);
  else if (tab === "settings") paintSettings(c);
  else paintModules(c);
  if (tabByKeyboard === tab) {
    const btn = $("#tab-" + tab);
    if (btn) btn.focus();
  }
}

/* Left and right move between tabs, as a tablist is expected to. Selection is a route
   change, so the button the arrow key chose is gone by the time the screen is redrawn —
   and a panel that focuses its first field on arrival would take the focus out of the
   tablist after one press. `tabByKeyboard` is how both are avoided: paintCourse gives the
   focus back to the tab, and the panel leaves it there. */
let tabByKeyboard = null;
function tabKeys(ev, current) {
  const i = TABS.findIndex(t => t[0] === current);
  let next = null;
  if (ev.key === "ArrowRight") next = TABS[(i + 1) % TABS.length];
  else if (ev.key === "ArrowLeft") next = TABS[(i - 1 + TABS.length) % TABS.length];
  else if (ev.key === "Home") next = TABS[0];
  else if (ev.key === "End") next = TABS[TABS.length - 1];
  if (!next) return;
  ev.preventDefault();
  setTab(next[0], true);
}

function setTab(tab, fromKeyboard) {
  tabByKeyboard = fromKeyboard ? tab : null;
  const q = Object.assign({}, route.query, { tab });
  delete q.rewrite;
  delete q.from;
  delete q.sec;
  delete q.q;
  delete q.review;
  location.hash = `#/course/${encodeURIComponent(route.id)}?` + new URLSearchParams(q).toString();
}

/* A validation problem usually names the file it is about. Make that name the way to it. */
function problemList(c, problems) {
  const link = text => {
    const m = String(text).match(/([\w./-]+\.(?:md|json|svg|ipynb))/);
    if (!m) return esc(text);
    const href = `#/course/${encodeURIComponent(c.id)}/edit?path=${encodeURIComponent(m[1])}`;
    return esc(text).replace(esc(m[1]), `<a href="${href}">${esc(m[1])}</a>`);
  };
  return problems.map(p => `<li>${link(p)}</li>`).join("");
}

function paintModules(c) {
  const mp = c.moduleProgress || {},
    reviews = c.reviews || {};
  const manyParts = (c.parts || []).length > 1;
  const parts = (c.parts || [])
    .map(part => {
      const mods = (c.moduleList || []).filter(m => m.part === part.id);
      const rows = mods.map((m, i) =>
        moduleRow(c, part, m, i, mods.length, mp, reviews, manyParts)
      );
      return `<div class="partblock">
      <div class="parttitle"><h3>${esc(part.name)}</h3><span class="tag">${esc(part.hours)}h</span><span class="tag">${mods.length} module${mods.length === 1 ? "" : "s"}</span></div>
      ${part.blurb ? `<p class="blurb">${esc(part.blurb)}</p>` : ""}
      ${rows.join("") || `<p class="sub">No modules in this part yet.</p>`}
      <div class="result" id="partout-${esc(part.id)}"></div>
    </div>`;
    })
    .join("");
  $("#tabbody").innerHTML =
    (parts && moduleToolbar(c) + verdictLegend(c) + parts) ||
    `<div class="card"><p class="sub">This course has no readable modules yet.</p></div>`;
  if (route.query.rewrite) {
    const el = document.getElementById("rwn-" + route.query.rewrite);
    if (el) {
      el.scrollIntoView({ block: "center" });
      el.focus();
    }
  }
  if (route.query.review) {
    const box = document.getElementById("rv-" + route.query.review);
    if (box) {
      box.classList.remove("hidden");
      box.scrollIntoView({ block: "center" });
    }
  }
}

/* One row of controls above the module list, instead of three explanatory cards that were
   read once and then scrolled past for the rest of the course's life. */
function moduleToolbar(c) {
  return `<div class="toolbar">
    <span class="tgroup">${quickModelBar()}</span>
    <span class="tgroup">${figuresBar(c)}</span>
    <span class="tgroup">${notebooksBar(c)}</span>
  </div>
  <details class="explainer"><summary>What these do</summary>
    <p><b>Model</b> — which model runs Review, Draw figures and Write notebooks from a row's menu.</p>
    <p><b>Figures</b> — SVG diagrams inlined in a module's Read step. One call per module.</p>
    <p><b>Notebooks</b> — Jupyter notebooks the reader runs inside a module. Only for a course that declares the runtime, under Settings.</p>
  </details>`;
}

/* The verdict scale, once, where the verdicts are. */
function verdictLegend(c) {
  const any = Object.keys(c.reviews || {}).length;
  if (!any) return "";
  return `<details class="explainer"><summary>What the verdicts mean</summary>
    <p><span class="tag ok">solid</span> ${esc(help("solid"))}</p>
    <p><span class="tag warn">needs work</span> ${esc(help("needs work"))}</p>
    <p><span class="tag bad">rewrite</span> ${esc(help("rewrite"))}</p>
    <p><span class="tag stale">· before edit</span> ${esc(help("stale"))}</p>
  </details>`;
}

function verdictTag(m, rv) {
  if (!rv) return "";
  // The owner's "this is good" outranks the review's verdict. A stale one, from before the
  // module's last rewrite or edit, is about text that is no longer there: shown greyed with
  // a note, never as current.
  const good = !!rv.accepted;
  const shown = good ? "good" : rv.verdict;
  if (rv.stale)
    return `<button class="tag stale" data-help="${good ? "Marked good" : "Reviewed"} ${new Date(good ? rv.accepted : rv.at).toLocaleString()}, but the module changed on ${new Date(rv.moduleChangedAt).toLocaleString()}. ${esc(help("stale"))}" onclick="toggleEl('rv-${m.id}')">${esc(shown)} · before edit</button>`;
  if (good)
    return `<button class="tag ok" data-help="You marked this good on ${new Date(rv.accepted).toLocaleString()}${rv.ownerOnly ? "" : " — the review's findings are kept underneath"}" onclick="toggleEl('rv-${m.id}')">good ✓</button>`;
  const cls = rv.verdict === "solid" ? "ok" : rv.verdict === "rewrite" ? "bad" : "warn";
  return `<button class="tag ${cls}" data-help="Reviewed ${new Date(rv.at).toLocaleDateString()}. ${esc(help(rv.verdict))} Click for the findings." onclick="toggleEl('rv-${m.id}')">${esc(rv.verdict)}</button>`;
}

/* A module whose prompts the owner has rewritten says so where the verdict says so: it is
   the first thing to know when its text reads unlike the rest of the course. */
function promptTag(m) {
  const own = (m.prompts || []).length;
  if (!own) return "";
  const what = m.prompts.join(", ");
  return ` <span class="tag acc" data-help="This module sends ${what} prompt${own === 1 ? "" : "s"} of your own">${own} own prompt${own === 1 ? "" : "s"}</span>`;
}

function moduleRow(c, part, m, i, total, mp, reviews, manyParts) {
  const st = mp[m.id] || {};
  const dot = st.done ? "done" : st.read || st.minutes || st.quiz ? "part" : "";
  const state = st.done
    ? "completed"
    : st.read
      ? `${st.read}/${m.sections} sections read${st.quiz ? " · quiz done" : ""}`
      : "";
  const open = c.built ? `<a class="btn sm" href="${courseUrl(c, "#/m/" + m.id)}">Read</a>` : "";
  const rewriting = route.query.rewrite === m.id;
  const rv = reviews[m.id];
  const isGood = !!(rv && rv.accepted && !rv.stale);
  const gate = providerReady() ? "" : "disabled";
  return `<div class="modrow" id="mod-${m.id}">
    <span class="order"><button data-help="Move ${esc(m.id)} up" aria-label="Move ${esc(m.id)} up" ${i === 0 ? "disabled" : ""} onclick="moveModule('${c.id}','${m.id}','${part.id}',${i - 1})">${ico("up", 13)}</button><button data-help="Move ${esc(m.id)} down" aria-label="Move ${esc(m.id)} down" ${i === total - 1 ? "disabled" : ""} onclick="moveModule('${c.id}','${m.id}','${part.id}',${i + 1})">${ico("down", 13)}</button></span>
    <span class="mid">${esc(m.id)}</span>
    <span class="title"><span class="dot ${dot}" data-help="${esc(state)}"></span>${esc(m.title)} ${verdictTag(m, rv)}${promptTag(m)}<small>${m.minutes} min · ${m.sections} sections${m.figures ? ` · ${m.figures} figure${m.figures === 1 ? "" : "s"}` : ""}${m.notebooks ? ` · ${m.notebooks} notebook${m.notebooks === 1 ? "" : "s"}` : ""}${state ? " · " + esc(state) : ""}</small></span>
    <span class="rowtools">${open}
      <button class="btn sm kebab" aria-haspopup="menu" aria-expanded="false" aria-label="More actions for ${esc(m.id)}" data-help="Edit, review, patch, move, remove" onclick="toggleMenu(event,'${m.id}')">${ico("more", 15)}</button>
      <div class="menu hidden" id="menu-${m.id}" role="menu" onkeydown="menuKeys(event,'${m.id}')">
        <a role="menuitem" href="#/course/${encodeURIComponent(c.id)}/edit?path=${encodeURIComponent(m.path)}">Edit the text<small>the markdown, by hand</small></a>
        <button role="menuitem" onclick="closeMenus();reviewModule('${c.id}','${m.id}')" ${gate}>${rv && !rv.ownerOnly ? "Review again" : "Review this module"}<small>a verdict, gaps, errors, quiz issues · ${esc(modelName(quickModel()))}</small></button>
        <button role="menuitem" onclick="closeMenus();acceptModule('${c.id}','${m.id}',${isGood ? "false" : "true"})">${isGood ? "Unmark" : "Mark as good"}<small>${isGood ? "back to the review's verdict" : "your verdict outranks the review"}</small></button>
        <button role="menuitem" onclick="closeMenus();toggleRewrite('${m.id}')" ${gate}>Patch or rewrite…<small>with notes, by the model</small></button>
        <button role="menuitem" onclick="closeMenus();openCoursePrompts('${c.id}','${m.id}')">Prompts…<small>every call this module makes, and your own wording for any of them</small></button>
        ${figuresMenuItem(c, m)}
        ${notebooksMenuItem(c, m)}
        ${manyParts ? `<div class="sep"></div><label class="label" for="part-${m.id}">Move to part</label><select id="part-${m.id}" onchange="moveModule('${c.id}','${m.id}',this.value,-1)">${(c.parts || []).map(p => `<option value="${esc(p.id)}" ${p.id === part.id ? "selected" : ""}>${esc(p.name)}</option>`).join("")}</select>` : ""}
        <div class="sep"></div>
        <button role="menuitem" class="danger" onclick="closeMenus();toggleRemove('${m.id}')">Remove…<small>moves the file to the trash</small></button>
      </div></span>
  </div>
  ${rv ? reviewBox(c, m, rv) : ""}
  <div class="inlineform hidden" id="pr-${m.id}"></div>
  <div class="inlineform ${rewriting ? "" : "hidden"}" id="rw-${m.id}">
    <label for="rwn-${m.id}">What should change in ${esc(m.id)}?</label>
    <textarea id="rwn-${m.id}" rows="3" placeholder="Go much deeper on the worked example in Core concepts; the current version stops before the arithmetic. Keep the exercise.">${esc(route.query.rewrite === m.id && route.query.q ? route.query.q : "")}</textarea>
    ${mediaChoices("rw-" + m.id, c, "for a full rewrite")}
    ${modelChoice("rw-" + m.id, "the patch or the new module")}
    <div class="rwmodes">
      <label class="radio"><input type="radio" name="rwmode-${m.id}" value="patch" ${route.query.rewrite === m.id && route.query.q ? "checked" : ""}> <b>Patch</b></label>
      <span class="fhint">${esc(help("patch"))} Right for a review's findings.</span>
      <label class="radio gap-top"><input type="radio" name="rwmode-${m.id}" value="rewrite" ${route.query.rewrite === m.id && route.query.q ? "" : "checked"}> <b>Full rewrite</b></label>
      <span class="fhint">${esc(help("full rewrite"))} New text, new quiz, new cards.</span>
    </div>
    <div class="actions gap-top">
      <button class="btn sm primary" onclick="rewriteModule('${c.id}','${m.id}')">Patch or rewrite ${esc(m.id)}</button>
      <button class="btn sm" onclick="toggleRewrite('${m.id}')">Cancel</button>
    </div>
    <p class="fhint">Keeps the id and position. Your progress for it stays; after a full rewrite, section ticks may shift.</p>
  </div>
  <div class="inlineform danger hidden" id="rm-${m.id}">
    <b>Remove ${esc(m.id)} · ${esc(m.title)}?</b>
    <p class="sub">The file moves to <span class="mono">state/trash/</span>, its quiz, cards and questions are dropped, and the id is never reused. Rebuild afterwards.</p>
    <div class="actions gap-top">
      <button class="btn sm danger" onclick="removeModule('${c.id}','${m.id}','${esc(part.id)}')">Remove</button>
      <button class="btn sm" onclick="toggleRemove('${m.id}')">Cancel</button>
    </div>
  </div>`;
}

function reviewBox(c, m, rv) {
  const list = (rows, first) =>
    rows.length
      ? `<ul class="findings">${rows.map(r => `<li>${r[first] ? `<b>${esc(r[first])}</b> — ` : ""}${esc(r.issue)}${r.fix ? ` <i>Fix: ${esc(r.fix)}</i>` : ""}</li>`).join("")}</ul>`
      : `<p class="sub">Nothing.</p>`;
  return `<div class="reviewbox hidden" id="rv-${m.id}">
    ${rv.stale ? `<div class="note">This ${rv.accepted ? "verdict" : "review"} is from <b>${new Date(rv.accepted || rv.at).toLocaleString()}</b>; the module was rewritten or edited on <b>${new Date(rv.moduleChangedAt).toLocaleString()}</b>, so it describes the old text. <a href="#" onclick="reviewModule('${c.id}','${m.id}');return false">Review again</a> for a verdict on what is there now, or mark it good if you have read it.</div>` : ""}
    ${rv.accepted && !rv.stale ? `<p class="sub ok-text">You marked this module good on ${new Date(rv.accepted).toLocaleString()}.${rv.ownerOnly ? " It has not been reviewed." : " The review's findings below are kept for reference."}</p>` : ""}
    ${
      rv.ownerOnly
        ? ""
        : `<p class="summary">${esc(rv.summary)}</p>
    <h4>Gaps</h4>${list(rv.gaps || [], "where")}
    <h4>Errors</h4>${list(rv.errors || [], "where")}
    <h4>Quiz</h4>${list(rv.quiz || [], "item")}`
    }
    <div class="actions gap-top">
      ${rv.rewriteBrief && !(rv.accepted && !rv.stale) ? `<a class="btn sm primary" href="#/course/${encodeURIComponent(c.id)}?tab=modules&rewrite=${encodeURIComponent(m.id)}&q=${encodeURIComponent(rv.rewriteBrief)}">Patch with these notes</a>` : ""}
      ${rv.accepted && !rv.stale ? "" : `<button class="btn sm" onclick="acceptModule('${c.id}','${m.id}',true)" data-help="Your verdict: it is good as it is">Mark as good</button>`}
      <button class="btn sm" onclick="toggleEl('rv-${m.id}')">Close</button>
      <span class="sub">${rv.ownerOnly ? "" : `Reviewed ${new Date(rv.at).toLocaleString()}${rv.model ? " · " + esc(rv.model) : ""}`}</span>
    </div></div>`;
}

async function moveModule(id, mid, part, index) {
  try {
    const r = await api(
      `/api/courses/${encodeURIComponent(id)}/modules/${encodeURIComponent(mid)}/move`,
      { part, index }
    );
    toast(r.moved ? `${mid} moved` : `${mid} reordered`);
    delete courseCache[id];
    await viewCourse();
    reportUnderPart(
      part,
      r.problems,
      `Order saved to course.json. Rebuild to publish the change; reader progress is keyed by id and unaffected.`,
      `Moved, but the course now has`
    );
  } catch (err) {
    toast(err.message, { kind: "bad" });
  }
}

/* The answer to an action on a module belongs beside that module, not at the top of the
   page where the eye is not. */
function reportUnderPart(partId, problems, okLine, badLead) {
  const out = document.getElementById("partout-" + partId) || $("#courseout");
  if (!out) return;
  const c = courseCache[route.id] || { id: route.id };
  out.innerHTML =
    problems && problems.length
      ? `<div class="problems"><b>${badLead} ${problems.length} problem${problems.length === 1 ? "" : "s"}</b><ul>${problemList(c, problems)}</ul></div>`
      : `<p class="sub ok-text">${okLine}</p>`;
  out.scrollIntoView({ block: "nearest" });
}

async function acceptModule(id, mid, accepted) {
  try {
    await api(`/api/courses/${encodeURIComponent(id)}/modules/${encodeURIComponent(mid)}/accept`, {
      accepted,
    });
    toast(accepted ? `${mid} marked good` : `${mid}: verdict withdrawn`);
    delete courseCache[id];
    await viewCourse();
  } catch (err) {
    toast(err.message, { kind: "bad" });
  }
}

async function reviewModule(id, mid) {
  try {
    const { job: j } = await api(
      `/api/courses/${encodeURIComponent(id)}/modules/${encodeURIComponent(mid)}/review`,
      quickModelBrief()
    );
    location.hash = "#/job/" + j.id;
  } catch (err) {
    toast(err.message, { kind: "bad" });
  }
}

/* The row menu: one primary action stays on the row (Read), everything else lives here.
   One menu open at a time; a click anywhere else, or Escape, closes it and gives the
   focus back to the button that opened it. */
let menuOpener = null;
function toggleMenu(ev, mid) {
  ev.stopPropagation();
  const menu = document.getElementById("menu-" + mid);
  if (!menu) return;
  const wasOpen = !menu.classList.contains("hidden");
  closeMenus();
  if (!wasOpen) {
    menu.classList.remove("hidden");
    menuOpener = ev.currentTarget;
    menuOpener.setAttribute("aria-expanded", "true");
    const first = menu.querySelector("[role=menuitem]:not([disabled])");
    if (first) first.focus();
  }
}

function menuItems(menu) {
  return Array.from(menu.querySelectorAll("[role=menuitem]:not([disabled])"));
}

function menuKeys(ev, mid) {
  const menu = document.getElementById("menu-" + mid);
  if (!menu) return;
  const items = menuItems(menu);
  const at = items.indexOf(document.activeElement);
  if (ev.key === "ArrowDown" || ev.key === "ArrowUp") {
    ev.preventDefault();
    const step = ev.key === "ArrowDown" ? 1 : -1;
    const next = items[(at + step + items.length) % items.length];
    if (next) next.focus();
  } else if (ev.key === "Home" || ev.key === "End") {
    ev.preventDefault();
    (ev.key === "Home" ? items[0] : items[items.length - 1]).focus();
  } else if (ev.key === "Escape" || ev.key === "Tab") {
    closeMenus();
  }
}

function closeMenus() {
  const wasOpen = document.querySelector(".menu:not(.hidden)");
  document.querySelectorAll(".menu").forEach(m => m.classList.add("hidden"));
  document
    .querySelectorAll(".kebab[aria-expanded=true]")
    .forEach(b => b.setAttribute("aria-expanded", "false"));
  if (wasOpen && menuOpener && document.body.contains(menuOpener)) menuOpener.focus();
  menuOpener = null;
}
document.addEventListener("click", e => {
  if (!e.target.closest(".menu") && !e.target.closest(".kebab")) closeMenus();
});

function toggleRewrite(mid) {
  const el = document.getElementById("rw-" + mid);
  if (!el) return;
  el.classList.toggle("hidden");
  if (!el.classList.contains("hidden")) document.getElementById("rwn-" + mid).focus();
}

function toggleRemove(mid) {
  const el = document.getElementById("rm-" + mid);
  if (el) el.classList.toggle("hidden");
}

async function removeModule(id, mid, partId) {
  try {
    const r = await api(
      `/api/courses/${encodeURIComponent(id)}/modules/${encodeURIComponent(mid)}/remove`,
      {}
    );
    toast(`${mid} removed`);
    await refresh();
    await viewCourse();
    reportUnderPart(
      partId,
      r.problems,
      `${mid} removed — its file is in ${esc(r.trash || "state/trash/")}. Rebuild to publish the change.`,
      `${mid} removed, but the course now has`
    );
  } catch (err) {
    toast(err.message, { kind: "bad" });
  }
}

/* ---- questions: what the reader marked while studying ---- */

function paintQuestions(c) {
  const qs = c.questions || [];
  const gaps = paintGaps(c) + paintFlags(c);
  if (!qs.length) {
    $("#tabbody").innerHTML = `${gaps}<div class="card"><h3 class="eyebrow">Open questions</h3>
      <p class="sub">Nothing marked yet. While reading, select a sentence and turn it into a question — every one collects here, where it can become a new module or a rewrite.</p></div>`;
    return;
  }
  const rows = qs
    .map(q => {
      const brief = q.q || q.note || q.text;
      const topic = encodeURIComponent((q.q || q.text || "").slice(0, 140));
      const notes = encodeURIComponent(
        `From ${q.mid} (${q.title})${q.sec != null ? ", section " + (q.sec + 1) : ""}: "${(q.text || "").slice(0, 300)}"${q.q ? "\nThe reader asked: " + q.q : ""}`
      );
      return `<div class="qrow">
      <div class="qmeta"><span class="mid">${esc(q.mid)}</span> ${esc(q.title)} <span class="pill ${q.status === "answered" ? "on" : ""}">${esc(q.status)}</span></div>
      <blockquote>${esc(q.text)}</blockquote>
      ${q.q ? `<p class="qask">${esc(q.q)}</p>` : ""}${q.note && q.note !== brief ? `<p class="qask">${esc(q.note)}</p>` : ""}
      <div class="actions">
        <a class="btn sm" href="#/course/${encodeURIComponent(c.id)}?tab=add&from=${encodeURIComponent(q.mid)}&q=${topic}&notes=${notes}">Make this a module</a>
        <a class="btn sm" href="#/course/${encodeURIComponent(c.id)}?tab=modules&rewrite=${encodeURIComponent(q.mid)}&q=${notes}">Patch or rewrite ${esc(q.mid)}…</a>
        ${c.built ? `<a class="btn sm" href="${courseUrl(c, "#/m/" + q.mid + "/read")}">Open the passage</a>` : ""}
      </div>
    </div>`;
    })
    .join("");
  $("#tabbody").innerHTML = `${gaps}<div class="card">
    <h3 class="eyebrow">Open questions</h3>
    <p class="sub">The passages the reader marked with a question. They are the most honest map of where this course stops short — turn one into a brief.</p>
    ${rows}</div>`;
}
/* the quiz questions the reader flagged as wrong, each offered as a patch brief */
function paintFlags(c) {
  const flags = c.flags || [];
  if (!flags.length) return "";
  const rows = flags
    .map(f => {
      const notes = encodeURIComponent(
        `Quiz question ${f.qi + 1} of ${f.mid} ("${f.q}") was flagged by the reader${f.note ? ": " + f.note : ""}. Fix the question, its answer or its feedback; leave the module's text alone unless the text is what is wrong.`
      );
      return `<div class="qrow">
      <div class="qmeta"><span class="mid">${esc(f.mid)}</span> ${esc(f.title)} · question ${f.qi + 1}</div>
      <blockquote>${esc(f.q)}</blockquote>
      ${f.note ? `<p class="qask">${esc(f.note)}</p>` : ""}
      <div class="actions">
        <a class="btn sm" href="#/course/${encodeURIComponent(c.id)}?tab=modules&rewrite=${encodeURIComponent(f.mid)}&q=${notes}">Patch or rewrite ${esc(f.mid)}…</a>
      </div></div>`;
    })
    .join("");
  return `<div class="card">
    <h3 class="eyebrow" data-help="${esc(help("flagged question"))}">Flagged quiz questions</h3>
    <p class="sub">Questions the reader thinks are wrong. A patch fixes the quiz and leaves the text alone.</p>
    ${rows}</div>`;
}
/* the gaps the page's tutor is working on, each offered as a rewrite brief */
function paintGaps(c) {
  const L = c.learner || {};
  const gaps = L.gaps || [];
  if (!gaps.length && !L.brief) return "";
  const rows = gaps
    .map(g => {
      const notes = encodeURIComponent(
        `The reader keeps getting this wrong: ${g.topic}. ${g.why}${g.ask ? " A question that tests it: " + g.ask : ""}`
      );
      return `<div class="qrow">
      <div class="qmeta"><span class="mid">${esc(g.mid)}</span> ${esc(g.title)}</div>
      <p class="qask"><b>${esc(g.topic)}</b> — ${esc(g.why)}</p>
      <div class="actions">
        <a class="btn sm" href="#/course/${encodeURIComponent(c.id)}?tab=modules&rewrite=${encodeURIComponent(g.mid)}&q=${notes}">Patch or rewrite ${esc(g.mid)}…</a>
      </div></div>`;
    })
    .join("");
  const when = L.at ? new Date(L.at).toLocaleDateString() : "";
  return `<div class="card">
    <h3 class="eyebrow" data-help="${esc(help("gap"))}">Knowledge gaps${when ? ` · written ${esc(when)}` : ""}</h3>
    <p class="sub">${esc(L.brief || "What the page's tutor has learned about this reader.")}</p>
    ${rows || `<p class="sub">No open gaps.</p>`}</div>`;
}

/* ---- settings: the presentation fields of course.json, as a form ---- */

function paintSettings(c) {
  const s = c.settings || {},
    a = s.anchor || {},
    nb = s.notebooks || null;
  const milestones = (s.milestones || []).map((m, i) => milestoneRow(m, i)).join("");
  const parts = (s.parts || [])
    .map(
      p => `<div class="row parts" data-part="${esc(p.id)}">
      <input type="text" class="p-name" value="${esc(p.name)}" aria-label="Part name">
      <input type="number" class="p-hours" value="${esc(p.hours)}" min="0" step="0.5" aria-label="Hours">
      <input type="text" class="p-blurb" value="${esc(p.blurb || "")}" placeholder="One line on what this part is for" aria-label="Blurb">
    </div>`
    )
    .join("");
  $("#tabbody").innerHTML = `<form class="card" id="settingsform">
    <h3 class="eyebrow">Settings</h3>
    <p class="sub">Everything here is presentation and prompt — it changes what the page says and how the tutor speaks. The id <span class="mono">${esc(s.id)}</span> is locked: it is the key your progress is stored under.</p>
    <div class="row r2 gap-top">
      <div class="field"><label for="s-title">Title</label><input type="text" id="s-title" value="${esc(s.title)}"></div>
      <div class="field"><label for="s-tagline">Tagline</label><input type="text" id="s-tagline" value="${esc(s.tagline)}"></div>
    </div>
    <div class="row r2">
      <div class="field"><label for="s-audience">Who is studying</label><input type="text" id="s-audience" value="${esc(s.audience)}">
        <span class="fhint">What the reader already knows. It sets the level of every module.</span></div>
      <div class="field"><label for="s-practitioner">Practitioner</label><input type="text" id="s-practitioner" value="${esc(s.practitioner)}">
        <span class="fhint">${esc(help("practitioner"))}</span></div>
    </div>
    <div class="field"><label for="s-persona">Tutor persona</label><textarea id="s-persona" rows="2">${esc(s.tutorPersona)}</textarea>
      <span class="fhint">One or two sentences describing who answers in the page. It is pasted into the tutor's system prompt, so write it as a statement ending in a period.</span></div>

    <label>Notebooks</label>
    <span class="fhint">Jupyter notebooks the reader runs inside each module — for a subject learned by running code. Off for everything else.</span>
    <div class="row nbrow gap-top">
      <label class="radio"><input type="checkbox" id="nb-on" ${nb ? "checked" : ""}> <b>This course has notebooks</b></label>
      <input type="text" id="nb-kernel" value="${esc(nb ? nb.kernel : "")}" placeholder="Kernel, e.g. python3" aria-label="Kernel">
      <input type="text" id="nb-packages" value="${esc(nb ? (nb.packages || []).join(", ") : "")}" placeholder="Packages the notebooks import: numpy, pandas" aria-label="Packages">
    </div>

    <label class="gap-top">The reader's own case</label>
    <span class="fhint">${esc(help("anchor"))} A business, a kitchen, a next negotiation.</span>
    <div class="row r2 headed gap-top">
      <span class="colhead">Label</span><span class="colhead">In a question</span>
      <input type="text" id="a-label" value="${esc(a.label)}" placeholder="Your business" aria-label="Label">
      <input type="text" id="a-noun" value="${esc(a.noun)}" placeholder="my business" aria-label="Noun">
      <span class="colhead">Ask the reader to name it</span><span class="colhead">Placeholder</span>
      <input type="text" id="a-prompt" value="${esc(a.prompt)}" placeholder="What are you applying this to?" aria-label="Prompt">
      <input type="text" id="a-placeholder" value="${esc(a.placeholder)}" placeholder="my sister's clinic" aria-label="Placeholder">
    </div>

    <label class="gap-top">Parts</label>
    <span class="fhint">The course total follows the sum of these hours.</span>
    <div class="row parts headed gap-top"><span class="colhead">Name</span><span class="colhead">Hours</span><span class="colhead">What this part is for</span></div>
    ${parts}
    <label class="gap-top">Milestones</label>
    <span class="fhint">The honest line on the reader's stats page: after this many modules, say this.</span>
    <div class="row ms headed gap-top"><span class="colhead">After</span><span class="colhead">Say</span><span></span></div>
    <div id="milestones">${milestones}</div>
    <button type="button" class="btn sm" onclick="addMilestone()">+ Milestone</button>
    <div class="actions gap-top">
      <button class="btn primary" id="savesettings">Save and rebuild</button>
      <button type="button" class="btn" onclick="saveSettings('${c.id}',false)">Save only</button>
    </div>
    <p class="fhint">The model Studio writes with, and the log of every run, are under <a href="#/settings">Settings &amp; logs</a>.</p>
    <div id="settingsout"></div>
  </form>

  <div class="card">
    <h3 class="eyebrow">Progress backup</h3>
    <p class="sub">The platform's copy of your progress for this course — completion, quiz answers, flashcard schedule, notes, highlights and conversations. Download it to keep, or paste a backup to replace it.</p>
    <div class="actions gap-top">
      <button class="btn sm" onclick="downloadProgress('${c.id}')">Download progress</button>
      <button class="btn sm" onclick="toggleEl('restorebox')">Restore from a backup…</button>
    </div>
    <div id="restorebox" class="hidden gap-top">
      <label class="visually-hidden" for="restoretext">Backup JSON</label>
      <textarea id="restoretext" class="mono" rows="5" placeholder='Paste the backup JSON here. Either the raw state ({"progress": …}) or a download from this page.'></textarea>
      <div class="actions gap-top"><button class="btn sm danger" onclick="restoreProgress('${c.id}')">Replace the platform copy</button></div>
    </div>
  </div>

  <div class="card dangerzone">
    <h3 class="eyebrow">Delete this course</h3>
    <p class="sub">Moves the <span class="mono">${esc(c.id)}</span> folder (the whole course repository, if it is one) and its build to <span class="mono">state/trash/</span> and forgets the platform copy of your progress. Nothing is erased; you can move it back by hand. Type the id to confirm.</p>
    <div class="actions gap-top">
      <label class="visually-hidden" for="delconfirm">Type the course id to confirm</label>
      <input type="text" id="delconfirm" placeholder="${esc(c.id)}" autocomplete="off">
      <button class="btn sm danger" onclick="deleteCourse('${c.id}')">Delete course</button></div>
  </div>`;
  $("#settingsform").onsubmit = e => {
    e.preventDefault();
    saveSettings(c.id, true);
  };
}

function milestoneRow(m, i) {
  return `<div class="row ms" data-ms="${i}">
    <input type="number" class="ms-after" value="${esc(m.after)}" min="0" aria-label="After how many modules">
    <input type="text" class="ms-text" value="${esc(m.text)}" aria-label="Text">
    <button type="button" class="btn sm" onclick="this.parentNode.remove()" data-help="Remove this milestone" aria-label="Remove this milestone">${ico("close", 13)}</button>
  </div>`;
}

function addMilestone() {
  $("#milestones").insertAdjacentHTML(
    "beforeend",
    milestoneRow({ after: 0, text: "" }, Date.now())
  );
}

async function saveSettings(id, rebuild) {
  const body = {
    title: $("#s-title").value,
    tagline: $("#s-tagline").value,
    audience: $("#s-audience").value,
    practitioner: $("#s-practitioner").value,
    tutorPersona: $("#s-persona").value,
    anchor: {
      label: $("#a-label").value,
      noun: $("#a-noun").value,
      prompt: $("#a-prompt").value,
      placeholder: $("#a-placeholder").value,
    },
    notebooks: $("#nb-on").checked
      ? { kernel: $("#nb-kernel").value, packages: $("#nb-packages").value }
      : null,
    milestones: [...document.querySelectorAll("[data-ms]")].map(el => ({
      after: Number(el.querySelector(".ms-after").value) || 0,
      text: el.querySelector(".ms-text").value,
    })),
    parts: [...document.querySelectorAll("[data-part]")].map(el => ({
      id: el.dataset.part,
      name: el.querySelector(".p-name").value,
      hours: Number(el.querySelector(".p-hours").value) || 0,
      blurb: el.querySelector(".p-blurb").value,
    })),
  };
  const out = $("#settingsout");
  const stop = busy(out, rebuild ? "Saving, then rebuilding…" : "Saving…", "#settingsform");
  try {
    await api(`/api/courses/${encodeURIComponent(id)}/settings`, body);
    stop();
    delete courseCache[id];
    if (rebuild) return buildAfterSettings(id);
    toast("Settings saved");
    out.innerHTML = `<p class="sub ok-text result">Saved. Rebuild when you are ready, so the page picks it up.</p>`;
    await refresh();
  } catch (err) {
    stop();
    if (out) out.innerHTML = `<div class="problems">${esc(err.message)}</div>`;
  }
}

async function buildAfterSettings(id) {
  const out = $("#settingsout");
  const stop = busy(out, "Checking every file, then rendering the page…", "#settingsform");
  try {
    const data = await api(`/api/courses/${encodeURIComponent(id)}/build`, {});
    stop();
    if (!data.built) {
      const c = courseCache[id] || { id };
      out.innerHTML = `<div class="problems"><b>Saved, but not built</b><ul>${problemList(c, data.problems)}</ul></div>`;
      return;
    }
    toast("Saved and rebuilt " + id);
    await refresh();
    await viewCourse();
  } catch (err) {
    stop();
    if (out) out.innerHTML = `<div class="problems">${esc(err.message)}</div>`;
  }
}

function toggleEl(id) {
  const el = document.getElementById(id);
  if (el) el.classList.toggle("hidden");
}

async function downloadProgress(id) {
  try {
    const r = await api(`/api/courses/${encodeURIComponent(id)}/progress`);
    if (!r.state) {
      toast("No progress stored yet for this course");
      return;
    }
    const blob = new Blob([JSON.stringify(r.state, null, 1)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${id}-progress-${new Date().toISOString().slice(0, 10)}.json`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  } catch (err) {
    toast(err.message, { kind: "bad" });
  }
}

async function restoreProgress(id) {
  let obj;
  try {
    obj = JSON.parse($("#restoretext").value);
  } catch (e) {
    toast("That is not valid JSON", { kind: "bad" });
    return;
  }
  if (obj && obj.state && typeof obj.state === "object") obj = obj.state;
  if (!obj || typeof obj !== "object" || Array.isArray(obj)) {
    toast("That is not a progress backup", { kind: "bad" });
    return;
  }
  obj.updatedAt = Date.now(); // it must win over whatever a course page still holds
  try {
    await api(`/api/courses/${encodeURIComponent(id)}/progress`, { state: obj }, "PUT");
    toast("Progress replaced");
    await refresh();
    await viewCourse();
  } catch (err) {
    toast(err.message, { kind: "bad" });
  }
}

async function deleteCourse(id) {
  const typed = ($("#delconfirm").value || "").trim();
  if (typed !== id) {
    toast("Type the course id exactly to confirm", { kind: "bad" });
    $("#delconfirm").focus();
    return;
  }
  try {
    const r = await api(`/api/courses/${encodeURIComponent(id)}/delete`, { confirm: typed });
    delete courseCache[id];
    await refresh();
    location.hash = "#/";
    toast(`${id} moved to ${r.trash}`);
  } catch (err) {
    toast(err.message, { kind: "bad" });
  }
}

async function rewriteModule(id, mid) {
  const notes = (document.getElementById("rwn-" + mid) || {}).value || "";
  const mode =
    (document.querySelector(`input[name="rwmode-${mid}"]:checked`) || {}).value || "rewrite";
  const stop = busy(null, "", document.getElementById("rw-" + mid));
  try {
    const { job: j } = await api(
      `/api/courses/${encodeURIComponent(id)}/modules/${encodeURIComponent(mid)}/rewrite`,
      Object.assign({ notes: notes.trim(), mode }, mediaBrief("rw-" + mid), modelBrief("rw-" + mid))
    );
    location.hash = "#/job/" + j.id;
  } catch (err) {
    stop();
    toast(err.message, { kind: "bad" });
  }
}

function paintAdd(c) {
  const from = (c.moduleList || []).find(m => m.id === route.query.from);
  const defaultPart = from ? from.part : c.parts.length ? c.parts[c.parts.length - 1].id : "";
  const sec = route.query.sec || "";
  const seed = route.query.q || "";
  const seedNotes =
    route.query.notes ||
    (from
      ? "Requested after " +
        (sec ? 'the section "' + sec + '" of ' : "finishing ") +
        from.id +
        " (" +
        from.title +
        ")."
      : "");
  $("#tabbody").innerHTML = `<form class="card" id="addform">
    <h3 class="eyebrow">Add a module</h3>
    <p class="sub">Describe what the course should go further on. One module is designed to fit the existing curriculum — building on what is there, not repeating it — writes it, adds its quiz and flashcards, and rebuilds. It is appended to the part you choose and your progress elsewhere is untouched.</p>
    ${from ? `<div class="note gap-top">Coming from <b>${esc(from.id)} · ${esc(from.title)}</b>${sec ? `, section <b>${esc(sec)}</b>` : ""}. Say what that ${sec ? "section" : "module"} left you wanting.</div>` : ""}
    <div class="field gap-top">
      <label for="x-topic">What should the new module cover?</label>
      <input type="text" id="x-topic" value="${esc(seed)}" placeholder="${from ? "e.g. the part of " + esc(from.title) + " that needs a whole session" : "e.g. reading a failed loaf backwards"}" autocomplete="off">
    </div>
    <div class="row r2">
      <div class="field">
        <label for="x-part">Append to part</label>
        <select id="x-part">${(c.parts || []).map(p => `<option value="${esc(p.id)}" ${p.id === defaultPart ? "selected" : ""}>${esc(p.name)}</option>`).join("")}</select>
      </div>
      <div class="field">
        <label for="x-min">Minutes</label>
        <input type="number" id="x-min" value="60" min="15" max="240" step="15">
        <span class="fhint">One sitting. Sixty minutes is about six sections.</span>
      </div>
    </div>
    <div class="field">
      <label for="x-notes">Direction <span class="hint">optional</span></label>
      <textarea id="x-notes" placeholder="What confused you, what you want it to assume you already know, what to avoid.">${esc(seedNotes)}</textarea>
    </div>
    ${mediaChoices("x", c, "for the new module")}
    ${modelChoice("x", "the design, the module and its study data")}
    ${providerGate()}
    <div class="actions gap-top">
      <button class="btn primary" id="extendbtn" ${providerReady() ? "" : "disabled"}>Design and write it</button>
    </div>
  </form>`;
  // The panel does not take the focus. Selecting a tab leaves the focus on the tab, which
  // is what lets the next arrow key reach the next tab — and this screen paints twice per
  // route change (the cached copy, then the fetched one), so a panel that grabbed the
  // focus would also grab it back out of whatever the reader had moved on to.
  $("#addform").onsubmit = e => {
    e.preventDefault();
    extendCourse(c.id);
  };
}

async function extendCourse(id) {
  const topic = $("#x-topic").value.trim();
  if (!topic) {
    toast("Say what it should cover", { kind: "bad" });
    $("#x-topic").focus();
    return;
  }
  const btn = $("#extendbtn");
  btn.disabled = true;
  btn.textContent = "Starting…";
  try {
    const { job: j } = await api(
      `/api/courses/${encodeURIComponent(id)}/extend`,
      Object.assign(
        {
          topic,
          part: $("#x-part").value,
          minutes: Number($("#x-min").value) || 60,
          notes: $("#x-notes").value.trim(),
        },
        mediaBrief("x"),
        modelBrief("x")
      )
    );
    location.hash = "#/job/" + j.id;
  } catch (err) {
    toast(err.message, { kind: "bad" });
    btn.disabled = false;
    btn.textContent = "Design and write it";
  }
}

function paintFiles(c) {
  const groups = {};
  (c.files || []).forEach(f => {
    const dir = f.includes("/") ? f.slice(0, f.lastIndexOf("/")) : "course";
    (groups[dir] = groups[dir] || []).push(f);
  });
  const html = Object.keys(groups)
    .sort()
    .map(
      dir => `<div class="filegroup"><h4>${esc(dir)}</h4><div class="filelist">
    ${groups[dir].map(f => `<a href="#/course/${encodeURIComponent(c.id)}/edit?path=${encodeURIComponent(f)}" data-help="${esc(f)}">${esc(f.slice(f.lastIndexOf("/") + 1))}</a>`).join("")}
  </div></div>`
    )
    .join("");
  $("#tabbody").innerHTML = `<div class="card">
    <h3 class="eyebrow">Every file of the course</h3>
    <p class="sub">A course is markdown and JSON, nothing else. Edit anything here, then Check and Build. The format is a contract: <span class="mono">## </span> headings are sections, and each module's suggestion list needs one entry per section.</p>
    ${html}</div>`;
}

/* The Resume button opens the choices first: a resumed run writes only what is missing,
   and figures and notebooks are one call each per module it touches. It gets a slot
   of its own, so Check or Build cannot wipe the form out from under it. */
function toggleResume(id) {
  const out = $("#resumeout");
  if (!out) return;
  if (out.querySelector("#rs-figures")) {
    out.innerHTML = "";
    return;
  }
  const c = courseCache[id] || {};
  out.innerHTML = `<div class="inlineform gap-top">
    <b>Resume the run.</b> <span class="sub">${esc(help("resume"))}</span>
    ${mediaChoices("rs", c, "for modules without any")}
    ${modelChoice("rs", "the modules still missing")}
    <div class="actions gap-top">
      <button class="btn warm" onclick="resumeCourse('${esc(id)}','rs')">Resume</button>
      <button class="btn sm" onclick="toggleResume('${esc(id)}')">Cancel</button>
    </div></div>`;
}

async function resumeCourse(id, prefix) {
  const stop = busy(null, "", $("#resumeout"));
  try {
    const { job: j } = await api(
      `/api/courses/${encodeURIComponent(id)}/resume`,
      Object.assign(mediaBrief(prefix || "rs"), modelBrief(prefix || "rs"))
    );
    location.hash = "#/job/" + j.id;
  } catch (err) {
    stop();
    toast(err.message, { kind: "bad" });
  }
}

async function checkCourse(id) {
  const out = $("#courseout");
  const stop = busy(out, "Checking every module, quiz and suggestion file…", "#courseops");
  try {
    const { problems } = await api(`/api/courses/${encodeURIComponent(id)}/check`, {});
    stop();
    const c = courseCache[id] || { id };
    out.innerHTML = problems.length
      ? `<div class="problems"><b>${problems.length} problem${problems.length === 1 ? "" : "s"}</b><ul>${problemList(c, problems)}</ul></div>`
      : `<p class="sub ok-text result">Consistent — ready to build. Checked in ${stop.took()}.</p>`;
  } catch (err) {
    stop();
    out.innerHTML = `<div class="problems">${esc(err.message)}</div>`;
  }
}

async function buildCourse(id) {
  const out = $("#courseout");
  const stop = busy(out, "Checking every file, then rendering the page…", "#courseops");
  try {
    const data = await api(`/api/courses/${encodeURIComponent(id)}/build`, {});
    stop();
    if (!data.built) {
      const c = courseCache[id] || { id };
      out.innerHTML = `<div class="problems"><b>Not built — fix these first</b><ul>${problemList(c, data.problems)}</ul></div>`;
      return;
    }
    const r = data.result;
    toast("Built " + id);
    delete courseCache[id];
    await refresh();
    await viewCourse();
    const o = $("#courseout");
    if (o)
      o.innerHTML = `<p class="sub ok-text result">Built in ${stop.took()}: ${r.modules} modules · ${r.sections} sections · ${r.quiz} quiz items · ${r.cards} cards · ${r.kb} KB</p>`;
  } catch (err) {
    stop();
    out.innerHTML = `<div class="problems">${esc(err.message)}</div>`;
  }
}
