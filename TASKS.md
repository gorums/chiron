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

## Phase 5 — one product: UX/UI review (2026-09-09)

Findings, file:line anchors and the vocabulary in `UX-REVIEW.md`. Order matters: 5a fixes
bugs, 5b builds the shared system the rest is written in. Every task ends with both suites,
prettier, and `page_smoke.js` on both surfaces.

### 5a — bugs found by the review

- [x] U5.1 Duplicate `id="readbar"`: rename the module bar `#readpct` (`shell.html`, `07-module.js:145,414`, `20-keys.js:101`)
- [x] U5.2 `ico("spark")` undefined → add `spark` to `ICON_PATHS` (`02-helpers.js:361`, `17-rail.js:365`)
- [x] U5.3 Palette results land on the item: section → `jumpToPassage(mid, sec)`, glossary → `glossFilter`, model → open card (`13-palette.js:56-69,124-130`)
- [x] U5.4 Sections tick when scrolled past the reading band; Read hint says so (`07-module.js:319-335,148`); `rail_checks.js` case
- [x] U5.5 Render `.scrim` for the slide-over sidebar and the rail on narrow screens; tap closes; lock body scroll (`21-boot.js:36`, `03-chat.css:562,972`)
- [x] U5.6 Chat send: Enter inserts a newline, Ctrl/Cmd+Enter sends, hint and help agree (`17-rail.js:294,304`, `13-palette.js:179`)
- [x] U5.7 Sending while disconnected keeps the draft and shows the warnbar's Connect (`17-rail.js:560-566`)
- [x] U5.8 Clickable `div`s become `<button>`/`<a>`: library cards, mastery chips, flashcard, marks (`11-library.js:7-23,79`, `10b-plan.js:226`, `09-review.js:73`, `16-selection.js:86`)
- [x] U5.9 `--on-accent` token; every `#fff`-on-accent/ok/warm rule uses it in both themes (`02-content.css:403,411,419`, `03-chat.css:12,165`, `04-practice.css:71,76`)
- [x] U5.10 Studio ≤720px: ☰ menu with Courses / New course / Settings; search icon ≤900px; header `flex-wrap` (`studio.css:117,813,1036`)
- [x] U5.11 Approval gate is unmissable: "Waiting for your approval" eyebrow with `.pulse` in the waiting head, tab title, header pill refreshed on `await`, `Notification` when permitted (`40-job.js:232,273-276,350,698`)
- [x] U5.12 Define `.card.tight` and `.disabled` (anchors locked by `busy()`) in Studio's CSS until 5b shares them (`00-core.js:101`)
- [x] U5.13 Settings-tab grids collapse on narrow: `.row.r2 / .parts / .ms` classes instead of inline `grid-template-columns` (`20-course.js:397-427,465`)
- [x] U5.14 Remove profile needs an inline confirm like remove module (`00-core.js:289`, `30-settings.js:38`)

### 5b — one design system, served to both

- [x] U5.15 `web/css/00-tokens.css`: palette (both themes), shadows, fig colours, fonts, `--s1..--s6`, `--fs-xs/sm/md/base`, `--radius-xs`, `--on-accent`, `--overlay`; `--muted` darkened to ≥4.5:1 on `--bg`
- [x] U5.16 `web/css/01-base.css` = the shared primitives: reset, `:focus-visible` (one ring, 6px radius), `.btn` family (`.btn` outlined · `.primary` · `.ghost` · `.sm` · `.danger` · `.warm` · `.iconbtn` · `:disabled`/`.disabled`), form block (Studio's superset: label, `.hint`, text/number/select/textarea, `.field`, `.row`), `.card(.tight/.raised)`, `.eyebrow`, `.sub`, `.lede`, `.tag(ok/warn/bad/acc/stale)`, `.pill(.on/.off/.live)`, `.badge`, `.bar-track/-fill`, `.note`, `.problems`, `.toast(.bad)`, `.chip`, `.menu[role=menu]`, `.empty`, `.spin/.pulse` + reduced motion, `.ic`, `.topbar`, `kbd`, `.mono`, `.hidden`
- [x] U5.17 Studio links the shared files: `server.py` serves `web/css/00-tokens.css`, `01-base.css` and `web/js/00-dom.js` under `/ui/shared/`; `studio.css` keeps layout only (target ≈800 lines); `bundler` inlines the same files into the page
- [x] U5.18 `web/js/00-dom.js`: `$`, `$$`, `esc`, `toast(msg, {kind, sticky})` with `role=status` and duration ∝ length, `ico`, `ago`, `fmtH`, `clock`, `help(term)`; delete the copies in `00-core.js:64-136` and `02-helpers.js`
- [x] U5.19 Studio buttons re-classed to the shared vocabulary: one `.primary` per region (Plan / Design and write / Rebuild-when-dirty / Approve); Check, Build, Test, Save the list, Export become `.btn`; Resume `.btn.warm` (no inline background); danger stays `.danger`
- [x] U5.20 Reader buttons: one primary per region (footnav non-primary until `stepDone`, Apply 3→1, Home ≤2); danger via `.btn.danger` not inline colour; the 10 inline serif headings → `.h-serif`; the big-score block shared by quiz and checkpoint
- [x] U5.21 Reader `.pill` → `.badge`; Studio `.verdict.*` → `.tag.*`; Studio `.today` chips → `.chip`; Studio `.sub` → shared `.sub` + `.lede`, drop the ~30 inline `margin:0`/`font-size` overrides
- [x] U5.22 Studio's Unicode glyphs (◐ ⋯ ▲ ▼ × › +) → shared `ico()` set (menu, search, theme, more, up, down, close, check, spark, plus)
- [x] U5.23 One theme key `platform_theme` read by Studio and a served page; the page falls back to `S.theme` off disk; `S.ui.motion` honoured by Studio too
- [x] U5.24 Inline `style=` purge: reader 387 → under 60, Studio 143 → under 30, via `.result`, `.stack`, `.row.settings`, a `select` rule, spacing tokens
- [x] U5.25 Guards in `TestCodeConventions`/`TestServerConventions`: no hex outside `00-tokens.css`; no `font-size: Npx` outside the scale; every class used in `web/js` and `ui/js` exists in the served CSS; no `.btn` variant outside the list; inline `style=` count ceiling per tree

### 5c — navigation and wayfinding

- [x] U5.26 Reader: `<header>`, `<main>`, `<nav aria-label="Course">` with `<a href>` items and `aria-current="page"`, labelled asides (`shell.html`, `05-sidebar.js:16-31`)
- [x] U5.27 Step keys in URLs (`#/m/M03/quiz`), numeric accepted for old links; step pills carry `title` from `STEPS[i].d` (`04-router.js:8`, `07-module.js:69`)
- [x] U5.28 Prev/next show `id · short title` with the full title in `title`; `j/k` off a module go to the next unfinished module (`07-module.js:74,76`, `20-keys.js:96`)
- [x] U5.29 First-visit "How this course works" card (six steps, mastery, practice deck, checkpoints; `S.ui.introSeen`) and a "How it works" section in the `?` modal (`06-home.js:17`, `13-palette.js:164`)
- [x] U5.30 Dead ends: review "Session complete" offers Fix mistakes / Next module; `#/plan/*` and `/resources` get a heading; worksheet page links back to its module's Apply step; unknown module id toasts (`09-review.js:60`, `11-library.js:32,98`, `07-module.js:48`)
- [x] U5.31 "All conversations" opens Marks on the chats filter (`17-rail.js:440`)
- [x] U5.32 Studio nav active on every route (Courses for course/edit/search/job); crumbs always reach the parent, the job crumb links its course while running, the editor crumb shows the title (`00-core.js:351`, `40-job.js:619,674`, `30-settings.js:165`)
- [x] U5.33 `#/jobs`: the recent 12 with status, duration, course link; hero shows "Last run: failed 3 min ago — view"; no boot teleport to a live job, a banner instead (`00-core.js:198-212,381`)
- [x] U5.34 Claude pill links to `#/settings`; when not found, a library banner with the two steps (install, `claude login`); "+ Write a course" is a real disabled button with the same sentence (`index.html:27`, `10-library.js:100`, `30-settings.js:44`)
- [x] U5.35 One `claudeGate()` that renders the reason once per screen instead of silent `disabled` (`20-course.js:144,641`, `25-figures.js`)
- [x] U5.36 Zero-course library = first-run hero (Write your first course / Bring one in), calendar and today strip hidden (`10-library.js:103-120`). **The review's second half was reverted:** "Bring a course in" went behind a `<details>` below the grid and cloning a course from GitHub became a grey triangle nobody would find. It is a way of getting a course, so it is back in the grid as a peer of "New course"
- [x] U5.37 "Manage profiles…" leaves the `<select>`; a settings link beside it; the select keeps a visible label under 1200px (`00-core.js:247`, `studio.css:1359`)
- [x] U5.38 Export stays available during a job; Check/Build disabled with a reason; error states get a crumb and Try again (`20-course.js:15,51-58`, `00-core.js:392`)

### 5d — explain at the point of use

- [x] U5.39 `HELP` glossary in `00-dom.js` (mastery levels, freeze, mistake card, calibration, checkpoint, compact, verdict scale, patch vs rewrite, resume, stale, candidate model, profile, anchor, practitioner, curriculum, module design) and `help(term)`; every place a term is printed carries it as `title` or `.hint`
- [x] U5.40 Reader: `MASTERY_HELP` on every dot, chip and legend row; Retrieve step gets its "Why" hint; streak freeze, mistake card and Compact explained where shown (`05-sidebar.js:25`, `08-quiz.js:50,69,239`, `10b-plan.js:103`, `17-rail.js:295,439`)
- [x] U5.41 Reader: names and states on icon controls — section tick and bookmark `aria-pressed`, menu button `aria-expanded`, theme button announces the current theme, convo switcher `aria-haspopup/expanded`, `.dotstat`/`.dot` get text or `aria-label`, reorder arrows labelled (`07-module.js:154,157`, `shell.html:14,21`, `17-rail.js:332-333`, `08-quiz.js:155`)
- [x] U5.42 Reader: every input and textarea has a label (19 today) — rail box, plan form, anchor, settings, notes
- [x] U5.43 Reader Settings: title "Settings"; key/bridge prose only off disk; Studio mode says how the tutor is connected; `#setmodel` gets `data-model-pick` and goes through `setTutorModel` (`19-settings.js:7,22-61,66`)
- [x] U5.44 Studio forms: hints under Hours ("about one module per hour"), Practitioner ("the noun for someone who does this"), Notebooks yes/no, Tutor persona, Milestones; anchor / parts / milestones rows get column headers instead of placeholder-labels (`10-library.js:307-330`, `20-course.js:397-433,465`)
- [x] U5.45 Studio verdicts: `title` with the three-line scale, a legend above the module list on first sight, "before edit" explained inline (`20-course.js:129-134`)
- [x] U5.46 Modules tab: the three prose cards become one toolbar row (Model · Figures 12/20 Draw · Notebooks 0/20 Write) with `title`s; the prose behind `<details>` (`28-model.js:71`, `25-figures.js:22`, `27-notebooks.js:28`)
- [x] U5.47 Settings & logs: platform table gets a description column and a source legend; "Clear view" → "Clear log buffer (file kept)"; "the platform's list" → "the built-in list" (`30-settings.js:62,82`, `31-models.js:265`)
- [x] U5.48 Plan gate: live total minutes vs requested hours, undoable Skip instead of drop, "+ module" per part, what reload does (`40-job.js:799-827`)

### 5e — every action answers

- [x] U5.49 Toast kinds: `ok` / `bad` (red, sticky until dismissed) / `info`; `role=status`; max-width; used by both surfaces (`00-core.js:96`, `02-helpers.js:344`, `index.html:33`)
- [x] U5.50 Reader grader and gap errors inline in the reply box with Retry; original button label kept on failure; `finishRoleplay` locks while waiting (`17b-grader.js:98-104,151-157,195,255-261`, `07b-gaps.js:126-132`)
- [x] U5.51 Reader confirms: restore, abandon checkpoint, retake, uncheck all, disconnect; danger dialogs focus Cancel (`12-backup.js:32`, `09b-checkpoint.js:115`, `08-quiz.js:435`, `07-module.js:146`, `19-settings.js:227`, `13-palette.js:19`)
- [x] U5.52 Reader boot skeleton while `profileInit` + `syncPull` run; `refreshLearner` does not repaint a screen with a focused input (`21-boot.js:53`, `17c-learner.js:526`)
- [x] U5.53 Studio "changed since build": server reports `dirty` (file mtimes vs `builtAt`); hero pill + Rebuild becomes the primary; Save settings offers Save / Save and rebuild without a full repaint (`20-course.js:64,438,508`)
- [x] U5.54 Move / remove / apply results render under the affected part; Resume form gets its own slot so Check/Build cannot wipe it (`20-course.js:229-237,318-323,709-748`)
- [x] U5.55 `busy()` on every request: git clone, review, figures, notebooks, rewrite, resume, model Test, Check now; spinner inside the button; card Build locked against double click (`10-library.js:195,269`, `31-models.js:313,349`)
- [x] U5.56 Stop confirms for a generate run (with the resume hint) and disables itself; review-done opens the review box via `&review=<mid>`; model Test shows the error text inline; Delete sends one toast (`40-job.js:755,868`, `20-course.js:204,576`, `31-models.js:357`)
- [x] U5.57 Validator problems link their file path to `#/course/<id>/edit?path=` (`20-course.js:737-762`)

### 5f — accessibility and layout

- [x] U5.58 Dialogs: `role=dialog aria-modal`, focus trap, focus return, Esc closes the chat menu too; the modal guard runs before single-letter shortcuts (`13-palette.js:2-30`, `20-keys.js:5-42`)
- [x] U5.59 Studio tabs `role=tablist/tab/tabpanel` with arrow keys; row menu with up/down keys and focus return, `<select>` moved out of it; reorder targets ≥28px (`20-course.js:80,137,270-295`, `studio.css:1127`)
- [x] U5.60 Headings: `<h3 class="eyebrow">` for card titles on both surfaces; `role=log` on the activity and log boxes, autoscroll only when already at the bottom (`40-job.js:681`)
- [x] U5.61 Contrast pass: `.parthead .ph`, `.sec.done .prose` opacity, `--muted` at ≤13px, dark `#fff` rules (with U5.9); a contrast check in the test suite over the token pairs used at ≤13px
- [x] U5.62 Reduced motion honoured by JS scrolls (`matchMedia`) in the reader and by Studio's bar/toast transitions (`07-module.js:401`, `07d-audio.js:238`)
- [x] U5.63 Container queries for `.g2/.g3/.g4` and `.setrow` so grids follow `#main`, not the viewport; `.parask` no longer overlaps ≤1080 (`03-chat.css:281,918-959`)
- [x] U5.64 Rail resize grip works with keyboard and touch; dock buttons ≥32px (`17-rail-layout.js:109`)
- [x] U5.65 Tables keep semantics: wrap in `overflow-x:auto` instead of `display:block` (`02-content.css:307`)
- [x] U5.66 Studio narrow: `.modrow` grid fits four children, `.menu` never leaves the viewport, `.figbar` wraps, editor wrap toggle, editor Esc-then-Tab hint (`studio.css:784,809,1408,1479`, `30-settings.js:183`)
- [x] U5.67 New-course and add-module forms are real `<form>`s (Enter submits, one submit handler) (`10-library.js:300`, `20-course.js:600`)

### 5g — one vocabulary

- [x] U5.68 Apply the table in `UX-REVIEW.md` §D across both surfaces: tutor/Claude/Claude Code/model; Practice / Fix mistakes / Retrieve; Your gaps; Rebuild; Stop/Cancel; Mark as good/Unmark; Patch or rewrite…; curriculum/design; "needs fixing"; `KIND_LABELS` for job kinds (`00-core.js:176`)
- [x] U5.69 Subject-flavoured copy out of the engine ("cost you money", "in front of a client") → neutral or `CFG` (`08-quiz.js:402`, `09b-checkpoint.js:160`); extend the leak test with the words found
- [x] U5.70 `CLAUDE.md`: the shared-system section (what lives in `00-tokens` / `01-base` / `00-dom`, how Studio consumes them, the vocabulary), the section-tick rule as implemented, the new guards

### 5h — verify

- [x] U5.71 Both suites, prettier, `page_smoke.js` on the page and on Studio, `rail_checks.js` / `learner_checks.js` / `audio_checks.js`
- [~] U5.72 Browser pass — done at 1440 in dark on the Studio-served pair: library, course page (hero, toolbar, module rows), recent runs, settings & logs, reader dashboard with the first-visit card, a module's Read step with the rail docked, reader Settings, Progress. A stray vertical scrollbar on the tab strip and a full-width new-profile field were found and fixed. **Still to do by a person: 1024 and 390px, light theme, the plan gate and a running job, the editor, checkpoint and marks**
- [m] U5.73 Keyboard-only pass: every route, every dialog and menu, Tab never escapes an open modal, focus visible everywhere

### What Phase 5 changed

- **One design system, three files.** `web/css/00-tokens.css`, `web/css/01-base.css` and
  `web/js/00-dom.js` are now the whole vocabulary; Studio links them at `/ui/shared/`
  (`SHARED_UI` in `server.py`) instead of keeping a copy. `studio.css` went from 1 491 lines
  to layout only; the reader's shell moved to `web/css/01b-shell.css`.
- **`.btn` means one thing.** Outlined by default, `.primary` filled, one per region. Every
  Studio button was re-classed; `.verdict.*` became `.tag.*`; the reader's `.pill` became
  `.badge`.
- **Inline styles:** reader 387 → 25, Studio 143 → 3. Five guards in `TestCodeConventions`
  hold the system: no colour outside the token file, no font size off the scale, no `.btn`
  variant without a rule, no class used with no rule behind it, and a ceiling on inline
  `style=`.
- **`help(term)`** puts the platform's own words — mastery, freeze, mistake card,
  calibration, verdict, patch, resume, stale — where they are printed.
- Two bugs found in the browser pass and fixed: the course page's tab strip grew a vertical
  scrollbar over a 1px overflow, and the new-profile field on the settings page stretched
  the full card width.
- One instruction from the review reversed after use: U5.36 put "Bring a course in" behind a
  disclosure, which hid cloning from GitHub. Restored to a card in the grid.

**One known failure, not from this phase.** `rail_checks.js` fails against the `aba` course
at "after the reveal it is": that course's model answer is 1 414 characters and
`PLACE_TEXT_CHARS` (2 400, a literal in `17a-place.js`) cuts it out of the Apply prompt.
The check passes against the fixture the suite builds and against `marketing`.
`17a-place.js` is untouched by Phase 5. Worth its own task: move that cap into
`settings.json` like every other limit, and give the model answer room.
