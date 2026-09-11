/* ---------- library ---------- */

function progressLine(c) {
  const p = c.progress || {};
  if (!p.modules) return "";
  const bits = [`${p.done} of ${p.modules} modules`];
  if (p.minutes) bits.push(`${p.minutes} min studied`);
  if (p.due) bits.push(`${p.due} card${p.due === 1 ? "" : "s"} due`);
  if (p.updatedAt) bits.push("last studied " + ago(p.updatedAt / 1000));
  return bits.join(" · ");
}

function courseCard(c) {
  const p = c.progress || {};
  const pct = Math.round((p.pct || 0) * 100);
  const running = c.job && !FINISHED.includes(c.job.status);
  const status = c.error
    ? `<span class="pill off" data-help="${esc(help("needs fixing"))}">needs fixing</span>`
    : running || c.built
      ? ""
      : `<span class="pill">not built</span>`;
  const liveLine = running
    ? `<p class="liveline"><a class="pill live" data-jobof="${esc(c.id)}" href="#/job/${esc(c.job.id)}">${esc(jobLabel(c.job))}</a></p>`
    : "";
  const underway = p.done || p.started;
  const primary = c.built
    ? underway
      ? `<a class="btn sm primary" href="${courseUrl(c, "#/m/" + (p.next || ""))}">Continue ${esc(p.next || "")}</a>`
      : `<a class="btn sm primary" href="${courseUrl(c)}">Start</a>`
    : `<button class="btn sm primary" id="build-${esc(c.id)}" onclick="buildFromCard('${c.id}')" ${c.error || running ? "disabled" : ""}>Build</button>`;
  return `<div class="coursecard">
    <div class="head"><h3><a class="plain" href="#/course/${encodeURIComponent(c.id)}">${esc(c.title)}</a></h3>${status}</div>
    <p class="tagline">${esc(c.tagline || "")}</p>${liveLine}
    ${underway ? `<div class="bar-track"><div class="bar-fill" style="width:${pct}%"></div></div>` : ""}
    <p class="facts">${esc(progressLine(c) || `${c.modules} module${c.modules === 1 ? "" : "s"} · ${esc(c.hours)}h`)}${c.error ? " · " + esc(c.error) : ""}</p>
    <div class="actions">
      ${primary}
      <a class="btn sm" href="#/course/${encodeURIComponent(c.id)}">Manage</a>
    </div>
    <div id="out-${c.id}"></div>
  </div>`;
}

function todayStrip() {
  // Across every course: what is due and what is half-done. The "open the app and know
  // what to do" moment a learning platform owes its reader.
  const items = [];
  STATE.courses.forEach(c => {
    const p = c.progress || {};
    if (!c.built || !p.modules) return;
    if (p.due)
      items.push(
        `<a class="chip" href="${courseUrl(c, "#/review")}"><b>${p.due}</b> card${p.due === 1 ? "" : "s"} due · ${esc(c.title)}</a>`
      );
    // "in progress" means real work, not a page that was opened once
    if (p.started && (p.done || (p.minutes || 0) >= 5))
      items.push(
        `<a class="chip" href="${courseUrl(c, "#/m/" + (p.next || ""))}"><b>${esc(p.next || "")}</b> in progress · ${esc(c.title)}</a>`
      );
  });
  if (!items.length) return "";
  return `<div class="todaystrip"><h3 class="eyebrow">Today</h3>${items.join("")}</div>`;
}

function calendarStrip() {
  const cal = STATE.calendar;
  if (!cal || !cal.total) return "";
  const t = cal.today,
    days = cal.days || {};
  const dow = (new Date(t * 86400000).getUTCDay() + 6) % 7;
  const weeks = 17,
    start = t - dow - (weeks - 1) * 7;
  let heat = "";
  for (let w = 0; w < weeks; w++) {
    heat += `<div class="hcol">`;
    for (let d = 0; d < 7; d++) {
      const day = start + w * 7 + d,
        who = days[String(day)] || [];
      const label = new Date(day * 86400000).toLocaleDateString(undefined, {
        day: "numeric",
        month: "short",
      });
      heat += `<i class="${day > t ? "future" : who.length > 1 ? "many" : who.length ? "on" : ""}" data-help="${esc(label)}${who.length ? " · " + esc(who.join(", ")) : ""}"></i>`;
    }
    heat += `</div>`;
  }
  const active = STATE.profile && STATE.profile !== "default" ? ` as ${esc(STATE.profile)}` : "";
  return `<div class="calendar">
    <div class="caltext"><b>${cal.streak} day${cal.streak === 1 ? "" : "s"}</b>study streak across every course${active} · ${cal.total} study day${cal.total === 1 ? "" : "s"} on record</div>
    <div class="heat">${heat}</div></div>`;
}

/* What happened last, when nothing is happening now. A failed run is otherwise reachable
   only through the back button. */
function lastRunLine() {
  if (liveJobs().length) return "";
  const j = lastFinishedJob();
  if (!j) return "";
  const who = (j.meta || {}).course || (j.meta || {}).theme || "";
  const word = j.status === "done" ? "finished" : j.status;
  return `<p class="sub">Last run: ${esc(kindLabel(j.kind))}${who ? " · " + esc(who) : ""} ${esc(word)} ${esc(ago(j.finished || j.started))} —
    <a href="#/job/${esc(j.id)}">view it</a> · <a href="#/jobs">every recent run</a></p>`;
}

/* A model is what writes a course. If none can answer, say it once, at the top, with
   the two commands that fix it — not as a silently greyed button. */
function providerBanner() {
  if (providerReady()) return "";
  return `<div class="note gap-top"><b>${esc(providerName())} is not answering.</b> Studio can still open, build and export a course,
    but it cannot write one. ${esc(llmState().hint || "Configure a provider that can answer")}, then reload.
    <a href="#/settings">Settings &amp; logs</a> shows what Studio sees.</div>`;
}

/* Bringing a course in is a way of getting a course, so it sits in the grid beside "New
   course" rather than under a disclosure: cloning from GitHub is how somebody else's course
   arrives, and it is not a footnote. */
function importCard() {
  return `<div class="coursecard" id="importcard">
    <h3>Bring a course in</h3>
    <p class="tagline">A zip exported from another Studio, or a course repository on GitHub or anywhere git can reach.</p>
    <div class="importbox">
      <div class="dropzone" id="dropzone">Drop a course .zip here, or
        <label class="inlinelabel">choose one<input type="file" id="zipfile" accept=".zip,application/zip" class="hidden"></label></div>
      <form class="rowline" id="gitform">
        <label class="visually-hidden" for="giturl">Course repository URL</label>
        <input type="text" id="giturl" placeholder="https://github.com/you/course-repo" autocomplete="off" ${STATE.git ? "" : 'disabled data-help="git is not installed on this machine"'}>
        <button class="btn sm" id="clonebtn" ${STATE.git ? "" : "disabled"}>Clone</button>
      </form>
    </div>
    <div id="importout"></div>
  </div>`;
}

/* Nothing here yet: one hero with the two ways in, and none of the furniture that only
   makes sense once there are courses to show. */
function firstRun() {
  $("#view").innerHTML = `
    ${providerBanner()}
    <div class="firstrun">
      <h2 class="big">No courses yet</h2>
      <p class="lede">Name a subject and an hour budget. The model designs the curriculum, you approve it,
        and it writes every module, quiz and flashcard. Or bring in a course somebody else wrote.</p>
      <div class="rowline center wrapped">
        ${newCourseButton("primary")}
        <button class="btn" onclick="document.getElementById('importcard').scrollIntoView({block:'center'})">Bring one in</button>
      </div>
    </div>
    <div class="cards">${importCard()}</div>`;
  bindImport();
}

function newCourseButton(kind) {
  const ok = providerReady();
  return ok
    ? `<a class="btn ${kind || ""}" href="#/new">New course</a>`
    : `<button class="btn ${kind || ""}" disabled data-help="Studio cannot reach ${esc(providerName())}, which is what writes a course.">New course</button>`;
}

function viewLibrary() {
  if (!STATE.courses.length) return firstRun();
  const cards = STATE.courses.map(courseCard).join("");
  const newCard = `<div class="coursecard new">
    <h3>New course</h3>
    <p>Name a subject and an hour budget. The model designs the curriculum, you approve it, then it writes every module.</p>
    ${newCourseButton("primary")}
  </div>`;
  $("#view").innerHTML = `
    ${liveJobBanner()}
    ${providerBanner()}
    <h2 class="big">Your courses</h2>
    <p class="lede">Progress is kept here when a course is opened from Studio, so you can pick up where you left off.
      Each course is a folder of markdown — its own repository — in the courses directory shown under Settings.</p>
    ${lastRunLine()}
    ${calendarStrip()}
    ${todayStrip()}
    <div class="cards">${cards}${newCard}${importCard()}</div>`;
  bindImport();
}

function bindImport() {
  const file = $("#zipfile"),
    zone = $("#dropzone");
  if (file)
    file.onchange = () => {
      if (file.files[0]) importZipFile(file.files[0]);
    };
  if (zone) {
    zone.ondragover = e => {
      e.preventDefault();
      zone.classList.add("over");
    };
    zone.ondragleave = () => zone.classList.remove("over");
    zone.ondrop = e => {
      e.preventDefault();
      zone.classList.remove("over");
      const f = e.dataTransfer.files[0];
      if (f) importZipFile(f);
    };
  }
  const form = $("#gitform");
  if (form)
    form.onsubmit = e => {
      e.preventDefault();
      importGit();
    };
}

function importReport(course) {
  const b = course.build || {};
  const built = b.built
    ? `Built. <a href="#/course/${encodeURIComponent(course.id)}">Open ${esc(course.title)}</a>.`
    : `Imported but not built — ${(b.problems || []).length} problem${(b.problems || []).length === 1 ? "" : "s"}: <a href="#/course/${encodeURIComponent(course.id)}">open it to fix them</a>.`;
  return `<p class="sub result ${b.built ? "ok-text" : ""}">${esc(course.id)} · ${course.modules} module${course.modules === 1 ? "" : "s"}. ${built}</p>`;
}

function importZipFile(f) {
  const out = $("#importout");
  if (!/\.zip$/i.test(f.name)) {
    toast("That is not a .zip file", { kind: "bad" });
    return;
  }
  const stop = busy(out, `Uploading ${f.name}, then checking and building it…`, "#importcard");
  const reader = new FileReader();
  reader.onload = async () => {
    try {
      const course = await api("/api/import", { name: f.name, data: reader.result });
      stop();
      toast("Imported " + course.id);
      await refresh();
      render();
      const o = $("#importout");
      if (o) o.innerHTML = importReport(course);
    } catch (err) {
      stop();
      const o = $("#importout");
      if (o) o.innerHTML = `<div class="problems">${esc(err.message)}</div>`;
    }
  };
  reader.readAsDataURL(f);
}

async function importGit() {
  const url = ($("#giturl") || {}).value || "",
    out = $("#importout");
  if (!url.trim()) {
    $("#giturl").focus();
    return;
  }
  const stop = busy(out, "Cloning the repository, then checking and building it…", "#importcard");
  try {
    const course = await api("/api/import/git", { url: url.trim() });
    stop();
    toast("Cloned " + course.id);
    await refresh();
    render();
    const o = $("#importout");
    if (o) o.innerHTML = importReport(course);
  } catch (err) {
    stop();
    const o = $("#importout");
    if (o) o.innerHTML = `<div class="problems">${esc(err.message)}</div>`;
  }
}

/* ---------- search ---------- */

function viewSearch() {
  const q = route.query.q || "";
  const input = $("#searchq");
  if (input && input.value !== q) input.value = q;
  $("#view").innerHTML = `<p class="crumb"><a href="#/">Courses</a> › Search</p>
    <h2 class="big">${q ? `Results for “${esc(q)}”` : "Search every course"}</h2>
    <p class="lede">Module titles, section headings, the text itself and glossary terms, across the whole library.</p>
    <form class="rowline" id="searchpage">
      <label class="visually-hidden" for="searchq2">Search every course</label>
      <input type="search" id="searchq2" value="${esc(q)}" placeholder="Search every course" autocomplete="off">
      <button class="btn primary">Search</button>
    </form>
    <div id="searchout">${q ? `<p class="sub result">Searching…</p>` : ""}</div>`;
  $("#searchpage").onsubmit = e => {
    e.preventDefault();
    const v = $("#searchq2").value.trim();
    if (v) location.hash = "#/search?q=" + encodeURIComponent(v);
  };
  if (!q) return;
  api(`/api/search?q=${encodeURIComponent(q)}`)
    .then(r => {
      if (route.name !== "search" || route.query.q !== q) return;
      const out = $("#searchout");
      if (!out) return;
      if (!r.hits.length) {
        out.innerHTML = `<div class="card result"><p class="sub">Nothing in ${r.courses} course${r.courses === 1 ? "" : "s"} mentions that.</p></div>`;
        return;
      }
      const byCourse = {};
      r.hits.forEach(h => (byCourse[h.course] = byCourse[h.course] || []).push(h));
      out.innerHTML =
        Object.keys(byCourse)
          .map(cid => {
            const hits = byCourse[cid],
              c = STATE.courses.find(x => x.id === cid);
            return `<div class="card"><h3><a class="plain" href="#/course/${encodeURIComponent(cid)}">${esc(hits[0].title)}</a></h3>
        ${hits.map(h => searchHit(h, c)).join("")}</div>`;
          })
          .join("") +
        (r.total > r.hits.length
          ? `<p class="sub">Showing ${r.hits.length} of ${r.total} hits — narrow the search.</p>`
          : "");
    })
    .catch(err => {
      const out = $("#searchout");
      if (out) out.innerHTML = `<div class="problems">${esc(err.message)}</div>`;
    });
}

function searchHit(h, c) {
  const mark = esc(h.text).replace(
    new RegExp(esc(route.query.q).replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "ig"),
    m => `<mark>${m}</mark>`
  );
  const where =
    h.kind === "term"
      ? "Glossary"
      : `<b>${esc(h.mid)}</b> · ${esc(h.module)}${h.heading ? " · " + esc(h.heading) : ""}`;
  const read =
    c && c.built && h.mid
      ? `<a class="btn sm" href="${courseUrl(c, "#/m/" + h.mid + (h.sec != null ? "/read" : ""))}">Read</a>`
      : "";
  const edit = h.mid
    ? `<a class="btn sm" href="#/course/${encodeURIComponent(h.course)}?tab=modules&rewrite=${encodeURIComponent(h.mid)}">Patch or rewrite…</a>`
    : "";
  return `<div class="hit"><p class="where">${where} · ${esc(h.kind)}</p><p class="what">${mark}</p><div class="actions">${read}${edit}</div></div>`;
}

async function buildFromCard(id) {
  const out = $("#out-" + id);
  const btn = document.getElementById("build-" + id);
  const stop = busy(out, "Checking, then rendering the page…", btn);
  try {
    const data = await api(`/api/courses/${encodeURIComponent(id)}/build`, {});
    stop();
    if (!data.built) {
      out.innerHTML = `<div class="problems"><b>Not built — ${data.problems.length} problem${data.problems.length === 1 ? "" : "s"}</b><ul>${data.problems
        .slice(0, 6)
        .map(p => `<li>${esc(p)}</li>`)
        .join(
          ""
        )}</ul><a href="#/course/${encodeURIComponent(id)}">Open the course page to fix them</a></div>`;
      return;
    }
    toast("Built " + id + " in " + stop.took());
    await refresh();
    render();
  } catch (err) {
    stop();
    out.innerHTML = `<div class="problems">${esc(err.message)}</div>`;
  }
}

/* ---------- new course ---------- */

function viewNew() {
  $("#view").innerHTML = `
    <p class="crumb"><a href="#/">Courses</a> › New course</p>
    <h2 class="big">New course</h2>
    <p class="lede">The curriculum is designed first and shown to you. Nothing is written until you approve it.</p>
    ${providerGate()}
    <form class="card" id="newform">
      <div class="row">
        <div class="field">
          <label for="f-theme">Theme</label>
          <input type="text" id="f-theme" placeholder="negotiation" autocomplete="off">
          <span class="fhint">The subject, as you would say it out loud.</span>
        </div>
        <div class="field">
          <label for="f-hours">Hours</label>
          <input type="number" id="f-hours" value="20" min="3" max="200" step="1">
          <span class="fhint">Roughly one module per hour.</span>
        </div>
        <div class="field">
          <label for="f-practitioner">Practitioner</label>
          <input type="text" id="f-practitioner" placeholder="negotiator" autocomplete="off">
          <span class="fhint">${esc(help("practitioner"))}</span>
        </div>
      </div>
      <div class="field">
        <label for="f-audience">Who is studying</label>
        <input type="text" id="f-audience" value="a complete beginner" autocomplete="off">
        <span class="fhint">What the reader already knows decides where module one starts.</span>
      </div>
      <div class="field">
        <label for="f-notes">Anything else it should cover or avoid <span class="hint">optional</span></label>
        <textarea id="f-notes" placeholder="Weighted toward salary and contract talks. Skip hostage-negotiation material."></textarea>
      </div>
      <label class="radio"><input type="checkbox" id="f-figures" checked> <b>Draw figures</b></label>
      <span class="fhint">One or two SVG diagrams per module where a picture beats a paragraph: a flow, a funnel, a 2×2, a build-up the reader steps through. One extra call per module.</span>
      <div class="field gap-top">
        <label>Notebooks</label>
        <span class="fhint">Jupyter notebooks the reader runs and edits inside each module. Worth it for a subject you learn by running code; one extra call per module.</span>
        <div class="rowline wrapped gap-top">
          <label class="radio"><input type="radio" name="f-notebooks" value="auto" checked> <b>Planner decides</b></label>
          <label class="radio"><input type="radio" name="f-notebooks" value="yes"> <b>Yes</b></label>
          <label class="radio"><input type="radio" name="f-notebooks" value="no"> <b>No</b></label>
        </div>
      </div>
      ${modelChoice("f", "the curriculum, every module and the study data")}
      <div class="actions gap-top">
        <button class="btn primary" id="planbtn" ${providerReady() ? "" : "disabled"}>Design the curriculum</button>
        <a class="btn" href="#/">Cancel</a>
      </div>
      <p class="sub result">A 20-hour course is about 20 modules. Writing them all takes a while — the run shows each one as it lands, and you can stop at any point.</p>
    </form>`;
  $("#f-theme").focus();
  $("#newform").onsubmit = e => {
    e.preventDefault();
    startGeneration();
  };
}

async function startGeneration() {
  const theme = $("#f-theme").value.trim();
  if (!theme) {
    toast("Give it a theme first", { kind: "bad" });
    $("#f-theme").focus();
    return;
  }
  const btn = $("#planbtn");
  btn.disabled = true;
  btn.textContent = "Designing the curriculum…";
  try {
    const notebooks =
      (document.querySelector('input[name="f-notebooks"]:checked') || {}).value || "auto";
    const brief = Object.assign(
      {
        theme,
        hours: Number($("#f-hours").value) || 20,
        practitioner: $("#f-practitioner").value.trim(),
        audience: $("#f-audience").value.trim(),
        notes: $("#f-notes").value.trim(),
        figures: $("#f-figures").checked,
        notebooks,
      },
      modelBrief("f")
    );
    const { job: j } = await api("/api/generate", brief);
    location.hash = "#/job/" + j.id;
  } catch (err) {
    toast(err.message, { kind: "bad" });
    btn.disabled = false;
    btn.textContent = "Design the curriculum";
  }
}
