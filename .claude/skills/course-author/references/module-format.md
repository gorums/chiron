# Module file format

The build parses these files. The parts marked **required** are a contract — get them wrong
and the module either fails to load or silently renders short.

## Skeleton

```markdown
# M07 — Websites and Conversion

**Time:** 90 minutes (40 read · 40 exercise · 10 recall)
**Requires:** M03, M05
**Part 2 of 7 · Digital core**

---

## Why this matters

...

---

## Core concepts

### A subheading

...

---

## If you remember one thing

...
```

## The rules

**Line 1 — required.** `# <ID> — <Title>`, separated by an em dash (—, not a hyphen). The id
is the first token: `M07`. Everything after the em dash is the full title. The id must be
unique across the whole course and must match the key used in the assessment and suggestion
files.

**`**Time:**` line — required, within the first 8 lines.** The first number in it becomes the
module's planned minutes, which drives the progress bar and the time budget on the stats
page. `**Time:** 90 minutes (40 read · 40 exercise · 10 recall)` reads as 90.

**`**Requires:**` line — optional, within the first 8 lines.** The 0–3 *earlier* modules this
one genuinely builds on — the ones a reader must have understood, not merely read before.
Every id named must exist in the course; the build rejects an unknown one. The page shows
them under the module title and warns when one of them is still weak; the map draws the
dependency. Nothing is ever locked. Leave the line out for a module that stands alone.

**`## ` headings define sections.** Each one becomes a scroll target, a completion checkbox,
a bookmarkable unit, a unit of chat context, and one row in the suggestions file. This is
the count that has to match. `###` headings are ordinary content inside a section.

**Content before the first `## `** is ignored by the renderer. Put the `**Time:**`,
`**Requires:**` and part lines there and nothing you need read.

**A `## ` section with no body is dropped** — including from the count. If you leave a
heading empty, the suggestion file will not line up.

**`---` on its own line is stripped.** Use them freely as visual separators between sections;
they do not survive into the page.

**A trailing `**Next:** …` line is stripped.** Navigation belongs to the app. Do not write
cross-module links expecting them to work: relative markdown links are turned into plain
italic text, because a one-file site cannot resolve them.

## Markdown that renders

Tables, fenced code blocks, blockquotes, nested lists, and `{: .class}` attribute lists are
all available. Blockquotes are the right tool for a definition worth memorising:

```markdown
> Marketing is the work of understanding a group of people well enough to build, price,
> place, and describe something they will choose over the alternatives.
```

## Figures

A course cannot carry photographs, but it can carry **diagrams as SVG**. Where a picture
shows something the prose can only list - a flow, a funnel, a 2x2, a timeline, a
before/after, the parts of a thing and how they connect - write the SVG to
`figures/<ID>-<n>.svg` and refer to it from the section on a paragraph of its own:

```markdown
![The three stages, and where most of the loss happens](figures/M03-1.svg)
```

The build inlines the file into the page inside a `<figure>` with the alt text as its
caption, sanitises it, and refuses to build when it is missing, malformed, has no
`viewBox`, or is over the size limit. Any other image reference is refused: a one-file
site has nothing to load it from.

Rules for the SVG, which the build enforces or the page depends on:

- Start with `<svg viewBox='0 0 800 450'>` (up to 800x600 for a tall one). No `width`
  or `height`, no XML declaration, no `xmlns` needed.
- **Colour only through the page's classes**, so the figure reads in the light and the
  dark theme: `fig-1` `fig-2` `fig-3` `fig-4` (four strong fills, in that order of
  importance), `fig-soft` (a quiet fill for boxes and bands), `fig-line` (a stroke for
  connectors and frames; sets fill to none), `fig-muted` (secondary text). Text and
  arrows use `fill='currentColor'` / `stroke='currentColor'`. No hex colours, no
  `<style>` - an inline `<style>` would restyle the whole page and is stripped.
- `<text>` only, font-size 15-24, at most 40 words in the whole figure. A figure that a
  paragraph says just as well is not a figure.
- Nothing that runs or loads: no `<script>`, `<image>`, `<foreignObject>`, links or
  external references. They are stripped anyway.
- A `<title>` as the first child, for screen readers.
- Under 8 KB.

**A build-up** is the moving picture a course can carry. Wrap each stage in
`<g data-step='1'>`, `<g data-step='2'>`, ... (up to five) in the order they should
appear; the page hides them and gives the reader Back, Next and Play. Everything outside
a step group is always visible: put the frame and the axes there, the moving parts in the
steps. Use steps only where the order itself teaches something.

One or two figures per module is plenty. Zero is right for a module with nothing to draw.

## Section-by-section intent

| Section | What belongs in it |
|---|---|
| Why this matters | The 30-second case. Name the specific mistake this module prevents. |
| Core concepts | The teaching. `###` per idea. Definitions, the arithmetic, worked examples. |
| How it works in practice | The Tuesday-afternoon version. Tools, sequence, what it looks like on a real screen. |
| \<Year\> reality check | What changed recently that older guides get wrong. Date the claim. |
| Common mistakes | 3–6 traps. For each: what it looks like, why it is tempting, what to do instead. |
| Exercise | Applied to the reader's one chosen subject. Concrete deliverable, bounded time. Name the worksheet in `templates/` it fills. |
| If you remember one thing | One paragraph. The sentence that survives if everything else fades. |

## Length

A 60-minute module runs roughly 1,200–2,000 words. Under 800 and there is not enough to
spend an hour on; over 3,000 and it should have been two modules.

## Worksheets (`templates/*.md`)

A worksheet is filled in *on the page*: the reader's answers are saved with their progress,
can be copied out as text, and can be handed to Claude for review. The build turns the
blanks an author writes naturally into inputs:

| You write | The reader gets |
|---|---|
| a run of four or more underscores, `______` | a text field |
| an empty table cell, `\| \|` | a text field in that cell |
| a checklist item, `- [ ] …` | a checkbox |
| a fenced block tagged `answer` | a multi-line text area (the block's content is discarded) |

Fenced code blocks without the `answer` tag are left alone, so a filled-in example inside a
fence stays an example. A `**Use with:** M14 — …` line near the top links the worksheet to
those modules: their Apply step offers it, and Claude's review reads those modules for
context. Field numbering follows document order, so inserting a blank in the middle
renumbers the ones after it and orphans what readers typed there — add blanks at the end
of a worksheet people are already using.
