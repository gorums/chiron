# M07 — The Digital Ecosystem, Websites & CRO

**Time:** 120 minutes (50 read · 50 exercise · 20 recall)
**Part 2 of 6 · Digital core**

---

## Why this matters

Every channel in Part 2 ends at a page. If that page converts at 1% instead of 3%, you pay triple for every customer, and no amount of ad optimization recovers it. Conversion work is also the cheapest lever you own — no budget approval, no algorithm's cooperation required — which makes it the highest-leverage skill in this course relative to the time it takes to learn.

---

## Core concepts

### Owned, earned, paid — and why the distinction is strategic

- **Owned** — website, email list, product, customer database. You control it, it survives platform policy changes, and it appreciates.
- **Earned** — press, reviews, word of mouth, Reddit mentions, being cited by an AI answer engine. Credible, free, not directly controllable.
- **Paid** — ads. Instant, scalable, and it stops the moment you stop paying. You are renting attention.

The rule: **paid and earned should feed owned.** A campaign that generates sales but no email addresses, no reviews, and no returning-visitor cohort bought revenue without building an asset. Your social followers are not owned — platforms can throttle your reach to them tomorrow and repeatedly have. Your email list is.

### The website's actual job

A website is not a brochure. Three jobs, in order: **convert** the people you already paid to bring there; **answer** the questions that block a purchase — including for the AI answer engines that read your site to describe you to buyers (M08); and **prove** you are real, since trust, not persuasion, is usually the binding constraint.

### Site vs. landing page

A **website** serves many intents — browsing, research, support, credibility checks. Navigation is a feature. A **landing page** serves one intent from one traffic source with one action; navigation is usually a bug, because every extra link is an exit.

Use a **landing page** for paid traffic, a specific offer, message match with an ad, or testing variants without touching the main site. Use **site pages** when intent is exploratory or the traffic is organic search that expects depth — sending SEO traffic to a stripped landing page fails, because it has no internal links and nothing to rank for.

The common error is the reverse: sending cold paid traffic to a homepage. A homepage serves everyone, which means it persuades no one in particular.

### Anatomy of a landing page that converts

**Above the fold**, a visitor must answer three questions in about five seconds: what is this, is it for me, what do I do next.

- **Headline** — the outcome or specific claim, not a slogan. "Bookkeeping for UK contractors, done in 48 hours" beats "Financial clarity, delivered."
- **Subhead** — who it is for, and the one differentiator.
- **Visual** — the product in use or the result, not a stock photo of someone smiling at a laptop.
- **One primary action.** One. A second equally-weighted CTA reduces action on both; secondary options should look secondary.

**Message match and scent.** The ad promised something; the page must repeat that promise in near-identical words. "Information scent" is the visitor's confidence they are still on the trail toward what they wanted — break it and they bounce. Five ad angles need five headline variants, not one generic page. This is the most common fixable defect in paid campaigns.

**Social proof placement.** Proof works next to the doubt it answers, not in a carousel at the bottom nobody reaches. A quote about easy setup belongs beside the signup form; logos belong near the pricing. Specific and slightly awkward beats polished: "cut our close time from 9 days to 3" outperforms "Great service, highly recommend!"

**Objection handling.** List the real reasons people do not buy — price, switching cost, contract length, "will this work for my case", data security, refunds — and answer each on the page. An FAQ is not filler; it is the objection list. Read support tickets to get the real ones.

**Friction removal and form length.** Every field, forced account, and unexpected cost is a leak. Ask only for what you use *now*. Shorter forms raise conversion rate and lower lead quality, so the right length depends on your bottleneck: if reps are idle, shorten; if they are drowning in junk, add one qualifying question. If sales demands more fields, convert first and qualify on the next screen.

### Speed, Core Web Vitals, and mobile

Core Web Vitals are Google's three page-experience metrics: **LCP** (largest contentful paint — when main content appears, target under 2.5s), **INP** (interaction to next paint — responsiveness, under 200ms), **CLS** (cumulative layout shift — visual stability, under 0.1). A modest ranking factor and a large conversion factor: slow pages lose people before they read anything, and mobile ad traffic is the most impatient traffic you will buy.

Practical wins in order of payoff: compress and size images correctly (WebP/AVIF), lazy-load below-the-fold media, remove unused third-party scripts (chat widgets and tag managers are the usual offenders), preload the hero image and font. Measure with **PageSpeed Insights** using field data from real users, not only the lab score.

Most traffic is mobile. Design the mobile layout first. Check the CTA is thumb-reachable, the form does not trigger zoom, and the sticky header does not eat a third of the screen.

### Trust signals

Real address and a named human. Working phone or chat. Recognizable payment logos. HTTPS. Third-party reviews (G2, Trustpilot, Google) rather than only self-hosted quotes. Refund terms stated plainly. Compliance badges only if genuine. For anything strangers pay for upfront, trust signals are often worth more than copy improvements.

### Diagnosing conversion, in order

Do not redesign. Diagnose.

1. **Where do people leave?** In GA4, build a funnel exploration across the real path (landing → key page → form start → submit). Segment by device and traffic source — a "site problem" is often a mobile-only or single-campaign problem.
2. **What are they doing on the page?** Session replay and scroll/click heatmaps. **Microsoft Clarity** is free with no traffic cap and flags rage clicks and dead clicks; **Hotjar** and **PostHog** do the same with product analytics attached. Watch 15 replays of abandoned sessions — more informative than a week of dashboards.
3. **Where does the form die?** Form analytics: the last field touched before abandonment. It is nearly always one field — a phone number, a required company size, a bad validation error.
4. **What do the words say?** Read it as a first-time visitor and mark every sentence a skeptic would challenge.

Only then form a hypothesis and change one thing.

### Benchmarks, honestly

Published "average conversion rates" are close to useless as targets: they mix branded with cold traffic, wildly different price points, incompatible definitions of "conversion," and self-selected survey samples. Use them only to notice when you are wildly off — a 0.1% rate signals something broken. **Your real benchmark is your own page last month.**

---

## How it works in practice

A CRO cycle on a small site:

1. Pick the page with the most traffic × the worst conversion rate. You cannot learn from a page with 40 visits a month.
2. Watch replays and read the heatmap. Write down three specific observations.
3. Write hypotheses as: *Because [evidence], I believe [change] will [effect] measured by [metric].*
4. Rank by impact × confidence ÷ effort. Ship the top one.
5. If traffic is too low for a valid A/B test (M14 — usually true under a few hundred conversions a month), make the change and compare periods, accepting weaker evidence. Do not run a test you cannot power; you will read noise as truth.

---

## 2026 reality check

- **Your analytics undercount, permanently.** Google did *not* remove third-party cookies from Chrome — it confirmed in April 2025 they stay, then in October 2025 announced it was retiring most Privacy Sandbox technologies (Topics, Protected Audience, Attribution Reporting), deprecated in Chrome 144 (January 2026) and targeted for removal in Chrome 150 (July 2026). Ignore the 2023-era "cookieless future" advice. The real constraints are unchanged: **consent** (GDPR/ePrivacy) means a share of EU visitors is never measured, **Safari's ITP** truncates cookie lifetimes, and **ad blockers** remove more. Server-side tagging and consent mode help; nothing makes it exact.
- **AI answer engines read your pages.** Clear headings, plain answers, and structured data now affect how you are described to a buyer who never visits (M08).
- **AI makes page production nearly free**, so the differentiator is a specific offer and real proof, not more pages. Generated pages full of generic reassurance convert badly and always have.

---

## Common mistakes

- **Redesigning instead of diagnosing.** A redesign changes 50 variables at once, so you learn nothing and often lose conversions you had.
- **Testing button colors.** Micro-tests on low-traffic sites waste months. Test offers, headlines, page structure, form length — things big enough to detect.
- **Homepage as landing page** for cold paid traffic.
- **Stacking a chat widget, popup, cookie banner, and review carousel**, then wondering why mobile LCP is 6 seconds.
- **Optimizing the page when the offer is wrong.** If nobody wants it at that price, no layout fixes it (M01, M04).
- **Trusting a "winning" test that ran four days.** Weekday and weekend buyers differ; run full weeks.
- **Copying a competitor's page.** You cannot see their conversion rate. They may be losing money elegantly.

---

## Exercise (50 minutes)

Pick a real landing page for **your chosen business** — yours, or a direct competitor's if you have none. Open it on a phone as well as a desktop.

**Part A — audit (25 min).** Score each item Pass / Weak / Fail, with one sentence of evidence:

1. Can you tell what it is, who it is for, and what to do in five seconds?
2. Is there exactly one primary action?
3. Does the headline match the promise of the ad or link that would send traffic here?
4. Is there proof, and is it placed next to the relevant doubt?
5. Are the top three buyer objections answered on the page?
6. How many form fields, and is each one used immediately?
7. Are pricing and terms findable without contacting anyone?
8. Run PageSpeed Insights on the mobile URL. Record LCP, INP, CLS.
9. On mobile, is the primary CTA visible without scrolling past two screens?
10. What trust signals exist? What would a suspicious first-time buyer still be worried about?

**Part B — five prioritized fixes (25 min).** Write five fixes, each with:
- The evidence from your audit
- The hypothesis in the format: *Because [evidence], I believe [change] will [effect] measured by [metric]*
- Effort (hours) and your confidence (low/med/high)

Then rank them. If you have access to the site, install **Microsoft Clarity** (free) before you change anything, so you have a baseline of replays.

---

## Recall (20 minutes)

Close everything. Write from memory:

1. Owned vs. earned vs. paid, with two examples of each, and the rule connecting them
2. Three situations that call for a landing page rather than a site page
3. The three questions a visitor must answer above the fold
4. What "message match" means and why it breaks paid campaigns
5. The three Core Web Vitals and roughly what each measures
6. The four-step conversion diagnosis order
7. Why published conversion benchmarks are close to useless
8. The form-length trade-off, and what determines the right answer

---

## If you remember one thing

**Diagnose before you change, and change the biggest thing you can measure.** Watch ten session replays before you touch a pixel — the problem is almost never the one you assumed, and it is usually the offer, the message match, or the form, not the design.

---

**Next:** [M08 — SEO and AI search (GEO/AEO)](M08-seo-and-ai-search.md)
