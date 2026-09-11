/* ---------- notebooks: Jupyter notebooks for a module, written by the model ----------
   Only a course whose course.json declares `notebooks` (the Settings tab has the switch)
   carries any. The Modules tab shows how many modules have one and offers to write the
   missing ones; each module's row menu can write or replace its own. Both start a
   "notebooks" job (POST /api/courses/<id>/notebooks, .../modules/<mid>/notebooks) that
   ends with a rebuild, like a rewrite. Whether the notebooks can be run in the course
   page depends on the Jupyter server (STATE.jupyter, from /api/state). */

function notebooksBar(c) {
  const mods = c.moduleList || [];
  if (!mods.length || !c.notebooks) return "";
  const withNotebooks = mods.filter(m => m.notebooks > 0).length;
  const total = mods.reduce((n, m) => n + (m.notebooks || 0), 0);
  const missing = mods.length - withNotebooks;
  const can = providerReady();
  const jupyter = STATE.jupyter || {};
  const server = jupyter.available
    ? `Jupyter is running at ${jupyter.url}, so these run inside the course page.`
    : `Jupyter is not running, so the course page shows their saved runs only. Start it with docker compose up, or build.py jupyter.`;
  const why = `A Jupyter file written for a section (kernel ${c.notebooks.kernel}): the reader runs and edits it inside the module. ${server}`;
  const action =
    missing > 0
      ? `<button class="btn sm" ${can ? "" : "disabled"} data-help="${esc(why)}" onclick="writeNotebooks('${c.id}',null,false)">Write the missing ${missing}</button>`
      : `<button class="btn sm" ${can ? "" : "disabled"} data-help="${esc(why)}" onclick="writeNotebooks('${c.id}',null,true)">Replace all</button>`;
  return `<b>Notebooks</b> <span class="sub" data-help="${esc(why)}">${total} in ${withNotebooks}/${mods.length} modules</span> ${action}`;
}

/* One row menu entry, only in a course that declares notebooks. */
function notebooksMenuItem(c, m) {
  if (!c.notebooks) return "";
  const can = providerReady();
  const label = m.notebooks > 0 ? "Replace the notebooks" : "Write notebooks";
  const sub =
    m.notebooks > 0
      ? `${m.notebooks} now · replaced by new ones, by ${modelName(quickModel())}`
      : `a Jupyter notebook for its exercise, by ${modelName(quickModel())}`;
  return `<button role="menuitem" onclick="closeMenus();writeNotebooks('${c.id}','${m.id}',false)" ${can ? "" : "disabled"}>${label}<small>${sub}</small></button>`;
}

async function writeNotebooks(id, mid, all) {
  const base = `/api/courses/${encodeURIComponent(id)}`;
  const url = mid ? `${base}/modules/${encodeURIComponent(mid)}/notebooks` : `${base}/notebooks`;
  try {
    const { job: j } = await api(url, Object.assign({ all: !!all }, quickModelBrief()));
    location.hash = "#/job/" + j.id;
  } catch (err) {
    toast(err.message, { kind: "bad" });
  }
}
