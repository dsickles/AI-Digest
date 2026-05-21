# Feature Research

**Domain:** Personal weekly AI news/information digest (web dashboard)
**Researched:** 2026-05-21
**Confidence:** HIGH (product pages, official docs, and blog posts verified; some third-party roundups used for triangulation only)

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels incomplete.

| Feature | Why Expected | Complexity | Notes | v1 Status |
|---------|--------------|------------|-------|-----------|
| **Concise per-item summaries with links to originals** | Every product studied (TLDR AI, Ben's Bites, AI Breakfast, Last Week in AI, Refind, Particle) pairs a short summary with a tap-through to the source. Summaries without links feel like plagiarism and break verification. | LOW | Render title + 2–4 sentence summary + canonical URL on every item. | **Gap** — implied by digest UX but not listed in Active Requirements |
| **Source attribution per item** | Readers need to know *where* a story came from (Substack name, YouTube channel, subreddit). Feedly, Inoreader, Readwise, and all newsletters show source/publisher metadata inline. | LOW | Show publisher name, favicon, and content type (article / video / thread). | **Gap** — not explicit in PROJECT.md |
| **Publication date on each item** | RSS readers and newsletters anchor items in time ("May 20 • AI Breakfast"). Without dates, archive browsing and "what happened this week" lose meaning. | LOW | Store and display `published_at` from feed/API metadata. | **Gap** — week-range header exists; per-item dates not specified |
| **Multi-format ingestion (RSS, email, video, forums)** | Personal AI digest users follow blogs, Substacks, YouTube, newsletters, and Reddit/HN. Matter and Readwise Reader both support RSS + newsletter email forwarding + saved articles; Miniflux supports RSS/Atom/JSON + YouTube playback. | MEDIUM | v1 covers RSS, YouTube (transcripts), Reddit/HN, email→RSS bridge. | **Covered** |
| **Reliable scheduled delivery cadence** | TLDR AI (daily), AI Breakfast (3× weekly), Import AI and Last Week in AI (weekly) all ship on predictable schedules. Missing an edition breaks trust. | MEDIUM | Weekly pipeline finishing before Sunday morning. | **Covered** |
| **Browseable archive of past editions** | Last Week in AI (`lastweekin.ai/archive`), AI Breakfast, Import AI (`jack-clark.net`), and Ben's Bites ("view past issues") all expose historical issues. | LOW–MEDIUM | Full archive by week range. | **Covered** |
| **Topic or section organization** | TLDR splits into AI / Tech / Data / Design / Programming. Refind and Particle organize by followed topics. Unstructured firehose feels broken at 15–40 sources. | MEDIUM | Four topic tabs + Briefing landing. | **Covered** |
| **Scannable ranked list on landing page** | Reference dashboard and newsletters (Ben's Bites "pick what interests you", Refind "5 links manageable") assume a curated top list, not equal-weight chronological dump. | MEDIUM | Briefing Top N + ranked numbering. | **Covered** |
| **Resilience when a source fails** | RSS readers (Miniflux, FreshRSS, Inoreader) skip bad feeds and continue. Automated pipeline must not abort on one broken URL. | MEDIUM | Per-source error isolation. | **Covered** |
| **Dedupe / collapse same story from multiple sources** | Particle clusters 100+ articles into one "Story"; Feedly AI Feeds dedupe by topic. With 15–40 overlapping AI sources, the same GPT release appears everywhere. Without dedupe, ranked lists feel repetitive. | MEDIUM–HIGH | Needs URL normalization + title/entity similarity or LLM clustering. | **Gap** — not in PROJECT.md; high impact at source-list scale |
| **Dark/readable typography for long reads** | Reference is dark-themed dashboard. Miniflux offers dark themes; Matter/Readwise optimize reading view. | LOW | Dark-themed dashboard. | **Covered** |

### Differentiators (Competitive Advantage)

Features that set products apart. Not required, but valuable.

| Feature | Value Proposition | Complexity | Notes | v1 Status |
|---------|-------------------|------------|-------|-----------|
| **Weekly narrative roll-up ("editor's note")** | Import AI and Last Week in AI succeed via editorial framing, not just link lists. Refind "Weekend Edition" synthesizes the week. Aligns directly with Core Value: "coherent narrative of what happened." | MEDIUM | Depends on per-item summaries + categorization completing first. | **Covered** — key differentiator |
| **LLM auto-categorization into personal topic lenses** | Generic AI newsletters (TLDR) use fixed sections. A personal digest with edtech/business/technical/design tabs mirrors how the user actually thinks about AI — closer to custom Refind topic follows than mass-market TLDR. | MEDIUM | Requires stable taxonomy prompt + fallback for ambiguous items. | **Covered** |
| **Automated ranking / "Briefing" curation** | Ben's Bites and Refind surface "best" items so readers don't triage 200 links. Ranking is the automation that replaces manual curation. | MEDIUM–HIGH | Depends on summaries + optional cross-item relevance scoring. | **Covered** |
| **Rich multi-sentence summaries (not one-liners)** | Import AI's depth and the reference dashboard's numbered stories with paragraph summaries beat TLDR's byte-sized blurbs for a "Sunday morning read." | MEDIUM | LLM cost driver; needs token budget per item. | **Covered** (per-item TL;DR) |
| **YouTube + forum ingestion in same digest** | Most newsletters are link-only. Last Week in AI covers news + podcast; Readwise ingests RSS + Twitter Lists + newsletters. Surfacing video transcripts and HN/Reddit threads inside topic tabs is uncommon. | HIGH | YouTube transcript fetch + Reddit/HN parsing add pipeline complexity. | **Covered** |
| **Full archive as personal newspaper morgue** | Cheaper than Re-readers' highlight libraries for "what happened in March?" Use case. | LOW | Static site generation or DB-backed archive pages. | **Covered** |
| **On-demand AI Q&A / chat over content** | Feedly Ask AI (synthesize 25 articles), Readwise Ghostreader chat, Particle story chatbot, Matter Co-Reader (Perplexity). Powerful but shifts product from "read digest" to "research tool." | HIGH | — | **Correctly deferred** (Out of Scope: Q&A chat) |
| **Multi-perspective / bias spectrum views** | Particle "Opposite Sides" and political spectrum charts. Valuable for general news; odd fit for personal AI/tech sources that aren't politically polarized. | HIGH | — | **Correctly deferred** |
| **Audio / TTS playback** | Refind Premium audio, Matter human-like TTS, Particle audio summaries. Great for commute; not core to dashboard "Sunday read." | MEDIUM | — | **Correctly deferred** (v2 consideration) |
| **Highlighting + second-brain export** | Readwise → Readwise highlights, Matter highlights, Wallabag tags. Knowledge capture, not digest consumption. | MEDIUM | — | **Correctly deferred** |
| **Community curation (vote/submit)** | Ben's Bites News feed: users vote/comment/submit; best posts enter digest. Social layer for mass newsletter, not single-user tool. | HIGH | — | **Correctly deferred** |
| **Intelligence reports / bulk synthesis UI** | Inoreader Intelligence reports: select N articles → run prompt → save report. Overlaps with weekly roll-up but as interactive ad-hoc tool. | MEDIUM | Weekly roll-up covers batch synthesis for v1. | **Correctly deferred** |
| **KPI / big-number headline strip** | Reference dashboard feature. Particle extracts quotes and facts. Adds extraction prompt chain for marginal gain when narrative roll-up exists. | MEDIUM | — | **Correctly deferred** (Out of Scope) |
| **Personalized recommendation algorithm** | Refind and Particle learn from swipes/clicks. v1 uses fixed sources + LLM rank — intentional for one user. | HIGH | — | **Correctly deferred** |
| **Podcast episode transcription** | Matter manual podcast transcript; Inoreader podcast summaries (2025). High cost/latency for weekly batch. | HIGH | — | **Correctly deferred** (Out of Scope) |
| **Search across archive** | Inoreader, Matter, FreshRSS, Wallabag all offer full-text search. "Browse by date" alone is weaker for "find that Claude article from February." | MEDIUM | Worth v1.x if archive grows. | **Gap** — deferred but high QoL |
| **Pipeline observability (cost + source health dashboard)** | Inoreader token usage tracking; self-hosted tools show feed errors. PROJECT.md requires bounded cost but not a UI for it. | LOW–MEDIUM | Logs/metrics sufficient for v1; UI nice later. | **Partial** — ops requirement without presentation spec |
| **Edition numbering** | Import AI #431, Last Week in AI #340 — reinforces continuity and shareability. | LOW | "Week of …" may suffice; numbering is polish. | **Optional v1.x** |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but create problems for a personal weekly digest.

| Feature | Why Requested | Why Problematic | Alternative | v1 Plan |
|---------|---------------|-----------------|-------------|---------|
| **Real-time / daily / push-notification cadence** | TLDR and Ben's Bites train users to expect daily email. | Conflicts with "Sunday morning read" and narrative roll-up; multiplies LLM + ops cost; creates FOMO treadmill. | Weekly batch + full archive | **Correctly avoided** |
| **Twitter/X ingestion** | Many AI voices live on X. | Paid API (~$100/mo), brittle scrapers, TOS risk (PROJECT.md). | Reddit/HN + blogs + YouTube | **Correctly avoided** |
| **Q&A chat over full archive** | Feedly Ask AI, Particle chat, Readwise Ghostreader make this tempting. | Changes IA from curated edition to open corpus; retrieval quality becomes the product; scope explosion. | Weekly narrative + linked originals | **Correctly avoided** |
| **KPI / stat extraction strip** | Reference dashboard; Particle quote extraction. | Extra LLM pass, hallucination risk on numbers, low value vs. prose roll-up for personal use. | Editor's note calling out 2–3 themes in prose | **Correctly avoided** |
| **Multi-user / auth / BYO sources** | Readwise, Inoreader, FreshRSS are multi-user. | v1 goal is ship for one person; auth + tenant isolation delays core pipeline. | Hard-coded config file | **Correctly avoided** |
| **Podcast audio transcription** | Matter, Inoreader transcribe audio. | Whisper-scale cost and latency on hours of audio weekly. | Ingest podcast RSS metadata only; defer transcription | **Correctly avoided** |
| **Infinite-scroll raw feed UI** | RSS readers default to chronological streams. | Opposite of curated digest; recreates the 5-hour skimming problem. | Ranked Briefing + topic tabs | **Correctly avoided** (by design) |
| **Opaque algorithmic personalization** | Refind/Particle optimize for engagement. | Single user with fixed sources doesn't need black-box ranking; hard to debug wrong picks. | Explicit LLM rank with inspectable prompts | **Correctly avoided** |
| **Social/community layer** | Ben's Bites voting, Particle suggested questions from community. | Moderation, spam, and product identity shift away from personal tool. | Solo automated pipeline | **Correctly avoided** |
| **Replacing publishers (summary-only, no click-through)** | AI news apps criticized for stealing traffic. | Erodes trust; can't verify claims; publisher ethics issue (Particle explicitly links prominently to sources). | Summary + prominent source link | **Avoid in implementation** — not yet explicit in requirements |
| **Email as sole delivery channel** | All competitor newsletters are email-first. | v1 is dashboard-first by design (reference screenshot). Email duplicate is ops overhead. | Web archive as canonical edition | **Acceptable tradeoff** for v1 |

## Competitor Feature Analysis

Evidence from products named in the research brief.

| Feature | TLDR AI | Ben's Bites | Import AI | AI Breakfast | Last Week in AI | Feedly AI | Refind | Readwise Reader | Matter | Inoreader | Miniflux | Particle | Wallabag / FreshRSS | AI Digest v1 |
|---------|---------|-------------|-----------|--------------|-----------------|-----------|--------|-----------------|--------|-----------|----------|----------|---------------------|--------------|
| **Cadence** | Daily email | Daily email | Weekly essay | 3× weekly | Weekly + podcast | Continuous RSS | Daily digest | Continuous feed | Continuous | Continuous | Continuous | Continuous app | Continuous RSS | **Weekly edition** |
| **Per-item summary** | 1–2 sentence blurbs | Short + many links | Long-form analysis | 4–6 min reads | Brief story list | Feed inline summaries | Key takeaways | Ghostreader on demand | Co-Reader Q&A | On-demand Summarize | Community AI plugins | Multi-format summaries | None native | **LLM TL;DR every item** |
| **Weekly roll-up** | No (daily only) | No | Editorial essay | No | Issue theme | Ask AI batch | Weekend Edition | No | No | Intelligence reports | AI digest plugins | Story clustering | No | **Narrative editor's note** |
| **Topic sections** | AI/Tech/Data/Design/Programming | Tools + news | Research focus | General AI | General AI | AI Feeds / boards | Follow topics | Filtered views | Feeds + tags | Folders/tags | Categories | Follow topics | Tags/categories | **4 personal topics + Briefing** |
| **Ranking / top picks** | Implicit (order in email) | Curated picks + community votes | Author's pick of papers | Chronological archive | Chronological | Leo prioritization | Algorithm + editors | Manual | Algorithm | Manual rules | Manual | Algorithm + editors | Manual | **LLM Top N on Briefing** |
| **Archive** | Web | Beehiiv archive | jack-clark.net | Beehiiv archive | Substack archive | Yes | Library | Full library | Library | Yes | Yes | Yes | Yes | **Full weekly archive** |
| **Source link** | Every item | Every item | Inline links | Every item | Every item | Yes | Yes | Yes | Yes | Yes | Yes | Prominent below summary | Original URL | **Should require — gap** |
| **Video / podcast** | Links only | Product links | Rare | Rare | Podcast episodes | Enclosures | Video search | Podcast RSS + transcript button | Podcast transcription | Podcast summaries (2025) | YouTube in-app | Podcast clips | Enclosures | **YouTube transcripts in tabs** |
| **Newsletter ingestion** | Is a newsletter | Is a newsletter | Is a newsletter | Is a newsletter | Is a newsletter | Email-to-feed | N/A | Custom @feed email | Gmail / custom email | Email newsletters | N/A | Publisher APIs | Save + RSS out | **Email→RSS bridge** |
| **Chat / Q&A** | No | No | No | No | No | Ask AI | No | Ghostreader chat | Co-Reader | Custom prompts | No | Story chatbot | No | **Out of scope** |
| **Self-host** | No | No | No | No | No | No | No | No | No | No | Yes | No | Yes | TBD stack |

**Note on Granola and Lex:** Granola (`granola.ai`) is an AI meeting-notepad (transcription + notes), not a news digest — not comparable. Lex (`lex.page`) is an AI writing tool; "Lexi AI" on the App Store is a generic news app with minimal verified feature detail. Neither informs v1 scope meaningfully.

## Feature Dependencies

```
[Ingestion: RSS / YouTube / Reddit-HN / email→RSS]
    └──requires──> [Source config file]
    └──requires──> [Per-source error isolation]
                       └──requires──> [Item store with url, title, published_at, source_id, raw content]

[Per-item TL;DR summary]
    └──requires──> [Ingestion + item store]
    └──blocks──> [Weekly narrative roll-up]
    └──blocks──> [Auto-categorization]
    └──blocks──> [Ranking / Top N]

[Auto-categorize: edtech | business | technical | design]
    └──requires──> [Per-item TL;DR summary] (or raw content + summary)

[Rank items + Briefing Top N]
    └──requires──> [Per-item summaries + categories]
    └──enhanced by──> [Dedupe / story clustering] (optional but high value)

[Weekly narrative roll-up]
    └──requires──> [All per-item summaries for the week]
    └──requires──> [Categorization + ranking output]

[Presentation: Briefing + 4 topic tabs]
    └──requires──> [Ranked + categorized items for one week edition]
    └──requires──> [Archive storage keyed by week range]

[Full archive browse]
    └──requires──> [Immutable weekly edition snapshots]

[LLM cost observability]
    └──requires──> [Token/cost logging in pipeline]
    └──enhances──> [Bounded spend guardrails]

[Dedupe / story clustering] ──conflicts with──> [Naive "every RSS entry is unique" ingestion]
[Weekly cadence] ──conflicts with──> [Real-time push / continuous feed UX]
[Q&A chat over archive] ──conflicts with──> [Curated edition as finished artifact]
```

### Dependency Notes

- **Narrative roll-up requires per-item summaries:** Roll-up prompts need the full set of summarized items as input; running roll-up on raw HTML is lower quality and much more expensive.
- **Ranking requires categorization (soft dependency):** Briefing Top N can rank globally, but topic tabs need categorized items first. Pipeline order: ingest → summarize → categorize → rank → roll-up → publish.
- **Dedupe enhances ranking:** Without clustering, Top N may be five variants of the same model release from different blogs.
- **Source links are not a pipeline dependency but a presentation invariant:** Can ship without extra LLM work — store `canonical_url` at ingestion.

## Gap Analysis (v1 Plan vs. Market Table Stakes)

Cross-reference of PROJECT.md Active Requirements and Out of Scope against market expectations.

| Gap | Severity | Evidence | Recommendation |
|-----|----------|----------|----------------|
| **No explicit requirement for original source links on every item** | **HIGH** | Universal across TLDR, Ben's Bites, Particle (prominent gold links), Refind, RSS readers | Add to Presentation: "Every item links to canonical original URL" |
| **No explicit source/publisher attribution** | **MEDIUM** | Feedly/Inoreader/Readwise show source name + favicon; newsletters brand each link | Add: publisher name, source type badge, favicon |
| **No per-item publication date** | **MEDIUM** | All archives and feeds show item dates | Add: display `published_at`; week filter is necessary but not sufficient |
| **No dedupe / story clustering across sources** | **MEDIUM–HIGH** | Particle clusters by story; overlapping AI sources routinely repost same news | Add to AI Pipeline or Ingestion: URL dedupe minimum; title/entity clustering ideal for v1 |
| **No archive search** | **MEDIUM** | FreshRSS, Wallabag, Matter, Inoreader all searchable; browse-only gets painful after ~20 weeks | Defer to v1.x unless static search (Pagefind/Algolia) is trivial with chosen stack |
| **No email/push delivery of edition** | **LOW** (for v1) | All named newsletters are email-native; v1 is dashboard-first by design | Accept for v1; add "email me this week's Briefing" in v1.x if validated |
| **No "why ranked / why it matters" field** | **LOW** | Refind explains picks; Import AI adds editorial framing | Optional LLM field on Briefing items; narrative roll-up partially covers |
| **No pipeline status / failed-source visibility in UI** | **LOW–MEDIUM** | Ops table stakes for unattended automation | v1: structured logs; v1.x: admin strip showing "3 sources failed this run" |
| **Paid Substack / paywalled content** | **LOW** (known limitation) | Readwise: paid Substack RSS shows partial content only; full content via email forward | Document constraint; email→RSS bridge mitigates for forwarded newsletters |

### Table Stakes the v1 Plan Covers

- Multi-source automated ingestion (RSS, YouTube, Reddit/HN, email newsletters)
- Hard-coded source config
- LLM per-item summaries
- Auto-categorization into four personal topics
- LLM ranking + Briefing Top N
- Weekly narrative roll-up
- Dark-themed tabbed dashboard (Briefing + 4 topics)
- Week-range dating + Updated timestamp
- Full archive of past digests
- Weekly cadence with single-source failure resilience
- Bounded/observable LLM cost (ops requirement)

### Differentiators Worth Pulling Into v1 (Low Cost, High Alignment)

| Feature | Effort | Why now |
|---------|--------|---------|
| **Canonical source link + publisher badge** | Trivial | Trust, verification, table stakes |
| **Per-item `published_at`** | Trivial | Already in feed metadata |
| **URL-level dedupe** | Low | Prevents exact duplicate entries from retries/overlapping feeds |
| **Edition slug / shareable URL** | Low | ` /2026/week-20` supports archive mental model |

### Differentiators Correctly Deferred

- Q&A chat, Feedly-style Ask AI, Particle story chat
- KPI / big-number extraction strip
- Twitter/X, LinkedIn, podcast transcription
- Multi-user auth and BYO sources
- Real-time/daily cadence and push notifications
- Audio/TTS, highlights/Readwise export, community voting
- Algorithmic personalization and bias-spectrum views
- Interactive Intelligence reports (Inoreader-style ad-hoc batch prompts)

### Anti-Features the v1 Plan Correctly Avoids

All items listed in PROJECT.md Out of Scope match market anti-patterns for this product shape: auth/multi-user, Twitter/X, podcast transcription, Q&A chat, Workday lens, daily/real-time cadence, KPI strip. Additional correct avoids validated by research: infinite raw feed UI, social/community curation layer, summary-only without attribution, opaque engagement ranking.

## MVP Definition

### Launch With (v1)

Minimum viable product — what's needed to validate Core Value: *"coherent narrative of what happened in AI this week in 15 minutes."*

- [ ] **Automated ingestion from hard-coded sources** — Without this, it's manual curation (a fancier Pocket).
- [ ] **Per-item LLM summary + categorization + ranking** — The machine does triage the user currently does by hand.
- [ ] **Weekly narrative roll-up on Briefing** — Differentiates from TLDR/Ben's Bites link lists; matches reference dashboard.
- [ ] **Briefing + 4 topic tabs, dark theme, week-range header** — The "Sunday morning read" container.
- [ ] **Full archive by week** — Validates "weekly newspaper" model.
- [ ] **Source link + attribution on every item** — *Recommend adding to PROJECT.md*; table stakes for trust.
- [ ] **Pipeline resilience + cost logging** — Unattended weekly runs must not silently fail or overspend.

### Add After Validation (v1.x)

Features to add once core weekly experience is read regularly for 4–8 weeks.

- [ ] **Story-level dedupe/clustering** — Trigger: Briefing Top N feels repetitive across sources.
- [ ] **Archive full-text search** — Trigger: Browsing by date alone feels slow.
- [ ] **Failed-source status in UI** — Trigger: User notices missing favorite source with no explanation.
- [ ] **Email edition ("Briefing in inbox")** — Trigger: User skips site because email is existing habit.
- [ ] **"Why this made Briefing" one-liner** — Trigger: Ranking feels arbitrary.

### Future Consideration (v2+)

- [ ] **Podcast transcription** — High cost; RSS metadata sufficient until then.
- [ ] **Twitter/X ingestion** — Revisit if API economics or stable unofficial path changes.
- [ ] **Q&A chat over archive** — After corpus quality and citations are proven.
- [ ] **Audio/TTS edition** — Commute consumption layer.
- [ ] **BYO sources / multi-user** — After personal v1 validates pipeline architecture.
- [ ] **Highlights export (Readwise/Obsidian)** — Knowledge capture, not digest reading.
- [ ] **KPI strip** — Only if narrative roll-up fails to surface quantitative milestones.

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Multi-source ingestion | HIGH | MEDIUM | P1 |
| Per-item LLM summary | HIGH | MEDIUM | P1 |
| Categorization (4 topics) | HIGH | LOW–MEDIUM | P1 |
| Briefing rank + Top N | HIGH | MEDIUM | P1 |
| Weekly narrative roll-up | HIGH | MEDIUM | P1 |
| Tabbed dark dashboard + archive | HIGH | MEDIUM | P1 |
| Source link + attribution | HIGH | LOW | P1 *(gap — add to spec)* |
| Per-item published date | MEDIUM | LOW | P1 *(gap — add to spec)* |
| URL dedupe | MEDIUM | LOW | P2 |
| Story clustering | MEDIUM | MEDIUM–HIGH | P2 |
| Archive search | MEDIUM | MEDIUM | P2 |
| Pipeline status UI | LOW–MEDIUM | LOW | P2 |
| Email delivery | MEDIUM | MEDIUM | P3 |
| Audio/TTS | LOW (for dashboard v1) | MEDIUM | P3 |
| Q&A chat | LOW (for v1 scope) | HIGH | P3 (v2) |

**Priority key:**
- P1: Must have for launch
- P2: Should have, add when possible
- P3: Nice to have, future consideration

## Sources

- [TLDR AI](https://tldr.tech/ai) — daily AI newsletter, multi-section (AI/Tech/Data/Design/Programming)
- [Ben's Bites](https://bensbites.co/) — daily digest, community newsfeed, past issues archive
- [Import AI](https://jack-clark.net/) — weekly numbered research newsletter, long-form editorial
- [AI Breakfast](https://aibreakfast.beehiiv.com/) — 3× weekly curated analysis, Beehiiv archive
- [Last Week in AI archive](https://lastweekin.ai/archive) — weekly issues + podcast companion
- [Feedly AI Summarization](https://feedly.com/new-features/posts/feedly-ai-and-summarization) — inline feed summaries, highlight key sentences
- [Feedly Ask AI](https://feedly.com/new-features/posts/new-feedly-ask-ai-from-information-overload-to-actionable-insights) — synthesize up to 25 articles
- [Refind About](https://refind.com/about) / [Refind Premium](https://refind.com/premium) — daily digest, key takeaways, Weekend Edition, audio, library
- [Readwise Ghostreader docs](https://docs.readwise.io/reader/guides/ghostreader/overview) — summarize, chat, custom prompts; Reader FAQ for RSS/newsletter ingestion
- [Matter](https://www.getmatter.com/) — save/read, newsletter email, audio, highlights; [Co-Reader coverage](https://www.radneurons.com/matter-co-reader/)
- [Inoreader Intelligence launch](https://www.inoreader.com/blog/2025/03/inoreader-intelligence-and-article-summaries-are-here.html) — article summaries, custom prompts
- [Inoreader Intelligence reports](https://www.inoreader.com/blog/2025/04/new-intelligence-reports-and-team-intelligence-plan.html) — bulk multi-article synthesis
- [Miniflux features](https://miniflux.app/features.html) — RSS, privacy, search, dark themes, no native AI
- [miniflux-ai community project](https://github.com/Qetesh/miniflux-ai) — LLM summaries via webhook extension pattern
- [Particle launch (TechCrunch)](https://techcrunch.com/2024/11/12/particle-launches-an-ai-news-app-to-help-publishers-instead-of-just-stealing-their-work/) — clustering, multi-format summaries, Opposite Sides, story chat, publisher links
- [FreshRSS](https://freshrss.org/) — self-hosted RSS, OPML, search, WebSub
- [Wallabag](https://wallabag.org/) — self-hosted read-later, RSS export of saved articles
- [Granola](https://www.granola.ai/) — verified as meeting-notes product, not news digest
- PROJECT.md Active Requirements and Out of Scope (2026-05-21)

---
*Feature research for: AI Digest personal weekly dashboard*
*Researched: 2026-05-21*
