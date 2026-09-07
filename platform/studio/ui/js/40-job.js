/* ---------- a running job ---------- */

function viewJob() {
  const jobId = route.id;
  if (job && job.id === jobId) {
    paintJob(true);
    return;
  }
  job = {
    id: jobId,
    events: [],
    plan: null,
    awaiting: null,
    meta: {},
    progress: { done: 0, total: 0, label: "" },
    status: "running",
    result: null,
    startedAt: 0,
    stepAt: 0,
    stepTimes: [],
    call: null,
  };
  const known = (STATE.jobs || []).find(j => j.id === jobId);
  if (known) {
    job.meta = known.meta || {};
    job.kind = known.kind;
  }
  paintJob(true);
  connect(jobId, 0);
  clearInterval(jobTimer);
  jobTimer = setInterval(tickJob, 1000);
}

let jobTimer = null;

function connect(jobId, from) {
  if (stream) stream.close();
  stream = new EventSource(`/api/jobs/${encodeURIComponent(jobId)}/events?from=${from}`);
  stream.onmessage = ev => {
    let event;
    try {
      event = JSON.parse(ev.data);
    } catch (e) {
      return;
    }
    absorb(event);
    paintJob();
  };
  stream.onerror = () => {
    stream.close();
    // The server closes the stream when the job ends; only reconnect if it has not.
    if (route.name === "job" && route.id === jobId && !FINISHED.includes(job.status)) {
      setTimeout(
        () => connect(jobId, job.events.length ? job.events[job.events.length - 1].i + 1 : 0),
        1200
      );
    }
  };
}

function absorb(event) {
  job.events.push(event);
  if (event.kind === "started") {
    job.kind = event.job;
    job.startedAt = event.at;
  }
  if (event.kind === "progress") {
    // Each step's duration feeds the estimate of what is left; the timestamps come with
    // the events, so a replay after a reload measures the same thing.
    if (job.stepAt && job.progress.total) job.stepTimes.push(event.at - job.stepAt);
    job.stepAt = event.at;
    job.progress = { done: event.done, total: event.total, label: event.label };
  }
  if (event.kind === "call") job.call = event.phase === "start" ? event : null;
  if (event.kind === "plan") job.plan = event.plan;
  if (event.kind === "await") {
    job.awaiting = event;
    job.status = "waiting";
  }
  if (event.kind === "resumed") {
    job.awaiting = null;
    job.status = "running";
  }
  if (event.kind === "done") job.result = event.result;
  if (event.kind === "end") {
    job.status = event.status;
    refresh().then(() => {
      const known = (STATE.jobs || []).find(j => j.id === job.id);
      if (known) job.meta = known.meta || {};
      if (route.name === "job") paintJob();
    });
  }
}

function stepLine(e) {
  if (e.kind === "log") return { text: e.message };
  if (e.kind === "progress")
    return { text: `Step ${e.done} of ${e.total} — ${e.label}`, cls: "head" };
  if (e.kind === "call" && e.phase === "start")
    return {
      text: `Asking Claude for ${e.what || "a reply"} — ${e.model}, ${(e.chars || 0).toLocaleString()} chars sent`,
      cls: "dim",
    };
  if (e.kind === "call")
    return e.ok
      ? {
          text: `Claude answered in ${fmtDur(e.seconds)} — ${(e.reply || 0).toLocaleString()} chars`,
          cls: "ok",
        }
      : {
          text: `Claude did not answer after ${fmtDur(e.seconds)} — ${e.error || "no output"}`,
          cls: "bad",
        };
  if (e.kind === "spec")
    return { text: `${e.id} designed — "${e.title}", ${e.minutes} minutes`, cls: "ok" };
  if (e.kind === "module")
    return {
      text: e.patched
        ? `${e.id} patched — ${e.changedLines} line${e.changedLines === 1 ? "" : "s"} changed, ${e.sections} sections, ${e.words} words`
        : `${e.id} written — ${e.sections} sections, ${e.words} words`,
      cls: "ok",
    };
  if (e.kind === "studydata")
    return {
      text: `${e.id} study data${e.patched ? " patched" : ""} — ${e.quiz} quiz, ${e.cards} cards, ${e.sections} question sets`,
      cls: "ok",
    };
  if (e.kind === "worksheet") return { text: `Worksheet: ${e.name}`, cls: "ok" };
  if (e.kind === "figures")
    return {
      text: e.count
        ? `${e.id} figures — ${e.count} drawn${e.steps ? `, ${e.steps} in steps` : ""} (${(e.sections || []).join(", ")})`
        : `${e.id} figures — nothing worth drawing, or nothing usable came back`,
      cls: e.count ? "ok" : "",
    };
  if (e.kind === "review")
    return {
      text: `${e.id} reviewed — ${e.verdict}; ${e.gaps} gap${e.gaps === 1 ? "" : "s"}, ${e.errors} error${e.errors === 1 ? "" : "s"}, ${e.quiz} quiz issue${e.quiz === 1 ? "" : "s"}`,
      cls: e.verdict === "solid" ? "ok" : "",
    };
  if (e.kind === "plan") return { text: `Curriculum proposed — ${e.plan.modules.length} modules` };
  if (e.kind === "await") return { text: "Waiting for you to approve the curriculum" };
  if (e.kind === "built")
    return { text: `Built — ${e.modules} modules, ${e.sections} sections, ${e.kb} KB`, cls: "ok" };
  if (e.kind === "failed") return { text: e.error, cls: "bad" };
  if (e.kind === "cancelled") return { text: "Stopped.", cls: "bad" };
  return null; // progress is shown by the bar, not the log
}

function jobTitle() {
  const m = job.meta || {};
  if (job.kind === "extend") return `Adding a module to ${m.course || ""}`;
  if (job.kind === "rewrite")
    return `${m.mode === "patch" ? "Patching" : "Rewriting"} ${m.module || ""} in ${m.course || ""}`;
  if (job.kind === "review") return `Reviewing ${m.module || ""} in ${m.course || ""}`;
  if (job.kind === "figures")
    return m.module
      ? `Drawing figures for ${m.module} in ${m.course || ""}`
      : `Drawing figures in ${m.course || ""}`;
  return m.theme ? `Writing ${m.theme}` : "Working";
}

function paintJob(full) {
  if (route.name !== "job" || !job) return;
  if (full || !$("#jobwrap")) {
    $("#view").innerHTML =
      `<p class="crumb"><a href="#/">Courses</a> › ${esc(jobTitle())}</p><div id="jobwrap"></div>`;
  }
  const p = job.progress;
  const pct = p.total ? Math.round((p.done / p.total) * 100) : 0;
  const finished = FINISHED.includes(job.status);
  const courseId = (job.meta || {}).course || (job.result || {}).course || "";
  const back = courseId
    ? `<a class="btn ghost" href="#/course/${encodeURIComponent(courseId)}">Back to the course</a>`
    : `<a class="btn ghost" href="#/">Back to courses</a>`;

  // Keep each line paired with its own event: stepLine() drops some events, so the
  // filtered index no longer lines up with job.events.
  const lines = job.events
    .map(e => {
      const l = stepLine(e);
      return l && Object.assign({ at: e.at }, l);
    })
    .filter(Boolean)
    .slice(-200);
  const log = lines
    .map(
      l =>
        `<div class="step ${l.cls || ""}"><span class="when">${esc(clock(l.at))}</span><span class="what">${esc(l.text)}</span></div>`
    )
    .join("");

  let head;
  if (job.status === "waiting" && job.awaiting) head = reviewPlanHTML();
  else if (job.status === "done") head = doneHTML(back);
  else if (finished)
    head = `<div class="card"><h3>${job.status === "cancelled" ? "Stopped" : "It did not finish"}</h3>
      <p class="sub" style="margin:6px 0 0">${esc(
        lines
          .filter(l => l.cls === "bad")
          .map(l => l.text)
          .join(" ") || ""
      )}</p>
      <p class="sub" style="margin:10px 0 0">Anything written before this point is still on disk under <span class="mono">courses/</span>.${job.kind === "generate" && courseId ? " The curriculum is saved, so the run can be resumed: it keeps what is written and does only the rest." : ""} The <a href="#/settings">log</a> has the CLI's own error.</p>
      <div class="actions">${job.kind === "generate" && courseId ? `<button class="btn" style="background:var(--warm)" onclick="resumeCourse('${esc(courseId)}')">Resume the run</button>` : ""}${back}</div></div>`;
  else
    head = `<div class="card">
      <p class="eyebrow">${esc(job.status)} · ${esc(jobTitle())}</p>
      <h3>${esc(p.label || (job.kind === "generate" ? "Designing the curriculum" : "Working…"))}</h3>
      <div class="bar-track"><div class="bar-fill" style="width:${pct}%"></div></div>
      <div class="jobfacts" id="jobfacts"></div>
      <p class="now" id="jobnow"></p>
      <div class="actions" style="margin-top:12px"><button class="btn danger sm" onclick="cancelJob()">Stop</button>
        <a class="btn ghost sm" href="#/settings">Full log</a></div>
    </div>`;

  $("#jobwrap").innerHTML =
    head +
    `<div class="card"><p class="eyebrow">Activity</p><div class="steps" id="steps">${log}</div></div>`;
  const box = $("#steps");
  if (box) box.scrollTop = box.scrollHeight;
  tickJob();
}

/* The clocks on the job screen, once a second. Only the small elements are rewritten, so
   the activity log keeps its scroll position and nothing flickers. */
function tickJob() {
  if (!job) return;
  const finished = FINISHED.includes(job.status);
  const p = job.progress || {};
  if (finished || route.name !== "job") {
    document.title = "Course Studio";
    if (finished) clearInterval(jobTimer);
    return;
  }
  const now = Date.now() / 1000;
  document.title =
    (p.total ? `${p.done}/${p.total} · ` : "") + (p.label || jobTitle()) + " — Course Studio";

  const facts = $("#jobfacts");
  if (facts) {
    const bits = [];
    bits.push(
      p.total ? `<span>step <b>${p.done} of ${p.total}</b></span>` : `<span><b>starting</b></span>`
    );
    if (job.stepAt) bits.push(`<span>this step <b>${fmtDur(now - job.stepAt)}</b></span>`);
    if (job.startedAt) bits.push(`<span>running for <b>${fmtDur(now - job.startedAt)}</b></span>`);
    const left = estimateLeft(now);
    if (left) bits.push(`<span>roughly <b>${left}</b> left</span>`);
    facts.innerHTML = bits.join("");
  }

  const nowEl = $("#jobnow");
  if (nowEl) {
    if (job.status === "waiting") {
      nowEl.innerHTML = `<span class="pulse"></span>Waiting for you — nothing runs until the curriculum is approved.`;
    } else if (job.call) {
      const secs = now - job.call.at;
      const cap = job.call.timeout ? ` · up to ${fmtDur(job.call.timeout)} allowed` : "";
      nowEl.innerHTML = `<span class="pulse"></span>Claude is writing ${esc(job.call.what || "a reply")}<span class="mono">${fmtDur(secs)}${cap}</span>`;
    } else {
      nowEl.innerHTML = `<span class="pulse"></span>Studio is working between calls — saving files, checking them, building.`;
    }
  }
}

/* A rough remaining time from the steps finished so far. Steps differ (a module takes
   minutes, its quiz less), so the mean over what has completed is the honest guess; it is
   not shown until two steps have finished. */
function estimateLeft(now) {
  const p = job.progress || {};
  const times = job.stepTimes || [];
  if (!p.total || times.length < 2) return "";
  const avg = times.reduce((a, b) => a + b, 0) / times.length;
  const thisStep = job.stepAt ? now - job.stepAt : 0;
  const remaining = (p.total - p.done) * avg + Math.max(0, avg - thisStep);
  if (remaining < 60) return "a minute";
  const mins = Math.round(remaining / 60);
  return mins < 60
    ? `${mins} min`
    : `${Math.floor(mins / 60)}h ${String(mins % 60).padStart(2, "0")}m`;
}

function doneHTML(back) {
  const r = job.result || {};
  const id = r.course || "";
  const c = (STATE.courses || []).find(x => x.id === id);
  if (job.kind === "review") {
    const n = (r.gaps || []).length + (r.errors || []).length + (r.quiz || []).length;
    return `<div class="card">
      <p class="eyebrow" style="color:${r.verdict === "solid" ? "var(--ok)" : r.verdict === "rewrite" ? "var(--bad)" : "var(--warm)"}">Verdict: ${esc(r.verdict || "")}</p>
      <h3>${esc(r.module || "")} · ${esc(r.title || "")}</h3>
      <p style="margin:6px 0 0;color:var(--text-2)">${esc(r.summary || "")}</p>
      <p class="sub" style="margin:8px 0 0;font-size:13px">${n} finding${n === 1 ? "" : "s"}. The full list is on the course page, under the module.</p>
      <div class="actions" style="margin-top:14px">
        ${r.rewriteBrief && r.verdict !== "solid" ? `<a class="btn" href="#/course/${encodeURIComponent(id)}?tab=modules&rewrite=${encodeURIComponent(r.module || "")}&q=${encodeURIComponent(r.rewriteBrief)}">Patch with these notes</a>` : ""}
        ${r.module ? `<button class="btn ghost" onclick="acceptModule('${esc(id)}','${esc(r.module)}',true).then(()=>{location.hash='#/course/${encodeURIComponent(id)}'})" title="Your verdict outranks the review until the module changes">This is good</button>` : ""}
        ${back}</div>
      ${r.verdict !== "solid" ? `<p class="sub" style="margin:12px 0 0;font-size:13px">A patch changes only what the findings name and keeps every other sentence. If you have read the module and disagree with the findings, mark it good instead: your verdict is what the course page shows.</p>` : ""}</div>`;
  }
  const target = r.module ? "#/m/" + r.module : "#/home";
  const open =
    c && c.built
      ? `<a class="btn" href="${courseUrl(c, target)}">${r.module ? "Read " + esc(r.module) : "Open the course"}</a>`
      : "";
  const drawn = r.drawn || [];
  const what =
    job.kind === "extend"
      ? `${esc(r.module || "A module")} was added to ${esc(id)}`
      : job.kind === "rewrite"
        ? `${esc(r.module || "The module")} was ${r.mode === "patch" ? "patched" : "rewritten"}`
        : job.kind === "figures"
          ? `Figures drawn for ${drawn.length ? esc(drawn.join(", ")) : "no module"}`
          : `${esc(id)} is built`;
  return `<div class="card">
    <p class="eyebrow" style="color:var(--ok)">Finished</p>
    <h3>${what}</h3>
    <p class="sub" style="margin:4px 0 0">${r.modules} modules · ${r.sections} sections${r.figures ? ` · ${r.figures} figures` : ""} · ${r.quiz} quiz items · ${r.cards} flashcards · ${r.glossary} glossary terms · ${r.kb} KB</p>
    <div class="actions" style="margin-top:14px">${open}${(job.kind === "rewrite" || job.kind === "extend") && r.module && STATE.claude.available ? `<button class="btn ghost" onclick="reviewModule('${esc(id)}','${esc(r.module)}')">Review ${esc(r.module)} now</button>` : ""}${back}</div>
    ${job.kind === "rewrite" ? `<p class="sub" style="margin:10px 0 0;font-size:13px">An earlier review of ${esc(r.module || "this module")} judged the old text, so the course page now shows it as "before edit". A new review reads what was just written.</p>` : ""}
    <p class="sub" style="margin:14px 0 0;font-size:13px">Opened from here, the course keeps its progress on the platform and asks its questions through Studio — no key, no bridge, no disk copy needed.</p>
  </div>`;
}

/* ---------- the approval gate ---------- */

function reviewPlanHTML() {
  const plan = job.plan || {};
  const parts = (plan.parts || [])
    .map(part => {
      const mods = (plan.modules || [])
        .filter(m => m.part === part.id)
        .map(
          m => `
      <div class="mod" data-id="${esc(m.id)}">
        <span class="mid">${esc(m.id)}</span>
        <input class="mtitle" type="text" value="${esc(m.title)}" aria-label="Module title">
        <input class="mmin" type="number" value="${m.minutes}" min="15" step="15" aria-label="Minutes">
        <button class="drop" title="Remove this module" onclick="dropModule('${esc(m.id)}')">×</button>
      </div>`
        )
        .join("");
      return `<div class="part" data-part="${esc(part.id)}">
      <div class="parthead">
        <input class="pname" type="text" value="${esc(part.name)}" aria-label="Part name">
        <input class="phours" type="number" value="${part.hours}" min="0" step="1" aria-label="Hours">
        <span class="tag">hours</span>
      </div>${mods}</div>`;
    })
    .join("");

  const total = (plan.modules || []).length;
  return `<div class="card">
    <p class="eyebrow">Review before it writes anything</p>
    <h3 style="font-size:24px">${esc(plan.title || "")}</h3>
    <p class="sub" style="margin:2px 0 16px">${esc(plan.tagline || "")}</p>
    <div class="note">Edit titles, minutes and part names in place, or drop modules you do not want. Writing ${total} modules takes a while, so it is worth a minute here.</div>
    <div style="margin-top:16px">${parts}</div>
    <div class="actions" style="margin-top:16px">
      <button class="btn" onclick="approvePlan()">Write all ${total} modules</button>
      <button class="btn danger" onclick="cancelJob()">Stop</button>
    </div>
  </div>`;
}

function dropModule(id) {
  job.plan.modules = job.plan.modules.filter(m => m.id !== id);
  paintJob(true);
}

function harvestPlan() {
  const plan = JSON.parse(JSON.stringify(job.plan));
  document.querySelectorAll(".part").forEach(el => {
    const part = plan.parts.find(p => p.id === el.dataset.part);
    if (!part) return;
    part.name = el.querySelector(".pname").value.trim() || part.name;
    part.hours = Number(el.querySelector(".phours").value) || part.hours;
  });
  document.querySelectorAll(".mod").forEach(el => {
    const mod = plan.modules.find(m => m.id === el.dataset.id);
    if (!mod) return;
    mod.title = el.querySelector(".mtitle").value.trim() || mod.title;
    mod.minutes = Number(el.querySelector(".mmin").value) || mod.minutes;
  });
  return plan;
}

async function approvePlan() {
  const plan = harvestPlan();
  if (!plan.modules.length) {
    toast("There are no modules left to write");
    return;
  }
  try {
    await api(`/api/jobs/${encodeURIComponent(job.id)}/answer`, { plan });
    job.awaiting = null;
    job.status = "running";
    paintJob(true);
  } catch (err) {
    toast(err.message);
  }
}

async function cancelJob() {
  try {
    await api(`/api/jobs/${encodeURIComponent(job.id)}/cancel`, {});
    toast("Stopping…");
  } catch (err) {
    toast(err.message);
  }
}
