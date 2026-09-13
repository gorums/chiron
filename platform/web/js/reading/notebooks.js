/* Notebooks on the Read step: a Jupyter notebook the build rendered read-only for a
   section (coursekit/notebooks.py). Served by Studio with a Jupyter server up, the block
   gains "Run it here", which swaps the rendering for the live notebook in a frame - the
   same file, under the course's notebooks/, so what the reader saves is what the course
   carries - and "Open in a tab". Off disk, or with no server, the saved run is all there
   is and the block says so.

   The reading column is about 560px wide, which is enough to read a notebook and not
   enough to work in one, so the block carries its own room to work: drag the live frame's
   bottom edge for height, "Wide" trades the section list and the reading measure for
   width, and
   "Full screen" gives it the window. Height and width are device settings under STATE.ui,
   like the reading preferences; nothing about the notebook itself is stored, so it starts
   as its saved run every time the section is drawn. */

const notebooks = {
  probe: null, // the pending or finished ask to Studio about Jupyter, one per Read step
  full: null, // the block filling the window, or null
  spacer: null, // what holds that block's place in the flow meanwhile
};

/* What Studio knows about the Jupyter server: {available, url, token}, or null when the
   page is not served by Studio or the server is down. Asked once per Read step. */
function jupyterInfo() {
  if (!STUDIO) return Promise.resolve(null);
  if (!notebooks.probe) {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), TUTOR.probeTimeoutMs);
    notebooks.probe = fetch(STUDIO.origin + "/api/jupyter", {
      signal: ctrl.signal,
      cache: "no-store",
    })
      .then(r => r.json())
      .then(j => (j && j.available && j.url ? j : null))
      .catch(() => null)
      .finally(() => clearTimeout(t));
  }
  return notebooks.probe;
}

function setupNotebooks() {
  const blocks = [...document.querySelectorAll(".notebook[data-nb]")];
  if (notebooks.full && !notebooks.full.isConnected) notebookForget();
  if (!blocks.length) return;
  applyNotebookWide();
  blocks.forEach(block => {
    notebookHeightApply(block);
    notebookTools(block, null);
  });
  notebooks.probe = null;
  jupyterInfo().then(info => {
    if (!info) return;
    blocks.forEach(block => {
      if (block.isConnected) notebookTools(block, info);
    });
  });
}

/* Leaving the Read step takes the window back: a block left full screen would outlive the
   page it belongs to, and the wide column means nothing anywhere else. */
function notebookRouteChanged() {
  if (notebooks.full) notebookFull(notebooks.full);
  document.body.classList.remove("nb-wide");
}
/* The same, for a block the page redrew out from under us: there is nothing left to put
   back, only the window to give up. */
function notebookForget() {
  document.body.classList.remove("nb-full");
  if (notebooks.spacer) notebooks.spacer.remove();
  notebooks.spacer = null;
  notebooks.full = null;
}

/* The live notebook: Jupyter serves the courses directory, so the path is the course id
   and the file under its notebooks/. The token is only needed once; the server then
   keeps a cookie. */
function notebookUrl(info, name) {
  const path = `${encodeURIComponent(CFG.id)}/notebooks/${encodeURIComponent(name)}`;
  return `${info.url}/notebooks/${path}?token=${encodeURIComponent(info.token || "")}`;
}

function notebookTools(block, info) {
  const tools = block.querySelector(".nb-tools");
  if (!tools) return;
  const name = block.getAttribute("data-nb");
  const wide = notebookWide();
  const full = notebooks.full === block;
  const live = !!block.querySelector("iframe.nb-frame");
  const room = `<button type="button" class="btn sm ghost" data-act="wide" aria-pressed="${wide}" data-help="${wide ? "Back to the reading column and the section list" : "Give the whole step the width - the section list makes way"}">${wide ? "Narrow" : "Wide"}</button>
    <button type="button" class="btn sm ghost" data-act="full" aria-pressed="${full}" data-help="${full ? "Put the notebook back in the page" : "Fill the window with this notebook"}">${full ? "Close" : "Full screen"}</button>`;
  if (!info) {
    const why = STUDIO
      ? "Jupyter is not running, so this is the saved run."
      : "The saved run. Opened from Studio with Jupyter running, it runs here.";
    tools.innerHTML = `<span class="nb-note">${why}</span>${room}`;
  } else {
    const runLabel = live ? "Show the saved run" : "▶ Run it here";
    tools.innerHTML = `${room}
      <button type="button" class="btn sm" data-act="run">${runLabel}</button>
      <a class="btn sm ghost" href="${notebookUrl(info, name)}" target="_blank" rel="noopener">Open in a tab ↗</a>`;
  }
  const run = tools.querySelector('[data-act="run"]');
  if (run) run.onclick = () => notebookToggle(block, info);
  tools.querySelector('[data-act="wide"]').onclick = () => notebookToggleWide();
  tools.querySelector('[data-act="full"]').onclick = () => notebookFull(block);
}

/* Swap the saved run for the live notebook, or back. */
function notebookToggle(block, info) {
  const frame = block.querySelector("iframe.nb-frame");
  if (frame) {
    frame.remove();
    block.classList.remove("live");
  } else {
    const name = block.getAttribute("data-nb");
    const live = document.createElement("iframe");
    live.className = "nb-frame";
    live.title = `Notebook ${name}`;
    live.src = notebookUrl(info, name);
    block.classList.add("live");
    block.appendChild(live);
  }
  notebookTools(block, info);
}

/* ---------- room to work ---------- */

/* How tall a notebook is: what the reader last dragged a live frame to, or the platform's
   default. One number for every block - a reader who wants a tall notebook wants tall
   notebooks - and the cap on the saved run as well. */
function notebookHeight() {
  const kept = (STATE.ui || {}).nbHeight;
  if (!kept) return NOTEBOOKS.height;
  return Math.min(Math.max(kept, NOTEBOOKS.minHeight), NOTEBOOKS.maxHeight);
}
function notebookHeightApply(block) {
  block.style.setProperty("--nb-h", notebookHeight() + "px");
  block.addEventListener("pointerup", () => notebookHeightKeep(block));
}
/* A drag on the frame's bottom edge is the browser's own resize, and it reports nothing
   while it runs: read what it left behind, and keep it for every notebook after this. */
function notebookHeightKeep(block) {
  const frame = block.querySelector("iframe.nb-frame");
  if (!frame || notebooks.full === block) return;
  const h = Math.round(frame.getBoundingClientRect().height);
  if (!h || Math.abs(h - notebookHeight()) < 4) return;
  if (!STATE.ui) STATE.ui = {};
  STATE.ui.nbHeight = Math.min(Math.max(h, NOTEBOOKS.minHeight), NOTEBOOKS.maxHeight);
  document
    .querySelectorAll(".notebook[data-nb]")
    .forEach(b => b.style.setProperty("--nb-h", STATE.ui.nbHeight + "px"));
  save();
}

function notebookWide() {
  return !!(STATE.ui && STATE.ui.nbWide);
}
function applyNotebookWide() {
  const on = notebookWide() && route.view === "m" && route.step === 1;
  document.body.classList.toggle("nb-wide", on);
}
function notebookToggleWide() {
  if (!STATE.ui) STATE.ui = {};
  STATE.ui.nbWide = !notebookWide();
  save();
  applyNotebookWide();
  const wide = notebookWide();
  document.querySelectorAll('.notebook[data-nb] [data-act="wide"]').forEach(button => {
    button.setAttribute("aria-pressed", String(wide));
    button.textContent = wide ? "Narrow" : "Wide";
  });
}

/* Full screen, and back. The block leaves the flow, so a spacer of the same height holds
   its place - without one the page behind collapses and the reader comes back to
   somewhere else. The frame itself is never re-made, so a running kernel survives it. */
function notebookFull(block) {
  const on = notebooks.full !== block;
  if (notebooks.full && notebooks.full !== block) notebookFull(notebooks.full);
  if (on) {
    const spacer = document.createElement("div");
    spacer.className = "nb-spacer";
    spacer.style.height = Math.round(block.getBoundingClientRect().height) + "px";
    block.parentNode.insertBefore(spacer, block);
    notebooks.spacer = spacer;
    notebooks.full = block;
    block.classList.add("full");
    document.body.classList.add("nb-full");
  } else {
    block.classList.remove("full");
    notebookForget();
  }
  const button = block.querySelector('[data-act="full"]');
  if (!button) return;
  button.setAttribute("aria-pressed", String(on));
  button.textContent = on ? "Close" : "Full screen";
  const hint = on ? "Put the notebook back in the page" : "Fill the window with this notebook";
  button.setAttribute("data-help", hint);
  button.focus();
}

/* What the tutor is told about a section's notebooks: the code, so it can talk about
   the cell the reader is stuck on. */
function notebookPlaceText(sec) {
  return (sec.notebooks || [])
    .map(n => `\n\nThe notebook ${n.name} in this section, which they can run and edit:\n${n.code}`)
    .join("");
}
