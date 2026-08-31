# Unit Economics and Funnel Model

**Use with:** M05 — Funnels, journeys, and unit economics
**Time to fill:** 60 minutes
**Refill:** monthly. This is the single most-used sheet in the whole course.

The arithmetic on this page decides whether a channel is allowed to exist. Marketers who cannot do it get fired; marketers who can do it get to allocate budget. There is no third option.

Work in a spreadsheet if you prefer — the point is the structure, not the file format.

---

## The formulas, written out

Learn these. They are all you need.

```
Step conversion rate     = outputs of step / inputs to step
Overall conversion rate  = product of every step conversion rate
Customers               = traffic x overall conversion rate

CAC                     = total acquisition spend / new customers acquired
                          (spend must include ad spend + tools + agency/salary
                           attributable to acquisition. Excluding people costs
                           is the most common way CAC gets faked.)

Contribution margin     = revenue per order (or per month) - variable costs
                          Variable = COGS, payment fees, shipping, delivery
                          labour, support. NOT rent, NOT salaries of people who
                          would be there anyway.

Contribution margin %   = contribution margin / revenue

Average lifetime (mo)   = 1 / monthly churn rate
LTV                     = monthly contribution margin x average lifetime
                          (subscription)
LTV                     = AOV x contribution margin % x purchases per lifetime
                          (transactional)

LTV:CAC                 = LTV / CAC
Payback (months)        = CAC / monthly contribution margin
                          (transactional: CAC / contribution per order x orders
                           per month)

Max affordable CAC      = LTV / target LTV:CAC ratio
Max affordable CPA      = max affordable CAC x (conversion rate from that step
   (at any funnel step)    to customer)
Max affordable CPC      = max affordable cost per lead x landing page CVR
Break-even CAC          = LTV  (i.e. LTV:CAC = 1:1 — you make nothing)
```

Two rules that stop most bad decisions:

1. **LTV must be gross contribution, not revenue.** If you use revenue, every ratio flatters you by roughly the size of your cost of delivery, and you will fund a channel that loses money on every sale.
2. **Cap the lifetime horizon.** An LTV built on 60 months of assumed retention is a work of fiction financed with real money. Use 12, 24, or at most 36 months and say which.

---

## Part 1 — The funnel

Fill in the volume at each step; the rates compute from them. Add or remove rows to match your real funnel.

| # | Step | Volume | Step CVR | Note |
|---|------|--------|----------|------|
| 1 | Impressions / reach | | — | |
| 2 | Clicks / visits | | | CTR |
| 3 | Engaged sessions (or product views) | | | |
| 4 | Leads / add to cart | | | Landing page CVR |
| 5 | Qualified / checkout started | | | |
| 6 | Opportunity / call held | | | |
| 7 | **Customers** | | | |

- Overall conversion rate (step 2 to step 7): ______ %
- Time from step 2 to step 7 (median days): ______

### Worked example — a B2B service, one paid search channel, one month

| # | Step | Volume | Step CVR |
|---|------|--------|----------|
| 1 | Impressions | 200,000 | — |
| 2 | Clicks | 2,400 | 1.20% (CTR) |
| 3 | Engaged sessions | 1,730 | 72.1% |
| 4 | Leads (form submits) | 96 | 4.00% of clicks |
| 5 | Calls booked | 43.2 | 45.0% |
| 6 | Calls held | 30.2 | 70.0% |
| 7 | Customers | 7.56 | 25.0% |

Overall click-to-customer rate: 7.56 / 2,400 = **0.315%**
Lead-to-customer rate: 7.56 / 96 = **7.875%**

---

## Part 2 — Cost side

| Line | Amount | Note |
|------|--------|------|
| Media spend | | |
| Tools attributable to acquisition | | |
| Agency / freelancer | | |
| Internal time (hours x loaded rate) | | Do not skip this |
| **Total acquisition spend** | | |
| New customers acquired | | |
| **CAC** | | Total spend / new customers |
| Cost per click | | |
| Cost per lead | | |

**Worked example:**

| Line | Amount |
|------|--------|
| Media spend | 2,640 EUR (2,400 clicks x 1.10 EUR CPC) |
| Tools | 0 (shared, immaterial at this volume) |
| Internal time | Excluded here for simplicity — see note below |
| **Total acquisition spend** | 2,640 EUR |
| New customers | 7.56 |
| **CAC** | 2,640 / 7.56 = **349 EUR** |
| Cost per click | 1.10 EUR |
| Cost per lead | 2,640 / 96 = 27.50 EUR |

Note on internal time: if the founder spends 8 hours a month on this channel at a 40 EUR/h loaded rate, that is 320 EUR, and true CAC becomes 2,960 / 7.56 = **392 EUR**, 12% worse. Decide once whether you include it, write the decision down, and be consistent. Comparing a channel with people costs against one without is how bad allocations get made.

---

## Part 3 — Value side

### If subscription / recurring

| Line | Amount |
|------|--------|
| Price per month | |
| Variable delivery cost per month | |
| **Monthly contribution margin** | |
| Contribution margin % | |
| Monthly churn rate | |
| Implied average lifetime (1 / churn) | |
| **Horizon used** (12 / 24 / 36 months) | |
| **LTV** (monthly contribution x horizon) | |

### If transactional / ecommerce

| Line | Amount |
|------|--------|
| AOV | |
| COGS per order | |
| Shipping + payment fees per order | |
| **Contribution per order** | |
| Contribution margin % | |
| Orders per customer per year | |
| Horizon used (years) | |
| **LTV** | |

**Worked example (subscription):**

| Line | Amount |
|------|--------|
| Price per month | 220 EUR |
| Variable delivery cost | 90 EUR |
| **Monthly contribution margin** | **130 EUR** (59.1%) |
| Monthly churn | 2.5% |
| Implied average lifetime | 1 / 0.025 = 40 months |
| **Horizon used** | 24 months (deliberately shorter than implied — we have only 19 months of data) |
| **LTV** | 130 x 24 = **3,120 EUR** |

---

## Part 4 — The verdict

| Metric | Your number | Rough benchmark | Verdict |
|--------|-------------|-----------------|---------|
| LTV:CAC | | 3:1 healthy; under 1:1 you are paying for customers | |
| Payback (months) | | Under 12 for SMB subscription; under 3 for ecommerce; under 18 tolerable for enterprise if funded | |
| Contribution margin % | | Above 50% gives room to buy growth; under 25% means most channels are closed to you | |
| Overall CVR | | Compare to yourself last month, not to a blog post | |

**Worked example:**

- LTV:CAC = 3,120 / 349 = **8.9 : 1**
- Payback = 349 / 130 = **2.7 months**
- Contribution margin = **59%**

Verdict: not "we are doing great." A ratio of 8.9:1 with a 2.7-month payback usually means the channel is **underfunded**, not that it is efficient. There is room to bid CPCs up substantially, or to enter more expensive channels, and still be well inside a healthy range. Ratios that look too good are usually a sign of a volume ceiling, not a triumph.

---

## Part 5 — Ceilings: max affordable CPA and CPC

This is where the sheet becomes operational. It tells you the number to type into an ad platform.

```
Target LTV:CAC ratio      = _____ (3:1 is the usual planning target)
Max affordable CAC        = LTV / target ratio
Max affordable cost/lead  = max CAC x lead-to-customer rate
Max affordable CPC        = max cost per lead x landing page CVR
Break-even CPC            = LTV x lead-to-customer rate x landing page CVR
```

**Worked example:**

```
Target ratio            = 3 : 1
Max affordable CAC      = 3,120 / 3            = 1,040 EUR
Lead-to-customer rate   = 7.875%
Max cost per lead       = 1,040 x 0.07875      = 81.90 EUR
Landing page CVR        = 4.0%
Max affordable CPC      = 81.90 x 0.04         = 3.28 EUR
Break-even CPC          = 3,120 x 0.07875 x 0.04 = 9.83 EUR
```

Current CPC is 1.10 EUR against a max of 3.28 EUR at a 3:1 target. That is the answer to "should we spend more on Google Ads." Yes, up to roughly 3x the current bid, as long as the conversion rates hold at higher volume — which they usually do not, because you buy less-qualified traffic as you widen. Re-measure at every 50% step up in spend.

**Your numbers:**

```
Target ratio            = _____ : 1
Max affordable CAC      = _____
Max cost per lead       = _____
Max affordable CPC      = _____
Break-even CPC          = _____
```

Also compute the payback ceiling, because it usually binds before the ratio does when cash is tight:

```
Max CAC by payback rule = monthly contribution x months of payback you can fund
Worked example          = 130 x 12 = 1,560 EUR
```

**Your binding constraint is the lower of the two.** In the example, 1,040 EUR (the ratio) binds before 1,560 EUR (payback). Which one binds tells you whether your problem is profitability or cash.

---

## Part 6 — Where the leverage is

Recompute the funnel changing one step at a time by a realistic amount. The step with the biggest effect on CAC is where your next month of work goes.

| Step changed | From | To | New customers | New CAC | CAC change |
|--------------|------|----|---------------|---------|------------|
| CTR | | | | | |
| Landing page CVR | | | | | |
| Lead to call booked | | | | | |
| Call held rate | | | | | |
| Close rate | | | | | |
| Price | | | | | |

**Worked example:**

| Step changed | From | To | New customers | New CAC | CAC change |
|--------------|------|----|---------------|---------|------------|
| Landing page CVR | 4.0% | 5.0% | 9.45 | 279 EUR | -20% |
| Call held rate | 70% | 85% | 9.18 | 288 EUR | -18% |
| Close rate | 25% | 28% | 8.47 | 312 EUR | -11% |
| CPC | 1.10 | 0.95 | 7.56 (spend 2,280) | 302 EUR | -14% |

The call-held fix is a reminder text and a shorter booking window. It is a day of work and it is worth as much as a 14% CPC reduction that would take a month of bid work. **The weakest step in the funnel is almost never the one people are optimising.** That is the whole point of building this sheet.

**My weakest step:** ______________
**Cheapest realistic improvement to it:** ______________
**Expected effect on CAC:** ______________

---

## What good looks like

Every number on the sheet traces to a source you could open right now — the ad platform, the CRM, the invoice, the P&L. LTV uses contribution, not revenue, and a stated horizon shorter than the implied lifetime. The max CPC figure is written on a sticky note next to whoever manages bids. Part 6 has been done, and the next month's work is aimed at the step it identified, not at the step that is most fun to optimise.

## Common failure

LTV inflation. It happens three ways, often at once: using revenue instead of contribution margin, assuming a retention curve you have not observed for long enough, and excluding people costs from CAC. Each is individually defensible-sounding and together they can make a channel that loses money look like a 5:1 winner. If a model justifies a decision you already wanted to make, recompute it with revenue swapped for contribution and the horizon halved, and see if it survives.
