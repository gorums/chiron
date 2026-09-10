/* ---------- the model list ----------
   The models every picker offers - the default here, the forms that write a course, the
   one-click actions, the tutor in a served page - are one list: the platform's, from
   settings.json, under whatever this editor saved (GET/PUT /api/models). So when a model
   ships or retires, the owner edits a table instead of a committed file. A row's Test
   button asks the CLI once with that model only, no fallback, so a typo shows up here and
   not forty minutes into a run. */

const modelEditor = {
  rows: [], // the rows being edited: {provider, id, alias, label, note}; saved as one list
  results: {}, // id -> the last Test result for that row, {ok, seconds, reply|error}
  testing: "", // the id a test is running for, "" when none
  custom: false, // is the list in use Studio's own rather than the platform's?
  message: "", // the last save error, shown under the table
  discovery: {}, // GET /api/settings `discovery`: the last automatic check and its sources
  checking: false, // is "Check now" running?
};

const MODEL_FIELDS = [
  ["id", "id, as claude --model takes it", "claude-sonnet-5"],
  ["alias", "short alias (optional)", "sonnet"],
  ["label", "shown as", "Claude Sonnet 5"],
  ["note", "when to pick it", "fast and cheap; fine for a patch or the tutor"],
];

/* Load the rows from what the settings page already fetched. */
function loadModelEditor(list, discovery) {
  modelEditor.discovery = discovery || modelEditor.discovery || {};
  modelEditor.rows = (list.list || []).map(m => ({
    provider: m.provider || "",
    id: m.id,
    alias: m.alias || "",
    label: m.label || "",
    note: m.note || "",
  }));
  modelEditor.custom = !!list.custom;
  modelEditor.message = "";
}

function modelEditorCard() {
  const source = modelEditor.custom
    ? `<span class="pill on">Studio's own list</span> saved in <span class="mono">state/settings.json</span>`
    : `<span class="pill">the built-in list</span> from <span class="mono">platform/settings.json</span>`;
  const reset = modelEditor.custom
    ? `<button class="btn sm" onclick="resetModelList()">Back to the built-in list</button>`
    : "";
  return `<div class="card" id="modelcard">
    <h3 class="eyebrow">Models on offer</h3>
    <p class="sub">Every picker in Studio and in a course page opened from here offers this list, in this order. Add a model the day it ships, retire one that is gone, and <b>Test</b> it before trusting it with a run: the test asks Claude Code once with that model only. In use: ${source}.</p>
    <div class="modelrows gap-top" id="modelrows">${modelEditor.rows.map((r, i) => modelRow(r, i)).join("")}</div>
    <div class="actions gap-top">
      <button class="btn sm" onclick="addModelRow()">Add a model</button>
      <span class="spacer"></span>
      ${reset}
      <button class="btn sm primary" onclick="saveModelList()">Save the list</button>
    </div>
    <div id="modelmsg">${modelEditor.message ? `<div class="problems">${esc(modelEditor.message)}</div>` : ""}</div>
    ${discoveryLine()}
    <p class="sub result">A course page opened from Studio takes the new list on its next load; one opened off disk keeps the list it was built with until the course is rebuilt. The bridge reads it when it starts.</p>
  </div>`;
}

/* The automatic check: where models come from, when it last ran, what it changed. */
function discoveryLine() {
  const d = modelEditor.discovery || {};
  const last = d.last || null;
  const cli = last && last.sources ? last.sources.cli : null;
  const api = last && last.sources ? last.sources.api : null;
  const cliText = !cli
    ? "not read yet"
    : cli.ok
      ? `${cli.known} models known, ${cli.offered} offered`
      : `could not be read (${cli.error})`;
  const apiText = d.apiConfigured
    ? api && api.ok
      ? `${api.count} models listed`
      : api
        ? `failed (${api.error})`
        : "not read yet"
    : "no API key; set <span class='mono'>ANTHROPIC_API_KEY</span> in <span class='mono'>.env</span> to use it";
  const changes = !last
    ? ""
    : last.changed
      ? ` Added ${last.added.length ? last.added.map(esc).join(", ") : "none"}; removed ${last.removed.length ? last.removed.map(esc).join(", ") : "none"}.`
      : " Nothing new.";
  const when = last ? `Last check ${esc(last.at.replace("T", " "))}.` : "No check has run yet.";
  const every = d.hours > 0 ? `every ${d.hours} hours` : "off (discovery.hours is 0)";
  return `<div class="discovery">
    <p class="sub result"><b>Kept up to date automatically</b>, ${every}: Claude Code's catalog (${cliText}) and Anthropic's model list (${apiText}). ${when}${changes}</p>
    <div class="actions"><button class="btn sm" onclick="discoverModels()" ${modelEditor.checking ? "disabled" : ""}>${modelEditor.checking ? `<span class="spin"></span> Checking…` : "Check now"}</button></div>
  </div>`;
}

async function discoverModels() {
  modelEditor.checking = true;
  renderModelEditor();
  try {
    const { report, models } = await api("/api/models/discover", {});
    loadModelEditor(models, { ...modelEditor.discovery, last: report });
    toast(
      report.changed
        ? `Models: added ${report.added.length}, removed ${report.removed.length}`
        : "No new models"
    );
    await refresh();
    viewSettingsPage();
  } catch (err) {
    modelEditor.message = err.message;
  }
  modelEditor.checking = false;
  renderModelEditor();
}

function modelRow(row, i) {
  const inputs = MODEL_FIELDS.map(
    ([key, hint, sample]) =>
      `<input type="text" class="${key}" value="${esc(row[key])}" placeholder="${esc(sample)}" title="${esc(hint)}" aria-label="${esc(hint)}" oninput="editModelRow(${i}, '${key}', this.value)" spellcheck="false">`
  ).join("");
  const testing = modelEditor.testing === row.id;
  const first = i === 0;
  const last = i === modelEditor.rows.length - 1;
  return `<div class="modelrow">
    <div class="fields">${inputs}</div>
    <div class="tools">
      ${modelTestResult(row.id)}
      <button class="btn sm" onclick="testModelRow(${i})" ${testing ? "disabled" : ""} title="Ask Claude Code once with this model only">${testing ? `<span class="spin"></span> Testing…` : "Test"}</button>
      <button class="btn sm" onclick="moveModelRow(${i}, -1)" ${first ? "disabled" : ""} title="Move up" aria-label="Move up">${ico("up", 13)}</button>
      <button class="btn sm" onclick="moveModelRow(${i}, 1)" ${last ? "disabled" : ""} title="Move down" aria-label="Move down">${ico("down", 13)}</button>
      <button class="btn sm rm" onclick="removeModelRow(${i})" title="Remove from the list" aria-label="Remove">${ico("close", 13)}</button>
    </div>
  </div>
  ${modelTestError(row.id)}`;
}

/* "refused" only when the model is what was refused. An account that is out of quota, or a
   CLI nobody has signed in to, would fail this test for every id on the list, and calling
   that a bad model sends the reader off editing something that was never wrong. */
function modelTestResult(id) {
  const r = modelEditor.results[id];
  if (!r) return "";
  const blame = r.why === "quota" || r.why === "auth" ? "not this model" : "refused";
  return `<span class="pill ${r.ok ? "on" : "off"}">${r.ok ? `answers in ${r.seconds}s` : blame}</span>`;
}

/* A refusal is the whole point of the Test button, so it is printed, not left in a title. */
function modelTestError(id) {
  const r = modelEditor.results[id];
  if (!r || r.ok) return "";
  const advice = r.advice ? `<br />${esc(r.advice)}` : "";
  return `<p class="problems modelerr">${esc(id)} refused: ${esc(r.error)}${advice}</p>`;
}

function editModelRow(i, key, value) {
  modelEditor.rows[i][key] = value;
}

function renderModelEditor() {
  const card = $("#modelcard");
  if (!card) return;
  card.outerHTML = modelEditorCard();
}

function addModelRow() {
  modelEditor.rows.push({ provider: "", id: "", alias: "", label: "", note: "" });
  renderModelEditor();
  const rows = document.querySelectorAll("#modelrows .modelrow input.id");
  if (rows.length) rows[rows.length - 1].focus();
}

function removeModelRow(i) {
  modelEditor.rows.splice(i, 1);
  renderModelEditor();
}

function moveModelRow(i, by) {
  const to = i + by;
  if (to < 0 || to >= modelEditor.rows.length) return;
  const [row] = modelEditor.rows.splice(i, 1);
  modelEditor.rows.splice(to, 0, row);
  renderModelEditor();
}

async function testModelRow(i) {
  const id = (modelEditor.rows[i].id || "").trim();
  if (!id) return;
  modelEditor.testing = id;
  renderModelEditor();
  try {
    modelEditor.results[id] = await api("/api/models/test", { model: id });
  } catch (err) {
    modelEditor.results[id] = { ok: false, seconds: 0, error: err.message };
  }
  modelEditor.testing = "";
  renderModelEditor();
  const r = modelEditor.results[id];
  toast(r.ok ? `${id} answers` : r.advice || `${id} refused: ${r.error}`, {
    kind: r.ok ? "ok" : "bad",
  });
}

/* Save the whole list; the server validates it and every picker takes it from /api/state. */
async function saveModelList() {
  const list = modelEditor.rows.map(r => ({
    provider: r.provider || "",
    id: r.id.trim(),
    alias: r.alias.trim(),
    label: r.label.trim(),
    note: r.note.trim(),
  }));
  try {
    const { models } = await api("/api/models", { list }, "PUT");
    loadModelEditor(models);
    toast("Model list saved");
    await refresh();
    viewSettingsPage();
  } catch (err) {
    modelEditor.message = err.message;
    renderModelEditor();
  }
}

async function resetModelList() {
  try {
    const { models } = await api("/api/models/reset", {});
    loadModelEditor(models);
    toast("Back to the platform's model list");
    await refresh();
    viewSettingsPage();
  } catch (err) {
    modelEditor.message = err.message;
    renderModelEditor();
  }
}
