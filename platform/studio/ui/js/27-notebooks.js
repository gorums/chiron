/* ---------- notebooks: Jupyter notebooks for a module, written by Claude ----------
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
  const can = STATE.claude.available;
  const jupyter = STATE.jupyter || {};
  const summary =
    withNotebooks === 0
      ? "No notebooks yet."
      : `${total} notebook${total === 1 ? "" : "s"} across ${withNotebooks} of ${mods.length} modules.`;
  const server = jupyter.available
    ? `Jupyter is running at <span class="mono">${esc(jupyter.url)}</span>, so they run inside the course page.`
    : `Jupyter is not running, so the course page shows their saved runs only. Start it with <span class="mono">docker compose up</span> or <span class="mono">build.py jupyter</span>.`;
  const action =
    missing > 0
      ? `<button class="btn sm" ${can ? "" : "disabled"} onclick="writeNotebooks('${c.id}',null,false)">Write notebooks for the ${missing === mods.length ? "modules" : missing + " without"}</button>`
      : `<button class="btn sm ghost" ${can ? "" : "disabled"} onclick="writeNotebooks('${c.id}',null,true)">Replace every notebook</button>`;
  return `<div class="card tight figbar">
    <div><b>Notebooks.</b> <span class="sub" style="margin:0">${summary} A notebook is a Jupyter file Claude writes for a section (kernel <span class="mono">${esc(c.notebooks.kernel)}</span>): the reader runs and edits it inside the module. Stored under <span class="mono">notebooks/</span>, rendered by the build. ${server}</span></div>
    <div class="actions" style="margin:0">${action}</div>
  </div>`;
}

/* One row menu entry, only in a course that declares notebooks. */
function notebooksMenuItem(c, m) {
  if (!c.notebooks) return "";
  const can = STATE.claude.available;
  const label = m.notebooks > 0 ? "Replace the notebooks" : "Write notebooks";
  const sub =
    m.notebooks > 0
      ? `${m.notebooks} now · replaced by new ones`
      : "a Jupyter notebook for its exercise, by Claude";
  return `<button role="menuitem" onclick="closeMenus();writeNotebooks('${c.id}','${m.id}',false)" ${can ? "" : "disabled"}>${label}<small>${sub}</small></button>`;
}

async function writeNotebooks(id, mid, all) {
  const base = `/api/courses/${encodeURIComponent(id)}`;
  const url = mid ? `${base}/modules/${encodeURIComponent(mid)}/notebooks` : `${base}/notebooks`;
  try {
    const { job: j } = await api(url, { all: !!all });
    location.hash = "#/job/" + j.id;
  } catch (err) {
    toast(err.message);
  }
}
