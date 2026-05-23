# Phase 4: Dashboard + Archive - Pattern Map

**Mapped:** 2026-05-23
**Files analyzed:** 38 new/modified files
**Analogs found:** 12 / 38 (Python + config); 26 Astro/web files have no in-repo analog

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `pipeline/render/digest_json.py` | service | file-I/O + transform | `pipeline/render/html.py` | exact |
| `pipeline/render/partition.py` | utility | transform | `pipeline/render/html.py` (extract source) | exact |
| `pipeline/render/html.py` | service | transform | self (deprecated dev-preview) | exact |
| `pipeline/render/__init__.py` | config | — | `pipeline/reporting/__init__.py` | role-match |
| `pipeline/orchestrator.py` | service | batch | self (`run_render` / `_finalize`) | exact |
| `pipeline/reporting/pipeline_report.py` | service | file-I/O | self (`write_pipeline_report`) | exact |
| `pipeline/run.py` | utility | request-response (CLI) | self (`render` subcommand) | exact |
| `.gitignore` | config | — | self (existing `out/` entry) | exact |
| `tests/render/test_digest_json_*.py` | test | — | `tests/render/test_partition_cards_phase3.py` | role-match |
| `web/package.json` | config | — | no in-repo analog | none |
| `web/pnpm-lock.yaml` | config | — | no in-repo analog | none |
| `web/.nvmrc` | config | — | no in-repo analog | none |
| `web/astro.config.mjs` | config | — | no in-repo analog | none |
| `web/tsconfig.json` | config | — | no in-repo analog | none |
| `web/src/content.config.ts` | config | transform (Zod validate) | no in-repo analog | none |
| `web/src/content/digests/{week_id}.json` | model (data) | file-I/O | `out/pipeline-report-{week_id}.json` (committed JSON shape) | data-flow-match |
| `web/src/content/reports/{week_id}.json` | model (data) | file-I/O | `out/pipeline-report-{week_id}.json` | exact |
| `web/src/pages/index.astro` | component/route | request-response (SSG) | no in-repo analog | none |
| `web/src/pages/[topic].astro` | component/route | request-response (SSG) | no in-repo analog | none |
| `web/src/pages/digest/[week].astro` | component/route | request-response (SSG) | no in-repo analog | none |
| `web/src/pages/digest/[week]/[topic].astro` | component/route | request-response (SSG) | no in-repo analog | none |
| `web/src/pages/archive.astro` | component/route | request-response (SSG) | no in-repo analog | none |
| `web/src/components/*.astro` | component | transform | `pipeline/render/html.py` (HTML string builders) | partial (presentational port) |
| `web/src/styles/globals.css` | config | — | `pipeline/render/html.py::_CSS` | partial (palette source) |
| `web/src/lib/*.ts` | utility | transform | `pipeline/render/html.py` (`_format_week_header`) + `pipeline/week.py` | partial |
| `.planning/REQUIREMENTS.md` | docs | — | self | exact |
| `.planning/LOCKED-DIRECTIVES.md` | docs | — | self | exact |

---

## Pattern Assignments

### `pipeline/render/partition.py` (utility, transform) — NEW extract

**Analog:** `pipeline/render/html.py`

**Module docstring pattern** (lines 1–47 of `html.py`):
```python
"""Plain-HTML weekly digest renderer.

PROJECT.md **LOCKED** directive (2026-05-22, refined 2026-05-23): the only
items that route to the ``<aside id="also-seen">`` footer are those whose
RSS body is genuinely too short to summarize (``summary_status='thin'``).
...
Import boundary: this module must NOT import adapters or LLM packages —
it only consumes pre-built ``DigestCard`` records (D-20).
"""
```

**Constants + routing statuses** (lines 59–98):
```python
DEFAULT_OUT_DIR = Path("out")
VIDEO_INDICATOR = "[video]"
QUOTA_BODY_COPY = "The summary couldn't be generated this week."
ALSO_COVERED_PREFIX = "Also covered by "
ALSO_COVERED_SEPARATOR = ", "
CATEGORY_ORDER = ("edtech", "business", "technical")
CATEGORY_LABELS = {
    "edtech": "Edtech",
    "business": "Business",
    "technical": "Technical",
}
DEFAULT_CATEGORY = "technical"
BRIEFING_HEADER_TEMPLATE = "Briefing — Top {n} this week"
WEEKLY_ROLLUP_FAILURE_COPY = (
    "This week's narrative roll-up couldn't be generated. The Top {n} stories are below."
)
PARTIAL_PUBLISH_COPY = (
    "Pipeline cost estimate exceeded the weekly budget; this week's digest reflects "
    "what completed before the cap."
)
_IN_PLACE_TRANSIENT_STATUSES = frozenset(
    {"quota_exhausted", "api_error", "parse_error", "client_init_error", "transcript_missing"}
)
```

**Note:** UI-SPEC/D-A4c locks a longer `PARTIAL_PUBLISH_COPY` string — planner must reconcile to UI-SPEC verbatim when moving constants to `partition.py`.

**Dataclass card types** (lines 101–132):
```python
@dataclass(frozen=True)
class AlsoCoveredMember:
    display_name: str
    url: str

@dataclass(frozen=True)
class DigestCard:
    title: str
    publisher: str
    canonical_url: str
    published_at: datetime
    tldr: str | None
    summary_confidence: str
    source_type: str = "rss"
    transcript_status: str | None = None
    summary_status: str | None = None
    also_covered: tuple[AlsoCoveredMember, ...] = ()
    category: str | None = None
    rank_position: int | None = None
```

**LOCKED-01 router — single source of truth** (lines 321–363):
```python
def _is_quota_in_place(card: DigestCard) -> bool:
    return card.summary_status in _IN_PLACE_TRANSIENT_STATUSES

def _is_healthy(card: DigestCard) -> bool:
    return bool(card.tldr and card.tldr.strip())

def _partition_cards(
    cards: list[DigestCard],
) -> tuple[list[DigestCard], list[DigestCard]]:
    main_feed: list[DigestCard] = []
    also_seen: list[DigestCard] = []
    for card in cards:
        if _is_healthy(card) or _is_quota_in_place(card):
            main_feed.append(card)
        else:
            also_seen.append(card)
    return main_feed, also_seen
```

**Category grouping helpers to co-locate** (lines 477–500):
```python
def _effective_category(card: DigestCard) -> str:
    if card.category in CATEGORY_LABELS:
        return card.category
    return DEFAULT_CATEGORY

def _card_section_sort_key(card: DigestCard) -> tuple[int, float, float]:
    if card.rank_position is not None:
        return (0, float(card.rank_position), 0.0)
    return (1, 0.0, -card.published_at.timestamp())

def _group_main_feed_by_category(
    main_feed: list[DigestCard],
) -> dict[str, list[DigestCard]]:
    grouped: dict[str, list[DigestCard]] = {key: [] for key in CATEGORY_ORDER}
    for card in main_feed:
        grouped[_effective_category(card)].append(card)
    for key in grouped:
        grouped[key].sort(key=_card_section_sort_key)
    return grouped
```

**Re-export contract:** `html.py` imports from `partition.py`; existing tests import `DigestCard`, `QUOTA_BODY_COPY`, `render_digest` from `html.py` — keep backward-compatible re-exports until tests are updated.

---

### `pipeline/render/digest_json.py` (service, file-I/O + transform) — NEW

**Analog:** `pipeline/render/html.py` (`render_digest` orchestration) + `pipeline/llm/summarize.py` (Pydantic models)

**Imports pattern** (follow `html.py` boundary — no adapter/LLM imports):
```python
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import structlog
from pydantic import BaseModel, Field

from pipeline.render.partition import (
    BRIEFING_HEADER_TEMPLATE,
    CATEGORY_ORDER,
    CATEGORY_LABELS,
    DigestCard,
    PARTIAL_PUBLISH_COPY,
    QUOTA_BODY_COPY,
    WEEKLY_ROLLUP_FAILURE_COPY,
    _group_main_feed_by_category,
    _partition_cards,
    _rollup_row_value,  # or move rollup helpers to shared module
)
from pipeline.week import week_bounds

logger = structlog.get_logger(__name__)

DEFAULT_WEB_CONTENT_DIR = Path("web/src/content/digests")
```

**Pydantic model pattern** (from `pipeline/llm/summarize.py` lines 48–68):
```python
class SummaryResponse(BaseModel):
    """Structured-output contract — must match the schema in summarize_v1.md."""
    summary: str | None = Field(default=None)
    reason: str | None = Field(default=None)
```

**Apply to digest JSON** (RESEARCH Pattern 3 — snake_case, `model_dump_json`):
```python
class AlsoCoveredJson(BaseModel):
    display_name: str
    url: str

class DigestCardJson(BaseModel):
    title: str
    publisher: str
    canonical_url: str
    published_at: str  # UTC ISO8601 via .strftime("%Y-%m-%dT%H:%M:%SZ")
    tldr: str | None
    summary_status: str | None
    source_type: str = "rss"
    also_covered: list[AlsoCoveredJson] = Field(default_factory=list)
    category: str | None = None
    rank_position: int | None = None
    degraded_body: str | None = None  # QUOTA_BODY_COPY when in-place degraded

class DigestDocument(BaseModel):
    schema_version: Literal[1] = 1
    week_id: str
    generated_at: str
    week_range: dict[str, str]  # {start, end} ISO8601
    updated_at: str
    weekly_synthesis: dict[str, str | None]
    briefing_top_n: list[DigestCardJson]
    category_sections: dict[str, dict]  # edtech|business|technical → {mini_rollup, cards}
    main_feed: list[DigestCardJson]
    footer_aside: list[DigestCardJson]
    pipeline_notes: dict
    failure_notice: dict[str, str] | None = None
```

**Card serialization helper** (mirror `_render_body` logic from html.py lines 366–372):
```python
def _card_to_json(card: DigestCard) -> DigestCardJson:
    from pipeline.render.partition import _is_healthy, _is_quota_in_place
    degraded = None
    if _is_quota_in_place(card) and not _is_healthy(card):
        degraded = QUOTA_BODY_COPY
    return DigestCardJson(
        title=card.title,
        publisher=card.publisher,
        canonical_url=card.canonical_url,
        published_at=card.published_at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        tldr=card.tldr,
        summary_status=card.summary_status,
        source_type=card.source_type,
        also_covered=[AlsoCoveredJson(display_name=m.display_name, url=m.url) for m in card.also_covered],
        category=card.category,
        rank_position=card.rank_position,
        degraded_body=degraded,
    )
```

**Briefing Top-N selection** (copy from html.py lines 583–604):
```python
def _select_briefing_top_n(main_feed: list[DigestCard], *, top_n: int) -> list[DigestCard]:
    ranked = [card for card in main_feed if card.rank_position is not None]
    ranked.sort(key=lambda c: c.rank_position)
    return ranked[:top_n]
```

**Main emit function** (mirror `render_digest` signature from html.py lines 608–640):
```python
def emit_digest_json(
    *,
    week_id: str,
    week_start: datetime,
    week_end: datetime,
    cards: list[DigestCard],
    out_dir: Path | None = None,
    rollups_by_scope: dict[str, object] | None = None,
    partial_publish: bool = False,
    top_n_briefing: int | None = None,
    pipeline_report: dict | None = None,  # OBS-01 inputs
    conn=None,  # silent-source consecutive-week query (D-A4b)
) -> Path:
    out_root = out_dir or DEFAULT_WEB_CONTENT_DIR
    out_root.mkdir(parents=True, exist_ok=True)
    out_path = out_root / f"{week_id}.json"

    from pipeline.config import load_digest_config
    top_n = top_n_briefing or load_digest_config().top_n_briefing

    main_feed, footer_aside = _partition_cards(cards)
    grouped = _group_main_feed_by_category(main_feed)
    # ... build DigestDocument ...
    doc = DigestDocument(...)
    out_path.write_text(doc.model_dump_json(indent=2) + "\n", encoding="utf-8")
    logger.info("digest_json.written", week_id=week_id, path=str(out_path))
    return out_path
```

**Week header formatting** — reuse or move from html.py (lines 301–314):
```python
def _day_label(dt: datetime) -> str:
    local = dt.astimezone(UTC)
    return f"{local.strftime('%b')} {local.day}"

def _format_week_header(week_start: datetime, week_end: datetime) -> str:
    return f"Week of {_day_label(week_start)} – {_day_label(week_end)}, {week_end.year}"
```

**JSON write pattern** (from `pipeline/reporting/pipeline_report.py` lines 261–265):
```python
text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
per_week.write_text(text, encoding="utf-8")
```
Prefer Pydantic `model_dump_json(indent=2)` for digest; keep trailing newline convention.

---

### `pipeline/render/html.py` (service, transform) — MODIFY (deprecated)

**Analog:** self

**Deprecation pattern:** Add module-level note + docstring `DEPRECATED` banner; import partition types instead of defining them. Keep `render_digest()` callable for dev preview.

**Public entry unchanged** (lines 608–640) — orchestrator continues calling until flags add `--no-html-preview`.

**Presentational patterns to preserve for Astro port reference:**
- External links: `target="_blank" rel="noopener"` (line 384, 410)
- Video indicator: `source_type == "youtube"` branch (lines 396–399) → becomes `PlayIcon.astro`
- Pipeline notice zero-state: empty string return (lines 444–451)
- Category sections omit empty buckets (lines 557–580)

---

### `pipeline/render/__init__.py` (config) — MODIFY

**Analog:** `pipeline/reporting/__init__.py`

**Current** (line 1):
```python
"""Render pipeline — Phase 1 plain HTML; Phase 4 swaps in Astro dashboard."""
```

**Target pattern** (from `pipeline/reporting/__init__.py` + `pipeline_report.py` `__all__`):
```python
"""Render pipeline — JSON archive emitter + deprecated HTML dev preview."""
from pipeline.render.digest_json import emit_digest_json
from pipeline.render.html import render_digest
from pipeline.render.partition import DigestCard

__all__ = ["DigestCard", "emit_digest_json", "render_digest"]
```

---

### `pipeline/orchestrator.py` (service, batch) — MODIFY

**Analog:** self — `run_render` + `_finalize` + `run_all` render block

**Current imports** (line 26):
```python
from pipeline.render.html import AlsoCoveredMember, DigestCard, render_digest
```

**Phase 4 wiring target:** import `emit_digest_json` from `digest_json`; import `DigestCard` from `partition`.

**Render-only entry point** (lines 1733–1772) — extend after `render_digest`:
```python
def run_render(
    week_id: str,
    *,
    db_path: Path | str | None = None,
    out_dir: Path | None = None,
    top_n_briefing: int | None = None,
) -> RunStats:
    """Render HTML from existing SQLite data — no network, no LLM (D-20)."""
    # ...
    cards = _build_cards_from_db(conn, week_rows, week_id)
    pending, failed = _pipeline_notice_counts(cards=cards, stats=stats)
    stats.out_path = render_digest(...)  # dev preview → out/digest-{week_id}.html
    # ADD: emit_digest_json(...) → web/src/content/digests/{week_id}.json
    # ADD: write archive report → web/src/content/reports/{week_id}.json
    _finalize(conn, run_id, stats, phase="render", out_dir=out_dir)
```

**Pipeline notice inputs** (lines 1097–1113) — emitter expands beyond this for OBS-01:
```python
def _pipeline_notice_counts(*, cards: list[DigestCard], stats: RunStats) -> tuple[int, int]:
    pending = sum(1 for c in cards if c.transcript_status == "pending_local")
    failed_sources = sum(
        1 for err in stats.errors
        if err.get("phase") == "ingest" and err.get("category") not in (None, "empty_feed")
    )
    return pending, failed_sources
```

**Finalize + report write** (lines 1237–1267):
```python
def _finalize(conn, run_id, stats, *, phase, budget=None, out_dir=None) -> None:
    status = "success" if not stats.errors else "partial"
    if budget is not None and budget.halted:
        status = "partial"
    finalize_pipeline_run(conn, run_id, status=status, ...)
    conn.commit()
    write_pipeline_report(conn, stats, run_id=run_id, status=status, budget=budget, out_dir=out_dir)
```

**`run_all` render block** (lines 1919–1940) — same dual emit; pass `partial_publish=budget.halted`.

---

### `pipeline/reporting/pipeline_report.py` (service, file-I/O) — MODIFY

**Analog:** self — `write_pipeline_report`

**Schema anchor** (lines 203–243):
```python
return {
    "schema_version": 1,
    "week_id": week_id,
    "generated_at": _utc_now_iso(),
    "run_id": run_id,
    "status": status,
    "summary_status": _summary_status_counts(conn, week_id),
    "stages": { ... },
    "source_health": _source_health_snapshot(conn, week_id),
    "budget": budget_block,
}
```

**Write pattern to extend** (lines 246–266):
```python
def write_pipeline_report(..., out_dir: Path | None = None) -> tuple[Path, Path]:
    target_dir = out_dir or DEFAULT_OUT_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    payload = build_pipeline_report(...)
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    per_week = target_dir / f"pipeline-report-{stats.week_id}.json"
    latest = target_dir / "pipeline_report.json"
    per_week.write_text(text, encoding="utf-8")
    latest.write_text(text, encoding="utf-8")
    return per_week, latest
```

**Phase 4 addition:** third write to `Path("web/src/content/reports") / f"{stats.week_id}.json"` (filename `{week_id}.json` not `pipeline-report-{week_id}.json` per content collection convention). Shape identical — only path differs. Consider `write_pipeline_report_archive(conn, stats, ...)` or optional `archive_dir` parameter to avoid breaking existing callers.

**UTC timestamp helper** (lines 30–31):
```python
def _utc_now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
```

---

### `pipeline/run.py` (utility, CLI) — MODIFY

**Analog:** self — subcommand + flag wiring

**Subparser pattern** (lines 162–167):
```python
render_cmd = sub.add_parser(
    "render",
    help="Render HTML digest from SQLite (no network, no LLM).",
)
_add_week_arg(render_cmd)
_add_phase3_flags(render_cmd)
```

**Flag helper pattern** (lines 65–95):
```python
def _add_phase3_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--top-n",
        dest="top_n_briefing",
        type=int,
        default=None,
        metavar="N",
        help="Override config/digest.yaml top_n_briefing for Briefing section size.",
    )
```

**Phase 4 flags to add on `render_cmd` only** (D-22 triad — README + `--help` + UAT):
```python
parser.add_argument(
    "--no-html-preview",
    action="store_true",
    help="Skip deprecated out/digest-{week}.html dev preview; emit JSON archive only.",
)
parser.add_argument(
    "--web-out",
    dest="web_out_dir",
    type=Path,
    default=None,
    help="Override web/src/content/digests output directory for digest JSON.",
)
```

**Dispatch** (lines 228–231):
```python
elif command == "render":
    from pipeline.orchestrator import run_render
    stats = run_render(week_id, top_n_briefing=p3["top_n_briefing"])
```

**Stats printout** (lines 180–189) — extend `_print_stats` to show JSON path alongside `digest:` line.

---

### `.gitignore` (config) — MODIFY

**Analog:** existing `out/` entry (lines 7–8)

**Current:**
```
# Generated digest output (Phase 1 plain HTML; archive JSON moves to git in Phase 4)
out/
```

**Add under new `# Web / Astro` section:**
```
web/node_modules/
web/.astro/
web/dist/
```

**Do NOT ignore:** `web/src/content/digests/`, `web/src/content/reports/` — committed archive per D-A2a.

---

### `tests/render/test_digest_json_*.py` (test) — NEW

**Analog:** `tests/render/test_partition_cards_phase3.py`

**Fixture helper pattern** (lines 10–24):
```python
def _card(*, tldr: str | None, summary_status: str | None, title: str = "Story") -> DigestCard:
    return DigestCard(
        title=title,
        publisher="Example Publisher",
        canonical_url="https://example.com/post",
        published_at=datetime(2026, 5, 20, tzinfo=UTC),
        tldr=tldr,
        summary_confidence="unavailable" if not tldr else "high",
        summary_status=summary_status,
    )
```

**Partition parity tests:** After extract, import `_partition_cards` from `partition`; add JSON emitter tests asserting `main_feed`/`footer_aside`/`briefing_top_n` match HTML render lists for same card fixtures.

**Schema test:** Load emitted JSON → validate with `DigestDocument.model_validate(json.loads(...))`; assert `schema_version == 1`.

---

### Astro / `web/` scaffold — NO in-repo analog

**Reference:** `.planning/research/ARCHITECTURE.md` §Render Strategy + §Static-First Pattern (feedmeup precedent):

> Pipeline writes structured digest files → frontend build reads all weeks → generates `/digest/2026-W20`, `/archive`, tab routes.
>
> Git-tracked `content/digests/*.json` is the archive of record. The site is a **view** over that corpus.

**RESEARCH.md patterns to copy verbatim:**

1. **Content config path:** `web/src/content.config.ts` (Astro 6 — NOT `src/content/config.ts`)

2. **Tailwind 4 via Vite** (`04-RESEARCH.md` Code Examples):
```javascript
import { defineConfig } from 'astro/config';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  vite: { plugins: [tailwindcss()] },
});
```

3. **Zod collection** — see RESEARCH Pattern 1 (`defineCollection` + `glob` loader + `schema_version: z.literal(1)`)

4. **Nested getStaticPaths** — RESEARCH Pattern 2 for `/digest/[week]/[topic].astro`

5. **Design tokens** — copy verbatim from `04-UI-SPEC.md` `:root` block into `web/src/styles/globals.css`

**HTML → Astro component mapping** (presentational port from `html.py`):

| html.py builder | Astro component | Key behavior |
|-----------------|-----------------|--------------|
| header block | `Header.astro` | week range, updated, optional back-link |
| tab nav (implicit in future) | `TabBar.astro` | static `<a href>` only |
| `_render_pipeline_notice` | `PipelineNotes.astro` | `<details>`; omit DOM when zero-state |
| `_render_partial_publish_notice` | `PartialPublishNotice.astro` | amber band |
| `_render_weekly_synthesis_section` | `WeeklySynthesis.astro` | synthesis or failure copy |
| `_render_briefing_section` | `BriefingTopN.astro` | numbered `<ol>` |
| `_render_category_sections` | `CategorySection.astro` | mini-rollup + cards |
| `_render_card` | `Card.astro` | same outer structure all statuses (D-25) |
| `_render_also_seen` | `FooterAside.astro` | link-only thin items |
| video suffix | `PlayIcon.astro` | inline SVG, `aria-hidden="true"` |

**`web/src/lib/` helpers — partial Python analogs:**

| Helper | Python source |
|--------|---------------|
| `formatWeekRange(start, end)` | `html.py::_format_week_header` (lines 307–309) |
| `latestWeek()` | sort `getCollection('digests')` by `week_id` desc, take first |
| `canonicalUrl(weekId, topic?)` | D-A3b-extras — `/digest/{week}` or `/digest/{week}/{topic}` |

**Week bounds for JSON** — emitter uses `pipeline/week.py::week_bounds` (lines 48–60):
```python
def week_bounds(week_id: str) -> tuple[datetime, datetime]:
    year, week = parse_week_id(week_id)
    monday = date.fromisocalendar(year, week, 1)
    sunday = date.fromisocalendar(year, week, 7)
    week_start = datetime.combine(monday, time.min, tzinfo=UTC)
    week_end = datetime.combine(sunday, time(23, 59, 59), tzinfo=UTC)
    return week_start, week_end
```

---

## Shared Patterns

### Import boundary (render modules)

**Source:** `pipeline/render/html.py` module docstring (line 45–46)

Render modules must NOT import adapters or LLM packages — they consume pre-built `DigestCard` records only. `digest_json.py` and `partition.py` inherit this rule.

### structlog logging

**Source:** `pipeline/render/html.py` line 57, `pipeline/orchestrator.py` throughout

```python
import structlog
logger = structlog.get_logger(__name__)
logger.info("digest_json.written", week_id=week_id, path=str(out_path))
```

### ISO week parameterization (D-11)

**Source:** `pipeline/week.py` lines 1–7

`datetime.now()` lives ONLY in `week.py`. Render modules receive resolved `week_id`, `week_start`, `week_end` from orchestrator — never call `datetime.now()` inside `digest_json.py` except for `generated_at`/`updated_at` publish timestamps (same as html.py line 643).

### JSON artifact conventions

**Source:** `pipeline/reporting/pipeline_report.py`

- `schema_version: 1` literal on every committed JSON root
- `indent=2`, `ensure_ascii=False`, trailing `\n`
- UTC ISO8601 via `strftime("%Y-%m-%dT%H:%M:%SZ")`
- Per-week filename: `{week_id}.json` in content collections; `pipeline-report-{week_id}.json` in `out/`

### CLI discoverability (D-22)

**Source:** `pipeline/run.py`

Every new flag: argparse `help=` string + README section + UAT checklist item. Follow `_WEEK_HELP` / `_PENDING_TRANSCRIPTS_HELP` prose style (plain English, example values).

### Test card fixtures

**Source:** `tests/render/test_partition_cards_phase3.py`

Use `_card()` factory with explicit `tldr` + `summary_status` for LOCKED-01 routing tests. Import path will shift to `pipeline.render.partition` after extract.

### Orchestrator card building

**Source:** `pipeline/orchestrator.py` lines 1068+, 1756–1757

```python
week_rows = _canonical_rows_for_render(conn, week_rows, week_id=week_id)
cards = _build_cards_from_db(conn, week_rows, week_id)
```

Emitter receives same `cards` list as `render_digest` — guarantees partition parity.

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `web/**` (entire Astro project) | component/route/config | SSG | First frontend in repo; design from RESEARCH + UI-SPEC + ARCHITECTURE §Static-First |
| `web/src/content.config.ts` | config | transform | Astro 6 API — no TypeScript in pipeline repo today |
| `web/src/lib/*.ts` | utility | transform | New TS helpers; partial logic mirrors Python string formatters |
| OBS-01 silent-source counter | logic in emitter | batch | D-A4b 3+ consecutive empty weeks — new query against `pipeline_runs` history |

---

## Metadata

**Analog search scope:** `pipeline/render/`, `pipeline/orchestrator.py`, `pipeline/reporting/`, `pipeline/run.py`, `pipeline/week.py`, `pipeline/llm/summarize.py`, `tests/render/`, `.gitignore`, `.planning/research/ARCHITECTURE.md`
**Files scanned:** ~15 source files + 3 phase artifacts
**Pattern extraction date:** 2026-05-23

**Planner notes:**
1. Extract `partition.py` before `digest_json.py` — Wave 0 per RESEARCH MVP slices
2. Astro 6 path is `src/content.config.ts` not `src/content/config.ts` (CONTEXT drift)
3. Reconcile `PARTIAL_PUBLISH_COPY` in html.py vs UI-SPEC when moving constants
4. Update `.planning/LOCKED-DIRECTIVES.md` code anchors to cite `partition._partition_cards` + `digest_json` emitter
5. Do NOT install `@astrojs/react`, `astro-icon`, or shadcn CLI (locked decisions)
