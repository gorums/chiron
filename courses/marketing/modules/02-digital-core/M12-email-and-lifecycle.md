# M12 — Email and Lifecycle Marketing

**Time:** 90 minutes (40 read · 40 exercise · 10 recall)
**Part 6 of 7 · Digital Core**

---

## Why this matters

Every other channel is rented. Google changes the SERP, Meta changes the algorithm, TikTok changes what it promotes, and your traffic halves through no decision of yours. An email list is the only audience you own outright — a set of addresses you can reach without paying an intermediary for permission. For most ecommerce and subscription businesses, automated email flows produce a disproportionate share of channel revenue from a small fraction of sends. It is the highest-margin work in marketing and the least glamorous, which is why it is so often neglected.

---

## Core concepts

### Building the list without poisoning it

A list is only an asset if the people on it want to hear from you. Buying lists, pre-ticked consent boxes, and scraped addresses destroy deliverability for everyone on your domain, permanently.

The lead magnet rule that matters: **the magnet must be adjacent to the purchase, not merely popular.** A €50 Amazon voucher builds a list of people who want vouchers. A "20-point roof inspection checklist" builds a list of people who own roofs and are worried about them. Generic magnets produce big lists with near-zero revenue per recipient, and then the unengaged majority drags your sender reputation down. Optimise the magnet for buyer adjacency, then for volume.

Collection points that work: exit-intent and scroll-triggered popups with a real offer, checkout opt-in, post-purchase, content upgrades inside articles, webinars, and waitlists. Always capture the source in a field so you can segment by it later.

### The five flows that make most of the money

Automated **flows** (triggered by behaviour) beat **campaigns** (one-off broadcasts) on revenue per recipient because they arrive at the moment of relevance.

1. **Welcome / indoctrination** (3–5 emails). Deliver the promised thing immediately, then: who you are and why you exist, the strongest proof you have, the objection handler, and a first-purchase offer. This flow typically earns the most per recipient of anything you send.
2. **Abandoned cart and abandoned browse.** Cart: 3 emails at roughly 1 hour, 24 hours, 72 hours — remind, handle the objection (shipping, returns, sizing), then incentivise only if margin allows. Browse abandonment is softer and lower intent; treat it as a nudge, not a chase.
3. **Post-purchase / onboarding.** Order confirmation and shipping updates are the highest-open emails you will ever send — use them. For software, onboarding is where churn is decided: drive to the activation action, not to a feature tour.
4. **Winback.** Triggered at a defined lapse point (e.g. 2× the median purchase interval). Ask what changed, offer a reason to return, and set a hard exit: if they don't engage after 3 emails, suppress them. Sending forever to the dead is how you lose the inbox.
5. **Replenishment or upgrade.** Consumables: time the email to just before the product runs out. SaaS or services: trigger on usage thresholds that signal readiness for the next tier.

### Segmentation and RFM

Sending everything to everyone is what kills lists. The simplest durable framework is **RFM**: Recency, Frequency, Monetary value. Score customers on each, then treat the groups differently — champions get early access and referral asks, at-risk high-value customers get personal attention, one-time low-value buyers get a repeat-purchase nudge, and the never-engaged get a sunset sequence.

For non-transactional lists, segment by source, by engagement recency (opened or clicked in 30/60/90 days), and by declared interest.

### Personalisation that helps vs. creepy merge tags

Useful personalisation changes the *content*: showing the size they bought, the plan they're on, the city they're in when it affects delivery. Cosmetic personalisation — a first name pasted into a subject line — is neutral at best and actively unsettling when it's obviously automated ("Hi {FIRSTNAME},"). Personalise on behaviour you legitimately hold, and never demonstrate knowledge that will make someone uncomfortable about how you got it.

### Subject lines and preview text

Subject line and preview text are one unit — the preview should extend the subject, not repeat it or show "View in browser." Specific beats clever. Short and plain beats punctuation-heavy. Avoid full-caps, excessive emoji, and words that look like a shouting sale; they read as spam to humans and to filters. Test subject lines only when your list is large enough for the difference to be measurable (M14).

### Metrics, and which ones are now broken

- **Delivery rate** — accepted by the receiving server. Watch bounces; over ~2% hard bounces means a hygiene problem.
- **Open rate — unreliable since Apple Mail Privacy Protection.** MPP pre-fetches images for Apple Mail users, inflating opens and making them useless as an absolute measure and dangerous as an optimisation target. Use trend and relative comparison only, never as your headline number.
- **Click rate and click-to-open** — the first honest engagement signal.
- **Conversion rate and revenue per recipient (RPR)** — RPR is the number that lets you compare a flow to a campaign to a segment fairly. Make it your default.
- **Unsubscribe rate and spam complaint rate** — the real health metrics. A campaign with great revenue and a rising complaint rate is borrowing from next quarter.

### Deliverability fundamentals

Authentication is no longer optional. Gmail and Yahoo's bulk sender requirements (in force since 2024) mean you need:

- **SPF** — DNS record listing who may send for your domain.
- **DKIM** — cryptographic signature proving the message wasn't altered.
- **DMARC** — a published policy telling receivers what to do when SPF/DKIM fail, plus reporting. Effectively mandatory for bulk senders to Gmail and Yahoo.
- **One-click unsubscribe** in the header, honoured within two days.
- **Spam complaint rate kept under 0.3%**, ideally under 0.1%. Cross it and delivery collapses.

Beyond that: send from a subdomain (`mail.yourdomain.com`) so a mistake doesn't burn your corporate mail; warm new domains and IPs gradually; clean the list — remove hard bounces immediately and sunset subscribers with no opens or clicks in 6+ months even though it shrinks a number you like reporting. Reputation is behavioural: consistent volume, high engagement, low complaints.

### Consent and law

Under **GDPR/ePrivacy** you need freely given, specific, informed consent for marketing email in the EU/UK, with a record of when and how it was given, and easy withdrawal. Under **CAN-SPAM** (US) the bar is lower — accurate headers and sender identity, a physical postal address, a working unsubscribe honoured within 10 business days — but the deliverability consequences of behaving as if consent were optional are worse than the legal ones. Legitimate interest can cover some B2B sending in some jurisdictions; check locally rather than assuming.

### SMS and push

Higher open and response rates, far higher intrusiveness cost, and stricter consent rules (separate explicit opt-in, no implied consent from an email signup). Use SMS for time-critical, high-value moments only: delivery updates, appointment reminders, an abandoned cart at high basket value, a genuine deadline. One irrelevant 9pm text costs you the subscriber and possibly the customer. Push notifications follow the same logic with a lower cost per annoyance and a lower ceiling.

### Lifecycle mapping

Lifecycle marketing is simply: define the stages a customer moves through, define the transition you want at each stage, and put a triggered message at each transition. Stages for most businesses: unaware → subscriber → first purchase → repeat → advocate, with lapse and churn as exits. For each stage write the desired next action, the trigger, the message, and the suppression rule that stops someone receiving two competing sequences at once.

---

## How it works in practice

A weekly rhythm for a small business, roughly 2 hours:

- **Monday** — check the previous week's flows: revenue per recipient by flow, unsubscribes, complaint rate, bounce rate. Fix anything trending wrong before you write anything new.
- **Midweek** — build one campaign to a *segment*, not the whole list. Segment first, then write to that segment as if you were writing to one person in it.
- **Monthly** — one flow improvement. Add an email, rewrite the weakest one, change a delay, or fix a suppression rule. Flows compound; campaigns don't.
- **Quarterly** — list hygiene and a sunset sequence for the unengaged.

Tooling is mostly interchangeable: Klaviyo for ecommerce, Mailchimp or Brevo for small general lists, HubSpot or Customer.io for B2B lifecycle. Pick on the strength of segmentation and flow builders, not on template galleries.

---

## 2026 reality check

- **Open rates are decoration.** Apple Mail Privacy Protection broke them years ago and they have not recovered. Any advice, agency report, or tool that leads with open rate is out of date — judge on clicks, conversions and revenue per recipient.
- **Authentication is enforced, not advised.** Without SPF, DKIM and DMARC aligned, bulk mail to Gmail and Yahoo simply doesn't arrive reliably.
- **First-party email data got more valuable, not less.** As ad platforms lose browser signal to consent rules, Safari ITP, ad blockers and iOS ATT, hashed email is the identifier that still works — for customer match audiences, for CAPI matching, and for suppression lists. Your list is now an advertising asset as well as a channel.
- **AI writes competent email at zero cost,** which means competent email no longer stands out. Specificity, real customer language and a genuine offer do.

---

## Common mistakes

- **A generic lead magnet.** Big list, no buyers, degraded reputation.
- **Campaigns but no flows.** The flows are where the money is.
- **Blasting the whole list every time** because segmenting shrinks the send count.
- **Never removing anyone.** Unengaged subscribers actively suppress delivery to engaged ones.
- **Optimising subject lines for opens.** You are optimising a broken metric, and clickbait subject lines raise complaints.
- **No plain-text alternative, image-only emails.** They break, they look like spam, and they fail accessibility.
- **Treating unsubscribes as failure.** An unsubscribe is far better than a spam complaint. Make it easy.
- **Ignoring transactional emails.** The highest-attention messages you send, usually left at the platform default.

---

## Exercise (40 minutes)

For **your chosen business**:

1. **Lead magnet.** Write the magnet and one sentence explaining why it is adjacent to the purchase. Then write the alternative generic version, and state exactly what the difference would do to revenue per recipient.
2. **The welcome flow — 3 emails, written in full.** For each: trigger, delay, subject line, preview text, body, one call to action. Email 1 delivers the promise. Email 2 carries the strongest proof you actually have. Email 3 handles the biggest objection and makes the offer. Keep them shorter than feels comfortable.
3. **Lifecycle map.** Table it: stage, desired next action, trigger, message, suppression rule. Cover subscriber → first purchase → repeat → lapse, and mark which of the five flows sits at each transition.
4. **Metrics and health.** Define the three numbers you will report monthly (one of them revenue per recipient) and the two health limits that would make you stop sending — including your complaint-rate threshold.
5. **Deliverability check.** List whether SPF, DKIM and DMARC exist for the domain you'd send from, and what you'd fix first. If you don't have a domain yet, write the plan for the sending subdomain.

---

## Recall (10 minutes)

Close everything. Write from memory:

1. Why a lead magnet must be adjacent to the purchase.
2. The five flows and what each contains.
3. Why open rate is unreliable and what you use instead.
4. SPF, DKIM, DMARC — what each does, and the spam complaint threshold.
5. RFM, and one action for each of two RFM segments.
6. Why an unsubscribe is better than a spam complaint.

---

## If you remember one thing

**The list is the only audience you own — and you keep it by sending less to fewer people, more relevantly.** Flows beat campaigns; revenue per recipient beats open rate; complaint rate beats both as a warning.

---

**Next:** [M13 — Analytics and measurement](M13-analytics-and-measurement.md)
