/* ---- settings: how the tutor is connected, and how the page reads ---- */
function viewSettings() {
  const b = conn();
  const local = isLocalFile();
  const on = connMode() !== "none";
  const state = bridgeChecking ? "busy" : on ? "on" : "";
  // Served by Studio the tutor is already wired up, so none of the key-and-bridge material
  // belongs on the page: it would be telling the reader to solve a problem they do not have.
  const viaStudio = connMode() === "studio";
  const status = bridgeChecking
    ? "Checking…"
    : on
      ? b.echo
        ? "Connected — test mode"
        : "Connected"
      : "Not connected";
  const direct = directFor();
  const how = on
    ? connMode() === "direct"
      ? "This page talks to " +
        direct.label +
        " directly with the key you saved. Ask about anything you are reading."
      : viaStudio
        ? "Answers come through Course Studio, using whatever it is signed in to. Nothing to set up here, and nothing extra to pay."
        : "Answers come through the local bridge" +
          (b.mode === "cli" ? ", using the tool it found on this machine." : ".")
    : "The tutor cannot answer yet. Connect it below.";

  let h = `<div class="wrap"><h2 class="big">Settings</h2>
  <p class="lede">How the tutor is connected, how the page reads, and what happens to your progress.</p>

  <div class="card centered connectcard ${on ? "ok" : ""}">
    <span class="dotstat big ${state}"></span>
    <div class="h-serif">${status}</div>
    <p class="sub narrow gap-bottom">${how}</p>
    ${
      on
        ? viaStudio
          ? `<div class="rowline center wrapped"><button class="btn" id="connectbtn" onclick="connectTutor()">Re-check</button></div>`
          : `<div class="rowline center wrapped"><button class="btn" id="connectbtn" onclick="connectTutor()">Re-check</button>
             <button class="btn danger" onclick="askDisconnect()">Disconnect</button></div>`
        : `<div class="narrow">
      <button class="btn primary" id="connectbtn" onclick="useBridge()">Connect through the local bridge</button>
      <p class="sub gap-top">Uses a command-line tool you are already signed in to — nothing billed per question. Start <span class="mono">tools\\bridge\\start-bridge.bat</span> first.</p>
      <div class="orline"><span></span><span class="sub">or pay per question</span><span></span></div>
      <div class="rowline wrapped">${keyField()}
        <button class="btn" onclick="connectTutor()">Use a key</button></div></div>`
    }
    <div id="connectlog" class="gap-top lefted"></div>
  </div>`;

  if (!local && !viaStudio) {
    h += `<div class="card warmcard gap-bottom">
      <h3 class="eyebrow warnnote">You are on the published web version</h3>
      <p class="lede">A page served from the web is not permitted to call other services — that restriction is what keeps published pages safe. Reading, quizzes and flashcards all work here; <b>asking questions needs the local copy</b>. Open <span class="mono">${esc(CFG.localFile)}</span> from your <b>${esc(CFG.folderLabel)}</b> folder. Use <b>Backup &amp; restore</b> below to carry progress across.</p></div>`;
  }

  // The whole cost-and-keys story is only useful to someone who has to solve it themselves.
  if (!viaStudio) {
    h += `<div class="card warmcard gap-bottom">
    <h3 class="eyebrow warnnote">Already paying for a subscription?</h3>
    <p class="lede">API usage is <b>billed separately</b> from a chat subscription — a paid plan does not usually include API credits, so every question asked through a key here costs money on top of what you already pay.</p>
    <p class="lede">A command-line tool you are signed in to often <b>is</b> included. If you have one, use the bridge: questions then count against the subscription you already have instead of costing extra. Leave the key field empty if you go that way.</p>
  </div>

  <div class="card gap-bottom">
    <h3 class="eyebrow">Where to get a key</h3>
    <div class="stepbox"><span class="n">1</span><div class="c">Open your provider's console and create an API key.</div></div>
    <div class="stepbox"><span class="n">2</span><div class="c">Copy it and paste it above, against the provider it belongs to.</div></div>
    <div class="stepbox last"><span class="n">3</span><div class="c">Press <b>Connect</b>. It sends one tiny test request, then remembers the key in this browser. Questions cost a fraction of a cent each — billed per use.</div></div>
  </div>`;
  }

  h += `<div class="card gap-bottom">
    <h3 class="eyebrow">The tutor</h3>
    <div class="setrow"><span class="lab">Model<small>Which model answers your questions. The same picker sits under the chat box.</small></span>
      <select id="setmodel" data-model-pick aria-label="Which model answers" onchange="setTutorModel(this.value)">
        ${PLATFORM.models.map(m => `<option value="${esc(m.id)}" ${modelFor(b) === m.id ? "selected" : ""}>${esc(m.label)}</option>`).join("")}
      </select></div>
    ${
      viaStudio
        ? `<div class="setrow last"><span class="lab">Connection<small>Studio is serving this page, so questions go through it and cost nothing extra.</small></span>
             <span class="sub">through Course Studio</span></div>`
        : keyRows()
    }
    <div id="diagbox" class="gap-top"></div>
  </div>

  ${
    viaStudio
      ? ""
      : `<details class="card gap-bottom"><summary>Alternative — use the local bridge instead (no key)</summary>
    <div class="gap-top">
      <p class="lede">If a command-line tool on this machine is already signed in and you would rather not use a key at all, the folder <span class="mono">tools\\bridge\\</span> holds a small Python program that routes questions through it. Start <span class="mono">start-bridge.bat</span> there, then press the button below. Everything works the same afterwards; the difference is only where the answers come from.</p>
      <div class="setrow"><span class="lab"><label for="seturl">Bridge address</label></span><input type="text" id="seturl" value="${esc(b.url)}"></div>
      <div class="rowline wrapped gap-top">
        <button class="btn" onclick="useBridge()">Use the bridge</button>
        ${b.route === "bridge" ? `<button class="btn" onclick="useDirect()">Back to direct</button>` : ""}
      </div>
    </div>
  </details>`
  }

  <div class="card gap-bottom">
    <h3 class="eyebrow">${esc((CFG.anchor || {}).label || "Your own case")}</h3>
    <p class="sub gap-bottom" title="${esc(help("anchor"))}">${esc((CFG.anchor || {}).prompt || "")}</p>
    <label class="visually-hidden" for="bizin">${esc((CFG.anchor || {}).label || "Your own case")}</label>
    <input type="text" id="bizin" value="${esc(STATE.biz || "")}" placeholder="${esc((CFG.anchor || {}).placeholder || "")}" onchange="STATE.biz=this.value.trim();save();toast('Saved')">
  </div>

  <div class="card gap-bottom">
    <h3 class="eyebrow">Reading</h3>
    <p class="sub gap-bottom">Kept in this browser only.</p>
    <div class="setrow"><span class="lab">Text size</span><div class="chips">${[
      ["s", "Smaller"],
      ["m", "Normal"],
      ["l", "Larger"],
      ["xl", "Largest"],
    ]
      .map(
        ([v, l]) =>
          `<button class="chip ${(uiPrefs().size || "m") === v ? "on" : ""}" aria-pressed="${(uiPrefs().size || "m") === v}" onclick="setReading('size','${v}')">${l}</button>`
      )
      .join("")}</div></div>
    <div class="setrow"><span class="lab">Line width<small>Narrow is easier to read; wide fits more.</small></span><div class="chips">${[
      ["narrow", "Narrow"],
      ["normal", "Normal"],
      ["wide", "Wide"],
    ]
      .map(
        ([v, l]) =>
          `<button class="chip ${(uiPrefs().width || "normal") === v ? "on" : ""}" aria-pressed="${(uiPrefs().width || "normal") === v}" onclick="setReading('width','${v}')">${l}</button>`
      )
      .join("")}</div></div>
    <div class="setrow"><span class="lab">Font<small>A serif body suits long reading for some eyes.</small></span><div class="chips">${[
      ["sans", "Sans"],
      ["serif", "Serif"],
    ]
      .map(
        ([v, l]) =>
          `<button class="chip ${(uiPrefs().font || "sans") === v ? "on" : ""}" aria-pressed="${(uiPrefs().font || "sans") === v}" onclick="setReading('font','${v}')">${l}</button>`
      )
      .join("")}</div></div>
    <div class="setrow last"><span class="lab">Motion</span><label class="radio"><input type="checkbox" ${uiPrefs().nomotion ? "checked" : ""} onchange="setReading('nomotion',this.checked)"> Reduce animation</label></div>
  </div>

  ${audioSettingsCard()}

  <div class="card gap-bottom">
    <h3 class="eyebrow">Chat panel</h3>
    <p class="sub gap-bottom">Where the tutor sits while you read. Kept in this browser only. You can also drag the panel's edge to resize it, and double-click the edge to reset.</p>
    <div class="setrow"><span class="lab">Position</span><div class="chips">${DOCKS.map(([p, _g, tip]) => `<button class="chip ${railPos() === p ? "on" : ""}" aria-pressed="${railPos() === p}" onclick="setRailPos('${p}')">${tip.replace("Dock ", "").replace("along the ", "")}</button>`).join("")}</div></div>
    <div class="setrow last"><span class="lab">Size<small>Width when docked at a side, height when docked at the bottom.</small></span>
      <div class="rowline wrapped"><span class="sub">${railPos() === "bottom" ? railHeight() + "px tall" : railWidth() + "px wide"}</span>
      <button class="btn sm" onclick="resetRailSize()">Reset</button></div></div>
  </div>

  <div class="card gap-bottom">
    <h3 class="eyebrow">Backup &amp; restore</h3>
    <p class="sub gap-bottom">${STUDIO ? "Progress is also kept on the platform while this page is served by Studio. A backup is still the way to move it to a page opened off disk." : "Progress lives in this browser only. Keep a copy, or move it to another machine."}</p>
    <button class="btn" onclick="openData()">Open backup &amp; restore</button>
  </div>

  ${
    viaStudio
      ? ""
      : `<div class="card">
    <h3 class="eyebrow">Why the key sits in the browser</h3>
    <p class="lede">A provider that allows a page to call its API directly is called directly — so there is no proxy, no Python and no window to leave open. The cost is that your key lives in this browser's storage for this file.</p>
    <p class="lede">That is fine here because this page is a file on your own computer that only you open. It would <b>not</b> be fine in a page you put on the internet — anyone visiting could read the key. So do not host this file publicly with a key saved in it, and press <b>Forget it</b> on a shared machine.</p>
  </div>`
  }</div>`;
  $("#view").innerHTML = h;
}

/* Which provider a key is being typed for: the one that reaches the chosen model, or the
   only one this page can call. With one provider there is nothing to pick. */
function keyProvider() {
  const forModel = providerForModel(modelFor(conn()));
  return forModel || directProviders()[0] || null;
}

/* The key field on the connect card, labelled with the provider it belongs to. */
function keyField() {
  const provider = keyProvider();
  if (!provider) return `<span class="sub grow">This page cannot call a provider directly.</span>`;
  const label = provider.label + " API key";
  return `<label class="visually-hidden" for="mainkey">${esc(label)}</label>
        <input type="password" id="mainkey" class="grow" placeholder="${esc(label)} (billed per question)" value="${esc(keyFor(provider.name))}">`;
}

/* One row per provider this page can call: what is stored, and what to do about it. A
   reader may hold more than one key, so this is a list rather than a field. */
function keyRows() {
  const providers = directProviders();
  if (!providers.length)
    return `<div class="setrow last"><span class="lab">Your key<small>This page cannot call a provider directly.</small></span>
      <span class="sub">use the bridge, or open this course from Studio</span></div>`;
  return providers
    .map((p, i) => {
      const key = keyFor(p.name);
      const shown = key ? esc(key.slice(0, 14) + "…" + key.slice(-4)) : "none stored";
      const buttons = key
        ? `<button class="btn sm" onclick="testDirect('${esc(p.name)}')">Test it</button>
           <button class="btn sm danger" onclick="askDisconnect('${esc(p.name)}')">Forget it</button>`
        : "";
      return `<div class="setrow ${i === providers.length - 1 ? "last" : ""}"><span class="lab">${esc(p.label)} key<small>Kept in this browser only, sent only to ${esc(p.label)}.</small></span>
      <div class="rowline wrapped"><span class="mono">${shown}</span>${buttons}</div></div>`;
    })
    .join("");
}

async function connectTutor() {
  const btn = document.getElementById("connectbtn"),
    log = document.getElementById("connectlog");
  const field = document.getElementById("mainkey");
  const b = conn();
  const provider = keyProvider();
  const key = ((field && field.value.trim()) || (provider && keyFor(provider.name)) || "").trim();
  const show = html => {
    const l = document.getElementById("connectlog") || log;
    if (l) l.innerHTML = html;
  };

  if (!key) {
    // no key typed — see whether the optional bridge is running instead
    show(
      `<div class="hint"><span class="i">…</span>No key given, checking for the local bridge.</div>`
    );
    b.route = "bridge";
    const ok = await checkBridge(true);
    if (!ok) {
      b.route = "direct";
      save();
    }
    show(
      ok
        ? `<div class="hint good"><span class="i">✓</span>Connected through the local bridge.</div>`
        : `<div class="hint warn"><span class="i">!</span>Paste a key above, or start the bridge if you would rather use a tool you are already signed in to.</div>`
    );
    return;
  }

  if (btn) {
    btn.disabled = true;
    btn.textContent = "Checking…";
  }
  show(
    `<div class="hint"><span class="i">…</span>Sending one tiny request to check the key.</div>`
  );
  const res = await verifyKey(key, provider && provider.name);
  if (res.ok) {
    setKeyFor(provider.name, key);
    b.route = "direct";
    b.mode = "direct";
    save();
    bridgeOk = true;
    renderSidebar();
    viewSettings();
    show(`<div class="hint good"><span class="i">✓</span>
      <div><b>Connected.</b> The key is saved in this browser — you will not be asked again. Go and read; select any sentence to ask about it.</div></div>`);
    toast("The tutor is connected");
  } else {
    if (btn) {
      btn.disabled = false;
      btn.textContent = "Connect";
    }
    show(`<div class="hint bad"><span class="i">✕</span>
      <div><b>Did not work.</b> ${esc(res.problem || "")}</div></div>`);
  }
}
async function testDirect(name) {
  const box = document.getElementById("diagbox");
  if (box) box.innerHTML = `<div class="hint"><span class="i">…</span>Checking.</div>`;
  const res = await verifyKey(keyFor(name), name);
  if (box)
    box.innerHTML = res.ok
      ? `<div class="hint good"><span class="i">✓</span>The key works.</div>`
      : `<div class="hint bad"><span class="i">✕</span>${esc(res.problem || "")}</div>`;
}
/* Forgetting a key means pasting it again from the provider's console. It asks. */
function askDisconnect(name) {
  const provider = providerByName(name);
  confirmModal(
    provider ? "Forget the " + provider.label + " key?" : "Disconnect the tutor?",
    "The key stored in this browser is erased. Reading, quizzes and flashcards keep working; nothing else is touched.",
    "Forget it",
    () => disconnect(name),
    true
  );
}
function resetRailSize() {
  if (!STATE.ui) STATE.ui = {};
  STATE.ui.railW = LAYOUT.railDefault;
  STATE.ui.railH = LAYOUT.railHeightDefault;
  save();
  applyRail();
  viewSettings();
}
function disconnect(name) {
  if (name) setKeyFor(name, "");
  else conn().keys = {};
  conn().mode = "none";
  bridgeOk = false;
  save();
  renderSidebar();
  viewSettings();
  toast("Key removed from this browser");
}
function useDirect() {
  conn().route = "direct";
  save();
  checkBridge();
}
async function useBridge() {
  const u = document.getElementById("seturl");
  if (u) conn().url = u.value.trim().replace(/\/$/, "");
  conn().route = "bridge";
  save();
  const log = () => document.getElementById("connectlog");
  const l0 = log();
  if (l0)
    l0.innerHTML = `<div class="hint"><span class="i">…</span>Looking for the bridge, then for a tool it can use.</div>`;
  const up = await checkBridge(true);
  if (!up) {
    conn().route = "direct";
    save();
    renderSidebar();
    viewSettings();
    const l = log();
    if (l)
      l.innerHTML = `<div class="hint bad"><span class="i">✕</span>
      <div>The bridge is not running. Double-click <b>start-bridge.bat</b> in <b>tools\\bridge</b>, leave that window open, then press this again.</div></div>`;
    return;
  }
  try {
    const j = await bridgePost("/connect", {});
    await checkBridge(true);
    const l = log();
    if (l)
      l.innerHTML = j.ok
        ? `<div class="hint good"><span class="i">✓</span>
         <div><b>Connected — ${esc(j.source || "")}.</b> ${esc(j.note || "")}</div></div>`
        : `<div class="hint warn"><span class="i">!</span>
         <div><b>The bridge is running, but nothing answered.</b> ${
           j.cli
             ? "A command-line tool is installed — sign in to it once in a terminal, then press this again."
             : "No command-line tool was found. Install one and sign in, or use an API key instead."
         }</div></div>`;
    if (j.ok) toast("Connected — no API charges");
  } catch (e) {
    const l = log();
    if (l)
      l.innerHTML = `<div class="hint bad"><span class="i">✕</span>${esc(e.message || "Could not reach the bridge")}</div>`;
  }
  renderSidebar();
}
async function bridgePost(path, payload) {
  const r = await fetch(conn().url.replace(/\/$/, "") + path, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload || {}),
  });
  return r.json();
}
/* ---- reading preferences: device-local, applied as classes on <body> ---- */
function uiPrefs() {
  if (!STATE.ui) STATE.ui = {};
  return STATE.ui;
}
function setReading(k, v) {
  uiPrefs()[k] = v;
  save();
  applyReading();
  if (route.view === "settings") viewSettings();
}
function applyReading() {
  const u = uiPrefs(),
    b = document.body;
  ["sz-s", "sz-l", "sz-xl", "w-narrow", "w-wide", "font-serif", "nomotion"].forEach(c =>
    b.classList.remove(c)
  );
  if (u.size && u.size !== "m") b.classList.add("sz-" + u.size);
  if (u.width && u.width !== "normal") b.classList.add("w-" + u.width);
  if (u.font === "serif") b.classList.add("font-serif");
  if (u.nomotion) b.classList.add("nomotion");
}
