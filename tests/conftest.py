"""Shared pytest fixtures for the AI Digest test suite."""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture
def temp_sqlite_path(tmp_path: Path) -> Iterator[Path]:
    """Yield a temporary on-disk SQLite path for tests that need a real file.

    Using an on-disk DB (not :memory:) so WAL mode and `init_db` behave the
    same way they do in production.
    """
    db_path = tmp_path / "aidigest-test.db"
    yield db_path
    if db_path.exists():
        db_path.unlink()


@pytest.fixture
def apply_schema(temp_sqlite_path: Path) -> Path:
    """Apply the production schema to a temp DB and return its path.

    Skips at collection time if ``store.db`` is not yet importable
    (allows Task 1 scaffold to ship before Task 2 creates the store).
    """
    pytest.importorskip("store.db")
    from store.db import init_db

    init_db(temp_sqlite_path)
    return temp_sqlite_path
