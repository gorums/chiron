# M17 — Retention, Growth Loops, and LTV

**Time:** 60 minutes (25 read · 25 exercise · 10 recall)
**Part 4 of 6 · Expert Layer**

---

## Why this matters

Acquisition is rented. Every customer you buy, you buy again next month at a slightly higher price, because auctions get more competitive and the easy audience is exhausted first.

Retention is owned. A customer who stays gives you revenue with no acquisition cost, which raises LTV, which raises the CAC you can afford, which lets you outbid competitors for the same click. That is the whole strategic argument, and it is why the highest-leverage marketing work in most companies is not in the ad account.

It is also the argument nobody makes in the budget meeting, because retention improvements are slow, invisible to attribution, and belong to no single team.

---

## Core concepts

### Retention multiplies everything

Take a subscription at £50/month with 60% gross margin.

- **8% monthly churn** → lifetime 1 / 0.08 = **12.5 months** → LTV (gross profit) = £50 × 0.60 × 12.5 = **£375**
- **5% churn** → **20 months** → **£600**
- **3% churn** → **33.3 months** → **£1,000**

Cutting churn from 8% to 5% raised LTV by 60%. From 8% to 3% it nearly tripled it.

**Now convert that into acquisition power.** At a 3:1 LTV:CAC target, max CAC goes £125 → £200 → £333. At £375 LTV you cannot profitably buy a customer at £150; at £1,000 you can outbid almost everyone in your category, run channels competitors find unaffordable, and still hit payback. **A retention improvement is a weapon in the ad auction.**

Payback moves too. At 8% churn and £125 CAC, payback is £125 / £30 monthly gross profit = **4.2 months**. Halve churn and you can spend £250 and accept 8.3 months, if cash allows — which is now a financing question, not a marketing one.

Two cautions. `1 / churn` assumes a constant rate, which is wrong: churn is highest early and falls as cohorts mature, so simple LTV overstates for young cohorts. Use cohort curves for anything important. And LTV is only real if computed on **gross profit**, not revenue, and capped at a defensible horizon (24 or 36 months) rather than projected to infinity.

### Logo churn vs revenue churn

**Logo churn** counts customers lost; **revenue churn** counts money lost. The gap tells you which problem you have. Losing 5% of customers who were all on your cheapest plan might be 2% of revenue — a mix issue. Losing 2% who were your largest accounts might be 9%.

**Net revenue retention (NRR)** = (starting revenue − churn − contraction + expansion) / starting revenue. Above 100% means the existing base grows on its own: customers who stay and upgrade more than replace those who leave, so the business grows even acquiring nobody. Report gross retention alongside it, because expansion from a few big accounts can hide a leaky base.

For ecommerce the equivalents are **repeat purchase rate** and time between orders — same logic, different arithmetic.

### Cohort curves and what flattening means

Group customers by joining month and track what share is still active at months 1, 3, 6, 12. Never average across all customers; a growing company's average is dominated by new joiners, which hides everything.

**Does the curve flatten?** A curve that drops steeply then levels at, say, 35% means you have a durable core who genuinely need the product. That plateau is the real business, and growth compounds on top of it. A curve declining toward zero means there is no core — everyone eventually leaves, so you must acquire forever, faster, to stand still. **Finding out whether your curve flattens is the single most informative analysis in this module.**

**Are later cohorts above earlier ones?** January at month 3 at 30% and June at 42% means product or onboarding is improving. The reverse means something you did — a channel change, a promotion, a pricing move — is bringing in worse customers. Retention curves are also a channel-quality signal: cheap CAC with terrible month-3 retention is more expensive than it looks.

### Onboarding, time-to-value, activation

Most churn is decided in the first days, before any lifecycle email fires, because the customer never got the thing they came for.

**Time-to-value** is elapsed time from signup to first real benefit. Shortening it does more for retention than almost anything else: strip setup steps, provide templates and sample data, defer configuration, do the first bit of work for them.

**An activation metric** is the observable behaviour that predicts retention — imported contacts, invited a teammate, placed a second order. Find it by comparing what retained customers did in week one that churned ones did not. It must be causally plausible, not merely correlated; if the behaviour is a symptom of already-motivated users, pushing everyone toward it changes nothing.

Once you have it, activation rate becomes a leading indicator you can manage weekly, and it belongs at the top of your metric tree beside acquisition — exactly where most companies never put it.

### Growth loops vs funnels

A **funnel** is linear: money in the top, customers out the bottom. Output does not feed input, so when you stop spending, growth stops. A **loop** is circular: the output of one cycle becomes the input of the next, and each turn makes the next cheaper or larger.

- **Viral / referral loop.** Customer uses product → invites or shares → some convert → they invite others. Native where the product is shared (file sharing, collaboration, payment requests). Measured by the **viral coefficient (k)** = invites per user × conversion per invite. k above 1 is self-sustaining and rare; k of 0.3 is not viral but cuts effective CAC by roughly 30%, which is a serious result.
- **Content loop.** Publish → rank or get shared → attract users → users generate questions, reviews or data → that becomes more publishable material. Review platforms and marketplaces run on this.
- **Paid loop.** Spend → acquire customer → margin funds the next acquisition. It only compounds if payback is short enough that cash recycles inside your working-capital cycle. Most ecommerce runs on this, and its speed limit is payback period, not ROAS.
- **UGC loop.** Customers post → their audiences discover you → some buy and post. Fuelled by making the product remarkable, prompting at the right moment (post-delivery, post-result), and reposting contributors so posting is rewarded.
- **B2B word-of-mouth loop.** A customer succeeds → becomes a reference and case study → shortens the next deal's cycle and raises win rate.

Loops are slower to build and harder to attribute than campaigns. That is precisely why they are underbuilt, and why they are durable when they exist.

### Network effects are not the same as loops

A **loop** is a growth mechanism: usage produces more users. A **network effect** is a value mechanism: the product gets *better* for each user as more join (marketplaces, messaging, standards). Network effects usually create loops, but plenty of loops have no network effect — a content loop makes you bigger, not more useful per user. The distinction matters because network effects create defensibility while loops merely create efficiency. Do not claim one when you have the other.

### Referral programmes: what makes them work

- **The product is worth talking about.** A referral programme amplifies word of mouth; it cannot create it. If nobody recommends you unprompted, fix that first.
- **Double-sided reward,** so the sharer is doing a favour rather than collecting a bounty.
- **The reward matches the product's value.** Account credit works when the product is used repeatedly. Cash bounties attract people who want cash and produce customers who churn.
- **Asked at the moment of realised value** — after a good result or a successful delivery — not at signup, when the customer has nothing to vouch for.
- **Frictionless mechanics:** prefilled message, one link, works on mobile, credit applied automatically and visibly.
- **Measured on retained referred customers,** not shares. Referred customers frequently retain better than paid-acquired ones; that difference is the real return, and averaging hides it.

### Owned audiences compound

Email lists, SMS lists and communities are the assets you keep when a platform changes its algorithm or its prices. Reach is not free — deliverability, hygiene and consent all cost work (M12) — but it is not auctioned against competitors every time you use it. A list of 20,000 engaged subscribers can be activated for the cost of a send, repeatedly, for years; the same audience rented through paid social costs money every single time. Every acquisition campaign should therefore be judged not only on the sale but on whether it added someone to an audience you own.

### When retention beats acquisition

**Almost always, for subscription and repeat-purchase businesses.** If the cohort curve does not flatten, acquisition spend pours into a bucket with a hole; more spend just makes the hole busier.

**Less so for genuinely one-off, high-ticket purchases** — a wedding venue, a loft conversion. Nobody buys a second loft. There, "retention" is redefined as referrals, reviews, reputation and adjacent services, and acquisition remains the main engine.

**A rough decision rule.** Estimate the revenue effect of a realistic 20% relative churn improvement, and compare it to a realistic 20% increase in acquisition spend at current marginal returns (M15). For most subscription businesses past their first year, retention wins by a wide margin — and costs less, because it usually means product and onboarding work rather than media spend.

---

## How it works in practice

**Worked example.** A £45/month subscription, 65% gross margin, 7% monthly churn, CAC £160.

- Lifetime 14.3 months. LTV = £45 × 0.65 × 14.3 = **£418**. LTV:CAC = 2.6:1. Payback = £160 / £29.25 = **5.5 months**. Workable, not comfortable.
- Diagnosis: cohort analysis shows 41% of churn happens in the first 60 days, and customers who connect their calendar in week one retain at nearly twice the rate. Activation metric: calendar connected within 7 days. Current rate: 38%.
- Interventions: move the connection into the signup flow, add a one-click integration, send a day-2 nudge with a 90-second video, give human onboarding above a threshold. Activation reaches 55% over a quarter; churn falls 7% → 5.5%.
- New numbers: lifetime 18.2 months, LTV **£532** (+27%). At the same 2.6:1 ratio, affordable CAC rises to **£204**, with payback at that CAC of 7.0 months.
- What that buys: £204 CAC opens channels that were unaffordable at £160 — broader prospecting, higher-CPC keywords, sponsorships — while total customers grow both from lower churn and from more addressable acquisition. And it compounds, because every future cohort inherits it, which no ad optimisation ever does.

Nobody in the ad account produced that result. It came from one cohort analysis, one activation metric and three product changes.

---

## 2026 reality check

- **Rising acquisition costs make retention the arbitrage.** With buying automated (Performance Max, Advantage+), most competitors run similar algorithms against similar audiences, so targeting cleverness is largely gone as an edge. Being able to pay more per customer than your competitor is one of the few remaining structural advantages.
- **First-party data is now an input to the ad platforms, not just a mailing list.** Customer lists, offline conversion imports and value-based bidding signals are how you steer black boxes, so a well-maintained owned audience improves acquisition performance directly.
- **Zero-click search rewards direct relationships.** With ~60% of Google searches ending without a click and AI Overviews compressing organic CTR, audiences you can reach without an intermediary are worth more relative to rented reach than they were.
- **AI shortens time-to-value.** In-product assistance, automated setup and generated starting configurations genuinely reduce the gap between signup and first benefit — one of the clearer non-hype applications of AI to a growth problem (M18).

---

## Common mistakes

- **Reporting an average retention rate** instead of cohort curves, hiding every trend that matters.
- **Computing LTV on revenue instead of gross profit,** then over-spending on the strength of a number 40% too high.
- **Projecting LTV to infinity** on a constant-churn assumption.
- **Confusing logo and revenue churn** and misdiagnosing which customers you are losing.
- **Chasing a correlated activation metric** and pushing users toward a behaviour that never caused anything.
- **Launching a referral programme to fix bad word of mouth.**
- **Calling a referral programme a network effect.**
- **Discounting to reduce churn,** which retains price-sensitive customers and trains everyone to wait for the offer.
- **Treating retention as the product team's problem** and never bringing it to the budget meeting.
- **Ignoring payback in a paid loop** and running out of cash while profitable on paper.

---

## Exercise (25 minutes)

For **your chosen business**:

1. **Build a cohort table.** Six monthly cohorts, retention at months 1, 3 and 6 — real numbers if you have them, estimates if not. Answer in one sentence: does the curve flatten, and at what level?
2. **Churn to LTV to max CAC.** Compute current churn, average lifetime, LTV on gross profit, and max CAC at your chosen ratio. Recompute with a 25% relative churn improvement and state the change in max CAC and payback.
3. **Name your activation metric** — the specific first-week or first-order behaviour you believe predicts retention — and how you would test whether it is causal rather than correlated.
4. **Time-to-value audit.** List every step between signup and first real benefit. Cross out the unnecessary ones. Estimate the time saved.
5. **Design one loop** (viral, content, paid or UGC) as a numbered cycle where the last step feeds the first, and state the one number that determines whether it compounds — k, publishing rate, payback period or posting rate.
6. **The comparison.** In three sentences, argue which is worth more next quarter — a 20% churn improvement or 20% more acquisition spend — using your numbers from questions 2 and 5, and what would have to be true for the answer to flip.

---

## Recall (10 minutes)

Close everything. Write from memory:

1. Why a churn improvement raises the CAC you can afford, with the arithmetic.
2. Logo churn vs revenue churn, and what NRR above 100% means.
3. What a flattening cohort curve tells you and what a non-flattening one tells you.
4. Time-to-value and activation metric, and the trap in choosing an activation metric.
5. Four growth loops with one concrete example each.
6. A loop vs a network effect.
7. Three features of referral programmes that work.

---

## If you remember one thing

**Retention sets the price you can afford to pay for a customer.** Every point of churn you remove raises max CAC, opens channels your competitors cannot afford, and compounds across every future cohort — which no ad optimisation ever does.

---

**Next:** [M18 — The AI-native marketing stack](M18-ai-native-marketing.md)
