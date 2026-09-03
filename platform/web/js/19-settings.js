
/* ---- settings: connect the page to Claude ---- */
function viewSettings() {
  const b = BR();
  const local = isLocalFile();
  const on = connMode() !== "none";
  const state = bridgeChecking ? "busy" : on ? "on" : "";
  let h = `<div class="wrap"><h2 class="big">Connect Claude</h2>
  <p class="sub" style="margin-bottom:22px">${connMode() === "studio" ? "This page is served by Course Studio, so questions go through it. Paste a key only if you would rather pay per question." : "Paste a key once. Nothing to install, nothing to keep running."}</p>

  <div class="card" style="margin-bottom:20px;border-color:${on ? "var(--ok)" : "var(--line)"};text-align:center;padding:26px 20px">
    <span class="dotstat ${state}" style="width:14px;height:14px;display:inline-block;margin-bottom:12px"></span>
    <div style="font-family:var(--serif);font-size:23px;font-weight:600;margin-bottom:6px">
      ${bridgeChecking ? "Checking…" : on ? (b.echo ? "Connected — test mode" : "Connected") : "Not connected"}</div>
    <p class="sub" style="max-width:460px;margin:0 auto 16px">${on
      ? (connMode() === "direct"
        ? "This page talks to Anthropic directly. Ask about anything you are reading."
        : connMode() === "studio"
          ? "Connected through Course Studio, using the Claude Code it is signed in to. Nothing to set up, no API charges."
          : "Connected through the local bridge" + (b.mode === "cli" ? " using Claude Code." : "."))
      : "Paste your Anthropic API key below and press Connect."}</p>
    ${on ? "" : `<div style="max-width:520px;margin:0 auto">
      <button class="btn primary" id="connectbtn" style="font-size:15px;padding:11px 22px" onclick="useBridge()">Connect with Claude Code</button>
      <p class="sub" style="font-size:12.5px;margin:10px 0 0">Included in your Pro/Max plan — no API charges. Start <code>tools\\bridge\\start-bridge.bat</code> first.</p>
      <div style="display:flex;align-items:center;gap:10px;margin:18px 0 12px"><span style="flex:1;height:1px;background:var(--line)"></span><span style="font-size:11.5px;color:var(--muted)">or pay per question</span><span style="flex:1;height:1px;background:var(--line)"></span></div>
      <div style="display:flex;gap:8px;flex-wrap:wrap">
        <input type="password" id="mainkey" placeholder="sk-ant-… (billed separately)" style="flex:1;min-width:230px" value="${esc(b.key || "")}">
        <button class="btn" onclick="connectClaude()">Use API key</button></div></div>`}
    ${on ? `<button class="btn" id="connectbtn" onclick="connectClaude()">Re-check</button>
      <button class="btn ghost" onclick="disconnect()">Disconnect</button>` : ""}
    <div id="connectlog" style="margin-top:16px;text-align:left"></div>
  </div>`;

  if (!local) {
    h += `<div class="card" style="margin-bottom:20px;border-color:var(--warm)">
      <p class="eyebrow" style="color:var(--warm)">You are on the published web version</p>
      <p style="color:var(--text-2);margin:0">A page served from claude.ai is not permitted to call other services — that restriction is what keeps published pages safe. Reading, quizzes and flashcards all work here; <b>asking questions needs the local copy</b>. Open <code>${esc(CFG.localFile)}</code> from your <b>${esc(CFG.folderLabel)}</b> folder. Use <b>Backup / restore</b> in the sidebar to carry progress across.</p></div>`;
  }

  h += `<div class="card" style="margin-bottom:20px;border-color:var(--warm)">
    <p class="eyebrow" style="color:var(--warm)">On a Pro or Max subscription?</p>
    <p style="color:var(--text-2);margin:0 0 10px">API usage is <b>billed separately</b> from a Claude subscription — a Max plan does not include API credits, so every question asked through a key here costs money on top of what you already pay.</p>
    <p style="color:var(--text-2);margin:0">Claude Code, on the other hand, <b>is</b> included in Pro and Max. If you have it installed, use the bridge route in the collapsed section below: questions then count against your subscription's usage instead of costing extra. Leave the key field empty if you go that way.</p>
  </div>

  <div class="card" style="margin-bottom:20px">
    <p class="eyebrow">Where to get a key</p>
    <div class="stepbox"><span class="n">1</span><div class="c">Go to <b>console.anthropic.com</b> → <b>API keys</b> → <b>Create key</b>.</div></div>
    <div class="stepbox"><span class="n">2</span><div class="c">Copy it (it starts with <code>sk-ant-</code>) and paste it above.</div></div>
    <div class="stepbox" style="border-bottom:0"><span class="n">3</span><div class="c">Press <b>Connect</b>. It sends one tiny test request, then remembers the key in this browser. Questions cost a fraction of a cent each — billed per use, separately from a Claude subscription.</div></div>
  </div>

  <div class="card" style="margin-bottom:20px">
    <p class="eyebrow">Settings</p>
    <div class="setrow"><span class="lab">Model<small>Which Claude answers your questions. The list comes from the platform's settings.</small></span>
      <select id="setmodel" onchange="saveSettings()" style="padding:10px 12px;border-radius:10px;border:1px solid var(--line-2);background:var(--surface);color:var(--text);font-family:inherit;font-size:14px">
        ${PLATFORM.models.map(m => `<option value="${esc(m.id)}" ${modelFor(b) === m.id ? "selected" : ""}>${esc(m.label)}</option>`).join("")}
      </select></div>
    <div class="setrow" style="border-bottom:0"><span class="lab">Your key<small>Kept in this browser only, sent only to Anthropic.</small></span>
      <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">
        <span style="font-family:var(--mono);font-size:12.5px">${b.key ? esc(b.key.slice(0, 14) + "…" + b.key.slice(-4)) : "none stored"}</span>
        ${b.key ? `<button class="btn sm" onclick="testDirect()">Test it</button>
                   <button class="btn sm ghost" onclick="disconnect()">Forget it</button>` : ""}
      </div></div>
    <div id="diagbox" style="margin-top:12px"></div>
  </div>

  <details class="card" style="margin-bottom:20px"><summary style="cursor:pointer;font-size:13px;color:var(--muted)">Alternative — use the local bridge instead (no API key, uses Claude Code)</summary>
    <div style="margin-top:14px">
      <p style="color:var(--text-2);margin:0 0 12px">If you have <b>Claude Code</b> installed and would rather not use an API key at all, the folder <code>tools\\bridge\\</code> holds a small Python program that routes questions through it. Start <code>start-bridge.bat</code> there, then press the button below. Everything works the same afterwards; the difference is only where the answers come from.</p>
      <div class="setrow"><span class="lab">Bridge address</span><input type="text" id="seturl" value="${esc(b.url)}"></div>
      <div style="display:flex;gap:9px;margin-top:14px;flex-wrap:wrap">
        <button class="btn" onclick="useBridge()">Use the bridge</button>
        ${b.route === "bridge" ? `<button class="btn ghost" onclick="useDirect()">Back to direct</button>` : ""}
      </div>
    </div>
  </details>

  <div class="card" style="margin-bottom:20px">
    <p class="eyebrow">Reading</p>
    <p class="sub" style="margin-bottom:6px">Kept in this browser only.</p>
    <div class="setrow"><span class="lab">Text size</span><div class="chips" style="margin:0">${[["s", "Smaller"], ["m", "Normal"], ["l", "Larger"], ["xl", "Largest"]].map(([v, l]) => `<button class="chip ${(UI().size || "m") === v ? "on" : ""}" onclick="setReading('size','${v}')">${l}</button>`).join("")}</div></div>
    <div class="setrow"><span class="lab">Line width<small>Narrow is easier to read; wide fits more.</small></span><div class="chips" style="margin:0">${[["narrow", "Narrow"], ["normal", "Normal"], ["wide", "Wide"]].map(([v, l]) => `<button class="chip ${(UI().width || "normal") === v ? "on" : ""}" onclick="setReading('width','${v}')">${l}</button>`).join("")}</div></div>
    <div class="setrow"><span class="lab">Font<small>A serif body suits long reading for some eyes.</small></span><div class="chips" style="margin:0">${[["sans", "Sans"], ["serif", "Serif"]].map(([v, l]) => `<button class="chip ${(UI().font || "sans") === v ? "on" : ""}" onclick="setReading('font','${v}')">${l}</button>`).join("")}</div></div>
    <div class="setrow" style="border-bottom:0"><span class="lab">Motion</span><label style="display:flex;gap:8px;align-items:center;font-size:14px;cursor:pointer"><input type="checkbox" ${UI().nomotion ? "checked" : ""} onchange="setReading('nomotion',this.checked)"> Reduce animation</label></div>
  </div>

  <div class="card" style="margin-bottom:20px">
    <p class="eyebrow">Chat panel</p>
    <p class="sub" style="margin-bottom:6px">Where the tutor sits while you read. Kept in this browser only. You can also drag the panel's edge to resize it, and double-click the edge to reset.</p>
    <div class="setrow"><span class="lab">Position</span><div class="chips" style="margin:0">${DOCKS.map(([p, ico, tip]) => `<button class="chip ${railPos() === p ? "on" : ""}" onclick="setRailPos('${p}')">${ico} ${tip.replace("Dock ", "").replace("along the ", "")}</button>`).join("")}</div></div>
    <div class="setrow" style="border-bottom:0"><span class="lab">Size<small>Width when docked at a side, height when docked at the bottom.</small></span>
      <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap"><span class="sub">${railPos() === "bottom" ? railHeight() + "px tall" : railWidth() + "px wide"}</span>
      <button class="btn sm" onclick="if(!S.ui)S.ui={};S.ui.railW=LAYOUT.railDefault;S.ui.railH=LAYOUT.railHeightDefault;save();applyRail();viewSettings()">Reset</button></div></div>
  </div>

  <div class="card">
    <p class="eyebrow">Why the key sits in the browser</p>
    <p style="color:var(--text-2);margin:0 0 10px">Anthropic allows a page to call the API directly, as long as it says it means to. That is what this does — so there is no proxy, no Python and no window to leave open. The cost is that your key lives in this browser's storage for this file.</p>
    <p style="color:var(--text-2);margin:0">That is fine here because this page is a file on your own computer that only you open. It would <b>not</b> be fine in a page you put on the internet — anyone visiting could read the key. So do not host this file publicly with a key saved in it, and press <b>Forget it</b> on a shared machine.</p>
  </div></div>`;
  $("#view").innerHTML = h;
}

async function connectClaude() {
  const btn = document.getElementById("connectbtn"), log = document.getElementById("connectlog");
  const field = document.getElementById("mainkey");
  const b = BR();
  const key = ((field && field.value.trim()) || b.key || "").trim();
  const show = html => { const l = document.getElementById("connectlog") || log; if (l) l.innerHTML = html; };

  if (!key) {
    // no key typed — see whether the optional bridge is running instead
    show(`<div class="hint"><span class="i">…</span>No key given, checking for the local bridge.</div>`);
    b.route = "bridge";
    const ok = await checkBridge(true);
    if (!ok) { b.route = "direct"; save(); }
    show(ok
      ? `<div class="hint" style="background:var(--ok-soft);color:var(--ok)"><span class="i">✓</span>Connected through the local bridge.</div>`
      : `<div class="hint" style="background:var(--warm-soft);color:var(--warm)"><span class="i">!</span>Paste an API key above, or start the bridge if you would rather use Claude Code.</div>`);
    return;
  }

  if (btn) { btn.disabled = true; btn.textContent = "Checking…"; }
  show(`<div class="hint"><span class="i">…</span>Sending one tiny request to check the key.</div>`);
  const res = await verifyKey(key);
  if (res.ok) {
    b.key = key; b.route = "direct"; b.mode = "direct"; save();
    bridgeOk = true;
    renderSidebar(); viewSettings();
    show(`<div class="hint" style="background:var(--ok-soft);color:var(--ok)"><span class="i">✓</span>
      <div><b>Connected.</b> The key is saved in this browser — you will not be asked again. Go and read; select any sentence to ask about it.</div></div>`);
    toast("Connected to Claude");
  } else {
    if (btn) { btn.disabled = false; btn.textContent = "Connect"; }
    show(`<div class="hint" style="background:var(--bad-soft);color:var(--bad)"><span class="i">✕</span>
      <div><b>Did not work.</b> ${esc(res.why || "")}</div></div>`);
  }
}
async function testDirect() {
  const box = document.getElementById("diagbox");
  if (box) box.innerHTML = `<div class="hint"><span class="i">…</span>Checking.</div>`;
  const res = await verifyKey(BR().key);
  if (box) box.innerHTML = res.ok
    ? `<div class="hint" style="background:var(--ok-soft);color:var(--ok)"><span class="i">✓</span>The key works.</div>`
    : `<div class="hint" style="background:var(--bad-soft);color:var(--bad)"><span class="i">✕</span>${esc(res.why || "")}</div>`;
}
function disconnect() {
  BR().key = ""; BR().mode = "none"; bridgeOk = false; save();
  renderSidebar(); viewSettings(); toast("Key removed from this browser");
}
function useDirect() { BR().route = "direct"; save(); checkBridge(); }
async function useBridge() {
  const u = document.getElementById("seturl");
  if (u) BR().url = u.value.trim().replace(/\/$/, "");
  BR().route = "bridge"; save();
  const log = () => document.getElementById("connectlog");
  const l0 = log(); if (l0) l0.innerHTML = `<div class="hint"><span class="i">…</span>Looking for the bridge, then for Claude Code.</div>`;
  const up = await checkBridge(true);
  if (!up) {
    BR().route = "direct"; save(); renderSidebar(); viewSettings();
    const l = log(); if (l) l.innerHTML = `<div class="hint" style="background:var(--bad-soft);color:var(--bad)"><span class="i">✕</span>
      <div>The bridge is not running. Double-click <b>start-bridge.bat</b> in <b>tools\\bridge</b>, leave that window open, then press this again.</div></div>`;
    return;
  }
  try {
    const j = await bridgePost("/connect", {});
    await checkBridge(true);
    const l = log();
    if (l) l.innerHTML = j.ok
      ? `<div class="hint" style="background:var(--ok-soft);color:var(--ok)"><span class="i">✓</span>
         <div><b>Connected — ${esc(j.source || "")}.</b> ${esc(j.note || "")}</div></div>`
      : `<div class="hint" style="background:var(--warm-soft);color:var(--warm)"><span class="i">!</span>
         <div><b>The bridge is running, but Claude Code did not answer.</b> ${j.cli
           ? "It is installed — run <code>claude</code> once in a terminal to sign in, then press this again."
           : "It does not appear to be installed. Install Claude Code and sign in, or use an API key instead."}</div></div>`;
    if (j.ok) toast("Connected — no API charges");
  } catch (e) {
    const l = log(); if (l) l.innerHTML = `<div class="hint" style="background:var(--bad-soft);color:var(--bad)"><span class="i">✕</span>${esc(e.message || "Could not reach the bridge")}</div>`;
  }
  renderSidebar();
}
async function bridgePost(path, payload) {
  const r = await fetch(BR().url.replace(/\/$/, "") + path, {
    method: "POST", headers: { "content-type": "application/json" },
    body: JSON.stringify(payload || {})
  });
  return r.json();
}
function saveSettings() {
  const m = document.getElementById("setmodel");
  if (m) BR().model = m.value;
  const u = document.getElementById("seturl");
  if (u) BR().url = u.value.trim().replace(/\/$/, "");
  save(); toast("Saved");
}

/* ---- reading preferences: device-local, applied as classes on <body> ---- */
function UI() { if (!S.ui) S.ui = {}; return S.ui; }
function setReading(k, v) { UI()[k] = v; save(); applyReading(); if (route.v === "settings") viewSettings(); }
function applyReading() {
  const u = UI(), b = document.body;
  ["sz-s", "sz-l", "sz-xl", "w-narrow", "w-wide", "font-serif", "nomotion"].forEach(c => b.classList.remove(c));
  if (u.size && u.size !== "m") b.classList.add("sz-" + u.size);
  if (u.width && u.width !== "normal") b.classList.add("w-" + u.width);
  if (u.font === "serif") b.classList.add("font-serif");
  if (u.nomotion) b.classList.add("nomotion");
}
