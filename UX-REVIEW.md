# UX / UI review — one product, not two (2026-09-09)

A code pass over the reader (`platform/web/`, 3 105 lines CSS + 6 986 JS) and Studio
(`platform/studio/ui/`, 1 491 CSS + 2 576 JS), against the goal: **the whole platform feels
like one product, every screen explains itself, navigation is obvious, and the reader is
respected.** The tasks that come out of it are Phase 5 in `TASKS.md`. Line numbers are
file-local at the time of the review.

## The verdict in five lines

1. **Palette, fonts and radii are already identical** in both surfaces (`studio.css:5-77` is a
   copy of `01-base.css:1-94`). The "two websites" feeling is not colour; it is *components*:
   the same class names mean different things, and two toasts, two icon sets, two focus
   rings, two theme keys.
2. **`.btn` is inverted.** Studio `.btn` = filled accent; the page `.btn` = outlined, `.btn.primary`
   = filled. Same name, opposite weight. This is the single biggest tell.
3. **Explanation is prose-heavy and label-light.** Studio explains in paragraphs above lists
   (three explanatory cards above every module list) while fields use placeholders as
   labels; the page prints jargon (mastery, freezes, mistake queue, Compact, verdict) with
   a definition living on one other screen. The step descriptions in `STEPS[i].d` exist and
   are never shown.
4. **Feedback is a black pill for everything.** Success and a 500 look the same, for 2.1 s /
   2.6 s, with no live region; grader errors vanish while the reply box stays empty;
   results of Move/Remove/Save land at the top of the page.
5. **A handful of real bugs** hide behind the polish gap: a duplicate `id="readbar"`, an icon
   name that does not exist, palette results that land nowhere, sections that never tick on
   scroll (the doc says they do), a scrim that is styled but never rendered, `.card.tight`
   and `.disabled` used but undefined in Studio, the approval-gate "waiting for you" line
   that only renders on the *running* head.

## Design principles for the fix

- **One vocabulary.** One `.btn` family, one `.tag`, one `.pill`, one `.toast`, one icon set,
  one `.menu`, one form block, one focus ring - defined once, served to both.
- **Explain at the point of use.** Every control that carries a concept has a `title` (or
  an inline hint) that says what it does in one sentence; jargon gets a `help(term)`
  tooltip from one glossary object. Long prose goes behind `<details>` or a first-visit card.
- **One primary per region.** The next thing to do is the only filled button in view.
- **Every action answers.** Busy while it runs, a result where the eye is, an error that
  stays until read, a confirm before anything the reader cannot undo.
- **The URL says where you are.** Step names not indexes, nav that highlights on every
  route, crumbs that always reach the parent.
- **Keyboard and screen reader first-class.** Landmarks, roles, states, focus traps in
  dialogs, 24 px targets, AA contrast in both themes.

---

## A. Consistency across Studio and the reader

### Tokens (`studio.css:5-77` vs `01-base.css:1-94`)

| Token | Studio | Reader |
|---|---|---|
| palette light + dark | identical | identical |
| `--shadow-lg`, `--fig-*` | missing | present |
| spacing / type / radius scale | none (410 px literals, 15 font sizes) | none (24 font sizes, 23 radii, 72 paddings) |
| focus ring | 2px outline, no radius (`:111`) | + `border-radius:6px` (`:124`) |
| theme key | `localStorage.studio_theme` (`00-core.js:309`) | `STATE.theme` per course |
| `--muted` on `--bg` | ≈ 4.0:1 at 12-13px | same |

→ A dark Studio can open a light course page. `--muted` fails AA at the sizes it is used.

### Components with the same name and a different meaning

| Class | Studio | Reader | Do |
|---|---|---|---|
| `.btn` | filled accent, 600/14px (`studio.css:181`) | outlined, 500/13.5px (`01-base.css:360`); `.primary` filled; `.ghost` borderless | adopt the reader's: `.btn` outlined, `.primary`, `.ghost`, `.sm`, `.danger`, `.warm`, `.iconbtn` |
| `.pill` | neutral status chip, `.on/.off/.live` (`:240`) | 10.5px bold warm count badge (`01-base.css:268`) | reader's becomes `.badge`; share Studio's `.pill` |
| `.tag` | plain 11px (`:259`); verdicts are `.verdict.solid/.needs/.rewrite/.stale` (`:1151`) | `.tag.ok/.warn/.acc` (`02-content.css:84`) | one `.tag` with `ok/warn/bad/acc/stale` |
| `.sub` | 16px, margin 22 (`:165`) - overridden inline ~30 times | muted 13.5px, margin 0 | reader's `.sub`; add `.lede` for the one intro paragraph |
| `.toast` | `.show`, 2 600 ms (`00-core.js:96`) | `.on`, 2 100 ms, `--shadow-lg` (`02-helpers.js:344`) | one rule, one helper, `kind` + `sticky`, `role=status` |
| `.card.tight` | **undefined** (used `25-figures.js:22`, `27-notebooks.js:28`, `28-model.js:71`) | defined | share |
| `.disabled` | **undefined**; `busy()` adds it to `<a>` buttons (`00-core.js:101`) → links stay clickable while "locked" | - | define in shared base |
| icons | Unicode ◐ ⋯ ▲ ▼ × › | inline SVG `ico()` (`02-helpers.js:361`) | shared `icons.js` |
| inputs | radius 9, 3px soft ring, styles number/select (`:278`) | radius 10, inset outline, text/textarea only (`01-base.css:462`) | Studio's block (superset), one focus treatment |
| headings | `h2.big` 30, `h3` 19, card h3 21, part h3 17 | 27 and per-component | two display sizes |
| helpers | `$`, `esc`, `toast`, `ago`, `fmtH`, `clock` (`00-core.js:64-136`) | same names in `02-helpers.js` | one `00-dom.js` served to both |

### Proposal: one source, two consumers

`bundler` already concatenates `web/css/*.css` into the page. Studio's `index.html` can
`<link>` the same files at `/ui/...`; nothing about "the page is one inlined file" prevents
sharing the *source*.

- `web/css/00-tokens.css` - palette (both themes), shadows, fig colours, fonts, **new**
  `--s1..--s6` (4/8/12/16/24/32), `--fs-xs/sm/md/base` (11.5/12.5/13.5/16), `--radius-xs` 6,
  `--on-accent`, `--overlay`, `--muted` darkened to pass AA.
- `web/css/01-base.css` - the primitives both use: reset, `:focus-visible`, `.btn` family,
  form block, `.card(.tight/.raised)`, `.eyebrow`, `.sub`, `.lede`, `.tag`, `.pill`, `.badge`,
  `.bar-track/-fill`, `.note`, `.problems`, `.toast`, `.chip`, `.menu[role=menu]`, `.empty`,
  `.spin/.pulse` + reduced-motion, `.ic`, `.topbar` recipe, `kbd`, `.mono`, `.hidden`, `.disabled`.
- `web/js/00-dom.js` - `$`, `$$`, `esc`, `toast(msg, {kind, sticky})`, `ico`, `ago`, `fmtH`,
  `clock`, `help(term)`; served by Studio at `/ui/shared/` and inlined into the page.
- `studio.css` keeps only Studio layout (`.cards`, `.coursecard`, `.hero`, `.tabs`, `.modrow`,
  `.inlineform`, `.reviewbox`, `.editor`, `.steps`, `.modelrow`, `.logbox`, `.calendar`, gate).
  Expected: 1 491 → ≈ 800 lines; 143 inline `style=` → a few dozen.
- One theme key `platform_theme` read by both; the page falls back to `S.theme` off disk.
- **Guards** in `TestCodeConventions`: no hex outside `00-tokens.css`; no `font-size: Npx`
  outside the scale; every class used in `ui/js` and `web/js` exists in the served CSS
  (would have caught `.tight` and `.disabled`); no `.btn` variant outside the list.

---

## B. Reader (`platform/web/`)

### Bugs (P0)

| # | Where | What |
|---|---|---|
| R1 | `shell.html:9`, `07-module.js:145,414`, `20-keys.js:101` | duplicate `id="readbar"`; module reading bar never updates, audio tick writes the scroll bar |
| R2 | `17-rail.js:365`, `02-helpers.js:361` | `ico("spark")` - no such icon; blank 12px SVG beside every model picker |
| R3 | `13-palette.js:56-69,124-130` | section / glossary / model results route to the module top, not the item |
| R4 | `07-module.js:319-335,148` | sections tick only by click or audio; CLAUDE.md says scrolling ticks them; a reader who reads everything stays "Not started" |
| R5 | `03-chat.css:972`, `21-boot.js:36` | `.scrim` styled, never rendered; on ≤860px the sidebar cannot be closed by tap |
| R6 | `17-rail.js:294,304`, `13-palette.js:179` | Enter sends; hint and help say Ctrl+↵; readers lose newlines |
| R7 | `17-rail.js:560-566` | sending while disconnected navigates to Settings and drops the draft |
| R8 | `11-library.js:7-23,79`, `10b-plan.js:226`, `09-review.js:73`, `16-selection.js:86` | `div onclick` cards / chips / flashcard / marks - not keyboard reachable |
| R9 | `02-content.css:403,411,419`, `03-chat.css:12,165`, `04-practice.css:71,76` | `#fff` on accent/ok/warm in dark theme ≈ 2:1; only `.btn.primary` and `.step.on` were fixed |

### Navigation

- `#/m/M03/2` is "Step 3 · Retrieve" (`07-module.js:69`): unreadable, off by one → accept
  step keys (`#/m/M03/quiz`), keep numbers for old links (`04-router.js:8`).
- Prev/next show ids only ("← M02") (`07-module.js:74,76`) → id · short title + `title`.
- Two primary "complete" CTAs per step, one on Predict before anything is read
  (`07-module.js:75`, `07b-gaps.js:38`) → non-primary until `stepDone`, one wording.
- Onboarding is one line ("Start with Module 01.", `06-home.js:19`); `?` is shortcuts only
  (`13-palette.js:164`) → dismissable "How this course works" card (`S.ui.introSeen`) and a
  "How it works" section in the help modal.
- Dead ends: review "Session complete" → Dashboard only (`09-review.js:60`); `#/plan/*` and
  `/resources` have no heading (`11-library.js:32,98`); worksheet page has no way back to the
  Apply step; unknown module id silently goes home (`07-module.js:48`).
- `j/k` off a module jumps to M01 (`20-keys.js:96`); "All conversations" opens Marks on
  "all" not "chats" (`17-rail.js:440`).
- Sidebar nav is `<button>`s in an `<aside>`: no `aria-current`, no links, no landmark
  (`05-sidebar.js:16-31`) → `<nav aria-label="Course">` with `<a href>` + `aria-current`.

### Explanation and help

Counts: `title=` 43, `aria-label` 17, `role=` 0, `aria-pressed/expanded/current/live` 0,
inputs with no label 19.

- Jargon with a definition on another screen: mastery levels (sidebar legend `05-sidebar.js:25`,
  defined in `10-stats.js:40`), "❄ 2 freezes" (`10b-plan.js:103` / `10-stats.js:71`),
  "mistake queue" (`08-quiz.js:69,239` / `09-review.js:18`), "Compact" (`17-rail.js:295,439`),
  "calibration". → one `HELP` glossary object in `02-helpers.js`, `help(term)` returns the
  `title`; used everywhere the term is printed.
- Step pills never show `STEPS[i].d` (`07-module.js:69`) → `title`. Retrieve step is the
  only one without a "Why" hint (`08-quiz.js:50`).
- Icon / status controls without name or state: section tick (`07-module.js:154`, no
  `aria-pressed`), bookmark (`:157`, label never changes), reorder ↑↓ (`08-quiz.js:155`),
  `.dotstat` and `.dot` (`05-sidebar.js:16,32,38`, `17-rail.js:332`, `19-settings.js:11`),
  `#menubtn` (no `aria-expanded`), `#themebtn` (no current value), `.convobtn`
  (`17-rail.js:333`, no `aria-haspopup`).

### Feedback

- Grader/gap errors are 2.1 s toasts while the reply box stays empty; on failure buttons
  relabel to "Check again" as if it succeeded (`17b-grader.js:98-104,151-157,255-261`,
  `07b-gaps.js:126-132`) → inline error + Retry, original label kept.
- Toast: fixed duration, no `role=status`, no max-width, not dismissable (`02-helpers.js:344`).
- No boot state: blank until `profileInit` + `syncPull` (`21-boot.js:53-61`) → skeleton.
- `finishRoleplay` double-submit (`17b-grader.js:195`); `refreshLearner` re-renders home
  mid-interaction (`17c-learner.js:526`).
- Not confirmed: `restore()` (`12-backup.js:32`), `abandonCheck()` (`09b-checkpoint.js:115`),
  `retake()` (`08-quiz.js:435`), "Uncheck all" (`07-module.js:146`), `disconnect()`
  (`19-settings.js:227`). Danger confirm auto-focuses the danger button so Enter erases
  (`13-palette.js:19-22`).
- Settings `#setmodel` lacks `data-model-pick`, never syncs (`19-settings.js:66`).

### Consistency inside the reader

- Up to 6 primaries on Home, 3 on Apply (`06-home.js:30-55`, `07-module.js:208,234,247`).
- 10+ button visual families (`.figsteps button`, `.gradebar button`, `.selbar button`,
  `.trow`, `.cmain`, `.msgctx`, `.tag` as button); danger via inline `color:var(--bad)`
  (`12-backup.js:10`, `18-notes.js:16,112`, `13-palette.js:18`).
- Serif heading repeated inline 10× → `.h-serif`; big-score block duplicated
  (`08-quiz.js:398` = `09b-checkpoint.js:158`); three empty-state shapes.
- Card titles are `<p class="eyebrow">`, not headings → `<h3 class="eyebrow">`.
- 387 inline `style=` in JS (19-settings 58, 07-module 35, 08-quiz 32, 10-stats 28).

### Accessibility

- No landmarks; modals and palette lack `role=dialog`, focus trap, focus return
  (`13-palette.js:2-8`); chat menu has no keyboard nav and Esc does not close it
  (`20-keys.js:5-10`); single-letter shortcuts fire with a modal open (`20-keys.js:22-42`).
- Contrast: `.parthead .ph` in `--line-2` ≈ 1.9:1 (`01-base.css:291`); `.sec.done .prose`
  opacity .62 (`02-content.css:233`); the dark `#fff` rules above.
- Tables `display:block` strip semantics (`02-content.css:307`); JS smooth scroll ignores
  reduced motion (`07-module.js:401`); rail grip mouse-only (`17-rail-layout.js:109`);
  touch targets 22-24px in the rail dock.

### Layout

- `.g2/.g3/.g4` collapse on viewport ≤860 only (`03-chat.css:955`); with the rail open on a
  1 200px screen `#main` is ~500px and stat tiles wrap → container queries like `.readgrid`.
- Rail on narrow: full-height overlay, no scrim, no scroll lock (`03-chat.css:562`).
- `.parask` overlaps the first line ≤1080 (`03-chat.css:281`).

### Wording

- Tutor / Claude / "Ask Claude" / "Chat panel" / "chat rail" for one thing (85× "Claude",
  66× "tutor"). Rule: *tutor* = the role in the page; *Claude* only in connection copy.
- Retrieve (step) / Review (nav) / Retrieval practice (card) / Fix mistakes / mistake queue.
- "Your gaps" / "What the tutor knows about you" / "Build my profile" / "Update your profile".
- Settings page is titled "Connect Claude" and shows key/bridge prose when served by
  Studio (`19-settings.js:7,22-33,45-61`).
- Subject-flavoured copy in the engine: "cost you money" (`08-quiz.js:402`), "in front of a
  client" (`09b-checkpoint.js:160`).

---

## C. Studio (`platform/studio/ui/`)

### Bugs (P0)

| # | Where | What |
|---|---|---|
| S1 | `studio.css:813` | ≤720px `.topnav {display:none}` with no menu; New course and Settings unreachable |
| S2 | `40-job.js:232,273-276,350`, `:698` | "Waiting for you" renders only in the running head; the waiting head has no `#jobnow`; tab title stays "Designing the curriculum"; no notification; header pill not refreshed on `await` |
| S3 | `00-core.js:96`, `index.html:33` | one black toast for "Built" and "Request failed (500)", 2.6 s, no live region |
| S4 | `studio.css:181` vs `01-base.css:360` | `.btn` semantics inverted (see A) |
| S5 | `00-core.js:101`, `25-figures.js:22` | `.disabled` and `.card.tight` undefined |
| S6 | `20-course.js:397-427,465` | Settings-tab grids set `grid-template-columns` inline; the ≤720 collapse never applies |
| S7 | `00-core.js:289`, `30-settings.js:38` | remove profile: one click, no confirm, trashes a reader's progress |

### Navigation

- Nav highlights only Library / New / Settings (`00-core.js:351-360`); on course, job, edit
  and search nothing is active.
- No jobs list: the pill shows the first live job (`00-core.js:198-212`), finished ones
  vanish; a failed run is reachable only through browser history → `#/jobs` + "Last run:
  failed 3 min ago" on the hero.
- Boot with a live job teleports `#/` to `#/job/<id>` (`00-core.js:381`) → banner instead.
- Running job screen has no link to its course (`40-job.js:619,674`).
- Export hidden during a job (`20-course.js:51-58`); Check/Build should disable with a reason.
- Error states have no crumb, Back or Retry (`20-course.js:15`, `00-core.js:392`).
- "Manage profiles…" is a `<select>` option that navigates (`00-core.js:247`).
- Claude pill is static text; when "not found" it links nowhere (`index.html:27`);
  "+ Write a course" is an `<a>` with `pointer-events:none` (`10-library.js:100`).
- Zero-course library still shows the "Your courses" heading and repository prose
  (`10-library.js:115`) → first-run hero.
- Editor crumb shows the raw id and duplicates a Back button (`30-settings.js:165,171`).
- Every gate to Claude is a silent `disabled` (`20-course.js:641`, `:144`) → `claudeGate()`
  that renders the reason once per screen.

### Explanation and help

Counts: `title=` 26, `aria-label` 25, `.hint` 11, `.sub` paragraphs ≈ 30.

- Fields: Hours has no hint (its one sentence sits at the form's foot, `10-library.js:337`);
  Practitioner (`:311`, `20-course.js:413`), Notebooks yes/no (`:325`), Tutor persona
  ("system prompt fragment", `20-course.js:415`), milestones ("honest-read line", `:433`).
- Anchor ×4, parts ×3, milestones ×2 rows use placeholders as labels (`20-course.js:397,
  422-430, 465`) → column headers per row group.
- Verdict pill prints raw `solid` / `needs work` / `rewrite` / `· before edit`
  (`20-course.js:129-134`); the scale is never explained → `title` + a legend.
- "Clear view" clears the server ring (`30-settings.js:82`); platform settings table has
  raw keys and no description column (`:62`); "the platform's list" (`31-models.js:265`).
- Gate: no total minutes vs requested hours; drop is silent-permanent (`40-job.js:799-827`).
- Modules tab: three prose cards (~120 words) above the list on every visit
  (`28-model.js:71`, `25-figures.js:22`, `27-notebooks.js:28`) → one toolbar row.

### Feedback

- Save settings repaints the whole page; "Then Rebuild" hint has no button beside Save
  (`20-course.js:508,438`) → Save / Save and rebuild.
- Move / remove results land in `#courseout` at the top (`:229-237,318-323`).
- No "changed since build" state anywhere (`:64`) → `dirty` from the server, Rebuild primary.
- Resume form and Check/Build share `#courseout` (`:709,733,748`); Check wipes the form.
- `busy()` skipped for git clone (`10-library.js:195`), review / figures / notebooks /
  rewrite / resume (nothing before the hash changes), Test / Check now (`31-models.js:349,313`).
- Stop: no confirm, stays enabled (`40-job.js:868`); card Build has no lock → double build
  (`10-library.js:269`).
- Review done: "The full list is on the course page" but the box is `hidden` until the pill
  is clicked (`40-job.js:755`, `20-course.js:204`) → `&review=<mid>` opens it.
- Model Test error lives in a `title` (`31-models.js:357`); Delete fires two toasts into one
  slot (`20-course.js:576`).
- Validator problems are raw strings; paths could link to the editor.

### Accessibility

- Tabs without `role=tablist` / arrow keys (`20-course.js:80`); row menu with `<select>`
  children, no ↑/↓, no focus return (`:270-295`); ▲▼ ≈ 15×12px (`studio.css:1127`).
- One heading per page; sections are `p.eyebrow` (`20-course.js:335-457`, `30-settings.js:27-74`).
- `#toast`, `#claudestate`, `#jobstate`, log box: no live regions.
- Editor Tab-capture is a trap with no announced exit (`30-settings.js:183`).
- New-course form is not a `<form>`; Enter in Theme does nothing (`10-library.js:300`).
- Activity log force-scrolls on every event even when the user scrolled up (`40-job.js:681`).

### Layout

- Header has no `flex-wrap`; between ~760 and 1 000px it clips (`studio.css:117`); search
  hidden ≤900 with no alternative (`:1036`).
- `.modrow` ≤720 declares 3 columns for 4 children (`:809`); `.menu` can overflow left on 360px.
- `.figbar` no wrap (`:1479`); editor `white-space:pre` with no wrap toggle (`:784`).

### Wording

- Curriculum / plan / design: "Plan the course" → "Designing the curriculum…" → "Curriculum
  proposed" → "the saved curriculum" → `plan.json`. Rule: *curriculum* = the whole outline,
  *design* = one module's spec; never "plan" in the UI.
- New course / Write a course / Plan the course / Writing <theme> - four labels, one flow.
- `jobLabel` falls back to raw `kind` ("figures", "review") (`00-core.js:176`).
- Rebuild / Build / rendering / "publish" - "publish" implies hosting.
- Stop / Cancel / cancelled / Stopped (`40-job.js:594,649`).
- "Mark as good" / "This is good" / "good ✓" / "Withdraw "good"" (`20-course.js:133,145,217`).
- Patch or rewrite… / Apply to M03 / Rewrite / Rewrite M03 with this - four labels.
- Claude Code / Claude / model / tutor mixed in one sentence (`30-settings.js:28`). Rule:
  *Claude Code* = the installed CLI (status only), *Claude* = who writes and reviews in
  Studio, *tutor* = who answers in the page, *model* = the picker.
- "broken" for a course with a check error (`10-library.js:17`) → "needs fixing".

---

## D. Vocabulary (the one list both surfaces use)

| Say | Never | Meaning |
|---|---|---|
| course | - | one folder, one repository |
| curriculum | plan | the whole outline Studio proposes and you approve |
| module design | spec, plan | one module's outline before it is written |
| module, section, step | lesson, chapter | as in the page |
| Predict · Read · Retrieve · Elaborate · Apply · Close the gaps | Review (for the step) | the six steps, same everywhere |
| Practice (deck) | Review, Retrieval practice | `#/review` nav item and card |
| Fix mistakes | mistake queue | `#/review/mistakes` |
| mastery: Not started · Read · Practised · Proficient · Mastered | - | with one tooltip each |
| tutor | Claude, assistant, chat panel | who answers in the page |
| Claude | model | who writes and reviews in Studio |
| Claude Code | - | the installed CLI; status pill only |
| model | - | the picker |
| Rebuild | publish, render | write `dist/` again |
| Stop (a job) / Cancel (a form) | - | |
| Mark as good / Unmark | This is good, Withdraw | owner's verdict |
| Patch or rewrite… | Apply, Rewrite with this | the one action |
| Your gaps | profile, learner memory | `#/learner` |
| needs fixing | broken | a course whose check fails |
