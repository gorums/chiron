# M10 — Paid Search: Google Ads

**Time:** 120 minutes (55 read · 50 exercise · 15 recall)
**Part 4 of 7 · Digital Core**

---

## Why this matters

Paid search is the purest demand capture (M01). Someone types what they want; you pay to be the answer. That makes it the fastest channel to revenue and the easiest to measure — which is why it is where the most money is quietly wasted. It looks like it works because the conversions land in the report. Whether they would have happened anyway is a different question, and it is the one that gets people promoted or fired.

---

## Core concepts

### The auction: you don't pay your bid

**Ad Rank** ≈ bid × ad quality (expected CTR, ad relevance, landing page experience) + expected impact of assets, filtered by context and rank thresholds. You then pay roughly the minimum needed to beat the advertiser below you.

Practically: a competitor with better ads and a better landing page outranks you while paying less. Quality is a discount, not a vanity score. **Quality Score** (1–10, keyword level) reports the same three components — treat it as a diagnostic. Low expected CTR means weak copy for that query; low ad relevance means query and ad don't match; low landing page experience usually means you dumped traffic on the homepage.

### Match types as they actually behave in 2026

- **Broad** — matched on meaning, not words. With smart bidding and real conversion data it can outperform tight matching. Without conversion tracking it is an incinerator.
- **Phrase** — the meaning of the phrase must be present. The workhorse.
- **Exact** — no longer exact. It matches "same meaning": plurals, synonyms, reordering. `[running shoes]` can serve "sneakers for jogging."

Nothing you buy is literal anymore. This is the key correction for anyone learning from pre-2021 material.

### Negatives are the real control surface

Because match types leak, **negative keywords are how you steer**. Three layers: an account-level list (free, jobs, torrent, competitor-review terms); campaign level (separate brand from non-brand so campaigns don't cannibalise); ad group level when intent splits ("hire" vs "buy").

The **search terms report** shows the queries that actually triggered your ads. Weekly for the first month, then biweekly. For each meaningful term: promote it, block it, or ignore it. Google hides some low-volume terms, so you will never see 100% — read spend concentration, not just the top rows.

### Structure in the automation era

Old advice: single-keyword ad groups, dozens of tiny campaigns. That is now harmful. Smart bidding needs conversion volume per campaign to learn, and splitting 40 conversions/month across 12 campaigns starves every one of them.

Modern default: **fewer, better-fed campaigns**, split only where you need separate budget or separate targets — brand vs non-brand, different CPA/ROAS goals, different geographies or languages.

### Responsive search ads and assets

RSAs are the only text format: up to 15 headlines, 4 descriptions, assembled by Google. Write **distinct** headlines, not 15 rewordings. Pin only for legal or brand requirements — heavy pinning cripples the system. Chase "Good"/"Excellent" Ad Strength but never trade away a strong claim for it; Ad Strength is a checklist, not a ranking factor. Run 2 RSAs per ad group.

**Assets** (formerly extensions) — sitelinks, callouts, structured snippets, call, lead form, image, price, promotion. More real estate and higher CTR at no extra cost. Missing sitelinks is the most common free money in a beginner account.

### Message match

Query, ad, and landing page headline should read as one continuous sentence. Someone searching "emergency plumber Dublin" who lands on "Welcome to our site" is a click you already paid for and wasted. Message match usually beats another 10% off your CPC.

### Bidding and the volume threshold

- **Manual CPC** — tiny accounts and diagnostics only.
- **Maximize clicks** — cold-start traffic gathering; always cap max CPC.
- **Maximize conversions** — no target, spends the budget hunting conversions. Sensible starting point.
- **Target CPA** — you name the price per conversion.
- **Target ROAS** — ecommerce, needs reliable revenue values.

Smart bidding needs roughly **30+ conversions per month per campaign** to be stable; tROAS wants more. Below that, use maximize conversions, or move the conversion action earlier in the funnel (qualified lead rather than closed deal) so there is signal. Good B2B accounts solve this by importing offline conversions back into Google Ads.

### Performance Max

PMax spans Search, Shopping, Display, YouTube, Gmail, Maps and Discover from one campaign. You supply budget, goal, asset groups, audience signals, and for ecommerce a product feed.

It works with a healthy feed and real conversion volume. It fails with thin data, lead-gen where lead quality isn't fed back, or when it simply harvests branded search and claims credit. Reporting is opaque by design — asset insights, not clean placement data.

Control it with: **brand exclusions** so it doesn't eat traffic you'd win free; **account-level negative keywords**; **separate asset groups** per category or persona so results are readable; **audience signals** (hints, not targeting — feed customer match and high-value site audiences); and **feed quality**, which for ecommerce *is* the targeting.

### AI Max for Search

A toggle on a Search campaign, not a new type. It extends matching beyond your keyword list using semantic understanding of queries and your landing pages, and can generate ad text. It finds queries you'd never have thought of, and queries you'd never have bought. Enable it only with tight negatives and a weekly search terms review, and judge it incrementally rather than by in-platform CPA.

### Branded search and the incrementality trap

Bidding on your own name shows a spectacular CPA. Most of it is not incremental — those people were arriving via the organic result below. Legitimate reasons: competitors bidding on you, a crowded SERP pushing you below the fold, message control, a fragile organic position. The test is easy and almost nobody runs it: pause brand in half your geographies for two weeks and watch *total* branded conversions, paid plus organic. Method in M15.

### Shopping and budget pacing

Standard Shopping is still worth running beside PMax for control and cleaner data — there are no keywords, so optimisation means titles, images, price competitiveness and feed attributes.

Daily budget × ~30.4 = the monthly cap; Google may overspend up to 2× on a day but not over the month. A campaign "limited by budget" while hitting target CPA is the easiest scaling decision in marketing. Raise budgets in 20–30% steps to avoid re-triggering learning.

---

## How it works in practice

**Computing max CPC.** Work backwards from the money. Target CPA €50, landing page converts clicks to leads at 4%:

Max CPC = target CPA × conversion rate = €50 × 0.04 = **€2.00**

If the auction demands €4, you have exactly three options: raise conversion rate (page, offer, form), raise what a conversion is worth (price, LTV, close rate), or don't run in this auction. There is no fourth, and "improve the ad copy" is a rounding error against a 2× gap. For ecommerce, extend one step: €2.00 CPC at 4% CVR means €50 cost per order, so contribution margin must exceed €50 before you even discuss ROAS targets.

**The diagnostic ladder.** When a campaign underperforms, go in order and stop at the first broken rung:

1. **Impressions** — showing at all? Budget, bids, approvals, targeting, search volume.
2. **CTR** — shown, not clicked. Copy, offer, position, intent mismatch.
3. **CPC** — clicked, too expensive. Quality Score, competition, match type, bid strategy.
4. **Landing page CVR** — clicks, no conversions. Message match, speed, form friction, trust (M07).
5. **The offer** — good page, still nothing. Price, proposition, or audience. Google Ads cannot fix this.

Beginners spend their week on rung 2. Most real problems live on rungs 4 and 5.

---

## 2026 reality check

- **Manual targeting is over; input quality is the job.** Your leverage is the conversion action you choose, the first-party data you feed, asset quality, and your negatives.
- **The SERP is more answer-shaped.** With ~60% of Google searches ending without a click and AI Overviews sharply cutting top-position organic CTR, paid results carry more of the click load — which argues for higher CPCs, not lower.
- **Chrome did not remove third-party cookies.** April 2025 confirmed they stay; October 2025 Google announced retirement of most Privacy Sandbox tech (Topics, Protected Audience, Attribution Reporting), deprecated in Chrome 144 and targeted for removal in Chrome 150. Your real constraints are GDPR/ePrivacy consent, Safari ITP, ad blockers and iOS ATT. Enhanced conversions and Consent Mode v2 patch those gaps.
- **Assume in-platform CPA is optimistic.** PMax and AI Max blur which query drove what. Validate with holdouts.

---

## Common mistakes

- **Sending all traffic to the homepage.** Kills message match and Quality Score at once.
- **Tracking the wrong event.** Optimising to "all form submits" when half are spam teaches the algorithm to find more spam.
- **Over-segmenting into SKAGs.** Starves smart bidding.
- **Ignoring the search terms report,** then discovering 30% of spend went somewhere irrelevant.
- **Judging PMax by its own report.** It grades its own homework.
- **Calling cheap branded CPA "performance."**
- **Changing bids and budgets daily.** Change one thing, then wait 1–2 weeks or ~30 conversions.

---

## Exercise (50 minutes)

Build a full campaign plan for **your chosen business**. Spend nothing.

1. **Structure.** Name campaigns and ad groups. Justify each split by budget or target, not tidiness. Include a brand campaign and state whether you would actually run it.
2. **20 keywords by intent.** Label each transactional ("buy", "near me", "pricing"), commercial investigation ("best", "vs", "alternatives"), or informational. Assign a match type and say why. Use Keyword Planner for volume and bid estimates.
3. **Negatives.** At least 15 terms across account and campaign level, including three you'd only find by imagining how broad match misfires.
4. **Three ad variants** for your highest-intent ad group: 8 distinct headlines, 3 descriptions, 4 sitelinks, 4 callouts. Write the landing page headline beside them and check the three read as one sentence.
5. **The math.** Target CPA (derive it from your M05 CAC ceiling), estimated landing page conversion rate, computed max CPC. Compare to Keyword Planner's top-of-page bids. If your max CPC is below market, name the three things you'd change and which you'd try first.
6. **Bidding plan.** Strategy at launch, the trigger to switch to tCPA, and the conversion volume needed to get there.

---

## Recall (15 minutes)

Close everything. Write from memory:

1. Ad Rank in words, and why a competitor can rank above you while paying less.
2. What "exact match" matches in 2026, and your main lever of control.
3. Why granular SKAG structures now hurt performance.
4. The max CPC formula, and your three options when market price exceeds it.
5. The five rungs of the diagnostic ladder, in order.
6. Two ways to control Performance Max.

---

## If you remember one thing

**Paid search rewards arithmetic before cleverness.** Compute the max CPC you can afford, decide whether the auction is winnable — and never let a channel's own report be your only evidence that it worked.

---

**Next:** [M11 — Paid social and creative](M11-paid-social-and-creative.md)
