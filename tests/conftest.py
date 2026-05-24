"""Shared pytest fixtures for the AI Digest test suite."""
from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

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


class _B2Stub:
    """In-memory stand-in for ``rclone``-backed B2 access used in Phase 5
    cron/home-worker rendezvous tests (D-B3 + D-B5b). Models a flat
    key/value bucket; ``ls`` lists keys under a prefix and
    ``copy_in``/``copy_out`` move bytes between disk and the fake bucket."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self._bucket: dict[str, bytes] = {}
        self.calls: list[tuple[str, str]] = []  # (verb, key) audit log

    def copy_in(self, src: Path, key: str) -> None:
        self.calls.append(("copy_in", key))
        self._bucket[key] = Path(src).read_bytes()

    def copy_out(self, key: str, dst: Path) -> None:
        self.calls.append(("copy_out", key))
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(self._bucket[key])

    def ls(self, prefix: str) -> list[str]:
        self.calls.append(("ls", prefix))
        return sorted(k for k in self._bucket if k.startswith(prefix))

    def write_json(self, key: str, payload: dict[str, Any]) -> None:
        self.calls.append(("write_json", key))
        self._bucket[key] = json.dumps(payload).encode("utf-8")

    def read_json(self, key: str) -> dict[str, Any]:
        self.calls.append(("read_json", key))
        return json.loads(self._bucket[key].decode("utf-8"))

    def delete(self, key: str) -> None:
        self.calls.append(("delete", key))
        self._bucket.pop(key, None)

    def exists(self, key: str) -> bool:
        return key in self._bucket


@pytest.fixture
def b2_stub_fixture(tmp_path: Path) -> _B2Stub:
    """In-memory B2 stand-in for cron/home-worker marker rendezvous tests
    (D-B3 + D-B5b). Replaces the real ``rclone`` subprocess shell-outs so
    no external network or binary is required."""
    return _B2Stub(root=tmp_path / "b2-fake")


class _HealthcheckStub:
    """Records GET/POST calls that would have been ``curl``-ed to
    Healthchecks.io. Lets tests assert ping-URL + payload contracts (D-B7)
    without any real HTTP traffic."""

    def __init__(self) -> None:
        self.pings: list[dict[str, Any]] = []

    def ping(self, url: str, *, body: str | None = None) -> None:
        self.pings.append({"url": url, "body": body})

    def urls(self) -> list[str]:
        return [p["url"] for p in self.pings]


@pytest.fixture
def healthcheck_stub_fixture() -> _HealthcheckStub:
    """In-memory replacement for the Healthchecks.io ping caller (D-B7).

    Phase 5 cron + worker + sentinel each ping start/end URLs; this stub
    captures the calls so tests can verify the three-checks contract
    (D-B7) without hitting the network."""
    return _HealthcheckStub()
