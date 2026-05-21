"""Smoke tests for the SQLite store.

Task 1 placeholder: only asserts schema applies. Real store tests
(upsert idempotence, etc.) land in Task 2.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path


def test_apply_schema_creates_items_table(apply_schema: Path) -> None:
    """init_db should create the items table on a fresh SQLite file."""
    with sqlite3.connect(apply_schema) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='items'"
        ).fetchall()
    assert rows == [("items",)], f"expected 'items' table, got {rows!r}"
