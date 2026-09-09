/* ---------- the model a writing job runs on ----------
   Every job that writes a course - a new one, a resumed run, an added module, a rewrite -
   is one long chain of Claude calls, and which model answers them is the biggest lever on
   both the quality and the cost of the result. So each of those forms shows the list from
   settings.json (modelChoice), preselected to Studio's default from Settings & logs, and
   sends what was picked as `model` in the request (modelBrief); the server takes a known
   alias and falls back to the default otherwise. Picking one here changes that run only. */

function modelChoice(prefix, what) {
  const models = (STATE.claude && STATE.claude.models) || [];
  if (!models.length) return "";
  const current = STATE.claude.model;
  const options = models
    .map(
      m =>
        `<option value="${esc(m.id)}" ${m.id === current ? "selected" : ""}>${esc(m.name)}${m.note ? " — " + esc(m.note) : ""}</option>`
    )
    .join("");
  const when = what ? ` ${esc(what)}` : "";
  return `<div class="field model" style="margin:10px 0">
    <label for="${prefix}-model">Model <span class="hint">writes${when}; the default is set under Settings &amp; logs</span></label>
    <select id="${prefix}-model">${options}</select>
  </div>`;
}

/* What the form picked. A missing select means Studio's default, which the server applies. */
function modelBrief(prefix) {
  const select = document.getElementById(prefix + "-model");
  return select && select.value ? { model: select.value } : {};
}

/* ---------- the model behind the one-click actions ----------
   Review with Claude, Draw figures and Write notebooks start from a button or a row menu,
   with no form to hold a select of their own. So the Modules tab carries one pick for all
   of them (quickModelBar), and each of those calls sends it (quickModelBrief). It is kept
   for this Studio session only: a reload goes back to Studio's default. */
const modelPick = {
  quick: "", // the model the one-click actions run on; "" means Studio's default
};

/* The label a model is shown under, for a menu row or a button that names what will run. */
function modelName(id) {
  const models = (STATE.claude && STATE.claude.models) || [];
  const found = models.find(m => m.id === id);
  return found ? found.name : id || "the default model";
}

/* The pick, or the default when nothing (or a model this Studio no longer lists) is picked. */
function quickModel() {
  const models = (STATE.claude && STATE.claude.models) || [];
  const known = models.some(m => m.id === modelPick.quick);
  return known ? modelPick.quick : STATE.claude.model;
}

function setQuickModel(id) {
  modelPick.quick = id;
  toast("Review, figures and notebooks now run on " + modelName(quickModel()));
  if (typeof viewCourse === "function" && route.view === "course") viewCourse();
}

function quickModelBar() {
  const models = (STATE.claude && STATE.claude.models) || [];
  if (!models.length) return "";
  const current = quickModel();
  const options = models
    .map(
      m =>
        `<option value="${esc(m.id)}" ${m.id === current ? "selected" : ""}>${esc(m.name)}${m.note ? " — " + esc(m.note) : ""}</option>`
    )
    .join("");
  return `<div class="card tight figbar modelbar">
    <div><b>Model.</b> <span class="sub" style="margin:0">Review with Claude, Draw figures and Write notebooks run on the model picked here, for this session. The default is set under <a href="#/settings">Settings &amp; logs</a>; Patch or rewrite, Add a module and Resume pick their own on their forms.</span></div>
    <div class="actions" style="margin:0"><select id="quick-model" aria-label="Model for review, figures and notebooks" onchange="setQuickModel(this.value)">${options}</select></div>
  </div>`;
}

/* What a one-click action sends. */
function quickModelBrief() {
  return { model: quickModel() };
}
