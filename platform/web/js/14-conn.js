/* ============================ reaching the tutor ============================ */
/* ---- which way the question goes ----
   Three routes, and the page picks rather than asking:
     studio  — this page is served by Course Studio, which answers on its own origin using
               whatever provider it is configured with. Nothing for the reader to set up.
     bridge  — the small program in tools/bridge/, for a page opened off disk.
     direct  — a key the reader pasted into Settings; the page calls that provider itself
               (the wire formats are in 14b-wire.js). Only possible from a local copy of
               this file: a published page is not allowed to call other hosts.

   A saved key wins over Studio, because pasting one is an explicit choice to pay per
   question. Keys are per provider and never leave the browser.
*/
let bridgeOk = null,
  bridgeErr = "",
  bridgeChecking = false,
  studioOk = false;
function conn() {
  if (!STATE.bridge) STATE.bridge = connDefaults();
  const b = STATE.bridge;
  if (!b.keys || typeof b.keys !== "object") b.keys = {};
  return b;
}
/* The key the reader stored for one provider. */
function keyFor(name) {
  return (conn().keys[name] || "").trim();
}
function setKeyFor(name, key) {
  const keys = conn().keys;
  if (key) keys[name] = key;
  else delete keys[name];
}
/* The provider the reader's chosen model would be reached through, when this page can call
   it directly, and the key they have for it. */
function directFor(model) {
  const provider = providerForModel(model || modelFor(conn()));
  return provider && keyFor(provider.name) ? provider : null;
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
  if (typeof syncModelPickers === "function") syncModelPickers();
  toast("Answers now come from " + tutorModelLabel());
}
function tutorModelLabel() {
  const id = modelFor(conn());
  const found = PLATFORM.models.find(m => m.id === id);
  return found ? found.label : id;
}
/* The model list Studio reports replaces the one this page was built with, in place, so a
   model added on Studio's settings page is offered here without a rebuild. Each model keeps
   the provider that reaches it, which is what lets a direct call pick the right wire format.
   A saved pick that the new list no longer has falls back to the default through modelFor(). */
function adoptStudioModels(llm) {
  const list = Array.isArray(llm.models) ? llm.models.filter(m => m && m.apiId) : [];
  if (!list.length) return;
  PLATFORM.models.splice(
    0,
    PLATFORM.models.length,
    ...list.map(m => ({ id: m.apiId, label: m.name || m.apiId, provider: m.provider || "" }))
  );
  if (llm.defaultModel) PLATFORM.defaultModel = llm.defaultModel;
  if (typeof syncModelPickers === "function") syncModelPickers();
}
function isLocalFile() {
  return location.protocol === "file:";
}
/* Which route is live right now. A key wins over Studio - pasting one is an explicit choice
   to pay per question - but only a key that can actually reach the chosen model: a stored
   key for one provider must not turn off a Studio that reaches the model through another. */
function connMode() {
  if (studioOk && !directFor()) return "studio";
  if (conn().route === "bridge" && bridgeOk) return "bridge";
  return directFor() ? "direct" : "none";
}
async function checkStudio() {
  if (!STUDIO) return false;
  try {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), TUTOR.probeTimeoutMs);
    const r = await fetch(STUDIO.origin + "/api/state", { signal: ctrl.signal, cache: "no-store" });
    clearTimeout(t);
    const j = await r.json();
    // `llm` is the block; `claude` is what it was called before providers had names.
    const llm = (j && (j.llm || j.claude)) || null;
    studioOk = !!(llm && llm.available);
    if (llm) adoptStudioModels(llm);
  } catch (e) {
    studioOk = false;
  }
  return studioOk;
}

/* ---- what went wrong ----
   All three routes report trouble the same way: an Error carrying `why`, one of "quota",
   "auth", "model", "transient", "timeout" or "unknown". Studio and the bridge send it in the
   error body (coursekit/failures.py names it); the direct route reads it off the HTTP status
   here. The page needs it for one decision - whether trying the same thing again is worth
   offering, or whether the reader has to go and fix something first. */
const TROUBLE_BY_STATUS = {
  401: "auth",
  403: "auth",
  404: "model",
  429: "quota",
  500: "transient",
  502: "transient",
  503: "transient",
  504: "transient",
  529: "transient",
};
function troubleFromStatus(status) {
  return TROUBLE_BY_STATUS[status] || "unknown";
}
function troubleOf(err) {
  return (err && err.why) || "unknown";
}
/* Settings is where a key, a model and the bridge address live, so it is the answer to a
   rejected key, a refused model and a puzzle - not to an account that is simply out until
   three o'clock, which needs nothing but the clock. */
function worthCheckingSettings(why) {
  return why === "auth" || why === "model" || why === "unknown";
}

/* One call the page makes itself. Which provider, and therefore which wire format, comes
   from the model - the reader picks a model, never a protocol. */
async function callDirect(system, messages, model, maxTokens, provider, key) {
  const chosen = provider || providerForModel(model);
  if (!chosen) {
    const err = new Error("There is no way to reach that model from this page.");
    err.why = "model";
    throw err;
  }
  const wire = WIRE[chosen.kind];
  const stored = key || keyFor(chosen.name);
  const req = {
    model: model || PLATFORM.defaultModel,
    maxTokens: maxTokens || TUTOR.maxTokens,
    maxTokensField: chosen.maxTokensField,
    system,
    messages: messages.slice(-TUTOR.history),
  };
  const r = await fetch(wire.url(chosen, req), {
    method: "POST",
    headers: wire.headers(chosen, stored),
    body: JSON.stringify(wire.body(req)),
  });
  let j = null;
  try {
    j = await r.json();
  } catch (e) {}
  if (!r.ok) throw directError(chosen, r.status, wire.problem(j));
  return wire.reply(j) || "(empty reply)";
}

/* What a refused direct call says. The status decides the kind, exactly as it does on the
   Python side; the provider is named because the reader may hold more than one key. */
function directError(provider, status, said) {
  const detail = said || "HTTP " + status;
  const friendly =
    {
      401: provider.label + " rejected the key: " + detail,
      403: "That key is not allowed to do this: " + detail,
      404: "That model is not available on this key.",
      429: "Rate limited, or the key is out of credit.",
      529: provider.label + " is overloaded right now — try again in a moment.",
    }[status] || provider.label + " error " + status + ": " + detail;
  const err = new Error(friendly);
  err.status = status;
  err.why = troubleFromStatus(status);
  return err;
}

/* One tiny real request, to find out whether a key works before it is relied on. */
async function verifyKey(key, providerName) {
  const provider = providerByName(providerName) || providerForModel(modelFor(conn()));
  if (!provider) return { ok: false, problem: "There is no provider to test that key on." };
  const model = (PLATFORM.models.find(m => m.provider === provider.name) || {}).id;
  try {
    await callDirect("", [{ role: "user", content: "hi" }], model, 4, provider, key);
    return { ok: true };
  } catch (e) {
    const net = /failed|network|load/i.test(e.message || "") && !e.status;
    return {
      ok: false,
      problem: net
        ? isLocalFile()
          ? "The request could not leave the browser. Check your internet connection."
          : "A published page is not allowed to call " +
            provider.label +
            ". Open " +
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
  if ((await checkStudio()) && !directFor()) {
    // served by Studio: it answers itself
    bridgeOk = true;
    b.mode = "studio";
    bridgeChecking = false;
    save();
    redrawForConnection();
    return true;
  }
  if (directFor() && b.route !== "bridge") {
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
      bridgeErr = "The bridge is running but has no way to reach a model yet.";
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
/* The screens that say whether the tutor is connected, redrawn once the answer is known. */
function redrawForConnection() {
  renderSidebar();
  if (route.view === "settings") viewSettings();
  if (route.view === "home") viewHome();
  if (route.view === "learner") viewLearner();
  if (route.view === "m" && route.step === 5) renderStep(byId(route.id), 5);
  if (route.view === "m" && railOpen()) renderRail();
}

/* An error body from Studio or the bridge, turned into the Error the page throws. `why` is
   theirs when they sent one, and the HTTP status when they did not. */
function tutorError(body, status, fallback) {
  const err = new Error((body && body.error) || fallback);
  err.status = status;
  err.why = (body && body.why) || troubleFromStatus(status);
  return err;
}

async function askBridge(system, messages) {
  const b = conn();
  if (connMode() === "direct") {
    return callDirect(system, messages, modelFor(b), TUTOR.maxTokens);
  }
  if (connMode() === "studio") {
    const r = await fetch(STUDIO.origin + "/api/ask", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ model: modelFor(b), system, messages }),
    });
    const j = await r.json().catch(() => ({ error: "Studio sent something unreadable." }));
    if (!r.ok || j.error) throw tutorError(j, r.status, "Studio error " + r.status);
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
  if (!r.ok || j.error) throw tutorError(j, r.status, "Bridge error " + r.status);
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
