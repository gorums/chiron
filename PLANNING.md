# Planning — the course platform as a local learning product

## Vision

One `docker compose up`, one address (`http://127.0.0.1:8790`), and the whole loop happens
there: see every course and how far you are, continue where you left off, ask the tutor
while reading, and when a module leaves you wanting more, grow the course from inside it.
The experience should feel like Coursera or a good learning platform — a library, a course
page, progress that follows you — but everything is local, subject-agnostic, and made of
markdown you own.

## Principles that shape every decision

1. **The engine never mentions a subject.** Everything course-specific arrives through
   `course.json` → `CFG`. Checkable: `grep -rniE "marketing|marketer" platform/web/` is empty.
2. **A course is markdown and JSON, nothing else.** Studio, the skill and a text editor are
   three ways to produce the same files.
3. **Progress belongs to the reader, not the course or the build.** It lives outside
   `courses/` (content) and `dist/` (regenerated): `state/progress/<id>.json`.
4. **Module ids are never reused.** Progress is keyed by them.
5. **Model output is trusted for prose, distrusted for structure.** Every shape a model
   returns is coerced before the validator sees it.
6. **Loopback only.** Studio writes files and spawns processes. Compose publishes to
   `127.0.0.1`; the code defaults to it.
7. **Written to disk as produced.** A job that dies leaves real files behind.

## Architecture (current)

```
browser ── Studio UI (#/ library · #/course/<id> · #/job/<id>) ──┐
   │                                                             │  HTTP, same origin
   └── served course page (/course/<id>/<output>-local.html) ────┤
            localStorage (working copy)                          │
            syncPull / syncPush ──────────────► /api/courses/<id>/progress ─► state/progress/
            askBridge ────────────────────────► /api/ask ─► claude CLI (stdin, scratch cwd)
                                                                 │
                        platform/studio/server.py ◄──────────────┘
                              ├── generator.py   generate · extend · rewrite   (jobs, SSE)
                              ├── progress.py    reader state, summaries
                              ├── claude_cli.py  the only way Claude is called
                              └── coursekit      load · validate · render (no subject)
```

The bridge (`tools/bridge/`) remains for a course opened off disk (`file://`), where none of the
same-origin machinery exists.

## Phases

### Phase 1 — platform, not file viewer (done)

- Server-side progress store and sync from the served page; library cards with progress and
  Continue.
- Per-course page: modules with progress, Add a module, Rewrite, Files editor, Check/Build.
- `extend` and `rewrite` generation jobs; the course grows from its own module footer.
- Tutor through Studio on the same origin; bridge moved to stdin.
- Engine leak fixed (`30h`), Studio hash-routed, docs and tests.

### Phase 2 — manage a course end to end, without a terminal (this iteration)

The gaps that still send someone to a text editor or a shell, plus the pieces that make
"my learning" visible across courses:

- **Course settings as a form**, not raw JSON: title, tagline, audience, practitioner,
  tutor persona, milestones. `id` stays locked — it is the storage key.
- **Remove a module** cleanly: file, its assessment and suggestion entries, its short title.
- **Delete a course** reversibly: moved to `state/trash/`, never `rm -rf`.
- **Open questions in Studio.** The highlights the reader marked as questions are the most
  honest signal of what the course is missing. Show them on the course page and turn any of
  them into an Add-a-module brief with one click.
- **Extend from a section**, not just a module: the footer link carries the section heading.
- **Backup and restore from Studio**: download the progress file, paste one back — the
  migration path for progress made on a `file://` copy.
- **Durable job history.** Jobs currently die with the server; in Docker a restart erases
  the record of a run. Persist finished jobs to `state/jobs/` and replay them.
- **A "today" strip** on the library: cards due and modules in progress across every course.

### Phase 3 — later, if the product earns it

- Reorder modules and move one between parts (needs id-stable ordering metadata in
  `course.json`; the loader currently orders by filename).
- Cross-course search in Studio.
- Per-reader profiles (a `reader` dimension in `state/`) for a shared household machine.
- A study calendar / streak view built from the progress files.
- Course export as a zip; import of a course folder.
- An "ask Studio to check this" review pass: Claude reads a module and lists what it gets
  wrong or leaves out, before the reader does.

## What stays out of scope

- Multi-user auth, remote access, hosting. This is a personal, local tool by design.
- Replacing the single-file course build. Offline and `file://` must keep working.
- A JS build step or framework. One scope, numbered files, no dependencies.

## Verification standard

Every phase ends with: `test_build.py` and `test_studio.py` green, the HTTP smoke test
green, the bundle and `ui/js/*.js` passing `node --check`, the subject-leak grep empty, both
shipped courses rebuilt, and a manual pass through the UI in a browser served from Docker.
