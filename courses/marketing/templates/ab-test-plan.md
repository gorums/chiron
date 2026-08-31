# A/B Test Plan

**Use with:** M14 — Experimentation and testing
**Time to fill:** 30 minutes
**Rule:** if you cannot fill in the sample size section, you cannot run the test. That is a real answer, and it is the most common one.

Most small businesses do not have enough traffic to A/B test anything. Discovering that here, in thirty minutes, saves you from three months of running tests that will tell you nothing while feeling scientific.

---

## Header

| Field | Value |
|-------|-------|
| Test name | |
| Owner | |
| Surface (page / email / ad) | |
| Traffic source(s) included | |
| Planned start | |
| Planned end | |
| Status | Planned / Running / Concluded / Abandoned |

---

## 1. Hypothesis

Use this format. All four parts are required.

> **Because** [evidence you already have],
> **we believe that** [change],
> **will cause** [effect on the primary metric],
> **and we will know we are right when** [observable result].

**Your hypothesis:**

```
Because ______________________________________________________
we believe that ______________________________________________
will cause ___________________________________________________
and we will know we are right when ___________________________
```

**Filled example:**

```
Because Clarity recordings show 61% of mobile visitors scroll past the form
without stopping, and 7 of 12 exit-survey responses asked what it costs,
we believe that showing a starting price above the form
will cause more form submissions per session on mobile paid traffic,
and we will know we are right when mobile CVR rises from 3.1% to at least
3.9% over the test window with the lead-quality guardrail intact.
```

**A failing hypothesis:** "We think a green button will work better." No evidence, no mechanism, no threshold. Even if it wins you learn nothing transferable, which is the point of testing at all.

**What is the belief being tested?** Write the general principle, because the specific result is worth less than the principle: ______________

---

## 2. Variants

| Variant | Description | What exactly differs |
|---------|-------------|----------------------|
| A (control) | | — |
| B | | |
| C (only if traffic allows) | | |

**Change one thing at a time** unless you are deliberately testing a whole new concept against the old one. A five-change redesign test tells you the new page won, not why, and you cannot carry the lesson anywhere else. Both are legitimate; know which you are doing:

- [ ] Isolated variable (learn a principle, smaller effect, needs more traffic)
- [ ] Whole-concept test (bigger effect, faster, learn less)

---

## 3. Primary metric

**One.** Chosen before launch. If you have two primary metrics you have none.

| Field | Your answer |
|-------|-------------|
| Primary metric | |
| Exact definition | |
| Where it is measured | |
| Current baseline | |
| Baseline measured over | |

Choose the metric closest to money that you have enough volume to measure. Click-through rate is easy to move and often does not move revenue. Prefer the downstream metric unless volume forbids it, and if you must use an upstream proxy, say so explicitly here: ______________

---

## 4. MDE and required sample size

**MDE** (minimum detectable effect) is the smallest improvement you care about. Set it by what is worth the effort, not by what would be nice.

| Field | Your answer |
|-------|-------------|
| Baseline conversion rate | |
| MDE (relative, e.g. +15%) | |
| MDE (absolute) | |
| Statistical significance (use 95%) | |
| Statistical power (use 80%) | |
| One-tailed or two-tailed | Two-tailed |
| **Required sample per variant** | |
| **Required total sample** | |

Use any free A/B test sample size calculator. Do not estimate this in your head; the relationship is not intuitive.

**Rules of thumb to sanity-check the calculator's answer:**

- Halving the MDE roughly **quadruples** the required sample.
- At a 3% baseline, detecting a relative +10% lift needs on the order of tens of thousands of visitors per variant.
- At a 3% baseline, detecting a relative +30% lift needs on the order of a few thousand per variant.
- Under ~200 conversions per variant, do not bother. The result will not be trustworthy no matter what the tool's confidence number says.

**Worked example:**

```
Baseline CVR              3.1%
MDE (relative)            +25%  → absolute target 3.875%
Significance / power      95% / 80%, two-tailed
Required per variant      ~7,400 sessions
Required total            ~14,800 sessions
Current mobile paid traffic  2,100 sessions/month
Time to reach sample      ~7 months
Verdict                   Do not run this as an A/B test.
```

That verdict is a success, not a failure. It took twenty minutes and it saved seven months.

**If you do not have the traffic, use one of these instead:**

- **Just ship it.** If the change is cheap, low-risk, and supported by qualitative evidence, make it and move on. Most page copy falls here.
- **Before/after with a long window and no other changes.** Weak evidence, honest about being weak. Freeze everything else, compare 8 weeks to 8 weeks, and do not claim causality.
- **Qualitative research.** Five user tests, session recordings, an exit survey. Lower confidence per unit of evidence, dramatically higher information per hour at low traffic.
- **Test bigger things.** You cannot detect a +5% button change, but you may be able to detect a +60% new offer. If you lack traffic, only test changes big enough to be visible.
- **Test upstream.** Ad creative usually has far more volume than the landing page and larger effect sizes.

---

## 5. Duration

| Field | Your answer |
|-------|-------------|
| Expected traffic per week (total) | |
| Weeks to reach required sample | |
| **Minimum run length** | At least 2 full weeks, and always whole weeks |
| Planned end date | |
| Anything scheduled in the window that could distort it | Holidays, promotions, PR, seasonality, a competitor's sale |

Run whole weeks. Tuesday behaves differently from Sunday, and a test stopped mid-week is weighted toward whichever days it happened to include.

Also consider the **business cycle**: if your median time from click to purchase is 18 days, a 14-day test measures the front of the funnel only, and you must either extend it or accept you are testing a proxy.

- Median time from exposure to conversion: ______ days
- Test window covers it? Yes / No / Using a proxy metric because:

---

## 6. Guardrail metrics

Metrics that must not get worse, even if the primary metric improves. Volume wins that destroy quality are the most common self-inflicted injury in CRO.

| Guardrail | Why it matters | Acceptable range | Action if breached |
|-----------|----------------|------------------|--------------------|
| | | | |
| | | | |
| | | | |

**Filled example:**

| Guardrail | Why | Acceptable | If breached |
|-----------|-----|------------|-------------|
| Lead-to-customer rate | Showing price may attract browsers | Not below 6.5% (baseline 7.9%) | Declare no-win even if CVR rose; net customers is what matters |
| Average deal size | Anchoring low could shrink deals | Within 10% of baseline | Investigate before rolling out |
| Page load (LCP) | The variant adds an element | Under 2.5s | Fix before continuing |

**Always include a downstream guardrail.** If your primary metric is a form fill, at least one guardrail must be about what happens to those leads afterwards.

---

## 7. Stopping rule

Agreed before launch, in writing.

- **We will not look at results before:** ______ (date)
- **We will stop when:** the required sample is reached OR the end date arrives, whichever is later.
- **We will stop early only if:** a guardrail is breached beyond its range, or something is technically broken.
- **We will NOT stop early because a variant looks like it is winning.**

**Why this matters:** peeking at a running test and stopping when it looks significant inflates your false-positive rate badly — checking daily and stopping at the first significant reading can push a nominal 5% error rate to well over 20%. Early "winners" that evaporate are the single most common reason organisations lose faith in testing.

**Pre-committed decision table:**

| Outcome | Decision |
|---------|----------|
| B wins, significant, guardrails intact | Ship B. Record the principle learned. |
| B wins, significant, guardrail breached | Do not ship. Investigate the trade-off. |
| No significant difference | Ship whichever is cheaper to maintain. Record that the variable does not matter at this magnitude — that is a real finding. |
| A wins significantly | Keep A. Ask what the result implies about the belief in section 1. |
| Test invalid (tracking broke, traffic mix changed, sample not reached) | Discard. Do not report the number. Fix and rerun or abandon. |

Fill this in before launch and you will never have the "well, if we squint..." conversation.

---

## 8. Result log

| Field | Value |
|-------|-------|
| Actual start / end | |
| Sample achieved (A / B) | |
| Conversions (A / B) | |
| Conversion rate (A / B) | |
| Relative lift | |
| Confidence / p-value | |
| Guardrails held? | |
| Decision taken | |
| Date shipped or reverted | |

**What we learned (the principle, not the pixel):**

```

```

**What we would do differently in the next test:**

```

```

**Did the shipped winner hold up 30 days later?** ______________

That last question is worth asking every time. A meaningful share of shipped "winners" do not show up in the aggregate numbers afterwards. Checking is how you find out whether your testing programme is producing real value or a scrapbook of noise.

---

## Running test index

Keep one row per test, forever. This log becomes your most valuable asset as a marketer: it is evidence you can reason about outcomes, and it is portfolio material.

| # | Date | Surface | Hypothesis (short) | Result | Lift | Shipped? | Principle learned |
|---|------|---------|--------------------|--------|------|----------|-------------------|
| 1 | | | | | | | |
| 2 | | | | | | | |
| 3 | | | | | | | |

---

## What good looks like

The sample size was calculated before the test was built, and roughly a third of planned tests get cancelled at that step — correctly. The hypothesis names the evidence that prompted it. There is a downstream guardrail. The stopping rule and the decision table were written before launch and were honoured even when the early numbers were exciting. The log records the transferable principle, not just which variant won.

## Common failure

Peeking and stopping early. It feels like diligence and it is the fastest way to fill your site with changes that do nothing. The close second is testing trivial variables at low traffic — button colours, headline synonyms — where the true effect is smaller than the noise, so every result is a coin flip dressed up as a finding. If your traffic is thin, do not test small things more carefully; test bigger things, or stop testing and go talk to five customers instead.
