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
  const status = c.error
    ? `<span class="pill off">broken</span>`
    : c.job && !FINISHED.includes(c.job.status)
      ? "" // shown on its own line below
      : c.built
        ? ""
        : `<span class="pill">not built</span>`;
  const liveLine =
    c.job && !FINISHED.includes(c.job.status)
      ? `<p class="liveline"><a class="pill live" data-jobof="${esc(c.id)}" href="#/job/${esc(c.job.id)}">${esc(jobLabel(c.job))}</a></p>`
      : "";
  const underway = p.done || p.started;
  const primary = c.built
    ? underway
      ? `<a class="btn sm" href="${courseUrl(c, "#/m/" + (p.next || ""))}">Continue ${esc(p.next || "")}</a>`
      : `<a class="btn sm" href="${courseUrl(c)}">Start</a>`
    : `<button class="btn sm" onclick="buildFromCard('${c.id}')" ${c.error ? "disabled" : ""}>Build</button>`;
  return `<div class="coursecard">
    <div class="head"><h3><a href="#/course/${encodeURIComponent(c.id)}" style="text-decoration:none;color:inherit">${esc(c.title)}</a></h3>${status}</div>
    <p class="tagline">${esc(c.tagline || "")}</p>${liveLine}
    ${underway ? `<div class="bar-track" style="margin:0 0 8px"><div class="bar-fill" style="width:${pct}%"></div></div>` : ""}
    <p class="facts">${esc(progressLine(c) || `${c.modules} module${c.modules === 1 ? "" : "s"} · ${esc(c.hours)}h`)}${c.error ? " · " + esc(c.error) : ""}</p>
    <div class="actions">
      ${primary}
      <a class="btn sm ghost" href="#/course/${encodeURIComponent(c.id)}">Manage</a>
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
        `<a class="today" href="${courseUrl(c, "#/review")}"><b>${p.due}</b> card${p.due === 1 ? "" : "s"} due · ${esc(c.title)}</a>`
      );
    // "in progress" means real work, not a page that was opened once
    if (p.started && (p.done || (p.minutes || 0) >= 5))
      items.push(
        `<a class="today" href="${courseUrl(c, "#/m/" + (p.next || ""))}"><b>${esc(p.next || "")}</b> in progress · ${esc(c.title)}</a>`
      );
  });
  if (!items.length) return "";
  return `<div class="todaystrip"><span class="eyebrow" style="margin:0 6px 0 0">Today</span>${items.join("")}</div>`;
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
      heat += `<i class="${day > t ? "future" : who.length > 1 ? "many" : who.length ? "on" : ""}" title="${esc(label)}${who.length ? " · " + esc(who.join(", ")) : ""}"></i>`;
    }
    heat += `</div>`;
  }
  const active = STATE.profile && STATE.profile !== "default" ? ` as ${esc(STATE.profile)}` : "";
  return `<div class="calendar">
    <div class="caltext"><b>${cal.streak} day${cal.streak === 1 ? "" : "s"}</b>study streak across every course${active} · ${cal.total} study day${cal.total === 1 ? "" : "s"} on record</div>
    <div class="heat">${heat}</div></div>`;
}

function viewLibrary() {
  const cards = STATE.courses.map(courseCard).join("");
  const newCard = `<div class="coursecard new">
    <h3>New course</h3>
    <p>Name a subject and an hour budget. Claude designs the curriculum, you approve it, then it writes every module.</p>
    <a class="btn" href="#/new" ${STATE.claude.available ? "" : 'style="pointer-events:none;opacity:.45"'}>+ Write a course</a>
    ${STATE.claude.available ? "" : `<p style="font-size:12.5px;margin-top:10px">Needs the <span class="mono">claude</span> command on this machine's PATH.</p>`}
  </div>
  <div class="coursecard" id="importcard">
    <h3>Bring a course in</h3>
    <p class="tagline">A zip exported from another Studio, or a course repository on GitHub or anywhere git can reach.</p>
    <div class="importbox">
      <div class="dropzone" id="dropzone">Drop a course .zip here, or <label style="display:inline;font-weight:600;color:var(--accent-ink);cursor:pointer">choose one<input type="file" id="zipfile" accept=".zip,application/zip" style="display:none"></label></div>
      <div style="display:flex;gap:8px">
        <input type="text" id="giturl" placeholder="https://github.com/you/course-repo" autocomplete="off" ${STATE.git ? "" : 'disabled title="git is not installed on this machine"'}>
        <button class="btn sm" onclick="importGit()" ${STATE.git ? "" : "disabled"}>Clone</button>
      </div>
    </div>
    <div id="importout"></div>
  </div>`;
  $("#view").innerHTML = `
    <h2 class="big">Your courses</h2>
    <p class="sub">Progress is kept here when a course is opened from Studio, so you can pick up where you left off. Each course is a folder of markdown - its own repository - in the courses directory shown under Settings.</p>
    ${calendarStrip()}
    ${todayStrip()}
    <div class="cards">${cards}${newCard}</div>`;
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
  const url = $("#giturl");
  if (url)
    url.onkeydown = e => {
      if (e.key === "Enter") {
        e.preventDefault();
        importGit();
      }
    };
}

function importReport(course) {
  const b = course.build || {};
  const built = b.built
    ? `Built. <a href="#/course/${encodeURIComponent(course.id)}">Open ${esc(course.title)}</a>.`
    : `Imported but not built — ${(b.problems || []).length} problem${(b.problems || []).length === 1 ? "" : "s"}: <a href="#/course/${encodeURIComponent(course.id)}">open it to fix them</a>.`;
  return `<p class="sub ${b.built ? "ok-text" : ""}" style="margin:10px 0 0;font-size:13px">${esc(course.id)} · ${course.modules} module${course.modules === 1 ? "" : "s"}. ${built}</p>`;
}

function importZipFile(f) {
  const out = $("#importout");
  if (!/\.zip$/i.test(f.name)) {
    toast("That is not a .zip file");
    return;
  }
  const stop = busy(out, `Uploading ${f.name}, then checking and building it…`);
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
  out.innerHTML = `<p class="sub" style="margin:10px 0 0;font-size:13px">Cloning…</p>`;
  try {
    const course = await api("/api/import/git", { url: url.trim() });
    toast("Cloned " + course.id);
    await refresh();
    render();
    const o = $("#importout");
    if (o) o.innerHTML = importReport(course);
  } catch (err) {
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
    <p class="sub">Module titles, section headings, the text itself and glossary terms, across the whole library.</p>
    <div id="searchout">${q ? `<p class="sub">Searching…</p>` : ""}</div>`;
  if (!q) return;
  api(`/api/search?q=${encodeURIComponent(q)}`)
    .then(r => {
      if (route.name !== "search" || route.query.q !== q) return;
      const out = $("#searchout");
      if (!out) return;
      if (!r.hits.length) {
        out.innerHTML = `<div class="card"><p class="sub" style="margin:0">Nothing in ${r.courses} course${r.courses === 1 ? "" : "s"} mentions that.</p></div>`;
        return;
      }
      const byCourse = {};
      r.hits.forEach(h => (byCourse[h.course] = byCourse[h.course] || []).push(h));
      out.innerHTML =
        Object.keys(byCourse)
          .map(cid => {
            const hits = byCourse[cid],
              c = STATE.courses.find(x => x.id === cid);
            return `<div class="card"><h3><a href="#/course/${encodeURIComponent(cid)}" style="text-decoration:none;color:inherit">${esc(hits[0].title)}</a></h3>
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
      ? `<a class="btn sm" href="${courseUrl(c, "#/m/" + h.mid + (h.sec != null ? "/1" : ""))}">Read</a>`
      : "";
  const edit = h.mid
    ? `<a class="btn sm ghost" href="#/course/${encodeURIComponent(h.course)}?tab=modules&rewrite=${encodeURIComponent(h.mid)}">Rewrite</a>`
    : "";
  return `<div class="hit"><p class="where">${where} · ${esc(h.kind)}</p><p class="what">${mark}</p><div class="actions">${read}${edit}</div></div>`;
}

async function buildFromCard(id) {
  const out = $("#out-" + id);
  const stop = busy(out, "Checking, then rendering the page…");
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
    <p class="sub">Claude will design the curriculum first and show it to you. Nothing is written until you approve it.</p>
    <div class="card">
      <div class="row">
        <div class="field">
          <label for="f-theme">Theme</label>
          <input type="text" id="f-theme" placeholder="negotiation" autocomplete="off">
        </div>
        <div class="field">
          <label for="f-hours">Hours</label>
          <input type="number" id="f-hours" value="20" min="3" max="200" step="1">
        </div>
        <div class="field">
          <label for="f-practitioner">Practitioner <span class="hint">what one is called</span></label>
          <input type="text" id="f-practitioner" placeholder="negotiator" autocomplete="off">
        </div>
      </div>
      <div class="field">
        <label for="f-audience">Who is studying</label>
        <input type="text" id="f-audience" value="a complete beginner" autocomplete="off">
      </div>
      <div class="field">
        <label for="f-notes">Anything else it should cover or avoid <span class="hint">optional</span></label>
        <textarea id="f-notes" placeholder="Weighted toward salary and contract talks. Skip hostage-negotiation material."></textarea>
      </div>
      <label class="radio" style="margin:0 0 4px"><input type="checkbox" id="f-figures" checked> <b>Draw figures</b> <span class="sub" style="margin:0">— one or two SVG diagrams per module where a picture beats a paragraph: a flow, a funnel, a 2x2, a build-up the reader steps through. Adds one Claude call per module.</span></label>
      <div class="field" style="margin-top:10px">
        <label>Notebooks <span class="hint">Jupyter notebooks the reader runs and edits inside each module; one Claude call per module</span></label>
        <div style="display:flex;gap:16px;flex-wrap:wrap">
          <label class="radio" style="margin:0"><input type="radio" name="f-notebooks" value="auto" checked> <b>Planner decides</b> <span class="sub" style="margin:0">— on for a subject learned by running code</span></label>
          <label class="radio" style="margin:0"><input type="radio" name="f-notebooks" value="yes"> <b>Yes</b></label>
          <label class="radio" style="margin:0"><input type="radio" name="f-notebooks" value="no"> <b>No</b></label>
        </div>
      </div>
      ${modelChoice("f", "the curriculum, every module and the study data")}
      <div class="actions" style="margin-top:6px">
        <button class="btn" id="planbtn">Plan the course</button>
        <a class="btn ghost" href="#/">Cancel</a>
      </div>
      <p class="sub" style="margin:14px 0 0;font-size:13px">A 20-hour course is about 20 modules. Writing them all takes a while — the progress view shows each one as it lands, and you can stop at any point.</p>
    </div>`;
  $("#f-theme").focus();
  $("#planbtn").onclick = startGeneration;
}

async function startGeneration() {
  const theme = $("#f-theme").value.trim();
  if (!theme) {
    toast("Give it a theme first");
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
    toast(err.message);
    btn.disabled = false;
    btn.textContent = "Plan the course";
  }
}
