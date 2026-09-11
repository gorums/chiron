/* ---------- the model a writing job runs on ----------
   Every job that writes a course - a new one, a resumed run, an added module, a rewrite -
   is one long chain of calls to a model, and which model answers them is the biggest lever
   on both the quality and the cost of the result. So each of those forms shows the list from
   settings.json (modelChoice), preselected to Studio's default from Settings & logs, and
   sends what was picked as `model` in the request (modelBrief); the server takes a known
   alias and falls back to the default otherwise. Picking one here changes that run only. */

function modelList() {
  return llmState().models || [];
}

/* One <option> per model. Grouped by provider only when there is more than one to tell
   apart: with a single provider the group heading would say the same thing on every row. */
function modelOptions(current) {
  const rows = modelList();
  const groups = [];
  rows.forEach(m => {
    const label = m.providerLabel || m.provider || "";
    const group = groups.find(g => g.label === label);
    (group || groups[groups.push({ label, models: [] }) - 1]).models.push(m);
  });
  const option = m =>
    `<option value="${esc(m.id)}" ${m.id === current ? "selected" : ""}>${esc(m.name)}${m.note ? " — " + esc(m.note) : ""}</option>`;
  if (groups.length < 2) return rows.map(option).join("");
  return groups
    .map(g => `<optgroup label="${esc(g.label)}">${g.models.map(option).join("")}</optgroup>`)
    .join("");
}

function modelChoice(prefix, what) {
  if (!modelList().length) return "";
  const options = modelOptions(llmState().model);
  const when = what ? ` ${esc(what)}` : "";
  return `<div class="field model">
    <label for="${prefix}-model">Model</label>
    <select id="${prefix}-model">${options}</select>
    <span class="fhint">Writes${when}. The default is set under <a href="#/settings">Settings &amp; logs</a>; this picks for this run only.</span>
  </div>`;
}

/* What the form picked. A missing select means Studio's default, which the server applies. */
function modelBrief(prefix) {
  const select = document.getElementById(prefix + "-model");
  return select && select.value ? { model: select.value } : {};
}

/* ---------- the model behind the one-click actions ----------
   Review, Draw figures and Write notebooks start from a button or a row menu,
   with no form to hold a select of their own. So the Modules tab carries one pick for all
   of them (quickModelBar), and each of those calls sends it (quickModelBrief). It is kept
   for this Studio session only: a reload goes back to Studio's default. */
const modelPick = {
  quick: "", // the model the one-click actions run on; "" means Studio's default
};

/* The label a model is shown under, for a menu row or a button that names what will run. */
function modelName(id) {
  const found = modelList().find(m => m.id === id);
  return found ? found.name : id || "the default model";
}

/* The pick, or the default when nothing (or a model this Studio no longer lists) is picked. */
function quickModel() {
  const known = modelList().some(m => m.id === modelPick.quick);
  return known ? modelPick.quick : llmState().model;
}

function setQuickModel(id) {
  modelPick.quick = id;
  toast("Review, figures and notebooks now run on " + modelName(quickModel()));
  if (route.name === "course") viewCourse();
}

function quickModelBar() {
  if (!modelList().length) return "";
  const options = modelOptions(quickModel());
  const why =
    "Review, Draw figures and Write notebooks run on this, for this session only. Patch or rewrite, Add a module and Resume pick their own on their forms.";
  return `<label for="quick-model" data-help="${esc(why)}">Model</label>
    <select id="quick-model" data-help="${esc(why)}" aria-label="Model for review, figures and notebooks" onchange="setQuickModel(this.value)">${options}</select>`;
}

/* What a one-click action sends. */
function quickModelBrief() {
  return { model: quickModel() };
}
