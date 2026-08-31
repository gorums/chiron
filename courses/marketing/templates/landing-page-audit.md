# Landing Page Audit — 25 Points

**Use with:** M07 — The digital ecosystem, websites and CRO
**Time to run:** 40 minutes per page
**Refill:** before any campaign that sends paid traffic to a page, and quarterly on your top three pages

Audit one page against one traffic source. The same page can be excellent for branded search and terrible for cold paid social, because message match is relative to where the visitor came from.

Before you start, write down:

- **Page URL:**
- **Traffic source being audited:**
- **What the visitor just clicked (ad headline / query / link text):**
- **The one action we want:**
- **Current conversion rate for this source:** ______ % over ______ sessions
- **Auditor and date:**

---

## Scoring method

Score each of the 25 points from 0 to 4:

| Score | Meaning |
|-------|---------|
| 0 | Absent or actively harmful |
| 1 | Present but poor |
| 2 | Adequate — a competent competitor does the same |
| 3 | Good — clearly better than the category norm |
| 4 | Excellent — a genuine advantage |

Maximum 100. Interpret as:

| Total | Read |
|-------|------|
| 0-40 | The page is the constraint. Do not spend more on traffic until it is rebuilt. |
| 41-60 | Fixable. Expect 30-80% conversion lift from the top five fixes. |
| 61-80 | Solid. Gains now come from testing, not from obvious repair. |
| 81-100 | Rare. Your leverage is elsewhere in the funnel — check `unit-economics-model.md` Part 6. |

Also record a **section score** (out of 20) per group. A page at 70/100 with Friction at 6/20 is not a "good page with a weak area"; it is a page with one broken thing that is costing you most of the conversions.

**Important:** the score is a diagnostic, not a target. Never optimise the score. Optimise the prioritised fixes it surfaces.

---

## Group A — Clarity (20 points)

Can a stranger, in five seconds, say what this is and who it is for?

| # | Point | What a 4 looks like | Score | Note |
|---|-------|---------------------|-------|------|
| A1 | The headline states what the thing is, not a mood | Names the product category and the outcome in plain words. No metaphor, no "Reimagine your workflow." | | |
| A2 | The subhead says who it is for and what changes | One sentence, names the segment or situation | | |
| A3 | The primary action is obvious and singular | One dominant button, repeated, same words each time | | |
| A4 | The page passes the five-second test with real people | 3 of 5 strangers can say what it does and who it's for | | |
| A5 | No unexplained jargon or internal product names above the fold | A first-time visitor needs no glossary | | |

**Section A score: ______ / 20**

**The five-second test:** show the page to five people who do not know the business, for five seconds, then ask "what do they sell and who is it for." Do this before you argue about button colours. It is the highest information-per-minute activity in all of CRO.

---

## Group B — Relevance and message match (20 points)

Does the page continue the sentence the ad or the query started?

| # | Point | What a 4 looks like | Score | Note |
|---|-------|---------------------|-------|------|
| B1 | Headline echoes the ad copy or the query | Literal word overlap with what they clicked | | |
| B2 | Visual continuity with the ad | Same image, colour, or person as the creative | | |
| B3 | The offer on the page is the offer in the ad | No bait and switch, no surprise "book a demo" | | |
| B4 | Page addresses the specific stage of intent | Cold traffic gets context; high-intent search gets the price and the button | | |
| B5 | One page per offer / audience where volume justifies it | Not one generic page absorbing six different campaigns | | |

**Section B score: ______ / 20**

Message match is the cheapest conversion win that exists. Making the H1 match the ad headline routinely moves paid conversion rates by double-digit percentages and takes ten minutes.

---

## Group C — Proof (20 points)

Trust is usually the real conversion bottleneck, especially for anything bought online without a conversation.

| # | Point | What a 4 looks like | Score | Note |
|---|-------|---------------------|-------|------|
| C1 | Specific, attributed social proof | Named customer, photo, role, and a number in the quote | | |
| C2 | Proof is near the decision points | Testimonial beside the form and the pricing, not in a carousel at the bottom | | |
| C3 | Third-party credibility | Review scores, certifications, press, membership bodies, real client logos | | |
| C4 | Objections are named and answered on the page | The top three anxieties from `icp-and-jtbd.md` addressed explicitly | | |
| C5 | Demonstration, not description | Screenshot, sample output, short video of the actual thing | | |

**Section C score: ______ / 20**

Ranked power of proof: the customer's own numbers > third-party data > named quote with photo > demonstration > your own claim with a statistic > unattributed praise. Unattributed praise ("Amazing service!" — J.) scores 1 at best; visitors discount it entirely.

---

## Group D — Friction (20 points)

Every field, click, and moment of doubt costs conversions.

| # | Point | What a 4 looks like | Score | Note |
|---|-------|---------------------|-------|------|
| D1 | Form asks only for what is needed to take the next step | Every field justified out loud; phone number optional or absent | | |
| D2 | Number of steps to complete the action | Counted and minimised; no account creation before value | | |
| D3 | Price or cost is discoverable | A number, a range, or an honest explanation of why there isn't one | | |
| D4 | Risk reversal is present and visible at the point of commitment | Guarantee, no card required, cancel anytime, data-deletion promise | | |
| D5 | No unnecessary interruptions | No exit popup on paid landing pages, no cookie wall covering the CTA, no chat widget obscuring the button on mobile | | |

**Section D score: ______ / 20**

Count your form fields right now and write the number here: ______. For a lead form, each field beyond the third typically costs conversions; the honest trade is fewer fields and more junk leads versus more fields and fewer, better leads. Decide deliberately with reference to your lead-to-customer rate, do not drift into it.

---

## Group E — Speed and technical (20 points)

| # | Point | What a 4 looks like | Score | Note |
|---|-------|---------------------|-------|------|
| E1 | Largest Contentful Paint on mobile | Under 2.5s on a real 4G test, measured in field data (CrUX), not lab | | |
| E2 | Interaction to Next Paint / layout stability | INP under 200ms, CLS under 0.1; nothing jumps as it loads | | |
| E3 | Mobile rendering and tap targets | CTA reachable with a thumb, no horizontal scroll, form usable one-handed | | |
| E4 | Conversion tracking verified end to end | A test submission produced a visible event in GA4 and in the ad platform, today | | |
| E5 | Correct indexing and URL hygiene | Canonical set, UTMs do not create duplicate pages, paid-only pages noindexed if appropriate, no broken links | | |

**Section E score: ______ / 20**

Tools: PageSpeed Insights for field data, Microsoft Clarity for session recordings and rage clicks, Chrome DevTools with mobile throttling, and Google Search Console for indexing. All free.

E4 fails more often than any other point on this sheet, and it is the only one that invalidates every other number in your account. Test it first, every time.

---

## Score summary

| Group | Score | /20 |
|-------|-------|-----|
| A — Clarity | | 20 |
| B — Relevance / message match | | 20 |
| C — Proof | | 20 |
| D — Friction | | 20 |
| E — Speed / technical | | 20 |
| **Total** | | **100** |

**Weakest group:** ______________

---

## Prioritised fixes

Sort by (expected impact ÷ effort). Do the top three before anything else. Do not queue twelve fixes; you will do none of them.

| Rank | Fix | Point ref | Effort (h) | Expected impact | Owner | Due | Result after |
|------|-----|-----------|------------|-----------------|-------|-----|--------------|
| 1 | | | | | | | |
| 2 | | | | | | | |
| 3 | | | | | | | |
| 4 | | | | | | | |
| 5 | | | | | | | |

**Filled example:**

| Rank | Fix | Ref | Effort | Expected impact | Owner | Due |
|------|-----|-----|--------|-----------------|-------|-----|
| 1 | Verify the form submission fires the GA4 key event and the Google Ads conversion; it currently fires on page load | E4 | 1h | Unknown but every optimisation decision is currently based on a wrong number | A. | Today |
| 2 | Rewrite H1 to match the ad headline ("Hand over the mess exactly as it is") | B1 | 0.5h | 10-25% CVR on paid traffic | A. | Thu |
| 3 | Cut form from 7 fields to 3 (name, email, trade) | D1 | 2h | 20-40% more submissions; watch lead quality as a guardrail | A. | Fri |
| 4 | Add the electrician video testimonial directly above the form | C2 | 3h | 5-15% | A. | Next week |
| 5 | Publish a price range on the page | D3 | 1h + a decision | Fewer, better leads; unknown net | Founder | Next week |

Note that rank 1 has unknown impact and is still first. Fix measurement before you fix anything you intend to measure.

Note also that fixes 3 and 5 have guardrails attached. Any change that increases volume by lowering commitment must be watched downstream, or you will celebrate a conversion-rate win that produced fewer customers.

---

## Re-audit

| Date | Total score | CVR before | CVR after | What actually moved it |
|------|-------------|------------|-----------|------------------------|
| | | | | |
| | | | | |

---

## What good looks like

The audit was done against one specific traffic source with the ad copy open in another tab. At least five strangers took the five-second test and their exact words are recorded in the notes column. Tracking was verified with a live test submission before anything else was judged. The output is three fixes with owners and dates, not a twenty-item wishlist, and the re-audit table gets filled in four weeks later with the actual conversion-rate change.

## Common failure

Auditing on a desktop monitor at full width, on fast wifi, with an ad blocker on, while already knowing what the product does. That combination hides almost every real problem: mobile layout, load time, cookie walls, and above all the fact that a stranger cannot tell what you sell. Open the page on your phone, on mobile data, and hand it to someone who has never heard of the business. That takes four minutes and beats the other thirty-six.
