/* ============================ talking to Claude ============================ */
/* ---- talking to Claude ----
   Two routes, in order of preference:
     direct  — this page calls api.anthropic.com itself. Nothing to install, nothing to run.
               Only possible from the local copy of this file; a published page is not
               allowed to call other hosts.
     bridge  — the optional little Python program in tools/bridge/. Useful if you would rather
               use Claude Code than an API key.
*/
let bridgeOk = null,
  bridgeErr = "",
  bridgeChecking = false,
  studioOk = false;
function conn() {
  if (!STATE.bridge) STATE.bridge = connDefaults();
  return STATE.bridge;
}
/* An empty model in a saved state (or one this build no longer offers) means the default. */
function modelFor(b) {
  return PLATFORM.models.some(m => m.id === b.model) ? b.model : PLATFORM.defaultModel;
}
/* The reader's pick for the tutor, from the rail's menu or the Settings page. Only a model
   this build lists is kept; anything else leaves the current choice alone. */
function setTutorModel(id) {
  if (!PLATFORM.models.some(m => m.id === id)) return;
  conn().model = id;
  save();
  toast("Answers now come from " + tutorModelLabel());
}
function tutorModelLabel() {
  const id = modelFor(conn());
  const found = PLATFORM.models.find(m => m.id === id);
  return found ? found.label : id;
}
function isLocalFile() {
  return location.protocol === "file:";
}
/* Three routes, in order of preference:
     studio  — this page is served by Course Studio, which answers on the same origin
               through the Claude Code it already uses. Nothing to configure.
     bridge  — the small program in tools/bridge/, for a page opened off disk.
     direct  — an API key pasted into Settings; the page calls Anthropic itself.
   A saved key always wins: it is an explicit choice to pay per question. */
function connMode() {
  if (studioOk && !conn().key) return "studio";
  return conn().route === "bridge" && bridgeOk ? "bridge" : conn().key ? "direct" : "none";
}
async function checkStudio() {
  if (!STUDIO) return false;
  try {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), TUTOR.probeTimeoutMs);
    const r = await fetch(STUDIO.origin + "/api/state", { signal: ctrl.signal, cache: "no-store" });
    clearTimeout(t);
    const j = await r.json();
    studioOk = !!(j && j.claude && j.claude.available);
  } catch (e) {
    studioOk = false;
  }
  return studioOk;
}

async function callAnthropic(key, system, messages, model, maxTokens) {
  const body = {
    model: model || PLATFORM.defaultModel,
    max_tokens: maxTokens || TUTOR.maxTokens,
    messages: messages.slice(-TUTOR.history),
  };
  if (system) body.system = system;
  const r = await fetch(PLATFORM.apiUrl, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-api-key": key,
      "anthropic-version": PLATFORM.apiVersion,
      "anthropic-dangerous-direct-browser-access": "true",
    },
    body: JSON.stringify(body),
  });
  let j = null;
  try {
    j = await r.json();
  } catch (e) {}
  if (!r.ok) {
    const msg = (j && j.error && j.error.message) || "HTTP " + r.status;
    const friendly =
      {
        401: "Anthropic rejected the key: " + msg,
        403: "That key is not allowed to do this: " + msg,
        404: "That model is not available on this key.",
        429: "Rate limited, or the key is out of credit.",
        529: "Anthropic is overloaded right now — try again in a moment.",
      }[r.status] || "Anthropic error " + r.status + ": " + msg;
    const err = new Error(friendly);
    err.status = r.status;
    throw err;
  }
  return (
    (j.content || [])
      .filter(c => c.type === "text")
      .map(c => c.text)
      .join("") || "(empty reply)"
  );
}

async function verifyKey(key) {
  try {
    await callAnthropic(key, "", [{ role: "user", content: "hi" }], modelFor(conn()), 4);
    return { ok: true };
  } catch (e) {
    const net = /failed|network|load/i.test(e.message || "") && !e.status;
    return {
      ok: false,
      why: net
        ? isLocalFile()
          ? "The request could not leave the browser. Check your internet connection."
          : "A published page is not allowed to call Anthropic. Open " +
            CFG.localFile +
            " from your " +
            CFG.folderLabel +
            " folder instead."
        : e.message,
    };
  }
}

/* the bridge is optional now — only probed when it is the chosen route, or when there is no key */
async function checkBridge(quiet) {
  const b = conn();
  bridgeChecking = true;
  bridgeErr = "";
  if (!quiet) renderSidebar();
  if ((await checkStudio()) && !b.key) {
    // served by Studio: it answers itself
    bridgeOk = true;
    b.mode = "studio";
    bridgeChecking = false;
    save();
    redrawForConnection();
    return true;
  }
  if (b.key && b.route !== "bridge") {
    // direct mode: nothing to probe
    bridgeOk = true;
    b.mode = "direct";
    bridgeChecking = false;
    save();
    redrawForConnection();
    return true;
  }
  try {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), TUTOR.probeTimeoutMs);
    const r = await fetch(b.url.replace(/\/$/, "") + "/health", { signal: ctrl.signal });
    clearTimeout(t);
    const j = await r.json();
    b.echo = !!j.echo;
    b.cliSeen = !!j.cli;
    b.hasKey = !!j.has_key;
    b.keySource = j.key_source || "";
    b.keyHint = j.key_hint || "";
    bridgeOk = !!j.ok && j.ready !== false;
    b.mode = bridgeOk ? "bridge" : "none";
    if (bridgeOk) b.route = "bridge";
    if (!!j.ok && j.ready === false)
      bridgeErr = "The bridge is running but has no way to reach Claude yet.";
  } catch (e) {
    bridgeOk = false;
    b.mode = "none";
    bridgeErr = "Not connected yet.";
  }
  bridgeChecking = false;
  save();
  redrawForConnection();
  return bridgeOk;
}
/* The screens that say whether Claude is connected, redrawn once the answer is known. */
function redrawForConnection() {
  renderSidebar();
  if (route.view === "settings") viewSettings();
  if (route.view === "home") viewHome();
  if (route.view === "learner") viewLearner();
  if (route.view === "m" && route.step === 5) renderStep(byId(route.id), 5);
  if (route.view === "m" && railOpen()) renderRail();
}

async function askBridge(system, messages) {
  const b = conn();
  if (connMode() === "direct") {
    return callAnthropic(b.key, system, messages, modelFor(b), TUTOR.maxTokens);
  }
  if (connMode() === "studio") {
    const r = await fetch(STUDIO.origin + "/api/ask", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ model: modelFor(b), system, messages }),
    });
    const j = await r.json().catch(() => ({ error: "Studio sent something unreadable." }));
    if (!r.ok || j.error) throw new Error(j.error || "Studio error " + r.status);
    return j.text || "(empty reply)";
  }
  const r = await fetch(b.url.replace(/\/$/, "") + "/ask", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      key: "",
      model: modelFor(b),
      system,
      messages,
      max_tokens: TUTOR.maxTokens,
    }),
  });
  const j = await r.json().catch(() => ({ error: "The bridge sent something unreadable." }));
  if (!r.ok || j.error) throw new Error(j.error || "Bridge error " + r.status);
  if (j.notice) {
    toast(j.notice);
    save();
  }
  return j.text || "(empty reply)";
}

/* Repair text that was already stored after being decoded with the wrong code page:
   UTF-8 bytes read as Windows-1252 turn "—" into "â€”". Only runs when that signature
   is present and the bytes really do form valid UTF-8, so correct text is never touched. */
const CP1252_HIGH = {
  "€": 128,
  "‚": 130,
  ƒ: 131,
  "„": 132,
  "…": 133,
  "†": 134,
  "‡": 135,
  ˆ: 136,
  "‰": 137,
  Š: 138,
  "‹": 139,
  Œ: 140,
  Ž: 142,
  "‘": 145,
  "’": 146,
  "“": 147,
  "”": 148,
  "•": 149,
  "–": 150,
  "—": 151,
  "˜": 152,
  "™": 153,
  š: 154,
  "›": 155,
  œ: 156,
  ž: 158,
  Ÿ: 159,
};
function unmojibake(s) {
  if (!s || !/Ã.|â€|Â./.test(s)) return s;
  try {
    const bytes = new Uint8Array(s.length);
    for (let i = 0; i < s.length; i++) {
      const ch = s[i],
        code = ch.charCodeAt(0);
      if (code <= 0xff) bytes[i] = code;
      else if (CP1252_HIGH[ch] != null) bytes[i] = CP1252_HIGH[ch];
      else return s; // not representable — leave it alone
    }
    return new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  } catch (e) {
    return s;
  }
}

function mdLite(src) {
  let t = esc(unmojibake(src));
  t = t.replace(
    /```([\s\STATE]*?)```/g,
    (m, c) =>
      "<pre style='white-space:pre-wrap;background:var(--surface-3);padding:9px;border-radius:8px;font-size:12.5px'>" +
      c.trim() +
      "</pre>"
  );
  t = t.replace(/`([^`\n]+)`/g, "<code>$1</code>");
  t = t.replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>");
  t = t.replace(/(^|\n)#{1,4}\s*([^\n]+)/g, "$1<h4>$2</h4>");
  const lines = t.split("\n");
  let out = "",
    list = null;
  lines.forEach(l => {
    const ul = l.match(/^\s*[-*]\s+(.*)$/),
      ol = l.match(/^\s*(\d+)[.)]\s+(.*)$/);
    if (ul) {
      if (list !== "ul") {
        out += (list ? "</" + list + ">" : "") + "<ul>";
        list = "ul";
      }
      out += "<li>" + ul[1] + "</li>";
    } else if (ol) {
      if (list !== "ol") {
        out += (list ? "</" + list + ">" : "") + "<ol>";
        list = "ol";
      }
      out += "<li>" + ol[2] + "</li>";
    } else {
      if (list) {
        out += "</" + list + ">";
        list = null;
      }
      if (l.trim()) out += l.startsWith("<h4>") || l.startsWith("<pre") ? l : "<p>" + l + "</p>";
    }
  });
  if (list) out += "</" + list + ">";
  return out;
}
