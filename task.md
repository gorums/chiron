# Tasks — decoupling the platform from Claude

Companion to `plan.md`. One checkbox per unit of work that can be finished and tested on its
own. **Both suites must pass at the end of every phase**:

```
python platform/tests/test_build.py
python platform/tests/test_studio.py
npm run format
node platform/tests/page_smoke.js dist/<id>/<output>-local.html
```

---

## Phase 1 — Extract the provider layer (no behaviour change)

- [x] `platform/coursekit/llm/__init__.py` — the registry: `providers()` from settings,
      `provider(name)`, `complete(req)`, and re-exports of `ask`, `ask_json`, `strip_fence`.
      Module docstring says what it is for and why it is stdlib-only.
- [x] `platform/coursekit/llm/base.py` — `Provider`, `Request`, `Reply`, `Capabilities`,
      `LLMFailed(message, kind, detail, resets_at, provider)`. No implementation.
- [x] `platform/coursekit/llm/shape.py` — move `chat_prompt`, `strip_fence`, `_slice_json`
      (→ `slice_json`, public since two modules want it), `ask_json` out of
      `studio/claude_cli.py` unchanged.
- [x] `platform/coursekit/llm/chain.py` — move `ask`, `_ask_model`, `_one_call`, `model_chain`,
      `_FINAL`, `_tell`, `_say`. Keep the job-event emission; take the emit callback as an
      argument so `coursekit` does not import `studio.jobs`.
- [x] `platform/coursekit/llm/cli.py` — move `find_cli`, `available`, `_argv`, `_run`,
      `_HEADLESS`, `probe`, `_refused`, `PROBE_PROMPT`. Implements `Provider`.
- [x] Move `platform/coursekit/failures.py` → `platform/coursekit/llm/failures.py`; leave a
      one-line re-export at the old path (the bridge imports it by path today).
- [x] Rewrite `platform/studio/claude_cli.py` as a shim: same public names
      (`ask`, `ask_json`, `strip_fence`, `timeout_for`, `available`, `find_cli`, `probe`,
      `model_aliases`, `default_model`, `chat_prompt`, `model_chain`, `ClaudeFailed`,
      `ClaudeUnavailable`, `DEFAULT_TIMEOUT`), each delegating. `ClaudeFailed = LLMFailed`.
- [x] Wire the job-event callback in `studio/` so `call` events still reach `jobs.current()`.
- [x] `platform/tests/test_build.py` — new `TestProviderLayer`: the CLI provider builds the
      argv it did before; `chain` retries on `transient`, walks the chain on `model`, stops on
      `quota` / `auth` / `timeout`; `shape.ask_json` recovers from a fenced reply.
- [x] Confirm all 94 `claude_cli.ask` stubs in `test_studio.py` still work through the shim.
      *(They do. `ask_json` takes an `asker` so stubbing one name still stubs both. The
      dozen tests that reached for internals — `find_cli`, `_run`, `_tell`/`_say`,
      `BACKOFF`, `RETRIES`, `_slice_json` — now patch `coursekit.llm.cli` /
      `coursekit.llm.chain` instead, which is where those live.)*

**Done.** 96 tests in `test_build.py` (14 new), 140 in `test_studio.py`, `build marketing` and `page_smoke.js` clean. `CLAUDE.md` gained a "Reaching a model" section and the two module tables were corrected; the rest of the documentation waits for Phase 8.

## Phase 2 — Settings: providers, and models that name one

- [x] `platform/settings.json` — add the `providers` block (`claude-code`, `anthropic`,
      `openai`, `google`, `local`) and `llm.*`; give every `models.list` entry a `provider`.
      *(The old blocks are gone from the committed file rather than deprecated in place:
      present at all now means deliberately set by an overlay, Studio or an older
      settings.json, so `_absorb_legacy` can let them win and then drop them. Two places
      to look would have been the bug this avoids.)*
- [x] `coursekit/settings.py` — read `llm.*` with `claude.*` as fallback; synthesise
      `providers.anthropic` from a legacy `anthropic.*` block; `models[].provider` defaults to
      `llm.defaultProvider`.
- [x] `coursekit/settings.py` — `SECRET_KEYS` becomes a predicate matching `providers.*.apiKey`
      and `jupyter.token`; `describe()` and `page()` both use it.
- [x] `coursekit/settings.py` — `ENV_KEYS` gains `OPENAI_API_KEY`, `GOOGLE_API_KEY`,
      `LLM_DEFAULT_PROVIDER`; existing names repointed (`ANTHROPIC_API_KEY` →
      `providers.anthropic.apiKey`, `BRIDGE_API_URL` → `providers.anthropic.apiUrl`,
      `ANTHROPIC_API_VERSION` → `providers.anthropic.apiVersion`).
- [x] `coursekit/settings.py` — `model_aliases`, `default_model`, `model_id` become
      provider-aware; add `provider_of(alias_or_id)` and `models_for(provider)`.
- [x] `studio/models.py` — widen `MODEL_ID` to `^[a-z0-9][a-z0-9._:/-]{0,119}$`; validate
      `provider` against the configured providers; uniqueness of `id` per provider, of `alias`
      globally.
- [x] `.env.example` — document the new keys; keep every old one working with a note.
- [x] Tests: an old-shape `state/settings.json` (no `provider`, `claude.*` only) still loads
      and resolves; `page()` never carries an `apiKey`; `describe()` shows `(set)` for one.

Also done, not foreseen:

- [x] `llm/__init__.py` builds its providers from the `providers` block, so Claude Code is
      an ordinary `cli` row (`CliProvider.from_settings`) rather than a hard-coded one. A
      kind with no adapter yet is skipped, not an error; a configuration that leaves
      nothing still yields the CLI.
- [x] `models.normalise` also refuses an alias that is another model's id — with ids now
      scoped per provider, that collision stopped being caught by the id rule, and
      `model_aliases` maps both into one table.
- [x] `ui/js/31-models.js` round-trips each row's `provider` untouched, so saving the list
      from a Studio that cannot yet edit that column does not silently reassign a model.
      The column itself is Phase 6.

**Done.** 100 tests in `test_build.py` (4 new), 141 in `test_studio.py` (1 new), `build marketing`, `page_smoke.js` and `prettier --check` clean. Verified on this machine against a real `state/settings.json` written before providers existed: its models resolve to `claude-code` and nothing had to be migrated.

## Phase 3 — The Anthropic provider, and the bridge on the shared layer

- [x] `platform/coursekit/llm/anthropic.py` — `complete`, `probe`, `catalog`, `describe`;
      lift `call_api` and `read_api_catalog` from the bridge and `discover.py`.
- [x] `llm/failures.py` — keep `from_status`; add Anthropic error-body codes.
- [x] `tools/bridge/tutor-bridge.py` — new file: the HTTP server, CORS, `config.json`,
      `candidate_keys` (extended to `OPENAI_API_KEY`, `GOOGLE_API_KEY`), `/health`, `/ask`.
      Every call goes through `coursekit.llm`.
- [x] Delete `call_api`, `call_cli`, `flatten`, `cli_argv`, `verify_key`, `api_error`,
      `CliFailed`, `FINAL_KINDS`, `ALLOWED_MODELS`, `CLI_MODELS` from the bridge.
      *(`cli_works` and `active_mode` stayed — they are the bridge deciding which route
      is live, which is its own job. `flatten`'s trimming became `trim`, which returns
      the trimmed parts for a provider to shape: it bounds cost per question, not any
      command-line length.)*
- [x] `tools/bridge/claude-bridge.py` — reduce to a shim importing `tutor-bridge.py`; update
      `start-bridge.bat` and `tools/bridge/README.md`.
- [x] `/health` reports `{providers: [{name, label, kind, ready, keySource}], ready}` instead
      of `{cli, has_key, key_source}`; keep the old fields for one release.
- [x] Tests: the bridge answers through a stubbed provider; a 429 becomes `why: "quota"`;
      the two-provider chain falls through correctly.

Also done, not foreseen:

- [x] `chain.model_chain(model, provider)` never crosses providers. Falling back to a
      model on another account answers a question nobody asked and bills someone who did
      not agree to it. A provider with nothing listed yet is not filtered by.
- [x] `llm.ask` resolves the provider from the model through `SETTINGS.provider_of`. A
      caller names a model, never a provider — otherwise every call site in Studio would
      be a second place to keep right, and a non-default provider would never be reached.
- [x] `discover.read_api_catalog` delegates to `AnthropicProvider.catalog`, so the paging
      exists once. Only the label tidying stayed behind, which is discovery's own want.
- [x] `claude_cli.available()` means the default provider, not any provider — otherwise
      an Anthropic key with no CLI installed would tell Studio it may write courses.

**Done.** 116 tests in `test_build.py` (16 new: the Anthropic wire format, the provider-scoped chain, the bridge), 141 in `test_studio.py`. The bridge was run for real: `/health` reports both providers, an echo-mode question round-trips, and one live question came back through the CLI provider. `claude-bridge.py` went from 574 lines to a 27-line shim; `tutor-bridge.py` is 489, because what is genuinely the bridge's — the key hunt, the routing, the budget, the HTTP — stayed and got documented. The duplicated model-calling code is what went.

## Phase 4 — OpenAI, Gemini, and a generic CLI

- [x] `platform/coursekit/llm/openai.py` — Chat Completions; system as a `system` message;
      `choices[0].message.content`; `Authorization: Bearer`; base URL from settings so the
      same adapter serves Ollama, LM Studio, vLLM, OpenRouter, Groq and Azure.
- [x] `platform/coursekit/llm/gemini.py` — `generateContent`; `systemInstruction`;
      `contents[].parts[].text` with `assistant` → `model`; `x-goog-api-key`.
- [x] `llm/failures.py` — OpenAI (`insufficient_quota`, `invalid_api_key`, `model_not_found`,
      `rate_limit_exceeded`, `context_length_exceeded`) and Google (`RESOURCE_EXHAUSTED`,
      `PERMISSION_DENIED`, `NOT_FOUND`, `UNAVAILABLE`) patterns.
- [x] `llm/cli.py` — argv from the provider's `command` / `args` / `modelFlag` / `promptOn`
      settings; Claude Code becomes one configuration among several.
- [x] Tests: one round-trip per wire format against a stubbed `urlopen`; the shared retry and
      chain logic behaves identically across all four kinds.

Also done, not foreseen:

- [x] `llm/wire.py` — `HttpProvider`: the socket, the key, the probe and the failure
      translation, written once. An adapter fills in four hooks (`url_for`, `headers`,
      `body_for`, `text_of`), which is why `openai.py` and `gemini.py` are ~70 lines.
      `anthropic.py` was moved onto it in the same pass rather than left as a third copy.
- [x] `maxTokensField` per provider. Newer OpenAI reasoning models reject `max_tokens`
      and older servers reject `max_completion_tokens`; guessing here would be a literal
      in the code for something that differs per server.
- [x] **A bug the live test found.** `llm.complete` on a provider with no models listed
      silently replaced the asked-for model with the default: a request naming
      `llama3.1:70b` went out as `opus`. `model_chain` now says which list it is
      consulting — the list decides where it has anything to say about that provider,
      and passes the name through where it has not. Two Studio tests caught the
      over-correction (a model taken off the list must still not be asked for), which is
      how the rule ended up stated properly rather than patched twice.

**Done.** 132 tests in `test_build.py` (16 new: both wire formats, the shared-failure
sweep across all four providers, the argument-passing CLI), 141 in `test_studio.py`.
Proved live against a local OpenAI-shaped server: system prompt as a turn, the model id
sent verbatim, one attempt, the reply read back out of `choices[0].message.content`.

## Phase 5 — Discovery, per provider

- [x] Move `read_cli_catalog`, `read_cached_catalog`, `parse_cli_catalog`, `CLI_SELECTOR`,
      `CLI_CATALOG` out of `discover.py`; `CliProvider.catalog()` delegates to them and
      returns "could not be read" for a binary that is not Claude Code.
      *(They went to `llm/claude_code.py`, not into `cli.py`. `cli.py` is how to run any
      headless tool; these regular expressions are one program's internals. A file named
      for the vendor is where a vendor-specific thing belongs, and it keeps `cli.py`
      generic — which is the whole point of the phase.)*
- [x] `catalog()` on the `anthropic`, `openai` and `gemini` providers.
- [x] `studio/discover.py` — `sources()` asks every enabled provider; `plan` and `removals`
      keyed by provider; a provider whose sources all failed yields no removal candidates.
- [x] `state/models-discovery.json` gains `provider` on every row; the settings-page report
      shows it.
- [x] Tests: the existing `plan` / `removals` cases still pass with a provider key; a failing
      provider never shrinks another provider's models.

Also done, not foreseen:

- [x] `Provider.catalog()` grew a stated contract: `{ok, models, known, error}`, where
      `known` is the wider set a source recognises (a picker offers five models and
      accepts twenty). `sources()` fills it in for a source that draws no distinction.
- [x] `catalog_is_complete` on the provider replaces `api_answered` in `removals`. Who
      may be believed when a model is missing is a property of the source, not of
      whichever source happened to be called Anthropic.
- [x] "Only what is newer" generalised: a source whose models carry creation dates offers
      only what is newer than the newest listed; one without dates offers everything.
      That was hard-coded as "the API does this, the binary does not".
- [x] `ui/js/31-models.js` iterates the report's providers instead of naming two sources
      in prose, and tolerates a report written before this release (plain ids, `cli`/`api`
      keys) — there is one on disk after an upgrade.

**Done.** 132 tests in `test_build.py`, 144 in `test_studio.py` (3 new; the discovery
tests were rewritten for the per-provider merge rather than patched). Run against the
real installed binary: 3 models offered, 19 known, read from the binary, nothing added or
removed — and the Anthropic row reports "no API key configured" rather than an empty
catalogue, which is what stops it removing anything.

## Phase 6 — Studio UI

- [x] `catalog.state()` — the `claude` block becomes `llm`
      (`{available, providers, model, models, defaultModel}`); keep `claude` as an alias for
      one release so an unrebuilt page still boots.
- [x] `server.py` — `NO_CLAUDE` → `NO_PROVIDER`, sentence from the provider's label;
      `_claude()` guard → `_provider()`; docstring route table updated.
- [x] `ui/js/31-models.js` — a provider column in the model-list editor; add-a-model picks its
      provider; the Test button says which provider refused.
- [x] `ui/js/30-settings.js` — per-provider cards: enabled, endpoint, key state
      (`(set)` / empty), Test.
- [x] `ui/js/28-model.js` — `modelChoice` / `modelBrief` group by provider when more than one
      is enabled; `quickModelBar` likewise.
- [x] `ui/js/00-core.js` — the status pill names the configured provider, not "Claude Code".
- [x] `ui/js/10-library.js`, `20-course.js`, `25-figures.js`, `26-media.js`, `27-notebooks.js`,
      `40-job.js` — replace every "Claude" with the provider label or "the model".
- [x] Tests: `page_smoke.js` over `ui/js/*.js` still boots; every route in the docstring
      resolves.

Also done, not foreseen:

- [x] **A bug found by driving the live API.** `POST /api/models/test` with
      `provider: "openai"` was answered by Claude Code refusing the model, because
      `provider_for` fell back to the default for any name not in the *enabled* list.
      `enabled` governs what is **offered**, not what may be **addressed**:
      `llm.find(name)` now reaches a configured provider whether or not it is on, and
      `llm.probe` refuses an unknown name rather than trying somewhere else.
- [x] The settings page lists **every configured provider**, disabled ones included — a
      row nobody can see is a row nobody can enable, and a model can be added to a
      provider before it is switched on.
- [x] `prefs.models()` returns dicts rather than positional tuples, so a fifth field is
      not a fifth index every caller has to count to.

**Done.** 134 tests in `test_build.py` (2 new), 144 in `test_studio.py`; prettier clean.
The new UI was rendered inside the real boot harness (`page_smoke.js --checks`) rather
than eyeballed: provider rows, grouped model options, the provider column appearing only
when there is a choice, and the gate quoting the provider's own hint. Then driven live
against a running Studio on 8795: a probe on a disabled provider now says "OpenAI has no
API key configured", a real one answers OK in 5.4s, and all five providers report with
their enabled and ready state.

## Phase 7 — The course page

- [x] `SETTINGS.page()` — add `providers` (enabled and direct-callable only, never a key);
      keep `apiUrl` / `apiVersion` for one release.
- [x] `platform/web/js/14b-wire.js` — new: `WIRE.anthropic`, `WIRE.openai`, `WIRE.gemini`,
      each with `request`, `reply`, `problem`.
- [x] `platform/web/js/14-conn.js` — `callAnthropic` → `callDirect(provider, …)` through
      `WIRE`; `TROUBLE_BY_STATUS` stays (it is the JS twin of `from_status`);
      `adoptStudioModels` reads the new `llm` block.
- [x] `platform/web/js/01-state.js` — `bridge.keys` map; `upgrade()` moves an old
      `bridge.key` into `keys.anthropic`; `connDefaults()` updated.
- [x] `platform/web/js/19-settings.js` — connection card rewritten around providers: pick one,
      paste its key, Test; the Claude-Code / bridge path becomes one provider among them.
- [x] `platform/web/js/17-rail.js`, `08-quiz.js`, `07b-gaps.js`, `17c-learner.js`,
      `00-dom.js` — every user-facing "Claude" becomes "the tutor" or a resolved label;
      `HELP.tutor` and `HELP.verdict` rewritten.
- [x] Tests: `rail_checks.js` and `learner_checks.js` still pass; a saved model id no longer
      in the list falls back to the default.

Also done, not foreseen:

- [x] **`apiProvider`, and the bug that asked for it.** A browser cannot spawn a
      process, so a model whose provider is the `cli` row is unreachable from a page
      opened off disk — even with a perfectly good API key, because the same model sits
      behind an API under a different provider name. Caught by the first live check:
      `connMode()` said `none` with a key stored. The `cli` row now names its API twin,
      `page_providers` turns that into `standsInFor`, and the page follows it. A setting,
      because nothing should infer which company's API serves which model id.
- [x] **A key that cannot reach the chosen model no longer disables Studio.** The old
      rule was "any key wins over Studio"; with per-provider keys that let a stored
      OpenAI key turn off a Studio serving a Claude model. Now only a *usable* key wins.
- [x] `19-settings.js` shows one key row per callable provider rather than one field, and
      the cost explainer stopped naming one company's plans.

**Done.** 135 tests in `test_build.py` (1 new), 144 in `test_studio.py`; `rail_checks.js`
and `learner_checks.js` still pass. 22 new checks run inside the built page: the three
wire formats byte for byte, the key migration from a pre-provider save, every routing
case, and that a refusal reports the same six kinds whoever sent it. Then fed the running
container's own `/api/state` into the built page: it adopts the list, keeps each model's
provider, and works out that a browser reaches `claude-opus-5` through the Anthropic API
while Studio reaches it through Claude Code.

## Phase 8 — The words, and the guards

- [ ] `test_build.py` — extend `HARDCODED` with `claude`, `anthropic`, `openai`, `chatgpt`,
      `gemini` (case-insensitive) for `platform/web/js/`; add the same check for
      `platform/studio/ui/js/`. Docstring names the rule.
- [ ] `test_build.py` — a test that `SETTINGS.page()` carries no `apiKey` for any provider.
- [ ] `CLAUDE.md` — new "Providers" section (the layer, the settings shape, the `cli` kind,
      what stays vendor-specific); vocabulary table gains provider / model / the model runner;
      update "Course Studio", "The two-layer rule", "Settings", the bridge paragraphs and the
      module table.
- [ ] `README.md`, `.env.example`, `tools/bridge/README.md` — provider language throughout.
- [ ] `docker/Dockerfile` and `compose.yaml` — comments say Claude Code is the default
      provider's runner, not a platform requirement; `CLAUDE_HOME` documented as needed only
      when that provider is enabled.
- [ ] `grep -rniE "claude|anthropic|openai|gemini" platform/web/ platform/studio/ui/` returns
      nothing; record the one-liner in CLAUDE.md beside the existing two-layer grep.
- [ ] Remove the one-release aliases added in Phases 3 and 6 (`/health` legacy fields, the
      `claude` block in `/api/state`, `claude-bridge.py`) once everything reads the new names.

---

## Order of attack

1. Phases 1–3 in sequence — they are load-bearing and each ends green.
2. Phase 4 whenever a second real provider is wanted; Phase 5 straight after it.
3. Phases 6 and 7 are independent of each other.
4. Phase 8 last, and not optional.

## Definition of done

- A model row naming any of `claude-code`, `anthropic`, `openai`, `google` or `local` can be
  added on the Studio settings page and used to write a module, review one, draw figures and
  answer in the tutor — with no code change.
- `platform/coursekit/llm/` is the only place any wire format or CLI argv appears.
- No vendor name in `platform/web/js/` or `platform/studio/ui/js/`, enforced by a test.
- A fresh clone with no `.env` behaves exactly as it does today: Claude Code, Opus 5, one
  provider, nothing new to configure.
