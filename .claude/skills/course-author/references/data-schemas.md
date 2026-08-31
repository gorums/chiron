# Study data schemas

Two JSON families live in `courses/<id>/data/`. The build validates both and refuses to
produce output while either is inconsistent with the modules.

Split them by part (`part1.json`, `part2.json`, …) so a course stays editable. The build
merges every `.json` in each directory, so the filenames are yours to choose; the only rule
is that two files must not claim the same module.

---

## `data/assessments/partN.json`

A JSON **list**. One object per module.

```json
[
  {
    "id": "M01",

    "predict": "Before reading: if marketing is not the same thing as advertising, what else do you think it includes? Write one sentence with your best guess.",

    "quiz": [
      {
        "q": "According to the module's definition, which activity is LEAST likely to count as marketing work?",
        "options": [
          "Deciding what price to charge",
          "Deciding where the product can be bought",
          "Choosing which group the product is built for",
          "Negotiating the payment schedule with the packaging printer"
        ],
        "answer": 3,
        "why": "The definition covers understanding a group of people and then building, pricing, placing and describing something for them. Pricing is the tempting answer to exclude because it feels like a finance job, but the module says directly that what you charge is a marketing decision."
      }
    ],

    "cards": [
      { "front": "State the module's definition in one sentence.", "back": "The work of understanding a group of people well enough to build, price, place and describe something they will choose over the alternatives — profitably and repeatedly." }
    ],

    "elaborate": [
      "In two sentences, explain to a friend why buying customers at a loss is a subsidy rather than marketing, using a product you bought recently.",
      "Split your chosen business's current activity into demand capture and demand creation. In three sentences, say what the split is and what breaks first if capture saturates."
    ],

    "transfer": {
      "scenario": "A two-person company sells scheduling software to dental practices. All acquisition is search ads, converting at 4% at a stable cost. They have been flat at ~40 new customers a month for five months, and adding budget only raised cost per click. The founder wants to hire a copywriter to rewrite the ads.",
      "prompt": "Diagnose what is actually constraining growth and say what you would do instead of rewriting the ads.",
      "model": "The constraint is not ad quality, it is the size of the pool..."
    }
  }
]
```

### Field rules

| Field | Type | Rules |
|---|---|---|
| `id` | string | Must match a module's id exactly. |
| `predict` | string | One question asked *before* reading. It should be answerable by guessing — the point is committing to a guess, not being right. |
| `quiz` | list | 6 questions is the working default. |
| `quiz[].options` | list | 4 options. All plausible — a question with three obvious throwaways teaches nothing. |
| `quiz[].answer` | int | **Zero-based index into `options`.** The build rejects an out-of-range index. Vary the correct position; do not let it settle on one slot. |
| `quiz[].why` | string | **Required.** Explain why the right answer is right *and* why the most tempting wrong one is tempting. This is where the teaching happens. |
| `cards` | list | 6 flashcards. `front` is a question or prompt, `back` is the answer. Both required. |
| `elaborate` | list | 2 prompts that force the reader to explain in their own words, at least one applied to their chosen subject. |
| `transfer` | object | `scenario` (a concrete situation the module never discussed), `prompt` (what to produce), `model` (the answer, revealed after they commit). |

### Writing good quiz questions

Test whether the reader can *use* the idea, not whether they read the sentence. The weak
form is "Which of these is the definition of X?". The strong form gives a situation and asks
what follows from it. Distractors should be things a half-learner would actually believe.

---

## `data/suggestions/partN.json`

A JSON **object**, keyed by module id. Each value is a list of question-sets — **one set per
`##` section, in document order**.

```json
{
  "M01": [
    [
      "What does 'most marketing money is wasted' actually look like?",
      "Give me an example of spend wasted by treating marketing as ads",
      "How do I tell if my own business is making this mistake right now?"
    ],
    [
      "Why is 'do nothing' called the toughest competitor to beat?",
      "Apply that definition to a small local business for me",
      "How do I list the alternatives my buyers actually compare me against?"
    ]
  ]
}
```

These appear as one-tap prompts in the chat rail while the reader is on that section, so:

- **The count must equal the module's section count.** Matched by position. This is the
  single most common build failure. Count headings in the finished file; remember that a
  `##` heading with an empty body is dropped and does not count.
- 3 questions per set.
- Under ~70 characters each — they render as small buttons.
- Specific to that section's actual content. "Tell me more" is wasted.
- Mix the kinds: one *clarify*, one *make it concrete*, one *apply it to me*.

---

## Validating

```
python platform/build.py check <course-id>
```

Reports every problem in one pass: missing assessments, bad answer indexes, missing `why`,
incomplete cards, section/suggestion count mismatches, and orphaned entries that match no
module. Fix them all before building.
