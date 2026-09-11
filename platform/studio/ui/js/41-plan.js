/* ---------- the approval gate ----------
   The one screen where a person decides what gets written. A curriculum is only worth
   approving if you can see what each line of it turns into, so every module opens onto the
   brief it will be written from — its sidebar label, its intent, its section headings — and
   onto the prompt itself, assembled by the writer on the server rather than guessed here. */

const planEdit = {
  open: "", // the module whose brief is expanded, "" for none
};

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
        .map(m => planModuleHTML(m))
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
  const hours = Number(plan.hours || (job.meta || {}).hours || 0);
  return `<div class="card">
    <h3 class="eyebrow"><span class="pulse"></span>Waiting for your approval</h3>
    <h3 class="planttl">${esc(plan.title || "")}</h3>
    <p class="sub">${esc(plan.tagline || "")}</p>
    <div class="rowline gap-top">
      <label class="planhours">The course is <input class="phrs" type="number" value="${hours}" min="1" step="1" aria-label="Course hours"> hours long</label>
      <span class="sub">every module is written as part of a course that size</span>
    </div>
    <div class="note gap-top">Nothing is written until you press the button below. Edit titles, minutes, hours and part names in place, open a module to change the brief it is written from, skip modules you do not want, or add one. Writing ${total} modules takes a while, so it is worth a minute here. Reloading this page does not lose the run — it reattaches to it.</div>
    <p class="budget ${budget.over ? "over" : ""}" id="planbudget">${budgetLine(budget)}</p>
    <div class="gap-top">${parts}</div>
    <div class="actions gap-top">
      <button class="btn primary" onclick="approvePlan()">Write all ${total} modules</button>
      <button class="btn danger" onclick="askStop()">Stop</button>
    </div>
  </div>`;
}

function planModuleHTML(mod) {
  const open = planEdit.open === mod.id && !mod.dropped;
  const off = mod.dropped ? "disabled" : "";
  const row = `<div class="mod ${mod.dropped ? "dropped" : ""}" data-id="${esc(mod.id)}">
        <span class="mid">${esc(mod.id)}</span>
        <input class="mtitle" type="text" value="${esc(mod.title)}" aria-label="Module title" ${off}>
        <input class="mmin" type="number" value="${mod.minutes}" min="15" step="15" aria-label="Minutes" ${off}>
        <button class="btn sm ${open ? "warm" : ""}" aria-expanded="${open}" data-help="The brief this module is written from, and the prompts it becomes" onclick="toggleModuleBrief('${esc(mod.id)}')" ${off}>Brief</button>
        <button class="btn sm ${mod.dropped ? "" : "rm"}" data-help="${mod.dropped ? "Put it back in the course" : "Leave this module out"}" aria-label="${mod.dropped ? "Restore" : "Skip"} ${esc(mod.id)}" onclick="toggleModuleSkip('${esc(mod.id)}')">${mod.dropped ? "Put back" : ico("close", 13)}</button>
      </div>`;
  return open ? row + planBriefHTML(mod) : row;
}

/* What the writer is actually told about this module. The three fields are the whole brief:
   the title above is the fourth. */
function planBriefHTML(mod) {
  const sections = (mod.sections || []).join("\n");
  const open = promptsOpenFor(mod.id);
  const own = Object.keys(((job.plan || {}).prompts || {})[mod.id] || {}).length;
  const mine = own ? ` <span class="tag acc">${own} yours</span>` : "";
  return `<div class="brief" data-brief="${esc(mod.id)}">
      <div class="field">
        <label for="bshort-${esc(mod.id)}">Sidebar label</label>
        <input id="bshort-${esc(mod.id)}" class="bshort" type="text" value="${esc(mod.short || "")}" placeholder="3-5 words">
      </div>
      <div class="field">
        <label for="bintent-${esc(mod.id)}">What it teaches, and why it sits here</label>
        <textarea id="bintent-${esc(mod.id)}" class="bintent" rows="3" placeholder="Two sentences. This reaches the writer as the module's intent.">${esc(mod.summary || "")}</textarea>
      </div>
      <div class="field">
        <label for="bsec-${esc(mod.id)}">Sections, one per line — written verbatim as the <span class="mono">##</span> headings</label>
        <textarea id="bsec-${esc(mod.id)}" class="bsec" rows="7">${esc(sections)}</textarea>
      </div>
      <div class="actions">
        <button class="btn sm" aria-expanded="${open}" onclick="openPlanPrompts('${esc(mod.id)}')">${open ? "Hide the prompts" : "The prompts it is written from"}${mine}</button>
      </div>
      <div id="pr-${esc(mod.id)}">${open ? promptEditorHTML() : ""}</div>
    </div>`;
}

function budgetLine(b) {
  const asked = b.asked ? ` against the ${fmtH(b.asked)} you asked for` : "";
  return `<b>${b.kept.length} modules · ${fmtH(b.minutes)}</b> of teaching${asked}.${b.over ? " That is well over budget — skip a few, or shorten them." : ""}`;
}

function toggleModuleBrief(id) {
  const plan = harvestPlan();
  planEdit.open = planEdit.open === id ? "" : id;
  closeModulePrompts();
  job.plan = plan;
  paintJob(true);
}

/* Skipping is a toggle, not a deletion: a module left out by mistake can be put back
   without starting the whole design again. */
function toggleModuleSkip(id) {
  const plan = harvestPlan();
  plan.modules.forEach(m => {
    if (m.id === id) m.dropped = !m.dropped;
  });
  if (planEdit.open === id) {
    planEdit.open = "";
    closeModulePrompts();
  }
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
  const hours = $(".phrs");
  if (hours) plan.hours = Number(hours.value) || plan.hours;
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
  document.querySelectorAll(".brief[data-brief]").forEach(el => {
    const mod = plan.modules.find(m => m.id === el.dataset.brief);
    if (!mod) return;
    mod.short = el.querySelector(".bshort").value.trim() || mod.title;
    mod.summary = el.querySelector(".bintent").value.trim();
    const lines = el
      .querySelector(".bsec")
      .value.split("\n")
      .map(s => s.replace(/^#+\s*/, "").trim())
      .filter(Boolean);
    if (lines.length) mod.sections = lines;
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
