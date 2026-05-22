"""SQLite working store for AI Digest.

Single connection per call site (cheap on SQLite); WAL mode for safer
concurrent reads while the pipeline writes. All timestamps are ISO 8601 UTC.
"""
from __future__ import annotations

import sqlite3
import uuid
from collections.abc import Iterable
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pipeline.config import SourceConfig
    from pipeline.models import NormalizedItem


SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"
MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"
DEFAULT_DB_PATH = Path("data") / "aidigest.db"


def _utcnow_iso() -> str:
    """ISO 8601 UTC timestamp with millisecond precision."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


@contextmanager
def connect(db_path: Path | str | None = None) -> Iterable[sqlite3.Connection]:
    """Yield a SQLite connection with FK + WAL enabled.

    Creates the parent directory if missing. Caller commits/rolls back.
    """
    path = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.row_factory = sqlite3.Row
        yield conn
    finally:
        conn.close()


def _strip_sql_line_comments(text: str) -> str:
    """Drop ``--`` line comments before statement-splitting.

    SQLite tolerates comments inside ``executescript`` but the per-statement
    runner below splits on ``;`` and then passes each chunk to ``conn.execute``,
    which rejects bare comment text. Stripping line-comments up-front avoids
    parsing the SQL by hand while keeping behavior obvious.
    """
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("--")
    )


def _apply_migrations(conn: sqlite3.Connection) -> None:
    """Apply numbered migrations from ``store/migrations/*.sql`` in lexicographic order.

    Each migration is split on ``;`` and executed statement-by-statement so a single
    ``ALTER TABLE ADD COLUMN`` re-run (SQLite lacks ``IF NOT EXISTS`` for columns)
    can be swallowed as a no-op without aborting the rest of the file. Any
    ``OperationalError`` that is NOT a duplicate-column re-run is re-raised.
    """
    if not MIGRATIONS_DIR.is_dir():
        return
    for migration in sorted(MIGRATIONS_DIR.glob("*.sql")):
        text = _strip_sql_line_comments(migration.read_text(encoding="utf-8"))
        for raw_stmt in text.split(";"):
            stmt = raw_stmt.strip()
            if not stmt:
                continue
            try:
                conn.execute(stmt)
            except sqlite3.OperationalError as exc:
                message = str(exc).lower()
                if "duplicate column name" in message:
                    continue
                if "already exists" in message:
                    continue
                raise


def _ensure_pipeline_runs_phases(conn: sqlite3.Connection) -> None:
    """Rebuild ``pipeline_runs`` when the phase CHECK lacks Phase 3 stages.

    SQLite cannot ALTER CHECK constraints; existing DBs from Phase 1–2 need a
    one-time table rebuild. Idempotent — no-op when ``dedup`` is already allowed.
    """
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='pipeline_runs'"
    ).fetchone()
    if row is None:
        return
    ddl = row[0] or ""
    if "dedup" in ddl:
        return
    conn.executescript(
        """
        CREATE TABLE pipeline_runs__v2 (
            run_id              TEXT PRIMARY KEY,
            started_at          TEXT NOT NULL,
            finished_at         TEXT,
            week_id             TEXT NOT NULL,
            phase               TEXT NOT NULL CHECK (phase IN (
                'ingest', 'summarize', 'render', 'all',
                'dedup', 'categorize', 'rank', 'rollup'
            )),
            status              TEXT NOT NULL CHECK (status IN ('running', 'success', 'partial', 'failed')),
            errors_json         TEXT NOT NULL DEFAULT '[]',
            items_fetched       INTEGER NOT NULL DEFAULT 0,
            summaries_written   INTEGER NOT NULL DEFAULT 0,
            items_degraded      INTEGER NOT NULL DEFAULT 0,
            cost_usd_estimate   REAL NOT NULL DEFAULT 0.0
        );
        INSERT INTO pipeline_runs__v2
            SELECT run_id, started_at, finished_at, week_id, phase, status,
                   errors_json, items_fetched, summaries_written, items_degraded,
                   cost_usd_estimate
              FROM pipeline_runs;
        DROP TABLE pipeline_runs;
        ALTER TABLE pipeline_runs__v2 RENAME TO pipeline_runs;
        CREATE INDEX IF NOT EXISTS idx_pipeline_runs_week ON pipeline_runs(week_id);
        """
    )


def init_db(db_path: Path | str | None = None) -> Path:
    """Apply ``store/schema.sql`` plus numbered migrations to the target DB.

    Idempotent — safe to call on every run. Fresh DBs receive the canonical
    schema; existing DBs receive only the additive ALTER TABLE statements that
    have not been applied yet.
    """
    path = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    with connect(path) as conn:
        conn.executescript(schema_sql)
        _apply_migrations(conn)
        _ensure_pipeline_runs_phases(conn)
        conn.commit()
    return path


def update_source_health(
    conn: sqlite3.Connection,
    source_id: str,
    *,
    last_success_at: str | None = None,
    last_item_at: str | None = None,
    last_error_category: str | None = None,
) -> None:
    """Write the D-40 source-health columns for ``source_id``.

    Only non-``None`` columns are updated — pass ``None`` to leave a column
    untouched. Callers clear ``last_error_category`` on success by passing
    the literal string ``""`` (mapped to SQL NULL via empty-string sentinel
    handling here).
    """
    fields: list[str] = []
    values: list[object] = []
    if last_success_at is not None:
        fields.append("last_success_at = ?")
        values.append(last_success_at)
    if last_item_at is not None:
        fields.append("last_item_at = ?")
        values.append(last_item_at)
    if last_error_category is not None:
        fields.append("last_error_category = ?")
        values.append(last_error_category or None)
    if not fields:
        return
    values.append(source_id)
    conn.execute(
        f"UPDATE sources SET {', '.join(fields)} WHERE source_id = ?",
        values,
    )


def upsert_source(conn: sqlite3.Connection, source: SourceConfig) -> None:
    """Mirror a SourceConfig into the ``sources`` table (FK target for items).

    Preserves any existing fetch state (etag/last_modified/last_fetched_at);
    only the static config columns are overwritten.
    """
    conn.execute(
        """
        INSERT INTO sources (source_id, type, url, display_name, tag, enabled)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_id) DO UPDATE SET
            type         = excluded.type,
            url          = excluded.url,
            display_name = excluded.display_name,
            tag          = excluded.tag,
            enabled      = excluded.enabled
        """,
        (
            source.id,
            source.type,
            source.url,
            source.display_name,
            source.tag,
            1 if source.enabled else 0,
        ),
    )


def upsert_item(
    conn: sqlite3.Connection,
    item: NormalizedItem,
    *,
    transcript_status: str | None = None,
) -> str:
    """Insert an item or update mutable columns on (source_id, external_id) collision.

    Uses ``INSERT ... ON CONFLICT DO UPDATE`` so ``item_id`` stays stable and
    ``ingested_at`` reflects the latest ingest (INGEST-08). D-23: the YouTube
    adapter passes ``transcript_status`` (ok / pending_local / missing); other
    adapters leave it ``None``. ``item.transcript_status`` from the adapter
    takes precedence; the explicit kwarg lets callers (e.g. the catch-up path
    in plan 02-04) override without rebuilding the item.
    """
    item_id = uuid.uuid4().hex
    effective_status = (
        transcript_status if transcript_status is not None else item.transcript_status
    )
    conn.execute(
        """
        INSERT INTO items (
            item_id, source_id, external_id, canonical_url, title,
            publisher, published_at, raw_content, content_hash, transcript_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_id, external_id) DO UPDATE SET
            canonical_url     = excluded.canonical_url,
            title             = excluded.title,
            publisher         = excluded.publisher,
            published_at      = excluded.published_at,
            raw_content       = excluded.raw_content,
            content_hash      = excluded.content_hash,
            transcript_status = COALESCE(excluded.transcript_status, items.transcript_status),
            ingested_at       = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
        """,
        (
            item_id,
            item.source_id,
            item.external_id,
            item.canonical_url,
            item.title,
            item.publisher,
            item.published_at_iso(),
            item.raw_content,
            item.content_hash,
            effective_status,
        ),
    )
    row = conn.execute(
        "SELECT item_id FROM items WHERE source_id = ? AND external_id = ?",
        (item.source_id, item.external_id),
    ).fetchone()
    assert row is not None
    return row["item_id"]


def get_pending_transcript_items(
    conn: sqlite3.Connection,
    *,
    source_id: str | None = None,
) -> list[sqlite3.Row]:
    """Return items whose ``transcript_status == 'pending_local'`` (D-23 catch-up).

    Joined with ``sources.type`` so the orchestrator can keep the YouTube-only
    filter without re-querying the sources table per item.
    """
    sql = (
        "SELECT items.*, sources.type AS source_type "
        "FROM items JOIN sources ON sources.source_id = items.source_id "
        "WHERE items.transcript_status = 'pending_local'"
    )
    params: tuple[object, ...] = ()
    if source_id is not None:
        sql += " AND items.source_id = ?"
        params = (source_id,)
    sql += " ORDER BY items.published_at DESC"
    return conn.execute(sql, params).fetchall()


def update_item_transcript(
    conn: sqlite3.Connection,
    item_id: str,
    *,
    transcript_status: str,
    raw_content: str | None = None,
) -> None:
    """Flip ``transcript_status`` and optionally rewrite ``raw_content`` (D-23).

    The catch-up path passes the freshly fetched transcript when status flips
    to ``ok``; ``missing`` writes leave ``raw_content`` untouched so the
    description fallback (from the original ingest) survives.
    """
    if raw_content is not None:
        conn.execute(
            "UPDATE items SET transcript_status = ?, raw_content = ? WHERE item_id = ?",
            (transcript_status, raw_content, item_id),
        )
    else:
        conn.execute(
            "UPDATE items SET transcript_status = ? WHERE item_id = ?",
            (transcript_status, item_id),
        )


def get_items_for_week(
    conn: sqlite3.Connection,
    week_start_iso: str,
    week_end_iso: str,
) -> list[sqlite3.Row]:
    """Return items whose ``published_at`` falls in [week_start, week_end], newest first.

    Joins ``sources.type`` as ``source_type`` so the renderer can apply D-30
    (YouTube video indicator) and D-25 (degradation copy) without a second
    per-row source lookup.
    """
    return conn.execute(
        """
        SELECT items.*, sources.type AS source_type
          FROM items
          JOIN sources ON sources.source_id = items.source_id
         WHERE items.published_at >= ? AND items.published_at <= ?
         ORDER BY items.published_at DESC
        """,
        (week_start_iso, week_end_iso),
    ).fetchall()


def get_existing_summary(
    conn: sqlite3.Connection,
    item_id: str,
    week_id: str,
    prompt_version: str,
) -> sqlite3.Row | None:
    """Look up a prior summary row to enforce UNIQUE(item_id, week_id, prompt_version)."""
    return conn.execute(
        """
        SELECT *
          FROM item_summaries
         WHERE item_id = ? AND week_id = ? AND prompt_version = ?
        """,
        (item_id, week_id, prompt_version),
    ).fetchone()


def insert_item_summary(
    conn: sqlite3.Connection,
    *,
    item_id: str,
    week_id: str,
    tldr: str | None,
    summary_confidence: str,
    prompt_version: str,
    model_id: str,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    cost_usd_estimate: float | None = None,
    summary_input_truncated: bool = False,
    summary_status: str | None = None,
) -> str:
    """Insert a fresh ``item_summaries`` row. Caller is responsible for skip-if-exists.

    D-28: ``summary_input_truncated`` records whether the LLM input was elided
    by ``pipeline.llm.summarize._maybe_truncate_transcript``.

    ``summary_status`` (PROJECT.md LOCKED directive 2026-05-22): records why a
    summary is unavailable so the renderer can route content-thin items to the
    footer aside vs transient LLM-call failures (``quota_exhausted``) to an
    in-place "summary couldn't be generated this week" card. ``None`` for
    backwards compat with historical rows.
    """
    summary_id = uuid.uuid4().hex
    conn.execute(
        """
        INSERT INTO item_summaries (
            summary_id, item_id, week_id, tldr, summary_confidence,
            prompt_version, model_id, input_tokens, output_tokens, cost_usd_estimate,
            summary_input_truncated, summary_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            summary_id,
            item_id,
            week_id,
            tldr,
            summary_confidence,
            prompt_version,
            model_id,
            input_tokens,
            output_tokens,
            cost_usd_estimate,
            1 if summary_input_truncated else 0,
            summary_status,
        ),
    )
    return summary_id


def delete_clusters_for_week(conn: sqlite3.Connection, week_id: str) -> None:
    """Remove all cluster rows for ``week_id`` before a deterministic rebuild."""
    conn.execute(
        """
        DELETE FROM cluster_members
         WHERE cluster_id IN (
             SELECT cluster_id FROM story_clusters WHERE week_id = ?
         )
        """,
        (week_id,),
    )
    conn.execute("DELETE FROM story_clusters WHERE week_id = ?", (week_id,))


def insert_story_cluster(
    conn: sqlite3.Connection,
    *,
    cluster_id: str,
    week_id: str,
    canonical_item_id: str,
    canonical_url: str,
    title_normalized: str,
) -> str:
    """Insert a cluster header row."""
    conn.execute(
        """
        INSERT INTO story_clusters (
            cluster_id, week_id, canonical_item_id, canonical_url, title_normalized
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (cluster_id, week_id, canonical_item_id, canonical_url, title_normalized),
    )
    return cluster_id


def insert_cluster_member(
    conn: sqlite3.Connection,
    *,
    cluster_id: str,
    item_id: str,
    is_canonical: bool,
) -> None:
    """Attach an item to a cluster."""
    conn.execute(
        """
        INSERT INTO cluster_members (cluster_id, item_id, is_canonical)
        VALUES (?, ?, ?)
        """,
        (cluster_id, item_id, 1 if is_canonical else 0),
    )


def get_clusters_for_week(
    conn: sqlite3.Connection,
    week_id: str,
) -> list[sqlite3.Row]:
    """Return cluster headers for ``week_id``."""
    return conn.execute(
        "SELECT * FROM story_clusters WHERE week_id = ? ORDER BY created_at",
        (week_id,),
    ).fetchall()


def get_cluster_members(
    conn: sqlite3.Connection,
    cluster_id: str,
) -> list[sqlite3.Row]:
    """Return member rows for a cluster."""
    return conn.execute(
        """
        SELECT cm.*, items.canonical_url, items.title, sources.display_name
          FROM cluster_members cm
          JOIN items ON items.item_id = cm.item_id
          JOIN sources ON sources.source_id = items.source_id
         WHERE cm.cluster_id = ?
         ORDER BY cm.is_canonical DESC, sources.display_name, items.item_id
        """,
        (cluster_id,),
    ).fetchall()


def get_canonical_item_ids_for_week(
    conn: sqlite3.Connection,
    week_id: str,
) -> set[str]:
    """Item ids that should receive LLM summarize (canonical representatives)."""
    rows = conn.execute(
        """
        SELECT canonical_item_id FROM story_clusters WHERE week_id = ?
        """,
        (week_id,),
    ).fetchall()
    return {row["canonical_item_id"] for row in rows}


def is_cluster_canonical_member(
    conn: sqlite3.Connection,
    *,
    week_id: str,
    item_id: str,
) -> bool:
    """True when ``item_id`` is the canonical representative for its week cluster."""
    row = conn.execute(
        """
        SELECT 1
          FROM story_clusters
         WHERE week_id = ? AND canonical_item_id = ?
        """,
        (week_id, item_id),
    ).fetchone()
    return row is not None


def get_existing_cluster_summary(
    conn: sqlite3.Connection,
    cluster_id: str,
    week_id: str,
    prompt_version: str,
) -> sqlite3.Row | None:
    """Look up a prior categorize row for checkpoint skip (D-67)."""
    return conn.execute(
        """
        SELECT *
          FROM cluster_summaries
         WHERE cluster_id = ? AND week_id = ? AND prompt_version = ?
        """,
        (cluster_id, week_id, prompt_version),
    ).fetchone()


def insert_cluster_summary(
    conn: sqlite3.Connection,
    *,
    cluster_id: str,
    week_id: str,
    category: str,
    category_confidence: str | None,
    category_status: str | None,
    prompt_version: str,
    model_id: str,
) -> str:
    """Insert a fresh ``cluster_summaries`` row."""
    summary_id = uuid.uuid4().hex
    conn.execute(
        """
        INSERT INTO cluster_summaries (
            cluster_summary_id, cluster_id, week_id, category,
            category_confidence, category_status, prompt_version, model_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            summary_id,
            cluster_id,
            week_id,
            category,
            category_confidence,
            category_status,
            prompt_version,
            model_id,
        ),
    )
    return summary_id


def get_cluster_categories_for_week(
    conn: sqlite3.Connection,
    week_id: str,
    prompt_version: str = "categorize_v1",
) -> dict[str, str]:
    """Map canonical ``item_id`` → category for render grouping."""
    rows = conn.execute(
        """
        SELECT sc.canonical_item_id, cs.category
          FROM cluster_summaries cs
          JOIN story_clusters sc ON sc.cluster_id = cs.cluster_id
         WHERE cs.week_id = ? AND cs.prompt_version = ?
        """,
        (week_id, prompt_version),
    ).fetchall()
    return {row["canonical_item_id"]: row["category"] for row in rows}


def delete_ranks_for_week(
    conn: sqlite3.Connection,
    week_id: str,
    prompt_version: str = "rank_v1",
) -> None:
    """Remove rank rows for a week (stage-level rebuild before re-rank)."""
    conn.execute(
        """
        DELETE FROM cluster_ranks
         WHERE week_id = ? AND prompt_version = ?
        """,
        (week_id, prompt_version),
    )


def get_ranks_for_week(
    conn: sqlite3.Connection,
    week_id: str,
    prompt_version: str = "rank_v1",
) -> list[sqlite3.Row]:
    """Return persisted rank rows ordered by ``rank_position`` ascending."""
    return conn.execute(
        """
        SELECT *
          FROM cluster_ranks
         WHERE week_id = ? AND prompt_version = ?
         ORDER BY rank_position ASC
        """,
        (week_id, prompt_version),
    ).fetchall()


def insert_cluster_ranks_batch(
    conn: sqlite3.Connection,
    *,
    week_id: str,
    rows: list[dict[str, object]],
) -> None:
    """Insert many ``cluster_ranks`` rows in one transaction."""
    for row in rows:
        rank_id = uuid.uuid4().hex
        conn.execute(
            """
            INSERT INTO cluster_ranks (
                cluster_rank_id, cluster_id, week_id, rank_score, rank_position,
                rank_status, prompt_version, model_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rank_id,
                row["cluster_id"],
                week_id,
                row["rank_score"],
                row["rank_position"],
                row.get("rank_status"),
                row["prompt_version"],
                row["model_id"],
            ),
        )


def get_rank_positions_for_week(
    conn: sqlite3.Connection,
    week_id: str,
    prompt_version: str = "rank_v1",
) -> dict[str, int]:
    """Map canonical ``item_id`` → global ``rank_position`` for render sort."""
    db_rows = conn.execute(
        """
        SELECT sc.canonical_item_id, cr.rank_position
          FROM cluster_ranks cr
          JOIN story_clusters sc ON sc.cluster_id = cr.cluster_id
         WHERE cr.week_id = ? AND cr.prompt_version = ?
        """,
        (week_id, prompt_version),
    ).fetchall()
    return {row["canonical_item_id"]: row["rank_position"] for row in db_rows}


def get_last_known_cluster_category(
    conn: sqlite3.Connection,
    cluster_id: str,
    *,
    exclude_prompt_version: str | None = None,
) -> str | None:
    """Most recent stored category for quota fallback (D-49)."""
    if exclude_prompt_version:
        row = conn.execute(
            """
            SELECT category FROM cluster_summaries
             WHERE cluster_id = ? AND prompt_version != ?
             ORDER BY created_at DESC LIMIT 1
            """,
            (cluster_id, exclude_prompt_version),
        ).fetchone()
    else:
        row = conn.execute(
            """
            SELECT category FROM cluster_summaries
             WHERE cluster_id = ?
             ORDER BY created_at DESC LIMIT 1
            """,
            (cluster_id,),
        ).fetchone()
    return row["category"] if row else None


def insert_pipeline_run(
    conn: sqlite3.Connection,
    *,
    week_id: str,
    phase: str,
    status: str = "running",
) -> str:
    """Open a ``pipeline_runs`` row and return its ``run_id``."""
    run_id = uuid.uuid4().hex
    conn.execute(
        """
        INSERT INTO pipeline_runs (run_id, started_at, week_id, phase, status)
        VALUES (?, ?, ?, ?, ?)
        """,
        (run_id, _utcnow_iso(), week_id, phase, status),
    )
    return run_id


def finalize_pipeline_run(
    conn: sqlite3.Connection,
    run_id: str,
    *,
    status: str,
    items_fetched: int = 0,
    summaries_written: int = 0,
    items_degraded: int = 0,
    cost_usd_estimate: float = 0.0,
    errors_json: str = "[]",
) -> None:
    """Close a ``pipeline_runs`` row with terminal status and counters."""
    conn.execute(
        """
        UPDATE pipeline_runs
           SET finished_at       = ?,
               status            = ?,
               items_fetched     = ?,
               summaries_written = ?,
               items_degraded    = ?,
               cost_usd_estimate = ?,
               errors_json       = ?
         WHERE run_id = ?
        """,
        (
            _utcnow_iso(),
            status,
            items_fetched,
            summaries_written,
            items_degraded,
            cost_usd_estimate,
            errors_json,
            run_id,
        ),
    )


def fetchone(
    conn: sqlite3.Connection,
    sql: str,
    params: tuple[Any, ...] = (),
) -> sqlite3.Row | None:
    """Convenience wrapper for one-shot reads in tests/CLI."""
    return conn.execute(sql, params).fetchone()
