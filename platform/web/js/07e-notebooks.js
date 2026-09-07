/* Notebooks on the Read step: a Jupyter notebook the build rendered read-only for a
   section (coursekit/notebooks.py). Served by Studio with a Jupyter server up, the block
   gains "Run it here", which swaps the rendering for the live notebook in a frame - the
   same file, under the course's notebooks/, so what the reader saves is what the course
   carries - and "Open in a tab". Off disk, or with no server, the saved run is all there
   is and the block says so. Nothing here is stored: a notebook starts as its saved run
   every time the section is drawn. */

const notebooks = {
  probe: null, // the pending or finished ask to Studio about Jupyter, one per Read step
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
  if (!blocks.length) return;
  blocks.forEach(block => notebookTools(block, null));
  notebooks.probe = null;
  jupyterInfo().then(info => {
    if (!info) return;
    blocks.forEach(block => {
      if (block.isConnected) notebookTools(block, info);
    });
  });
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
  if (!info) {
    const why = STUDIO
      ? "Jupyter is not running, so this is the saved run."
      : "The saved run. Opened from Studio with Jupyter running, it runs here.";
    tools.innerHTML = `<span class="nb-note">${why}</span>`;
    return;
  }
  tools.innerHTML = `<button type="button" class="btn sm" data-act="run">▶ Run it here</button>
    <a class="btn sm ghost" href="${notebookUrl(info, name)}" target="_blank" rel="noopener">Open in a tab ↗</a>`;
  tools.querySelector('[data-act="run"]').onclick = () => notebookToggle(block, info);
}

/* Swap the saved run for the live notebook, or back. */
function notebookToggle(block, info) {
  const button = block.querySelector('[data-act="run"]');
  const frame = block.querySelector("iframe.nb-frame");
  if (frame) {
    frame.remove();
    block.classList.remove("live");
    if (button) button.textContent = "▶ Run it here";
    return;
  }
  const name = block.getAttribute("data-nb");
  const live = document.createElement("iframe");
  live.className = "nb-frame";
  live.title = `Notebook ${name}`;
  live.style.height = NOTEBOOKS.height + "px";
  live.src = notebookUrl(info, name);
  block.classList.add("live");
  block.appendChild(live);
  if (button) button.textContent = "Show the saved run";
}

/* What the tutor is told about a section's notebooks: the code, so it can talk about
   the cell the reader is stuck on. */
function notebookPlaceText(sec) {
  return (sec.notebooks || [])
    .map(n => `\n\nThe notebook ${n.name} in this section, which they can run and edit:\n${n.code}`)
    .join("");
}
