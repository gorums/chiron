# Tasks

Status: `[x]` done · `[~]` in progress · `[ ]` open · `[m]` manual, needs a person.
See `PLANNING.md` for the why.

## Phase 1 — platform, not file viewer

- [x] P1.1 Progress store (`studio/progress.py`), `GET/PUT/POST /api/courses/<id>/progress`, device keys stripped
- [x] P1.2 Course page syncs progress when served by Studio (`STUDIO` detection, pull before first paint, debounced push, `sendBeacon` on unload)
- [x] P1.3 Library cards with percent, done/total, minutes, cards due, last studied, Continue deep link
- [x] P1.4 Course page: modules by part with progress, Read / Edit / Rewrite, Add a module, Files editor, Check / Build
- [x] P1.5 `generator.extend` — design a fitting module, next free id, own data files, short title, rebuild
- [x] P1.6 `generator.rewrite` — same id/file, direction from notes, data replaced in place
- [x] P1.7 Module footer links into Studio (add / rewrite)
- [x] P1.8 `POST /api/ask` — tutor through Studio on the same origin; `connMode()` "studio"
- [x] P1.9 Bridge: prompts on stdin from a scratch cwd
- [x] P1.10 Engine leak: `30h` → `CFG.hours` in sidebar and home
- [x] P1.11 Studio UI hash-routed; job screen handles generate / extend / rewrite
- [x] P1.12 Tests: progress store, extend pipeline (Claude stubbed), path confinement, chat prompt (60 total)
- [x] P1.13 Docs: `CLAUDE.md`, `README.md`, `.gitignore` (`state/`)
- [x] P1.14 Visual pass in Chrome on the Docker-served Studio — found and fixed an empty Read step (renderStep call displaced by the footer edit) and a rail that did not repaint after Studio was detected
- [m] P1.15 One real `extend` run against `sourdough` to exercise the live Claude path

## Phase 2 — manage a course end to end

- [x] P2.1 Course settings form: `POST /api/courses/<id>/settings` (title, tagline, audience, practitioner, tutorPersona, milestones); `id` locked; Settings tab in Studio
- [x] P2.2 Remove a module: `manage.remove_module` (file + data entries + short title), `POST /api/courses/<id>/modules/<mid>/remove`, inline confirm in UI, then check
- [x] P2.3 Delete a course reversibly: move `courses/<id>` and `dist/<id>` to `state/trash/<id>-<stamp>/`; `POST /api/courses/<id>/delete`; typed-id confirm in UI
- [x] P2.4 Open questions tab on the course page from `state.marks` (status `open`), with "Make this a module" prefill and "Rewrite with this" prefill
- [x] P2.5 Extend from a section: module footer link carries `sec=<heading>`; Add-a-module notes mention it
- [x] P2.6 Backup / restore from Studio: download `state/progress/<id>.json`, paste to restore (`PUT progress`), with a note that it replaces the platform copy
- [x] P2.7 Durable job history: finished jobs written to `state/jobs/<id>.json`; `/api/state` lists them; `/api/jobs/<id>/events` replays from disk when not in memory
- [x] P2.8 Library "today" strip: cards due and modules in progress across courses, each linking into the course
- [x] P2.9 Tests for P2.1–P2.7 (settings validation, remove cleans all three places, delete moves rather than deletes, job persistence round-trip)
- [x] P2.10 Docs: routes in `server.py` docstring and `CLAUDE.md`; `README.md` feature list
- [x] P2.11 Verification: both suites (27 + 69), HTTP smoke (29 checks), `node --check`, leak grep, rebuild both courses
- [x] P2.12 Visual pass of the new tabs (Questions, Settings) and the today strip in a browser; progress sync confirmed live

## Phase 2b — after the first real run failed

- [x] P2b.1 Diagnose: run died at M08 study data with `unrecognized_model` — the CLI inherited the interactive default `claude-fable-5-1[1m]`, which headless mode rejects
- [x] P2b.2 Every CLI call names a model: `claude_cli.model_chain()` (requested → Studio default → bare CLI); default `sonnet`, env `STUDIO_MODEL`
- [x] P2b.3 Studio-wide preferences (`prefs.py`, `state/studio.json`), `GET/POST /api/settings`, model choice in the UI
- [x] P2b.4 Logging (`log.py`): rotating `state/logs/studio.log` + ring buffer; every Claude call, job event and route error; `GET /api/logs`, `POST /api/logs/clear`
- [x] P2b.5 **Settings & logs** page (`#/settings`): model, Claude status, paths, live log viewer with level/filter/follow; linked from the course Settings tab and the failed-job screen
- [x] P2b.6 Resume a dead run: plan saved to `plan/plan.json`, `reconstruct_plan()` for older courses, `POST /api/courses/<id>/resume`, button on the course page and the failed-job screen
- [x] P2b.7 Tests: model chain, prefs, log filters, resume keeps-and-fills, plan reconstruction (74 total); smoke test extended
- [x] P2b.8 Resumed the real `aba` run: kept M01–M08, wrote M08 data, M09, shelf, plan docs, 9 worksheets; built clean (9 modules, 63 sections)

- [x] P2b.9 "The server sent something unreadable" on Rebuild: handlers that ignored the request body left it on the keep-alive connection and corrupted the next request. Body is now drained once per request; keep-alive regression check in the smoke test; check/build log a line
- [x] P2b.10 Resume refuses a course that is complete and consistent

## Phase 3 — later

- [ ] P3.1 Reorder / move modules between parts (ordering metadata in `course.json`)
- [ ] P3.2 Cross-course search in Studio
- [ ] P3.3 Reader profiles in `state/`
- [ ] P3.4 Study calendar / streak across courses
- [ ] P3.5 Course export/import as zip
- [ ] P3.6 "Review this module" pass by Claude before the reader finds the gap
