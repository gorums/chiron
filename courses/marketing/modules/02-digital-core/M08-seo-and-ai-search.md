# M08 — SEO and AI Search (GEO/AEO)

**Time:** 150 minutes (60 read · 60 exercise · 30 recall)
**Part 2 of 6 · Digital core**

---

## Why this matters

SEO has the best long-run economics and the worst patience requirements: no cost per click, compounding results, and six to twelve months before you know if it worked. It is also being restructured underneath you. Roughly 60% of Google searches now end without a click to any external site, and when an AI Overview appears the click-through rate of the top organic result drops sharply — roughly halved, per SISTRIX data reported in 2026. Ranking first is no longer the same as getting the visit.

That does not make search less valuable. It moves the prize from *ranking* to *being the brand the answer names*.

---

## Core concepts

### How search engines work

Three stages, each a separate failure point.

1. **Crawl** — a bot fetches pages, following links and your sitemap. If it cannot reach a page, nothing else matters.
2. **Index** — the page is parsed, rendered, and stored. Google may crawl and decline to index ("Crawled – currently not indexed" in Search Console), usually judging the page low-value or duplicative.
3. **Rank** — indexed pages are ordered by hundreds of signals, dominated by relevance to intent, content quality, and off-site authority.

### How answer engines differ

ChatGPT, Perplexity, Gemini, Copilot, and Google's AI Overviews work as **retrieval + synthesis + citation**: the system pulls candidate passages (from an index, a live fetch, or training data), writes one answer, and cites a few sources. Three consequences:

- **Passages compete, not pages.** A well-structured 80-word answer inside your page can be lifted even if the page does not rank first.
- **One answer, not ten links.** Positions 2-10 lose most of their value; rewards became far more winner-take-all.
- **Citation is the unit.** Brands cited inside an AI Overview get materially more clicks than uncited competitors on the same query, and the citation carries brand value even with no click.

### The four pillars

- **Technical** — can it be crawled, indexed, rendered, and loaded fast.
- **Content** — does it satisfy the intent better than what currently ranks.
- **On-page** — is it structured so a machine can tell what it is about.
- **Off-page / authority** — do credible third parties link to and talk about you.

Beginners spend all their time on on-page because it is the only pillar you can complete in an afternoon. Authority is the hardest and usually the binding constraint.

### Keyword research done properly

Start with **intent classification**, because intent determines what page type can possibly rank:

- **Informational** — "how does payroll tax work." Wants an explanation; a product page cannot rank. Increasingly answered without a click.
- **Commercial investigation** — "best payroll software for contractors", "X vs Y", "X pricing". **The highest-value SEO territory in 2026**: high purchase intent, and answer engines lean heavily on comparison and review content.
- **Transactional** — "buy X", "X free trial". Wants to act.
- **Navigational** — "Xero login". Belongs to that brand; ignore.

Then evaluate on three axes, not one:

- **Volume** — tools estimate this badly. Treat it as an order of magnitude, not a number.
- **Difficulty** — who ranks now, and can you plausibly beat them. Judge from the actual SERP, not the tool's score.
- **Business value** — would this searcher ever buy? A 20,000-volume term that brings students is worth less than a 60-volume term that brings buyers.

**Long tail:** specific, multi-word, low-volume, high-intent queries. For a new site they are the entire viable strategy — twenty terms at 40 searches a month converting at 8% beat one term at 5,000 you will never rank for.

### SERP analysis and intent matching

Before writing anything, search the term and look at what Google is already rewarding: page type (listicle, product, forum, video), content depth, whether Reddit or YouTube dominates, whether an AI Overview appears and who it cites. **The SERP tells you what Google believes the intent is.** If nine results are comparison listicles, your product page will not rank there no matter how good it is. Match the format or pick a different query.

### On-page fundamentals

- **Title tag** — the strongest on-page element. Primary term near the front, written for a human to click.
- **One H1** matching the page's promise; H2/H3 mirroring the sub-questions people actually ask.
- **Internal links** — the most underused lever. Link from strong pages to the pages you want to rank, with descriptive anchor text. Free, fully under your control, and the fastest fix on most sites.
- **Structured data (schema.org)** — Organization, Product, FAQPage, Article, LocalBusiness, Review. No direct ranking boost, but it makes your entity and facts machine-readable, which matters more now that machines write the answer. Validate with Google's Rich Results Test.
- **Answer-first writing** — a direct, self-contained 40-80 word answer immediately under the heading that asks the question, then elaborate. That is what gets extracted.

### Technical basics

Indexation (Search Console's Pages report shows what is excluded and why), an accurate XML sitemap, a `robots.txt` blocking nothing important, correct canonicals on duplicate and parameterized URLs, a shallow structure putting important pages within three clicks of the homepage, and speed/Core Web Vitals (M07). Crawl with **Screaming Frog** (free to 500 URLs) for broken links, redirect chains, missing titles, and orphan pages.

Technical SEO is a floor, not a growth lever. Fix what is broken, then stop.

### Authority: links, PR, and why buying links is a bad trade

Backlinks from credible, topically relevant sites remain a strong signal. What earns them: original data, genuinely useful free tools, expert commentary journalists can quote, partnerships, and being the source others cite.

**Do not buy links** — the trade is bad economically, not just ethically. You pay recurring money for an asset one algorithm update can devalue, from networks selling to everyone including your competitors, with detectable footprints, and a manual action can remove your entire organic channel overnight. Negative expected value for any business planning to exist in three years. Guest posts on real publications with real audiences are a different thing; that is PR.

### E-E-A-T and entities

Experience, Expertise, Authoritativeness, Trustworthiness. Not a score Google assigns, but a description of what quality raters — and increasingly retrieval systems — look for. It matters most for money-and-health topics and, now, for whether an LLM treats you as a reliable entity.

Practically: named authors with real credentials, an About page saying who is behind the business, first-hand experience visible in the content ("we tested this on 40 accounts"), citations to primary sources, and **consistent entity information everywhere** — same business name, description, and founder names on your site, LinkedIn, Crunchbase, and directories. Answer engines assemble their picture of you from many sources; inconsistency makes you a fuzzy entity, and fuzzy entities do not get cited.

### Local SEO, briefly

If you serve a geography, **Google Business Profile** is the highest-return hour in this module. Complete every field, pick correct categories, post real photos, gather reviews steadily and reply to them. Keep NAP (name, address, phone) identical across your site and directories. Local pack rankings turn mostly on proximity, relevance, and review volume/recency.

### GEO / AEO: getting cited by answer engines

Answer/generative engine optimization is now a distinct discipline. What the evidence and practice point to:

- **Extractable answers.** Clear question-shaped headings with immediate, self-contained answers. Bulleted specifics. No 300-word preamble before the point.
- **Structured content and data.** Tables of specs, comparison tables, defined terms, schema markup. Synthesizers prefer content they can parse without inference.
- **Third-party mentions.** This is the big shift: **being talked about off-site now functions like a ranking signal.** LLMs assemble answers from a wide corpus, so mentions in listicles, review sites, industry publications, and directories affect whether you appear — even without a link. "Best X for Y" roundups that include you are now direct distribution.
- **Reviews and comparison content.** Answer engines lean on G2, Trustpilot, Capterra, and independent comparisons when a query has commercial intent. Being absent from those is being absent from the answer.
- **Reddit and YouTube.** Both are disproportionately retrieved. Reddit because it reads as authentic human experience; YouTube because it is transcribed and indexed. Genuine participation matters (M09); astroturfing gets you removed and does not survive moderation.
- **Consistent entity data**, as above.

**Measuring AI visibility.** Imperfect, but do it: pick 20-30 buyer queries, run them monthly across ChatGPT, Perplexity, Gemini, and Google AI Overviews, and log whether you are mentioned, cited with a link, or absent — and which competitors appear. That is your **share of answer**. In GA4 and Search Console, watch for the pattern of stable or rising impressions with falling clicks, which is the signature of answer-engine displacement. Referral traffic from `chatgpt.com` and `perplexity.ai` is small in volume and often high in intent; segment it.

**The strategic implication:** traffic-based SEO KPIs are dying. "Organic sessions" as a headline metric will keep falling for informational content even when your visibility improves. Report share of answer, branded search volume, and conversions from organic instead — and stop investing in thin informational content whose only job was to catch a click that no longer happens.

---

## How it works in practice

A realistic first 90 days on a small site:

1. **Week 1** — Set up and verify Google Search Console (free, non-negotiable). Crawl with Screaming Frog. Fix indexation blockers, broken links, missing titles.
2. **Weeks 2-3** — Build a keyword map: 20-40 terms grouped into topics, each with an intent, a target URL, and a page type taken from the SERP.
3. **Weeks 4-10** — Publish against commercial-intent terms first. Improve existing pages before writing new ones; moving a page from position 8 is faster than starting at zero.
4. **Ongoing** — Internal links from every new page to your money pages. Pursue mentions: directories, review platforms, roundups, podcasts, original data.
5. **Monthly** — Search Console query report plus your share-of-answer log.

Nothing meaningful happens before month three. Budget for that or do not start.

---

## 2026 reality check

- **Publishing volume is not a strategy.** AI made competent content free, so the supply of adequate articles is effectively infinite and worth near zero. Only content containing something unavailable elsewhere — proprietary data, real testing, named expertise, an actual opinion — earns links, citations, or trust.
- **Informational traffic is structurally declining.** If your model depended on ad revenue from "what is X" articles, it is in trouble. If it depended on reaching buyers, shift to commercial-intent and product-adjacent content.
- **SEO and PR merged.** The work that gets you cited by an LLM is the work that gets you mentioned by humans.
- **Do not buy an "AI SEO" tool before Search Console is configured and the keyword map exists.** The fundamentals did not change; the scoreboard did.

---

## Common mistakes

- **Chasing volume over intent.** Ranking for terms whose searchers will never buy.
- **Ignoring the SERP.** Writing a product page for a query where Google only shows listicles.
- **Publishing new pages while existing ones rot.** Refreshing usually beats creating.
- **Treating technical SEO as the whole job.** A perfectly crawlable site with nothing worth reading ranks for nothing.
- **Expecting results in six weeks**, then quitting at week ten, right before compounding starts.
- **Stuffing FAQ schema everywhere to "optimize for AI Overviews."** Citation follows genuine authority and clear answers, not markup tricks.
- **Reporting organic sessions in 2026** without explaining why the number falls while performance improves.

---

## Exercise (60 minutes)

**Part A — a 20-keyword map (35 min).** For **your chosen business**, build a table with these columns:

`Keyword | Intent (I/C/T/N) | Est. volume | Difficulty (from the actual SERP) | Business value 1-5 | SERP page type | AI Overview present? Who is cited? | Target URL | Have/Need`

Rules: at least 8 commercial-investigation terms, at least 8 long-tail terms, no navigational terms for other brands. Take volume from Google Keyword Planner or the free tiers of Ahrefs/Semrush, but verify every SERP by actually searching it. Sort by business value and rank the top five you would attack first, one line each on why you can win.

**Part B — one content brief (25 min).** For your top keyword, write a brief containing:

- Target keyword, intent, and the searcher's question in their own words
- What the top three ranking pages do, and what is missing from all of them
- Your angle — what only you can say (data, experience, customer stories)
- H1 and 5-8 H2s, each phrased as a question a buyer asks
- The 60-word answer-first paragraph for the top H2, written out in full
- Internal links in (which existing pages link here) and out (which money page this links to)
- Schema type, plus the proof elements: quotes, screenshots, numbers, author and credential
- What would make an answer engine cite this instead of the incumbent

---

## Recall (30 minutes)

Close everything. Write from memory:

1. Crawl / index / rank — and one failure mode for each
2. How answer engines differ from search engines, and the three consequences
3. The four SEO pillars, and which one is usually the constraint
4. The four intent types, and which one is most commercially valuable now
5. The three axes for evaluating a keyword
6. Why you read the SERP before writing
7. Four things that increase your odds of being cited by an AI answer engine
8. Why buying links is a bad trade, in economic rather than moral terms
9. What "share of answer" is and how you would measure it this month
10. The Search Console pattern that indicates answer-engine displacement

---

## If you remember one thing

**Ranking was the goal; being the cited answer is the goal now.** Write clear, extractable answers on commercial-intent topics, make your entity consistent and visible across the third-party sources machines read, and measure share of answer — not sessions.

---

**Next:** [M09 — Content marketing and organic social](M09-content-and-social.md)
