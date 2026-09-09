/* ---------- Studio settings & logs ---------- */

let logTimer = null;

/* What each layer of the settings stack means, so the source column reads as English. */
const SOURCE_HELP = {
  "settings.json": "the platform's committed default",
  Studio: "saved on this page",
  ".env": "set in the .env file at the repository root",
  environment: "set in this process's environment",
  overlay: "set by the JSON overlay named by SETTINGS_FILE",
};

async function viewSettingsPage() {
  let s;
  try {
    s = await api("/api/settings");
  } catch (err) {
    $("#view").innerHTML = `<p class="crumb"><a href="#/">Courses</a> › Settings &amp; logs</p>
      <div class="card"><h3>Cannot read the settings</h3><p class="sub">${esc(err.message)}</p>
      <div class="rowline gap-top"><button class="btn primary" onclick="viewSettingsPage()">Try again</button></div></div>`;
    return;
  }
  if (route.name !== "settings") return;
  loadModelEditor(s.modelList || {}, s.discovery || {});
  const models = (s.models || [])
    .map(
      m =>
        `<label class="radio"><input type="radio" name="model" value="${esc(m.id)}" ${s.model === m.id ? "checked" : ""} onchange="saveStudioSettings()"> <b>${esc(m.name)}</b>${m.note ? ` <span class="sub">— ${esc(m.note)}</span>` : ""}</label>`
    )
    .join("");
  $("#view").innerHTML = `
    <p class="crumb"><a href="#/">Courses</a> › Settings &amp; logs</p>
    <h2 class="big">Settings &amp; logs</h2>
    <p class="lede">What Studio uses for every writing and tutor call, and what it has been doing.</p>

    <div class="card">
      <h3 class="eyebrow">Model</h3>
      <p class="sub">The default for every writing and tutor call. Each form that writes a course — new, resume, add a module, patch or rewrite — offers the same list and can pick another model for that run alone. If a model is unavailable, Studio falls back to this one before giving up.</p>
      <div class="radios gap-top">${models}</div>
      <div id="settingsmsg"></div>
    </div>

    ${modelEditorCard()}

    <div class="card">
      <h3 class="eyebrow" title="${esc(help("profile"))}">Reader profiles</h3>
      <p class="sub">Each profile has its own progress for every course. Studio shows, and a course opened from Studio syncs to, the profile chosen in the header. The default profile keeps its files where they always were; the others live in a folder of their own under <span class="mono">state/progress/</span>.</p>
      <div id="profilelist" class="gap-top">${(STATE.profiles || ["default"]).map(profileRow).join("")}</div>
      <form class="actions gap-top" id="profileform">
        <label class="visually-hidden" for="newprofile">New profile name</label>
        <input type="text" id="newprofile" placeholder="new profile name, e.g. alex" autocomplete="off">
        <button class="btn">Add and switch</button>
      </form>
    </div>

    <div class="card">
      <h3 class="eyebrow">Claude Code</h3>
      <p>${s.claude.available ? `<span class="pill on">found</span> <span class="mono">${esc(s.claude.path)}</span>` : `<span class="pill off">not found on PATH</span> — writing a course and the tutor are off until it is installed and signed in.`}</p>
      ${s.claude.available ? "" : `<p class="sub">Install the <span class="mono">claude</span> command on this machine's PATH, run <span class="mono">claude login</span>, then reload this page.</p>`}
    </div>

    <div class="card">
      <h3 class="eyebrow">Jupyter</h3>
      <p>${jupyterStatusLine(s.jupyter || {})}</p>
      <p class="sub">A course whose settings turn notebooks on carries Jupyter notebooks the reader runs inside each module. Studio looks for the server at <span class="mono">${esc((s.jupyter || {}).internalUrl || "")}</span> and tells the course page to use <span class="mono">${esc((s.jupyter || {}).url || "")}</span>; both sides read <span class="mono">${esc((s.jupyter || {}).config || "")}</span>.</p>
    </div>

    <div class="card">
      <h3 class="eyebrow">Platform settings</h3>
      <p class="sub">Every default the platform has — ports, the API endpoint, the model list, timeouts, generation counts, the page's study rules and layout — is in <span class="mono">${esc(s.paths.settings)}</span>. Per-machine overrides go in <span class="mono">.env</span> or the environment under these names: ${Object.entries(
        s.envKeys || {}
      )
        .map(([k, v]) => `<span class="mono" title="${esc(v)}">${esc(k)}</span>`)
        .join(
          " · "
        )}. A JSON overlay named by <span class="mono">SETTINGS_FILE</span> can override anything. Restart Studio after changing any of them.${s.paths.overlay ? ` Overlay in use: <span class="mono">${esc(s.paths.overlay)}</span>.` : ""}</p>
      <table class="paths gap-top">
        <thead><tr><th>Setting</th><th>In use</th><th>Where it came from</th></tr></thead>
        <tbody>${(s.platform || []).map(settingRow).join("")}</tbody>
      </table>
    </div>

    <div class="card">
      <h3 class="eyebrow">Where things are</h3>
      <table class="paths">${Object.entries(s.paths)
        .map(([k, v]) => `<tr><td>${esc(k)}</td><td class="mono">${esc(v || "—")}</td></tr>`)
        .join("")}</table>
    </div>

    <div class="card">
      <div class="editbar">
        <h3 class="eyebrow">Log</h3>
        <span class="spacer"></span>
        <label class="visually-hidden" for="loglevel">Level</label>
        <select id="loglevel" onchange="loadLogs()">
          ${["DEBUG", "INFO", "WARNING", "ERROR"].map(l => `<option ${l === "INFO" ? "selected" : ""}>${l}</option>`).join("")}
        </select>
        <label class="visually-hidden" for="logq">Filter</label>
        <input type="text" id="logq" placeholder="filter…" oninput="loadLogs()">
        <label class="radio"><input type="checkbox" id="logfollow" checked onchange="followLogs()"> follow</label>
        <button class="btn sm" onclick="loadLogs()">Refresh</button>
        <button class="btn sm" onclick="clearLogs()" title="Empties what this page shows. The log file on disk is untouched.">Clear log buffer</button>
      </div>
      <pre class="logbox" id="logbox" role="log" aria-live="polite" aria-label="Studio log">loading…</pre>
      <p class="sub result">The full file is <span class="mono">${esc(s.paths.log || "console only")}</span>, rotating at ${Math.round((s.logs.maxBytes || 0) / 100000) / 10} MB × ${s.logs.backups}. Every Claude call is one line: model, time taken, prompt and reply size, and the CLI's stderr when it fails.</p>
    </div>`;
  $("#profileform").onsubmit = e => {
    e.preventDefault();
    addProfile();
  };
  loadLogs();
  followLogs();
}

function profileRow(name) {
  const active = name === STATE.profile;
  return `<div class="profilerow" id="prow-${esc(name)}">
    <span class="name">${esc(name)}</span>
    ${active ? `<span class="pill on">reading as</span>` : `<button class="btn sm" onclick="switchProfile('${esc(name)}')">Read as</button>`}
    ${name === "default" ? "" : `<button class="btn sm rm" title="Move this profile's progress to the trash" aria-label="Remove the profile ${esc(name)}" onclick="askRemoveProfile('${esc(name)}')">${ico("trash", 14)}</button>`}
    <span class="confirm" id="prm-${esc(name)}"></span>
  </div>`;
}

/* One resolved platform setting: what it is, what it is set to, and which layer said so. */
function settingRow(r) {
  const source = r.source === "settings.json" ? "" : r.source;
  const why = SOURCE_HELP[r.source] || "";
  return `<tr><td>${esc(r.key)}</td><td class="mono">${esc(String(r.value))}</td>
    <td class="sub"${why ? ` title="${esc(why)}"` : ""}>${esc(source || "default")}</td></tr>`;
}

function jupyterStatusLine(j) {
  if (j.available)
    return `<span class="pill on">running</span> <span class="mono">${esc(j.url)}</span> · Jupyter Server ${esc(j.version)}`;
  const install = j.installed ? "" : ` after <span class="mono">pip install notebook</span>`;
  return `<span class="pill off">not running</span> — notebooks show their saved runs only. Start it with <span class="mono">docker compose up</span>, or <span class="mono">python platform/build.py jupyter</span>${install}.`;
}

async function saveStudioSettings() {
  const model = (document.querySelector("input[name=model]:checked") || {}).value;
  const msg = $("#settingsmsg");
  try {
    await api("/api/settings", { model });
    toast("Default model: " + model);
    await refresh();
  } catch (err) {
    if (msg) msg.innerHTML = `<div class="problems">${esc(err.message)}</div>`;
  }
}

async function loadLogs() {
  const box = $("#logbox");
  if (!box || route.name !== "settings") return;
  const level = ($("#loglevel") || {}).value || "INFO";
  const q = ($("#logq") || {}).value || "";
  try {
    const { lines } = await api(
      `/api/logs?limit=500&level=${encodeURIComponent(level)}&q=${encodeURIComponent(q)}`
    );
    // Only follow when the reader has not scrolled up to look at something.
    const atBottom = box.scrollHeight - box.scrollTop - box.clientHeight < 40;
    box.innerHTML = lines.length
      ? lines
          .map(
            l =>
              `<div class="ll ${esc(l.level)}"><span class="lt">${esc(clock(l.t))}</span><span class="lv">${esc(l.level.slice(0, 4))}</span><span class="lm">${esc(l.msg)}</span></div>`
          )
          .join("")
      : `<div class="ll INFO"><span class="lm">Nothing yet at this level.</span></div>`;
    if (atBottom) box.scrollTop = box.scrollHeight;
  } catch (err) {
    box.textContent = err.message;
  }
}

function followLogs() {
  clearInterval(logTimer);
  if (($("#logfollow") || {}).checked) logTimer = setInterval(loadLogs, 3000);
}

async function clearLogs() {
  try {
    await api("/api/logs/clear", {});
    loadLogs();
  } catch (err) {
    toast(err.message, { kind: "bad" });
  }
}

/* ---------- the editor ---------- */

async function viewEdit() {
  const id = route.id,
    path = route.query.path || "";
  const course = courseCache[id];
  const name = course ? course.title : id;
  const crumb = `<p class="crumb"><a href="#/">Courses</a> › <a href="#/course/${encodeURIComponent(id)}?tab=files">${esc(name)}</a> › ${esc(path)}</p>`;
  $("#view").innerHTML = crumb + `<p class="sub">Loading…</p>`;
  let file;
  try {
    file = await api(
      `/api/courses/${encodeURIComponent(id)}/files?path=${encodeURIComponent(path)}`
    );
  } catch (err) {
    $("#view").innerHTML =
      crumb +
      `<div class="card"><h3>Cannot open that file</h3><p class="sub">${esc(err.message)}</p>
       <div class="rowline gap-top"><button class="btn primary" onclick="viewEdit()">Try again</button>
       <a class="btn" href="#/course/${encodeURIComponent(id)}?tab=files">Back to the files</a></div></div>`;
    return;
  }
  $("#view").innerHTML = `
    ${crumb}
    <div class="editbar">
      <span class="path">${esc(path)}</span>
      <label class="radio"><input type="checkbox" id="editwrap" onchange="toggleWrap()"> wrap lines</label>
      <button class="btn sm primary" id="savebtn" onclick="saveFile('${id}', 'build')">Save, check and build</button>
      <button class="btn sm" onclick="saveFile('${id}', true)">Save and check</button>
      <button class="btn sm" onclick="saveFile('${id}')">Save only</button>
    </div>
    <label class="visually-hidden" for="editor">${esc(path)}</label>
    <textarea class="editor" id="editor" spellcheck="false"></textarea>
    <div id="editout"></div>
    <p class="sub result">Ctrl+S saves, Ctrl+Shift+S saves and builds. Tab indents; press Escape first if you want to tab out of the box.
      A module's first line must be <span class="mono"># M07 — Title</span>; every <span class="mono">## </span> heading with content is one section, and the suggestion file for the module needs exactly that many entries.</p>`;
  const ta = $("#editor");
  ta.value = file.text;
  let tabEscapes = false;
  ta.addEventListener("keydown", e => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
      e.preventDefault();
      saveFile(id, e.shiftKey ? "build" : false);
      return;
    }
    if (e.key === "Escape") {
      tabEscapes = true;
      return;
    }
    if (e.key === "Tab" && !tabEscapes) {
      e.preventDefault();
      const s = ta.selectionStart;
      ta.setRangeText("  ", s, ta.selectionEnd, "end");
    }
    tabEscapes = false;
  });
  ta.focus();
}

function toggleWrap() {
  $("#editor").classList.toggle("wrapped", $("#editwrap").checked);
}

async function saveFile(id, check) {
  const path = route.query.path || "";
  const out = $("#editout");
  const course = courseCache[id] || { id };
  try {
    await api(
      `/api/courses/${encodeURIComponent(id)}/files?path=${encodeURIComponent(path)}`,
      { text: $("#editor").value },
      "PUT"
    );
    delete courseCache[id];
    toast("Saved " + path.slice(path.lastIndexOf("/") + 1));
    if (!check) {
      out.innerHTML = "";
      return;
    }
    if (check === "build") {
      const stop = busy(out, "Checking every file, then rendering the page…", ".editbar");
      const data = await api(`/api/courses/${encodeURIComponent(id)}/build`, {}).finally(stop);
      out.innerHTML = data.built
        ? `<p class="sub ok-text result">Built in ${stop.took()}: ${data.result.modules} modules · ${data.result.sections} sections · ${data.result.kb} KB. <a href="#/course/${encodeURIComponent(id)}">Back to the course</a>.</p>`
        : `<div class="problems"><b>Saved, but not built — ${data.problems.length} problem${data.problems.length === 1 ? "" : "s"}</b><ul>${problemList(course, data.problems)}</ul></div>`;
      return;
    }
    const stop = busy(out, "Checking every module, quiz and suggestion file…", ".editbar");
    const { problems } = await api(`/api/courses/${encodeURIComponent(id)}/check`, {}).finally(
      stop
    );
    out.innerHTML = problems.length
      ? `<div class="problems"><b>${problems.length} problem${problems.length === 1 ? "" : "s"}</b><ul>${problemList(course, problems)}</ul></div>`
      : `<p class="sub ok-text result">Consistent — <a href="#/course/${encodeURIComponent(id)}">build it from the course page</a>.</p>`;
  } catch (err) {
    out.innerHTML = `<div class="problems">${esc(err.message)}</div>`;
  }
}
