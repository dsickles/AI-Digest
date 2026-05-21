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


def init_db(db_path: Path | str | None = None) -> Path:
    """Apply ``store/schema.sql`` to the target DB, creating it if needed.

    Idempotent — safe to call on every run.
    """
    path = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    with connect(path) as conn:
        conn.executescript(schema_sql)
        conn.commit()
    return path


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


def upsert_item(conn: sqlite3.Connection, item: NormalizedItem) -> str:
    """Insert an item or update the mutable columns when (source_id, external_id) collides.

    Returns the canonical ``item_id`` (existing one preserved on conflict so
    downstream FKs in ``item_summaries`` stay stable).
    """
    existing = conn.execute(
        "SELECT item_id FROM items WHERE source_id = ? AND external_id = ?",
        (item.source_id, item.external_id),
    ).fetchone()

    if existing is not None:
        item_id = existing["item_id"]
        conn.execute(
            """
            UPDATE items
               SET canonical_url = ?,
                   title         = ?,
                   publisher     = ?,
                   published_at  = ?,
                   raw_content   = ?,
                   content_hash  = ?
             WHERE item_id = ?
            """,
            (
                item.canonical_url,
                item.title,
                item.publisher,
                item.published_at_iso(),
                item.raw_content,
                item.content_hash,
                item_id,
            ),
        )
        return item_id

    item_id = uuid.uuid4().hex
    conn.execute(
        """
        INSERT INTO items (
            item_id, source_id, external_id, canonical_url, title,
            publisher, published_at, raw_content, content_hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        ),
    )
    return item_id


def get_items_for_week(
    conn: sqlite3.Connection,
    week_start_iso: str,
    week_end_iso: str,
) -> list[sqlite3.Row]:
    """Return items whose ``published_at`` falls in [week_start, week_end), newest first."""
    return conn.execute(
        """
        SELECT *
          FROM items
         WHERE published_at >= ? AND published_at < ?
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
) -> str:
    """Insert a fresh ``item_summaries`` row. Caller is responsible for skip-if-exists."""
    summary_id = uuid.uuid4().hex
    conn.execute(
        """
        INSERT INTO item_summaries (
            summary_id, item_id, week_id, tldr, summary_confidence,
            prompt_version, model_id, input_tokens, output_tokens, cost_usd_estimate
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
