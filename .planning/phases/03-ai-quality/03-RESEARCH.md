# Phase 3: AI Quality — Research

**Researched:** 2026-05-22  
**Domain:** Dedup-before-LLM, LLM categorize/rank/rollup, cost governance, structured pipeline reporting  
**Confidence:** HIGH (codebase + locked CONTEXT); MEDIUM (Gemini invalid-enum edge cases, live dedup quality)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-43..D-71** — Full decision set in `03-CONTEXT.md` `<decisions>`; planner must cite decision IDs in PLAN.md. Highlights:
  - Tier 0 URL + Tier 1 RapidFuzz @ **0.85**; same ISO week only (D-44); canonical = longest `raw_content` (D-45)
  - Strict one category enum; source `tag` as soft hint + fallback (D-47..D-49); `temperature=0` + JSON enum only in v1 (D-50)
  - Top N default **5**; LLM-only ranking signals (D-51..D-53); ranks persisted with `model_id` + `prompt_version` (D-54)
  - Hierarchical rollup: 4 category minis + 1 weekly synthesis; minis = Phase 4 tab openers (D-55..D-57)
  - **$2/week** hard stop, **$0.10** meta reservation, partial publish (D-59..D-60); Flash-Lite vs Flash tiering (D-61)
  - Hybrid checkpointing (D-67); cascade on `content_hash` (D-68); `pipeline-report-{week_id}.json` + `pipeline_report.json` (D-69..D-70)
  - MVP inline execution in Cursor (D-71)
- **LOCKED-01** — Extend `_classify_llm_exception` + `_partition_cards`; quota-only in-place carve-out for item summaries; rollups degrade per D-58/D-66
- **DEDUP-04** — Dedup **before** summarize (canonical items only get LLM summarize)
- **D-22** — README + `--help` + UAT for every new subcommand/flag

### Claude's Discretion
- RapidFuzz function choice within family (`token_set_ratio` recommended)
- URL deny-list details, trailing slash, www/apex
- Schema: single vs separate cluster artifact tables
- `pipeline_report.json` exact key names; `budget.py` function signatures
- CLI flag final names; test/UAT checklist details

### Deferred Ideas (OUT OF SCOPE)
- Tier 2 SimHash / Tier 3 embeddings; anti-over-merge guardrails; few-shot categorize; ranking escalation ladders; Astro dashboard; GHA cron; formal $5 cap (Phase 5)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DEDUP-01 | URL canonicalization Tier 0 | §URL canonicalization deny-list; `pipeline/dedup/url.py` + httpx redirect follow |
| DEDUP-02 | RapidFuzz title clustering @ threshold | §RapidFuzz wrapper; 0–100 scale → compare `>= 85.0` |
| DEDUP-03 | Preserve all source attributions | `cluster_members` join table; renderer "Also covered by" (D-64) |
| DEDUP-04 | Dedup before LLM summarize | Reorder orchestrator: `dedup` → `summarize` (canonical only) |
| PIPELINE-02 | One of four categories | §Pydantic + Gemini enum; `cluster_summaries.category` |
| PIPELINE-03 | Rank + Top N (default 5) | `cluster_ranks` + Briefing section (D-63) |
| PIPELINE-04 | Weekly narrative roll-up | §Hierarchical rollup prompts; `weekly_rollups` table |
| PIPELINE-05 | Idempotent re-run | Checkpoint skips + stored artifacts; render reads DB only |
| PIPELINE-06 | Crash-safe resume | Item-level categorize/summarize; stage-level dedup/rank/rollup (D-67) |
| OBS-02 | Structured run report | §`pipeline_report.json` shape; projection from `pipeline_runs` |
</phase_requirements>

## Summary

Phase 3 is an **orchestration and schema extension** of the Phase 1–2 pipeline, not a greenfield stack. The codebase already provides the patterns every new LLM stage must copy: Pydantic `response_schema` on `google.genai.types.GenerateContentConfig`, per-row checkpointing in `_summarize_week_items`, LOCKED-01 routing in `_partition_cards`, and additive SQLite migrations. The highest-risk implementation work is (1) **reordering the pipeline** so dedup runs before summarize and only canonical cluster members are summarized, (2) **union-find clustering** with RapidFuzz on a 0–100 scale at threshold 85.0, and (3) **budget reservation** so meta stages (categorize, rank, rollup) always retain $0.10 even if per-item summarize hits the cap.

**Primary recommendation:** Plan as **five vertical MVP slices** (dedup → +categorize sections → +rank/Top N → +hierarchical rollup → +budget/report), each shipping a readable `out/digest-{week_id}.html`. Use **separate tables** for cluster artifacts (`story_clusters`, `cluster_members`, `cluster_summaries`, `cluster_ranks`, `weekly_rollups`) mirroring `item_summaries`. Extract `_classify_llm_exception` to a shared module and add artifact-specific status columns rather than overloading `summary_status` on items.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| URL canonicalization + fuzzy dedup | API / Backend (pipeline) | — | Deterministic; no LLM; writes SQLite |
| Summarize / categorize / rank / rollup | API / Backend (LLM modules) | — | Gemini calls; persists rows |
| Budget cap + reservation | API / Backend (`pipeline/budget.py`) | Orchestrator | Wraps every LLM call site |
| Cascade invalidation | API / Backend (orchestrator + `pipeline/cascade.py`) | Store | Reads `content_hash`, cluster membership |
| Briefing / category sections / footer | Renderer (`pipeline/render/html.py`) | — | Reads stored artifacts; never calls LLM |
| `pipeline_report.json` | Reporting (`pipeline/reporting/pipeline_report.py`) | Store (`pipeline_runs`) | Projection for Phase 4/5 consumers |

## Project Constraints (from `.cursor/rules/`)

- GSD workflow: phase plans must comply with **LOCKED-01** (`locked-directives.mdc` points to `.planning/LOCKED-DIRECTIVES.md`).
- No direct repo edits outside GSD commands unless user bypasses — research artifact only.
- Stack bias: Python pipeline + SQLite + plain HTML until Phase 4 Astro.

---

## Standard Stack

### Core (Phase 3 additions)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **rapidfuzz** | 3.13.0 (PyPI latest verified 2026-05-22) | Tier 1 title clustering | [CITED: RapidFuzz docs] 0–100 scores; `score_cutoff` early exit; feedmeup precedent |
| **google-genai** | ≥2.5.0 (already in `pyproject.toml`) | Structured JSON for categorize/rank/rollup | Same SDK as `summarize.py`; `response_schema` + Pydantic |
| **pydantic** | ≥2.13 (already in project) | `Literal` enum for categories; result models | `model_validate_json` fallback when `response.parsed` is None |
| **httpx** | ≥0.28 (already in project) | Single redirect follow for URL canonicalization | Already used in enrichment path |
| **PyYAML** | ≥6.0 (already in project) | `config/digest.yaml` knobs | Matches `sources.yaml` loader pattern |

### Supporting (unchanged)

| Library | Purpose |
|---------|---------|
| tenacity | Retry on 429/5xx for LLM stages (copy from `summarize.py`) |
| structlog | Per-stage cost/token logging |
| pytest + pytest-httpx | Unit tests; mock Gemini + HTTP redirects |

**Installation:**
```bash
# Add to pyproject.toml dependencies:
# rapidfuzz>=3.13.0,<4
```

**Version verification:** `python3 -m pip index versions rapidfuzz` → 3.13.0 (2026-05-22).

## Package Legitimacy Audit

> slopcheck unavailable in research environment — rapidfuzz tagged `[VERIFIED: PyPI index]` via `pip index versions`.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| rapidfuzz | PyPI | 8+ yrs | very high | github.com/rapidfuzz/RapidFuzz | n/a | Approved — add to pyproject.toml |
| google-genai | PyPI | existing dep | high | googleapis/python-genai | n/a | Already installed |

**Packages removed due to slopcheck [SLOP]:** none  
**Packages flagged [SUS]:** none

---

## Focus Area 1: RapidFuzz Wrapper (D-43)

### API facts [VERIFIED: RapidFuzz 3.x docs]

- All `rapidfuzz.fuzz.*_ratio` functions return **`float` in [0, 100]**, not [0, 1].
- D-43 threshold **0.85** → compare **`score >= 85.0`** (or pass `score_cutoff=85.0` for performance).
- **`token_set_ratio`** (recommended): tokenizes, compares intersection/remainder sets; **handles word reordering**; returns 100 when one title is a subset of another (common for "Breaking: X" vs "X").
- **`token_sort_ratio`**: sorts tokens then `ratio` — stricter on extra words; better when word order is stable.
- **`WRatio`**: weighted max of several ratios — more forgiving on partial matches; can increase over-merge vs `token_set_ratio`.

### Recommended wrapper (`pipeline/dedup/title_fuzzy.py`)

```python
from rapidfuzz import fuzz

DEFAULT_THRESHOLD = 0.85  # config: dedup.title_fuzzy_threshold

def title_similarity(a: str, b: str, *, threshold: float = DEFAULT_THRESHOLD) -> float:
    """Return similarity in [0, 1] for config-friendly threshold."""
    score = fuzz.token_set_ratio(a, b, score_cutoff=threshold * 100)
    return score / 100.0

def titles_match(a: str, b: str, *, threshold: float = DEFAULT_THRESHOLD) -> bool:
    return fuzz.token_set_ratio(a, b) >= threshold * 100
```

### Title normalization (before fuzzy)

Apply once when writing `story_clusters.title_normalized` and when comparing:

1. Unicode **NFKC** normalize (`unicodedata.normalize("NFKC", s)`)
2. Lowercase
3. Strip punctuation (keep alphanumerics + spaces): `re.sub(r"[^\w\s]", " ", s)`
4. Collapse whitespace
5. Optional: strip leading `"breaking:"` / `"update:"` prefixes (planner discretion — document if added)

### Clustering algorithm

For same-week items (D-44), **union-find** on pairs where `titles_match` OR Tier 0 `canonical_url` match:

1. Tier 0: bucket by normalized URL → merge buckets
2. Tier 1: for remaining, O(n²) pairwise within week is fine (~50–150 items/week post-ingest)
3. Use `score_cutoff` when scanning neighbors to skip obvious non-matches

### Gotchas

| Issue | Mitigation |
|-------|------------|
| **Scale confusion** (0.85 vs 85) | Unit test asserts `85.0` boundary; config documents "fraction 0–1" |
| **Subset inflation** (`token_set_ratio` → 100) | Accept for v1 (D-46); raise threshold to 0.90 if over-merge in UAT |
| **Unicode / emoji titles** | NFKC + optional emoji strip; test fixture with smart quotes |
| **Common-word headlines** ("AI weekly roundup") | Same-week + 0.85 still risky — monitor in UAT; no v1 guardrail (D-46) |
| **Empty titles** | Skip fuzzy; URL-only cluster |

---

## Focus Area 2: URL Canonicalization Deny-List (D-43 Tier 0)

### Recommended deny-list (strip query keys)

**Tier A — locked in CONTEXT:** any key matching `utm_*` prefix; `gclid`, `fbclid`, `ref`, `mc_cid`, `mc_eid`

**Tier B — common practice [CITED: Metricular / SEO canonical guides]:** `msclkid`, `_ga`, `_gl`, `igshid`, `mkt_tok`, `vero_id`, `wickedid`, `oly_anon_id`, `oly_enc_id`, `pk_campaign`, `pk_kwd`, `spm`

**Do not strip:** `page`, `p`, `q`, `id`, `v` (YouTube video id), functional filters — only keys in deny-list.

### Normalization steps (order matters)

1. Parse with `urllib.parse.urlparse` / `urlunparse`
2. Lowercase **host**; strip leading `www.` consistently (pick one rule: always strip `www.`)
3. Remove deny-list query params; sort remaining params for stable canonical string (optional)
4. Strip **fragment** (`#...`)
5. Trailing slash: **remove** on path unless path is `/` only (Substack/blog consistency)
6. **Single redirect follow** (optional but CONTEXT recommends): httpx GET with `follow_redirects=True`, `timeout=5.0`, then canonicalize `response.url`
7. Store `canonical_url` on cluster; hash with SHA-256 for index

### httpx redirect shape [VERIFIED: httpx docs / existing project usage]

```python
import httpx

def resolve_final_url(url: str, client: httpx.Client) -> str:
    try:
        resp = client.get(url, follow_redirects=True, timeout=5.0)
        return str(resp.url)
    except httpx.HTTPError:
        return url  # fall back to pre-redirect canonical form
```

Use a shared `httpx.Client` per dedup run; do not follow redirects for every item if rate-limit concern — Tier 0 can use pre-redirect URL when fetch fails.

---

## Focus Area 3: Pydantic + Gemini Enum (D-47, D-49, D-50)

### Extend `summarize.py` pattern

```python
from typing import Literal
from pydantic import BaseModel, Field

Category = Literal["edtech", "business", "technical", "design"]

class CategorizeResponse(BaseModel):
    category: Category
    confidence: float | None = Field(default=None, ge=0, le=1)

# In _generate():
config=types.GenerateContentConfig(
    response_mime_type="application/json",
    response_schema=CategorizeResponse,
    temperature=0,  # D-50
    max_output_tokens=64,
)
```

[CITED: ai.google.dev/gemini-api/docs/structured-output] JSON Schema `enum` on string fields is supported; Pydantic `Literal[...]` generates the enum in `model_json_schema()`.

### Invalid output behavior

| Path | Behavior |
|------|----------|
| Gemini returns schema-valid JSON | `response.parsed` is `CategorizeResponse` — use directly |
| `parsed` is None | `CategorizeResponse.model_validate_json(response.text)` — **raises `ValidationError`** on bad enum → map to **`parse_error`** |
| API failure | `_classify_llm_exception` → `quota_exhausted` or `api_error` |
| After one retry still invalid enum | **D-49:** fallback to source YAML `tag`; set `category_confidence = "fallback_source_tag"` |

**Do not assume SDK coerces** invalid enums to nearest value — treat validation as application responsibility (Pydantic + D-49 fallback).

### Config enforcement (D-49)

Add validator on `SourceConfig` / `SourcesFile`: when `tag` is present, must be one of the four enum strings. Migration not required — validate at load time in `pipeline/config.py` when reading sources for categorize.

---

## Focus Area 4: Hierarchical Rollup Prompts (D-55–D-57)

### Per-category mini (`rollup_category_v1.md`)

**Input (structured text, not raw HTML):**
```
Week: 2026-W21
Category: technical
Ranked clusters (best first):
1. [cluster_id=...] Title — TL;DR (2-4 sentences) — sources: Simon Willison, ...
2. ...
```

**Output contract:** single paragraph, **80–120 words**, no markdown headings.

**Voice (D-57 / PITFALLS #16):**
- Role: "sharp editor, not press release"
- Ban: `game-changer`, `landscape`, `delve`, `it's worth noting`, `significant implications`, `paradigm shift`
- Include 1–2 bad vs good examples in prompt file (locked pattern from D-57)

### Weekly synthesis (`rollup_weekly_v1.md`)

**Input = only the four mini-rollup paragraphs** (NOT cluster lists) — PITFALLS #14 mitigation:

```
Week: 2026-W21
Edtech: <mini paragraph>
Business: <mini paragraph>
Technical: <mini paragraph>
Design: <mini paragraph>
```

**Output:** **150–200 words**, two short paragraphs; tie cross-category threads; name specific entities/events from minis only (grounding).

### Editorial pattern [CITED: PITFALLS #14, #16; accio-ai / newsletter roll-up practice]

- **Hierarchical compression:** category summaries → week summary keeps token budget ~2K
- **Anti-slop:** require ≥1 concrete noun (company, product, number) per paragraph
- **No engagement framing** (D-31): ban "trending", "widely discussed"

### Model config (D-61)

- `rollup_category_v1.md` → `gemini-2.5-flash`, `temperature=0.3` (planner may use 0.2–0.4 for prose; rank stays 0)
- `rollup_weekly_v1.md` → `gemini-2.5-flash`
- Persist `input_token_count`, `output_token_count`, `cost_usd_estimate`, `prompt_version`, `model_id` on `weekly_rollups` row

---

## Focus Area 5: `pipeline_report.json` Shape (D-70)

### Design principle

Follow **CI job summary / build artifact** conventions (GitHub Actions job summary, CircleCI artifacts) — flat JSON with `schema_version`, stage timings, and counters — **not** full OpenTelemetry trace export. Phase 4 OBS-01 and Phase 5 OBS-03 consume via **stable dot-path keys**.

### Recommended top-level schema (`schema_version: 1`)

```json
{
  "schema_version": 1,
  "week_id": "2026-W21",
  "generated_at": "2026-05-22T12:00:00Z",
  "run_id": "uuid",
  "status": "success|partial|failed",
  "items_ingested": 42,
  "clusters": 28,
  "llm_calls": 35,
  "cost_usd": 0.042,
  "errors": [],
  "summary_status": {
    "ok": 20,
    "thin": 5,
    "quota_exhausted": 1,
    "api_error": 0,
    "parse_error": 0,
    "client_init_error": 0
  },
  "stages": {
    "ingest": { "items": 42, "duration_ms": 12000 },
    "dedup": { "clusters_created": 28, "items_clustered": 14, "duration_ms": 200 },
    "summarize": { "llm_calls": 28, "cost_usd": 0.028, "items_unchanged": 0, "duration_ms": 90000 },
    "categorize": {
      "llm_calls": 28,
      "cost_usd": 0.004,
      "distribution": {
        "edtech": 2,
        "business": 10,
        "technical": 12,
        "design": 4,
        "fallback_source_tag": 0
      }
    },
    "rank": { "llm_calls": 1, "cost_usd": 0.003 },
    "rollup": { "mini_rollups": 4, "weekly": true, "cost_usd": 0.007 }
  },
  "source_health": {
    "simon-willison": {
      "last_success_at": "...",
      "last_error_category": null,
      "items_this_week": 5,
      "clusters_canonical_this_week": 5
    }
  },
  "budget": {
    "cap_usd": 2.0,
    "reserved_meta_usd": 0.10,
    "spent_usd": 0.042,
    "pre_flight_estimate_usd": 0.05,
    "halted": false,
    "halted_at_stage": null
  }
}
```

**Output paths (D-69):** `out/pipeline-report-{week_id}.json` + always-latest `out/pipeline_report.json` (both gitignored).

Implementation: `pipeline/reporting/pipeline_report.py` builds dict from `RunStats` + SQL aggregates; `finalize_pipeline_run` remains source of truth in SQLite.

---

## Focus Area 6: Budget Mechanism (D-60)

### Recommended API (`pipeline/budget.py`)

```python
@dataclass
class WeekBudget:
    cap_usd: float
    reserved_meta_usd: float
    spent_usd: float = 0.0
    halted: bool = False
    halted_at_stage: str | None = None

    @property
    def available_usd(self) -> float:
        return max(0.0, self.cap_usd - self.spent_usd)

    @property
    def summarize_pool_usd(self) -> float:
        """Per-item pool after meta reservation (D-60)."""
        return max(0.0, self.cap_usd - self.reserved_meta_usd - self._spent_on_summarize)

    def record_spend(self, amount: float, *, stage: str) -> None:
        self.spent_usd += amount

    def can_afford(self, estimated_usd: float, *, stage: str) -> bool:
        if self.halted:
            return False
        if stage in {"categorize", "rank", "rollup"}:
            # Meta stages: must leave room within full cap (reservation already accounted in planning)
            return self.spent_usd + estimated_usd <= self.cap_usd
        # summarize: use summarize pool
        return self._spent_on_summarize + estimated_usd <= self.cap_usd - self.reserved_meta_usd

    def halt_if_over_cap(self, *, stage: str) -> None:
        if self.spent_usd >= self.cap_usd:
            self.halted = True
            self.halted_at_stage = stage
```

**Orchestrator integration:**
1. Load `digest.yaml` → `pipeline.hard_stop_usd` (default 2.0), `pipeline.meta_reservation_usd` (0.10)
2. **Pre-flight:** `estimate_remaining = pending_items * baseline_per_item + meta_fixed_estimate`
3. Before each LLM call: `if not budget.can_afford(estimate, stage=...): break` (partial publish)
4. After each call: `budget.record_spend(result.cost_usd_estimate)` + `RunStats.cost_usd_estimate += ...`
5. **Between stages:** if summarize halted but `spent + meta_estimate <= cap`, still run categorize/rank/rollup (D-60)

### Baseline per-item cost (cold start)

Query prior week from `pipeline_runs` + item counts:

```sql
SELECT cost_usd_estimate, summaries_written FROM pipeline_runs
WHERE week_id = ? AND phase = 'all' AND status IN ('success', 'partial')
ORDER BY finished_at DESC LIMIT 1
```

Fallback: **`$0.001/item`** conservative (D-59). Meta fixed estimate: ~$0.01 for 5 Flash calls (generous).

---

## Focus Area 7: Cascading Invalidation (D-68)

### Trigger: `items.content_hash` changes

Dominant case: YouTube catch-up flips `pending_local` → `ok` with new transcript (`orchestrator._ingest_pending_transcripts` already updates hash).

### Cascade rules

| Event | Actions |
|-------|---------|
| `content_hash` changed | Re-summarize item |
| Item is cluster **canonical** OR `title_normalized` changed | Re-run **dedup** for `week_id` |
| Cluster membership changed for any cluster in current Top-N set | Re-**rank** week |
| Top-N composition changed | Re-run **rollup** (4 minis + weekly) |

Most content edits only re-summarize one item — full cascade is rare.

### Where logic lives

**Recommend `pipeline/cascade.py`** with pure functions:

```python
def plan_invalidation(
    *,
    item_id: str,
    old_hash: str,
    new_hash: str,
    is_canonical: bool,
    title_changed: bool,
    week_id: str,
    force_rebuild_clusters: bool,
    force_rebuild_rollup: bool,
) -> set[str]:  # stages to rerun: {"summarize", "dedup", "rank", "rollup"}
```

Orchestrator calls after catch-up / ingest upsert when hash changes. Flags:

- `--rebuild-clusters` → unconditional `dedup` (+ downstream rank + rollup if cluster set changes)
- `--rebuild-rollup` → skip dedup/rank unless cascade demands; force rollup stages

Automatic detection runs by default; flags override skip logic.

---

## Focus Area 8: Schema Layout for Cluster Artifacts

### Recommendation: **separate tables** (planner discretion resolved)

| Table | Purpose | Key columns |
|-------|---------|-------------|
| `story_clusters` | Cluster header | `cluster_id`, `week_id`, `canonical_item_id`, `canonical_url`, `title_normalized`, `created_at` |
| `cluster_members` | DEDUP-03 attributions | `cluster_id`, `item_id`, `is_canonical` |
| `cluster_summaries` | Category LLM artifact | `cluster_id`, `week_id`, `category`, `category_confidence`, `category_status`, `prompt_version`, `model_id`, … |
| `cluster_ranks` | Rank LLM artifact | `cluster_id`, `week_id`, `rank_score`, `rank_position`, `rank_status`, `prompt_version`, `model_id`, … |
| `weekly_rollups` | Rollup LLM artifacts | `week_id`, `scope` (`category:technical` / `weekly`), `narrative_md`, `rollup_status`, tokens, cost, `prompt_version`, `model_id` |

**Rationale:**
- Mirrors proven `item_summaries` pattern (PIPELINE-05 idempotent re-render)
- Re-running categorize does not wipe rank rows; cascade can target one stage
- `UNIQUE(cluster_id, week_id, prompt_version)` on summaries/ranks for checkpoint skip
- Separate `*_status` columns (`ok`, `quota_exhausted`, …) parallel `summary_status` — avoids overloading item row

**Denormalized single-table alternative:** fewer JOINs at render time but wider rows and harder partial invalidation — not recommended.

Migration file: `store/migrations/004_dedup_categorize_rank_rollup.sql` (additive). Extend `pipeline_runs.phase` CHECK to include `dedup`, `categorize`, `rank`, `rollup`, `all`.

---

## Focus Area 9: `_classify_llm_exception` Extension (LOCKED-01)

### Step 1: Extract shared helper

Move to `pipeline/llm/exceptions.py`:

```python
def classify_llm_exception(exc: BaseException) -> Literal[
    "ok", "quota_exhausted", "api_error", "parse_error", "client_init_error"
]:
    ...
```

Import from `summarize.py`, `categorize.py`, `rank.py`, `rollup.py`.

### Partitioning rules by artifact type

| Artifact | quota_exhausted | api_error / parse_error / client_init_error |
|----------|-----------------|-----------------------------------------------|
| **Item summary** (existing) | In-place main feed + `QUOTA_BODY_COPY` | Footer `<aside id="also-seen">` |
| **Cluster category** | In-place card with last-known category or source-tag fallback + `quota_exhausted` confidence (D-49) | Fallback source tag; no reader notice |
| **Cluster rank** | Use last persisted rank if present; else sort by `published_at` | Same fallback sort |
| **Category mini-rollup** | Omit paragraph silently (D-58) | Omit paragraph silently |
| **Weekly synthesis** | One-line in-place placeholder at top of `<main>` (D-58/D-66) | Same placeholder family |

Extend `_partition_cards` only for **item-level** routing. Rollups and category sections use **separate render helpers** that read `*_status` from DB — do not duplicate footer logic for clusters.

**New locked string constants** (mirror `QUOTA_BODY_COPY`):

- `WEEKLY_ROLLUP_FAILURE_COPY` — planner finalizes; must be plain English, one line
- Reuse `QUOTA_BODY_COPY` only for item summaries, not rollups

---

## Focus Area 10: MVP Vertical-Slice Grouping (D-71)

Each plan must ship a **readable digest** for its slice.

| Slice | Delivers | Pipeline order touched | Reader-visible outcome |
|-------|----------|------------------------|------------------------|
| **3-01 Dedup foundation** | Migration 004, `dedup/` module, `run dedup`, summarize **canonical only**, "Also covered by", basic report counters | ingest → **dedup** → summarize → render | Fewer duplicate cards; attribution line |
| **3-02 Categorize** | `categorize.py`, `digest.yaml`, per-category `<h2>` sections (chronological within section) | + **categorize** | Stories grouped by edtech/business/technical/design |
| **3-03 Rank + Briefing** | `rank.py`, Top N section (D-63) | + **rank** | Numbered "Briefing — Top 5 this week" |
| **3-04 Rollup** | `rollup.py`, hierarchical prompts, weekly + mini paragraphs | + **rollup** | Editor's note + section openers |
| **3-05 Governance** | `budget.py`, full `pipeline_report.json`, cascade + CLI flags, `last_run.md` extensions | Wrap all stages | Partial publish at cap; OBS-02 complete |

**Wave dependency:** 3-01 → 3-02 → 3-03 → 3-04 → 3-05 (each slice merges to main independently).

**Critical reorder in 3-01:** Change `run_all` from `ingest → summarize → render` to `ingest → dedup → summarize → render`.

---

## Architecture Patterns

### System Architecture Diagram

```
[CLI: pipeline.run]
        │
        ▼
[Orchestrator] ──reads──► config/sources.yaml, config/digest.yaml
        │
        ├──► ingest ──► items (SQLite)
        │
        ├──► dedup ──► story_clusters + cluster_members
        │       (Tier 0 URL, Tier 1 RapidFuzz, canonical pick D-45)
        │
        ├──► summarize (canonical items only) ──► item_summaries
        │       ▲ WeekBudget.can_afford per call
        │
        ├──► categorize ──► cluster_summaries
        ├──► rank ──► cluster_ranks
        ├──► rollup ──► weekly_rollups (×5)
        │
        ├──► render ──► out/digest-{week_id}.html
        │       (_partition_cards LOCKED-01; Briefing + category sections)
        │
        └──► pipeline_report ──► out/pipeline-report-{week_id}.json
                                out/pipeline_report.json
```

### Recommended project structure (Phase 3 additions)

```
pipeline/
├── dedup/
│   ├── url.py
│   ├── title_fuzzy.py
│   └── cluster.py          # engine: read items → write clusters
├── llm/
│   ├── exceptions.py       # classify_llm_exception (shared)
│   ├── categorize.py
│   ├── rank.py
│   ├── rollup.py
│   └── prompts/
│       ├── categorize_v1.md
│       ├── rank_v1.md
│       ├── rollup_category_v1.md
│       └── rollup_weekly_v1.md
├── budget.py
├── cascade.py
├── reporting/
│   └── pipeline_report.py
config/
└── digest.yaml
store/migrations/
└── 004_dedup_categorize_rank_rollup.sql
```

### Anti-patterns to avoid

- Summarizing all cluster members (violates DEDUP-04)
- Parallel `_partition_cards` for new artifact types
- Re-calling LLM in `run_render` (violates PIPELINE-05)
- Storing only JSON report without SQLite rows (violates D-09)

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Title fuzzy match | Custom Levenshtein | RapidFuzz `token_set_ratio` | Unicode, speed, battle-tested |
| JSON enum enforcement | Regex on model text | Pydantic + Gemini `response_schema` | D-49 retry + fallback needs typed errors |
| URL tracking strip | Ad-hoc string replace | `urllib.parse` query rewrite + deny-list set | Preserves functional params |
| Cost accounting | Global variable | `WeekBudget` + `RunStats` | Testable; feeds pipeline_report |
| Union-find clustering | LLM dedup | Deterministic Tier 0+1 | D-61 cost |

---

## Common Pitfalls (Phase 3 mitigations)

| Pitfall | Phase 3 mitigation |
|---------|-------------------|
| #1 Runaway cost | D-59/D-60 budget + dedup-before-summarize |
| #8 Under-dedup | D-43/D-44/D-45 |
| #9 Over-dedup | D-46 deferred; threshold knob in digest.yaml |
| #12 Categorization drift | D-50 temperature=0 + enum; UAT watch |
| #13 Prompt versioning | D-04 pattern on all new rows |
| #14 Lost-in-the-middle | D-55 hierarchical rollup input |
| #16 Slop | D-57 ban list + examples in rollup prompts |

---

## Code Examples

### Categorize call (mirror summarize.py)

```python
# Source: existing pipeline/llm/summarize.py + ai.google.dev structured output
response = client.models.generate_content(
    model=MODEL_ID,
    contents=[system_prompt, user_content],
    config=types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=CategorizeResponse,
        temperature=0,
        max_output_tokens=64,
    ),
)
parsed = response.parsed or CategorizeResponse.model_validate_json(response.text or "{}")
```

### Dedup-before-summarize orchestrator gate

```python
# After dedup: only canonical item_ids get summarize_item()
for cluster in clusters_for_week:
    row = get_item(conn, cluster.canonical_item_id)
    if get_existing_summary(conn, row.item_id, week_id, PROMPT_VERSION):
        continue
    if not budget.can_afford(estimate_per_item, stage="summarize"):
        budget.halt_if_over_cap(stage="summarize")
        break
    result = summarize_item(...)
```

---

## Validation Architecture

> Nyquist validation enabled (`workflow.nyquist_validation: true` in `.planning/config.json`).

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest ≥9.0.3 |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `pytest tests/test_dedup.py -x -q` (Wave 0 creates file) |
| Full suite command | `pytest tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DEDUP-01 | Strip utm/gclid; redirect canonical | unit | `pytest tests/test_dedup_url.py -x` | ❌ Wave 0 |
| DEDUP-02 | Known overlapping titles merge @ 0.85 | unit | `pytest tests/test_dedup_fuzzy.py -x` | ❌ Wave 0 |
| DEDUP-03 | cluster_members preserves all sources | unit | `pytest tests/test_dedup_cluster.py -x` | ❌ Wave 0 |
| DEDUP-04 | Non-canonical members skip summarize | integration | `pytest tests/test_pipeline_dedup_order.py -x` | ❌ Wave 0 |
| PIPELINE-02 | Enum categorize + tag fallback | unit | `pytest tests/test_categorize.py -x` | ❌ Wave 0 |
| PIPELINE-03 | rank_position stable same inputs | unit | `pytest tests/test_rank.py -x` | ❌ Wave 0 |
| PIPELINE-04 | Weekly rollup input = minis only | unit | `pytest tests/test_rollup.py -x` | ❌ Wave 0 |
| PIPELINE-05 | Second render identical HTML | integration | `pytest tests/test_render_idempotent.py -x` | ❌ Wave 0 |
| PIPELINE-06 | Resume skips summarized clusters | integration | `pytest tests/test_checkpoint.py -x` | ❌ Wave 0 |
| OBS-02 | pipeline_report schema_version + stages | unit | `pytest tests/test_pipeline_report.py -x` | ❌ Wave 0 |
| LOCKED-01 | quota vs thin routing extended | unit | `pytest tests/test_render.py -x` | ✅ extend |
| D-60 | Budget halt partial publish | unit | `pytest tests/test_budget.py -x` | ❌ Wave 0 |

### Fixture requirements (Wave 0)

- `tests/fixtures/dedup/title_pairs.json` — positive/negative pairs at 0.84/0.85/0.86
- `tests/fixtures/categorize/golden/` — one stub per category + invalid enum mock response
- `tests/fixtures/rollup/minis_sample.txt` — assert weekly prompt builder excludes raw clusters

### Sampling rate

- **Per task commit:** module-specific `-x` command from table above
- **Per wave merge:** `pytest tests/ -q` (currently 68 tests; expect ~+40)
- **Phase gate:** full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] All `tests/test_dedup*.py`, `test_categorize.py`, `test_rank.py`, `test_rollup.py`, `test_budget.py`, `test_pipeline_report.py`
- [ ] `rapidfuzz` added to `pyproject.toml`
- [ ] Extend `tests/test_render.py` for Briefing + category sections + rollup failure copy

### Manual UAT (from CONTEXT deferred watch)

- Dedup quality on live week; categorize spot-check 10–15 clusters; Top N reasonableness; rollup voice/length; partial publish with `hard_stop_usd: 0.01`

---

## Security Domain

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V5 Input Validation | yes | Pydantic on LLM outputs; enum on category; URL parse |
| V6 Cryptography | no new crypto | — |
| V10 Malicious input | yes | `html.escape` on all new reader strings (D-24) |

| Threat | STRIDE | Mitigation |
|--------|--------|------------|
| Prompt injection via RSS titles | Tampering | Grounding prompts; no tool execution |
| SSRF via redirect follow | Spoofing | 5s timeout; optional skip on failure |
| Cost exhaustion | DoS | WeekBudget hard stop |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Gemini `response_schema` rejects most invalid enums at generation | Focus 3 | More D-49 fallbacks than expected |
| A2 | ~50–150 items/week pre-dedup makes O(n²) fuzzy acceptable | Focus 1 | Need indexing if catalog grows |
| A3 | Source tags always map to valid categories after validator | Focus 3 | fallback_source_tag breaks render |

---

## Open Questions

1. **Redirect fetch on every ingest vs dedup-only** — CONTEXT allows planner discretion; recommend dedup-stage only with failure fallback to pre-redirect URL.
2. **`pipeline_runs.phase` CHECK migration** — extend via new migration vs recreate CHECK; use additive SQL that SQLite accepts.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12+ | pipeline | ✓ | system | — |
| GEMINI_API_KEY | LLM stages | env-dependent | — | Skip LLM in unit tests (mock client) |
| rapidfuzz | dedup | ✗ not in pyproject yet | 3.13.0 PyPI | Add dependency in Slice 3-01 |
| pytest | validation | ✓ | 9.x dev dep | — |

---

## Sources

### Primary (HIGH confidence)
- [RapidFuzz fuzz module](https://rapidfuzz.github.io/RapidFuzz/Usage/fuzz.html) — 0–100 scale, `token_set_ratio`, `score_cutoff`
- [Gemini structured output](https://ai.google.dev/gemini-api/docs/structured-output) — JSON Schema enum, Pydantic `Literal`
- `pipeline/llm/summarize.py`, `pipeline/orchestrator.py`, `pipeline/render/html.py` — existing patterns
- `.planning/phases/03-ai-quality/03-CONTEXT.md` — D-43..D-71
- `.planning/LOCKED-DIRECTIVES.md` — LOCKED-01

### Secondary (MEDIUM confidence)
- `.planning/research/ARCHITECTURE.md` §Dedup Strategy, §Pipeline Orchestration
- `.planning/research/PITFALLS.md` #1, #8–#16
- Metricular / SEO canonical guides — tracking param deny-list

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — RapidFuzz + existing google-genai path verified
- Architecture: HIGH — CONTEXT locks behavior; code anchors exist
- Pitfalls: HIGH — mapped to explicit decisions
- Gemini invalid-enum edge cases: MEDIUM — rely on Pydantic + D-49 fallback

**Research date:** 2026-05-22  
**Valid until:** ~2026-06-22 (stable stack); re-verify Gemini model IDs if Google deprecates 2.5-flash-lite

---

## RESEARCH COMPLETE

Phase 3 planning can proceed with **five vertical MVP slices**, **RapidFuzz at 85.0/100**, **separate cluster artifact tables**, **shared `classify_llm_exception`**, and a **WeekBudget + schema_versioned pipeline_report.json** projection. The critical path is reordering to **dedup-before-summarize** in slice 3-01; everything else extends patterns already proven in Phases 1–2.
