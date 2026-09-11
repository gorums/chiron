# Course Platform
  
---
 
### 🧑 Alejandro
 
> Do you understand what is this all about?
 
---
 
### 🤖 AI
 
> Yes. You built a local tool that turns "teach me X in N hours" into a complete, rigorous self-study course, and then helps you actually learn it. It isn't just content; the course keeps track of how you're learning.
 
> It has two halves:
 
> **1. Authoring (Course Studio, or the `course-author` skill).** You give a theme, hours and audience ("negotiation, 20 hours, beginner"). A model proposes a curriculum, and nothing gets written until you approve it. Then it writes module by module: markdown text, SVG diagrams, glossary, worksheets, quizzes, flashcards, suggested tutor questions, and notebooks for courses you learn by coding. A `check` step rejects any course that breaks the format rules. After that you can still review, patch, rewrite or add modules, and your own knowledge gaps can feed straight into those rewrites.
 
> **2. Studying (the built HTML page).** Every module follows the same learning-science loop: **Predict → Read → Retrieve → Elaborate → Apply → Close the gaps**. On top of that sit spaced-repetition flashcards, a queue of the questions you missed, confidence ratings, mastery levels, checkpoints, a study plan and streaks. There's also an AI tutor in a side rail. It follows the section you're reading, grades your written answers, role-plays a persona, and keeps a "learner memory" of your weak spots.
 
> A few design rules hold it together:
 
> - **Two layers kept apart.** The engine (`platform/`) never mentions a subject. Everything about the subject lives in each course's `course.json`, and a test fails the build if the two leak into each other.
> - **Courses are just folders.** Markdown, JSON, SVG and notebooks, each one its own git repo. Your progress lives separately in `state/`, so a course never carries anyone's reading history.
> - **Model-agnostic.** It runs on the Claude Code or Codex command-line tools you're already signed in to, or on API keys, or on local models, all configured in `platform/settings.json`.
> - **It runs only on your machine** (127.0.0.1), via Docker or `start-studio.bat`.

# Ready!

**Build an interactive course on any subject, for any number of hours, and study it in your
browser.**

You give a theme and a budget — "marketing, 30 hours"; "negotiation, 20 hours" — and a model
writes the whole thing: the curriculum, the modules, the diagrams, the glossary, the
worksheets, the quizzes and the flashcards. The build turns that into **one self-contained
HTML file** that tracks your progress, schedules your revision, remembers what you keep
getting wrong, and lets you ask a tutor about whatever paragraph you are stuck on.

---

## Contents

- [Start here](#start-here) — Docker, or double-click, or terminal
- [Studying a course](#studying-a-course) — what the page does
- [Writing a course](#writing-a-course) — Studio, and the authoring skill
- [Models and providers](#models-and-providers) — who writes and who answers
- [Notebooks and Jupyter](#notebooks-and-jupyter)
- [Two files, one difference](#two-files-one-difference)
- [Where things live](#where-things-live)
- [One platform repository, many course repositories](#one-platform-repository-many-course-repositories)
- [Settings](#settings)

---

## Start here

### Always-on, with Docker

One command, once. The services then come back on every boot, so there is nothing to start
by hand:

```bash
cp .env.example .env       # set CLAUDE_HOME and CODEX_HOME to your path ex: CLAUDE_HOME=~/.claude  and CODEX_HOME=~/.codex
docker compose up -d --build
```

| | |
|---|---|
| **http://127.0.0.1:8790** | **Course Studio** — write, edit and study courses |
| http://127.0.0.1:8787 | the bridge — the tutor for a page opened off disk |
| http://127.0.0.1:8888 | Jupyter — runs a course's notebooks inside the page |

`docker compose logs -f studio` watches a generation run; `docker compose down` stops them.

One image, three services. It mounts your `~/.claude` (and `~/.codex`, if you set
`CODEX_HOME`) so the containers use the command-line tool you are **already signed in to** —
no API key, no per-token bill. Every port is published to `127.0.0.1` only, so nothing
outside your machine can reach them.

### Or run it directly

Double-click **`start-studio.bat`**, or:

```bash
pip install markdown
python platform/build.py studio
```

Course Studio opens in your browser. Same app, no Docker.

### Or from the terminal

```bash
python platform/build.py list                                   # what you have
python platform/build.py where                                  # which courses/ and dist/ are in use
python platform/build.py new --theme "negotiation" --hours 20   # scaffold, no content
python platform/build.py check negotiation                      # validate — reports everything at once
python platform/build.py build negotiation                      # -> dist/negotiation/
python platform/build.py jupyter                                # notebook server, for courses that use one
```

---

## Studying a course

Open a course **from Studio** and everything below just works: the tutor answers through
Studio, progress is stored by the platform, and the course can grow while you read it.

### The learning cycle

Every module runs the same six steps:

**Predict → Read → Retrieve → Elaborate → Apply → Close the gaps**

| Step | What happens |
|---|---|
| **Predict** | You guess before you read. |
| **Read** | Sections with their own checkbox and timer; a section ticks itself once you have scrolled past all of it. The timer pauses when you stop touching the page, so a tab left open is not study. |
| **Retrieve** | The quiz. |
| **Elaborate** | You explain it in writing; the tutor grades it. |
| **Apply** | You use it on your own real case. |
| **Close the gaps** | Drill on exactly what you got wrong here — every missed question, every lapsing card, every exercise graded partial. An item closes only when your written answer is right *for the right reason*. |

### Practice that is honest

- **Eight question types** — single, multi, true/false, numeric, ordering, matching, cloze,
  and short written answers graded by the tutor. Per-option feedback, a hints ladder, and a
  **confidence rating** on every answer, so you see the gap between how sure you felt and how
  right you were.
- **Mistake queue** — a question you miss (or need a hint for) becomes a card due tomorrow,
  retired after four clean recalls.
- **Flashcards** on a spaced-repetition schedule, unlocked as you finish modules.
- **Checkpoints** — a mixed quiz across each finished part, and a course challenge across
  everything.
- **Mastery per module** — Not started → Read → Practised → Proficient → Mastered, shown as a
  coloured dot everywhere. A checkpoint miss can take it back down.

### The tutor

- A **side rail that follows you**: the conversation belongs to the place you are looking at
  — this module, this step, this section. Scroll to the next section and you see that
  section's chat. Pin a passage to keep it.
- **Suggested questions written for that specific passage**, with your own open gaps offered
  first.
- **The tutor as grader** — Elaborate and Apply answers, short quiz answers, filled
  worksheets and role-play transcripts all come back with a verdict and a
  Covered / Missing / Wrong / Ask-yourself reply.
- **Role-play** — the tutor plays the course's persona and stays in character until you press
  *Finish & get feedback*.
- **The learner memory** — one course's record of how *you* think: built from every miss,
  every verdict, every question you ask and every passage you mark unclear. It names your
  gaps, puts them in front of the tutor before it answers, offers them as questions, and
  lists them on a page of their own. Gaps that keep coming back are the best evidence that a
  module needs rewriting — Studio shows them for exactly that.

### Reading it your way

- **Figures** — SVG diagrams inlined in the Read step. Some are **build-ups**: step through
  them, or press Play.
- **Listening** — the Read step read aloud by your browser's own speech engine, block by
  block, with the spoken block highlighted and scrolled into view. A section heard to its end
  ticks itself. Voice and speed are yours, per device.
- **Notebooks** — a Jupyter notebook rendered inside the module, and *runnable* right there
  when Jupyter is up. See [below](#notebooks-and-jupyter).
- **Reading preferences** — size, width, serif, reduced motion, dark or light. A print
  stylesheet too.

### Keeping track

- **Study plan** — hours per week or a target date, a "today" list, a streak with freezes, a
  study-day heatmap, and browser notifications when served by Studio.
- **Highlight anything** to turn it into a note or an open question; the tutor's reply closes
  it.
- **Bookmarks, resume position, notes export** as markdown, and a course record page.
- **Fillable worksheets**, saved as you type, copied out as text or reviewed by the tutor.
- **Search everything** with `/` — inside the course, or across every course from Studio.
- **Backup / restore** to move progress between machines.

### Progress, kept properly

Everything lives in your browser's `localStorage`, so a course opened off disk needs nothing.
Served by Studio it is **also** kept in `state/progress/` and **merged**, not overwritten — two
tabs or two browsers never lose each other's chats or highlights. Device-only things (theme,
reading size, your API key) never leave the browser.

**Reader profiles** let more than one person study on the same machine: each gets its own
progress, its own streak and its own calendar.

---

## Writing a course

### With Studio (unattended)

1. **Describe it** — theme, hours, who is studying. *"negotiation, 20 hours, a complete
   beginner"*.
2. **Approve the curriculum** — the model proposes the parts, the module list and the time
   split. Edit titles and minutes, drop modules you do not want, then say go. **Nothing is
   written until you do**: twenty modules take a while, so this minute is worth it.
3. **Watch it write** — each module appears as it lands, with its section and word count, and
   the header says what the model is writing right now. Stop at any point; everything written
   so far stays on disk.
4. **Open it** — the course is validated and built. One button opens it.

Figures and notebooks are written module by module, right after its text — two switches on
every form that writes text.

**A run that dies can be resumed.** The approved curriculum is saved; *Resume the run* keeps
every module already on disk and writes only what is missing.

### Editing a course you already have

The course page (`#/course/<id>`) has a tab for each job:

| Tab | What you can do |
|---|---|
| **Modules** | Rewrite a module (fully, or **patch**: only your notes applied), reorder, move to another part, remove it, redraw its figures, rewrite its notebooks. Or have the model **review** it against the pedagogy checklist — verdict, gaps, errors, quiz issues and a rewrite brief, one click from becoming the rewrite. Mark a module **good** yourself and your verdict wins. |
| **Add a module** | A new module on a topic, designed to fit the existing curriculum. |
| **Questions** | The open questions you left while reading, and your knowledge gaps — each one a click away from becoming a new module or a rewrite brief. |
| **Files** | Edit any `.md`, `.json`, `.svg` or `.ipynb` in the course by hand; JSON and SVG are checked before they are written. |
| **Settings** | Title, tagline, audience, tutor persona, the notebooks runtime, part names, hours, blurbs, milestones. |

From inside a course you are reading, the module footer links straight to *Add a module* or
*Rewrite* — so a module that leaves you wanting more is one click from being fixed.

**Nothing is erased.** A removed module, a deleted course: both move to `state/trash/`.

**A course can come and go as a folder**: import a zip or clone a git URL onto the library
page, export any course as a zip.

**Studio says when a course is stale** — edit a file by hand and *Rebuild* becomes the one
button that matters.

### With the authoring skill (hand-guided)

Ask a coding agent, in this folder:

> Build me a 20-hour course on negotiation.

That runs the **`course-author`** skill in `common/skills/`, which writes the content file by
file and iterates with you — slower than Studio, but you stay in the loop on every module.
The same skill is available to Claude Code, Codex and Gemini through a stub each.

### What the build refuses

`build.py check` reports every problem in one pass, before anything is written: a module
without an assessment, a quiz item missing the shape its type demands, a flashcard with no
back, a `**Requires:**` line naming a module that does not exist, a figure that is not
well-formed SVG, a notebook in a course that has not turned notebooks on, and the most common
authoring failure of all — a suggestion list that does not have exactly one entry per section.

---

## Models and providers

**A provider is one way to reach models. A model names the provider that reaches it.**

| Provider | Kind |
|---|---|
| **Claude Code** | the signed-in command-line tool — no key, no per-token bill |
| **OpenAI Codex** | the same, for the other tool |
| **Anthropic API** | a key |
| **OpenAI API** | a key — and, being Chat Completions, also OpenRouter, Groq and Azure |
| **Google Gemini API** | a key |
| **Local** | the OpenAI adapter pointed at Ollama, LM Studio or vLLM on your own machine |

Everything above the provider layer — the generator, the reviewer, the tutor — asks for a
completion and knows nothing about who answered. Enabling a provider is a row in
`platform/settings.json` plus a key in `.env`.

- **The model list is editable without touching a committed file.** *Settings & logs* in
  Studio edits id, alias, label and note per row, reorders, adds and removes. A **Test**
  button asks that model once, so a typo is refused on the settings page and not at module 8
  of a run.
- **Nobody has to type a new model's id.** Studio asks every configured provider what it
  knows — an API's `/models`, or the tables inside the CLI binary — and merges the answers
  per provider. Daily, or **Check now**.
- **When a model says no, the reason decides what happens next.** An overloaded server is
  waited out and retried on the same model; a model it does not recognise moves down the
  chain; being out of quota ends the run at once and repeats the reset time back to you,
  instead of wasting a minute failing the same way on the next model. Every failure is a
  sentence saying what to do, with **Try again** where you are already looking.
- **Log first, then look.** Every call and every job step is logged with model, duration and
  sizes — read it on the Settings page or in `state/logs/studio.log`.

---

## Notebooks and Jupyter

For a course you learn by *running code* — a language, data analysis, statistics, a numerical
method — the course carries **Jupyter notebooks** next to the prose. Turn it on for a course
(the planner suggests it when the theme calls for it) and:

- The model writes notebooks alongside each module's text.
- The page renders every cell **read-only** — always, even off disk and even published.
- Served by Studio with the Jupyter service up, each notebook gains **Run it here** (live,
  in-place) and **Open in a tab**. The file you edit is the one the course carries.

The notebook server is a **separate service on purpose**: it runs code a model wrote, so it
gets the courses and nothing else — no OAuth directory in reach of a kernel.

---

## Two files, one difference

Each build produces two copies:

| File | Use it for |
|---|---|
| **`<course>-local.html`** | **Studying.** Open it straight from the folder. This is the copy whose tutor can answer. |
| `<course>.html` | Publishing. Everything works except the tutor — a hosted page is not allowed to call an API directly. |

Open the course **from Studio** and the tutor already works with nothing to set up. Opening
the local copy off disk works too: go to **Settings** in the sidebar and either paste an API
key (a typical question costs a fraction of a cent) or start the bridge to use a subscription
you already have — see `tools/bridge/README.md`. A key you paste stays in your browser.

---

## Where things live

```
platform/          the engine — subject-agnostic
  build.py         the CLI
  settings.json    every default the platform has
  coursekit/       the build package  (llm/ = every provider, one place)
  studio/          the local app: generate, edit and build from a browser
  web/             the course page's source: shell.html, css/, js/
courses/<id>/      one course, its own git repository (gitignored here — see below)
dist/<id>/         built output — generated, never edited
state/             yours, not the course's: progress/, reviews/, jobs/, trash/, logs/
tools/bridge/      local proxy, so a page opened off disk can reach a model
tools/jupyter/     the notebook server's configuration
docker/            the image all three services share
compose.yaml       Studio + bridge + Jupyter, restarting on every boot
common/            CONVENTIONS.md and the course-author skill, written once for every tool
start-studio.bat   double-click to open Course Studio without Docker
```

**Two layers, kept apart.** The engine never mentions a subject: everything
subject-specific reaches the page from `course.json`, and everything about *who makes the
model* comes from settings. A test fails the build if a subject word or a vendor name appears
in the front end.

A course is a folder with a `course.json` in it — markdown, JSON, SVG and notebooks, and no
code the platform runs.

---

## One platform repository, many course repositories

Courses are not part of this repository. Each is a git repository of its own, and the
platform only needs the directory that holds them:

```bash
python platform/build.py where          # prints the courses and dist directories in use
```

By default that is `courses/` inside this folder, which is gitignored — so clone a course into
it and it appears in Studio and in `build.py list`:

```bash
git clone https://github.com/<you>/<course>.git courses/<id>
```

To keep courses elsewhere, put `COURSES_DIR=<path>` in `.env` (relative paths count from this
folder; `../courses` is a sibling directory). Docker reads the same line.

A course Studio generates is an ordinary folder with a `README.md`; make it a repository the
usual way:

```bash
cd courses/<id>
git init && git add -A && git commit -m "Initial course"
git remote add origin https://github.com/<you>/<id>.git && git push -u origin HEAD
```

Progress, reviews, finished jobs and trash stay in `state/` on the platform side, keyed by
course id — so a course repository never carries anyone's reading history.

---

## Settings

**Every default the platform has lives in one file: `platform/settings.json`** — ports and
hosts, the providers and the model list, every timeout, the generation counts, and the page's
own study rules and layout sizes. Nothing in the code carries a literal of its own.

Later layers win:

| | |
|---|---|
| `platform/settings.json` | the committed defaults |
| `SETTINGS_FILE` | an optional JSON overlay — a different model list, longer timeouts |
| `state/settings.json` | what Studio's settings page saved |
| `.env` at the repo root | the named knobs: `STUDIO_PORT`, `BRIDGE_PORT`, `JUPYTER_TOKEN`, `STUDIO_MODEL`, `ANTHROPIC_API_KEY`, `COURSES_DIR`, … (see `.env.example`) |
| the environment | the same names, winning over `.env` |

`python platform/build.py where` prints what was resolved. Studio's settings page lists every
value **with the layer it came from**, so there is never a question of which file won.

Studio listens on `127.0.0.1` only, and that is a security boundary rather than a default: it
writes files and spawns processes. The same goes for the bridge and Jupyter.

---

### Requirements

Python 3 and the `markdown` package. That is the whole dependency list — `npm install` adds
prettier for the front end, and the test that uses it skips when it is absent.

```bash
python platform/tests/test_build.py      # engine, and the code conventions
python platform/tests/test_studio.py     # Studio
```

See **`common/CONVENTIONS.md`** for how the build works and the rules that keep the two
layers apart. `CLAUDE.md`, `AGENTS.md` and `GEMINI.md` all point at it.
