/* ---------- the prompts a module is written from ----------
   Every per-module call - the text, the figures, the notebooks, the quiz, the suggested
   questions, the review - is shown here exactly as it will be sent, and any of them can be
   replaced with the owner's own. An override is stored in the course (plan/prompts.json), so
   a rewrite next year is written to the same instructions as the first run.

   One editor, two surfaces: the approval gate, where the course does not exist yet and the
   overrides travel in the plan, and the course page, where they are saved as they are made. */

const promptEditor = {
  mid: "", // the module whose prompts are open, "" for none
  where: "", // "plan" at the approval gate, a course id on the course page
  stages: [], // what the server sent: {stage, label, note, prompt, default, overridden}
  tokens: [], // {token, what} - the values filled in at the moment of the call
  open: "", // the stage whose text is expanded for editing
  error: "", // why the last load or save failed
};

function promptsOpenFor(mid) {
  return promptEditor.mid === mid;
}

/* What the reader can actually see. The course page draws its rows from the server and
   leaves this box empty, so the state alone would say "open" about a box that was wiped by
   the last render — and the click meant to open it would close it instead. */
function promptsShowing(mid) {
  const box = $(`#pr-${mid}`);
  return (
    promptsOpenFor(mid) && !!box && !box.classList.contains("hidden") && !!box.innerHTML.trim()
  );
}

/* ---------- opening ---------- */

async function openPlanPrompts(mid) {
  const plan = harvestPlan();
  job.plan = plan;
  if (promptsOpenFor(mid)) return closeModulePrompts();
  await loadPrompts(mid, "plan", () => api("/api/plan/prompt", { plan, mid }));
  paintJob(true);
}

async function openCoursePrompts(courseId, mid) {
  const box = $(`#pr-${mid}`);
  if (promptsShowing(mid)) {
    closeModulePrompts();
    if (box) box.classList.add("hidden");
    return;
  }
  if (box) {
    box.classList.remove("hidden");
    box.innerHTML = `<p class="sub busy result"><span class="spin"></span><span>Assembling the prompts for ${esc(mid)}</span></p>`;
  }
  await loadPrompts(mid, courseId, () =>
    api(`/api/courses/${encodeURIComponent(courseId)}/modules/${encodeURIComponent(mid)}/prompts`)
  );
  repaintPrompts();
}

async function loadPrompts(mid, where, fetcher) {
  promptEditor.mid = mid;
  promptEditor.where = where;
  promptEditor.open = "";
  promptEditor.error = "";
  promptEditor.stages = [];
  promptEditor.tokens = [];
  try {
    const data = await fetcher();
    promptEditor.stages = data.stages || [];
    promptEditor.tokens = data.tokens || [];
  } catch (err) {
    promptEditor.error = err.message;
  }
}

function closeModulePrompts() {
  promptEditor.mid = "";
  promptEditor.open = "";
  promptEditor.stages = [];
}

function repaintPrompts() {
  const box = $(`#pr-${promptEditor.mid}`);
  if (box) box.innerHTML = promptEditorHTML();
}

/* ---------- drawing ---------- */

function promptEditorHTML() {
  if (promptEditor.error)
    return `<div class="problems"><b>The prompts could not be read.</b> ${esc(promptEditor.error)}</div>`;
  if (!promptEditor.stages.length)
    return `<p class="sub">Nothing to show for ${esc(promptEditor.mid)}.</p>`;
  const rows = promptEditor.stages.map(promptStageHTML).join("");
  const tokens = promptEditor.tokens
    .map(t => `<li><span class="mono">${esc(t.token)}</span> — ${esc(t.what)}</li>`)
    .join("");
  const saved =
    promptEditor.where === "plan"
      ? "Saved into the course when the run starts."
      : "Saved in the course, at <span class='mono'>plan/prompts.json</span>.";
  return `<div class="prompts">
    <p class="sub">Every call this module costs, in the order a run makes them. Edit one and it
      is sent instead of the platform's. ${saved}</p>
    ${rows}
    <div class="note">The prompt is sent word for word, except these, which are only known when
      the call is made:<ul class="tokens">${tokens}</ul></div>
  </div>`;
}

function promptStageHTML(row) {
  const open = promptEditor.open === row.stage;
  const id = `${promptEditor.mid}-${row.stage}`;
  const tag = row.overridden
    ? `<span class="tag acc" data-help="This course sends its own prompt for this call">yours</span>`
    : `<span class="tag" data-help="The platform's own prompt">platform</span>`;
  const body = open
    ? `<div class="field">
        <label class="visually-hidden" for="pt-${id}">The prompt sent for ${esc(row.label)}</label>
        <textarea id="pt-${id}" class="prompttext" rows="18" spellcheck="false">${esc(row.prompt)}</textarea>
      </div>
      <div class="actions" id="pa-${id}">
        <button class="btn sm primary" onclick="savePromptStage('${esc(row.stage)}')">Send this instead</button>
        <button class="btn sm" onclick="resetPromptStage('${esc(row.stage)}')" ${row.overridden ? "" : "disabled"} data-help="Take the override away and send the platform's prompt again">Back to the platform's</button>
        <button class="btn sm ghost" onclick="togglePromptStage('${esc(row.stage)}')">Close</button>
        <span class="sub">${row.prompt.length.toLocaleString()} characters</span>
      </div>`
    : "";
  return `<div class="pstage ${row.overridden ? "own" : ""}">
    <div class="rowline">
      <b class="grow">${esc(row.label)} ${tag}</b>
      <button class="btn sm" aria-expanded="${open}" onclick="togglePromptStage('${esc(row.stage)}')">${open ? "Hide" : "Read and edit"}</button>
    </div>
    <p class="sub">${esc(row.note)}</p>
    ${body}
  </div>`;
}

function togglePromptStage(stage) {
  promptEditor.open = promptEditor.open === stage ? "" : stage;
  redrawPrompts();
}

/* The gate redraws the whole job screen; the course page redraws only this box. */
function redrawPrompts() {
  if (promptEditor.where === "plan") paintJob(true);
  else repaintPrompts();
}

/* ---------- saving ---------- */

function promptStage(stage) {
  return promptEditor.stages.find(row => row.stage === stage);
}

function savePromptStage(stage) {
  const box = $(`#pt-${promptEditor.mid}-${stage}`);
  if (!box) return;
  const text = box.value;
  const row = promptStage(stage);
  if (row && text.trim() === row.default.trim()) {
    toast("That is the platform's prompt — nothing to override", { kind: "warn" });
    return;
  }
  storePrompt(stage, text);
}

function resetPromptStage(stage) {
  storePrompt(stage, "");
}

async function storePrompt(stage, text) {
  const row = promptStage(stage);
  const mid = promptEditor.mid;
  if (!row) return;
  if (promptEditor.where === "plan") {
    const plan = harvestPlan();
    const all = plan.prompts || {};
    const mine = Object.assign({}, all[mid]);
    if (text.trim()) mine[stage] = text;
    else delete mine[stage];
    if (Object.keys(mine).length) all[mid] = mine;
    else delete all[mid];
    plan.prompts = all;
    job.plan = plan;
    applyPromptRow(row, text);
    paintJob(true);
    toast(promptSaidWhat(mid, row, text, "will be used when the run starts"));
    return;
  }
  const stop = busy($(`#pa-${mid}-${stage}`), "Saving", `#pr-${mid}`);
  try {
    await api(
      `/api/courses/${encodeURIComponent(promptEditor.where)}/modules/${encodeURIComponent(mid)}/prompts`,
      { stage, text },
      "PUT"
    );
    applyPromptRow(row, text);
    stop();
    repaintPrompts();
    toast(promptSaidWhat(mid, row, text, "is saved"));
  } catch (err) {
    stop();
    repaintPrompts();
    toast(err.message, { kind: "bad" });
  }
}

/* A stage's label is a noun phrase of its own ("The module text"), so it is quoted rather
   than glued into a sentence - "your the module text prompt" is what gluing gets you. */
function promptSaidWhat(mid, row, text, done) {
  return text.trim()
    ? `${mid} · ${row.label}: your prompt ${done}`
    : `${mid} · ${row.label}: back to the platform's prompt`;
}

function applyPromptRow(row, text) {
  row.overridden = !!text.trim();
  row.prompt = row.overridden ? text : row.default;
}
