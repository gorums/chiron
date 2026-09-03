# Course platform

Build an interactive course on any subject, for any number of hours, and study it in your
browser.

You pick a theme and a budget — "marketing, 30 hours"; "negotiation, 20 hours" — and the
authoring skill writes the whole thing: the curriculum, the modules, the glossary, the
worksheets, the quizzes and the flashcards. The build turns that into a single HTML file
that tracks your progress, schedules your revision, and lets you ask Claude about whatever
paragraph you are stuck on.

The marketing course was the original project and is now the reference implementation. It
lives in its own repository, like every course: this repository is the platform alone.

---

## Always-on, with Docker

One command, once. Both services then come back on every boot, so there is nothing to start
by hand:

```bash
cp .env.example .env       # set CLAUDE_HOME to your ~/.claude path
docker compose up -d --build
```

| | |
|---|---|
| **http://127.0.0.1:8790** | Course Studio — write and build courses |
| **http://127.0.0.1:8787** | the bridge — the tutor inside a course page |

Both ports, and every other default of the platform, are in `platform/settings.json`; a
line in `.env` (`STUDIO_PORT=…`, `BRIDGE_PORT=…`, see `.env.example`) overrides them.

`docker compose logs -f studio` watches a generation run; `docker compose down` stops both.

It mounts your `~/.claude` so the containers use the Claude Code subscription you are already
signed in to — no API key, no per-token bill. Both ports are published to `127.0.0.1` only,
so nothing outside your machine can reach them.

Open **http://127.0.0.1:8790** and everything happens there:

- **Your courses**, each with how far you are, and a **Continue** button that opens the next
  module. Progress is kept by the platform in `state/progress/`, so a rebuild, a new browser,
  or a container restart does not lose it.
- **Study** a course served from Studio. It asks its questions through Studio's own Claude
  Code — no key, no bridge, nothing to open off disk.
- **Grow a course** when a module leaves you wanting more: the module footer links straight
  to *Add a module* (a new module on that topic, designed to fit the curriculum) or
  *Rewrite* (the same module again, with your direction). Both rebuild when done.
- **Edit any file** of a course — modules, glossary, quizzes — then Check and Build.
- **Your open questions**, collected from what you highlighted while reading, each one a
  click away from becoming a new module or a rewrite brief.
- **Settings as a form** (title, audience, tutor persona, parts, milestones), remove a
  module, delete a course — all reversible: nothing is erased, it moves to `state/trash/`.
- **A run that dies can be resumed.** The curriculum is saved; *Resume the run* keeps what
  was written and does only the rest.
- **Settings & logs**: pick the model Studio writes with, and read the log of every Claude
  call and job step when something goes wrong.

## Or run it directly

Double-click **`start-studio.bat`** (or run `python platform/build.py studio`). Course Studio
opens in your browser.

1. **Describe it** — theme, hours, who is studying. "negotiation, 20 hours, a complete beginner".
2. **Approve the curriculum** — Claude proposes the parts, the module list and the time split.
   Edit the titles and minutes, drop modules you do not want, then say go. Nothing is written
   until you do: twenty modules take a while, so this minute is worth it.
3. **Watch it write** — each module appears as it lands, with its section and word count. You
   can stop at any point, and everything written so far stays on disk.
4. **Open it** — the course is validated and built. One button opens it.

Studio also lists the courses you already have, with a page for each: the modules and your
progress through them, **Add a module**, **Rewrite** for any module, a **Files** tab that
edits anything in the course, and **Check** and **Build** — so you never need a terminal for
the ordinary work.

It uses the `claude` command you are already signed in to, so there is no API key to manage
and no separate per-token bill.

## Or from the terminal

```bash
pip install markdown

python platform/build.py list                                   # what you have
python platform/build.py new --theme "negotiation" --hours 20   # scaffold, no content
python platform/build.py check negotiation                      # validate
python platform/build.py build negotiation                      # -> dist/negotiation/
```

You can also ask Claude, in this folder:

> Build me a 20-hour course on negotiation.

That runs the `course-author` skill, which writes the content file by file and can iterate on
it with you — slower than Studio, but you stay in the loop on every module.

---

## What you get

A single self-contained page — no server, no install, works offline:

- **Read** modules split into sections, each with its own progress checkbox and timer.
- **Predict → Read → Retrieve → Elaborate → Apply**, the five steps every module runs.
- **Quizzes** that ask you to rate your confidence, then show you the gap between how sure
  you felt and how right you were.
- **Flashcards** on a spaced-repetition schedule, unlocked as you finish modules.
- **Highlight anything** to turn it into a note or a question.
- **Ask Claude** in a side rail that always knows which section you are reading, with
  suggested questions written for that specific passage.
- **Search everything** with `/`.
- **Backup / restore** to move progress between machines.

---

## Two files, one difference

Each build produces two copies:

| File | Use it for |
|---|---|
| `<course>-local.html` | **Studying.** Open it straight from the folder. This is the copy that can talk to Claude. |
| `<course>.html` | Publishing. Everything works except the tutor — a hosted page is not allowed to call Anthropic. |

If you open the course **from Studio**, the tutor already works and progress is kept on the
platform — nothing to set up. Opening the local copy straight off disk still works too: go to
**Settings** in the sidebar and either paste an Anthropic API key (a typical question costs a
fraction of a cent) or start the bridge to use a Claude Code subscription instead — see
`tools/bridge/README.md`.

---

## Layout

```
platform/          the engine — subject-agnostic
  build.py         the CLI
  coursekit/       the build package
  studio/          the local app: generate and build from a browser
  web/             front-end source: shell.html, css/, js/
courses/<id>/      one course, its own git repository (gitignored here — see below)
dist/<id>/         built output
state/             yours, not the course's: progress/, finished jobs/, trash/
tools/bridge/      local proxy, so a course page can reach Claude
docker/            the image both services share
compose.yaml       Studio + bridge, restarting on every boot
start-studio.bat   double-click to open Course Studio without Docker
```

Studio listens on `127.0.0.1` only — nothing outside your machine can reach it.

A course is a folder with a `course.json` in it. Everything subject-specific lives there;
the engine holds no opinions about what you are learning.

## One platform repository, many course repositories

Courses are not part of this repository. Each one is a git repository of its own — markdown
and JSON, nothing else — and the platform only needs the directory that holds them:

```
python platform/build.py where          # prints the courses and dist directories in use
```

By default that is `courses/` inside this folder, which is gitignored, so clone a course
into it and it appears in Studio and in `build.py list`:

```
git clone https://github.com/<you>/<course>.git courses/<id>
```

To keep courses somewhere else, put `COURSES_DIR=<path>` in `.env` (relative paths count
from this folder; `../courses` is a sibling directory). Docker reads the same line.

A course Studio generates is an ordinary folder with a `README.md`; turn it into a
repository the usual way:

```
cd courses/<id>
git init && git add -A && git commit -m "Initial course"
git remote add origin https://github.com/<you>/<id>.git && git push -u origin HEAD
```

Progress, finished jobs and trash stay in `state/` on the platform side, keyed by course
id, so a course repository never carries anyone's reading history.

See `CLAUDE.md` for how the build works and the rules that keep the two layers apart.
