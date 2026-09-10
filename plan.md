# Decoupling the platform from Claude

**Goal.** The engine should not know which company makes the model. Today "Claude" is three
different things wired into the same places — a *wire protocol* (Anthropic Messages), a
*local CLI* (Claude Code), and a *word printed at the reader* ("Claude replied"). Separating
those three is the whole job. Afterwards, adding Sol 5.6 or Gemini Flash 3 is a row in
`settings.json` and, at most, one ~80-line adapter file.

This is the same move the repository already made twice: the two-layer rule pushed every
subject word behind `CFG`, and the settings work pushed every literal behind `settings.json`.
This pushes every vendor word behind a **provider**.

---

## 1. What the research found

### 1.1 The good news: most of the code is already neutral

| Neutral today | Why it matters |
|---|---|
| `studio/prompts.py` (782 lines) | Not one prompt says "Claude". They are model-neutral instructions already. |
| `studio/coerce.py`, `curriculum.py`, `generator.py`, `editing.py`, `figures.py`, `notebooks.py` | They call `claude_cli.ask` / `ask_json` / `strip_fence` / `timeout_for` and nothing else. The call surface is a dozen names. |
| `coursekit/config.py`, `loader.py`, `validate.py`, `renderer.py` — the whole build | No vendor knowledge at all. |
| `coursekit/failures.py` | The *kinds* (`quota`, `auth`, `model`, `transient`, `timeout`, `unknown`) are already the right abstraction for any provider. Only the regexes and the sentences are Anthropic-shaped. |
| `courses/<id>/` | A course is markdown, JSON, SVG and notebooks. No coupling at all. |

So this is not a rewrite. It is an extraction plus a rename.

### 1.2 The coupling, located

**A. One provider implementation, hard-wired** — `platform/studio/claude_cli.py` (397 lines).
It mixes four separable things:

1. *Transport*: find the `claude` binary, `-p --output-format text`, prompt on stdin, run from
   a scratch cwd, `cmd /c` shim on Windows (`_HEADLESS`, `_run`, `_argv`, `find_cli`).
2. *Resilience*: retry on `transient` with doubling backoff, walk a model chain on `model`,
   stop dead on `quota` / `auth` / `timeout` (`ask`, `_ask_model`, `model_chain`, `_FINAL`).
3. *Shaping*: `chat_prompt` flattens system + messages into one prompt because the CLI takes
   one prompt; `strip_fence`, `_slice_json`, `ask_json` insist on JSON.
4. *Observability*: `call` events to `jobs.current()`, log lines.

Only (1) is Claude-specific. (2), (3) and (4) are the platform's, and every provider wants them.

**B. A second, duplicated implementation** — `tools/bridge/claude-bridge.py` (574 lines).
It re-implements the CLI call (`call_cli`, `flatten`, `cli_argv`, `cli_works`) *and* adds the
Anthropic HTTP call (`call_api`) that Studio does not have. Two copies of one job, already
drifting: the bridge trims prompts to a budget, Studio does not; the bridge's model chain is
three attempts, Studio's is two; the bridge classifies with `classify`, Studio with `describe`.
Any provider work done in one place has to be done twice unless this is fixed first.

**C. A third implementation, in the browser** — `platform/web/js/14-conn.js`, `callAnthropic()`.
Speaks the Anthropic wire format directly: `x-api-key`, `anthropic-version`,
`anthropic-dangerous-direct-browser-access`, a top-level `system`, and reply extraction from
`content[].text`. `TROUBLE_BY_STATUS` re-implements `failures.from_status` in JS.

**D. Settings shaped around one vendor** — `platform/settings.json`:

- `anthropic.{apiUrl, modelsUrl, apiVersion, apiKey}` — one endpoint block, singular.
- `models.list[]` — `{id, alias, label, note}`, with **no provider field**; every entry is
  implicitly "reachable through Claude Code".
- `claude.{timeout, jsonAttempts, chatHistory, probeTimeout, retries, backoffSeconds,
  backoffMaxSeconds}` — platform-wide resilience knobs, named after the vendor.
- `coursekit/settings.py`: `ENV_KEYS` hard-codes `ANTHROPIC_API_KEY`, `ANTHROPIC_API_VERSION`
  and `BRIDGE_API_URL`; `SECRET_KEYS` is the fixed tuple `("anthropic.apiKey", "jupyter.token")`;
  `model_aliases` / `default_model` / `model_id` assume one namespace of ids.
- `studio/models.py` validates ids against `^[a-z0-9][a-z0-9.\-]{1,79}$` — "what
  `claude --model` accepts". `gpt-sol-5.6` passes; `models/gemini-flash-3` (a Google resource
  path) and `llama3.1:70b` (an Ollama tag) do not.

**E. Discovery is Claude-Code-specific** — `platform/studio/discover.py` (366 lines) reads
model rows out of the `claude` binary with two regexes (`CLI_SELECTOR`, `CLI_CATALOG`) and out
of `~/.claude/cache/model-catalog/*.json`, plus Anthropic's `GET /v1/models`. The *merge rule*
(`plan`, `removals`, `base_id`) is provider-neutral and worth keeping verbatim; the two
*sources* are not.

**F. Vendor words in the user interface** — ~95 occurrences:

| Surface | Files (hits) | Roughly |
|---|---|---|
| Course page | `19-settings.js` (20), `14-conn.js` (14), `17-rail.js` (5), `07b-gaps.js` (4), `17c-learner.js` (3), `00-dom.js` (2), `08-quiz.js` (1) | "Which Claude answers", "Claude replied in …", "Claude: that covers it", the whole API-key explainer |
| Studio UI | `10-library.js` (17), `00-core.js` (14), `20-course.js` (11), `28-model.js` (9), `40-job.js` (7), `31-models.js` (5), `25-figures.js` (5), `27-notebooks.js` (4), `30-settings.js` (4), `26-media.js` (3) | "Claude Code is not on this PATH", "Review with Claude", the status pill |
| Python | `server.py` `NO_CLAUDE`, `catalog.py` `"claude": {…}` in `/api/state`, `failures.explain()` sentences | the API contract itself names the vendor |

Note that `/api/state` returns a key literally called `claude`, and the page reads
`j.claude.available` and `j.claude.models`. That is a wire contract to rename.

**G. Environment and container** — `.env.example` (`CLAUDE_HOME`, `ANTHROPIC_API_KEY`,
`BRIDGE_API_URL`), `compose.yaml` (mounts `${CLAUDE_HOME}` at `/root/.claude`),
`docker/Dockerfile` (`npm install -g @anthropic-ai/claude-code`). These stay — but as *one
provider's* requirements, optional rather than assumed.

**H. Guards that will fight the change** — `TestCodeConventions.HARDCODED` in `test_build.py`
already forbids `claude-sonnet`, `claude-opus`, `api.anthropic.com/` and friends in the front
end. Good: it will catch regressions. It must be *extended*, not relaxed.

### 1.3 What the providers actually differ on

| | Anthropic Messages | OpenAI Chat Completions | Google `generateContent` | Local CLI |
|---|---|---|---|---|
| Auth | `x-api-key` header | `Authorization: Bearer` | `x-goog-api-key` or `?key=` | none (signed-in binary) |
| System prompt | top-level `system` | a `{role:"system"}` message | top-level `systemInstruction` | prepended text |
| Messages | `messages[{role, content}]` | same | `contents[{role, parts:[{text}]}]`, `assistant` → `model` | flattened transcript |
| Token cap | `max_tokens`, required | `max_tokens` / `max_completion_tokens` | `generationConfig.maxOutputTokens` | n/a |
| Reply | `content[].text` | `choices[0].message.content` | `candidates[0].content.parts[].text` | stdout |
| Errors | HTTP status + `error.message` | HTTP status + `error.code` | HTTP status + `error.status` | exit code + stderr |
| Model list | `GET /v1/models` | `GET /v1/models` | `GET /v1beta/models` | regex over the binary |

Three adapters cover nearly everything, because **OpenAI Chat Completions is the de-facto
lingua franca**: Ollama, LM Studio, vLLM, OpenRouter, Groq, DeepSeek, Mistral, xAI and Azure
all speak it. So: `anthropic`, `openai` (with a configurable base URL — that one adapter is
also every local and aggregator backend), `gemini`, plus a generic `cli` kind.

And the `cli` kind generalises too. `claude -p --output-format text --model X` differs from
`codex exec -m X` and `gemini -p -m X` only in the argument vector. Make the argv a setting
and Claude Code stops being special-cased in code at all.

---

## 2. The design

### 2.1 One new package: `platform/coursekit/llm/`

It goes in `coursekit`, not `studio`, for the same reason `settings.py` and `failures.py` are
there: **`tools/bridge/` imports it from outside the package.** That is what deletes the
duplicate implementation (finding B). Consequence, and it is a hard constraint:
**`coursekit.llm` is standard library only** — `urllib.request` for HTTP, `subprocess` for a
CLI. No `anthropic`, no `openai`, no `httpx`. The wire formats above are stable and small; a
vendor SDK would cost more than it saves and would break `pip install markdown` being the
platform's only dependency.

```
coursekit/llm/
  __init__.py     the registry, and the one entry point everything calls
  base.py         Provider, Request, Reply, Capabilities — the interface, and nothing else
  chain.py        retry, backoff, model fallback, job `call` events   (from claude_cli.ask)
  shape.py        chat_prompt / flatten, strip_fence, slice_json, ask_json  (from claude_cli)
  failures.py     moved from coursekit/failures.py; kinds unchanged, wording parameterised
  cli.py          kind "cli": any headless binary, argv from settings  (Claude Code, codex, …)
  anthropic.py    kind "anthropic": Messages API
  openai.py       kind "openai": Chat Completions — also Ollama, OpenRouter, Groq, vLLM, Azure
  gemini.py       kind "gemini": generateContent
```

`base.Provider` — the whole interface, deliberately five methods:

```python
class Provider:
    kind: str                       # "cli" | "anthropic" | "openai" | "gemini"
    name: str                       # the settings key: "claude-code", "openai", "local"
    label: str                      # what a human is shown: "Claude Code", "OpenAI"
    caps: Capabilities              # single_prompt, system_role, max_tokens, needs_key

    def available(self) -> bool: ...                # binary on PATH / key present
    def complete(self, req: Request) -> Reply: ...  # the one call that matters
    def probe(self, model: str, timeout: int) -> dict: ...  # one cheap call, this model only
    def catalog(self) -> dict: ...                  # models this provider offers, for discovery
    def describe(self) -> dict: ...                 # what /api/state should say about it
```

`Request` is `{system, messages, model, timeout, max_tokens, what}`; `Reply` is
`{text, model, provider, seconds}`. `complete` raises
`LLMFailed(message, kind, detail, resets_at, provider)` — today's `ClaudeFailed` with a
provider on it.

Everything above the provider — `chain.py`, `shape.py`, the job events, the log lines — is
written once and shared. That is the point of the split: **the retry policy, the JSON
insistence and the progress reporting are the platform's, not the vendor's.**

### 2.2 Settings: `providers` alongside `models`

```json
"providers": {
  "claude-code": {
    "kind": "cli", "label": "Claude Code", "enabled": true,
    "command": ["claude", "claude.cmd", "claude.exe"],
    "args": ["-p", "--output-format", "text"],
    "modelFlag": "--model", "promptOn": "stdin",
    "signinHint": "Run `claude` once in a terminal and sign in."
  },
  "anthropic": {
    "kind": "anthropic", "label": "Anthropic API", "enabled": true,
    "apiUrl": "https://api.anthropic.com/v1/messages",
    "modelsUrl": "https://api.anthropic.com/v1/models",
    "apiVersion": "2023-06-01", "apiKey": ""
  },
  "openai": {
    "kind": "openai", "label": "OpenAI", "enabled": false,
    "apiUrl": "https://api.openai.com/v1/chat/completions",
    "modelsUrl": "https://api.openai.com/v1/models", "apiKey": ""
  },
  "google": {
    "kind": "gemini", "label": "Google Gemini", "enabled": false,
    "apiUrl": "https://generativelanguage.googleapis.com/v1beta", "apiKey": ""
  },
  "local": {
    "kind": "openai", "label": "Local models", "enabled": false,
    "apiUrl": "http://127.0.0.1:11434/v1/chat/completions",
    "modelsUrl": "http://127.0.0.1:11434/v1/models", "apiKey": "ollama"
  }
},
"models": {
  "default": "opus",
  "list": [
    {"provider": "claude-code", "id": "claude-opus-5",  "alias": "opus",  "label": "Claude Opus 5",   "note": "…"},
    {"provider": "openai",      "id": "gpt-sol-5.6",    "alias": "sol",   "label": "ChatGPT Sol 5.6", "note": "…"},
    {"provider": "google",      "id": "gemini-flash-3", "alias": "flash", "label": "Gemini Flash 3",  "note": "…"}
  ]
},
"llm": {
  "timeout": 600, "jsonAttempts": 3, "chatHistory": 20, "probeTimeout": 90,
  "retries": 2, "backoffSeconds": 5, "backoffMaxSeconds": 60,
  "defaultProvider": "claude-code"
}
```

Decisions baked into that shape:

- **`provider` is a field on a model, not a separate list.** A model is only ever reachable
  one way, and every picker in both surfaces already iterates `models.list`. Adding a field
  keeps every one of them working.
- **`provider` is optional on read.** An entry without it belongs to `llm.defaultProvider`.
  That is what makes a saved `state/settings.json` from before this change keep working with
  no migration script.
- **`claude.*` becomes `llm.*`.** The old block is still read as a fallback, so an existing
  `.env` or overlay does not break; `SETTINGS.describe()` reports it as deprecated.
- **`anthropic.*` stays readable** and seeds `providers.anthropic` when the new block is
  absent, for the same reason.
- **`enabled: false`** keeps a provider off every picker without deleting its configuration,
  which is how the settings page can offer OpenAI without pretending a key exists.

`SECRET_KEYS` stops being a tuple and becomes a predicate: any key matching
`providers.*.apiKey`, plus `jupyter.token`. `ENV_KEYS` gains `OPENAI_API_KEY`,
`GOOGLE_API_KEY` and `LLM_DEFAULT_PROVIDER`, and keeps every existing name pointed at its new
home.

**Model ids get a looser pattern.** `MODEL_ID` must accept `gpt-5.6`, `models/gemini-flash-3`,
`llama3.1:70b` and `us.anthropic.claude-opus-5-v1:0`. New rule: 1–120 characters of
`[a-z0-9._:/-]`, still lowercase, still no whitespace or quotes. Uniqueness becomes
**per provider** — `gpt-4o` on `openai` and on `local` are two different models and both must
be allowed. The alias, being the short name a human types, stays globally unique.

### 2.3 The bridge stops having its own brain

`tools/bridge/claude-bridge.py` → `tools/bridge/tutor-bridge.py`, and its 574 lines lose
roughly 250: `call_api`, `call_cli`, `flatten`, `cli_argv`, `cli_works`, `verify_key`,
`active_mode` and `CliFailed` all become one `coursekit.llm.complete(...)` call. What is left
is what a bridge should be: an HTTP server on loopback, CORS, a config file for a key, and the
first-run key hunt (`candidate_keys`, which is genuinely bridge-specific and worth keeping —
extended to look for `OPENAI_API_KEY` and `GOOGLE_API_KEY` too).

`claude-bridge.py` stays for one release as a two-line shim that imports the new file, because
`start-bridge.bat`, the docs and people's shortcuts point at it.

### 2.4 The page: three small adapters, chosen by kind

`CFG.platform` gains a `providers` block — for each *enabled, direct-callable* provider:
`{name, kind, label, apiUrl, apiVersion, needsKey}`. Never a key: `SETTINGS.page()` must strip
`apiKey` exactly as it already strips `jupyter.token`, and a test must say so.

`14-conn.js` splits:

- `14-conn.js` keeps route selection (`connMode`, `checkStudio`, `checkBridge`), `troubleOf`
  and `askBridge` — all provider-agnostic already.
- `14b-wire.js` (new) holds one `WIRE` entry per kind, each with `request(req, cfg, key)`
  returning `{url, headers, body}`, `reply(json)` returning text, and `problem(status, json)`
  returning `{message, why}`. Three entries: `anthropic`, `openai`, `gemini`. `callAnthropic`
  becomes `callDirect(providerName, …)`, which looks up the wire by kind. About 120 lines
  total, and the numeric prefix keeps load order intact.

The reader's saved `STATE.bridge.model` stays a bare model id. `modelFor()` already falls back
to the default when the id is not in `PLATFORM.models`, so a reader whose saved Claude id is
gone lands on whatever the list now offers — no migration, no lost state. `STATE.bridge.key`
becomes `STATE.bridge.keys[provider]`, with the old scalar read once and moved into
`keys.anthropic` in `upgrade()`, because a reader may plausibly hold two keys.

CORS reality check, because it decides how much of this is worth building: `file://` and a
Studio origin can reach `api.anthropic.com` (with the
`anthropic-dangerous-direct-browser-access` header), and OpenAI and Google both allow
browser-origin calls with a key. Ollama needs `OLLAMA_ORIGINS` set by the user. So direct mode
works for all three cloud kinds; the local kind is documented as "route it through Studio or
the bridge".

### 2.5 Discovery, per provider

Keep `plan()`, `removals()` and `base_id()` exactly as they are — a good, tested, pure merge
rule. Change only where the candidate lists come from:

- `discover.sources()` asks every enabled provider for `catalog()`.
- `cli.catalog()` = today's `read_cli_catalog` + `read_cached_catalog`, moved into
  `llm/cli.py` and made conditional on the binary actually being Claude Code (the regexes are
  Claude Code's; for any other CLI, `catalog()` returns "could not be read", which the merge
  already handles as "says nothing").
- `anthropic.catalog()` = today's `read_api_catalog`.
- `openai.catalog()` = `GET {modelsUrl}` → `data[].id`; also covers Ollama's `/v1/models`.
- `gemini.catalog()` = `GET {apiUrl}/models` → `models[].name`, `displayName`.
- The merge runs **per provider**: a model belonging to a provider whose sources all failed is
  never a removal candidate. That rule already exists for the "did the API answer" case; it
  just needs a provider key on it.

`state/models-discovery.json` grows a `provider` on every row. The report is read by one
screen, so widening it is safe.

### 2.6 The words

This is the half that is easy to underestimate. Three distinct nouns are currently all
"Claude", and the vocabulary table in CLAUDE.md must gain them:

| Say | Never | Meaning |
|---|---|---|
| provider | vendor, backend, service | one way to reach models: `claude-code`, `anthropic`, `openai`, `google`, `local` |
| model | | one row of `models.list`: `{provider, id, alias, label, note}` |
| the tutor | Claude, the assistant | who answers in the course page — unchanged, and it was already right |
| the model, the writer | Claude | who writes and reviews in Studio |
| the model runner | Claude Code | the `cli`-kind provider's binary; the status pill names the configured one |

Rules that follow, each testable:

- **No vendor name in `platform/web/js/` or `platform/studio/ui/js/`, at all.** Every name a
  reader sees comes from `CFG.platform.providers[…].label`, from a model's `label`, or from
  `/api/state`. Extend `TestCodeConventions.HARDCODED` from model ids to the words `Claude`,
  `Anthropic`, `OpenAI`, `GPT`, `ChatGPT`, `Gemini` — the same shape of guard the two-layer
  rule already uses for subject words, with
  `grep -rniE "claude|anthropic|openai|gemini" platform/web/ platform/studio/ui/` as the
  documented one-liner.
- **No vendor name in an API contract.** `/api/state`'s `claude` block becomes `llm`
  (`{available, providers: […], model, models, defaultModel}`); `NO_CLAUDE` becomes
  `NO_PROVIDER`, with a sentence built from the configured provider's label.
- **`failures.explain()` takes a provider label.** "Claude Code is not signed in. Run `claude`
  once…" becomes the provider's own `signinHint`, a settings field, so a `cli` provider can
  say what *it* needs. The kinds themselves do not change.
- Vendor names remain, correctly, in: `settings.json` (that is where configuration lives),
  `coursekit/llm/<vendor>.py` (that is the adapter), `.env.example`, `docker/`, `CLAUDE.md`
  and `.claude/skills/` (Claude Code's own files).

### 2.7 What deliberately does not change

- **The kinds in `failures.py`.** `quota` / `auth` / `model` / `transient` / `timeout` /
  `unknown` are already provider-neutral and every layer branches on them. Only the regexes
  gain vendor-specific patterns (`insufficient_quota`, `invalid_api_key`, `RESOURCE_EXHAUSTED`,
  `PERMISSION_DENIED`, `model_not_found`, `context_length_exceeded`).
- **Every prompt in `prompts.py`.** They are already neutral. Different models will produce
  different quality against them; `coerce.py` exists precisely because model output is
  distrusted for structure, and a weaker model just exercises it harder.
- **`courses/<id>/`.** No course file mentions a vendor, and none will.
- **The reader's stored state shape**, except `bridge.key` → `bridge.keys`, done with a
  read-old-write-new upgrade in `blank()` / `upgrade()` as the conventions require.
- **Claude Code as the default.** It stays `llm.defaultProvider`, it stays in the Dockerfile,
  and a fresh clone behaves exactly as it does today. This work adds options; it does not move
  anyone off anything.

---

## 3. Phases

Ordered so the suite is green at the end of each, and so the riskiest structural move
(extraction) happens while there is still only one provider to be wrong about.

**Phase 1 — Extract, change nothing.** Create `coursekit/llm/` with `base`, `chain`, `shape`,
`failures` (moved) and `cli` (Claude Code, argv hard-coded for now). `studio/claude_cli.py`
becomes a shim exporting the same dozen names. No settings change, no UI change. Success:
both suites pass with no edits except import paths.

**Phase 2 — The settings shape.** Add `providers`, `models[].provider` and `llm.*`; teach
`coursekit/settings.py` to read the old blocks as fallbacks; make `SECRET_KEYS` a predicate;
widen `MODEL_ID` and scope uniqueness per provider. Claude Code becomes an ordinary `cli` row.
Success: `build.py where` and the Studio settings page show the new keys with their sources,
and an old `state/settings.json` still loads.

**Phase 3 — The second provider, and the bridge.** Implement `llm/anthropic.py` (the code
already exists inside the bridge). Rewrite the bridge onto `coursekit.llm`. This is the phase
that proves the interface: two providers, one call path, ~250 duplicated lines deleted.

**Phase 4 — OpenAI and Gemini.** `llm/openai.py` (configurable base URL, which is also
Ollama / OpenRouter / Groq / vLLM / Azure) and `llm/gemini.py`. Per-provider failure regexes.
Generic `cli` argv from settings, so `codex` and `gemini` CLIs work as providers too.

**Phase 5 — Discovery per provider.** `catalog()` on each provider; `plan` / `removals` keyed
by provider; the report and the Models card grow a provider column.

**Phase 6 — Studio UI.** Provider column and per-provider key fields in the model-list editor;
the Test button reports which provider refused; every model picker groups by provider; the
status pill names the configured provider rather than "Claude Code".

**Phase 7 — The page.** `CFG.platform.providers`; `14b-wire.js` with three adapters;
`STATE.bridge.keys`; the connection screen rewritten around "which provider" rather than "a
key or Claude Code".

**Phase 8 — The words, and the guards.** De-vendor all ~95 strings across both surfaces;
rename the `/api/state` `claude` block; extend `TestCodeConventions.HARDCODED`; update the
CLAUDE.md vocabulary table and the sections describing Studio, the bridge and the settings.

Phases 1–3 are the load-bearing ones: after Phase 3 a second provider genuinely works and the
duplication is gone. Phases 4–7 are additive and can be done in any order, or dropped.
Phase 8 must not be skipped: a half-de-vendored interface is worse than an honest
single-vendor one.

---

## 4. Risks, and what to do about them

| Risk | Mitigation |
|---|---|
| The extraction changes retry or fallback behaviour by accident | Phase 1 moves code without editing it. The failure-classification tests in `test_build.py` cover the kinds, and `test_studio.py` stubs `claude_cli.ask` in 94 places — keep that stub name working through the shim so those call sites do not move at once. |
| A saved `state/settings.json` model list breaks | `provider` is optional on read and defaults to `llm.defaultProvider`. Tested explicitly. |
| A reader's saved model id disappears from the list | Already handled: `modelFor()` falls back to the default. Add a test that says so. |
| A widened `MODEL_ID` lets a bad id reach a shell | The `cli` provider passes argv as a list to `subprocess.run` with no shell, and always will. Ids never reach a shell; the widened pattern still forbids whitespace and quotes. |
| A weaker model produces worse course JSON | `coerce.py` is the existing answer, and `ask_json`'s retry-with-the-parse-error is the other. Record in each model's `note` whether it is known to write good modules. |
| A key leaks into a built page | `SETTINGS.page()` already strips `jupyter.token`; extend it to every `providers.*.apiKey` and add the test beside the existing one. |
| The Studio UI grows a provider dimension everywhere and gets cluttered | Group by provider only when more than one is enabled. With a single provider every screen looks exactly as it does today. |
