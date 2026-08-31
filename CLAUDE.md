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
  web/                      front-end source: shell.html + css/ + js/
courses/<id>/               one course, all content
  course.json               the manifest that makes a folder a course
  modules/<part>/M01-*.md   the teaching
  plan/ reference/ templates/
  data/assessments/ data/suggestions/
dist/<id>/                  build output (generated — do not edit)
bridge/                     optional local proxy to Claude Code instead of an API key
.claude/skills/course-author/   the skill that writes a course from a brief
```

## Commands

```
python platform/build.py list                            what courses exist
python platform/build.py new --theme "X" --hours 30      scaffold an empty course
python platform/build.py check <id>                      validate; reports everything at once
python platform/build.py build <id>                      validate, then write dist/<id>/
```

Requires Python 3 and the `markdown` package (`pip install markdown`). Nothing else.

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

## Authoring content

Use the `course-author` skill. Its references are the specification:

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
