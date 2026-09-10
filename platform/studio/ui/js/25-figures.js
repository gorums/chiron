/* ---------- figures: SVG diagrams for a module, drawn by the model ----------
   The course page's Modules tab shows how many modules carry figures and offers to draw
   the missing ones; each module's row menu can draw or redraw its own. Both start a
   "figures" job (POST /api/courses/<id>/figures, .../modules/<mid>/figures) that ends
   with a rebuild, like a rewrite. */

function figuresBar(c) {
  const mods = c.moduleList || [];
  if (!mods.length) return "";
  const withFigures = mods.filter(m => m.figures > 0).length;
  const total = mods.reduce((n, m) => n + (m.figures || 0), 0);
  const missing = mods.length - withFigures;
  const can = providerReady();
  const why = can
    ? "An SVG diagram drawn for a section: a flow, a funnel, a 2×2, a build-up the reader steps through. One call per module."
    : providerName() + " is not answering.";
  const action =
    missing > 0
      ? `<button class="btn sm" ${can ? "" : "disabled"} title="${esc(why)}" onclick="drawFigures('${c.id}',null,false)">Draw the missing ${missing}</button>`
      : `<button class="btn sm" ${can ? "" : "disabled"} title="${esc(why)}" onclick="drawFigures('${c.id}',null,true)">Redraw all</button>`;
  return `<b>Figures</b> <span class="sub" title="${esc(why)}">${total} in ${withFigures}/${mods.length} modules</span> ${action}`;
}

/* One row menu entry: draw, or redraw when the module already has figures. */
function figuresMenuItem(c, m) {
  const can = providerReady();
  const label = m.figures > 0 ? "Redraw the figures" : "Draw figures";
  const sub =
    m.figures > 0
      ? `${m.figures} now · replaced by new ones, by ${modelName(quickModel())}`
      : `SVG diagrams for its sections, by ${modelName(quickModel())}`;
  return `<button role="menuitem" onclick="closeMenus();drawFigures('${c.id}','${m.id}',false)" ${can ? "" : "disabled"}>${label}<small>${sub}</small></button>`;
}

async function drawFigures(id, mid, all) {
  const base = `/api/courses/${encodeURIComponent(id)}`;
  const url = mid ? `${base}/modules/${encodeURIComponent(mid)}/figures` : `${base}/figures`;
  try {
    const { job: j } = await api(url, Object.assign({ all: !!all }, quickModelBrief()));
    location.hash = "#/job/" + j.id;
  } catch (err) {
    toast(err.message, { kind: "bad" });
  }
}
