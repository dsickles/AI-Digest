"""Idempotence tests for migration 004."""
from __future__ import annotations

from pathlib import Path

from store.db import init_db


def test_init_db_twice_after_migration_004(temp_sqlite_path: Path) -> None:
    init_db(temp_sqlite_path)
    init_db(temp_sqlite_path)
