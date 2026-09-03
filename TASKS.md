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

## Phase 4 — UI review (2026-09-03)

Found in a code-and-browser pass over the reader (`platform/web/`) and Studio (`platform/studio/ui/`).

### Reader

- [x] U4.1 Rail open crushes the reading column: at 1350px the prose gets ~225px (`page.ui.readMin` 420, TOC grid ignores width). Raise `readMin`, hide the TOC below a container width, stop the search button wrapping
- [x] U4.2 Three different "time studied" numbers (sidebar ring counts finished modules; stats counts the timer; the timer keeps running while idle). Pause the timer after idle; show real time in the sidebar
- [x] U4.3 Subject leak: "practice business" / "Your business…" / clinic placeholder hardcoded in `06-home.js`, `07-module.js`, `17-rail.js`, `17b-grader.js`. Move to a `CFG.anchor` block from `course.json`, with a neutral default
- [x] U4.4 Dashboard repeats itself: Today card and Continue card both say "Continue M01"; the subtitle points at an input five cards down. Merge; move the anchor input into Settings
- [x] U4.5 No `:focus-visible` on buttons, links or chips anywhere — keyboard users cannot see focus. Add one rule
- [x] U4.6 Native `confirm()` / `prompt()` for delete conversation, rename, erase progress, clear worksheet. Use the existing modal host
- [x] U4.7 Section ask/bookmark and paragraph ask buttons are `opacity:0` until hover — invisible on touch. Show faintly always, fully on hover or `(hover:none)`
- [x] U4.8 Rail header is crowded: truncated title plus five icon buttons with dock glyphs nobody reads. Dock choice stays in Settings only
- [x] U4.9 Sidebar has 11 nav items plus the module list and a legend below the fold. Regroup; move Backup / restore into Settings; put the legend where it is seen
- [x] U4.10 Unicode glyph icons (◈ ↻ ◔ ▤ ✦ ◎ ✎ ⚙ ⇅ ⌂ 🗑 ⤳) render differently per OS. Replace with a small inline SVG set
- [x] U4.11 The floating "Ask Claude" button covers the quiz's Next button on short viewports. Move it into the topbar
- [x] U4.12 Stats page before any data is six cards of dashes. Show one empty-state card until there is something to measure
- [x] U4.13 Template tells: tracked ALL-CAPS eyebrows on every card, "→" appended to most buttons, identical shadowed cards. Sentence-case labels, drop the arrows, one raised card per page

### Studio

- [x] U4.14 Every `<a class="btn">` is underlined (Start, Manage, Read, Edit) — `.btn` never sets `text-decoration`
- [x] U4.15 Primary button is white text on the mint accent in dark mode (about 2:1). Reader already overrides this; Studio does not
- [x] U4.16 The remove "×" has the same weight as Read / Edit / Rewrite on every module row. Make it quiet until hover
- [x] U4.17 Library card says "Start →" for a course that is in progress (`courseCard` checks `done` only) while the Today strip says "in progress"
- [x] U4.18 Every tab switch refetches the course and paints "Loading…". Paint from `courseCache` first, refresh in the background
- [x] U4.19 Cards show progress three times: "0%" eyebrow, bar, "0 of 19 modules". Keep the bar and one line
- [x] U4.20 Today strip lists "M01 in progress" for every course that has been opened once. Only list modules actually under way
- [x] U4.21 Brand subline shows the container path (`/work`). Remove; it is on the Settings page
- [x] U4.22 Settings & logs model card reads like a developer note (`[1m]`, `unrecognized_model`). Plain copy; details in `CLAUDE.md`
- [x] U4.23 Editor: Save / Save and check, then back to the course page to build. Add "Save, check and build"
- [x] U4.24 Same template tells as the reader: caps eyebrows, arrows on buttons, uppercase file-group labels

## Phase 3 — the library grows (2026-09-03)

- [x] P3.1 Reorder / move modules: optional `order` list in `course.json`, honoured by `loader.module_files` (the build) and `server._module_ids` (the listing) alike; `manage.move_module` moves the file between part folders and rewrites `order`; `POST /api/courses/<id>/modules/<mid>/move {part, index}`; ▲▼ and a part select on every module row
- [x] P3.2 Cross-course search: `studio/search.py` parses every course with the build's loader and matches titles, headings, passages and glossary terms, ranked by where the hit landed; `GET /api/search?q=`; a search box in the Studio header and a `#/search?q=` results page with Read / Rewrite links
- [x] P3.3 Reader profiles: `progress.Store(dir, profile)` — the default profile keeps `state/progress/<id>.json`, every other one gets `state/progress/<profile>/`; the active profile is a Studio preference (`prefs.profile`); `GET/POST /api/profiles`; a "Reading as" picker in the header and a profiles card in Settings; a served page asks `GET /api/profile` on boot, keys its localStorage by profile, and names its profile on every sync so a switch in Studio cannot write one reader's state into another's file (409)
- [x] P3.4 Study calendar across courses: `summarise` exposes the days each course was studied; `server.calendar` unions them into a 17-week heatmap and a cross-course streak on the library page, coloured warm on a day with more than one course
- [x] P3.5 Export / import as zip: `transfer.export_zip` (without `.git`) behind `GET /api/courses/<id>/export`; `transfer.import_zip` behind `POST /api/import` (base64 body, zip-slip safe, refuses a taken id, builds if consistent); drop zone on the library page
- [x] P3.6 Import from a git repository: `transfer.import_git` shallow-clones an https:// or git@ URL into a staging folder, renames it to the id in `course.json`, keeps `.git` so the course stays a repository; `POST /api/import/git`; the Clone box is disabled when git is missing
- [x] P3.7 "Review this module": `prompts.review` + `generator.review` ask Claude for a verdict, gaps, errors, quiz issues and a rewrite brief, coerced by `_fix_review` and stored in `state/reviews/<course>/<mid>.json`; `POST /api/courses/<id>/modules/<mid>/review` runs it as a job; the module row shows the verdict, the findings unfold beneath it, and "Rewrite with these notes" prefills the rewrite form
- [x] P3.8 Tests for all of the above in `TestPhase3` (order, move, profiles, calendar, search, zip round trip and refusals, git URL gate, review coercion); docs in `CLAUDE.md` and the `server.py` route list
