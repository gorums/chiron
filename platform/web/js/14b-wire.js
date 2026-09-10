/* ============================ the wire formats the page can speak ============================ */
/* ---- one entry per kind of provider ----
   When the reader has pasted a key, this page calls the provider itself. Three formats
   cover every provider worth calling from a browser, and they differ in about ten lines
   each: where the key goes, whether the system prompt is a field or a turn, and where the
   reply is. Everything else - choosing a route, retrying, saying what went wrong - is
   14-conn.js and does not care which of these answered.

   This is the browser's half of coursekit/llm/. The two are separate on purpose: a page
   opened off disk has no Python next to it, and a served page must not need the bridge to
   ask a question the reader is paying for themselves.

   Each entry:
     url(cfg, req)      where the request goes (Google puts the model in the path)
     headers(cfg, key)  how the key travels
     body(req)          the request as that API wants it
     reply(json)        the text, dug out of whatever it came wrapped in
     problem(json)      what the error body said, when it said anything
*/
const WIRE = {
  anthropic: {
    url: cfg => cfg.apiUrl,
    headers: (cfg, key) => ({
      "content-type": "application/json",
      "x-api-key": key,
      "anthropic-version": cfg.apiVersion,
      // Anthropic requires a browser calling it directly to say so.
      "anthropic-dangerous-direct-browser-access": "true",
    }),
    body: req => {
      const out = {
        model: req.model,
        max_tokens: req.maxTokens,
        messages: req.messages,
      };
      if (req.system) out.system = req.system;
      return out;
    },
    reply: json =>
      (json.content || [])
        .filter(c => c.type === "text")
        .map(c => c.text)
        .join(""),
    problem: json => (json && json.error && json.error.message) || "",
  },

  openai: {
    url: cfg => cfg.apiUrl,
    headers: (cfg, key) => ({
      "content-type": "application/json",
      authorization: "Bearer " + key,
    }),
    body: req => {
      const messages = req.system
        ? [{ role: "system", content: req.system }].concat(req.messages)
        : req.messages;
      const out = { model: req.model, messages };
      out[req.maxTokensField || "max_tokens"] = req.maxTokens;
      return out;
    },
    reply: json => {
      const first = (json.choices || [])[0] || {};
      return (first.message && first.message.content) || "";
    },
    problem: json => (json && json.error && (json.error.message || json.error.code)) || "",
  },

  gemini: {
    /* The model is in the path here, and a Google model id may already be written as the
       resource path it prints. Do not repeat the prefix. */
    url: (cfg, req) => {
      const model = req.model.startsWith("models/") ? req.model : "models/" + req.model;
      return cfg.apiUrl.replace(/\/$/, "") + "/" + model + ":generateContent";
    },
    headers: (cfg, key) => ({ "content-type": "application/json", "x-goog-api-key": key }),
    body: req => {
      const out = {
        contents: req.messages.map(m => ({
          role: m.role === "assistant" ? "model" : "user",
          parts: [{ text: m.content }],
        })),
        generationConfig: { maxOutputTokens: req.maxTokens },
      };
      if (req.system) out.systemInstruction = { parts: [{ text: req.system }] };
      return out;
    },
    reply: json => {
      const first = (json.candidates || [])[0] || {};
      const parts = (first.content && first.content.parts) || [];
      return parts.map(p => p.text || "").join("");
    },
    problem: json => (json && json.error && (json.error.message || json.error.status)) || "",
  },
};

/* The providers this page may call itself, from CFG.platform - enabled, speaking a wire
   format this file has, and never carrying a key. */
function directProviders() {
  return (PLATFORM.providers || []).filter(p => WIRE[p.kind]);
}
function providerByName(name) {
  return directProviders().find(p => p.name === name) || null;
}
/* The provider this page would call for a model.

   Usually the model's own. But a model reached through a local command-line tool cannot be
   reached from a browser at all - nothing here can spawn a process - even though the same
   model sits behind an API. So a direct provider may declare that it serves another
   provider's models (`standsInFor`, from `apiProvider` in settings.json), and that is the
   one used. It is a setting rather than a guess: nothing here should be inferring which
   company's API serves which model id. */
function providerForModel(id) {
  const model = PLATFORM.models.find(m => m.id === id);
  if (!model) return null;
  const own = providerByName(model.provider);
  if (own) return own;
  return directProviders().find(p => (p.standsInFor || []).includes(model.provider)) || null;
}
