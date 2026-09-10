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
    told: false, // has the browser been notified that this run wants approval?
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

/* ---------- every recent run ----------
   Without this a finished run is reachable only through the back button, and a failed one
   is invisible the moment the header pill clears. */
function viewJobs() {
  const jobs = (STATE.jobs || []).slice(0, 12);
  const rows = jobs
    .map(j => {
      const m = j.meta || {};
      const who = m.course || m.theme || "";
      const cls = j.status === "done" ? "ok" : FINISHED.includes(j.status) ? "bad" : "acc";
      const took = j.finished && j.started ? fmtDur(j.finished - j.started) : "";
      return `<div class="jobrow">
        <span class="tag ${cls}">${esc(j.status)}</span>
        <span class="what"><a href="#/job/${esc(j.id)}">${esc(kindLabel(j.kind))}${who ? " · " + esc(who) : ""}</a></span>
        <span class="sub">${esc(took)}</span>
        <span class="sub">${esc(ago(j.finished || j.started))}</span>
      </div>`;
    })
    .join("");
  $("#view").innerHTML = `<p class="crumb"><a href="#/">Courses</a> › Recent runs</p>
    <h2 class="big">Recent runs</h2>
    <p class="lede">Every job Studio has run in this session and the ones it kept from before. Open one to read its activity log.</p>
    ${liveJobBanner()}
    <div class="card">${rows || `<p class="sub">Nothing has run yet.</p>`}</div>`;
}

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
    announceWaiting();
    refresh(); // the header pill has to say "waiting", not "designing the curriculum"
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

/* A run that stops for approval can sit unnoticed for an hour in a background tab. Say so
   in the tab title, and — only if the browser has already been given permission — outside it. */
function announceWaiting() {
  if (job.told) return;
  job.told = true;
  document.title = "Waiting for your approval — Course Studio";
  try {
    if (window.Notification && Notification.permission === "granted")
      new Notification("Course Studio", { body: "The curriculum is ready for your approval." });
  } catch (e) {
    /* notifications unavailable */
  }
}

function stepLine(e) {
  if (e.kind === "log") return { text: e.message };
  if (e.kind === "progress")
    return { text: `Step ${e.done} of ${e.total} — ${e.label}`, cls: "head" };
  if (e.kind === "call" && e.phase === "start")
    return {
      text: `Asking for ${e.what || "a reply"} — ${e.model}, ${(e.chars || 0).toLocaleString()} chars sent`,
      cls: "dim",
    };
  if (e.kind === "call")
    return e.ok
      ? {
          text: `Answered in ${fmtDur(e.seconds)} — ${(e.reply || 0).toLocaleString()} chars`,
          cls: "ok",
        }
      : {
          text: `No answer after ${fmtDur(e.seconds)} — ${e.error || "no output"}`,
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
  if (e.kind === "notebooks")
    return {
      text: e.count
        ? `${e.id} notebooks — ${e.count} written, ${e.cells} cells (${(e.sections || []).join(", ")})`
        : `${e.id} notebooks — nothing worth running, or nothing usable came back`,
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
  if (job.kind === "notebooks")
    return m.module
      ? `Writing notebooks for ${m.module} in ${m.course || ""}`
      : `Writing notebooks in ${m.course || ""}`;
  return m.theme ? `Writing ${m.theme}` : "Working";
}

function jobCrumb() {
  const id = (job.meta || {}).course || (job.result || {}).course || "";
  const middle = id
    ? `<a href="#/course/${encodeURIComponent(id)}">${esc(id)}</a> › `
    : `<a href="#/jobs">Recent runs</a> › `;
  return `<p class="crumb"><a href="#/">Courses</a> › ${middle}${esc(jobTitle())}</p>`;
}

function paintJob(full) {
  if (route.name !== "job" || !job) return;
  if (full || !$("#jobwrap")) {
    $("#view").innerHTML = jobCrumb() + `<div id="jobwrap"></div>`;
  }
  const p = job.progress;
  const pct = p.total ? Math.round((p.done / p.total) * 100) : 0;
  const finished = FINISHED.includes(job.status);
  const courseId = (job.meta || {}).course || (job.result || {}).course || "";
  const back = courseId
    ? `<a class="btn" href="#/course/${encodeURIComponent(courseId)}">Back to the course</a>`
    : `<a class="btn" href="#/">Back to courses</a>`;

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
  else if (finished) head = failedHTML(back, courseId, lines);
  else
    head = `<div class="card">
      <h3 class="eyebrow">${esc(job.status)} · ${esc(jobTitle())}</h3>
      <h3>${esc(p.label || (job.kind === "generate" ? "Designing the curriculum" : "Working…"))}</h3>
      <div class="bar-track"><div class="bar-fill" style="width:${pct}%"></div></div>
      <div class="jobfacts" id="jobfacts"></div>
      <p class="now" id="jobnow"></p>
      <div class="actions gap-top" id="stopbar">
        <button class="btn danger sm" id="stopbtn" onclick="askStop()">Stop</button>
        <a class="btn sm" href="#/settings">Full log</a>
      </div>
    </div>`;

  // Keep the log where the reader put it: only follow when they had not scrolled up.
  const old = $("#steps");
  const wasAtBottom = !old || old.scrollHeight - old.scrollTop - old.clientHeight < 40;
  $("#jobwrap").innerHTML =
    head +
    `<div class="card"><h3 class="eyebrow">Activity</h3><div class="steps" id="steps" role="log" aria-live="polite" aria-label="What this run is doing">${log}</div></div>`;
  const box = $("#steps");
  if (box && wasAtBottom) box.scrollTop = box.scrollHeight;
  tickJob();
}

function failedHTML(back, courseId, lines) {
  const why =
    lines
      .filter(l => l.cls === "bad")
      .map(l => l.text)
      .join(" ") || "";
  const canResume = job.kind === "generate" && courseId;
  // When the model was the problem rather than the course, the sentence above already says so
  // and says it better than the log does - pointing at the log there sends the reader off
  // to read the same thing in CLI spelling.
  const account = job.why === "quota" || job.why === "auth";
  const logHint = account ? "" : ' The <a href="#/settings">log</a> has the CLI\'s own error.';
  const later = account && canResume ? " Resume it once it answers again." : "";
  return `<div class="card">
    <h3>${job.status === "cancelled" ? "Stopped" : "It did not finish"}</h3>
    <p class="sub">${esc(why)}</p>
    <p class="sub result">Anything written before this point is still on disk under <span class="mono">courses/</span>.${canResume ? " The curriculum is saved, so the run can be resumed: it keeps what is written and does only the rest." : ""}${later}${logHint}</p>
    ${
      canResume
        ? mediaChoices(
            "rsj",
            (STATE.courses || []).find(c => c.id === courseId),
            "for modules without any"
          ) + modelChoice("rsj", "the modules still missing")
        : ""
    }
    <div class="actions gap-top">${canResume ? `<button class="btn warm" onclick="resumeCourse('${esc(courseId)}','rsj')">Resume the run</button>` : ""}${back}</div></div>`;
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
    job.status === "waiting"
      ? "Waiting for your approval — Course Studio"
      : (p.total ? `${p.done}/${p.total} · ` : "") + (p.label || jobTitle()) + " — Course Studio";

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
    if (job.call) {
      const secs = now - job.call.at;
      const cap = job.call.timeout ? ` · up to ${fmtDur(job.call.timeout)} allowed` : "";
      nowEl.innerHTML = `<span class="pulse"></span>Writing ${esc(job.call.what || "a reply")}<span class="mono">${fmtDur(secs)}${cap}</span>`;
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
    const cls = r.verdict === "solid" ? "ok" : r.verdict === "rewrite" ? "bad" : "warn";
    const findings = id
      ? `#/course/${encodeURIComponent(id)}?tab=modules&review=${encodeURIComponent(r.module || "")}`
      : "#/";
    return `<div class="card">
      <h3 class="eyebrow">Verdict <span class="tag ${cls}" title="${esc(help(r.verdict || ""))}">${esc(r.verdict || "")}</span></h3>
      <h3>${esc(r.module || "")} · ${esc(r.title || "")}</h3>
      <p class="summary">${esc(r.summary || "")}</p>
      <p class="sub result">${n} finding${n === 1 ? "" : "s"}.</p>
      <div class="actions gap-top">
        <a class="btn primary" href="${findings}">Read the findings</a>
        ${r.rewriteBrief && r.verdict !== "solid" ? `<a class="btn" href="#/course/${encodeURIComponent(id)}?tab=modules&rewrite=${encodeURIComponent(r.module || "")}&q=${encodeURIComponent(r.rewriteBrief)}">Patch with these notes</a>` : ""}
        ${r.module ? `<button class="btn" onclick="acceptModule('${esc(id)}','${esc(r.module)}',true).then(()=>{location.hash='#/course/${encodeURIComponent(id)}'})" title="Your verdict outranks the review until the module changes">Mark as good</button>` : ""}
        ${back}</div>
      ${r.verdict !== "solid" ? `<p class="sub result">${esc(help("patch"))} If you have read the module and disagree with the findings, mark it good instead: your verdict is what the course page shows.</p>` : ""}</div>`;
  }
  const target = r.module ? "#/m/" + r.module : "#/home";
  const open =
    c && c.built
      ? `<a class="btn primary" href="${courseUrl(c, target)}">${r.module ? "Read " + esc(r.module) : "Open the course"}</a>`
      : "";
  const drawn = r.drawn || [];
  const written = r.written || [];
  const what =
    job.kind === "extend"
      ? `${esc(r.module || "A module")} was added to ${esc(id)}`
      : job.kind === "rewrite"
        ? `${esc(r.module || "The module")} was ${r.mode === "patch" ? "patched" : "rewritten"}`
        : job.kind === "figures"
          ? `Figures drawn for ${drawn.length ? esc(drawn.join(", ")) : "no module"}`
          : job.kind === "notebooks"
            ? `Notebooks written for ${written.length ? esc(written.join(", ")) : "no module"}`
            : `${esc(id)} is built`;
  return `<div class="card">
    <h3 class="eyebrow ok-text">Finished</h3>
    <h3>${what}</h3>
    <p class="sub">${r.modules} modules · ${r.sections} sections${r.figures ? ` · ${r.figures} figures` : ""}${r.notebooks ? ` · ${r.notebooks} notebooks` : ""} · ${r.quiz} quiz items · ${r.cards} flashcards · ${r.glossary} glossary terms · ${r.kb} KB</p>
    <div class="actions gap-top">${open}${(job.kind === "rewrite" || job.kind === "extend") && r.module && claudeReady() ? `<button class="btn" onclick="reviewModule('${esc(id)}','${esc(r.module)}')">Review ${esc(r.module)} now</button>` : ""}${back}</div>
    ${job.kind === "rewrite" ? `<p class="sub result">An earlier review of ${esc(r.module || "this module")} judged the old text, so the course page now shows it as "before edit". A new review reads what was just written.</p>` : ""}
    <p class="sub result">Opened from here, the course keeps its progress on the platform and asks its questions through Studio — no key, no bridge, no disk copy needed.</p>
  </div>`;
}

/* ---------- the approval gate ---------- */

function planBudget(plan) {
  const kept = (plan.modules || []).filter(m => !m.dropped);
  const minutes = kept.reduce((n, m) => n + (Number(m.minutes) || 0), 0);
  const asked = Number(plan.hours || (job.meta || {}).hours || 0) * 60;
  return { kept, minutes, asked, over: asked && minutes > asked * 1.15 };
}

function reviewPlanHTML() {
  const plan = job.plan || {};
  const budget = planBudget(plan);
  const parts = (plan.parts || [])
    .map(part => {
      const mods = (plan.modules || [])
        .filter(m => m.part === part.id)
        .map(
          m => `
      <div class="mod ${m.dropped ? "dropped" : ""}" data-id="${esc(m.id)}">
        <span class="mid">${esc(m.id)}</span>
        <input class="mtitle" type="text" value="${esc(m.title)}" aria-label="Module title" ${m.dropped ? "disabled" : ""}>
        <input class="mmin" type="number" value="${m.minutes}" min="15" step="15" aria-label="Minutes" ${m.dropped ? "disabled" : ""}>
        <button class="btn sm ${m.dropped ? "" : "rm"}" title="${m.dropped ? "Put it back in the course" : "Leave this module out"}" aria-label="${m.dropped ? "Restore" : "Skip"} ${esc(m.id)}" onclick="toggleModuleSkip('${esc(m.id)}')">${m.dropped ? "Put back" : ico("close", 13)}</button>
      </div>`
        )
        .join("");
      return `<div class="part" data-part="${esc(part.id)}">
      <div class="parthead">
        <input class="pname" type="text" value="${esc(part.name)}" aria-label="Part name">
        <input class="phours" type="number" value="${part.hours}" min="0" step="1" aria-label="Hours">
        <span class="tag">hours</span>
      </div>${mods}
      <div class="mod"><button class="btn sm" onclick="addPlanModule('${esc(part.id)}')">${ico("plus", 13)} Add a module here</button></div></div>`;
    })
    .join("");

  const total = budget.kept.length;
  return `<div class="card">
    <h3 class="eyebrow"><span class="pulse"></span>Waiting for your approval</h3>
    <h3 class="planttl">${esc(plan.title || "")}</h3>
    <p class="sub">${esc(plan.tagline || "")}</p>
    <div class="note gap-top">Nothing is written until you press the button below. Edit titles, minutes and part names in place, skip modules you do not want, or add one. Writing ${total} modules takes a while, so it is worth a minute here. Reloading this page does not lose the run — it reattaches to it.</div>
    <p class="budget ${budget.over ? "over" : ""}" id="planbudget">${budgetLine(budget)}</p>
    <div class="gap-top">${parts}</div>
    <div class="actions gap-top">
      <button class="btn primary" onclick="approvePlan()">Write all ${total} modules</button>
      <button class="btn danger" onclick="askStop()">Stop</button>
    </div>
  </div>`;
}

function budgetLine(b) {
  const asked = b.asked ? ` against the ${fmtH(b.asked)} you asked for` : "";
  return `<b>${b.kept.length} modules · ${fmtH(b.minutes)}</b> of teaching${asked}.${b.over ? " That is well over budget — skip a few, or shorten them." : ""}`;
}

/* Skipping is a toggle, not a deletion: a module left out by mistake can be put back
   without starting the whole design again. */
function toggleModuleSkip(id) {
  const plan = harvestPlan();
  plan.modules.forEach(m => {
    if (m.id === id) m.dropped = !m.dropped;
  });
  job.plan = plan;
  paintJob(true);
}

function addPlanModule(partId) {
  const plan = harvestPlan();
  const nums = plan.modules.map(m => Number(String(m.id).replace(/\D/g, "")) || 0);
  const next = "M" + String(Math.max(0, ...nums) + 1).padStart(2, "0");
  const after = plan.modules.map(m => m.part).lastIndexOf(partId);
  const fresh = { id: next, part: partId, title: "", minutes: 60 };
  plan.modules.splice(after < 0 ? plan.modules.length : after + 1, 0, fresh);
  job.plan = plan;
  paintJob(true);
  const el = document.querySelector(`.mod[data-id="${next}"] .mtitle`);
  if (el) el.focus();
}

function harvestPlan() {
  const plan = JSON.parse(JSON.stringify(job.plan));
  document.querySelectorAll(".part").forEach(el => {
    const part = plan.parts.find(p => p.id === el.dataset.part);
    if (!part) return;
    part.name = el.querySelector(".pname").value.trim() || part.name;
    part.hours = Number(el.querySelector(".phours").value) || part.hours;
  });
  document.querySelectorAll(".mod[data-id]").forEach(el => {
    const mod = plan.modules.find(m => m.id === el.dataset.id);
    if (!mod) return;
    mod.title = el.querySelector(".mtitle").value.trim() || mod.title;
    mod.minutes = Number(el.querySelector(".mmin").value) || mod.minutes;
  });
  return plan;
}

async function approvePlan() {
  const plan = harvestPlan();
  plan.modules = plan.modules.filter(m => !m.dropped && String(m.title || "").trim());
  if (!plan.modules.length) {
    toast("There are no modules left to write", { kind: "bad" });
    return;
  }
  try {
    await api(`/api/jobs/${encodeURIComponent(job.id)}/answer`, { plan });
    job.awaiting = null;
    job.status = "running";
    job.told = false;
    paintJob(true);
  } catch (err) {
    toast(err.message, { kind: "bad" });
  }
}

/* Stopping loses the calls in flight, so it asks — in place, with what happens next. */
function askStop() {
  const bar = $("#stopbar") || document.querySelector(".actions");
  if (!bar) return cancelJob();
  const hint =
    job.kind === "generate"
      ? " Everything already written stays on disk, and the run can be resumed from the course page."
      : " Anything already written stays on disk.";
  bar.innerHTML = `<span class="sub">Stop this run?${hint}</span>
    <button class="btn sm danger" onclick="cancelJob()">Stop it</button>
    <button class="btn sm" onclick="paintJob(true)">Keep going</button>`;
}

async function cancelJob() {
  const btn = $("#stopbtn");
  if (btn) btn.disabled = true;
  try {
    await api(`/api/jobs/${encodeURIComponent(job.id)}/cancel`, {});
    toast("Stopping…");
  } catch (err) {
    toast(err.message, { kind: "bad" });
  }
}
