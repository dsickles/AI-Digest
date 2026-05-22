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
                if "duplicate column name" in str(exc).lower():
                    continue
                raise


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


def get_items_for_week(
    conn: sqlite3.Connection,
    week_start_iso: str,
    week_end_iso: str,
) -> list[sqlite3.Row]:
    """Return items whose ``published_at`` falls in [week_start, week_end], newest first."""
    return conn.execute(
        """
        SELECT *
          FROM items
         WHERE published_at >= ? AND published_at <= ?
         ORDER BY published_at DESC
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
) -> str:
    """Insert a fresh ``item_summaries`` row. Caller is responsible for skip-if-exists.

    D-28: ``summary_input_truncated`` records whether the LLM input was elided
    by ``pipeline.llm.summarize._maybe_truncate_transcript``.
    """
    summary_id = uuid.uuid4().hex
    conn.execute(
        """
        INSERT INTO item_summaries (
            summary_id, item_id, week_id, tldr, summary_confidence,
            prompt_version, model_id, input_tokens, output_tokens, cost_usd_estimate,
            summary_input_truncated
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        ),
    )
    return summary_id


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
