/* ---------- one course ---------- */

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
    $("#view").innerHTML =
      `<div class="card"><h3>Cannot open ${esc(id)}</h3><p class="sub">${esc(err.message)}</p></div>`;
    return;
  }
  courseCache[id] = c;
  if (route.id !== id) return; // navigated away while loading
  paintCourse(c);
}

function paintCourse(c) {
  const p = c.progress || {};
  const pct = Math.round((p.pct || 0) * 100);
  const tab = route.query.tab || "modules";
  const live = c.job && !FINISHED.includes(c.job.status);
  const head = `
    <p class="crumb"><a href="#/">Courses</a> › ${esc(c.title)}</p>
    <div class="card"><div class="hero">
      <div>
        <h2 class="big" style="margin:0">${esc(c.title)}</h2>
        <p class="sub" style="margin:2px 0 0">${esc(c.tagline || "")}${c.audience ? " · for " + esc(c.audience) : ""}</p>
        <div class="bar-track" style="margin:14px 0 6px;max-width:520px"><div class="bar-fill" style="width:${pct}%"></div></div>
        <div class="stats">
          <div class="stat"><b>${pct}%</b><span>complete</span></div>
          <div class="stat"><b>${p.done || 0}<span style="font-size:13px;color:var(--muted)">/${c.modules}</span></b><span>modules done</span></div>
          <div class="stat"><b>${p.minutes || 0}m</b><span>studied</span></div>
          <div class="stat"><b>${p.cards || 0}</b><span>cards · ${p.due || 0} due</span></div>
          <div class="stat"><b>${esc(fmtH((c.hours || 0) * 60))}</b><span>planned</span></div>
        </div>
      </div>
      <div class="actions" id="courseops" style="flex-direction:column;align-items:stretch;min-width:180px">
        ${
          c.built
            ? `<a class="btn" href="${courseUrl(c, p.done || p.started ? "#/m/" + (p.next || "") : "#/home")}">${p.done || p.started ? "Continue at " + esc(p.next || "") : "Start the course"}</a>
             <a class="btn ghost" href="${courseUrl(c)}">Open the course</a>`
            : `<span class="pill" style="text-align:center">not built yet</span>`
        }
        ${
          live
            ? `<a class="btn ghost" data-jobof="${esc(c.id)}" href="#/job/${c.job.id}">${esc(jobLabel(c.job))} — view</a>`
            : `${c.resumable ? `<button class="btn" style="background:var(--warm)" onclick="toggleResume('${c.id}')">Resume the run…</button>` : ""}
                  <button class="btn ghost" onclick="checkCourse('${c.id}')">Check</button>
                  <button class="btn ghost" onclick="buildCourse('${c.id}')">${c.built ? "Rebuild" : "Build"}</button>
                  <a class="btn ghost" href="/api/courses/${encodeURIComponent(c.id)}/export" download="${esc(c.id)}.zip" title="The course folder as a zip, without .git">Export .zip</a>`
        }
      </div>
    </div>
    <div id="courseout"></div>
    ${c.error ? `<div class="problems">${esc(c.error)}</div>` : ""}
    ${c.resumable && !live ? `<div class="note" style="margin-top:12px">This course's generation run did not finish — the saved curriculum is still here. <b>Resume the run</b> keeps every module and study-data entry already on disk and writes only what is missing, then builds. See <a href="#/settings">Settings &amp; logs</a> for why it stopped.</div>` : ""}
    ${c.built ? `<p class="sub" style="margin:12px 0 0;font-size:12.5px">Built ${esc(ago(c.builtAt))}. A rebuild keeps your progress — it lives with the platform, not the page.</p>` : ""}
    </div>
    <div class="tabs">
      ${[
        ["modules", "Modules"],
        ["add", "Add a module"],
        [
          "questions",
          "Questions" +
            ((c.questions || []).length ? ` <span class="count">${c.questions.length}</span>` : ""),
        ],
        ["files", "Files"],
        ["settings", "Settings"],
      ]
        .map(
          ([k, l]) =>
            `<button class="tab ${tab === k ? "active" : ""}" onclick="setTab('${k}')">${l}</button>`
        )
        .join("")}
    </div>
    <div id="tabbody"></div>`;
  $("#view").innerHTML = head;
  if (tab === "add") paintAdd(c);
  else if (tab === "files") paintFiles(c);
  else if (tab === "questions") paintQuestions(c);
  else if (tab === "settings") paintSettings(c);
  else paintModules(c);
}

function setTab(tab) {
  const q = Object.assign({}, route.query, { tab });
  delete q.rewrite;
  delete q.from;
  delete q.sec;
  delete q.q;
  location.hash = `#/course/${encodeURIComponent(route.id)}?` + new URLSearchParams(q).toString();
}

function paintModules(c) {
  const mp = c.moduleProgress || {},
    reviews = c.reviews || {};
  const manyParts = (c.parts || []).length > 1;
  const parts = (c.parts || [])
    .map(part => {
      const mods = (c.moduleList || []).filter(m => m.part === part.id);
      const rows = mods
        .map((m, i) => {
          const st = mp[m.id] || {};
          const dot = st.done ? "done" : st.read || st.minutes || st.quiz ? "part" : "";
          const state = st.done
            ? "completed"
            : st.read
              ? `${st.read}/${m.sections} sections read${st.quiz ? " · quiz done" : ""}`
              : "";
          const open = c.built
            ? `<a class="btn sm ghost" href="${courseUrl(c, "#/m/" + m.id)}">Read</a>`
            : "";
          const rewriting = route.query.rewrite === m.id;
          const rv = reviews[m.id];
          // The owner's "this is good" outranks the review's verdict. A stale one, from before
          // the module's last rewrite or edit, is about text that is no longer there: shown
          // greyed with a note, never as current.
          const good = !!(rv && rv.accepted);
          const shown = good ? "good" : (rv || {}).verdict;
          const verdict = !rv
            ? ""
            : rv.stale
              ? `<button class="verdict stale" title="${good ? "Marked good" : "Reviewed"} ${new Date(good ? rv.accepted : rv.at).toLocaleString()}, but the module changed on ${new Date(rv.moduleChangedAt).toLocaleString()} — judge it again" onclick="toggleEl('rv-${m.id}')">${esc(shown)} · before edit</button>`
              : good
                ? `<button class="verdict solid" title="You marked this good on ${new Date(rv.accepted).toLocaleString()}${rv.ownerOnly ? "" : " — the review's findings are kept underneath"}" onclick="toggleEl('rv-${m.id}')">good ✓</button>`
                : `<button class="verdict ${rv.verdict === "solid" ? "solid" : rv.verdict === "rewrite" ? "rewrite" : "needs"}" title="Reviewed ${new Date(rv.at).toLocaleDateString()} — click for the findings" onclick="toggleEl('rv-${m.id}')">${esc(rv.verdict)}</button>`;
          const isGood = good && !rv.stale;
          return `<div class="modrow" id="mod-${m.id}">
        <span class="order"><button title="Move up" aria-label="Move ${esc(m.id)} up" ${i === 0 ? "disabled" : ""} onclick="moveModule('${c.id}','${m.id}','${part.id}',${i - 1})">▲</button><button title="Move down" aria-label="Move ${esc(m.id)} down" ${i === mods.length - 1 ? "disabled" : ""} onclick="moveModule('${c.id}','${m.id}','${part.id}',${i + 1})">▼</button></span>
        <span class="mid">${esc(m.id)}</span>
        <span class="title"><span class="dot ${dot}" title="${esc(state)}" style="margin-right:6px"></span>${esc(m.title)} ${verdict}<small>${m.minutes} min · ${m.sections} sections${m.figures ? ` · ${m.figures} figure${m.figures === 1 ? "" : "s"}` : ""}${m.notebooks ? ` · ${m.notebooks} notebook${m.notebooks === 1 ? "" : "s"}` : ""}${state ? " · " + esc(state) : ""}</small></span>
        <span class="rowtools">${open}
          <button class="btn sm ghost kebab" aria-haspopup="menu" aria-expanded="false" aria-label="More actions for ${esc(m.id)}" title="Edit, review, patch, move, remove" onclick="toggleMenu(event,'${m.id}')">⋯</button>
          <div class="menu hidden" id="menu-${m.id}" role="menu">
            <a role="menuitem" href="#/course/${encodeURIComponent(c.id)}/edit?path=${encodeURIComponent(m.path)}">Edit the text<small>the markdown, by hand</small></a>
            <button role="menuitem" onclick="closeMenus();reviewModule('${c.id}','${m.id}')" ${STATE.claude.available ? "" : "disabled"}>${rv && !rv.ownerOnly ? "Review again" : "Review with Claude"}<small>a verdict, gaps, errors, quiz issues</small></button>
            <button role="menuitem" onclick="closeMenus();acceptModule('${c.id}','${m.id}',${isGood ? "false" : "true"})">${isGood ? "Withdraw “good”" : "Mark as good"}<small>${isGood ? "back to the review's verdict" : "your verdict outranks the review"}</small></button>
            <button role="menuitem" onclick="closeMenus();toggleRewrite('${m.id}')">Patch or rewrite…<small>with notes, by Claude</small></button>
            ${figuresMenuItem(c, m)}
            ${notebooksMenuItem(c, m)}
            ${manyParts ? `<div class="sep"></div><label class="label" for="part-${m.id}">Move to part</label><select id="part-${m.id}" onchange="moveModule('${c.id}','${m.id}',this.value,-1)">${(c.parts || []).map(p => `<option value="${esc(p.id)}" ${p.id === part.id ? "selected" : ""}>${esc(p.name)}</option>`).join("")}</select>` : ""}
            <div class="sep"></div>
            <button role="menuitem" class="danger" onclick="closeMenus();toggleRemove('${m.id}')">Remove…<small>moves the file to the trash</small></button>
          </div></span>
      </div>
      ${rv ? reviewBox(c, m, rv) : ""}
      <div class="inlineform ${rewriting ? "" : "hidden"}" id="rw-${m.id}">
        <label for="rwn-${m.id}">What should change in ${esc(m.id)}?</label>
        <textarea id="rwn-${m.id}" rows="3" placeholder="Go much deeper on the worked example in Core concepts; the current version stops before the arithmetic. Keep the exercise.">${esc(route.query.rewrite === m.id && route.query.q ? route.query.q : "")}</textarea>
        ${mediaChoices("rw-" + m.id, c, "for a full rewrite")}
        <div class="rwmodes">
          <label class="radio"><input type="radio" name="rwmode-${m.id}" value="patch" ${route.query.rewrite === m.id && route.query.q ? "checked" : ""}> <b>Patch</b> <span class="sub" style="margin:0">— change only what the notes say. Every other sentence, the cards and the untouched quiz items stay as they are. Right for a review's findings.</span></label>
          <label class="radio"><input type="radio" name="rwmode-${m.id}" value="rewrite" ${route.query.rewrite === m.id && route.query.q ? "" : "checked"}> <b>Rewrite</b> <span class="sub" style="margin:0">— write the module again from its design, with the notes as direction. New text, new quiz, new cards.</span></label>
        </div>
        <div class="actions" style="margin-top:10px">
          <button class="btn sm" onclick="rewriteModule('${c.id}','${m.id}')">Apply to ${esc(m.id)}</button>
          <button class="btn sm ghost" onclick="toggleRewrite('${m.id}')">Cancel</button>
          <span class="sub" style="font-size:12px;margin:0 0 0 6px">Keeps the id and position. Your progress for it stays; after a rewrite, section ticks may shift.</span>
        </div>
      </div>
      <div class="inlineform hidden" id="rm-${m.id}" style="border-color:var(--bad);background:var(--bad-soft)">
        <b>Remove ${esc(m.id)} · ${esc(m.title)}?</b>
        <p class="sub" style="margin:4px 0 10px;font-size:13px">The file moves to <span class="mono">state/trash/</span>, its quiz, cards and questions are dropped, and the id is never reused. Rebuild afterwards.</p>
        <div class="actions">
          <button class="btn sm danger" onclick="removeModule('${c.id}','${m.id}')">Yes, remove it</button>
          <button class="btn sm ghost" onclick="toggleRemove('${m.id}')">Keep it</button>
        </div>
      </div>`;
        })
        .join("");
      return `<div class="partblock">
      <div class="parttitle"><h3>${esc(part.name)}</h3><span class="tag">${esc(part.hours)}h</span><span class="tag">${mods.length} module${mods.length === 1 ? "" : "s"}</span></div>
      ${part.blurb ? `<p class="blurb">${esc(part.blurb)}</p>` : ""}
      ${rows || `<p class="sub" style="font-size:13px">No modules in this part yet.</p>`}
    </div>`;
    })
    .join("");
  $("#tabbody").innerHTML =
    (parts && figuresBar(c) + notebooksBar(c) + parts) ||
    `<div class="card"><p class="sub" style="margin:0">This course has no readable modules yet.</p></div>`;
  if (route.query.rewrite) {
    const el = document.getElementById("rwn-" + route.query.rewrite);
    if (el) {
      el.scrollIntoView({ block: "center" });
      el.focus();
    }
  }
}

function reviewBox(c, m, rv) {
  const list = (rows, first) =>
    rows.length
      ? `<ul style="margin:0;padding-left:18px">${rows.map(r => `<li>${r[first] ? `<b>${esc(r[first])}</b> — ` : ""}${esc(r.issue)}${r.fix ? ` <i>Fix: ${esc(r.fix)}</i>` : ""}</li>`).join("")}</ul>`
      : `<p class="sub" style="margin:0;font-size:13px">Nothing.</p>`;
  return `<div class="reviewbox hidden" id="rv-${m.id}">
    ${rv.stale ? `<div class="note" style="margin:0 0 10px">This ${rv.accepted ? "verdict" : "review"} is from <b>${new Date(rv.accepted || rv.at).toLocaleString()}</b>; the module was rewritten or edited on <b>${new Date(rv.moduleChangedAt).toLocaleString()}</b>, so it describes the old text. <a href="#" onclick="reviewModule('${c.id}','${m.id}');return false">Review again</a> for a verdict on what is there now, or mark it good if you have read it.</div>` : ""}
    ${rv.accepted && !rv.stale ? `<p class="sub ok-text" style="margin:0 0 8px;font-size:13px">You marked this module good on ${new Date(rv.accepted).toLocaleString()}.${rv.ownerOnly ? " Claude has not reviewed it." : " The review's findings below are kept for reference."}</p>` : ""}
    ${
      rv.ownerOnly
        ? ""
        : `<p style="margin:0 0 8px;font-size:14px">${esc(rv.summary)}</p>
    <h4>Gaps</h4>${list(rv.gaps || [], "where")}
    <h4>Errors</h4>${list(rv.errors || [], "where")}
    <h4>Quiz</h4>${list(rv.quiz || [], "item")}`
    }
    <div class="actions" style="margin-top:12px">
      ${rv.rewriteBrief && !(rv.accepted && !rv.stale) ? `<a class="btn sm" href="#/course/${encodeURIComponent(c.id)}?tab=modules&rewrite=${encodeURIComponent(m.id)}&q=${encodeURIComponent(rv.rewriteBrief)}">Patch with these notes</a>` : ""}
      ${rv.accepted && !rv.stale ? "" : `<button class="btn sm ghost" onclick="acceptModule('${c.id}','${m.id}',true)" title="Your verdict: it is good as it is">This is good</button>`}
      <button class="btn sm ghost" onclick="toggleEl('rv-${m.id}')">Close</button>
      <span class="sub" style="font-size:12px;margin-left:6px">${rv.ownerOnly ? "" : `Reviewed ${new Date(rv.at).toLocaleString()}${rv.model ? " · " + esc(rv.model) : ""}`}</span>
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
    const out = $("#courseout");
    if (out)
      out.innerHTML =
        r.problems && r.problems.length
          ? `<div class="problems"><b>Moved, but the course now has ${r.problems.length} problem${r.problems.length === 1 ? "" : "s"}</b><ul>${r.problems.map(p => `<li>${esc(p)}</li>`).join("")}</ul></div>`
          : `<p class="sub ok-text" style="margin:12px 0 0">Order saved to course.json. Rebuild to publish the change; reader progress is keyed by id and unaffected.</p>`;
  } catch (err) {
    toast(err.message);
  }
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
    toast(err.message);
  }
}

async function reviewModule(id, mid) {
  try {
    const { job: j } = await api(
      `/api/courses/${encodeURIComponent(id)}/modules/${encodeURIComponent(mid)}/review`,
      {}
    );
    location.hash = "#/job/" + j.id;
  } catch (err) {
    toast(err.message);
  }
}

/* The row menu: one primary action stays on the row (Read), everything else lives here.
   One menu open at a time; a click anywhere else, or Escape, closes it. */
function toggleMenu(ev, mid) {
  ev.stopPropagation();
  const menu = document.getElementById("menu-" + mid);
  if (!menu) return;
  const wasOpen = !menu.classList.contains("hidden");
  closeMenus();
  if (!wasOpen) {
    menu.classList.remove("hidden");
    ev.currentTarget.setAttribute("aria-expanded", "true");
    const first = menu.querySelector("[role=menuitem]:not([disabled])");
    if (first) first.focus();
  }
}

function closeMenus() {
  document.querySelectorAll(".menu").forEach(m => m.classList.add("hidden"));
  document
    .querySelectorAll(".kebab[aria-expanded=true]")
    .forEach(b => b.setAttribute("aria-expanded", "false"));
}
document.addEventListener("click", e => {
  if (!e.target.closest(".menu")) closeMenus();
});
document.addEventListener("keydown", e => {
  if (e.key === "Escape") closeMenus();
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

async function removeModule(id, mid) {
  try {
    const r = await api(
      `/api/courses/${encodeURIComponent(id)}/modules/${encodeURIComponent(mid)}/remove`,
      {}
    );
    toast(`${mid} removed`);
    await refresh();
    await viewCourse();
    const out = $("#courseout");
    if (out)
      out.innerHTML =
        r.problems && r.problems.length
          ? `<div class="problems"><b>${mid} removed, but the course now has ${r.problems.length} problem${r.problems.length === 1 ? "" : "s"}</b><ul>${r.problems.map(p => `<li>${esc(p)}</li>`).join("")}</ul></div>`
          : `<p class="sub ok-text" style="margin:12px 0 0">${mid} removed — its file is in <span class="mono">${esc(r.trash || "state/trash/")}</span>. Rebuild to publish the change.</p>`;
  } catch (err) {
    toast(err.message);
  }
}

/* ---- questions: what the reader marked while studying ---- */

function paintQuestions(c) {
  const qs = c.questions || [];
  const gaps = paintGaps(c);
  if (!qs.length) {
    $("#tabbody").innerHTML = `${gaps}<div class="card"><p class="eyebrow">Open questions</p>
      <p class="sub" style="margin:0">Nothing marked yet. While reading, select a sentence and turn it into a question — every one collects here, where it can become a new module or a rewrite.</p></div>`;
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
      <div class="qmeta"><span class="mid">${esc(q.mid)}</span> ${esc(q.title)} <span class="pill ${q.status === "answered" ? "on" : ""}" style="margin-left:6px">${esc(q.status)}</span></div>
      <blockquote>${esc(q.text)}</blockquote>
      ${q.q ? `<p class="qask">${esc(q.q)}</p>` : ""}${q.note && q.note !== brief ? `<p class="qask">${esc(q.note)}</p>` : ""}
      <div class="actions">
        <a class="btn sm" href="#/course/${encodeURIComponent(c.id)}?tab=add&from=${encodeURIComponent(q.mid)}&q=${topic}&notes=${notes}">Make this a module</a>
        <a class="btn sm ghost" href="#/course/${encodeURIComponent(c.id)}?tab=modules&rewrite=${encodeURIComponent(q.mid)}&q=${notes}">Rewrite ${esc(q.mid)} with this</a>
        ${c.built ? `<a class="btn sm ghost" href="${courseUrl(c, "#/m/" + q.mid + "/1")}">Open the passage</a>` : ""}
      </div>
    </div>`;
    })
    .join("");
  $("#tabbody").innerHTML = `${gaps}<div class="card">
    <p class="eyebrow">Open questions</p>
    <p class="sub" style="font-size:13.5px">The passages you marked with a question while reading. They are the most honest map of where this course stops short — turn one into a brief.</p>
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
        <a class="btn sm ghost" href="#/course/${encodeURIComponent(c.id)}?tab=modules&rewrite=${encodeURIComponent(g.mid)}&q=${notes}">Rewrite ${esc(g.mid)} for this</a>
      </div></div>`;
    })
    .join("");
  const when = L.at ? new Date(L.at).toLocaleDateString() : "";
  return `<div class="card" style="margin-bottom:16px">
    <p class="eyebrow">Knowledge gaps${when ? ` <span class="sub" style="font-weight:400">· written ${esc(when)}</span>` : ""}</p>
    <p class="sub" style="font-size:13.5px">${esc(L.brief || "What the page's tutor has learned about this reader.")}</p>
    ${rows || `<p class="sub" style="margin:0">No open gaps.</p>`}</div>`;
}

/* ---- settings: the presentation fields of course.json, as a form ---- */

function paintSettings(c) {
  const s = c.settings || {},
    a = s.anchor || {},
    nb = s.notebooks || null;
  const milestones = (s.milestones || []).map((m, i) => milestoneRow(m, i)).join("");
  const parts = (s.parts || [])
    .map(
      p => `<div class="row" style="grid-template-columns:1fr 90px 2fr;margin-bottom:8px" data-part="${esc(p.id)}">
      <input type="text" class="p-name" value="${esc(p.name)}" aria-label="Part name">
      <input type="number" class="p-hours" value="${esc(p.hours)}" min="0" step="0.5" aria-label="Hours">
      <input type="text" class="p-blurb" value="${esc(p.blurb || "")}" placeholder="One line on what this part is for" aria-label="Blurb">
    </div>`
    )
    .join("");
  $("#tabbody").innerHTML = `<div class="card">
    <p class="eyebrow">Settings</p>
    <p class="sub" style="font-size:13.5px">Everything here is presentation and prompt — it changes what the page says and how the tutor speaks. The id <span class="mono">${esc(s.id)}</span> is locked: it is the key your progress is stored under.</p>
    <div class="row" style="grid-template-columns:2fr 2fr">
      <div class="field"><label for="s-title">Title</label><input type="text" id="s-title" value="${esc(s.title)}"></div>
      <div class="field"><label for="s-tagline">Tagline</label><input type="text" id="s-tagline" value="${esc(s.tagline)}"></div>
    </div>
    <div class="row" style="grid-template-columns:2fr 2fr">
      <div class="field"><label for="s-audience">Who is studying</label><input type="text" id="s-audience" value="${esc(s.audience)}"></div>
      <div class="field"><label for="s-practitioner">Practitioner <span class="hint">what one is called</span></label><input type="text" id="s-practitioner" value="${esc(s.practitioner)}"></div>
    </div>
    <div class="field"><label for="s-persona">Tutor persona <span class="hint">the system prompt fragment; ends with a period</span></label><textarea id="s-persona" rows="2">${esc(s.tutorPersona)}</textarea></div>
    <label>Notebooks <span class="hint">Jupyter notebooks the reader runs inside each module — for a subject learned by running code</span></label>
    <div class="row" style="grid-template-columns:auto 1fr 2fr;margin-bottom:16px;align-items:center">
      <label class="radio" style="margin:0"><input type="checkbox" id="nb-on" ${nb ? "checked" : ""}> <b>This course has notebooks</b></label>
      <input type="text" id="nb-kernel" value="${esc(nb ? nb.kernel : "")}" placeholder="Kernel, e.g. python3" aria-label="Kernel">
      <input type="text" id="nb-packages" value="${esc(nb ? (nb.packages || []).join(", ") : "")}" placeholder="Packages the notebooks import: numpy, pandas" aria-label="Packages">
    </div>
    <label>The reader's own case <span class="hint">the one real thing every exercise is applied to — a business, a kitchen, a next negotiation</span></label>
    <div class="row" style="grid-template-columns:1fr 1fr;margin-bottom:8px">
      <input type="text" id="a-label" value="${esc(a.label)}" placeholder="Label, e.g. Your business" aria-label="Label">
      <input type="text" id="a-noun" value="${esc(a.noun)}" placeholder="In a question: my business" aria-label="Noun">
    </div>
    <div class="row" style="grid-template-columns:1fr 1fr;margin-bottom:16px">
      <input type="text" id="a-prompt" value="${esc(a.prompt)}" placeholder="One line asking the reader to name it" aria-label="Prompt">
      <input type="text" id="a-placeholder" value="${esc(a.placeholder)}" placeholder="Placeholder, e.g. my sister's clinic" aria-label="Placeholder">
    </div>
    <label>Parts <span class="hint">name, hours, blurb — the course total follows the sum</span></label>
    ${parts}
    <label style="margin-top:14px">Milestones <span class="hint">the honest-read line on the stats page: after N modules, say this</span></label>
    <div id="milestones">${milestones}</div>
    <button class="btn sm ghost" onclick="addMilestone()" style="margin:6px 0 16px">+ Milestone</button>
    <div class="actions">
      <button class="btn" id="savesettings" onclick="saveSettings('${c.id}')">Save settings</button>
      <span class="sub" style="font-size:12.5px;margin:0 0 0 6px">Then Rebuild, so the page picks it up. The model Studio writes with, and the log of every run, are under <a href="#/settings">Settings &amp; logs</a>.</span>
    </div>
    <div id="settingsout"></div>
  </div>

  <div class="card">
    <p class="eyebrow">Progress backup</p>
    <p class="sub" style="font-size:13.5px">The platform's copy of your progress for this course — completion, quiz answers, flashcard schedule, notes, highlights and conversations. Download it to keep, or paste a backup (from here, or from the course page's own Backup / restore) to replace it.</p>
    <div class="actions">
      <button class="btn sm ghost" onclick="downloadProgress('${c.id}')">Download progress</button>
      <button class="btn sm ghost" onclick="toggleEl('restorebox')">Restore from a backup…</button>
    </div>
    <div id="restorebox" class="hidden" style="margin-top:12px">
      <textarea id="restoretext" rows="5" placeholder='Paste the backup JSON here. Either the raw state ({"progress": …}) or a download from this page.' style="font-family:var(--mono);font-size:12px"></textarea>
      <div class="actions" style="margin-top:8px"><button class="btn sm danger" onclick="restoreProgress('${c.id}')">Replace the platform copy</button></div>
    </div>
  </div>

  <div class="card" style="border-color:var(--bad)">
    <p class="eyebrow" style="color:var(--bad)">Delete this course</p>
    <p class="sub" style="font-size:13.5px">Moves the <span class="mono">${esc(c.id)}</span> folder (the whole course repository, if it is one) and its build to <span class="mono">state/trash/</span> and forgets the platform copy of your progress. Nothing is erased; you can move it back by hand. Type the id to confirm.</p>
    <div class="actions"><input type="text" id="delconfirm" placeholder="${esc(c.id)}" style="max-width:240px" autocomplete="off">
      <button class="btn sm danger" onclick="deleteCourse('${c.id}')">Delete course</button></div>
  </div>`;
}

function milestoneRow(m, i) {
  return `<div class="row" style="grid-template-columns:90px 1fr 36px;margin-bottom:8px" data-ms="${i}">
    <input type="number" class="ms-after" value="${esc(m.after)}" min="0" aria-label="After how many modules">
    <input type="text" class="ms-text" value="${esc(m.text)}" aria-label="Text">
    <button class="btn sm ghost" onclick="this.parentNode.remove()" title="Remove">×</button>
  </div>`;
}

function addMilestone() {
  $("#milestones").insertAdjacentHTML(
    "beforeend",
    milestoneRow({ after: 0, text: "" }, Date.now())
  );
}

async function saveSettings(id) {
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
  try {
    await api(`/api/courses/${encodeURIComponent(id)}/settings`, body);
    toast("Settings saved");
    await refresh();
    await viewCourse();
  } catch (err) {
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
    toast(err.message);
  }
}

async function restoreProgress(id) {
  let obj;
  try {
    obj = JSON.parse($("#restoretext").value);
  } catch (e) {
    toast("That is not valid JSON");
    return;
  }
  if (obj && obj.state && typeof obj.state === "object") obj = obj.state;
  if (!obj || typeof obj !== "object" || Array.isArray(obj)) {
    toast("That is not a progress backup");
    return;
  }
  obj.updatedAt = Date.now(); // it must win over whatever a course page still holds
  try {
    await api(`/api/courses/${encodeURIComponent(id)}/progress`, { state: obj }, "PUT");
    toast("Progress replaced");
    await refresh();
    await viewCourse();
  } catch (err) {
    toast(err.message);
  }
}

async function deleteCourse(id) {
  const typed = ($("#delconfirm").value || "").trim();
  if (typed !== id) {
    toast("Type the course id exactly to confirm");
    $("#delconfirm").focus();
    return;
  }
  try {
    const r = await api(`/api/courses/${encodeURIComponent(id)}/delete`, { confirm: typed });
    toast(`${id} moved to trash`);
    delete courseCache[id];
    await refresh();
    location.hash = "#/";
    setTimeout(() => toast(`It is in ${r.trash}`), 1200);
  } catch (err) {
    toast(err.message);
  }
}

async function rewriteModule(id, mid) {
  const notes = (document.getElementById("rwn-" + mid) || {}).value || "";
  const mode =
    (document.querySelector(`input[name="rwmode-${mid}"]:checked`) || {}).value || "rewrite";
  try {
    const { job: j } = await api(
      `/api/courses/${encodeURIComponent(id)}/modules/${encodeURIComponent(mid)}/rewrite`,
      Object.assign({ notes: notes.trim(), mode }, mediaBrief("rw-" + mid))
    );
    location.hash = "#/job/" + j.id;
  } catch (err) {
    toast(err.message);
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
  $("#tabbody").innerHTML = `<div class="card">
    <p class="eyebrow">Add a module</p>
    <p class="sub">Describe what the course should go further on. Claude designs one module that fits the existing curriculum — building on what is there, not repeating it — writes it, adds its quiz and flashcards, and rebuilds. It is appended to the part you choose and your progress elsewhere is untouched.</p>
    ${from ? `<div class="note" style="margin-bottom:16px">Coming from <b>${esc(from.id)} · ${esc(from.title)}</b>${sec ? `, section <b>${esc(sec)}</b>` : ""}. Say what that ${sec ? "section" : "module"} left you wanting.</div>` : ""}
    <div class="field">
      <label for="x-topic">What should the new module cover?</label>
      <input type="text" id="x-topic" value="${esc(seed)}" placeholder="${from ? "e.g. the part of " + esc(from.title) + " that needs a whole session" : "e.g. reading a failed loaf backwards"}" autocomplete="off">
    </div>
    <div class="row">
      <div class="field">
        <label for="x-part">Append to part</label>
        <select id="x-part">${(c.parts || []).map(p => `<option value="${esc(p.id)}" ${p.id === defaultPart ? "selected" : ""}>${esc(p.name)}</option>`).join("")}</select>
      </div>
      <div class="field">
        <label for="x-min">Minutes</label>
        <input type="number" id="x-min" value="60" min="15" max="240" step="15">
      </div>
      <div class="field"></div>
    </div>
    <div class="field">
      <label for="x-notes">Direction <span class="hint">optional</span></label>
      <textarea id="x-notes" placeholder="What confused you, what you want it to assume you already know, what to avoid.">${esc(seedNotes)}</textarea>
    </div>
    ${mediaChoices("x", c, "for the new module")}
    <div class="actions">
      <button class="btn" id="extendbtn" onclick="extendCourse('${c.id}')" ${STATE.claude.available ? "" : "disabled"}>Design and write it</button>
    </div>
  </div>`;
  $("#x-topic").focus();
}

async function extendCourse(id) {
  const topic = $("#x-topic").value.trim();
  if (!topic) {
    toast("Say what it should cover");
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
        mediaBrief("x")
      )
    );
    location.hash = "#/job/" + j.id;
  } catch (err) {
    toast(err.message);
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
    ${groups[dir].map(f => `<a href="#/course/${encodeURIComponent(c.id)}/edit?path=${encodeURIComponent(f)}" title="${esc(f)}">${esc(f.slice(f.lastIndexOf("/") + 1))}</a>`).join("")}
  </div></div>`
    )
    .join("");
  $("#tabbody").innerHTML = `<div class="card">
    <p class="eyebrow">Every file of the course</p>
    <p class="sub" style="font-size:13.5px">A course is markdown and JSON, nothing else. Edit anything here, then Check and Build. The format is a contract: <span class="mono">## </span> headings are sections, and each module's suggestion list needs one entry per section.</p>
    ${html}</div>`;
}

/* The Resume button opens the choices first: a resumed run writes only what is missing,
   and figures and notebooks are one Claude call each per module it touches. */
function toggleResume(id) {
  const out = $("#courseout");
  if (!out) return;
  if (out.querySelector("#rs-figures")) {
    out.innerHTML = "";
    return;
  }
  const c = courseCache[id] || {};
  out.innerHTML = `<div class="inlineform" style="margin-top:12px">
    <b>Resume the run.</b> <span class="sub" style="margin:0;font-size:13px">Keeps every module already written and writes only what is missing.</span>
    ${mediaChoices("rs", c, "for modules without any")}
    <div class="actions">
      <button class="btn" style="background:var(--warm)" onclick="resumeCourse('${esc(id)}','rs')">Resume</button>
      <button class="btn sm ghost" onclick="toggleResume('${esc(id)}')">Cancel</button>
    </div></div>`;
}

async function resumeCourse(id, prefix) {
  try {
    const { job: j } = await api(
      `/api/courses/${encodeURIComponent(id)}/resume`,
      mediaBrief(prefix || "rs")
    );
    location.hash = "#/job/" + j.id;
  } catch (err) {
    toast(err.message);
  }
}

async function checkCourse(id) {
  const out = $("#courseout");
  const stop = busy(out, "Checking every module, quiz and suggestion file…", "#courseops");
  try {
    const { problems } = await api(`/api/courses/${encodeURIComponent(id)}/check`, {});
    stop();
    out.innerHTML = problems.length
      ? `<div class="problems"><b>${problems.length} problem${problems.length === 1 ? "" : "s"}</b><ul>${problems.map(p => `<li>${esc(p)}</li>`).join("")}</ul></div>`
      : `<p class="sub ok-text" style="margin:12px 0 0">Consistent — ready to build. Checked in ${stop.took()}.</p>`;
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
      out.innerHTML = `<div class="problems"><b>Not built — fix these first</b><ul>${data.problems.map(p => `<li>${esc(p)}</li>`).join("")}</ul></div>`;
      return;
    }
    const r = data.result;
    toast("Built " + id);
    await refresh();
    await viewCourse();
    const o = $("#courseout");
    if (o)
      o.innerHTML = `<p class="sub ok-text" style="margin:12px 0 0">Built in ${stop.took()}: ${r.modules} modules · ${r.sections} sections · ${r.quiz} quiz items · ${r.cards} cards · ${r.kb} KB</p>`;
  } catch (err) {
    stop();
    out.innerHTML = `<div class="problems">${esc(err.message)}</div>`;
  }
}
