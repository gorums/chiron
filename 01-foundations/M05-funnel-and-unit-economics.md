# M05 — Funnels, Journeys, and Unit Economics

**Time:** 90 minutes (35 read · 45 exercise · 10 recall)
**Part 1 of 6 · Foundations**

---

## Why this matters

**This is the most important module in Part 1.** Everything else is judgement you build over years. This is arithmetic you can learn in ninety minutes, and it decides whether a business survives.

Marketers who cannot do this arithmetic get fired, because they cannot answer the only question a CFO ever asks: *what did we get for the money, and can we afford more of it?*

---

## Core concepts

### AIDA and the modern lifecycle

AIDA — Attention, Interest, Desire, Action — dates from the 1890s and still describes the sequence of persuasion. The modern version adds what happens after the sale: **Awareness → Consideration → Conversion → Retention → Advocacy.** Retention and advocacy are where profit lives. Acquisition usually loses money on the first purchase; the business is made on the second and the tenth.

### The funnel is an accounting fiction

Real journeys are not funnels. People enter in the middle, leave, return months later, ask a friend, read reviews, forget, see an ad, then search your brand name — at which point search ads take credit for a decision made elsewhere. Google's researchers call this loop of exploration and evaluation the **messy middle**.

So why use a funnel? Because it is a **measurement device**, not a description of behaviour. It locates where people are lost and sizes the opportunity. Use it for arithmetic; never use it to claim you know the journey.

### Conversion math, and where the leverage is

A funnel multiplies. Small changes at each step compound.

**Worked example 1 — where to spend your effort**

An e-commerce store, one month:

| Step | Rate | Count |
|---|---|---|
| Visitors | — | 10,000 |
| Add to cart | 6% | 600 |
| Begin checkout | 50% | 300 |
| Complete purchase | 60% | 180 |
| Average order value | — | $80 |
| **Revenue** | | **$14,400** |

Two options:

- **Double traffic** to 20,000 → revenue $28,800. Cost: double the ad spend, and the second batch of traffic is usually worse than the first, so realistically less than double.
- **Fix checkout completion from 60% to 75%** — a plausible result of removing forced account creation. 225 purchases, $18,000. That is +25% for a one-off engineering change with no ongoing cost.

Compound them: cart 6%→7% *and* checkout 60%→75% gives 262 purchases and $20,960 — a 46% lift, permanent, which also makes every future ad dollar 46% more efficient.

The rule: **percentage gains deep in the funnel are cheap and permanent; traffic gains are linear and rented.** Fix the leakiest step first; the last step before payment is usually the most fixable.

The counter-case: with 200 visitors a month, no conversion improvement will save you and you could not measure one anyway (M14). Then traffic genuinely is the constraint. Diagnose which world you are in first.

### CAC, blended vs paid

**CAC** = total acquisition cost ÷ new customers. Include media, agency fees, tools and the salaries of people doing acquisition — not just ad spend.

**Paid CAC** = paid spend ÷ customers attributed to paid. **Blended CAC** = all acquisition spend ÷ *all* new customers, organic and word of mouth included.

Blended always looks better, because organic customers dilute it. It answers "can this business afford to grow," but hides whether paid is working. Watch the gap: if blended stays flat while paid CAC rises, organic is carrying you and paid is quietly failing.

### LTV, and why it is usually overstated

Lifetime value is the **gross profit** a customer generates, not the revenue. Three common inflations:

1. **Revenue instead of contribution margin.** A $100 customer at 30% margin is worth $30.
2. **Optimistic lifetimes.** "Customers stay 5 years," from a company 18 months old, is a projection.
3. **Ignoring time.** Money in year four is worth less than money now, and you may not survive to collect it.

Use a conservative window — 12 or 24 months of contribution margin — and call it LTV24. It is what a lender or investor will model anyway.

### LTV:CAC and payback

**LTV:CAC of 3:1** is the standard rule of thumb: below it you probably cannot fund acquisition plus overhead; well above it you are probably under-investing.

It is a heuristic, not a law. It came from SaaS benchmarking, assumes predictable subscription retention, and says nothing about *when* the money arrives. A business with 5:1 LTV:CAC and a 30-month payback can go bankrupt while growing.

**CAC payback period** = CAC ÷ monthly contribution margin per customer. This is the number that matters when you cannot raise capital freely, because it says how long your cash is locked up. Under 12 months is comfortable; over 18 means every new customer worsens your cash position before improving it.

**Worked example 2 — a subscription business**

- Price: $50/month. Gross margin 80% → **$40 contribution per month**
- Average retained life: 20 months → **LTV = $800** (contribution, not revenue)
- CAC: $200

LTV:CAC = **4:1**. Payback = $200 ÷ $40 = **5 months**. Healthy on both counts.

Now the acquisition chain. Target CAC is $200, and:

- Lead → customer conversion: **10%** → max cost per lead = $200 × 0.10 = **$20**
- Click → lead conversion: **5%** → max cost per click = $20 × 0.05 = **$1.00**

So $1.00 is your ceiling CPC at break-even on CAC. If the keyword costs $3.50, the channel is unaffordable *at your current conversion rates and price*, and you have exactly four ways out: raise the price, improve lead conversion, improve click-to-lead conversion, or find cheaper traffic. Three of the four are not "bid less."

Run this backwards for every channel before you launch it. Five minutes, and it prevents most wasted budget.

### Contribution margin and cohorts

**Contribution margin** = revenue − variable costs (COGS, payment fees, shipping, support). It is the money available to fund acquisition and overhead. Make marketing decisions in contribution margin, never revenue.

**Cohort thinking** groups customers by when they joined and tracks them over time. Aggregates lie: total revenue can rise while every cohort worsens, masked by growing volume. A cohort table is the only reliable way to see whether retention is improving and whether a channel's customers are as good as the ones you had.

---

## How it works in practice

Build one spreadsheet: traffic, step conversion rates, AOV or ARPU, margin, CAC by channel, retention curve, payback. Update it monthly. Most "should we do X?" questions are answered by changing one cell. When a channel underperforms, diagnose in order — traffic volume, step conversion, order value, margin — and check the model before the creative.

---

## 2026 reality check

- **Attribution is much weaker than it was.** Privacy changes, cookie loss and platform black boxes make channel-level CAC an estimate. That raises the value of blended CAC, media-mix modelling and holdout tests (M15) over dashboard attribution (M13).
- **Platform-reported conversions are inflated.** Ad platforms count every conversion they had a plausible claim to, so summing platform reports usually exceeds actual sales. Reconcile against your own order data.
- **Paid acquisition costs keep rising** faster than most price increases, widening the gap between businesses with retention loops (M17) and those renting demand.

---

## Common mistakes

- **Using revenue as LTV.** The most common error, and it inflates everything downstream.
- **Chasing traffic when the constraint is conversion** — or optimising conversion on 200 visitors.
- **Ignoring payback** because LTV:CAC looks good.
- **Excluding salaries and tools from CAC**, then wondering why the P&L disagrees with the dashboard.
- **Averaging across segments.** One profitable cohort can hide three unprofitable ones.

---

## Exercise (45 minutes)

For **your chosen business** — real numbers if you have them, honest estimates labelled as estimates if not:

1. **Build the funnel** (15 min): traffic → key intermediate step → conversion → repeat purchase, with a rate on every arrow.
2. **Contribution margin per customer** (5 min): price minus every variable cost.
3. **LTV24** (5 min): contribution per month or per order × a conservative 24-month retention assumption.
4. **Max affordable CPA** (10 min), backwards as in example 2: target CAC → max cost per lead → max cost per click. Compare with real CPCs in your category. Is any paid channel affordable today?
5. **CAC payback** (5 min). Over 18 months? Note which of the four levers you would pull.
6. **Find the leverage** (5 min): which single step, improved 20% relative, produces the biggest revenue change?

---

## Recall (10 minutes)

From memory:

1. The five lifecycle stages
2. Why the funnel is a fiction but still useful
3. CAC, blended vs paid, and why blended flatters
4. Two ways LTV gets overstated
5. Why payback period can matter more than LTV:CAC
6. The chain from target CAC to maximum cost per click

---

## If you remember one thing

**Work backwards from what a customer is worth in contribution margin to what you can afford to pay for a click.** If the answer is below the market price of traffic, no amount of creative or optimisation fixes it — change the price, the conversion rate, or the channel.

---

**Next:** [M06 — Writing a marketing strategy](M06-strategy-and-planning.md)
