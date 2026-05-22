# Phase 3: AI Quality - Pattern Map

**Mapped:** 2026-05-22  
**Files analyzed:** 38 new/modified  
**Analogs found:** 34 / 38  
**LOCKED compliance:** All reader-surface routing extends `_partition_cards` per **LOCKED-01** (`.planning/LOCKED-DIRECTIVES.md`); quota-only in-place carve-out preserved; rollup failures use new locked-string constants mirroring `QUOTA_BODY_COPY` (D-58, D-66).

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `pipeline/dedup/url.py` | utility | transform | `pipeline/adapters/rss.py` (`_fetch_bytes`) | data-flow-match |
| `pipeline/dedup/title_fuzzy.py` | utility | transform | — (greenfield; RESEARCH §Focus 1) | no analog |
| `pipeline/dedup/cluster.py` | service | batch | `pipeline/orchestrator.py::_ingest` + `store/db.py::upsert_item` | role-match |
| `pipeline/llm/exceptions.py` | utility | transform | `pipeline/llm/summarize.py::_classify_llm_exception` | exact |
| `pipeline/llm/categorize.py` | service | request-response | `pipeline/llm/summarize.py` | exact |
| `pipeline/llm/rank.py` | service | request-response | `pipeline/llm/summarize.py` | exact |
| `pipeline/llm/rollup.py` | service | request-response | `pipeline/llm/summarize.py` | exact |
| `pipeline/llm/prompts/categorize_v1.md` | config | — | `pipeline/llm/prompts/summarize_v1.md` | exact |
| `pipeline/llm/prompts/rank_v1.md` | config | — | `pipeline/llm/prompts/summarize_v1.md` | exact |
| `pipeline/llm/prompts/rollup_category_v1.md` | config | — | `pipeline/llm/prompts/summarize_v1.md` | exact |
| `pipeline/llm/prompts/rollup_weekly_v1.md` | config | — | `pipeline/llm/prompts/summarize_v1.md` | exact |
| `pipeline/budget.py` | utility | event-driven | `pipeline/orchestrator.py::RunStats` | role-match |
| `pipeline/cascade.py` | utility | transform | `pipeline/week.py` (pure helpers) | partial |
| `pipeline/reporting/pipeline_report.py` | service | transform | `pipeline/reporting/last_run.py` + `store/db.py::finalize_pipeline_run` | role-match |
| `config/digest.yaml` | config | — | `config/sources.yaml` | exact |
| `store/migrations/004_dedup_categorize_rank_rollup.sql` | migration | CRUD | `store/migrations/003_summary_status.sql` | exact |
| `store/db.py` (extend) | model/store | CRUD | existing `get_existing_summary` / `insert_item_summary` | exact |
| `pipeline/orchestrator.py` (extend) | service | batch | self — `run_summarize` / `_summarize_week_items` | exact |
| `pipeline/render/html.py` (extend) | component | transform | self — `_partition_cards`, `QUOTA_BODY_COPY` | exact |
| `pipeline/run.py` (extend) | route/CLI | request-response | self — `ingest`/`summarize` subcommands | exact |
| `pipeline/config.py` (extend) | config | — | self — `load_sources` / Pydantic union | exact |
| `pipeline/llm/summarize.py` (extend) | service | request-response | self — import from `exceptions.py` | exact |
| `pipeline/reporting/last_run.py` (extend) | service | transform | self — `RunSummary` / `write_last_run_md` | exact |
| `pyproject.toml` (extend) | config | — | existing deps block | exact |
| `tests/test_dedup_url.py` | test | — | `tests/test_ingest.py` (httpx mocks) | role-match |
| `tests/test_dedup_fuzzy.py` | test | — | — (greenfield) | no analog |
| `tests/test_dedup_cluster.py` | test | — | `tests/test_store.py` | role-match |
| `tests/test_pipeline_dedup_order.py` | test | — | `tests/test_pipeline.py` | exact |
| `tests/test_categorize.py` | test | — | `tests/test_summarize.py` | exact |
| `tests/test_rank.py` | test | — | `tests/test_summarize.py` | exact |
| `tests/test_rollup.py` | test | — | `tests/test_summarize.py` | exact |
| `tests/test_render_idempotent.py` | test | — | `tests/test_render.py` | exact |
| `tests/test_checkpoint.py` | test | — | `tests/test_summarize.py` (DB skip) | role-match |
| `tests/test_pipeline_report.py` | test | — | `tests/test_pipeline.py` | role-match |
| `tests/test_budget.py` | test | — | `tests/test_summarize.py` (unit isolation) | role-match |
| `tests/test_render.py` (extend) | test | — | self | exact |

---

## Pattern Assignments

### `pipeline/dedup/url.py` (utility, transform)

**Serves:** D-43 Tier 0, DEDUP-01  
**RESEARCH:** Focus Area 2 (URL deny-list, redirect follow)

**Analog:** `pipeline/adapters/rss.py` — httpx client with `follow_redirects=True`

**Imports pattern** (rss.py lines 6–12, 67–86):
```python
import httpx

def _fetch_bytes(url: str) -> tuple[bytes, int]:
    with httpx.Client(
        headers={"User-Agent": USER_AGENT, "Accept": accept_header},
        timeout=HTTP_TIMEOUT_SECONDS,
        follow_redirects=True,
    ) as client:
        response = client.get(url)
```

**Core URL canonicalization shape** (RESEARCH + urllib.parse; dedup-only, 5s timeout):
```python
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

TRACKING_KEYS = {"gclid", "fbclid", "ref", "mc_cid", "mc_eid", ...}

def canonicalize_url(url: str, *, client: httpx.Client | None = None) -> str:
    parsed = urlparse(url.lower() if url.startswith("http") else url)
    # strip www., deny-list query keys (utm_* prefix), fragment, trailing slash
    ...
def resolve_final_url(url: str, client: httpx.Client) -> str:
    try:
        resp = client.get(url, follow_redirects=True, timeout=5.0)
        return str(resp.url)
    except httpx.HTTPError:
        return canonicalize_url(url)  # fall back pre-redirect
```

**Error handling:** Never raise on redirect failure — fall back to pre-redirect canonical form (RESEARCH Focus 2).

---

### `pipeline/dedup/title_fuzzy.py` (utility, transform)

**Serves:** D-43, DEDUP-02  
**RESEARCH:** Focus Area 1 (RapidFuzz 0–100 scale → `>= 85.0`)

**Analog:** None in codebase — follow RESEARCH recommended wrapper exactly.

**Core pattern** (RESEARCH §Focus 1):
```python
from rapidfuzz import fuzz

DEFAULT_THRESHOLD = 0.85  # config: dedup.title_fuzzy_threshold

def titles_match(a: str, b: str, *, threshold: float = DEFAULT_THRESHOLD) -> bool:
    return fuzz.token_set_ratio(a, b) >= threshold * 100  # D-43: 0.85 → 85.0

def normalize_title(s: str) -> str:
    # NFKC → lowercase → strip punctuation → collapse whitespace
    ...
```

**Gotcha:** Config documents fraction 0–1; RapidFuzz returns 0–100 — unit test boundary at 0.84/0.85/0.86 (RESEARCH Validation).

---

### `pipeline/dedup/cluster.py` (service, batch)

**Serves:** D-44, D-45, D-46, DEDUP-03, DEDUP-04  
**RESEARCH:** Focus Area 1 (union-find), Focus Area 8 (separate tables)

**Analog:** `pipeline/orchestrator.py::_ingest` (per-item loop + commit) + `store/db.py::upsert_item` (idempotent writes)

**Week window pattern** (orchestrator.py lines 264–274, week.py):
```python
from pipeline.week import week_bounds

week_start, week_end = week_bounds(week_id)
rows = get_items_for_week(
    conn,
    week_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
    week_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
)
```

**Canonical pick** (D-45 — longest `raw_content`, tie-break `published_at`, then `item_id`):
```python
def pick_canonical(members: list[ItemRow]) -> ItemRow:
    return sorted(
        members,
        key=lambda m: (-len(m.raw_content or ""), m.published_at, m.item_id),
    )[0]
```

**Engine entry point shape** (mirror `run_ingest` public API):
```python
def run_dedup_for_week(*, week_id: str, conn, log, stats: RunStats) -> int:
    """Tier 0 URL bucket → Tier 1 fuzzy union-find → write story_clusters + cluster_members."""
    ...
    conn.commit()
    return clusters_created
```

---

### `pipeline/llm/exceptions.py` (utility, transform)

**Serves:** LOCKED-01, D-49, RESEARCH Focus Area 9  
**Pattern role:** Shared `classify_llm_exception` taxonomy mapper

**Analog:** `pipeline/llm/summarize.py::_classify_llm_exception` (extract verbatim logic)

**Core pattern** (summarize.py lines 70–83):
```python
def classify_llm_exception(exc: BaseException) -> str:
    """Map LLM exception → status: quota_exhausted | api_error."""
    text = f"{type(exc).__name__} {exc!s}".lower()
    if "resource_exhausted" in text or "429" in text or "rate limit" in text or "quota" in text:
        return "quota_exhausted"
    return "api_error"
```

**Integration:** `summarize.py` re-exports or imports; categorize/rank/rollup map to artifact-specific `*_status` columns (`category_status`, `rank_status`, `rollup_status`) — do not overload `summary_status` on items (RESEARCH Focus 9).

---

### `pipeline/llm/categorize.py` (service, request-response)

**Serves:** D-47..D-50, D-61, PIPELINE-02, LOCKED-01  
**RESEARCH:** Focus Area 3 (Pydantic `Literal` enum)

**Analog:** `pipeline/llm/summarize.py` — full module shape

**Pattern role:** Pydantic structured-output schema + tenacity retry + `classify_llm_exception` + versioned prompt loader

**Imports + schema** (summarize.py lines 7–21, 47–67; RESEARCH Focus 3):
```python
from typing import Literal
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential
from pipeline.llm.exceptions import classify_llm_exception

Category = Literal["edtech", "business", "technical", "design"]
PROMPT_VERSION = "categorize_v1"
MODEL_ID = "gemini-2.5-flash-lite"  # D-61

class CategorizeResponse(BaseModel):
    category: Category
    confidence: float | None = Field(default=None, ge=0, le=1)
```

**Generate call** (summarize.py lines 151–170; temperature=0 per D-50):
```python
config=types.GenerateContentConfig(
    response_mime_type="application/json",
    response_schema=CategorizeResponse,
    temperature=0,
    max_output_tokens=64,
)
```

**D-49 fallback:** On invalid enum after retry → source YAML `tag`; persist `category_confidence = "fallback_source_tag"`.

**Checkpoint skip** (orchestrator.py lines 277–295 — adapt for clusters):
```python
existing = get_existing_cluster_summary(conn, cluster_id, week_id, PROMPT_VERSION)
if existing is not None:
    continue
```

---

### `pipeline/llm/rank.py` (service, request-response)

**Serves:** D-51..D-54, D-61, PIPELINE-03  
**RESEARCH:** Focus Area 3 (structured output)

**Analog:** `pipeline/llm/summarize.py`

**Pattern role:** Same as categorize; **stage-level** checkpoint (D-67) — single call per week, idempotent re-run

**Model tier** (D-61):
```python
PROMPT_VERSION = "rank_v1"
MODEL_ID = "gemini-2.5-flash"  # meta stage
TEMPERATURE = 0
```

**Result model** (mirror `SummaryResult`):
```python
class RankResult(BaseModel):
    rank_score: float
    rank_position: int
    prompt_version: str
    model_id: str
    rank_status: str = "ok"
    cost_usd_estimate: float | None = None
```

**Storage:** `cluster_ranks` table — renderer reads DB only (PIPELINE-05, D-54).

---

### `pipeline/llm/rollup.py` (service, request-response)

**Serves:** D-55..D-58, D-61, PIPELINE-04, LOCKED-01  
**RESEARCH:** Focus Area 4 (hierarchical: 4 minis + 1 weekly)

**Analog:** `pipeline/llm/summarize.py`

**Pattern role:** Two prompt versions (`rollup_category_v1`, `rollup_weekly_v1`); prose temperature 0.2–0.4 for minis (D-61 discretion)

**Entry points:**
```python
def rollup_category(*, week_id: str, category: Category, clusters: list[ClusterInput], ...) -> RollupResult: ...
def rollup_weekly(*, week_id: str, mini_paragraphs: dict[Category, str], ...) -> RollupResult: ...
```

**Weekly input constraint** (D-55 / PITFALLS #14): weekly synthesis takes **only the four mini paragraphs**, not raw cluster lists.

**Failure routing** (D-58): `rollup_status != ok` → weekly: one-line placeholder at top of `<main>`; per-category mini: omit paragraph silently.

---

### `pipeline/llm/prompts/{categorize,rank,rollup_category,rollup_weekly}_v1.md` (config)

**Serves:** D-04, D-48, D-53, D-57  
**RESEARCH:** Focus Areas 3–4

**Analog:** `pipeline/llm/prompts/summarize_v1.md`

**Frontmatter pattern** (summarize_v1.md lines 1–9):
```markdown
---
prompt_version: categorize_v1
phase: 3
purpose: Per-cluster category classification for AI Digest
---
```

**Loader** (summarize.py lines 99–106):
```python
def _load_prompt_body() -> str:
    raw = PROMPT_PATH.read_text(encoding="utf-8")
    if raw.startswith("---"):
        parts = raw.split("---", 2)
        if len(parts) >= 3:
            return parts[2].strip()
    return raw.strip()
```

**D-48 soft hint:** Include `source_typically_covers: <tag>` when present; instruction: "hint, not a constraint."

**D-57 voice:** Ban list + 1–2 bad-vs-good examples in both rollup prompts.

---

### `pipeline/budget.py` (utility, event-driven)

**Serves:** D-59, D-60  
**RESEARCH:** Focus Area 6

**Analog:** `pipeline/orchestrator.py::RunStats` cost accumulator (lines 65–76, 354–355)

**Pattern role:** `WeekBudget` dataclass — reservation + pre-flight + mid-run check; integrates with `RunStats.cost_usd_estimate`

**Core shape** (RESEARCH Focus 6):
```python
@dataclass
class WeekBudget:
    cap_usd: float
    reserved_meta_usd: float
    spent_usd: float = 0.0
    halted: bool = False
    halted_at_stage: str | None = None

    def can_afford(self, estimated_usd: float, *, stage: str) -> bool: ...
    def record_spend(self, amount: float, *, stage: str) -> None: ...
    def halt_if_over_cap(self, *, stage: str) -> None: ...
```

**Orchestrator gate** (RESEARCH code example):
```python
if not budget.can_afford(estimate_per_item, stage="summarize"):
    budget.halt_if_over_cap(stage="summarize")
    break
budget.record_spend(result.cost_usd_estimate, stage="summarize")
stats.cost_usd_estimate += result.cost_usd_estimate or 0.0
```

**D-60:** Meta stages (`categorize`, `rank`, `rollup`) run if reservation intact even when summarize halted.

---

### `pipeline/cascade.py` (utility, transform)

**Serves:** D-68  
**RESEARCH:** Focus Area 7

**Analog:** `pipeline/week.py` — pure functions, no I/O

**Pattern role:** Pure `plan_invalidation(...) -> set[str]` returning stages to rerun

**Core shape** (RESEARCH Focus 7):
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
) -> set[str]:  # {"summarize", "dedup", "rank", "rollup"}
```

**Trigger hook:** Call from `orchestrator._ingest_pending_transcripts` after `content_hash` update (orchestrator.py lines 593–608).

---

### `pipeline/reporting/pipeline_report.py` (service, transform)

**Serves:** D-69, D-70, OBS-02, D-09  
**RESEARCH:** Focus Area 5

**Analog:** `pipeline/reporting/last_run.py::write_last_run_md` + `store/db.py::finalize_pipeline_run`

**Pattern role:** JSON projection from `RunStats` + SQL aggregates — not a parallel substrate

**Write shape** (mirror last_run.py lines 61–68):
```python
def write_pipeline_report(
    stats: RunStats,
    *,
    budget: WeekBudget,
    stage_metrics: dict,
    out_dir: Path | None = None,
) -> tuple[Path, Path]:
    """Write out/pipeline-report-{week_id}.json AND out/pipeline_report.json."""
    target_dir = out_dir or Path("out")
    target_dir.mkdir(parents=True, exist_ok=True)
    payload = {"schema_version": 1, "week_id": stats.week_id, ...}
    per_week = target_dir / f"pipeline-report-{stats.week_id}.json"
    latest = target_dir / "pipeline_report.json"
```

**Required top-level keys** (D-70): `stages`, `source_health`, `summary_status` counts, `budget`.

---

### `config/digest.yaml` (config)

**Serves:** D-43, D-51, D-59, D-60  
**RESEARCH:** Standard Stack (PyYAML)

**Analog:** `config/sources.yaml` + `pipeline/config.py::load_sources`

**Suggested shape:**
```yaml
top_n_briefing: 5
dedup:
  title_fuzzy_threshold: 0.85
pipeline:
  hard_stop_usd: 2.0
  meta_reservation_usd: 0.10
models:
  categorize: gemini-2.5-flash-lite
  rank: gemini-2.5-flash
  rollup: gemini-2.5-flash
```

**Loader pattern** (config.py lines 101–114):
```python
def load_digest_config(path: Path | str | None = None) -> DigestConfig:
    cfg_path = Path(path) if path is not None else DEFAULT_DIGEST_PATH
    raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    return DigestConfig.model_validate(raw)
```

**D-49 validator:** Extend `_SourceBase` or `SourcesFile` — when `tag` present, must be one of four category enum strings.

---

### `store/migrations/004_dedup_categorize_rank_rollup.sql` (migration)

**Serves:** D-44, D-54, D-55, PIPELINE-05  
**RESEARCH:** Focus Area 8

**Analog:** `store/migrations/003_summary_status.sql` + `002_expand_ingestion.sql`

**Pattern role:** Additive idempotent SQLite migration with column guards (runner swallows duplicate-column)

**Migration comment header** (003_summary_status.sql lines 1–17):
```sql
-- Phase 3: dedup + categorize + rank + rollup tables.
-- Idempotent: store/db.py swallows "duplicate column name" on re-run.
CREATE TABLE IF NOT EXISTS story_clusters (...);
CREATE TABLE IF NOT EXISTS cluster_members (...);
CREATE TABLE IF NOT EXISTS cluster_summaries (...);
CREATE TABLE IF NOT EXISTS cluster_ranks (...);
CREATE TABLE IF NOT EXISTS weekly_rollups (...);
```

**Runner** (db.py lines 62–83):
```python
for migration in sorted(MIGRATIONS_DIR.glob("*.sql")):
    ...
    try:
        conn.execute(stmt)
    except sqlite3.OperationalError as exc:
        if "duplicate column name" in str(exc).lower():
            continue
        raise
```

**Persist on every LLM row:** `prompt_version`, `model_id` (D-04, D-54, D-55).

---

### `store/db.py` (extend) (model/store, CRUD)

**Serves:** D-67, PIPELINE-05, PIPELINE-06

**Analog:** `get_existing_summary` / `insert_item_summary` (db.py lines 292–323)

**New helpers pattern:**
```python
def get_existing_cluster_summary(conn, cluster_id, week_id, prompt_version) -> Row | None: ...
def insert_cluster_summary(conn, *, cluster_id, week_id, category, category_confidence, category_status, prompt_version, model_id, ...) -> str: ...
def get_clusters_for_week(conn, week_id) -> list[Row]: ...
def insert_story_cluster(conn, ...) -> str: ...
```

**UNIQUE skip key:** `(cluster_id, week_id, prompt_version)` on summaries/ranks (RESEARCH Focus 8).

---

### `pipeline/orchestrator.py` (extend) (service, batch)

**Serves:** DEDUP-04, D-67, D-68, D-60, D-71  
**RESEARCH:** Focus Area 10 (pipeline reorder)

**Analog:** Self — `run_summarize`, `_summarize_week_items`, `run_all`

**Pattern role:** New stages slot **between ingest and summarize**; new public entry points mirror existing trio

**Stage order change** (DEDUP-04 — critical 3-01 reorder):
```python
# run_all: ingest → dedup → summarize (canonical only) → categorize → rank → rollup → render
def run_dedup(week_id: str, *, db_path=...) -> RunStats: ...
def run_categorize(week_id: str, *, db_path=...) -> RunStats: ...
def run_rank(week_id: str, *, db_path=...) -> RunStats: ...
def run_rollup(week_id: str, *, db_path=...) -> RunStats: ...
```

**RunStats extension** (lines 65–76):
```python
@dataclass
class RunStats:
    ...
    clusters_created: int = 0
    stage_durations_ms: dict[str, int] = field(default_factory=dict)
```

**Per-run wrapper** (mirror run_summarize lines 690–714):
```python
with connect(db_path) as conn:
    run_id = insert_pipeline_run(conn, week_id=week_id, phase="dedup")
    try:
        _dedup_week(...)
        _finalize(conn, run_id, stats, phase="dedup")
    except Exception as exc:
        ...
```

**Summarize canonical-only gate** (RESEARCH code example):
```python
for cluster in get_clusters_for_week(conn, week_id):
    if not cluster.is_canonical_item(item_id):
        continue
    ...
```

---

### `pipeline/render/html.py` (extend) (component, transform)

**Serves:** D-63..D-66, D-64, LOCKED-01, DISPLAY-03  
**RESEARCH:** Focus Area 9 (partition rules)

**Analog:** Self — `_partition_cards`, `QUOTA_BODY_COPY`, `_render_pipeline_notice`

**Pattern role:** Extend `_partition_cards` for item routing only; **separate helpers** for Briefing, category sections, rollups — do NOT duplicate footer logic (RESEARCH Focus 9)

**LOCKED-01 router** (lines 211–232) — extend, do not fork:
```python
def _partition_cards(cards: list[DigestCard]) -> tuple[list[DigestCard], list[DigestCard]]:
    main_feed: list[DigestCard] = []
    also_seen: list[DigestCard] = []
    for card in cards:
        if _is_healthy(card) or _is_quota_in_place(card):
            main_feed.append(card)
        else:
            also_seen.append(card)
    return main_feed, also_seen
```

**New locked-string constants** (mirror line 49):
```python
QUOTA_BODY_COPY = "The summary couldn't be generated this week."
WEEKLY_ROLLUP_FAILURE_COPY = "This week's narrative roll-up couldn't be generated. The Top N stories are below."
PARTIAL_BUDGET_NOTICE = "Pipeline cost estimate exceeded the weekly budget; this week's digest reflects what completed before the cap."
```

**Briefing section** (D-63 — class names for Phase 4):
```html
<section class="briefing">
  <h2>Briefing — Top {n} this week</h2>
  <ol class="briefing-list">...</ol>
</section>
```

**Cluster attribution** (D-64):
```html
<p class="also-covered">Also covered by <a href="...">Source B</a>, <a href="...">Source C</a></p>
```

**Category sections** (D-65): `<h2>Technical</h2>` + mini-rollup paragraph + ranked cards; no per-card category badge.

**Footer aside unchanged:** `<aside id="also-seen">` stays exactly as LOCKED-01 (lines 269–292).

---

### `pipeline/run.py` (extend) (route/CLI, request-response)

**Serves:** D-22, D-19  
**RESEARCH:** Focus Area 10

**Analog:** Self — subcommand registration (lines 76–102)

**Pattern role:** Module-level CLI subcommand registered in `pipeline/run.py`; lazy orchestrator imports

**Subcommand registration** (lines 78–95):
```python
dedup_cmd = sub.add_parser("dedup", help="Cluster same-story items for the week (deterministic).")
_add_week_arg(dedup_cmd)
categorize_cmd = sub.add_parser("categorize", help="Classify story clusters into edtech|business|technical|design.")
# rank, rollup — same shape
```

**Dispatch** (lines 142–158):
```python
elif command == "dedup":
    from pipeline.orchestrator import run_dedup
    stats = run_dedup(week_id)
```

**New flags** (D-22 triad — README + `--help` + UAT): `--top-n`, `--max-cost-usd`, `--rebuild-clusters`, `--rebuild-rollup`.

**Update `all` help:** `ingest → dedup → summarize → categorize → rank → rollup → render`.

---

### `pipeline/config.py` (extend) (config)

**Serves:** D-48, D-49, D-51, D-59

**Analog:** Self — `SourceConfig` discriminated union (lines 91–94)

**Tag validator for D-49:**
```python
_VALID_TAGS = frozenset({"edtech", "business", "technical", "design"})

@field_validator("tag")
@classmethod
def _tag_is_category(cls, value: str | None) -> str | None:
    if value is not None and value not in _VALID_TAGS:
        raise ValueError(f"tag must be one of {_VALID_TAGS}: {value!r}")
    return value
```

---

### `pipeline/llm/summarize.py` (extend)

**Serves:** LOCKED-01, RESEARCH Focus 9

**Change:** Replace local `_classify_llm_exception` with import from `pipeline.llm.exceptions`; re-export for backward compat if tests import it.

---

### `pipeline/reporting/last_run.md` path — `last_run.py` (extend)

**Serves:** D-70 (technical surface), D-24

**Analog:** Self — extend `RunSummary` dataclass (lines 15–31)

**Extension:**
```python
@dataclass
class RunSummary:
    ...
    clusters_created: int = 0
    categorize_calls: int = 0
    rank_calls: int = 0
    rollup_calls: int = 0
```

Technical surface may use CLI command names; digest HTML may not (D-24).

---

## Test Patterns

### `tests/test_categorize.py`, `test_rank.py`, `test_rollup.py`

**Analog:** `tests/test_summarize.py`

**Mock client pattern** (test_summarize.py lines 30–49):
```python
def _mock_genai_response(*, parsed: BaseModel, input_tokens=100, output_tokens=40) -> MagicMock:
    response = MagicMock()
    response.parsed = parsed
    response.usage_metadata = MagicMock(prompt_token_count=input_tokens, candidates_token_count=output_tokens)
    return response

def test_invalid_enum_falls_back_to_source_tag(monkeypatch) -> None:
    ...
```

**DB checkpoint test** (test_summarize.py + db helpers):
```python
existing = get_existing_cluster_summary(conn, cluster_id, week_id, "categorize_v1")
assert existing is not None  # second run skips LLM
```

---

### `tests/test_dedup_url.py`

**Analog:** `pipeline/adapters/rss.py` + `pytest-httpx`

**Pattern:** Hermetic URL fixtures; assert deny-list stripping and 85.0 boundary separate from fuzzy tests.

---

### `tests/test_dedup_fuzzy.py`

**Analog:** None — use `tests/fixtures/dedup/title_pairs.json` per RESEARCH Validation.

---

### `tests/test_dedup_cluster.py`

**Analog:** `tests/test_store.py` — `apply_schema` fixture (conftest.py lines 23–34)

```python
def test_cluster_members_preserves_all_sources(apply_schema: Path) -> None:
    ...
    assert len(members) == 3  # DEDUP-03
```

---

### `tests/test_pipeline_dedup_order.py`

**Analog:** `tests/test_pipeline.py::test_run_all_finalizes_pipeline_run`

**Pattern:** Monkeypatch adapters + summarize; assert non-canonical members have no `item_summaries` row (DEDUP-04).

---

### `tests/test_render_idempotent.py`, `tests/test_render.py` (extend)

**Analog:** `tests/test_render.py`

**LOCKED-01 tests** (lines 1–20 docstring, `_card` helper lines 35–57):
```python
def test_briefing_section_renders_top_n(tmp_path: Path) -> None:
    out = render_digest(..., briefing_cluster_ids=[...], top_n=5)
    body = out.read_text(encoding="utf-8")
    assert 'class="briefing"' in body
    assert "Briefing — Top 5 this week" in body

def test_weekly_rollup_failure_shows_placeholder(tmp_path: Path) -> None:
    ...
    assert WEEKLY_ROLLUP_FAILURE_COPY in body
    assert "<aside id=\"also-seen\">" in body  # footer unchanged LOCKED-01
```

---

### `tests/test_checkpoint.py`

**Analog:** `orchestrator._summarize_week_items` skip pattern + `test_summarize.py` DB tests

**Serves:** PIPELINE-06, D-67

---

### `tests/test_pipeline_report.py`

**Analog:** `tests/test_pipeline.py`

**Assert:** `schema_version == 1`, `stages.dedup.clusters_created`, `budget.halted` (OBS-02).

---

### `tests/test_budget.py`

**Analog:** Unit-test `WeekBudget` in isolation (no DB)

**D-60 UAT helper:** test `can_afford` summarize pool vs meta pool separately.

---

### Shared fixture

**Source:** `tests/conftest.py::apply_schema` — all integration tests use on-disk SQLite via `init_db`.

---

## Shared Patterns

### LOCKED-01 reader-surface routing

**Source:** `pipeline/render/html.py::_partition_cards`  
**Apply to:** Item-level cards only; cluster category failures use DB `category_status` + source-tag fallback (D-49); rollups use separate render helpers  
**Compliance:** Phase 3 extends — does not relax — LOCKED-01

```python
# Only quota_exhausted earns in-place main-feed slot for item summaries
_IN_PLACE_TRANSIENT_STATUSES = frozenset({"quota_exhausted"})
```

### LLM module shape (all four new stages)

**Source:** `pipeline/llm/summarize.py`  
**Apply to:** `categorize.py`, `rank.py`, `rollup.py`

1. Module constants: `PROMPT_VERSION`, `MODEL_ID`, `PROMPT_PATH`
2. Pydantic `*Response` + `*Result` models with `*_status` field
3. `_load_prompt_body()`, `_build_client()`, `_estimate_cost()`
4. `@retry` on `_generate()`
5. `classify_llm_exception()` from `exceptions.py`
6. Persist `prompt_version` + `model_id` on every row (D-04)

### Orchestrator run_* wrapper

**Source:** `pipeline/orchestrator.py::run_summarize` (lines 690–714)  
**Apply to:** `run_dedup`, `run_categorize`, `run_rank`, `run_rollup`

```python
init_db(db_path)
stats = RunStats(week_id=week_id, phase="categorize")
with connect(db_path) as conn:
    run_id = insert_pipeline_run(conn, week_id=week_id, phase="categorize")
    try:
        _categorize_week_clusters(...)
        _finalize(conn, run_id, stats, phase="categorize")
        write_pipeline_report(stats, ...)
        return stats
    except Exception as exc:
        finalize_pipeline_run(conn, run_id, status="failed", ...)
        raise
```

### Typed error taxonomy

**Source:** `pipeline/orchestrator.py::_append_ingest_error` (lines 96–121)  
**Apply to:** New failure categories: `dedup_internal`, `categorize_invalid_enum`, `rank_partial`, `rollup_synthesis_failed`

```python
stats.errors.append({
    "phase": "categorize",
    "category": "categorize_invalid_enum",
    "cluster_id": cluster_id,
    "message": "...",
})
```

### Week parameterization (no `datetime.now()` in modules)

**Source:** `pipeline/week.py`  
**Apply to:** All new modules accept `week_id: str`; orchestrator resolves bounds once

### HTML escaping on reader strings

**Source:** `pipeline/render/html.py::_render_card` (lines 245–247)  
**Apply to:** All new reader-surface copy (D-24, RESEARCH Security)

```python
title_safe = html.escape(card.title)
```

### Lazy LLM imports (D-20)

**Source:** `pipeline/orchestrator.py` lines 268, 696  
**Apply to:** `run_render` path must not import categorize/rank/rollup modules

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `pipeline/dedup/title_fuzzy.py` | utility | transform | First fuzzy-match module; follow RESEARCH §Focus 1 verbatim |
| `tests/test_dedup_fuzzy.py` | test | — | No prior RapidFuzz tests; fixture-driven from RESEARCH Validation |

---

## Metadata

**Analog search scope:** `pipeline/`, `store/`, `config/`, `tests/`, `.planning/LOCKED-DIRECTIVES.md`  
**Files scanned:** ~45 source + test files  
**Pattern extraction date:** 2026-05-22  
**Planner must cite:** Decision IDs (D-43..D-71) per task; LOCKED-01 on every render/routing task; RESEARCH Focus Area numbers for implementation details
