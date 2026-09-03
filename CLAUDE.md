# Course platform

A generic engine for building interactive study courses. You describe a theme and an hour
budget; the `course-author` skill writes the course; `platform/build.py` renders it into one
self-contained HTML file that tracks progress, runs spaced repetition, and lets the reader
ask Claude about whatever passage they are looking at.

The marketing course is the reference implementation. It was the original project; the
platform was extracted from it, and it now lives in its own repository like every course.

## Two kinds of repository

**This repository is the platform. A course is never committed here.** Each course is its
own git repository; the platform only needs the directory that holds the clones. That
directory is resolved once, in `platform/coursekit/paths.py`, and both entry points read it:

| | |
|---|---|
| `COURSES_DIR` environment variable | wins |
| `COURSES_DIR=` line in `.env` at the repo root | the same file compose reads |
| `<repo>/courses/` | the default, gitignored, a place for clones |

`DIST_DIR` resolves the same way and defaults to `<repo>/dist/`. A relative value is taken
from the repo root, so `COURSES_DIR=../courses` means a sibling folder on every machine.
`python platform/build.py where` prints what was resolved.

Consequences:

- `courses/` is in `.gitignore`. Cloning a course into it, or `git init` inside a folder
  Studio just generated, is the whole workflow. Nested repositories under an ignored
  directory are invisible to this one.
- A new course gets a `README.md` from `scaffold.write_readme` so the folder reads as a
  repository of its own. It is never overwritten.
- A course can also arrive as a zip (`POST /api/import`, the drop zone on the library page)
  or be cloned from a git URL (`POST /api/import/git`); `studio/transfer.py` renames the
  folder to the id in its `course.json`, because the folder name *is* the course id
  everywhere in Studio, and refuses to overwrite an existing one. `GET /api/courses/<id>/export`
  is the reverse: the folder as a zip, `.git` left behind.
- `folderLabel` in `course.json` is now just the course id. Older manifests carrying
  `courses/<id>` still work; the field is only shown to the reader.
- Inside the container `COURSES_DIR` and `DIST_DIR` are set in the image to `/work/courses`
  and `/work/dist`, and compose mounts `${COURSES_DIR:-./courses}` at `/work/courses`. That
  is what keeps a host path written in `.env` from reaching the code.
- The tests never assume a course is present: `TestShippedMarketingCourse` skips when the
  marketing course is not in `COURSES_DIR`.

## Settings: one file, no literals

**Every default the platform has lives in `platform/settings.json`.** Ports and hosts, the
Anthropic endpoint and API version, the model list and the default model, every timeout,
the generation counts, the log rotation, and the page's study rules and layout sizes. No
module under `platform/` or `tools/` carries a literal of its own; it asks
`coursekit.settings.SETTINGS` (`SETTINGS.get("studio.port")`, `SETTINGS.models`,
`SETTINGS.bridge_url`, ...). The bridge imports the same module from outside the package,
which is why `settings.py` is stdlib-only.

Resolution, later layers winning:

| | |
|---|---|
| `platform/settings.json` | the committed defaults |
| `SETTINGS_FILE` | an optional JSON overlay, deep-merged: a different model list, longer timeouts |
| `.env` at the repo root | the scalar knobs in `settings.ENV_KEYS` (`STUDIO_PORT`, `BRIDGE_HOST`, `STUDIO_MODEL`, ...) |
| the environment | the same names, winning over `.env` |

An environment value is coerced to the type of the default it replaces, so `STUDIO_PORT`
becomes an int. `SETTINGS.overrides` records which layer supplied each overridden key;
`build.py where` prints them and the Studio settings page (`#/settings`) lists every
resolved value with its source. Studio's own preference file, `state/studio.json`, sits on
top of all of this for the one thing the UI edits: the model.

**The page gets its slice as `CFG.platform`.** `renderer.runtime_config` merges
`SETTINGS.page()` into the `CFG` the shell receives: the bridge address, the API endpoint
and version, the model list and default, and the `page` block (tutor budgets, sync timing,
study rules, rail sizes). `01-state.js` binds them to `PLATFORM`, `TUTOR`, `SYNC`, `STUDY`
and `LAYOUT`; a fresh state's connection block comes from `connDefaults()`. Do not write an
address, a model id or a limit into `platform/web/js/` - add a key to `settings.json` and
read it through `CFG.platform`. `test_build.py` fails on `api.anthropic.com`, a `claude-*`
id, `127.0.0.1` or a port literal in the front end, the way it fails on a subject word.

`paths.COURSES_DIR` and `paths.DIST_DIR` are the same mechanism: `paths.courses` and
`paths.dist` in `settings.json`, overridden by `COURSES_DIR` / `DIST_DIR`.

## Layout

```
platform/                   the engine — knows nothing about any subject
  build.py                  CLI entry point
  settings.json             every default of the platform; see "Settings" above
  coursekit/                the build package
  studio/                   the local web app: generate + build from a browser
  web/                      front-end source: shell.html + css/ + js/
  tests/                    test_build.py, test_studio.py, page_smoke.js (boots a built page under node)
courses/<id>/               one course = one separate git repository (gitignored here;
                            the directory itself moves with COURSES_DIR)
  course.json               the manifest that makes a folder a course
  modules/<part>/M01-*.md   the teaching
  plan/ reference/ templates/
  data/assessments/ data/suggestions/
dist/<id>/                  build output (generated — do not edit)
state/                      generated, gitignored, personal:
  progress/<id>.json        the platform's copy of a reader's progress (the default profile)
  progress/<profile>/       the same, for every other reader profile
  reviews/<id>/<mid>.json   what Claude found when asked to review a module
  jobs/<id>.json            finished generation jobs, replayable after a restart
  trash/                    removed modules and deleted courses — moved, never erased
  logs/studio.log           every Claude call and job event, rotating (2 MB × 3)
  studio.json               Studio-wide preferences: the model
tools/bridge/               local proxy so a course page can reach Claude
docker/Dockerfile           one image; Studio and the bridge differ only by command
compose.yaml                both services, restart: unless-stopped
.claude/skills/course-author/   the skill that writes a course from a brief
```

## Commands

```
python platform/build.py list                            what courses exist
python platform/build.py where                           which courses/ and dist/ are in use
python platform/build.py new --theme "X" --hours 30      scaffold an empty course
python platform/build.py check <id>                      validate; reports everything at once
python platform/build.py build <id>                      validate, then write dist/<id>/
python platform/build.py studio                          open Course Studio in a browser
```

Or double-click `start-studio.bat`. Studio is the UI route: it generates a course from a
theme and an hour budget, shows how far you are in each one, and edits, extends and rebuilds
a course without a terminal.

Tests:

```
python platform/tests/test_build.py      48 tests — engine (one boots the page under node, skipped without it)
python platform/tests/test_studio.py     80 tests — Studio
```

Requires Python 3 and the `markdown` package (`pip install markdown`). Nothing else.

## Running in Docker

```
docker compose up -d --build     start both, and on every boot from now on
docker compose logs -f studio    watch a generation run
docker compose down              stop them
```

Needs a `.env` holding `CLAUDE_HOME` — the path to the host's `~/.claude`. Copy `.env.example`.
The same file may set `COURSES_DIR`; compose mounts it at `/work/courses`. `STUDIO_PORT` and
`BRIDGE_PORT` there are read by compose *and* by the code, so the published port and the
one the service binds always agree.

**One image, two services.** Studio and the bridge need the same things — Python, and the
Claude Code CLI — so they share a build and differ only in the command. Two Dockerfiles would
be two things to keep in step.

**Nothing is COPYed into the image.** The repo arrives as a bind mount, so a course written
inside the container is a real file in the user's folder and editing `platform/` needs only a
restart. Rebuild only when `docker/Dockerfile` changes.

**`~/.claude` is mounted as a whole directory, never as a single file.** Claude Code refreshes
its OAuth token by writing a new file and renaming it over the old one, which silently breaks
a single-file bind mount. The mount is read-write because that refresh has to persist; the
container then behaves like any other Claude Code session on the account.

**Services bind `0.0.0.0` inside the container, and compose publishes to `127.0.0.1`.**
`STUDIO_HOST` and `BRIDGE_HOST` default to loopback in the code and are overridden only in the
image. Dropping the `127.0.0.1:` prefix from a `ports:` entry would expose a service that
writes files and spawns processes to the whole network. Do not.

**Claude Code runs from an empty scratch directory** (`claude_cli._SCRATCH`), not the repo.
It prompts to trust the directory it starts in, which would hang a headless call — worse in a
container, where the workspace is a bind mount it has never seen. Studio passes everything in
the prompt and asks the model to read nothing, so it needs no filesystem context.

### A course served by Studio is the primary way to study

A course opened at `http://127.0.0.1:8790/course/<id>/<output>-local.html` behaves differently
from the same file opened off disk, and every difference goes through one detection: the
`STUDIO` constant in `01-state.js`, set only when the page's origin is http(s) and its path is
`/course/<id>/…` for its own course id.

- **Progress syncs to the platform.** `save()` still writes localStorage, then debounces a
  `PUT /api/courses/<id>/progress`; `pagehide` flushes with `sendBeacon`. On boot `syncPull()`
  runs before the first render and the newer `updatedAt` wins, so the same course can be
  studied from two browsers. Device settings (`bridge`, `ui`, `theme`) never leave the
  browser — `progress.DEVICE_KEYS` strips them again server-side.
- **The tutor answers on the same origin.** `connMode()` returns `"studio"` when Studio
  reports Claude available and no API key is saved; `askBridge()` then posts to `/api/ask`,
  which flattens the conversation with `claude_cli.chat_prompt` and runs the CLI on stdin. No
  bridge, no key, no CORS. A saved key still wins: it is an explicit choice to pay per question.
- **The course can grow from inside.** The module footer links to Studio's course page with
  `?tab=add&from=<mid>` or `?rewrite=<mid>`.

The bridge remains the route for a page opened off disk (`file://`), where none of this
applies. It now also passes prompts on stdin from a scratch cwd, like Studio.

## The two-layer rule

**The engine must never mention a subject.** No "marketing", no "marketer", no course title.
Everything subject-specific reaches the browser through the `CFG` object built by
`CourseConfig.runtime()` in `platform/coursekit/config.py`, sourced from `course.json`.

If you are about to write a course-specific string into `platform/web/js/`, add a `CFG` field
instead. `CFG.anchor` is the worked example: the one real thing the reader applies every
exercise to (a business, a kitchen, a next negotiation) is named by `anchor` in `course.json`
(`label`, `prompt`, `placeholder`, `noun`), with neutral defaults in `config.DEFAULT_ANCHOR`,
and the page only ever prints those four strings. This is checkable:

```
grep -rniE "marketing|marketer" platform/web/
```

must return nothing.

The mirror of that rule: `courses/<id>/` contains no code. A course is markdown, JSON and
nothing else.

## How the build works

`coursekit` modules, in dependency order:

| Module | Job |
|---|---|
| `errors` | `CourseError` and its three subclasses |
| `config` | `course.json` → `CourseConfig`; builds the `CFG` the page receives |
| `markdown_render` | markdown → HTML; HTML → plain text for search and chat context |
| `loader` | module markdown → `Module`/`Section` objects; reads the optional `**Requires:**` line |
| `assessments` | quizzes, flashcards, suggested questions; merges the per-part files |
| `library` | glossary, mental models, worksheets, plan pages — all optional. `fillable` turns a worksheet's blanks into numbered inputs |
| `validate` | every cross-file check, collected into one report |
| `bundler` | concatenates `web/css/*.css` and `web/js/*.js` |
| `renderer` | injects `CFG` + `DATA` into `shell.html`; writes both outputs |
| `scaffold` | theme + hours → an empty but valid course tree |
| `cli` | argparse |

### Front-end conventions

The app ships as one HTML file with no runtime dependency beyond a webfont, because a course
has to work offline and from a `file://` URL. That is why `bundler` concatenates rather than
bundles — but the source is still one file per concern under `platform/web/js/`.

**Load order is the numeric filename prefix**, and it matters: files declare functions and
are otherwise order-independent, but `21-boot.js` runs the app and must stay last. Insert a
new file by picking a free number, or a letter suffix on the neighbour it belongs beside
(`09b-checkpoint.js` sorts after `09-review.js`), not by renaming everything after it.

### What the reader can do

The page runs one learning cycle per module — Predict → Read → Retrieve → Elaborate → Apply —
and everything else exists to make the practice half of that honest:

| | Where |
|---|---|
| Eight question types (`single`, `multi`, `tf`, `numeric`, `order`, `match`, `cloze`, `short`), per-option feedback, a hints ladder, confidence rating on every answer | `08-quiz.js` — one engine, driven by the `QZ` object, shared by module quizzes and checkpoints |
| Mistake queue: a missed or hinted question becomes a card due tomorrow, retired after four clean recalls | `02-helpers.js` (`addMistake`, `grade`), `09-review.js` (`#/review/mistakes`) |
| Checkpoints: mixed quizzes across a finished part, and a course challenge across everything | `09b-checkpoint.js`, results in `S.cpHist`, per-module hits in `S.chk` |
| Mastery per module — Read → Practised → Proficient → Mastered — that a checkpoint miss can lower | `02-helpers.js` (`mastery`), coloured dots everywhere |
| Study plan (hours per week or a target date), the "today" list, streak freezes, a study-day heatmap, browser notifications when served by Studio | `10b-plan.js`, `10-stats.js`, `01-state.js` (`markDay`) |
| The tutor as grader: Elaborate and Apply answers, `short` quiz answers, filled worksheets and role-play transcripts all get a `VERDICT:` line and a Covered / Missing / Wrong / Ask-yourself reply | `17b-grader.js` |
| Role-play: the tutor plays `assess.roleplay.persona` in the rail and stays in character until "Finish & get feedback" | `17b-grader.js`, `17-rail.js` (`c.kind === "rp"`) |
| Fillable worksheets, saved in `S.sheets[slug]`, copied out as text or reviewed by Claude | `11b-worksheets.js`; the inputs are made at build time by `library.fillable` |
| Prerequisites from a module's `**Requires:**` line, shown as chips and warned about when weak | `07-module.js`, `06-home.js` |
| Bookmarks, resume position, open questions that the tutor's reply closes, notes export as markdown, reading preferences (size, width, serif, motion), a print stylesheet, and a course record page | `07-module.js`, `15-marks-core.js`, `18-notes.js`, `19-settings.js`, `10b-plan.js` (`viewRecord`), `css/04-practice.css` |

Everything above lives in `localStorage` with the rest of the reader's state, so it syncs
to Studio and travels through Backup / restore. Reading preferences and the notification
opt-in sit under `S.ui` and stay on the device.

There is no module system and no build step for the JS. Everything is top-level in one
scope. Adding a global means adding it to that shared scope — check the name is free.

### Two outputs, deliberately

| File | Purpose |
|---|---|
| `<output>.html` | fragment, for publishing. A hosted page may not call `api.anthropic.com`, so the tutor is unavailable — reading, quizzes and flashcards still work. |
| `<output>-local.html` | full document, for opening off disk. `file://` origins *are* allowed to reach Anthropic, so this is the copy where the tutor works. |

Always point a user at the `-local.html` copy.

## Invariants the build enforces

`build.py check` reports all of these in one pass, before anything is written:

- Every module has an assessment entry, keyed by module id.
- Every quiz item has the shape its `type` demands (`validate.QUIZ_TYPES`; `single` when
  absent), a `why`, and — if present — one `feedback` line per option and `hints` as a
  list. `validate.quiz_item_problems` is the single definition, and Studio's
  `_fix_quiz_item` coerces towards it.
- Every flashcard has both `front` and `back`.
- A `roleplay`, when present, has `persona`, `situation`, `goal` and a non-empty `rubric`.
- Every id in a module's `**Requires:**` line is a module in the course.
- **A module's suggestion list has exactly one entry per `##` section.** They are matched by
  position. This is the most common authoring failure.
- No duplicate module ids; no assessment or suggestion entry that matches no module.

**Module order** is filename order within each part unless `course.json` carries an `order`
list of ids; then listed ids come first in that sequence and the rest follow by filename.
`loader.module_files` is the one place that rule lives, and `server._module_ids` calls it,
so the cheap listing and the build never disagree. Part membership is still the folder the
file sits in; `manage.move_module` moves the file when the part changes and rewrites `order`.

The reading timer (`07-module.js`) pauses after `page.study.idleSeconds` without input, so a
tab left open does not count as study. `page.ui.readMin` is the narrowest the reading column
may get before the rail is capped; the section list beside the prose hides itself through a
container query on `#main`, not a viewport breakpoint, because the rail changes the column
without changing the window.

A `##` section whose body is empty is dropped from the render *and* from the count — which
is usually why a count mismatch appears out of nowhere.

## Course Studio

`platform/studio/` is a second front end onto `coursekit`, for what is awkward in a terminal:
watching a long generation run, editing a proposed curriculum before committing to it, and
reading validation errors next to the course they belong to.

| Module | Job |
|---|---|
| `claude_cli` | talks to Claude through the `claude` CLI |
| `jobs` | background work with a replayable event log |
| `prompts` | every prompt Studio sends |
| `generator` | the pipeline: plan → approve → write → validate → build; plus `extend` and `rewrite` for an existing course |
| `progress` | the platform-side copy of reader state, one JSON file per course |
| `manage` | course operations that need no model: settings form, remove a module, trash a course |
| `prefs` | Studio-wide preferences in `state/studio.json` — today, the model |
| `log` | the `studio` logger: rotating file + in-memory ring, read by `/api/logs` |
| `server` | HTTP, SSE, and the static UI in `ui/` |

**It binds to 127.0.0.1, and that is a security boundary, not a default.** Studio writes
files and spawns processes. Do not make it listen on another interface.

**Prompts go in on stdin, never as `-p <prompt>`.** A Windows command line caps at 8191
characters, and a module prompt is an order of magnitude larger. stdin removes the ceiling.
`tools/bridge/claude-bridge.py` does the same; its remaining trim only bounds cost per question.

**Every CLI call names its model.** Without `--model`, Claude Code inherits whatever the
person last chose interactively, and the headless SDK path rejects some of those (a `[1m]`
context variant fails with `unrecognized_model`) — which is how a run died at module 8 of 9.
`claude_cli.model_chain()` tries the requested alias, then Studio's default (`prefs`, env
`STUDIO_MODEL`, else `models.default` in `settings.json`), then the bare CLI as a last
resort. `prefs.MODELS` is the only list the Settings page offers, and it is `models.list`
from `settings.json`.

**A run can be resumed.** `generate()` saves the approved curriculum to `plan/plan.json`;
`brief["resume"]` reloads it (or `reconstruct_plan()` rebuilds one from `course.json` for
courses made before that), skips the approval gate, keeps every module and study-data entry
already on disk, and writes only what is missing. `POST /api/courses/<id>/resume`; the
course page and the failed-job screen offer the button when `can_resume()` says so.

**Log first, then look.** `log.log` is the `studio` logger. Every Claude call logs model,
duration, prompt/reply size and stderr on failure; every job event logs a line; every
unhandled route error logs a traceback. Read it at **Settings & logs** (`#/settings`) or in
`state/logs/studio.log`. `STUDIO_LOG_LEVEL=DEBUG` adds access lines. Rotation size and
count are `logs.maxBytes` / `logs.backups`.

**Model output is trusted for prose and distrusted for structure.** `generator._fix_assessment`
and `_fix_suggestions` coerce replies into shapes the validator accepts — clamping quiz answer
indexes, dropping half-written flashcards, forcing the per-section question count. Everything
is written to disk as it is produced, so a run that dies at module 14 leaves fourteen real
modules behind.

**The section count comes from `coursekit.loader.parse_sections`, never a second parser.**
Studio has to count sections exactly as the build does or the courses it generates fail
validation. That function is public for this reason; `test_studio.py` guards the agreement.

The approval gate is `Job.await_input`, which parks the worker thread until the browser POSTs
an answer. A cancel also releases it, so a job waiting for approval can still be stopped.

### Editing an existing course

Three routes, all on the Studio course page (`#/course/<id>`):

| | |
|---|---|
| `POST /api/courses/<id>/extend` | one new module on a topic. `generator.extend` asks for a design that fits the existing curriculum (`prompts.module_spec`), writes it under the next free id — ids are never reused because progress is keyed by them — appends it to the chosen part, writes its study data to `data/*/<mid>.json`, adds the short title, rebuilds. |
| `POST /api/courses/<id>/modules/<mid>/rewrite` | same id, same file, same position; the notes become `prompts.direction`. `_store_module_data` replaces the entry in whichever file already holds it, so the validator never sees two claims on one id. |
| `GET/PUT /api/courses/<id>/files?path=` | raw editing of any `.md`/`.json` inside the course. `resolve_course_file` confines the path; JSON is parsed before it is written. |

Both jobs stream events like a generation run and end with a build. A rewrite keeps the
reader's progress for the module but may leave section ticks misaligned if the section
count changes — the UI says so.

Without a model (`studio/manage.py`):

| | |
|---|---|
| `GET/POST /api/courses/<id>/settings` | title, tagline, audience, practitioner, tutor persona, part names/hours/blurbs, milestones. **`id` is refused**: it is the reader's storage key. |
| `POST /api/courses/<id>/modules/<mid>/remove` | the file moves to `state/trash/`, its assessment and suggestion entries are dropped from whichever files hold them, its short title and its `order` entry go; the reply carries the check result. |
| `POST /api/courses/<id>/modules/<mid>/move` | `{part, index}`: reorder within a part or move to another; writes `order`, moves the file, never touches study data. |
| `POST /api/courses/<id>/modules/<mid>/review` | a job: Claude reads the module against the pedagogy checklist in `prompts.review` and returns a verdict, gaps, errors, quiz issues and a rewrite brief. Stored under `state/reviews/`, not in the course - it is an opinion about content, not content. The module row shows the verdict; "Rewrite with these notes" turns the brief into a rewrite. |
| `POST /api/courses/<id>/delete` | needs `{confirm: <id>}`; moves `courses/<id>` and `dist/<id>` to `state/trash/<id>-<stamp>/` and forgets the progress copy. |

The reader's open questions (`state.marks` with status `open`/`answered`) come back in the
course detail as `questions`; the Studio Questions tab turns any of them into an Add-a-module
or Rewrite brief through query params (`?tab=add&q=…&notes=…`, `?rewrite=<mid>&q=…`).

**Jobs persist.** `jobs.Registry(store_dir)` writes a finished job's events and result to
`state/jobs/<id>.json` and reads them back as `StoredJob`, so `/api/state` and
`/api/jobs/<id>/events` work across a restart. Ids carry a per-process prefix so runs never
collide.

### The Studio UI

`ui/studio.js` is hash-routed: `#/` library with a "today" strip and progress cards, `#/new`,
`#/course/<id>` (tabs: Modules, Add a module, Questions, Files, Settings),
`#/course/<id>/edit?path=`, `#/job/<id>`, and `#/settings` — Studio-wide: the model, every
resolved platform setting with the layer it came from, where things are, and a live log
viewer polling `/api/logs`. The course
page reads `GET /api/courses/<id>`, which parses modules and is therefore not used for the
listing; `/api/state` counts module files instead (`server._module_ids`).

## Authoring content

Two routes, same contract. Studio generates unattended from a brief; the `course-author`
skill guides a model that can read files and iterate. `platform/studio/prompts.py` is the
machine-driven twin of the skill — **when the module format or a JSON schema changes, both
have to change.** The skill's `references/` stay the human-readable source of truth.

Use the `course-author` skill for hand-guided work. Its references are the specification:

- `.claude/skills/course-author/references/module-format.md` — the markdown contract
- `.claude/skills/course-author/references/data-schemas.md` — the JSON schemas
- `.claude/skills/course-author/references/pedagogy.md` — what makes a course worth finishing

Do not write course content freehand without reading those; the format is enforced and the
pedagogy is the point.

## Reader profiles and the study calendar

`state/studio.json` names the active reader profile (`prefs.profile`, default `default`).
`progress.Store(dir, profile)` keeps the default profile's files exactly where they were,
`state/progress/<id>.json`, and gives every other profile a folder of its own; `server.store()`
resolves the active one per request. A page served by Studio asks `GET /api/profile` before it
loads anything, keys its localStorage as `course_<id>_v1_<profile>` for a non-default profile,
and puts `?profile=` on every progress sync - the server answers 409 if Studio has since
switched readers, so one reader's state can never land in another's file. Off disk there is
no Studio and therefore one profile.

`GET /api/state` also carries `calendar`: the union of every course's study days for the
active profile, and the streak across them. `GET /api/search?q=` searches every course at once
through the build's own loader (`studio/search.py`).

## Progress and chat storage

All reader state — completion, timers, quiz answers, flashcard scheduling, highlights, notes
and every conversation — lives in the browser's `localStorage` under `CFG.storageKey`, which
is `course_<id>_v1`. Courses are therefore isolated from each other by construction.

When the page is served by Studio the same object is also kept at
`state/progress/<id>.json` (see above), which is what the library cards and the course page
read. A page opened off disk has no server; there, progress moves between machines through
**Backup / restore** in the sidebar. Changing `storageKey` orphans existing progress, so do
not change a course's `id` after anyone has started it.

## Gotchas

- **Windows console encoding.** `platform/build.py` forces UTF-8 on stdout/stderr. Courses
  use real typography and cp1252 cannot encode it. Keep that shim.
- **Every Studio handler must read the request body**, even one that ignores it.
  `Handler` speaks HTTP/1.1 with keep-alive and one handler instance serves a whole
  connection, so an unread `{}` becomes the first bytes of the *next* request on that
  connection: the server answers `Bad request syntax ('{}')` as an HTML page and the browser
  reports "The server sent something unreadable." `do_GET/POST/PUT` reset and drain the
  body before dispatch (`_raw_body`); the smoke test's keep-alive check guards it.
- **`</` inside embedded JSON** would close the `<script>` tag early; `renderer._embed_json`
  escapes it. Do not swap in a plain `json.dumps`.
- **Relative markdown links do not survive** — a one-file site cannot resolve them, so they
  render as italic text. Do not write cross-module links.
- **`dist/` is generated.** Edit `platform/web/` or `courses/<id>/`, never the built HTML.
