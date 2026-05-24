# Phase 5: Ops & Automation - Pattern Map

**Mapped:** 2026-05-24
**Files analyzed:** 28 new/modified files
**Analogs found:** 18 / 28 (pipeline + web + docs); 10 greenfield (GHA workflows, worker Docker, shell entrypoint)

## File Classification

| New/Modified File | Role | Layer | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-------|-----------|----------------|---------------|
| `.github/workflows/weekly-digest.yml` | workflow | CI | batch + file-I/O | **none in repo** — [GHA workflow syntax](https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions) | greenfield |
| `.github/workflows/daily-retry.yml` | workflow | CI | batch | same as weekly-digest | greenfield |
| `.github/workflows/sentinel.yml` | workflow | CI | batch + verify | same as weekly-digest | greenfield |
| `.github/workflows/build-worker-image.yml` | workflow | CI | file-I/O (GHCR push) | [Docker multi-platform GHA](https://docs.docker.com/build/ci/github-actions/multi-platform/) | greenfield (official doc shape) |
| `worker/Dockerfile` | config | runtime | batch | **none** — `pyproject.toml` + root `README.md` (`uv sync`) | greenfield assembly |
| `worker/docker-compose.yml` | config | runtime | event-driven (poll loop) | **none** — `.env.example` + `README.md` env table | greenfield |
| `worker/entrypoint.sh` | utility | runtime | event-driven + batch | `tests/test_catch_up.py` (`--only-pending-transcripts` CLI) | partial (CLI only) |
| `worker/README.md` | docs | ops | — | root `README.md` (Setup + env vars + uv) | role-match |
| `worker/.env.example` | config | ops | — | root `.env.example` | exact |
| `worker/rclone.conf.example` | config | ops | file-I/O | **none** — RESEARCH Pattern 2 (runtime materialization) | greenfield template |
| `pipeline/budget.py` | service | runtime | CRUD (SQLite aggregate) | self (`WeekBudget`, `baseline_per_item_from_runs`) | exact |
| `pipeline/orchestrator.py` | service | runtime | batch | self (`_summarize_week_items` halt, `_finalize`, `run_ingest(only_pending_transcripts)`) | exact |
| `pipeline/render/partition.py` | utility | render | transform | self (`_IN_PLACE_TRANSIENT_STATUSES`) | exact |
| `pipeline/render/digest_json.py` | service | render | transform + file-I/O | self (`_build_pipeline_notes`) | exact |
| `pipeline/reporting/pipeline_report.py` | service | render | file-I/O | self (`build_pipeline_report` budget block) | exact |
| `pipeline/week.py` | utility | runtime | transform | self (`week_bounds`, `current_week_id`) | exact |
| `pipeline/run.py` | utility | runtime | request-response (CLI) | self (`_add_only_pending_transcripts_arg`, `_add_phase3_flags`) | exact |
| `web/src/components/StatusBanner.astro` | component | web | transform | `PartialPublishNotice.astro` + `PipelineNotes.astro` | role-match |
| `web/src/components/Header.astro` | component | web | transform | self (minimal change — CONTEXT mounts banner in `<main>`, not inside Header) | exact (mount site: pages) |
| `web/src/content.config.ts` | config | web | transform (Zod) | self (`reports` collection `budget` field) | exact |
| `.gitignore` | config | ops | — | self (existing `.env`, `data/`) | exact |
| `.planning/runbooks/leak-recovery.md` | docs | ops | — | self (**already exists** — extend if Phase 5 adds secret names) | exact |
| `tests/budget/test_budget_halt.py` | test | — | — | self | exact |
| `tests/render/test_digest_json_partition_parity.py` | test | — | — | self (`test_all_in_place_transient_statuses_get_degraded_body`) | exact |
| `tests/week/test_week_bounds_et.py` | test | — | — | `tests/test_week.py` | role-match |
| `tests/test_retry_transient.py` (or extend CLI tests) | test | — | — | `tests/test_catch_up.py` | role-match |

### Greenfield inventory (no in-repo analog)

| Area | Status | Planner reference |
|------|--------|-------------------|
| `.github/workflows/` | **Directory does not exist** — zero workflow YAML in repo | RESEARCH Pattern 1–4 + [workflow permissions](https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions#permissions) |
| `worker/` | **Directory does not exist** — no Dockerfile/docker-compose anywhere | RESEARCH Pattern 2–3 + root `pyproject.toml` deps |
| `rclone` integration | **No existing rclone usage** | RESEARCH Pattern 2; [rclone B2 backend](https://rclone.org/b2/) |

---

## Pattern Assignments

### `.github/workflows/weekly-digest.yml` (workflow, batch + file-I/O)

**Analog:** None in repo. Canonical shape from RESEARCH Pattern 1 + GitHub docs.

**Schedule + permissions** (RESEARCH + D-B1):

```yaml
name: Weekly digest

on:
  schedule:
    - cron: '0 10 * * 0'   # Sun 10:00 UTC (~05:00 EST / ~06:00 EDT)
  workflow_dispatch:

permissions:
  contents: write

jobs:
  digest:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      # uv install, rclone materialization, Healthchecks /start — see Pattern 2/4 in 05-RESEARCH.md
      - run: |
          WEEK_ID=$(uv run python -c "from pipeline.week import active_digest_week_id; print(active_digest_week_id())")
          uv run python -m pipeline.run all --week "$WEEK_ID"
      - run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add web/src/content/digests/ web/src/content/reports/
          git diff --staged --quiet || git commit -m "chore(digest): weekly ${WEEK_ID}"
          git push
```

**Python install pattern** — mirror root README:

```bash
uv sync
uv run python -m pipeline.run all --week "$WEEK_ID"
```

**Secrets injection** — `${{ secrets.GEMINI_API_KEY }}`, `${{ secrets.B2_KEY_ID }}`, `${{ secrets.B2_APPLICATION_KEY }}`, `${{ secrets.HEALTHCHECK_CRON_URL }}` (D-B8).

**Source:** [GitHub Actions workflow syntax — `on.schedule`, `permissions`](https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions)

---

### `.github/workflows/daily-retry.yml` (workflow, batch)

**Analog:** `weekly-digest.yml` (same skeleton; differs in cron + CLI).

**Schedule** (D-B4):

```yaml
on:
  schedule:
    - cron: '0 10 * * 1-6'
  workflow_dispatch:
```

**CLI invocation** (RESEARCH):

```bash
WEEK_ID=$(uv run python -c "from pipeline.week import active_digest_week_id; print(active_digest_week_id())")
uv run python -m pipeline.run summarize --week "$WEEK_ID" --retry-transient-only
```

No Healthchecks pings (D-B4). Same B2 pull/push + weekly spend counter as Sunday cron.

---

### `.github/workflows/sentinel.yml` (workflow, batch + verify)

**Analog:** `weekly-digest.yml` checkout step + shell verification.

**Monday check** (D-B7) — `actions/checkout@v4`, then verify `web/src/content/digests/{week_id}.json` exists and report `budget.halted === false` (or `hard_cap_hit === false` after Phase 5 field rename). Ping `${{ secrets.HEALTHCHECK_SENTINEL_URL }}` with success/fail body.

---

### `.github/workflows/build-worker-image.yml` (workflow, GHCR push)

**Analog:** None in repo. RESEARCH Pattern 3 verbatim:

```yaml
permissions:
  contents: read
  packages: write

steps:
  - uses: docker/setup-qemu-action@v4
  - uses: docker/setup-buildx-action@v4
  - uses: docker/login-action@v4
    with:
      registry: ghcr.io
      username: ${{ github.actor }}
      password: ${{ secrets.GITHUB_TOKEN }}
  - uses: docker/build-push-action@v7
    with:
      context: worker
      platforms: linux/amd64,linux/arm64
      push: true
      tags: |
        ghcr.io/${{ github.repository_owner }}/aidigest-worker:latest
        ghcr.io/${{ github.repository_owner }}/aidigest-worker:sha-${{ github.sha }}
```

Trigger: `push` paths `worker/**` + `workflow_dispatch`.

**Source:** [Docker — Build multi-platform images with GitHub Actions](https://docs.docker.com/build/ci/github-actions/multi-platform/)

---

### `worker/Dockerfile` (config, batch container)

**Analog:** Greenfield assembly from `pyproject.toml` + README uv pattern.

**Base shape to copy:**

```dockerfile
# Multi-stage: builder installs deps via uv; runtime has Python 3.12 + rclone
FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY pipeline/ pipeline/
COPY store/ store/
COPY config/ config/
RUN uv sync --frozen --no-dev

FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends rclone git \
    && rm -rf /var/lib/apt/lists/*
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app /app
COPY worker/entrypoint.sh /entrypoint.sh
ENV PATH="/app/.venv/bin:$PATH"
WORKDIR /app
ENTRYPOINT ["/entrypoint.sh"]
```

Context is **repo root** (not `worker/` only) so `pipeline` and `store` packages resolve. `build-worker-image.yml` should set `context: .` and `file: worker/Dockerfile` if using this layout.

---

### `worker/docker-compose.yml` + `worker/.env.example` + `worker/rclone.conf.example`

**Analog:** Root `.env.example` (lines 1–1 today — extend in `worker/`):

```1:1:.env.example
GEMINI_API_KEY=
```

**Worker `.env.example` should list** (D-B8): `GEMINI_API_KEY`, `B2_KEY_ID`, `B2_APPLICATION_KEY`, `GITHUB_TOKEN` (fine-grained PAT), `HEALTHCHECK_WORKER_URL`, optional `REPO_URL`.

**docker-compose pattern:**

```yaml
services:
  aidigest-worker:
    image: ghcr.io/${OWNER}/aidigest-worker:latest
    env_file:
      - ${AIDIGEST_ENV_FILE:-/path/outside/repo/.env}
    volumes:
      - ./data:/app/data
    restart: unless-stopped
```

Mount `.env` read-only from host path outside cloned repo (`chmod 600`, D-B8).

**rclone.conf.example** — placeholder only; real config materialized at runtime (RESEARCH Pattern 2):

```ini
[b2]
type = b2
account = YOUR_B2_APPLICATION_KEY_ID
key = YOUR_B2_APPLICATION_KEY
```

---

### `worker/entrypoint.sh` (utility, poll + batch)

**Analog:** `tests/test_catch_up.py` documents the CLI surface the loop invokes:

```103:103:tests/test_catch_up.py
    stats = run_ingest("2026-W21", db_path=db_path, only_pending_transcripts=True)
```

**Home worker command** (D-23, CONTEXT):

```bash
python -m pipeline.run all --only-pending-transcripts
```

**Poll loop shape** (D-B5b):

```bash
while true; do
  # During Sunday window only (planner picks TZ guard)
  if rclone ls "b2:aidigest-state/markers/" | grep -q "cron-complete-${WEEK_ID}.json"; then
    rclone copy "b2:aidigest-state/db/aidigest.db" data/aidigest.db
    uv run python -m pipeline.run all --only-pending-transcripts --week "$WEEK_ID"
    rclone copy data/aidigest.db "b2:aidigest-state/db/aidigest.db"
    # git commit digest JSON via PAT; delete marker; Healthchecks end ping
    break
  fi
  sleep 600
done
```

Use `rclone copy` not `sync` (RESEARCH anti-pattern).

---

### `worker/README.md` (docs)

**Analog:** Root `README.md` Setup + Prerequisites sections:

```40:49:README.md
## Setup

```bash
# Install dependencies + create .venv
uv sync

# Copy the env template and add your Gemini API key
cp .env.example .env       # macOS / Linux
copy .env.example .env     # Windows (cmd)
```
```

Extend with: Healthchecks signup, B2 bucket, PAT issuance, dry-run procedure (CONTEXT deferred hand-off), link to `.planning/runbooks/leak-recovery.md`.

---

### `pipeline/budget.py` (service, CRUD aggregate)

**Analog:** self — extend `WeekBudget.from_config` and add cross-run loader.

**Existing dataclass + afford gate** (lines 19–107):

```19:50:pipeline/budget.py
@dataclass
class WeekBudget:
    """Tracks cap, reservation, and spend with stage-aware afford checks."""

    cap_usd: float
    reserved_meta_usd: float
    spent_usd: float = 0.0
    halted: bool = False
    halted_at_stage: str | None = None
    ...
    @classmethod
    def from_config(
        cls,
        *,
        cap_override: float | None = None,
        conn: sqlite3.Connection | None = None,
        week_id: str | None = None,
    ) -> WeekBudget:
        """Load cap and reservation from ``config/digest.yaml`` (D-59)."""
        cfg = load_digest_config()
        cap = cap_override if cap_override is not None else cfg.pipeline.hard_stop_usd
        ...
```

**Prior-week baseline query pattern to mirror** for cumulative spend (`tests/budget/test_baseline_prior_week.py`):

```11:26:tests/budget/test_baseline_prior_week.py
def _insert_completed_run(
    conn,
    *,
    week_id: str,
    cost_usd_estimate: float,
    summaries_written: int,
    status: str = "success",
) -> None:
    run_id = insert_pipeline_run(conn, week_id=week_id, phase="all", status="running")
    finalize_pipeline_run(
        conn,
        run_id,
        status=status,
        cost_usd_estimate=cost_usd_estimate,
        summaries_written=summaries_written,
    )
```

**Phase 5 additions:**

```python
HARD_CAP_USD = float(os.environ.get("HARD_CAP_USD", "1.0"))

def get_cumulative_week_spend_usd(conn: sqlite3.Connection, week_id: str) -> float:
    row = conn.execute(
        """
        SELECT COALESCE(SUM(cost_usd_estimate), 0.0) AS spent
          FROM pipeline_runs
         WHERE week_id = ?
           AND status IN ('success', 'partial')
        """,
        (week_id,),
    ).fetchone()
    return float(row["spent"] or 0.0)
```

Seed `spent_usd` in `from_config` from this aggregate before the run adds more.

---

### `pipeline/orchestrator.py` (service, batch)

**Analog:** self — `_summarize_week_items` halt + `_finalize` report write.

**Budget halt today (bare `break` — Phase 5 adds deferred marking)** (lines 389–398):

```389:398:pipeline/orchestrator.py
        if budget is not None and not budget.can_afford(
            estimate_per_item, stage="summarize"
        ):
            budget.halt_if_over_cap(stage="summarize")
            log.warning(
                "budget.summarize_halted",
                spent_usd=budget.spent_usd,
                cap_usd=budget.cap_usd,
            )
            break
```

**After `break`:** call `_mark_deferred_budget_for_remaining(...)` to insert `summary_status='deferred_budget'` rows for unprocessed canonical items (D-B9). Do not leave items invisible.

**Budget construction sites** — thread `conn` + `week_id` at every `WeekBudget.from_config` (example `run_summarize`, lines 1520–1522):

```1520:1522:pipeline/orchestrator.py
        budget = WeekBudget.from_config(
            cap_override=max_cost_usd, conn=conn, week_id=week_id
        )
```

**`_finalize` → report** (lines 1264–1270):

```1264:1270:pipeline/orchestrator.py
    write_pipeline_report(
        conn,
        stats,
        run_id=run_id,
        status=status,
        budget=budget,
        out_dir=out_dir,
    )
```

**`--retry-transient-only`:** filter in `_summarize_week_items` (or a wrapper) to only re-process rows where `summary_status IN ('quota_exhausted','api_error','client_init_error')` — taxonomy from `pipeline/llm/exceptions.py`:

```10:28:pipeline/llm/exceptions.py
def classify_llm_exception(exc: BaseException) -> str:
    ...
    if (
        "resource_exhausted" in text
        or "429" in text
        or "rate limit" in text
        or "quota" in text
    ):
        return "quota_exhausted"
    return "api_error"
```

**Marker file write:** add cloud-mode hook at end of successful `run_all` (not home worker path) — write `markers/cron-complete-{week_id}.json` to B2 via rclone (orchestrator stays B2-agnostic; GHA/worker shell may own rclone — planner picks seam).

---

### `pipeline/render/partition.py` (utility, transform)

**Analog:** self — one-line frozenset extension (LOCKED-01).

**Current set** (lines 59–67):

```59:67:pipeline/render/partition.py
_IN_PLACE_TRANSIENT_STATUSES = frozenset(
    {
        "quota_exhausted",
        "api_error",
        "parse_error",
        "client_init_error",
        "transcript_missing",
    }
)
```

**Phase 5:** add `"deferred_budget"`. Cards keep `QUOTA_BODY_COPY`; spend-specific copy lives in `StatusBanner` (D-24).

**Routing helper** (lines 105–113):

```105:113:pipeline/render/partition.py
def _is_quota_in_place(card: DigestCard) -> bool:
    ...
    return card.summary_status in _IN_PLACE_TRANSIENT_STATUSES
```

---

### `pipeline/render/digest_json.py` (service, transform)

**Analog:** self — `_build_pipeline_notes` already reads `budget.halted`.

**Budget / quota detail lines** (lines 268–333):

```268:333:pipeline/render/digest_json.py
    budget = report.get("budget") or {}
    ...
    quota_n = int(summary_status.get("quota_exhausted", 0))
    if quota_n > 0:
        ...
    if budget.get("halted"):
        details.append(PARTIAL_PUBLISH_COPY)
    ...
    if budget.get("halted"):
        summary_parts.append("pipeline stopped at budget cap")
```

**Phase 5:** also count `deferred_budget` in summary_status; optionally surface `budget.get("hard_cap_hit")` for banner consumers (report JSON is the source of truth for OBS-03).

---

### `pipeline/reporting/pipeline_report.py` (service, file-I/O)

**Analog:** self — extend `budget_block` and `_SUMMARY_STATUS_KEYS`.

**Budget block** (lines 183–192):

```183:192:pipeline/reporting/pipeline_report.py
    if budget is not None:
        budget_block = {
            "cap_usd": budget.cap_usd,
            "reserved_meta_usd": budget.reserved_meta_usd,
            "spent_usd": round(budget.spent_usd, 6),
            "pre_flight_estimate_usd": round(budget.pre_flight_estimate_usd, 6),
            "halted": budget.halted,
            "halted_at_stage": budget.halted_at_stage,
        }
```

**Phase 5 additions:**

```python
budget_block["hard_cap_hit"] = budget.halted
budget_block["deferred_items_count"] = int(
    (_summary_status_counts(conn, week_id).get("deferred_budget") or 0)
)
```

Add `"deferred_budget"` to `_SUMMARY_STATUS_KEYS` (lines 21–28).

**Archive write** (lines 247–276) — already commits to `web/src/content/reports/{week_id}.json`:

```272:275:pipeline/reporting/pipeline_report.py
    if archive_dir is not None:
        archive_dir.mkdir(parents=True, exist_ok=True)
        archive_path = archive_dir / f"{stats.week_id}.json"
        archive_path.write_text(text, encoding="utf-8")
```

---

### `pipeline/week.py` (utility, transform)

**Analog:** self — add parallel ET API; **do not change** `week_bounds()` default (175+ tests).

**Existing ISO bounds** (lines 48–60):

```48:60:pipeline/week.py
def week_bounds(week_id: str) -> tuple[datetime, datetime]:
    """Return ``(week_start, week_end)`` as tz-aware UTC datetimes.

    ``week_start`` is Monday 00:00:00 UTC; ``week_end`` is Sunday 23:59:59 UTC
    ...
    """
    year, week = parse_week_id(week_id)
    monday = date.fromisocalendar(year, week, 1)
    sunday = date.fromisocalendar(year, week, 7)
    week_start = datetime.combine(monday, time.min, tzinfo=UTC)
    week_end = datetime.combine(sunday, time(23, 59, 59), tzinfo=UTC)
    return week_start, week_end
```

**Phase 5 additions** (RESEARCH Option A):

```python
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

def week_bounds_et(week_id: str) -> tuple[datetime, datetime]:
    """Sun 00:00 ET – Sat 23:59:59 ET for digest window (D-B6b)."""
    ...

def active_digest_week_id(reference: datetime | None = None) -> str:
    """Week id for Sunday cron — prior Sun–Sat ET window."""
    ...
```

GHA resolves week via `python -c "from pipeline.week import active_digest_week_id; print(active_digest_week_id())"`.

---

### `pipeline/run.py` (utility, CLI)

**Analog:** self — copy `_add_only_pending_transcripts_arg` pattern for new flag.

**Existing flag helper** (lines 56–63):

```56:63:pipeline/run.py
def _add_only_pending_transcripts_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--only-pending-transcripts",
        dest="only_pending_transcripts",
        action="store_true",
        default=False,
        help=_PENDING_TRANSCRIPTS_HELP,
    )
```

**Add `--retry-transient-only`** to `summarize` subcommand + `_build_parser`; thread through `run_summarize(..., retry_transient_only=...)` (D-22: help text + README).

**Summarize dispatch** (lines 249–252):

```249:252:pipeline/run.py
        elif command == "summarize":
            from pipeline.orchestrator import run_summarize

            stats = run_summarize(week_id, max_cost_usd=p3["max_cost_usd"])
```

---

### `web/src/components/StatusBanner.astro` (component, transform)

**Analog:** `PartialPublishNotice.astro` (conditional banner) + `PipelineNotes.astro` (plain-English props).

**Partial publish notice pattern** (lines 1–19):

```1:19:web/src/components/PartialPublishNotice.astro
---
interface FailureNotice {
  kind: string;
  body: string;
}

interface Props {
  failureNotice?: FailureNotice | null;
}

const { failureNotice } = Astro.props;
---

{
  failureNotice?.kind === 'partial_publish' && (
    <p class="partial-publish-notice mb-6 rounded border border-[#8b6914] border-l-4 bg-[#1a1610] p-4 text-base leading-normal text-[#c8b896]">
      {failureNotice.body}
    </p>
  )
}
```

**StatusBanner variants** (D-24, OBS-03):

- **complete** — no banner or subtle "complete" when no pending transcripts and no cap hit
- **filling in N videos** — `pending_transcripts_count > 0`
- **partial — N items skipped** — `budget.hard_cap_hit` + `deferred_items_count`

Copy lives in `web/src/lib/copy.ts` (mirror `pipeline/render/partition.py` pattern):

```1:8:web/src/lib/copy.ts
/** Reader-surface copy — mirrors pipeline/render/partition.py (D-24). */
export const BRIEFING_HEADER_TEMPLATE = 'Briefing — Top {n} this week';
...
export function formatBriefingHeader(topN: number): string {
  return BRIEFING_HEADER_TEMPLATE.replace('{n}', String(topN));
}
```

---

### `web/src/components/Header.astro` + page mount sites

**Analog:** `web/src/pages/index.astro` component ordering.

**Current main layout** (lines 21–24):

```21:24:web/src/pages/index.astro
  <main class="mx-auto w-full max-w-[720px] px-4 py-6 md:px-5">
    <PipelineNotes pipelineNotes={data.pipeline_notes} />
    <PartialPublishNotice failureNotice={data.failure_notice} />
    <DigestBriefing digest={digest} />
```

**Phase 5 mount order** (D-A4a + CONTEXT): `Header` → `<main>` → **`StatusBanner`** → `PipelineNotes` → `PartialPublishNotice` → `DigestBriefing`.

Apply same change to `web/src/pages/digest/[week].astro` (lines 30–33). `Header.astro` itself likely unchanged unless week-level props needed.

**Data loading:** join digest entry with matching report from `getCollection('reports')` filtered by `week_id`, or embed banner fields into digest JSON emitter if planner consolidates.

---

### `web/src/content.config.ts` (config, Zod)

**Analog:** self — tighten `reports.budget` from loose record to typed object.

**Current reports schema** (lines 69–87):

```69:87:web/src/content.config.ts
const reports = defineCollection({
  loader: glob({ base: './src/content/reports', pattern: '**/*.json' }),
  schema: z.object({
    schema_version: z.literal(1),
    week_id: z.string(),
    ...
    budget: z.record(z.string(), z.unknown()),
  }),
});
```

**Phase 5:**

```typescript
const budgetSchema = z.object({
  cap_usd: z.number(),
  reserved_meta_usd: z.number(),
  spent_usd: z.number(),
  pre_flight_estimate_usd: z.number(),
  halted: z.boolean(),
  halted_at_stage: z.string().nullable(),
  hard_cap_hit: z.boolean(),
  deferred_items_count: z.number().int().nonnegative(),
});
// budget: budgetSchema,
```

Keep `schema_version: 1` on both collections (D-A2c).

---

### `.gitignore` (config)

**Analog:** self — extend existing secret/data entries.

**Current** (lines 1–5):

```1:5:.gitignore
# Secrets — never commit
.env

# Working data (gitignored per ARCHITECTURE store-and-forward)
data/
```

**Phase 5 additions** (D-B8):

```
.env.local
*.pem
*.key
data/*.db
```

(`.env` and `data/` already present.)

---

### `.planning/runbooks/leak-recovery.md` (docs)

**Analog:** self — **file already exists** and matches D-B8 five-step playbook. Phase 5 may only need cross-links from `worker/README.md`; no structural rewrite unless new secret types added.

Existing step-1 vendor table (lines 12–20) already covers Gemini, B2, PAT, Healthchecks.

---

## Test Patterns

### `tests/budget/test_budget_halt.py` — extend for `deferred_budget`

**Analog:** existing cap-halt integration test (lines 130–150):

```130:150:tests/budget/test_budget_halt.py
    stats = run_all(
        week_id,
        db_path=db_path,
        out_dir=out_dir,
        max_cost_usd=0.015,
    )
    ...
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["budget"]["halted"] is True
    assert report["budget"]["halted_at_stage"] == "summarize"
```

**Add assertions:** DB rows with `summary_status='deferred_budget'`; `report["budget"]["hard_cap_hit"]`; `report["summary_status"]["deferred_budget"] > 0`.

### `tests/render/test_digest_json_partition_parity.py` — auto-covers new status

**Analog** (lines 69–78):

```69:78:tests/render/test_digest_json_partition_parity.py
def test_all_in_place_transient_statuses_get_degraded_body(tmp_path: Path) -> None:
    cards = [
        _card(tldr=None, summary_status=status, title=f"InPlace {status}")
        for status in sorted(_IN_PLACE_TRANSIENT_STATUSES)
    ]
    ...
    for card in payload["main_feed"]:
        assert card["degraded_body"] == QUOTA_BODY_COPY
```

Adding `deferred_budget` to frozenset automatically extends this test.

### `tests/week/test_week_bounds_et.py` — new file

**Analog:** `tests/test_week.py` structure (lines 17–28):

```17:28:tests/test_week.py
def test_week_bounds_monday_to_sunday() -> None:
    """Week 19 of 2026: Mon 2026-05-04 00:00 UTC through Sun 2026-05-10 23:59:59 UTC."""
    start, end = week_bounds("2026-W19")
    assert start == datetime(2026, 5, 4, 0, 0, 0, tzinfo=UTC)
    assert end == datetime(2026, 5, 10, 23, 59, 59, tzinfo=UTC)
```

Mirror with `week_bounds_et` + `active_digest_week_id` ET/DST cases.

### `tests/test_retry_transient.py` (or extend CLI tests)

**Analog:** `tests/test_catch_up.py` — orchestrator flag wiring with monkeypatched summarize.

---

## Shared Patterns

### CLI flag discoverability (D-22)

**Source:** `pipeline/run.py`

Add `_RETRY_TRANSIENT_HELP` string + `_add_retry_transient_arg()` mirroring `_add_only_pending_transcripts_arg`; document in root `README.md` and `worker/README.md`.

### Cross-run SQLite spend (D-09 / D-69)

**Source:** `tests/budget/test_baseline_prior_week.py` + `pipeline/budget.py`

All `WeekBudget.from_config(conn=..., week_id=...)` call sites must seed cumulative spend from `pipeline_runs` SUM — cron, daily-retry, and home worker share one weekly counter.

### LOCKED-01 routing amendment

**Source:** `pipeline/render/partition.py::_IN_PLACE_TRANSIENT_STATUSES`

Update `.planning/LOCKED-DIRECTIVES.md` in the same commit as `deferred_budget` addition — not a silent default.

### Reader plain English (D-24)

**Source:** `web/src/lib/copy.ts` + `PartialPublishNotice.astro`

Never surface `deferred_budget` string in UI; banner says "N items skipped this week — weekly spend cap reached."

### Git commit from automation

**GHA cron:** `GITHUB_TOKEN` + `permissions: contents: write` + bot git config (RESEARCH Pattern 1).

**Home worker:** fine-grained PAT in `worker/.env` only (D-B8).

### Healthchecks curl sequence

**Source:** RESEARCH Pattern 4

```bash
curl -fsS -m 10 --retry 3 "${HEALTHCHECK_CRON_URL}/start"
# ... work ...
curl -fsS -m 10 --retry 3 --data-raw "spent_usd=${SPEND}" "${HEALTHCHECK_CRON_URL}"
curl -fsS -m 10 "${HEALTHCHECK_CRON_URL}/fail"  # on failure
```

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `.github/workflows/*.yml` (all 4) | workflow | batch | No `.github/workflows/` directory in repo |
| `worker/Dockerfile` | config | batch | No container assets anywhere |
| `worker/entrypoint.sh` | utility | event-driven | No shell automation in repo; CLI-only analog |
| `worker/rclone.conf.example` | config | file-I/O | No rclone usage in codebase |
| `tests/week/test_week_bounds_et.py` | test | — | New test file (pattern from `test_week.py`) |
| `tests/test_retry_transient.py` | test | — | Flag does not exist yet (A4 in RESEARCH) |

**Planner fallback:** Use `05-RESEARCH.md` Code Examples + Patterns 1–4 and official GitHub/Docker/rclone docs cited there.

---

## Metadata

**Analog search scope:** repo root — `pipeline/`, `web/src/`, `tests/`, `.github/`, `worker/`, `.planning/runbooks/`, root `README.md`, `.env.example`, `.gitignore`
**Files scanned:** ~45 source + test files
**Pattern extraction date:** 2026-05-24
