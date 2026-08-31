# M14 — Experimentation and Testing

**Time:** 90 minutes (35 read · 40 exercise · 15 recall)
**Part 1 of 6 · Expert Layer**

---

## Why this matters

M13 ended on an uncomfortable note: no measurement method is true. Experimentation is the exception. A properly randomised test is the only tool in marketing that produces a causal answer rather than a correlational story.

It is also the tool most often used badly. Most "A/B tests" in industry are underpowered, stopped early, judged on the wrong metric, or not randomised at all — producing confident conclusions that are noise. Knowing when a test can answer your question, and when you do not have the traffic to run one at all, is a senior skill few people acquire.

---

## Core concepts

### A hypothesis is a sentence with four parts

Not "let's try a green button." A usable hypothesis reads:

> **Because** [evidence], **we expect** [specific change] **to cause** [effect on one metric], **measured by** [metric, over what period].

Worked: *Because 61% of session recordings show users scrolling past the pricing table without stopping, we expect a three-tier comparison with a recommended plan to increase trial starts, measured by trial-start rate per session over four weeks.*

The "because" is the part that matters. Tests grounded in evidence — recordings, interviews, support tickets, funnel drop-off — win far more often than tests grounded in an opinion voiced in a meeting. The evidence also tells you what to do next when the test loses.

### Decide the primary metric before you run it

One primary metric, chosen in writing before launch. Everything else is secondary and cannot, by itself, declare a winner. The reason is arithmetic: if you track ten metrics and accept any one reaching significance, your real false-positive rate is nowhere near 5%. Deciding afterward which metric "won" is how organisations accumulate confident falsehoods.

Choose the metric closest to money that the test can plausibly move. A homepage test usually cannot move revenue detectably — the effect is diluted by everything downstream — so the honest primary metric may be click-through to the next step.

Always name **guardrail metrics**: things that must not get worse. Refund rate, unsubscribe rate, lead quality, page speed, AOV. A checkout test that lifts conversion 8% while raising refunds 20% is a loss.

### A/B vs multivariate vs before-after

**A/B (and A/B/n)** — split traffic randomly between control and variants at the same time. The default, and almost always right.

**Multivariate (MVT)** — test combinations of several elements at once (headline × image × button) to learn interaction effects. Traffic required multiplies by the number of cells: four elements with two versions each is sixteen. Almost nobody outside large ecommerce has the volume. Use A/B with bolder variants instead.

**Before-after** — change the page on Tuesday, compare this week to last week. Usually invalid, and the most common thing companies actually do. It is contaminated by everything else that changed: day of week, seasonality, a competitor's promotion, a press mention, a payday. You are measuring your change plus the world. Acceptable only for things that cannot be split — a rebrand, a price change — and then only with a long baseline, an explicit note that the result is not causal, and ideally a geographic control.

### Randomisation is the whole trick

Random assignment makes the two groups identical in expectation on everything, including things you never thought to measure. Break it and you have nothing. People break it by assigning by day (Mondays get A), by device or geography, by letting the variant load slower so impatient users bounce from one side, or by not persisting assignment so a returning user lands in both groups. On mailing lists, randomise recipients rather than sending A first and B an hour later.

### Sample size and minimum detectable effect

This is the calculation that kills most test plans, which is why it comes first, not last. Three inputs: **baseline conversion rate**, **minimum detectable effect (MDE)** — the smallest lift worth detecting — and tolerance for error (conventionally 95% confidence, 80% power).

A rule of thumb for a 50/50 test at those settings:

```
n per variant ≈ 16 × p × (1 − p) / (MDE in absolute terms)²
```

**Worked example.** Baseline conversion 3%. You want to detect a 10% relative lift, i.e. 3.0% → 3.3%, so the absolute MDE is 0.003.

```
n ≈ 16 × 0.03 × 0.97 / (0.003)²
  ≈ 16 × 0.0291 / 0.000009
  ≈ 0.4656 / 0.000009
  ≈ 51,700 per variant
```

Roughly **103,000 sessions total** — and about 3,100 conversions. At 5,000 sessions a week that is twenty weeks. The test is not feasible.

Now notice the shape of the curve. A 20% lift needs about a quarter of that traffic (~26,000 total). A 5% lift needs four times more (~414,000). **Halving the effect you want to detect quadruples the traffic required.** This single fact should govern your testing strategy: if you have modest traffic, only test changes big enough to produce big effects.

### Significance and p-values, in plain language

A p-value is: *if the variant made no difference at all, how often would chance alone produce a gap at least this large?* p = 0.03 means "a fluke this big happens 3% of the time." Below 0.05 is the convention.

What it is not: the probability the variant is better, or a measure of how big the effect is. A significant 0.4% lift can be commercially worthless; a non-significant 15% lift on thin traffic can be worth pursuing.

Report the **confidence interval**, not just the verdict. "Lift +7%, 95% CI −2% to +16%" tells a decision-maker the truth: probably positive, possibly nothing, worth another look. And **absence of significance is not evidence of no difference** — it usually means the test was too small.

### Peeking, and stopping rules

Checking a running test daily and stopping the moment it crosses 95% is the most common way marketers manufacture false wins: under repeated looks a null test will *eventually* cross the threshold by chance. The significance maths assumes one look at a pre-committed sample size.

Write the stopping rule before launch: run to the calculated sample size, and for at least two full business cycles (whole weeks, never partial ones) so weekday/weekend mix is balanced. Then look once and decide. If you must monitor continuously, use sequential or Bayesian methods designed for it — you are choosing that method, not peeking at a fixed-horizon test. Stopping early for a *loss* that is damaging revenue is a business decision, and fine; just do not record it as a finding.

### Many tests, many false positives

At 95% confidence, one in twenty null tests reads as a winner. Run forty tests a year with no real effects and expect two celebrated wins that are pure noise — usually the most surprising ones, since surprise correlates with fluke. So replicate anything surprising or strategically important before rolling it out, and distrust segment findings ("it worked for mobile users in Spain") that were not pre-specified.

### What to do when you cannot test

Most companies cannot run valid A/B tests. Under roughly 1,000 conversions a month, almost nothing but a very large effect is detectable. Do not fake it — substitute:

- **Bigger swings.** Test a different offer, page or positioning — not a button colour. Large changes produce detectable effects and teach more per test.
- **Painted-door and smoke tests.** Add the button for the plan that does not exist yet; count clicks; show an honest "coming soon, want early access?" You measure demand without building anything.
- **Qualitative research.** Five user tests or five customer interviews find your top three conversion killers faster than any underpowered test. Recordings tell you *where* people fail; interviews tell you *why*.
- **Best-practice priors.** Page speed, a clear value proposition above the fold, fewer form fields, visible pricing, credible social proof. Just implement them.
- **Holdouts at the account level.** For ads, hold out a region or an audience rather than splitting a page (M15).

Saying "we don't have the traffic to test this, so I'm deciding on evidence and judgment, and here's what would change my mind" is a senior answer. Running the test anyway and reporting a fake 95% is a junior one.

---

## How it works in practice

**The test log.** Organisations fail to learn from testing because results live in a screenshot in someone's Slack. Keep one shared table, one row per test, permanently:

| ID | Date | Area | Hypothesis | Primary metric | MDE | Sample | Result & CI | Decision | What we now believe |
|----|------|------|-----------|----------------|-----|--------|-------------|----------|---------------------|

The last column makes it an asset. Not "variant B won," but "customers respond to risk-reversal more than to discounting — third time we've seen it." Losses are entries too; a documented loss stops the same idea being re-proposed every year.

**Velocity vs quality.** Both fail alone. High velocity with sloppy method produces a fast stream of noise that you then act on — worse than not testing. High quality at four tests a year is too slow to compound. A realistic aim for a small team is a handful of well-formed tests a quarter, plus judgment-based improvements that were never going to be testable.

**Prioritise a backlog** with ICE (Impact, Confidence, Ease, 1–5, ranked by the product). The scoring is a discussion device, not a formula — its value is forcing you to say how confident you actually are.

---

## 2026 reality check

- **Platform-side testing is the norm for ads.** Meta's A/B tool and Google's experiments handle randomisation, but inherit black-box optimisation: Advantage+ and Performance Max reallocate delivery mid-test, and the platform judges on its own attributed conversions. Treat platform experiments as directional; treat geo holdouts and conversion lift studies as evidence (M15).
- **AI made variant production nearly free and hypothesis quality the bottleneck.** You can generate fifty ad variations in a morning; your traffic did not multiply by fifty. Testing capacity is unchanged — but there is no longer any excuse for a thin creative pipeline.
- **Personalisation claims deserve the same scrutiny.** "AI-personalised experiences lifted conversion 30%" is a before-after claim unless there was a holdout. Ask for the holdout.
- **Measurement gaps affect tests too.** Cookies survived, but consent rejection, ad blockers and ITP mean your test population is the measurable subset. Fine for comparing variants — both arms lose data the same way — unless the change itself affects tracking.

---

## Common mistakes

- **No pre-registered primary metric,** so the winner is chosen after the fact from whichever number looks best.
- **Stopping the moment it hits 95%.** Manufactured wins.
- **Testing trivia.** Button colours on 400 sessions a week.
- **Ignoring MDE**, running a test that could never have detected the effect, and concluding "no difference."
- **Running partial weeks,** so Tuesday-heavy traffic decides the outcome.
- **Not checking the guardrails** — lifting leads while destroying lead quality.
- **Never re-testing a big winner** and building strategy on a fluke.
- **No test log,** so the same idea is retested every eighteen months as staff turn over.

---

## Exercise (40 minutes)

For **your chosen business**:

1. **Three hypotheses** in the because/we-expect/measured-by format, each grounded in a specific piece of evidence you can name. If you have no evidence, your first task is not a test — write down how you would get it.
2. **Sample size reality check.** Take your top hypothesis. Write down your real baseline conversion rate and weekly traffic. Compute the sample needed for a 10% relative lift, then for a 25% lift. State how many weeks each would take, and conclude honestly whether you can test at all.
3. **If you cannot test**, write the alternative plan: which two of bigger swings / painted door / five user tests / best-practice priors you will use, and what evidence would change your mind afterward.
4. **Design one full test**: variant, primary metric, two guardrails, randomisation unit, sample size, duration in whole weeks, stopping rule. One page.
5. **Build the test log** with the columns above and enter this test as row one.
6. **Prioritise.** Score all three hypotheses on ICE and write one sentence on why the top one is worth the traffic it will consume.

---

## Recall (15 minutes)

Close everything. Write from memory:

1. The four parts of a hypothesis.
2. Why before-after comparisons are usually invalid, and the two cases where they are acceptable.
3. What happens to required sample size when you halve the effect you want to detect.
4. What a p-value of 0.04 does and does not mean.
5. What peeking does to a test, and what a stopping rule contains.
6. Four things to do when you lack the traffic to test.

---

## If you remember one thing

**Run the sample size calculation before you design the test, not after.** It tells you whether the question can be answered at all — and if it cannot, the honest move is a bigger change, a qualitative method, or a decision made on judgment with the reasoning written down.

---

**Next:** [M15 — Budgets, media mix, and incrementality](M15-budget-and-incrementality.md)
