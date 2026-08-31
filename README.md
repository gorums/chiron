# Course platform

Build an interactive course on any subject, for any number of hours, and study it in your
browser.

You pick a theme and a budget — "marketing, 30 hours"; "negotiation, 20 hours" — and the
authoring skill writes the whole thing: the curriculum, the modules, the glossary, the
worksheets, the quizzes and the flashcards. The build turns that into a single HTML file
that tracks your progress, schedules your revision, and lets you ask Claude about whatever
paragraph you are stuck on.

The marketing course in `courses/marketing/` was the original project and is now the
reference implementation.

---

## Make a course

Ask Claude, in this folder:

> Build me a 20-hour course on negotiation.

That runs the `course-author` skill, which scaffolds the folder, writes the content, and
builds it. Then open `dist/negotiation/negotiation-course-local.html`.

Or drive it yourself:

```bash
pip install markdown

python platform/build.py new --theme "negotiation" --hours 20   # scaffold
#   ... write the content, or have the skill write it ...
python platform/build.py check negotiation                      # validate
python platform/build.py build negotiation                      # -> dist/negotiation/
```

`python platform/build.py list` shows what you have.

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

To enable the tutor: open the local copy, go to **Settings** in the sidebar, paste an
Anthropic API key, press Connect. Typical question costs a fraction of a cent. If you would
rather use a Claude Code subscription than a key, see `bridge/README.md`.

---

## Layout

```
platform/          the engine — subject-agnostic
  build.py         the CLI
  coursekit/       the build package
  web/             front-end source: shell.html, css/, js/
courses/<id>/      one course: markdown, worksheets and study data
dist/<id>/         built output
bridge/            optional local proxy, so you can use Claude Code instead of an API key
```

A course is a folder with a `course.json` in it. Everything subject-specific lives there;
the engine holds no opinions about what you are learning.

See `CLAUDE.md` for how the build works and the rules that keep the two layers apart.
