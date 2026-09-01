# Course platform

A generic engine for building interactive study courses. You describe a theme and an hour
budget; the `course-author` skill writes the course; `platform/build.py` renders it into one
self-contained HTML file that tracks progress, runs spaced repetition, and lets the reader
ask Claude about whatever passage they are looking at.

The marketing course in `courses/marketing/` is the reference implementation. It was the
original project; the platform was extracted from it.

## Layout

```
platform/                   the engine — knows nothing about any subject
  build.py                  CLI entry point
  coursekit/                the build package
  studio/                   the local web app: generate + build from a browser
  web/                      front-end source: shell.html + css/ + js/
  tests/                    test_build.py, test_studio.py
courses/<id>/               one course, all content
  course.json               the manifest that makes a folder a course
  modules/<part>/M01-*.md   the teaching
  plan/ reference/ templates/
  data/assessments/ data/suggestions/
dist/<id>/                  build output (generated — do not edit)
bridge/                     local proxy so a course page can reach Claude
docker/Dockerfile           one image; Studio and the bridge differ only by command
compose.yaml                both services, restart: unless-stopped
.claude/skills/course-author/   the skill that writes a course from a brief
```

## Commands

```
python platform/build.py list                            what courses exist
python platform/build.py new --theme "X" --hours 30      scaffold an empty course
python platform/build.py check <id>                      validate; reports everything at once
python platform/build.py build <id>                      validate, then write dist/<id>/
python platform/build.py studio                          open Course Studio in a browser
```

Or double-click `start-studio.bat`. Studio is the UI route: it generates a course from a
theme and an hour budget, and runs check/build without a terminal.

Tests:

```
python platform/tests/test_build.py      27 tests — engine
python platform/tests/test_studio.py     42 tests — Studio
```

Requires Python 3 and the `markdown` package (`pip install markdown`). Nothing else.

## Running in Docker

```
docker compose up -d --build     start both, and on every boot from now on
docker compose logs -f studio    watch a generation run
docker compose down              stop them
```

Needs a `.env` holding `CLAUDE_HOME` — the path to the host's `~/.claude`. Copy `.env.example`.

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

### The tutor over HTTP

A course served from Studio at `http://127.0.0.1:8790/course/<id>/…` is not a `file://` page,
but the tutor still works through the bridge: `bridge/claude-bridge.py` sends
`Access-Control-Allow-Origin: *`, and `connMode()` in `14-conn.js` picks the bridge route
whenever it answers. `isLocalFile()` only shapes an error message — it gates nothing. So with
both containers up, the `file://` requirement goes away.

## The two-layer rule

**The engine must never mention a subject.** No "marketing", no "marketer", no course title.
Everything subject-specific reaches the browser through the `CFG` object built by
`CourseConfig.runtime()` in `platform/coursekit/config.py`, sourced from `course.json`.

If you are about to write a course-specific string into `platform/web/js/`, add a `CFG` field
instead. This is checkable:

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
| `loader` | module markdown → `Module`/`Section` objects |
| `assessments` | quizzes, flashcards, suggested questions; merges the per-part files |
| `library` | glossary, mental models, worksheets, plan pages — all optional |
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
new file by picking a free number, not by renaming everything after it.

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
- Every quiz `answer` is a valid zero-based index into its `options`, and has a `why`.
- Every flashcard has both `front` and `back`.
- **A module's suggestion list has exactly one entry per `##` section.** They are matched by
  position. This is the most common authoring failure.
- No duplicate module ids; no assessment or suggestion entry that matches no module.

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
| `generator` | the pipeline: plan → approve → write → validate → build |
| `server` | HTTP, SSE, and the static UI in `ui/` |

**It binds to 127.0.0.1, and that is a security boundary, not a default.** Studio writes
files and spawns processes. Do not make it listen on another interface.

**Prompts go in on stdin, never as `-p <prompt>`.** A Windows command line caps at 8191
characters; `bridge/claude-bridge.py` has to trim to ~5500 to stay clear of it. Course
prompts are an order of magnitude larger. stdin removes the ceiling.

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

## Progress and chat storage

All reader state — completion, timers, quiz answers, flashcard scheduling, highlights, notes
and every conversation — lives in the browser's `localStorage` under `CFG.storageKey`, which
is `course_<id>_v1`. Courses are therefore isolated from each other by construction.

There is no server. Progress moves between machines through **Backup / restore** in the
sidebar. Changing `storageKey` orphans existing progress, so do not change a course's `id`
after anyone has started it.

## Gotchas

- **Windows console encoding.** `platform/build.py` forces UTF-8 on stdout/stderr. Courses
  use real typography and cp1252 cannot encode it. Keep that shim.
- **`</` inside embedded JSON** would close the `<script>` tag early; `renderer._embed_json`
  escapes it. Do not swap in a plain `json.dumps`.
- **Relative markdown links do not survive** — a one-file site cannot resolve them, so they
  render as italic text. Do not write cross-module links.
- **`dist/` is generated.** Edit `platform/web/` or `courses/<id>/`, never the built HTML.
