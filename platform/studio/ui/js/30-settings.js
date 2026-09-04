/* ---------- Studio settings & logs ---------- */

let logTimer = null;

async function viewSettingsPage() {
  let s;
  try {
    s = await api("/api/settings");
  } catch (err) {
    $("#view").innerHTML = `<div class="problems">${esc(err.message)}</div>`;
    return;
  }
  if (route.name !== "settings") return;
  const models = (s.models || [])
    .map(
      m =>
        `<label class="radio"><input type="radio" name="model" value="${esc(m.id)}" ${s.model === m.id ? "checked" : ""} onchange="saveStudioSettings()"> <b>${esc(m.name)}</b> <span class="sub" style="margin:0">— ${esc(m.note)}</span></label>`
    )
    .join("");
  $("#view").innerHTML = `
    <p class="crumb"><a href="#/">Courses</a> › Settings &amp; logs</p>
    <h2 class="big">Settings &amp; logs</h2>
    <p class="sub">What Studio uses for every generation and tutor call, and what it has been doing.</p>

    <div class="card">
      <p class="eyebrow">Model</p>
      <p class="sub" style="font-size:13.5px">The model Studio writes courses with and answers the tutor's questions through. If it is unavailable, Studio falls back to the platform default before giving up.</p>
      <div class="radios">${models}</div>
      <div id="settingsmsg"></div>
    </div>

    <div class="card">
      <p class="eyebrow">Reader profiles</p>
      <p class="sub" style="font-size:13.5px">Each profile has its own progress for every course. Studio shows, and a course opened from Studio syncs to, the profile chosen in the header. The default profile keeps its files where they always were; the others live in a folder of their own under <span class="mono">state/progress/</span>.</p>
      <div id="profilelist">${(STATE.profiles || ["default"]).map(n => `<div class="profilerow"><span class="name">${esc(n)}</span>${n === STATE.profile ? `<span class="pill on">reading as</span>` : `<button class="btn sm ghost" onclick="switchProfile('${esc(n)}')">Read as</button>`}${n === "default" ? "" : `<button class="btn sm ghost rm" title="Move this profile's progress to the trash" onclick="removeProfile('${esc(n)}')">×</button>`}</div>`).join("")}</div>
      <div class="actions" style="margin-top:12px"><input type="text" id="newprofile" placeholder="new profile name, e.g. alex" style="max-width:240px" autocomplete="off" onkeydown="if(event.key==='Enter'){event.preventDefault();addProfile()}"><button class="btn sm" onclick="addProfile()">Add and switch</button></div>
    </div>

    <div class="card">
      <p class="eyebrow">Claude Code</p>
      <p style="margin:0 0 6px">${s.claude.available ? `<span class="pill on">found</span> <span class="mono">${esc(s.claude.path)}</span>` : `<span class="pill off">not found on PATH</span> — generation and the tutor are disabled until it is installed and signed in.`}</p>
    </div>

    <div class="card">
      <p class="eyebrow">Platform settings</p>
      <p class="sub" style="font-size:13.5px">Every default the platform has - ports, the API endpoint, the model list, timeouts, generation counts, the page's study rules and layout - is in <span class="mono">${esc(s.paths.settings)}</span>. Per-machine overrides go in <span class="mono">.env</span> or the environment under these names: ${Object.entries(
        s.envKeys || {}
      )
        .map(([k, v]) => `<span class="mono" title="${esc(v)}">${esc(k)}</span>`)
        .join(
          " · "
        )}. A JSON overlay named by <span class="mono">SETTINGS_FILE</span> can override anything. Restart Studio after changing any of them.${s.paths.overlay ? ` Overlay in use: <span class="mono">${esc(s.paths.overlay)}</span>.` : ""}</p>
      <table class="paths">${(s.platform || []).map(r => `<tr><td>${esc(r.key)}</td><td class="mono">${esc(String(r.value))}</td><td class="sub" style="font-size:12px">${r.source === "settings.json" ? "" : esc(r.source)}</td></tr>`).join("")}</table>
    </div>

    <div class="card">
      <p class="eyebrow">Where things are</p>
      <table class="paths">${Object.entries(s.paths)
        .map(([k, v]) => `<tr><td>${esc(k)}</td><td class="mono">${esc(v || "—")}</td></tr>`)
        .join("")}</table>
    </div>

    <div class="card">
      <div class="editbar" style="margin-bottom:10px">
        <p class="eyebrow" style="margin:0">Log</p>
        <span class="spacer"></span>
        <select id="loglevel" onchange="loadLogs()" style="width:auto">
          ${["DEBUG", "INFO", "WARNING", "ERROR"].map(l => `<option ${l === "INFO" ? "selected" : ""}>${l}</option>`).join("")}
        </select>
        <input type="text" id="logq" placeholder="filter…" style="width:180px" oninput="loadLogs()">
        <label class="radio" style="margin:0"><input type="checkbox" id="logfollow" checked onchange="followLogs()"> follow</label>
        <button class="btn sm ghost" onclick="loadLogs()">Refresh</button>
        <button class="btn sm ghost" onclick="clearLogs()">Clear view</button>
      </div>
      <pre class="logbox" id="logbox">loading…</pre>
      <p class="sub" style="font-size:12px;margin:8px 0 0">The full file is <span class="mono">${esc(s.paths.log || "console only")}</span>, rotating at ${Math.round((s.logs.maxBytes || 0) / 100000) / 10} MB × ${s.logs.backups}. Every Claude call is one line: model, time taken, prompt and reply size, and the CLI's stderr when it fails.</p>
    </div>`;
  loadLogs();
  followLogs();
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
    const atBottom = box.scrollHeight - box.scrollTop - box.clientHeight < 40;
    box.innerHTML = lines.length
      ? lines
          .map(
            l =>
              `<div class="ll ${esc(l.level)}"><span class="lt">${esc(clock(l.t))}</span><span class="lv">${esc(l.level.slice(0, 4))}</span><span class="lm">${esc(l.msg)}</span></div>`
          )
          .join("")
      : `<div class="ll INFO"><span class="lm">Nothing yet at this level.</span></div>`;
    if (atBottom || ($("#logfollow") || {}).checked) box.scrollTop = box.scrollHeight;
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
    toast(err.message);
  }
}

/* ---------- the editor ---------- */

async function viewEdit() {
  const id = route.id,
    path = route.query.path || "";
  $("#view").innerHTML =
    `<p class="crumb"><a href="#/">Courses</a> › <a href="#/course/${encodeURIComponent(id)}">${esc(id)}</a> › ${esc(path)}</p><p class="sub">Loading…</p>`;
  let file;
  try {
    file = await api(
      `/api/courses/${encodeURIComponent(id)}/files?path=${encodeURIComponent(path)}`
    );
  } catch (err) {
    $("#view").innerHTML += `<div class="problems">${esc(err.message)}</div>`;
    return;
  }
  $("#view").innerHTML = `
    <p class="crumb"><a href="#/">Courses</a> › <a href="#/course/${encodeURIComponent(id)}?tab=files">${esc(id)}</a> › ${esc(path)}</p>
    <div class="editbar">
      <span class="path">${esc(path)}</span>
      <button class="btn sm" id="savebtn" onclick="saveFile('${id}', 'build')">Save, check and build</button>
      <button class="btn sm ghost" onclick="saveFile('${id}', true)">Save and check</button>
      <button class="btn sm ghost" onclick="saveFile('${id}')">Save only</button>
      <a class="btn sm ghost" href="#/course/${encodeURIComponent(id)}">Back to course</a>
    </div>
    <textarea class="editor" id="editor" spellcheck="false"></textarea>
    <div id="editout"></div>
    <p class="sub" style="font-size:12.5px;margin-top:10px">Ctrl+S saves, Ctrl+Shift+S saves and builds. A module's first line must be <span class="mono"># M07 — Title</span>; every <span class="mono">## </span> heading with content is one section, and the suggestion file for the module needs exactly that many entries.</p>`;
  const ta = $("#editor");
  ta.value = file.text;
  ta.addEventListener("keydown", e => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
      e.preventDefault();
      saveFile(id, e.shiftKey ? "build" : false);
    }
    if (e.key === "Tab") {
      e.preventDefault();
      const s = ta.selectionStart;
      ta.setRangeText("  ", s, ta.selectionEnd, "end");
    }
  });
  ta.focus();
}

async function saveFile(id, check) {
  const path = route.query.path || "";
  const out = $("#editout");
  try {
    await api(
      `/api/courses/${encodeURIComponent(id)}/files?path=${encodeURIComponent(path)}`,
      { text: $("#editor").value },
      "PUT"
    );
    toast("Saved " + path.slice(path.lastIndexOf("/") + 1));
    if (!check) {
      out.innerHTML = "";
      return;
    }
    if (check === "build") {
      const stop = busy(out, "Checking every file, then rendering the page…", ".editbar");
      const data = await api(`/api/courses/${encodeURIComponent(id)}/build`, {}).finally(stop);
      out.innerHTML = data.built
        ? `<p class="sub ok-text" style="margin:12px 0 0">Built in ${stop.took()}: ${data.result.modules} modules · ${data.result.sections} sections · ${data.result.kb} KB. <a href="#/course/${encodeURIComponent(id)}">Back to the course</a>.</p>`
        : `<div class="problems"><b>Saved, but not built — ${data.problems.length} problem${data.problems.length === 1 ? "" : "s"}</b><ul>${data.problems.map(p => `<li>${esc(p)}</li>`).join("")}</ul></div>`;
      return;
    }
    const stop = busy(out, "Checking every module, quiz and suggestion file…", ".editbar");
    const { problems } = await api(`/api/courses/${encodeURIComponent(id)}/check`, {}).finally(
      stop
    );
    out.innerHTML = problems.length
      ? `<div class="problems"><b>${problems.length} problem${problems.length === 1 ? "" : "s"}</b><ul>${problems.map(p => `<li>${esc(p)}</li>`).join("")}</ul></div>`
      : `<p class="sub ok-text" style="margin:12px 0 0">Consistent — <a href="#/course/${encodeURIComponent(id)}">build it from the course page</a>.</p>`;
  } catch (err) {
    out.innerHTML = `<div class="problems">${esc(err.message)}</div>`;
  }
}
