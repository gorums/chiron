# Remember this

When reporting information to me, be extremely concise and sacrifice grammar for the sake of concision.

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
providers and the model list, every timeout, the generation counts, the log rotation, and
the page's study rules and layout sizes. No
module under `platform/` or `tools/` carries a literal of its own; it asks
`coursekit.settings.SETTINGS` (`SETTINGS.get("studio.port")`, `SETTINGS.models`,
`SETTINGS.bridge_url`, ...). The bridge imports the same module from outside the package,
which is why `settings.py` is stdlib-only.

Resolution, later layers winning:

| | |
|---|---|
| `platform/settings.json` | the committed defaults |
| `SETTINGS_FILE` | an optional JSON overlay, deep-merged: a different model list, longer timeouts |
| `state/settings.json` | what Studio's settings page saved - today the model list (`studio/models.py`); deep-merged the same way, written only by Studio, reported as source `Studio` |
| `.env` at the repo root | the scalar knobs in `settings.ENV_KEYS` (`STUDIO_PORT`, `BRIDGE_HOST`, `STUDIO_MODEL`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `JUPYTER_TOKEN`, ...) |
| the environment | the same names, winning over `.env` |

An environment value is coerced to the type of the default it replaces, so `STUDIO_PORT`
becomes an int. `SETTINGS.reload()` re-reads every layer into the same object, which is how
a list saved on the settings page reaches every module without a restart; anything derived
from the model list is therefore a function (`claude_cli.model_aliases()`,
`prefs.models()`), never a module constant. `SETTINGS.overrides` records which layer supplied each overridden key;
`build.py where` prints them and the Studio settings page (`#/settings`) lists every
resolved value with its source. Studio's own preference file, `state/studio.json`, sits on
top of all of this for the one thing the UI edits: the model.

**A model is named by two settings, never by one.** `providers` says how a model is
reached — `kind` picks the adapter in `coursekit/llm/`, and a row with `enabled: false`
keeps its configuration and is offered nowhere. `models.list` says which models there are,
each naming the `provider` that reaches it; a row that names none belongs to
`llm.defaultProvider`, which is what lets a list saved before providers existed keep
working. An `id` need only be unique within its provider — two providers may well offer the
same model — while an `alias`, being the short name a person types, is unique across the
whole list. `llm.*` holds how hard the platform tries: the timeout, the retries, the
backoff. **A setting written under its older name still works**: `claude.*` and
`anthropic.*` are read, moved to their new homes by `settings._absorb_legacy`, and reported
on the settings page with the name they came from. Every `providers.*.apiKey` is a secret
by rule (`settings.is_secret`), so a provider added later is masked without this file being
edited.

**The page gets its slice as `CFG.platform`.** `renderer.runtime_config` merges
`SETTINGS.page()` into the `CFG` the shell receives: the bridge address, the providers a
browser may call itself (`page_providers` — enabled, not a `cli` kind, **never a key**), the
model list with each model's provider and the default, and the `page` block (tutor budgets,
sync timing, study rules, rail sizes). `01-state.js` binds them to `PLATFORM`, `TUTOR`, `SYNC`, `STUDY`
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
    llm/                    reaching a model, whoever makes it: the provider layer
                            (see "Reaching a model"). The bridge imports it too
  studio/                   the local web app: generate + build from a browser
    ui/                     its front end: index.html + studio.css + js/ (one file per screen)
  web/                      the course page's source: shell.html + css/ + js/ (one file per concern).
                            00-tokens.css, 01-base.css and 00-dom.js are the design system
                            Studio links too (see "The design system")
  tests/                    test_build.py, test_studio.py, page_smoke.js (boots front-end code under node)
courses/<id>/               one course = one separate git repository (gitignored here;
                            the directory itself moves with COURSES_DIR)
  course.json               the manifest that makes a folder a course
  modules/<part>/M01-*.md   the teaching
  figures/<mid>-<n>.svg     diagrams a module refers to; inlined by the build (see "Figures")
  notebooks/<mid>-<n>.ipynb Jupyter notebooks a module refers to; rendered by the build, run in
                            the page when Jupyter is up (see "Notebooks")
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
tools/jupyter/              the Jupyter server's configuration, shared by compose and `build.py jupyter`
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
python platform/build.py jupyter                         start the Jupyter server for a course's notebooks
```

Or double-click `start-studio.bat`. Studio is the UI route: it generates a course from a
theme and an hour budget, shows how far you are in each one, and edits, extends and rebuilds
a course without a terminal.

Tests:

```
python platform/tests/test_build.py      70 tests — engine, and the code conventions below
python platform/tests/test_studio.py     131 tests — Studio
npm run format                           prettier over every .js and .css (see "Code conventions")
```

Requires Python 3 and the `markdown` package (`pip install markdown`). Nothing else - `npm
install` adds prettier for the front end, and the formatting test skips when it is absent.

## Running in Docker

```
docker compose up -d --build     start all three, and on every boot from now on
docker compose logs -f studio    watch a generation run
docker compose down              stop them
```

Needs a `.env` holding `CLAUDE_HOME` — the path to the host's `~/.claude`. Copy `.env.example`.
The same file may set `COURSES_DIR`; compose mounts it at `/work/courses`. `STUDIO_PORT`,
`BRIDGE_PORT`, `JUPYTER_PORT` and `JUPYTER_TOKEN` there are read by compose *and* by the
code, so the published port and the one the service binds always agree.

**One image, three services.** Studio, the bridge and Jupyter need the same things — Python,
and the Claude Code CLI for the first two — so they share a build and differ only in the
command and the mounts. Two Dockerfiles would be two things to keep in step. The `jupyter`
service is the one that runs code a model wrote, so it gets the courses and the platform's
configuration and nothing else: no `~/.claude` (see "Notebooks").

**Nothing is COPYed into the image.** The repo arrives as a bind mount, so a course written
inside the container is a real file in the user's folder and editing `platform/` needs only a
restart. Rebuild only when `docker/Dockerfile` changes.

**`~/.claude` is mounted as a whole directory, never as a single file.** Claude Code refreshes
its OAuth token by writing a new file and renaming it over the old one, which silently breaks
a single-file bind mount. The mount is read-write because that refresh has to persist; the
container then behaves like any other Claude Code session on the account.

**Services bind `0.0.0.0` inside the container, and compose publishes to `127.0.0.1`.**
`STUDIO_HOST`, `BRIDGE_HOST` and `JUPYTER_HOST` default to loopback in the code and are
overridden only in the image. Dropping the `127.0.0.1:` prefix from a `ports:` entry would expose a service that
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
  runs before the first render and **merges** the platform copy into the local one
  (`mergeStates` in `01-state.js`: union of every keyed collection, the later entry on a
  clash, deletions remembered in `STATE.gone`), so two tabs or two browsers never lose each
  other's chats or highlights. A `storage` event merges what another tab of the same
  course saved; a tab becoming visible pulls again. Device settings (`bridge`, `ui`, `theme`) never leave the
  browser — `progress.DEVICE_KEYS` strips them again server-side.
- **The tutor answers on the same origin.** `connMode()` returns `"studio"` when Studio
  reports Claude available and no API key is saved; `askBridge()` then posts to `/api/ask`,
  which flattens the conversation with `claude_cli.chat_prompt` and runs the CLI on stdin. No
  bridge, no key, no CORS. A saved key still wins: it is an explicit choice to pay per question.
- **The course can grow from inside.** The module footer links to Studio's course page with
  `?tab=add&from=<mid>` or `?rewrite=<mid>`.

The bridge remains the route for a page opened off disk (`file://`), where none of this
applies. It is `tools/bridge/tutor-bridge.py` (`claude-bridge.py` still starts it), and it
reaches a model only through `coursekit.llm` — the same provider layer Studio uses, so the
retry policy, the model chain and the failure kinds are one implementation rather than two
that drift. What is its own: a loopback socket with CORS, the key hunt (`candidate_keys`,
which looks in the half-dozen places a key is already likely to be and says which one it
used), choosing between the ways in and falling back from one to the other mid-question, and
`trim` — a budget per question, which bounds cost rather than any command-line length.
`GET /health` reports `providers` alongside the flat fields a page built before that
release looks for.

## Reaching a model

**`platform/coursekit/llm/` is the one place a wire format or a command line appears.**
Everything above it — the generator, the editor, the reviewer, the tutor route, the bridge —
asks for a completion and gets text back, and knows nothing about who answered.

It lives in `coursekit` rather than in `studio` because `tools/bridge/` imports it from
outside the package, the way it imports `settings`. That is what keeps one implementation
instead of two. For the same reason it is **standard library only**: `urllib.request` for an
HTTP provider, `subprocess` for a CLI one. A vendor SDK here would end `markdown` being the
platform’s only dependency.

| Module | Job |
|---|---|
| `failures` | why a call failed, in one word: `quota`, `auth`, `model`, `transient`, `timeout`, `unknown` — the kinds every layer branches on |
| `base` | what a provider is: `Provider`, `Request`, `Reply`, `Capabilities`, `LLMFailed` |
| `shape` | flattening a conversation into one prompt; digging JSON out of prose |
| `cli` | a model reached through a headless binary |
| `anthropic` | a model reached through Anthropic's Messages API |
| `chain` | retries, model fallback, and telling whoever is watching |

- **A provider runs one call and classifies what came back. `chain` decides what to do about
  it.** The retry policy, the JSON insistence and the progress reporting are the platform’s,
  not any vendor’s, so they are written once (see "When Claude says no" for the rules).
- **A prompt is sent verbatim when a caller built one.** `Request.prompt` goes through
  untouched — a module prompt is a document, not a conversation, and wrapping it in "User:"
  would change what the model is asked. `system` and `messages` are the chat shape, which a
  `single_prompt` provider flattens itself.
- **`coursekit` never imports `studio`.** Progress goes to a `chain.Reporter`, which by
  default goes nowhere; `studio/claude_cli.py` installs one that forwards to
  `jobs.current()`. That module is now a shim over this layer and nothing else.
- **A caller names a model, never a provider.** `models.list` already says which provider
  reaches which model, so `llm.ask(prompt, model=…)` resolves it through
  `SETTINGS.provider_of`; asking every call site to know as well would be a second place to
  keep right. `llm.provider_for(name)` is there for the one caller that does have a provider
  in hand — the bridge, which found its own key.
- **A chain never crosses providers.** `model_chain(model, provider)` offers only models
  that provider reaches: falling back to a model on another account answers a question
  nobody asked and bills someone who did not agree to it. A provider with no models listed
  yet is not filtered by, because there is nothing to filter with.
- **A key lives on the provider, not on the request.** `AnthropicProvider.with_key` is how
  the bridge uses the key it hunted down, so a secret never threads through `Request`,
  `chain` or a job event.

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

The mirror of that rule: `courses/<id>/` contains no code the platform runs. A course is
markdown, JSON, SVG figures and, where the subject calls for them, Jupyter notebooks (JSON
too), nothing else.

## How the build works

`coursekit` modules, in dependency order:

| Module | Job |
|---|---|
| `errors` | `CourseError` and its three subclasses |
| `llm` | the provider layer: one place a wire format or a command line appears (see "Reaching a model"). `llm.failures` names why a call failed, in one word; `coursekit/failures.py` re-exports it for the bridge |
| `config` | `course.json` → `CourseConfig`; builds the `CFG` the page receives |
| `markdown_render` | markdown → HTML; HTML → plain text for search and chat context |
| `figures` | SVG figures: sanitise, check, inline into a section's HTML, count the build-up steps |
| `notebooks` | Jupyter notebooks: check the `.ipynb`, render its cells read-only into a section's HTML, refuse one in a course without the runtime |
| `loader` | module markdown → `Module`/`Section` objects; reads the optional `**Requires:**` line; inlines the figures and the notebooks |
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

### The design system: three files, two surfaces

**The reader and Studio are one product, so they are built from one set of parts.** Three
files under `platform/web/` are the whole design system; the page inlines them with the rest
of its source, and Studio links the same files at `/ui/shared/` (`SHARED_UI` in `server.py`,
`GET /ui/shared/<file>`). A copy in the other surface is the bug this replaced: `.btn` used
to mean *filled* in Studio and *outlined* in the page.

| | |
|---|---|
| `web/css/00-tokens.css` | every colour, shadow, radius, font and size the platform has: the palette in both themes, `--on-accent` for text on a strong fill, `--overlay`, the spacing scale `--s1..--s6`, the type scale `--fs-xxs..--fs-base` |
| `web/css/01-base.css` | the primitives: reset, one `:focus-visible` ring, the `.btn` family, the form block, `.card`, `.tag`, `.pill`, `.badge`, `.bar`, `.chip`, `.note`, `.problems`, `.toast`, `.menu`, `.empty`, `.scrim`, `.spin`/`.pulse`, `.topbar`, and the spacing utilities (`.gap-top`, `.rowline`, `.grow`, …) that keep `style=` out of the markup |
| `web/js/00-dom.js` | `$`, `esc`, `toast(msg, {kind, sticky})`, `ico`, `clock`, `ago`, `fmtH`, `fmtDur`, `scrollBehavior`, and `HELP` / `help(term)` |

`web/css/01b-shell.css` holds the reader's own frame (the three-column grid, the sidebar) and
Studio's `studio.css` holds Studio's; neither surface loads the other's.

- **`.btn` is outlined. `.primary` is the filled one, and there is one per region** — the
  next thing to do. `.ghost`, `.sm`, `.warm`, `.danger` and `.iconbtn` are the rest of the
  family; a variant outside that list has no rule, and a test says so.
- **`.tag` says what something is** (`ok`, `warn`, `bad`, `acc`, `stale`), **`.pill` says what
  state a thing is in** (`on`, `off`, `live`), **`.badge` is a count**. Studio's verdicts are
  `.tag`, not a family of their own.
- **`help(term)` is the one glossary.** Mastery levels, freeze, mistake card, calibration,
  checkpoint, compact, the verdict scale, patch versus rewrite, resume, stale, profile,
  anchor, practitioner, curriculum — each defined once in `00-dom.js` and printed as a
  `title` where the word appears, instead of on a page the reader has to go and find.
- **One theme key, `platform_theme`.** Studio and a served page read and write it, so a dark
  Studio never opens a light course page; a page off disk falls back to `STATE.theme`.
- Four guards in `TestCodeConventions` hold this: no colour outside `00-tokens.css`, no font
  size off the scale, no `.btn` variant without a rule, no class used in a template that no
  stylesheet defines, and a ceiling on inline `style=` per tree.

### One vocabulary

Both surfaces name the same thing the same way. The words are a contract with the reader as
much as a variable name is a contract with the next person to read the code.

| Say | Never | Meaning |
|---|---|---|
| course | | one folder, one repository |
| curriculum | plan | the whole outline Studio proposes and you approve |
| module design | spec, plan | one module's outline before it is written |
| module, section, step | lesson, chapter | as in the page |
| Predict · Read · Retrieve · Elaborate · Apply · Close the gaps | Review (for a step) | the six steps, everywhere |
| Practice | Review, Retrieval practice | the flashcard deck, `#/review` |
| Fix mistakes | mistake queue | `#/review/mistakes` |
| mastery: Not started · Read · Practised · Proficient · Mastered | | each with a `help()` line |
| tutor | Claude, assistant, chat panel | who answers in the page |
| Claude | model | who writes and reviews in Studio |
| Claude Code | | the installed CLI; the status pill only |
| model | | the picker |
| Rebuild | publish, render | write `dist/` again |
| Stop (a run) / Cancel (a form) | | |
| Mark as good / Unmark | This is good, Withdraw | the owner's own verdict |
| Patch or rewrite… | Apply, Rewrite with this | the one action |
| Your gaps | profile, learner memory | `#/learner` |
| needs fixing | broken | a course whose check fails |

`KIND_LABELS` in `ui/js/00-core.js` is the same rule for job kinds: no screen prints a raw
`kind`.

### What the reader can do

The page runs one learning cycle per module — Predict → Read → Retrieve → Elaborate → Apply →
Close the gaps —
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
| Figures: SVG diagrams inlined in the Read step, and build-ups the reader steps through or plays (see "Figures") | `07c-figures.js`, `css/02-content.css` |
| Listening: the Read step read aloud by the browser's own speech engine, block by block with the spoken block highlighted; a section heard to its end is ticked read; voice and speed under `S.ui` (see "Listening") | `07d-audio.js`, `css/02-content.css` |
| Notebooks: a Jupyter notebook rendered read-only in the Read step and, when served by Studio with Jupyter running, run and edited right there (see "Notebooks") | `07e-notebooks.js`, `css/02b-notebooks.css` |
| Bookmarks, resume position, open questions that the tutor's reply closes, notes export as markdown, reading preferences (size, width, serif, motion), a print stylesheet, and a course record page | `07-module.js`, `15-marks-core.js`, `18-notes.js`, `19-settings.js`, `10b-plan.js` (`viewRecord`), `css/04-practice.css` |
| The learner memory: what the tutor knows about this reader, per course, built from every miss, verdict and question; it goes into every tutor prompt and ahead of the suggested questions (see "The learner memory" below) | `17c-learner.js`, `17d-learner-view.js` (`#/learner`), `06-home.js` (`renderGapCard`) |

Everything above lives in `localStorage` with the rest of the reader's state, so it syncs
to Studio and travels through Backup / restore. Reading preferences and the notification
opt-in sit under `S.ui` and stay on the device.

### The learner memory

`STATE.learner` is one course's memory of one reader - what the tutor should know before
it answers. It is built in three layers by `17c-learner.js`:

- **Evidence** (`learnerEvidence`) is derived, never stored: one line per sign in the
  state the page already keeps - a quiz miss with what was answered and how sure they
  were (`qAnswer` stamps `at` on the answer for this), a grader's Missing / Wrong lines
  (`graderFindings` parses the `verdictFormat` reply), a mistake card that keeps lapsing,
  a checkpoint miss, a question asked in the rail, a passage marked as unclear. Each line
  carries a `weight`; `weakSpots()` sums them per module, so the page can point at weak
  modules without a model.
- **The brief** is what Claude writes from the evidence (`refreshLearner`): a paragraph on
  how this reader thinks and what keeps going wrong, up to `page.learner.maxGaps` gaps
  `{id, mid, topic, why, ask, status}` - each with one question that would test whether
  the gap has closed - and a few strengths. `parseLearnerReply` distrusts the structure
  (a gap in an unknown module is dropped); `applyLearnerReply` keeps a gap the reader
  closed closed, and treats a gap the model left out as closed rather than lost.
  `maybeRefreshLearner()` runs after a quiz, a checkpoint or a verdict, and only when
  enough new evidence has arrived (`refreshAfterEvents`) and enough time has passed
  (`refreshMinutes`); `#/learner` has the button for an update on demand.
- **Use.** `systemForRail()` appends `learnerContext(mid)`: the brief, the gaps that touch
  this module and its prerequisites, and what went wrong here, capped at `promptChars`,
  with the instruction to close a gap rather than only answer. `renderSuggest` puts
  `gapChips(mid)` - the gaps' own questions, then the missed questions - ahead of the
  section's suggestions, styled `.chip.gap`. The dashboard shows the top gaps
  (`renderGapCard`); the sidebar counts them; "Ask the tutor" on a gap opens the module
  with the question already sent (`askAbout`, through `rail.pendingAsk`).

- **Close the gaps** is the sixth step of every module (`07b-gaps.js`). `gapItems(mid)`
  turns the module's record into drill items with a stable key - the brief's gaps for this
  module, each missed quiz question (`q:<index>`, carrying the right answer and its
  `why`), each lapsing card (`l:<card>`), each exercise graded partial or wrong (its
  grader key). The reader answers in writing; `checkGapAnswer` grades it with the module
  text and the original miss and closes the item only on `correct` (a right answer with
  wrong reasoning is `partial`); without Claude the reader scores themselves. Answers and
  verdicts live in `progressOf(mid).gapWork[key]`, so a closed item stays closed, leaves
  the chips and the tutor prompt, and `stepDone(m, 5)` is true once the step was opened
  and nothing is left. The course record lists the modules with open items.

It is part of the state, so it syncs to Studio, merges (`mergeLearner`: the later brief
wins, a gap closed on either side stays closed) and travels through Backup / restore.
Studio reads it back as `learner` in the course detail (`catalog.learner_view`) and the
Questions tab lists the open gaps, each as a rewrite brief - a gap that keeps coming back
is the best evidence that a module needs work. The knobs are `page.learner` in
`settings.json`; `platform/tests/learner_checks.js` exercises the whole thing inside a
booted page (`page_smoke.js --checks`).

### The chat rail

One rule: **the rail shows the conversation at the place the reader is looking at, and
follows them when they move.** A place is `{mid, step, sec}` - the module, the step from
the route (`predict`, `read`, `quiz`, `elab`, `apply`, `gaps`) and, on the Read step, the
section under the reading line. It is read off the page whenever it is needed
(`placeNow()` in `17a-place.js`), never stored; the only thing kept on scroll is
`rail.section`, which the scroll handler in `07-module.js` maintains with hysteresis.

- **One conversation per place, found, not tracked.** A conversation carries its place
  (`step`, `sec`); `convoAt(place)` returns the newest one there, or null, and nothing is
  created until the first message is sent (`17-convos.js`). There is no stored "active"
  conversation; an `active` map old saves still carry is ignored. A chat on the
  Elaborate step is about the Elaborate step; scrolling from section 2 to section 3 shows
  section 3's chat. Role-plays and chats from before places existed have no place and
  belong to the module as a whole.
- **Two explicit exceptions.** `rail.showing` is a conversation the reader picked by hand
  (menu, "New chat", a role-play, "Continue" on the Marks page, a compaction); it stays
  until they move to another place, or is answering (`railPlaceChanged`). `rail.pinned`
  is a selected passage; it fixes the place to that section until unpinned, and does not
  survive leaving the module's Read step (`railRouteChanged`, called from `render()`).
- **The tutor is told about the place.** `systemForRail(m, c, place)` puts the section
  text on the Read step and, on every other step, what the step asks and what the reader
  has written so far (`placeText`): the Predict guess, the quiz question in view, the
  Elaborate answers with their verdicts, the Apply draft (the model answer only once it
  is revealed), the open gap items. `placeSuggestions` gives each step its own chips.
- **Every way to a passage is `jumpToPassage(mid, sec, markId)`** (`07-module.js`): a TOC
  link, a message's label, a menu row, a bookmark, a mark opened from Marks & questions.
  On the Read step it scrolls now; from anywhere else it sets `jumpTarget` and changes
  the route, and `landOn()` scrolls once the step is drawn. Jumps are instant, so the
  sections in between are never "in view" and there is no lock to keep.

`platform/tests/rail_checks.js` runs all of this inside a booted page.

There is no module system and no build step for the JS. Everything is top-level in one
scope. Adding a global means adding it to that shared scope — check the name is free.

The names to know: `STATE` is the reader's whole saved state (`01-state.js`, shape in
`blank()`); `progressOf(mid)` is one module's slice of it; `route` is the parsed hash
(`view`, `id`, `step`); `MODS` and `byId` are the course; `QUIZ` is the quiz being drawn
(`08-quiz.js`); `rail` is everything the chat rail keeps between renders (`17-rail.js`),
and the conversations it shows live in `STATE.convos` (`17-convos.js`, which documents the
message shape). Keys stored in `STATE` are a contract with every existing save - rename a
function freely, never a stored key.

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
  `coerce.fix_quiz_item` coerces towards it.
- Every flashcard has both `front` and `back`.
- A `roleplay`, when present, has `persona`, `situation`, `goal` and a non-empty `rubric`.
- Every id in a module's `**Requires:**` line is a module in the course.
- Every figure a module refers to is on disk, well-formed, has a `viewBox` and is under
  `build.figureMaxBytes`; any other `<img>` is refused (see "Figures").
- Every notebook a module refers to is on disk, nbformat 4, under `build.notebookMaxBytes`,
  and the manifest declares `notebooks` (see "Notebooks").
- **A module's suggestion list has exactly one entry per `##` section.** They are matched by
  position. This is the most common authoring failure.
- No duplicate module ids; no assessment or suggestion entry that matches no module.

**Module order** is filename order within each part unless `course.json` carries an `order`
list of ids; then listed ids come first in that sequence and the rest follow by filename.
`loader.module_files` is the one place that rule lives, and `catalog.module_ids` calls it,
so the cheap listing and the build never disagree. Part membership is still the folder the
file sits in; `manage.move_module` moves the file when the part changes and rewrites `order`.

The reading timer (`07-module.js`) pauses after `page.study.idleSeconds` without input, so a
tab left open does not count as study. `page.ui.readMin` is the narrowest the reading column
may get before the rail is capped; the section list beside the prose hides itself through a
container query on `#main`, not a viewport breakpoint, because the rail changes the column
without changing the window.

A `##` section whose body is empty is dropped from the render *and* from the count — which
is usually why a count mismatch appears out of nowhere.

**A section ticks itself once the reader has scrolled past it.** `tickScrolledPast` in
`07-module.js` runs off the same scroll handler that decides which section is current, and
ticks any section whose bottom edge has left the reading band (`page.ui.readLine`) — the
whole section, so a glance at the first paragraph never counts. The tick is drawn in place
rather than by redrawing the step, which would throw the reader back to the top. A tick
taken back by hand stays off for the rest of the visit (`untickedByHand`), so the reader can
argue with it; leaving the module forgets that.

### Figures

A course cannot ship pictures - it is one file that works off disk, and a model cannot
draw a raster anyway - but it can ship **diagrams as SVG**, which is text. A figure is
`courses/<id>/figures/<mid>-<n>.svg`, referenced from the module on a paragraph of its own:

```
![What the reader should notice](figures/M03-1.svg)
```

`coursekit/figures.py` owns the contract. `loader.parse_sections(raw, figures_dir)`
replaces the paragraph with `<figure class="figure" data-fig=...>` holding the SVG and a
`<figcaption>`; the section's `text` excerpt is taken before that, so the tutor and search
see words, not markup. On the way in the SVG is **sanitised** (`<script>`, `<style>`,
`<foreignObject>`, `<image>`, event attributes and non-fragment hrefs are removed - a
`<style>` inside inline SVG would restyle the whole page) and **checked** (well-formed
XML, a `viewBox`, under `build.figureMaxBytes`); a problem is a `check` failure like any
other. Colour comes only from classes the page defines for both themes - `fig-1` ...
`fig-4`, `fig-soft`, `fig-line`, `fig-muted` - and from `currentColor`.

A figure whose groups carry `<g data-step="1">`, `<g data-step="2">`, ... is a **build-up**:
`07c-figures.js` hides the steps and adds Back / Next / Play (`page.figures.playMs`
between steps). That is the animated GIF a course cannot carry, with the reader in charge
of the pace. Everything outside a step group is always visible.

### Listening

A course cannot ship audio either - no model makes any, and an mp3 per module would not
fit in one file - so the Read step is read aloud by the **Web Speech API**, the voice the
operating system or the browser provides. `07d-audio.js` owns it: `sectionSpeech` turns a
section into chunks - the heading, then each block under `SPEECH_BLOCKS` (a paragraph, a
list item, a table row read as its cells, a figure's caption; the drawing is skipped),
long paragraphs split at sentence ends under `page.audio.chunkChars` because some engines
fall silent partway through a long utterance. The block being spoken carries `.speaking`
and is scrolled into view; a chunk's element is looked up when it is spoken
(`chunkEl`), so a Read step redrawn mid-listen does not lose its place. A section heard to
its end is ticked like one scrolled through (`audioSectionDone`, which also updates the
progress line without redrawing the step), and reading runs on into the next section after
`page.audio.sectionPauseMs`. Pause is a cancel that remembers the chunk, because
`speechSynthesis.pause()` does not resume with every voice. `render()` calls
`audioRouteChanged()`, so leaving the module's Read step stops it; `pagehide` does too.

The voice and speed sit in `S.ui` (device-side, never synced) and are set on the Settings
page (`audioSettingsCard`), which lists the voices for the course's language - `lang` in
`course.json`, default `en`, reaching the page as `CFG.lang` - and every voice when none
matches. `page.audio` in `settings.json` holds the default rate, the offered rates, the
chunk size and the pause. Browsers refuse speech without a user gesture, so nothing starts
on its own; the Listen button on the Read step and the speaker button on each section are
the only ways in. `platform/tests/audio_checks.js` exercises it inside a booted page.

Studio draws them (`studio/figures.py`): `prompts.figures` asks for up to
`generation.figuresPerModule` diagrams in a delimited text format (an SVG inside a JSON
string is a parse failure waiting to happen), `coerce.fix_figures` keeps only the ones
naming a real section that pass `coursekit.figures`, and `write_figures` replaces the
module's old figure files and reference lines with the new ones. A generation run draws
them right after each module's text (`brief["figures"]`, on by default; a failure is logged
and the module ships without); `extend` and a full `rewrite` do the same; a patch keeps
the reference lines where they are. `POST /api/courses/<id>/figures` draws for every
module without any (`{all: true}` redraws them all) and
`POST /api/courses/<id>/modules/<mid>/figures` for one; the Modules tab and the row menu
offer both. `remove_module` trashes a module's figures with its file, and the Files tab
can edit an `.svg` by hand (the PUT sanitises and checks it).

### Notebooks

A course that teaches something the reader learns by running code - a language, data
analysis, statistics, a numerical method - carries **Jupyter notebooks** next to the prose,
and the reader runs them inside the module. It is a per-course decision: `notebooks` in
`course.json` (`{"kernel": "python3", "packages": ["numpy", "pandas"]}`;
`config.notebooks_setting` normalises it) turns them on, reaches the page as
`CFG.notebooks`, and is what the planner sets when a theme is one that is learned by
running code (`PLAN_SCHEMA`; the `#/new` form can overrule it either way). A marketing
course has none, and a notebook reference in a course without the field is a `check`
failure. The Settings tab of a course switches it.

A notebook is `courses/<id>/notebooks/<mid>-<n>.ipynb`, referenced from the module on a
paragraph of its own as an ordinary link - the one relative link `markdown_render` leaves
alone:

```
[Try it: fit the line yourself](notebooks/M03-1.ipynb)
```

`coursekit/notebooks.py` owns the contract. `loader.parse_sections(raw, figures_dir,
notebooks_dir, notebooks_on)` replaces the paragraph with `<div class="notebook" data-nb=...>`
holding a **read-only rendering of every cell**: the markdown through the module's own
renderer, the code escaped, the outputs saved in the file (text, errors, and a `png` or
`jpeg` as a data URI; `text/html` and anything else that could run is dropped, because a
notebook is model output that would render inside the reader's page). The file must be
nbformat 4, under `build.notebookMaxBytes`, with at least one cell; a missing or broken one
is a `check` failure like a figure. The section's `text` excerpt is taken before the swap,
and the section's `public()` carries the code of its notebooks (`build.notebookPromptChars`)
so `placeText` on the Read step can hand it to the tutor.

The page (`07e-notebooks.js`) shows that rendering everywhere - off disk, published, and
when Jupyter is down - and, when served by Studio, asks `GET /api/jupyter` once per Read
step. If a Jupyter server answers, each block gains **Run it here**, which swaps the
rendering for the live notebook in a frame (`page.notebooks.height`), and **Open in a tab**.
The frame's URL is `<jupyter>/notebooks/<id>/notebooks/<file>?token=...`: the server serves
the courses directory, so the file the reader edits and saves is the one the course
carries. Nothing about a notebook is stored in the reader's state.

**The Jupyter server is a third service, never Studio itself.** `studio/jupyter.py` only
probes it (`/api/`, cached for `jupyter.probeCacheSeconds` because `/api/state` is polled)
and tells the page where it is. Both ways of running it read one configuration,
`tools/jupyter/jupyter_server_config.py`, which reads `jupyter.*` and `studio.*` from
settings.json like everything else (`JUPYTER_HOST`, `JUPYTER_PORT`, `JUPYTER_TOKEN`,
`JUPYTER_URL`, `JUPYTER_INTERNAL_URL` override): the root directory is the courses
directory, the token is fixed, and `frame-ancestors` in the Content-Security-Policy names
Studio's origin, because Jupyter's default refuses to be framed.

- `docker compose up` starts it as the `jupyter` service from the same image (Notebook 7,
  ipykernel, numpy, pandas, matplotlib; the pip line in the Dockerfile is where a course's
  packages go). It mounts the courses read-write and `platform/` and `tools/` read-only,
  and **not** `~/.claude`: it runs code a model wrote, and a kernel with the OAuth
  directory in reach is one `open()` from the token. Studio reaches it as
  `JUPYTER_INTERNAL_URL=http://jupyter:<port>`; the browser at the published loopback port.
- `python platform/build.py jupyter` runs the same thing on the host (`pip install
  notebook` first).

The token reaches the page through `GET /api/jupyter` on Studio's loopback origin and is
never in the built HTML (`SETTINGS.page()` does not carry it; a test checks). The published
loopback port is the boundary, as for Studio: do not drop the `127.0.0.1:` prefix.

Studio writes them (`studio/notebooks.py`), the twin of `figures.py`: `prompts.notebooks`
asks for up to `generation.notebooksPerModule` notebooks of at most
`generation.notebookCells` cells in a delimited text format (`=== NOTEBOOK`, then
`--- markdown` / `--- code` cells; code inside a JSON string is a parse failure waiting to
happen), `coerce.fix_notebooks` keeps the ones naming a real section with at least one code
cell, `make_notebook` assembles the nbformat 4 file with no outputs, and `write_notebooks`
replaces the module's old notebook files and reference lines. A generation run writes them
right after each module's text and figures when the plan declares the runtime; `extend`
and a full `rewrite` do the same for a course that declares it; a patch keeps the reference
lines. `POST /api/courses/<id>/notebooks` writes for every module without any
(`{all: true}` replaces them all) and `POST /api/courses/<id>/modules/<mid>/notebooks` for
one; both are refused for a course without the runtime. The Modules tab and the row menu
offer them; `remove_module` trashes a module's notebooks with its file; the Files tab can
edit an `.ipynb` by hand (the PUT checks it). `TestNotebooks` and `TestJupyterSettings` in
`test_build.py` and `TestNotebookWriting` and `TestJupyter` in `test_studio.py` cover it.

## Course Studio

`platform/studio/` is a second front end onto `coursekit`, for what is awkward in a terminal:
watching a long generation run, editing a proposed curriculum before committing to it, and
reading validation errors next to the course they belong to.

| Module | Job |
|---|---|
| `claude_cli` | Studio’s way in to `coursekit.llm`: the names the rest of Studio calls, and the `Reporter` that forwards every call to the job on the thread |
| `jobs` | background work with a replayable event log |
| `prompts` | every prompt Studio sends |
| `curriculum` | the plan a course is written from: `make_plan`, `normalise_plan`, `plan_from_course`, `load_plan` / `reconstruct_plan` for a resume |
| `coerce` | model output into shapes the validator accepts: `fix_quiz_item`, `fix_assessment`, `fix_suggestions`, `fix_spec`, `fix_review` |
| `generator` | the pipeline: plan → approve → write → validate → build; the writers (`write_module`, `write_study_data`) and `build_course` / `check_course` |
| `editing` | one module of an existing course: `extend`, `rewrite`, patch mode, `draw` (figures), `store_module_data` |
| `figures` | figures for one module: parse the delimited reply, write `figures/<mid>-<n>.svg`, put the references in the text |
| `notebooks` | notebooks for one module: parse the delimited cells, write `notebooks/<mid>-<n>.ipynb`, put the references in the text |
| `jupyter` | the Jupyter server: is it reachable, and what a served page is told (`GET /api/jupyter`); `build.py jupyter` |
| `models` | the model list Studio offers: validated, saved to `state/settings.json`, live everywhere after `SETTINGS.reload()`; `GET/PUT /api/models`, `/api/models/reset`, `/api/models/test` |
| `discover` | keeps that list current without anyone typing an id: Claude Code's catalog read out of the installed binary, Anthropic's `GET /v1/models` when a key is set; `plan()` merges, `schedule()` runs daily, `POST /api/models/discover` runs now |
| `reviews` | what Claude or the owner thinks of a module, under `state/reviews/` |
| `catalog` | what the API reports: `course_summary`, `course_detail`, `state`, `calendar`, `settings_view` |
| `runtime` | what one running Studio shares: state paths, `REGISTRY`, `PREFS`, `store()` |
| `progress` | the platform-side copy of reader state, one JSON file per course |
| `manage` | course operations that need no model: settings form, move or remove a module, trash a course |
| `transfer` | a course in or out as a zip or a git clone |
| `search` | every course searched at once, through the build's own loader |
| `prefs` | Studio-wide preferences in `state/studio.json` — the model, the reader profile |
| `files`, `ids`, `errors` | shared helpers: atomic `read_json` / `write_json` / `write_text`, the id patterns, `GenerationError` |
| `log` | the `studio` logger: rotating file + in-memory ring, read by `/api/logs` |
| `server` | HTTP: the route table, SSE, and the static UI in `ui/` |

**Every route is one method on `Handler`, registered with `@route(METHOD, pattern)`.** The
pattern's named groups become the method's arguments; a `course_id` group is resolved (400
for a bad id, 404 for a missing course) and a `mid` group checked before the method runs.
The docstring at the top of `server.py` lists every route and `test_studio.py` checks the
two agree. To add a route: write the method, decorate it, add the line to the docstring.

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
resort. `prefs.models()` is the only list the Settings page offers, and it is
`SETTINGS.models`: `models.list` from `settings.json` under whatever the settings page
saved over it. **The list is editable without touching a committed file.** The "Models on
offer" card on `#/settings` (`ui/js/31-models.js`) edits id, alias, label and note per row,
reorders, adds and removes; Save is `PUT /api/models` with the whole list, which
`studio/models.py` validates (an id `claude --model` would take, no name used twice, never
empty) and writes to `state/settings.json`, the Studio layer of the settings, then
`SETTINGS.reload()`. "Back to the platform's list" is `POST /api/models/reset`. A row's
Test button is `POST /api/models/test`: `claude_cli.probe` asks the CLI once with that
model only, no fallback chain, within `claude.probeTimeout`, so a typo or a retired id is
refused on the settings page and not at module 8 of a run. A served course page adopts the
list Studio reports in `/api/state` (`adoptStudioModels` in `14-conn.js`, `claude.models`
with `apiId` and `claude.defaultModel`), so it needs no rebuild; a page off disk keeps the
list it was built with, and the bridge reads the layer when it starts.

**Nobody has to type a new model's id.** `studio/discover.py` keeps the list current from
two sources: the catalog inside the installed `claude` binary (the rows its `/model` picker
offers and the fuller table of everything `--model` accepts; `claude update` refreshes it,
and Studio's calls go through that binary, so it is the list that decides whether a run
works) and, when `ANTHROPIC_API_KEY` is set in `.env` or the environment (`anthropic.apiKey`,
masked on the settings page with the other `SECRET_KEYS`, never sent to a page), Anthropic's
`GET /v1/models` (`anthropic.modelsUrl`), from which only models newer than the newest one
already listed are taken. Claude Code's picker rows come from the catalog it last fetched
(`cache/model-catalog/*.json` under `CLAUDE_CONFIG_DIR` or `~/.claude`) when there is one,
else from the seed in the binary. `plan()` is the pure merge: offered and missing is added
with a note saying when and from where; listed but unknown to every source that answered is
a *candidate*; a dated snapshot and its bare id are one model. `removals()` decides the
candidates: absent from Anthropic's list means gone; unknown to the binary's table alone is
not enough - Claude Code 2.1.252 in the image accepted `claude-fable-5-1` without listing
it - so such a candidate stays unless one real call (`claude_cli.probe`) is refused. The
list is never emptied. `run()` applies it through `models.replace` and writes
`state/models-discovery.json`; `schedule()` runs it `discovery.startDelaySeconds` after
Studio starts and every `discovery.hours` (0 turns it off); the Models card shows the last
check and has "Check now". Reading the binary is a regex over its bytes (`CLI_SELECTOR`,
`CLI_CATALOG`), so a build that changes the shape reports "could not be read" and changes
nothing. Studio on the host and Studio in the container share `state/settings.json`, so
each check is made against the Claude Code that runs it. **Every form that
writes a course picks its model** - new course,
resume, add a module, patch or rewrite - from the same list (`ui/js/28-model.js`:
`modelChoice`, `modelBrief`), preselected to Studio's default and sent as `model` in the
request; `Handler._model` keeps a known alias or id for that job alone and falls back to
the default otherwise. `/api/state` carries the list as `claude.models` so no form needs a
second request. The one-click actions - Review with Claude, Draw figures, Write notebooks -
have no form, so the Modules tab carries one pick for all three (`quickModelBar`,
`quickModelBrief`; `modelPick.quick`, kept for the session) and their row-menu entries name
the model that will run. In the course page the tutor's model sits under the chat box, always visible
(`modelPicker` in `17-rail.js`), in the rail's chat menu and on the Settings page; every
copy carries `data-model-pick` so `setTutorModel` (`14-conn.js`) can keep them in step
through `syncModelPickers`, and all of them write `STATE.bridge.model`, which every
`askBridge` call sends. The default is
Opus 5: the best writing for the price, with Fable 5.1 on the list for the course that has
to be right and Sonnet or Haiku for a cheap patch.

**When Claude says no, the reason decides what happens next.** Claude Code reports an
exhausted account, an overloaded server and a model it does not recognise the same way — a
non-zero exit and a line of stderr — so `coursekit/llm/failures.py` names the kind once
(`quota`, `auth`, `model`, `transient`, `timeout`, `unknown`) and everything above it acts
on the name rather than reading stderr again. It sits in `coursekit`, stdlib-only, because
`tools/bridge/claude-bridge.py` imports it from outside the package the way it imports
`settings`.

- **`transient` is waited out**, on the same model: `claude.retries` further attempts with
  the wait doubling from `claude.backoffSeconds` to `claude.backoffMaxSeconds`. A
  forty-minute run used to die at module 8 of 9 on a five-second outage.
- **`model` moves down the chain**, which is what the chain was for.
- **`quota`, `auth` and `timeout` end it at once.** Every model on the chain draws on the
  same account, so trying the next one wastes a minute and then tells the reader the wrong
  story — "Claude Code refused Opus" when the truth is "this account is out until 3pm". A
  usage-limit message that names its reset time has it repeated back.
- **The message is a sentence, not stderr.** `explain()` writes what to do; the CLI's own
  words go to `detail` and the log. A `ClaudeFailed` carries `kind`, `detail` and
  `resets_at`; `Job.why` carries the kind to the job screen, `/api/ask` sends it as `why`,
  and the bridge sends the same field — so all three routes reach the page alike. There,
  `troubleOf(err)` reads it and the failed answer offers **Try again** (`railRetry` re-asks
  the same question, no retyping) plus **Check the connection** only when Settings is
  actually the answer.
- **Only a model's own refusal removes it from the list.** `discover.removals` used to drop
  any candidate a probe would not answer for, so a nightly check run while the account was
  out of quota would quietly shrink the model list.

**A run can be resumed.** `generate()` saves the approved curriculum to `plan/plan.json`;
`brief["resume"]` reloads it through `curriculum.load_plan` (or `reconstruct_plan()` rebuilds
one from `course.json` for courses made before that), skips the approval gate, keeps every module and study-data entry
already on disk, and writes only what is missing. `POST /api/courses/<id>/resume` takes
`{figures, notebooks}`; the course page and the failed-job screen offer the button, with
both switches, when `can_resume()` says so.

**Every form that writes module text shows the same two switches** - draw figures, write
notebooks - and sends them as `figures` and `notebooks` in the request (`ui/js/26-media.js`:
`mediaChoices`, `mediaBrief`). A new course lets the planner decide about notebooks
(`notebooks: "auto" | "yes" | "no"`, see "Notebooks"); a resume, an added module and a
rewrite take booleans, and the notebooks switch is offered only when the course declares
them. The generator, `editing.extend` and `editing.rewrite` honour both; a patch never
touches either.

**What a job is doing is visible while it runs.** `jobs.current()` returns the job on the
calling thread, so `claude_cli.ask` needs no job in hand: it emits a `call` event when a
CLI call starts (`what`, `model`, prompt size, timeout) and when it ends (seconds, reply
size, or the error), narrates a model fallback and a JSON retry as `log` events, and every
generator call site passes `what=` ("the text of M03", "the quiz and flashcards for M03").
`Job.summary()` carries the last `progress` event and the `call` in flight, so `/api/state`
can say where a job is without replaying it: the header pill (`#jobstate`), the library
cards and the course page show that line and poll every few seconds while anything runs.
The job screen ticks once a second - step, time on this step, total, a rough estimate from
the steps already finished, and what Claude is writing right now - and the tab title
carries the step. Check, Build and an import are synchronous and show a spinner with a
clock (`busy()` in `studio.js`) with the buttons disabled meanwhile.

**Log first, then look.** `log.log` is the `studio` logger. Every Claude call logs model,
duration, prompt/reply size and stderr on failure; every job event logs a line; every
unhandled route error logs a traceback. Read it at **Settings & logs** (`#/settings`) or in
`state/logs/studio.log`. `STUDIO_LOG_LEVEL=DEBUG` adds access lines. Rotation size and
count are `logs.maxBytes` / `logs.backups`.

**Model output is trusted for prose and distrusted for structure.** `coerce.fix_assessment`
and `fix_suggestions` coerce replies into shapes the validator accepts — clamping quiz answer
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
| `POST /api/courses/<id>/extend` | one new module on a topic. `editing.extend` asks for a design that fits the existing curriculum (`prompts.module_spec`), writes it under the next free id — ids are never reused because progress is keyed by them — appends it to the chosen part, writes its study data to `data/*/<mid>.json`, adds the short title, rebuilds. |
| `POST /api/courses/<id>/modules/<mid>/rewrite` | same id, same file, same position; the notes become `prompts.direction`. With `mode: "patch"` (`editing._patch`) the module as it is goes to `prompts.patch_module` and comes back with only the notes applied, the quiz is patched in place through `prompts.patch_assessment`, and the suggested questions are kept unless a `##` heading changed - a full rewrite regenerates every sentence, so each pass fixes the last review's findings and creates new ones. The Studio form defaults to patch when opened from a review. `editing.store_module_data` replaces the entry in whichever file already holds it, so the validator never sees two claims on one id. |
| `GET/PUT /api/courses/<id>/files?path=` | raw editing of any `.md`/`.json` inside the course. `resolve_course_file` confines the path; JSON is parsed before it is written. |

Both jobs stream events like a generation run and end with a build. A rewrite keeps the
reader's progress for the module but may leave section ticks misaligned if the section
count changes — the UI says so.

Without a model (`studio/manage.py`):

| | |
|---|---|
| `GET/POST /api/courses/<id>/settings` | title, tagline, audience, practitioner, tutor persona, the notebooks runtime (off, or a kernel and packages), part names/hours/blurbs, milestones. **`id` is refused**: it is the reader's storage key. |
| `POST /api/courses/<id>/modules/<mid>/remove` | the file moves to `state/trash/`, its assessment and suggestion entries are dropped from whichever files hold them, its short title and its `order` entry go; the reply carries the check result. |
| `POST /api/courses/<id>/modules/<mid>/move` | `{part, index}`: reorder within a part or move to another; writes `order`, moves the file, never touches study data. |
| `POST /api/courses/<id>/modules/<mid>/review` | a job: Claude reads the module against the pedagogy checklist in `prompts.review` and returns a verdict, gaps, errors, quiz issues and a rewrite brief. Stored under `state/reviews/` by `reviews.py`, not in the course - it is an opinion about content, not content. The module row shows the verdict; "Rewrite with these notes" turns the brief into a rewrite. A review older than the module file comes back with `stale: true` (`load_reviews` compares `at` to the file mtime) and the row shows it greyed as "before edit": a rewrite or a hand edit never changes a verdict, only a new review does. The verdict scale is calibrated in the prompt: "solid" means publishable, minor findings do not lower it. |
| `POST /api/courses/<id>/modules/<mid>/accept` | `{accepted: bool}`: the owner's own verdict, "this is good". `reviews.accept_module` stores it in the same review file (`accepted`, and `ownerOnly` when there was no review), the row shows "good" over whatever Claude said, and it goes stale like a review when the module changes. |
| `POST /api/courses/<id>/delete` | needs `{confirm: <id>}`; moves `courses/<id>` and `dist/<id>` to `state/trash/<id>-<stamp>/` and forgets the progress copy. |

The reader's open questions (`state.marks` with status `open`/`answered`) come back in the
course detail as `questions`; the Studio Questions tab turns any of them into an Add-a-module
or Rewrite brief through query params (`?tab=add&q=…&notes=…`, `?rewrite=<mid>&q=…`). The
same tab shows the reader's knowledge gaps (`learner` in the detail, see "The learner
memory") with a Rewrite link each.

**Jobs persist.** `jobs.Registry(store_dir)` writes a finished job's events and result to
`state/jobs/<id>.json` and reads them back as `StoredJob`, so `/api/state` and
`/api/jobs/<id>/events` work across a restart. Ids carry a per-process prefix so runs never
collide.

### The Studio UI

`ui/js/` is one file per screen, loaded in name order by `ui/index.html` (`00-core.js` is
the plumbing every screen uses, `90-router.js` boots the app and must stay last), and
hash-routed: `#/` library with a "today" strip and progress cards, `#/new`,
`#/course/<id>` (tabs: Modules, Add a module, Questions, Files, Settings),
`#/course/<id>/edit?path=`, `#/job/<id>`, `#/jobs` (the recent runs, so a finished or failed
one is reachable without the back button), and `#/settings` — Studio-wide: the model, whether
Jupyter is up, every resolved platform setting with the layer it came from, where things
are, and a live log viewer polling `/api/logs`. The course
page reads `GET /api/courses/<id>`, which parses modules and is therefore not used for the
listing; `/api/state` counts module files instead (`catalog.module_ids`). `test_studio.py`
boots the whole UI under node with `page_smoke.js`, so a name one file uses and no file
declares fails the suite.

**Nothing hijacks the screen you asked for.** A live run is a banner with a link
(`liveJobBanner`), not a redirect; a missing Claude Code is one sentence at the top
(`claudeGate`, `claudeBanner`), not a row of silently greyed buttons; the nav highlights the
section that owns the route, not only the three top-level ones (`NAV_OWNER`). Under 720px
the nav collapses into a ☰ menu, because otherwise New course and Settings are unreachable.

**A course says when it is out of date.** `catalog.newest_source` compares the newest
`.md`/`.json`/`.svg`/`.ipynb` in the course against the build's timestamp; `dirty` in the
summary is what turns Rebuild into the one primary button on the course page.

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

## Code conventions

The rules below are what keeps the code readable. The ones a test can hold, a test holds
(`TestCodeConventions` in `test_build.py`, `TestServerConventions` in `test_studio.py`).

### Python (`platform/`, `tools/`)

- **One module, one job, said in its docstring.** Every module starts with a docstring that
  says what it is for and, when it is not obvious, why it is shaped the way it is. A test
  fails on a module without one. A module past ~500 lines is two jobs; split it the way
  `generator.py` became `curriculum` + `coerce` + `generator` + `editing` + `reviews`.
- **`_name` is private to its module.** Nothing imports or calls another module's
  underscore name (a test checks). Something two modules need is public, named for what it
  is, and lives in one place: file helpers in `studio/files.py`, id patterns in
  `studio/ids.py`, the plan in `curriculum.py`. Do not copy a helper into a second module.
- **Every file write goes through `files.write_json` / `files.write_text`.** They create the
  directory, write beside the target and rename over it, and end the file with one newline.
  No `open(path, "w")` in Studio outside `files.py`.
- **Every setting comes from `settings.json`** through `SETTINGS.get(...)`, read once at
  import into a module constant with a name that says what it bounds (`MAX_BODY`,
  `QUIZ_ITEMS`). See "Settings" above.
- **Model output is trusted for prose and distrusted for structure.** Anything a model
  returns as JSON passes through `coerce.py` before it is written, and the validator in
  `coursekit.validate` is the authority on what is valid.
- **A route is a decorated method.** `@route("POST", COURSE + r"/thing")` on `Handler`,
  a line in the `server.py` docstring, and the guards it needs (`_idle`, `_claude`) at the
  top. No path parsing inside a handler; no `if path ==` chains.
- **Comments say why, names say what.** A function whose body needs a comment to follow is
  two functions. `# noqa: BLE001` on a bare `except Exception` says why it is broad.
- **Style:** `from __future__ import annotations`, type hints on public functions, 100
  columns, `%`-formatting for log lines (lazy) and either for strings, no f-strings inside
  prompts (they are `%`-templates). Standard library only in `coursekit.settings` and the
  bridge, which import it from outside the package.

### JavaScript and CSS (`platform/web/`, `platform/studio/ui/`)

- **Prettier formats everything** (`npm run format`, config in `.prettierrc`). The test
  runs `prettier --check` when it is installed. One statement per line: never
  `a; b; c` on one line, never a `function f() { x; y }` one-liner with two statements.
- **One file per concern, in load order.** The numeric prefix is the load order; a file is
  a screen (`ui/js/20-course.js`) or a concern (`web/js/17-convos.js`). Past ~700 lines a
  file is two concerns (a test fails on a page file over 700 lines). Insert a new file with
  a free number or a letter suffix on its neighbour, not by renumbering.
- **Globals are named for what they are, in full.** `STATE`, `progressOf`, `convos()`,
  `rail.pinned` - never `S`, `P`, `CV`, `pi`. A file's own mutable state lives in one
  object at its top with a comment per field (`rail` in `17-rail.js`), not in a row of
  `let`s. Single letters are for lambda parameters and loop counters only, and only when
  the noun is obvious from the line (`m => m.id`).
- **Stored shapes are a contract.** Everything under `STATE` is in readers' localStorage
  and in `state/progress/`; a message is `{r, t, ts}` because every save says so. Add a
  field with a default in `blank()` and `upgrade()`; never rename or repurpose one.
- **No colour, size or component of your own** (see "The design system"): a colour comes
  from `00-tokens.css`, a button from the `.btn` family, a spacing from a `.gap-*` or
  `.rowline` utility. An inline `style=` is for a value only the code knows - a bar's width,
  a colour picked from a score - and a test caps how many there may be.
- **A control says its name and its state.** An icon button carries `aria-label`; a toggle
  carries `aria-pressed`; a menu button carries `aria-expanded` and `aria-haspopup`; a
  dialog carries `role="dialog" aria-modal="true"`, traps Tab and hands the focus back.
  Every input has a label, `.visually-hidden` when the layout does not want to show one.
- **Every action answers.** A request shows it is running (`busy()` in Studio, `graderStart`
  in the page), a failure lands where the eye already is with a way to retry, and anything
  that cannot be undone asks first through `confirmModal` - never `confirm()`.
- **No literal that belongs to a setting or a course** (see "Settings" and "The two-layer
  rule"): addresses, models, limits and layout sizes come from `CFG.platform`; every
  subject-specific string comes from `CFG`. A test fails on both.
- **A template literal is HTML, not logic.** Compute the values first, in named
  `const`s, then interpolate them; a `${cond ? "..." : "..."}` inside markup is fine, a
  nested one is not. Anything longer than a screen becomes a function that returns HTML.
- **Behaviour goes through `save()`.** State changes call `save()` once at the end, which
  writes localStorage and schedules the sync; nothing writes localStorage directly outside
  `01-state.js`.
- **Boot under node before you ship.** `node platform/tests/page_smoke.js <built page>`
  and the same with `platform/studio/ui/js/*.js` catch an undeclared name; both run from
  the test suites. `--checks <file.js>` runs a checks file inside the booted page, which
  is how page logic that needs a real `STATE` is tested (`learner_checks.js`,
  `rail_checks.js`).

### Tests

- Every module in `studio/` has tests in `test_studio.py`; the engine in `test_build.py`.
  A new route gets a line in the server docstring (the test checks it resolves) and, when
  it does real work, a test through `Handler` with a stub `claude_cli.ask`.
- Tests stub Claude by replacing `claude_cli.ask`; they never make a network call.
- A test that guards a rule of this file names the rule in its docstring.

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
