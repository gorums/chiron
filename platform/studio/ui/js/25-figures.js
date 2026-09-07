/* ---------- figures: SVG diagrams for a module, drawn by Claude ----------
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
  const can = STATE.claude.available;
  const summary =
    withFigures === 0
      ? "No figures yet."
      : `${total} figure${total === 1 ? "" : "s"} across ${withFigures} of ${mods.length} modules.`;
  const action =
    missing > 0
      ? `<button class="btn sm" ${can ? "" : "disabled"} onclick="drawFigures('${c.id}',null,false)">Draw figures for the ${missing === mods.length ? "modules" : missing + " without"}</button>`
      : `<button class="btn sm ghost" ${can ? "" : "disabled"} onclick="drawFigures('${c.id}',null,true)">Redraw every figure</button>`;
  return `<div class="card tight figbar">
    <div><b>Figures.</b> <span class="sub" style="margin:0">${summary} A figure is an SVG diagram Claude draws for a section: a flow, a funnel, a 2x2, a build-up in steps the reader plays. Stored under <span class="mono">figures/</span>, inlined by the build.</span></div>
    <div class="actions" style="margin:0">${action}</div>
  </div>`;
}

/* One row menu entry: draw, or redraw when the module already has figures. */
function figuresMenuItem(c, m) {
  const can = STATE.claude.available;
  const label = m.figures > 0 ? "Redraw the figures" : "Draw figures";
  const sub =
    m.figures > 0
      ? `${m.figures} now · replaced by new ones`
      : "SVG diagrams for its sections, by Claude";
  return `<button role="menuitem" onclick="closeMenus();drawFigures('${c.id}','${m.id}',false)" ${can ? "" : "disabled"}>${label}<small>${sub}</small></button>`;
}

async function drawFigures(id, mid, all) {
  const base = `/api/courses/${encodeURIComponent(id)}`;
  const url = mid ? `${base}/modules/${encodeURIComponent(mid)}/figures` : `${base}/figures`;
  try {
    const { job: j } = await api(url, { all: !!all });
    location.hash = "#/job/" + j.id;
  } catch (err) {
    toast(err.message);
  }
}
