# M11 — Paid Social and Creative

**Time:** 120 minutes (55 read · 50 exercise · 15 recall)
**Part 5 of 7 · Digital Core**

---

## Why this matters

Search waits for intent. Paid social interrupts people who weren't looking for you, which makes it the main scalable way to *create* demand (M01) rather than harvest it. It is also the channel where the platform has taken almost every decision away from you except one: what the ad says and shows. If you learn only one skill here, learn to brief and judge creative — that is now the actual targeting mechanism.

---

## Core concepts

### Interruption vs. intent

On Google you buy a query. On Meta, TikTok, or YouTube you buy attention from someone mid-scroll. Consequences: conversion rates are lower, CPMs are cheaper, and the ad has to do the work that the search query did for free — establish that a problem exists, that it's theirs, and that you solve it. This is why paid social copy is longer and more emotional than search copy, and why "we ran ads and nobody converted" is usually a creative failure, not a targeting failure.

### Creative is the targeting

Meta's Advantage+ Audience and broad targeting mean the delivery system decides who sees the ad. It decides largely by watching who responds to *this specific creative*. A founder-to-camera ad about back pain finds people with back pain. A slick brand film finds people who like slick brand films.

The practical rule: you no longer narrow the audience with checkboxes, you narrow it with the hook. Detailed interest targeting still exists but in many verticals it now underperforms broad, and Meta has consolidated much of it away.

### Meta campaign structure

Three levels:

- **Campaign** — objective and budget strategy. The objective choice is the single highest-leverage setting in the account. Choosing "Traffic" when you want purchases tells the system to find cheap clickers, and it will. Pick the objective that matches the outcome you actually want (Sales, Leads, App Promotion, Awareness, Engagement).
- **Ad set** — budget, audience, placements, optimisation event. Optimise for the deepest event you have enough volume for.
- **Ad** — the creative.

**Advantage+ Shopping Campaigns** (now largely folded into the standard Sales objective as Advantage+ features) automate audience, placement, and creative permutation. For most ecommerce accounts, one broad, well-fed campaign beats a hand-built structure.

### The learning phase

A new ad set enters learning and needs roughly **50 optimisation events in 7 days** to exit. Under that it stays in "Learning limited" and delivery is erratic and expensive. This is why over-segmenting kills performance: four ad sets at €25/day each will each fail to reach 50 events, where one ad set at €100/day would. Significant edits (budget change over ~20%, new creative, changed optimisation event) restart learning. Consolidate budget; use Advantage campaign budget rather than per-ad-set budgets unless you have a reason.

### Signal quality: CAPI and first-party data

The browser pixel alone loses a large share of events to ad blockers, Safari's ITP, and iOS ATT opt-outs. The **Conversions API** sends events server-side from your backend, matched to users by hashed email, phone, click ID and other parameters. Better matching means better attribution *and* better optimisation, because the algorithm learns from more complete data.

What to do: run pixel + CAPI together with deduplication via a shared `event_id`; pass rich customer parameters; upload customer lists for Advantage+ and exclusions; watch the Event Match Quality score. Signal quality is now a bigger performance lever than bid tinkering.

### Creative strategy

**The first 2 seconds decide everything.** If the hook fails, nothing else in the ad exists. Hooks that work: a specific claim, a visible problem, a pattern interrupt, a direct callout of who it's for ("If you rent in Dublin…").

Formats that consistently perform:

- **UGC / creator-style** — feels native, cheap to produce, works cold.
- **Testimonial** — someone like the viewer saying it worked.
- **Demo** — the product doing the thing, filmed plainly.
- **Founder-to-camera** — credibility and specificity; strong for new brands.
- **Problem–agitate–solve** — the reliable direct-response skeleton.
- **Listicle / "3 reasons"** — high information density, holds attention.
- **Static image and carousel** — cheap, fast to iterate, still wins in many B2B and considered-purchase categories. Do not assume video always beats static; test it.

**Test concepts, not colours.** The hierarchy is **concept → angle → format → variation**. A concept is a whole idea ("the ad is a customer complaint about our competitor"). An angle is the argument (speed vs. price vs. status). A format is the execution (UGC vs. demo). A variation is the thumbnail, the caption, the button. Variations produce small differences; concepts produce the outliers that carry the account. Spend your testing budget high in the hierarchy.

**Fatigue and refresh.** Performance decays as frequency climbs within a saturating audience. Watch for rising CPM and falling CTR on the same ad. At small budgets a winner can last months; at high spend, plan a meaningful new concept every 2–4 weeks and treat 3–5 fresh concepts per month as a baseline production rate.

**Briefing creative properly.** A usable brief names: the audience and their belief before seeing the ad, the one thing they should believe after, the hook line, the proof, the offer, the call to action, format and duration, and the specific thing being tested. "Make it pop" is not a brief.

### Platforms in brief

- **Meta** — broadest reach, best optimisation, the default starting point for most B2C and much SMB B2B.
- **TikTok** — creative-led discovery; native, unpolished content wins; production speed matters more than production value.
- **YouTube** — reach and demand creation at scale, strong for explaining a considered product; buy through Google Ads, often alongside PMax.
- **LinkedIn** — expensive CPMs but precise firmographic targeting (title, seniority, company size, company list). Worth it only where deal value is high; lead gen forms convert well.
- **Reddit** — cheap attention, community-sensitive, works when the ad reads like a participant rather than a brand.

### Retargeting, frequency, and incrementality

Retargeting reports beautiful ROAS and is the most over-credited spend in most accounts: you are paying to reach people who already visited, many of whom would have returned anyway. It is where non-incremental spend hides, alongside branded search. Keep it, cap it, and size it honestly — a common failure is a retargeting budget large enough that the same 4,000 people see the ad ten times a week.

Sensible frequency: roughly 1–3 per week for prospecting; retargeting windows tightened to the actual consideration cycle (7 days for impulse purchases, 30–90 for considered ones). Prove the value with a geo or audience holdout (M15), not with the platform's ROAS column.

---

## How it works in practice

**How CPM × CTR × CVR determines CPA.** Only three numbers matter, and every optimisation is one of them.

- CPM €10 → 1,000 impressions cost €10.
- CTR 1% → 10 clicks, so CPC = €1.00.
- Landing page CVR 3% → 0.3 conversions from those 10 clicks.
- CPA = €10 / 0.3 = **€33**.

Now double CTR to 2% — better creative, nothing else changes: 20 clicks, 0.6 conversions, CPA = **€17**. Creative quality halved your customer acquisition cost without touching targeting or bids.

Alternatively hold CTR and lift landing page CVR from 3% to 5%: 0.5 conversions, CPA = **€20**. This is why M07 (CRO) and M11 are the same problem viewed from two ends.

**Reading the funnel metrics.** CPM tells you how expensive the audience and how competitive the auction. CTR tells you whether the creative earns the click. CVR tells you whether the page and offer deliver. For video, three more: **hook rate** (3-second views ÷ impressions — did the opening stop them), **hold rate** (thru-plays or 15-second views ÷ 3-second views — did it keep them), and **thumbstop**, used loosely for the same stopping power. A high hook rate with low hold rate means a clickbait opening the ad can't pay off. A low hook rate means the first frame failed and nothing downstream is diagnosable yet.

---

## 2026 reality check

- **Advantage+ made manual detailed targeting largely obsolete** in many verticals. Your job moved upstream: creative, offer, first-party data signals, and the optimisation goal you choose.
- **Chrome kept third-party cookies** (confirmed April 2025), and Google retired most Privacy Sandbox technologies in October 2025. The constraints that actually degrade your social tracking are consent requirements, Safari ITP, ad blockers, and iOS ATT — which is exactly why server-side CAPI matters and why it isn't going away.
- **AI generation collapsed production cost, not judgment cost.** You can produce fifty variations in an afternoon. Deciding which five concepts are worth producing is the skill that still pays.
- **Attribution windows lie in your favour.** Platform-reported ROAS is self-reported and double-counted across platforms. Triangulate (M15).

---

## Common mistakes

- **Choosing the wrong objective** and then blaming the creative.
- **Splitting budget across many small ad sets,** guaranteeing permanent learning limited status.
- **Testing colours and button text** while never testing a genuinely different idea.
- **Killing ads after one day.** You need enough conversions to distinguish signal from noise (M14).
- **Judging creative by internal taste.** The team hates the ad that works. This happens constantly.
- **Running pixel only, no CAPI.** You are optimising on partial data and blaming the algorithm.
- **Uncapped retargeting** — high reported ROAS, low real incrementality, annoyed audience.
- **Reusing your TV-style brand film as a performance ad.** Wrong pacing, no hook, no offer.

---

## Exercise (50 minutes)

For **your chosen business**:

1. **Five creative concepts, genuinely distinct angles.** For each, write: the audience, the belief before, the belief after, the hook line (the literal first sentence or first visual), the format, the proof element, and the CTA. Concepts must differ at the idea level — five UGC videos with different scripts is one concept, not five.
2. **The test plan.** Which concept is the control, what budget and duration, what optimisation event, and what minimum number of conversions you need before you'll judge anything. State in advance the metric that decides the winner, and the kill criterion for a loser.
3. **The math.** Estimate CPM, CTR and landing page CVR for your category, compute expected CPA, and compare it to your CAC ceiling from M05. If the math doesn't work, write which of the three numbers has to move and by how much.
4. **One brief.** Write the full creative brief for your strongest concept, in the format above, as if handing it to someone else to produce.
5. **Signal setup.** List the events you would send server-side and the customer parameters you would pass. Note what you cannot collect under consent rules.

---

## Recall (15 minutes)

Close everything. Write from memory:

1. Why creative is now the targeting mechanism.
2. The learning phase threshold and why over-segmenting budget breaks it.
3. The concept/angle/format/variation hierarchy, and where testing budget belongs.
4. The CPM × CTR × CVR chain, and what doubling CTR does to CPA.
5. Hook rate vs. hold rate, and what a high hook / low hold pattern tells you.
6. Why retargeting ROAS overstates its value.

---

## If you remember one thing

**On paid social you are not buying an audience, you are buying attention with an idea — and the idea decides who shows up.** Fix the hook before you touch the targeting.

---

**Next:** [M12 — Email and lifecycle marketing](M12-email-and-lifecycle.md)
