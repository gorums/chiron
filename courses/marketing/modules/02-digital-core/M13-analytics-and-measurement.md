# M13 — Analytics and Measurement

**Time:** 120 minutes (50 read · 55 exercise · 15 recall)
**Part 7 of 7 · Digital Core**

---

## Why this matters

This is the module that separates people who keep their jobs from people who don't.

Anyone can run a campaign. The person who survives the budget review is the one who can say what happened, what it cost, what it produced, and how confident they are — in language a CFO accepts. Marketers get fired for two things: not being able to explain their numbers, and confidently explaining numbers that turn out to be wrong. Both are measurement failures, not campaign failures.

---

## Core concepts

### One metric that matters, and the tree beneath it

Pick a single number that, if it moves, means the business is working. Then decompose it into the inputs you actually control. That decomposition is the **metric tree**, and it is the whole job.

Ecommerce: Revenue = Sessions × Conversion rate × Average order value. Each branch splits again — sessions by channel, conversion rate by device and landing page.

B2B: Pipeline = Leads × Qualification rate × Average deal size, with Leads = Traffic × Form conversion rate.

The tree tells you where a change came from. Revenue down 20% is not actionable. Revenue down 20% because mobile conversion rate fell from 2.1% to 1.4% after a checkout release is a ticket someone can pick up.

**Leading vs. lagging.** Revenue is lagging — it tells you about decisions already made. Leading indicators move first: trial starts, demo requests, add-to-carts, email signups, branded search volume. Manage on leading indicators, report on lagging ones.

**Vanity metrics** are numbers that only go up and connect to nothing: impressions, followers, page views, "reach." The test is simple — if the number doubled, would you do anything differently? If not, stop reporting it.

### The GA4 event model

Universal Analytics counted sessions and pageviews. GA4 counts **events**, each carrying **parameters**, and some events are marked as **key events** (previously "conversions"). A pageview is an event. A click is an event. A purchase is an event with parameters for value, currency and items.

Three things confuse newcomers:

- **There is no bounce rate as you knew it.** GA4 has engagement rate — its inverse, defined by engaged sessions (10+ seconds, a key event, or 2+ pageviews).
- **Sessions are counted differently** and GA4 numbers rarely match old UA numbers or your ad platforms. Stop trying to reconcile; use each tool for what it's good at.
- **Custom dimensions must be registered** before parameters show up in reports, and data can take 24–48 hours to appear.

Set up: define your key events explicitly (purchase, lead submit, qualified signup), assign values where you can, and build Explorations rather than fighting the standard reports. Link Google Ads and Search Console.

### Tag management, conceptually

**Google Tag Manager** is a container you install once. Inside it: **tags** (things that fire — GA4 events, ad pixels), **triggers** (when they fire — a click, a page view, a form submit), and **variables** (values they use — order total, page path). The point is that you can add and change tracking without a developer deploying code, and preview before publishing.

**Server-side tagging** moves the container to a server you control. Requests go to your domain, then on to Google, Meta and others. Benefits: fewer losses to ad blockers and browser restrictions, better control over what data leaves, faster pages. Costs: hosting, complexity, and a real ability to break things silently. Worth it above meaningful spend; premature below it.

### UTM parameters — discipline beats tooling

UTMs are query parameters on inbound links that tell your analytics where a visit came from. Nothing you buy compensates for using them sloppily.

```
?utm_source=facebook&utm_medium=paid_social&utm_campaign=2026-q3-spring-sale&utm_content=ugc-testimonial-v2&utm_term=broad-women-25-45
```

- **source** — the platform: `google`, `facebook`, `newsletter`, `partner-name`.
- **medium** — the channel type, from a fixed list: `cpc`, `paid_social`, `email`, `organic_social`, `affiliate`, `referral`, `display`.
- **campaign** — a named initiative with a date convention: `2026-q3-spring-sale`.
- **content** — the specific creative or link position.
- **term** — keyword or audience.

Rules that save you: **lowercase everything** (UTMs are case-sensitive, so `Facebook` and `facebook` become two rows); never UTM-tag internal links (it starts a new session and destroys attribution); keep a shared spreadsheet of allowed source/medium values; auto-tag Google Ads with GCLID rather than hand-writing UTMs. One person owning the convention is worth more than any attribution tool.

### The attribution problem, honestly

Attribution assigns credit for a conversion to touchpoints. Every method is wrong in a knowable direction:

- **Last-click** over-credits capture channels — branded search, retargeting, and anything that catches people already on their way in.
- **First-click** over-credits discovery and ignores what closed the deal.
- **View-through** over-credits display and video; an unseen impression counts as influence.
- **Walled gardens self-report.** Meta, Google and TikTok each claim the same conversion. Sum their reported conversions and you will exceed your actual order count, often substantially.

**GA4 now retains only three models:** data-driven attribution plus two last-click variants. First-click, linear, time-decay and position-based were removed in November 2023 and are not coming back. Anyone offering you a "position-based model in GA4" is working from stale material.

**Platform-reported conversions never sum to actual revenue.** This is not a bug to fix, it is a property of the system. The correct response is to treat platform numbers as *tactical signal* — useful for deciding which creative to kill — and never as the source of truth for what the channel earned.

**Self-reported attribution.** Add "How did you hear about us?" as an open or lightly-optioned field at checkout or on the lead form. It is directionally useful, catches podcast, word-of-mouth and offline exposure that no pixel sees, and takes an afternoon to implement. It is biased toward the most recent memorable touch, so use it alongside the platforms rather than instead of them. It is the most underrated measurement tool available to a small business.

### Data hygiene and noise

Filter internal traffic and known bots. Exclude your own IPs and staging domains. Add referral exclusions for payment gateways so a Stripe redirect doesn't reset the session source. Check that a key event fires exactly once per conversion — duplicate purchase events are the most common cause of impossible-looking ROAS.

Then: **do not react to noise.** A 15% week-on-week swing on 40 conversions is nothing. Before you change anything, ask how many conversions the difference is based on and whether a coin flip could have produced it (M14). Weekly numbers are for spotting breakage; monthly numbers are for decisions.

### Privacy and consent

You need a consent banner in the EU/UK, and **Consent Mode v2** to tell Google whether ad and analytics storage is permitted; without it, Google Ads audiences and conversion modelling degrade. Note what did *not* happen: Chrome kept third-party cookies (confirmed April 2025), and in October 2025 Google announced retirement of most Privacy Sandbox technologies — Topics, Protected Audience, Attribution Reporting — deprecated in Chrome 144 (January 2026) and targeted for removal in Chrome 150 (July 2026). GDPR and ePrivacy consent requirements are unchanged. So your data gaps come from consent rejections, Safari ITP, ad blockers and iOS ATT — not from a Chrome deprecation that never arrived. Plan for permanently incomplete data and measure accordingly.

---

## How it works in practice

**Reporting cadence.**

- **Daily** — only anomaly checks. Did tracking break? Is spend pacing?
- **Weekly** — channel-level spend, leads or orders, cost per outcome. Look for breakage and trends, not verdicts.
- **Monthly** — the decision meeting. What we spent, what it produced, what we learned, what changes.
- **Quarterly** — allocation and incrementality (M15).

**Writing a monthly report a non-marketer can act on.** One page, in this order:

1. **The headline number** vs. target and vs. last month, in currency.
2. **Three bullets: what happened and why.** Written in cause-and-effect sentences, not metric dumps.
3. **A channel table:** spend, outcomes, cost per outcome, change vs. last month.
4. **What we learned** — one or two things now known that weren't before.
5. **What we're changing next month,** with the expected effect.
6. **Confidence note** — where the numbers are shaky and why (platform double-counting, small sample, tracking gap).

If the reader cannot make a decision from page one, it is not a report, it is a data dump. Never present platform-reported ROAS without stating that the platforms collectively over-claim.

---

## 2026 reality check

- **Triangulation is the standard.** Three independent lenses: **MMM** for the portfolio view across all spend including offline, **incrementality testing** for causal ground truth, and **platform attribution** for tactical, in-flight signal. Senior decision-makers trust independent incrementality testing more than MMM or in-platform reporting — so the marketer who can run a clean holdout has more credibility than the one with the prettiest dashboard.
- **Branded search and retargeting are where non-incremental spend hides.** If you only ever check one thing for incrementality, check those two.
- **Attribution got simpler and less flexible.** Three GA4 models, more modelled data, more black boxes. Arguing about models is now a lower-value activity than running an experiment.
- **~60% of Google searches end without a click,** so a growing share of your influence is invisible to any click-based measurement. Zero-click exposure, AI Overviews and AI assistants all create demand that arrives later as direct or branded traffic. Watch branded search volume as a proxy.

---

## Common mistakes

- **Reporting metrics instead of decisions.** Nobody wants your dashboard; they want to know what to do.
- **Summing platform-reported conversions.** You will report more sales than the company made.
- **Reacting to weekly noise** and restarting learning phases every Monday.
- **No UTM convention,** so half your traffic sits in `(other)` and nothing can be reconstructed later.
- **Tracking everything and defining nothing.** Two hundred events, no agreed key event.
- **Confusing correlation with cause.** Spend went up, revenue went up — in Q4, when revenue always goes up.
- **Trusting last-click** and defunding the demand-creation channels that fed it.
- **Never checking that tracking still works.** A silently broken tag can cost a quarter.

---

## Exercise (55 minutes)

For **your chosen business**:

1. **Metric tree.** Define the one metric that matters, then decompose it two levels down. Mark each node leading or lagging, and circle the two nodes you can actually influence next month.
2. **Key events.** List the 3–6 events you would track in GA4, with parameters and assigned values. State which single one is the primary key event for optimisation, and why the others are not.
3. **UTM convention.** Write it as a one-page standard: allowed `medium` values (a closed list), the `campaign` naming pattern with a date convention, casing rules, and who owns the spreadsheet. Then write three correctly-formed example URLs — one paid social, one email, one partner link.
4. **Monthly report template.** Build the one-page format above and fill it with real numbers if you have them, plausible estimates if you don't. Include the confidence note — it is the part that makes people trust you.
5. **Self-reported attribution.** Write the exact question and answer options you would add at checkout or on the lead form. Keep it to one question.
6. **The honest paragraph.** Write, in five sentences a non-marketer would understand, what you can and cannot prove about your marketing, and what you would need to do to prove more.

---

## Recall (15 minutes)

Close everything. Write from memory:

1. The metric tree for your business, two levels deep.
2. Three ways GA4's model differs from Universal Analytics.
3. The five UTM parameters and two rules that prevent broken data.
4. What last-click over-credits, what view-through over-credits, and how many attribution models GA4 retains.
5. Why platform conversions never sum to actual revenue.
6. The three legs of measurement triangulation, and which one senior decision-makers trust most.

---

## If you remember one thing

**No single measurement method is true; the skill is knowing the direction each one lies in.** Report decisions rather than metrics, state your confidence out loud, and treat platform numbers as signal rather than truth.

Part 2 gave you the channels. Part 3 gives you the judgment to allocate across them — starting with how to run a test that will not lie to you, then M15, where incrementality testing and media mix modelling turn the honest uncertainty above into a defensible budget.

---

**Next:** [M14 — Experimentation and testing](../03-expert-layer/M14-experimentation.md)
