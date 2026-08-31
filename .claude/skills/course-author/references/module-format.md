# Module file format

The build parses these files. The parts marked **required** are a contract — get them wrong
and the module either fails to load or silently renders short.

## Skeleton

```markdown
# M07 — Websites and Conversion

**Time:** 90 minutes (40 read · 40 exercise · 10 recall)
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

**`## ` headings define sections.** Each one becomes a scroll target, a completion checkbox,
a unit of chat context, and one row in the suggestions file. This is the count that has to
match. `###` headings are ordinary content inside a section.

**Content before the first `## `** is ignored by the renderer. Put the `**Time:**` and part
lines there and nothing you need read.

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

## Section-by-section intent

| Section | What belongs in it |
|---|---|
| Why this matters | The 30-second case. Name the specific mistake this module prevents. |
| Core concepts | The teaching. `###` per idea. Definitions, the arithmetic, worked examples. |
| How it works in practice | The Tuesday-afternoon version. Tools, sequence, what it looks like on a real screen. |
| \<Year\> reality check | What changed recently that older guides get wrong. Date the claim. |
| Common mistakes | 3–6 traps. For each: what it looks like, why it is tempting, what to do instead. |
| Exercise | Applied to the reader's one chosen subject. Concrete deliverable, bounded time. |
| If you remember one thing | One paragraph. The sentence that survives if everything else fades. |

## Length

A 60-minute module runs roughly 1,200–2,000 words. Under 800 and there is not enough to
spend an hour on; over 3,000 and it should have been two modules.
