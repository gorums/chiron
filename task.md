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

- [ ] `platform/coursekit/llm/anthropic.py` — `complete`, `probe`, `catalog`, `describe`;
      lift `call_api` and `read_api_catalog` from the bridge and `discover.py`.
- [ ] `llm/failures.py` — keep `from_status`; add Anthropic error-body codes.
- [ ] `tools/bridge/tutor-bridge.py` — new file: the HTTP server, CORS, `config.json`,
      `candidate_keys` (extended to `OPENAI_API_KEY`, `GOOGLE_API_KEY`), `/health`, `/ask`.
      Every call goes through `coursekit.llm`.
- [ ] Delete `call_api`, `call_cli`, `flatten`, `cli_argv`, `cli_works`, `verify_key`,
      `active_mode`, `CliFailed` from the bridge.
- [ ] `tools/bridge/claude-bridge.py` — reduce to a shim importing `tutor-bridge.py`; update
      `start-bridge.bat` and `tools/bridge/README.md`.
- [ ] `/health` reports `{providers: [{name, label, kind, ready, keySource}], ready}` instead
      of `{cli, has_key, key_source}`; keep the old fields for one release.
- [ ] Tests: the bridge answers through a stubbed provider; a 429 becomes `why: "quota"`;
      the two-provider chain falls through correctly.

## Phase 4 — OpenAI, Gemini, and a generic CLI

- [ ] `platform/coursekit/llm/openai.py` — Chat Completions; system as a `system` message;
      `choices[0].message.content`; `Authorization: Bearer`; base URL from settings so the
      same adapter serves Ollama, LM Studio, vLLM, OpenRouter, Groq and Azure.
- [ ] `platform/coursekit/llm/gemini.py` — `generateContent`; `systemInstruction`;
      `contents[].parts[].text` with `assistant` → `model`; `x-goog-api-key`.
- [ ] `llm/failures.py` — OpenAI (`insufficient_quota`, `invalid_api_key`, `model_not_found`,
      `rate_limit_exceeded`, `context_length_exceeded`) and Google (`RESOURCE_EXHAUSTED`,
      `PERMISSION_DENIED`, `NOT_FOUND`, `UNAVAILABLE`) patterns.
- [ ] `llm/cli.py` — argv from the provider's `command` / `args` / `modelFlag` / `promptOn`
      settings; Claude Code becomes one configuration among several.
- [ ] Tests: one round-trip per wire format against a stubbed `urlopen`; the shared retry and
      chain logic behaves identically across all four kinds.

## Phase 5 — Discovery, per provider

- [ ] Move `read_cli_catalog`, `read_cached_catalog`, `parse_cli_catalog`, `CLI_SELECTOR`,
      `CLI_CATALOG` into `llm/cli.py` as its `catalog()`; return "could not be read" for a
      binary that is not Claude Code.
- [ ] `catalog()` on the `anthropic`, `openai` and `gemini` providers.
- [ ] `studio/discover.py` — `sources()` asks every enabled provider; `plan` and `removals`
      keyed by provider; a provider whose sources all failed yields no removal candidates.
- [ ] `state/models-discovery.json` gains `provider` on every row; the settings-page report
      shows it.
- [ ] Tests: the existing `plan` / `removals` cases still pass with a provider key; a failing
      provider never shrinks another provider's models.

## Phase 6 — Studio UI

- [ ] `catalog.state()` — the `claude` block becomes `llm`
      (`{available, providers, model, models, defaultModel}`); keep `claude` as an alias for
      one release so an unrebuilt page still boots.
- [ ] `server.py` — `NO_CLAUDE` → `NO_PROVIDER`, sentence from the provider's label;
      `_claude()` guard → `_provider()`; docstring route table updated.
- [ ] `ui/js/31-models.js` — a provider column in the model-list editor; add-a-model picks its
      provider; the Test button says which provider refused.
- [ ] `ui/js/30-settings.js` — per-provider cards: enabled, endpoint, key state
      (`(set)` / empty), Test.
- [ ] `ui/js/28-model.js` — `modelChoice` / `modelBrief` group by provider when more than one
      is enabled; `quickModelBar` likewise.
- [ ] `ui/js/00-core.js` — the status pill names the configured provider, not "Claude Code".
- [ ] `ui/js/10-library.js`, `20-course.js`, `25-figures.js`, `26-media.js`, `27-notebooks.js`,
      `40-job.js` — replace every "Claude" with the provider label or "the model".
- [ ] Tests: `page_smoke.js` over `ui/js/*.js` still boots; every route in the docstring
      resolves.

## Phase 7 — The course page

- [ ] `SETTINGS.page()` — add `providers` (enabled and direct-callable only, never a key);
      keep `apiUrl` / `apiVersion` for one release.
- [ ] `platform/web/js/14b-wire.js` — new: `WIRE.anthropic`, `WIRE.openai`, `WIRE.gemini`,
      each with `request`, `reply`, `problem`.
- [ ] `platform/web/js/14-conn.js` — `callAnthropic` → `callDirect(provider, …)` through
      `WIRE`; `TROUBLE_BY_STATUS` stays (it is the JS twin of `from_status`);
      `adoptStudioModels` reads the new `llm` block.
- [ ] `platform/web/js/01-state.js` — `bridge.keys` map; `upgrade()` moves an old
      `bridge.key` into `keys.anthropic`; `connDefaults()` updated.
- [ ] `platform/web/js/19-settings.js` — connection card rewritten around providers: pick one,
      paste its key, Test; the Claude-Code / bridge path becomes one provider among them.
- [ ] `platform/web/js/17-rail.js`, `08-quiz.js`, `07b-gaps.js`, `17c-learner.js`,
      `00-dom.js` — every user-facing "Claude" becomes "the tutor" or a resolved label;
      `HELP.tutor` and `HELP.verdict` rewritten.
- [ ] Tests: `rail_checks.js` and `learner_checks.js` still pass; a saved model id no longer
      in the list falls back to the default.

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
