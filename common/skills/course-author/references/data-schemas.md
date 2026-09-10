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
        "feedback": [
          "Pricing feels like finance, but the module says what you charge is a marketing decision.",
          "Where it can be bought is 'place' — squarely marketing.",
          "Choosing the group is the first marketing decision of all.",
          "Right: a supplier negotiation is procurement, not marketing."
        ],
        "hints": ["Ask which of the four is not about the customer."],
        "why": "The definition covers understanding a group of people and then building, pricing, placing and describing something for them. Pricing is the tempting answer to exclude because it feels like a finance job, but the module says directly that what you charge is a marketing decision."
      },
      { "type": "numeric", "q": "Ads cost €2,000 and won 25 customers. What is the CAC?", "answer": 80, "tolerance": 0, "unit": "€", "why": "2,000 / 25." },
      { "type": "cloze", "q": "If CAC is €120 and LTV is €360, the LTV:CAC ratio is ___.", "answer": ["3", "3:1", "3 to 1"], "why": "360 / 120." }
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
    },

    "roleplay": {
      "persona": "You are the founder of that dental-scheduling company. You are certain the ads are the problem and you have already found a copywriter. You get defensive when told the market is small, and you only come round when shown the arithmetic.",
      "situation": "The founder has ten minutes before their next call and wants your sign-off on the copywriter.",
      "goal": "Get the founder to agree to test a second channel before spending on copy — without them feeling stupid.",
      "rubric": [
        "Named the real constraint (pool size) rather than agreeing about the ads",
        "Used a number from the scenario to make the case",
        "Proposed one concrete next step the founder accepted",
        "Kept the founder on side"
      ]
    }
  }
]
```

### Field rules

| Field | Type | Rules |
|---|---|---|
| `id` | string | Must match a module's id exactly. |
| `predict` | string | One question asked *before* reading. It should be answerable by guessing — the point is committing to a guess, not being right. |
| `quiz` | list | 6 questions is the working default. Mix at least three types across them. |
| `quiz[].type` | string | One of the types below. Omit it for `single`. |
| `quiz[].why` | string | **Required on every type.** Explain why the right answer is right *and* why the most tempting wrong one is tempting. This is where the teaching happens. |
| `quiz[].hints` | list | Optional, any type. 1–2 nudges that narrow the answer without giving it away. The page reveals them one at a time; a question answered after a hint goes into the mistake queue. |
| `quiz[].feedback` | list | Optional, `single` / `multi` / `tf` only. One line **per option** saying why that option is right or wrong. The reader who picked the tempting distractor gets a different sentence from the one who guessed. |
| `cards` | list | 6 flashcards. `front` is a question or prompt, `back` is the answer. Both required. |
| `elaborate` | list | 2 prompts that force the reader to explain in their own words, at least one applied to their chosen subject. The page can have Claude check the answer. |
| `transfer` | object | `scenario` (a concrete situation the module never discussed), `prompt` (what to produce), `model` (the answer, revealed after they commit). Claude can grade the reader's draft against `model` before it is revealed. |
| `roleplay` | object | **Optional.** A live conversation the tutor plays in the page. `persona` is an instruction to the tutor ("You are…") with a stated wrong belief or pressure; `situation` is what the reader sees; `goal` is what they must achieve; `rubric` is 3–4 things a good performance shows. Omit only when the module has no conversation worth practising. |

### Question types

| `type` | Fields | What the reader does |
|---|---|---|
| `single` (default) | `options` (4, all plausible), `answer` — **zero-based index**. Vary the position. | Picks one. |
| `multi` | `options`, `answer` — list of correct indexes. | Picks every option that applies, then locks in. |
| `tf` | `answer` — `true` or `false`. `feedback` has two entries. | Picks true or false. `q` is the statement. |
| `numeric` | `answer` — a number; `tolerance` — absolute slack, default 0; `unit` — short label. | Types a figure. Use it for the module's arithmetic. |
| `order` | `options` — listed **in the correct order**. | Arranges the shuffled list. |
| `match` | `pairs` — list of `[left, right]`. | Matches each left to a right from a shuffled list. |
| `cloze` | `q` contains **one** blank written as `___`; `answer` — a string, or a list of every acceptable fill. | Types the missing word. Compared case- and punctuation-insensitively. |
| `short` | `model` — what a good answer contains. | Writes one or two sentences. Graded by Claude when connected, self-scored otherwise. Not drawn into checkpoints. |

The build rejects an out-of-range index, a `multi` with an empty answer, a `tf` whose answer
is not a boolean, a `numeric` whose answer is not a number, an `order` or `match` with fewer
than two entries, a `cloze` without `___`, a `short` without `model`, and `feedback` whose
length does not match the options.

### Writing good quiz questions

Test whether the reader can *use* the idea, not whether they read the sentence. The weak
form is "Which of these is the definition of X?". The strong form gives a situation and asks
what follows from it. Distractors should be things a half-learner would actually believe.

Use the type the material calls for: `numeric` for anything with arithmetic, `order` for a
real sequence, `multi` when several things genuinely apply, `cloze` for a term the reader
must produce rather than recognise, `short` for the one idea per module that only a sentence
can test.

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

Reports every problem in one pass: missing assessments, bad answer indexes, wrong shapes
for a question type, missing `why`, incomplete cards, an incomplete `roleplay`, an unknown
module in a `**Requires:**` line, section/suggestion count mismatches, and orphaned entries
that match no module. Fix them all before building.
