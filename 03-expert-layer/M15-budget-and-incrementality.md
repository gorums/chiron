# M15 — Budgets, Media Mix, and Incrementality

**Time:** 90 minutes (35 read · 40 exercise · 15 recall)
**Part 2 of 6 · Expert Layer**

---

## Why this matters

This is the module that changes what you are worth. Anyone can run a campaign; the person who decides where the money goes, and defends it to a CFO, is doing the senior job.

The central idea is one sentence: **attribution tells you what happened after a click; it cannot tell you what would have happened without the ad.** That gap is where most marketing budgets quietly leak.

---

## Core concepts

### How budgets actually get set

**Percent of revenue.** A fixed share of last year's or forecast revenue — commonly 5–12% depending on category and margin. Easy, stable, and backwards: it cuts spend exactly when sales fall and you most need demand. A sanity constraint, never a rationale.

**Competitive parity.** Match a competitor's share of voice. Its merit is that share of voice and share of market track each other over time, so sustained under-investment tends to cost share. Its flaw is assuming your competitor knows what they are doing and shares your objectives, margins and awareness.

**Objective-and-task.** State the objective, enumerate the tasks, cost each, sum. "We need 240 new customers per quarter. At a 4% landing page conversion rate and £1.80 CPC, that is 6,000 clicks a month at £10,800, plus £4,000 of creative production, plus £3,000 of brand video to keep the top of the funnel filled."

**Only objective-and-task survives a hostile question,** because every line traces to an assumption you can name and revise. Build the number that way, then sanity-check against the other two. Add a **floor and ceiling**: what you would still spend if things went badly, and where you stop even if they go well.

### Allocating across creation and capture

Capture harvests existing demand; creation makes new demand (M01). Capture is capped — if 4,000 people a month search for what you sell and you already appear for all of it, more money buys higher prices on the same clicks. Creation is uncapped but slow, hard to measure, and the first thing cut in a bad quarter.

The failure pattern is universal enough to name: a company scales capture, hits the ceiling, sees CPA rise, cuts the creation spend that was refilling the pool because it "doesn't show ROAS," and enters a two-quarter decline whose cause is invisible in the attribution report. Watch **branded search volume** and **direct traffic** as a proxy for the size of the pool; flat or falling while you push harder on capture means you are harvesting a shrinking field.

### Marginal returns and why "scale what works" fails

Every channel has a **saturation curve**: strong returns early, diminishing returns as the cheap high-intent audience is exhausted, then flat or negative.

The mistake is reasoning from averages. "Google Ads returns 4× — put more in." But that 4× is the average across all spend, including the first, cheapest, most incremental pounds.

```
Spend/mo   Total revenue   Marginal revenue on last £2k
£2,000     £14,000         £14,000  (7.0×)
£4,000     £22,000         £8,000   (4.0×)
£6,000     £27,000         £5,000   (2.5×)
£8,000     £29,500         £2,500   (1.25×)
```

Average ROAS at £8k is 3.7× — healthy-looking. The last £2,000 returned 1.25×, likely below break-even on margin. **The right allocation equalises marginal return across channels**, not average return. You approximate it by stepping spend up or down and watching what the increment does — which requires holdouts, because attribution will credit incremental spend with conversions that were coming anyway.

### Incrementality

**Incremental conversions are the ones that would not have happened without the ad.** Everything else is spend you would have got for free. The only reliable way to know is to withhold advertising from a comparable group.

**Geo holdouts.** Split regions into treatment and control matched on baseline sales — many small regions randomised, not "the North vs the South." Advertise normally in treatment, not at all in control, for four to eight weeks, and compare total sales from your own books. The workhorse: platform-independent, works for offline and multi-channel businesses, and legible to a CFO because it is just "these towns got ads, those didn't."

**PSA and ghost ads.** The control group sees a public-service ad, or — better — has the ad withheld while the platform records that it would have been shown. Ghost ads avoid the PSA's bias, since a PSA still occupies the impression, but need platform support.

**Conversion lift studies.** The platforms' own randomised experiments. Far better than attribution, but the platform grades its own homework, tests are restricted to its inventory, minimum spends are meaningful, and results use its own conversion definitions.

**Switch-back tests.** Alternate weeks on and off. Cheap, but weak: confounded by seasonality, and carryover contaminates the off weeks.

**A cheap holdout anyone can run.** Take your smallest plausibly-representative slice — one region, 10% of your email list, one retargeting audience — and turn the spend off for four full weeks. Track conversions from that slice in your own database, comparing to its share over the prior twelve weeks and to the rest of the business over the same four weeks, which controls for seasonality. Not publishable; it will still catch the largest waste in your account. Be honest about power (M14): a holdout on 30 conversions a month proves nothing.

### Where non-incremental spend hides

**Branded search.** Someone types your brand, clicks the ad, buys, and last-click credits the ad with the full sale — but most of those people were coming regardless. They typed your name.

Worked illustration: £3,000/month on branded search reports 400 conversions, a £7.50 CPA that looks like the best line in the account. A four-week geo holdout pauses it, and conversions in the holdout regions fall 12%, not 100%. Incremental conversions are ~48, not 400, so true incremental CPA is ~£62.50. That is a different decision.

It does not follow that you switch it off. Defensible reasons to keep it: competitors bidding on your name, control of the message and sitelinks, marketplaces outranking you. But you are now buying insurance at a known price rather than "the best CPA in the account."

**Retargeting.** Same logic, sharper — you advertise to people who already visited and were already likely to return. It produces the most flattering number in digital marketing and is often among the least incremental. Test these two first.

### Media mix modelling

**MMM** is a statistical model — typically regression on weekly aggregated data — relating sales to spend by channel plus controls for price, promotions, seasonality and competitor activity. It estimates each channel's contribution plus adstock (carryover) and saturation curves.

**It needs** two to three years of weekly data, real variation in spend by channel (spend identically every week and it learns nothing), and clean records of promotions and price changes. Most small businesses fail that requirement, and no software fixes it.

**Good at:** the portfolio view including offline, TV and PR; long-term effects; working without user-level tracking, so it is immune to cookies, consent and iOS; answering "what if we move £200k from X to Y." **Bad at:** anything tactical, highly correlated channels (always run TV and YouTube together and it cannot separate them), new channels, and small businesses. It overfits easily into a confident wrong answer.

Open-source options — **Google's Meridian** and **Meta's Robyn** — lower the cost but not the data requirement or the analytical skill. Calibrating an MMM with incrementality results is standard practice and materially improves trust in it.

### Triangulation: the 2026 standard

| Method | Answers | Cadence | Weakness |
|--------|---------|---------|----------|
| **MMM** | How the whole portfolio contributes, including offline | Quarterly | Needs years of data; not tactical |
| **Incrementality tests** | Is this spend causing anything? | A few per year | Costs volume; narrow scope |
| **Platform attribution** | Which creative or audience to change now | Daily/weekly | Systematically over-claims |

Senior decision-makers trust independent incrementality testing most, MMM second, in-platform reporting least. Order your own confidence the same way. When the three disagree, that tells you where to run the next test.

### Short and long term

Advertising produces an immediate sales response and a slower accumulation of memory that makes future marketing cheaper. Activation without brand shows good short-term numbers and quietly rising CPAs; brand without activation looks unaccountable and gets cut.

The widely-cited heuristic is roughly **60% brand / 40% activation** for established consumer brands — a reference point, not a law. It shifts toward activation for B2B (commonly cited nearer 50/50), for small companies needing cash this quarter, and in a crisis; toward brand when you have distribution but low awareness, when CPAs climb at flat volume, or when building pricing power. The split is a decision you argue for, not a number you inherit.

---

## How it works in practice

### A worked reallocation

Ecommerce, £40,000/month, 60% gross margin, break-even ROAS 1.67×.

| Channel | Spend | Reported ROAS | Evidence |
|---------|-------|---------------|----------|
| Branded search | £4,000 | 9.0× | No holdout ever run |
| Non-brand search | £12,000 | 3.1× | Marginal ROAS on last £3k: 1.9× |
| Meta prospecting | £14,000 | 1.8× | Geo holdout showed real lift |
| Retargeting | £6,000 | 6.5× | No holdout ever run |
| Creative production | £2,000 | — | Two new concepts/month |
| Brand video | £2,000 | — | Cut last quarter, being restored |

1. **Run the cheap holdouts first.** Four weeks: retargeting off in one matched region, branded search off in another. Suppose retargeting comes back 30% incremental, branded search 15%.
2. **Re-price the flattering lines.** Retargeting's true ROAS is ~1.95× (6.5 × 0.30), barely above break-even. Branded search's is ~1.35× — below it, but partly insurance.
3. **Reallocate.** Retargeting £6,000 → £3,000 (tighter window, exclude recent purchasers); branded search £4,000 → £2,500, keeping defensive coverage on the highest-risk terms. That frees £4,500.
4. **Do not put it all in the best-looking channel.** Non-brand search is already at 1.9× marginal. Put £1,500 into Meta prospecting, where the holdout showed real lift and the curve is not yet flat; £1,500 into creative production, the main lever left in an Advantage+/PMax world; £1,500 into brand video, which refills the pool branded search harvests.
5. **Commit to the check.** Watch total revenue and blended CAC — total spend divided by all new customers — for eight weeks. Blended CAC cannot be gamed by reallocating credit.

Note what happened: reported total ROAS *fell*, because you moved money out of the channels best at claiming credit. If you cannot explain that in advance, do not make the move — you will be blamed for the dashboard.

**Defending it.** A CFO wants four things: the objective the money buys, the assumptions behind each line, what you cut first at −20%, and how you will know if it worked. Bring a one-page table — channel, spend, purpose, expected outcome, confidence, evidence type — and state uncertainty explicitly. "Meta prospecting: £15,500, demand creation, ~340 new customers, medium confidence, based on a geo holdout in May" earns more trust than a precise-looking forecast with no provenance.

---

## 2026 reality check

- **Cookies did not die.** Chrome kept third-party cookies (confirmed April 2025), and most Privacy Sandbox technologies were retired in October 2025 — deprecated in Chrome 144 (January 2026), removal targeted for Chrome 150 (July 2026). GDPR and ePrivacy obligations are unchanged. The measurement gap comes from consent rejection, ITP, ad blockers and ATT — strengthening the case for geo tests and MMM, neither of which needs user-level data.
- **Black-box buying moved the budget question up a level.** With Performance Max and Advantage+ the algorithm allocates to keywords and placements, not you. You still control how much each campaign gets, what conversion it optimises toward, which first-party data it learns from, and the creative and offer — so allocation and incrementality are a *larger* share of the job than five years ago.
- **Zero-click search lowers the capture ceiling.** With ~60% of Google searches ending without a click and AI Overviews cutting top-position organic CTR sharply, the harvestable pool is shrinking — pushing sensible allocation toward creation and toward being the brand people search for by name.

---

## Common mistakes

- **Allocating on average ROAS** instead of marginal return.
- **Scaling the channel with the best reported number,** usually the least incremental one.
- **Never running a single holdout,** then arguing about attribution models for years.
- **Cutting brand spend in a downturn** and mistaking the following two quarters' decline for a market problem.
- **Setting the budget as a percentage** and having no argument when asked why.
- **Judging an MMM by how good the numbers look** rather than whether spend varied enough for it to learn.
- **Reallocating and then judging it on channel ROAS,** which will get worse by construction.

---

## Exercise (40 minutes)

For **your chosen business**:

1. **Build the budget objective-and-task style.** From a customer or revenue target, back through your M05 funnel rates, costing each line. Compare the total to a percent-of-revenue sanity check.
2. **Split creation vs capture** and justify the ratio in two sentences, given your awareness level, category and cash position.
3. **Sketch the saturation curve** for your largest channel and mark where marginal return crosses break-even ROAS or max CPA.
4. **Design one cheap holdout:** which slice, how long, what you measure from your own data, what result would change your allocation, and what it costs in forgone sales. Pick branded search or retargeting if you run either.
5. **Do a reallocation.** Move at least 10% of the budget in a before/after table with reasoning per line and the expected effect on total revenue and blended CAC — including whether reported ROAS will fall.
6. **Write the CFO page:** objective, allocation table with purpose and confidence per line, what you cut first at −20%, and how you will know in 90 days.

---

## Recall (15 minutes)

Close everything. Write from memory:

1. Three ways budgets get set, and which is defensible.
2. Why "scale what works" fails, in terms of average vs marginal return.
3. What an incremental conversion is, and three ways to measure it.
4. The two places non-incremental spend hides, and why.
5. What MMM needs, one thing it is good at, one it is bad at.
6. The three legs of triangulation, ranked by trust.
7. The 60/40 heuristic and two conditions that shift it.

---

## If you remember one thing

**Attribution tells you what happened after a click; only a holdout tells you what would have happened without the ad.** Before you scale the channel with the best reported return, turn it off somewhere and find out what you actually bought.

---

**Next:** [M16 — B2B vs B2C and sales alignment](M16-b2b-vs-b2c.md)
