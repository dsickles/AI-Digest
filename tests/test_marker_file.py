"""Cron-complete marker file schema (D-B3 + D-B5b).

Wave 0 of plan 05-01 landed these as RED stubs; plan 05-02 turns them
GREEN by implementing ``pipeline.orchestrator.write_cron_complete_marker``
and the ``CLOUD_CRON_MODE`` env gate around it.

The marker file is the entire handoff protocol between cloud cron and
home worker (D-B5b). Shape per 05-CONTEXT.md D-B3:

```
markers/cron-complete-{week_id}.json
{"week_id": "2026-W21", "completed_at": "2026-05-24T10:38:14Z"}
```

The home worker polls the shared object-storage bucket every ~10
minutes, finds the marker whose ``week_id`` matches the current
calendar week, downloads the DB, runs ``--only-pending-transcripts``,
and deletes the marker on success (idempotency: a duplicate cycle
finds no marker and exits).
"""
from __future__ import annotations

from pathlib import Path

import pytest


def test_marker_writer_exists() -> None:
    """Plan 05-02 must export a ``write_cron_complete_marker`` (or analogous)
    function from the orchestrator or a new ``pipeline.markers`` module."""
    pytest.importorskip("pipeline.orchestrator")
    from pipeline import orchestrator

    writer = (
        getattr(orchestrator, "write_cron_complete_marker", None)
        or getattr(orchestrator, "write_marker", None)
    )
    if writer is None:
        try:
            from pipeline import markers  # noqa: PLC0415 — RED stub

            writer = getattr(markers, "write_cron_complete", None)
        except ImportError:
            writer = None
    assert writer is not None, (
        "Plan 05-02 must add a cron-complete marker writer "
        "(pipeline.orchestrator.write_cron_complete_marker or "
        "pipeline.markers.write_cron_complete) per D-B5b"
    )


def test_marker_roundtrip_shape(tmp_path: Path) -> None:
    """Plan 05-02 marker must roundtrip {week_id, completed_at} cleanly."""
    pytest.importorskip("pipeline.orchestrator")
    from pipeline import orchestrator

    writer = (
        getattr(orchestrator, "write_cron_complete_marker", None)
        or getattr(orchestrator, "write_marker", None)
    )
    assert writer is not None, "writer missing — see other failing test"

    target = tmp_path / "markers" / "cron-complete-2026-W21.json"
    writer(week_id="2026-W21", markers_dir=tmp_path / "markers")
    assert target.exists(), "writer must create markers/cron-complete-{week_id}.json"

    import json

    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["week_id"] == "2026-W21"
    assert "completed_at" in payload
    completed_at = payload["completed_at"]
    assert isinstance(completed_at, str)
    assert completed_at.endswith("Z") or "+" in completed_at, (
        "completed_at must be RFC 3339 / ISO 8601 with timezone (D-B5b)"
    )


def test_marker_filename_is_cron_complete_week_id_json() -> None:
    """Marker filename pattern is locked in 05-CONTEXT.md D-B5b."""
    expected = "cron-complete-2026-W21.json"
    assert expected.startswith("cron-complete-")
    assert expected.endswith(".json")


def test_cloud_cron_mode_env_var_exported() -> None:
    """Plan 05-02 declares ``CLOUD_CRON_MODE`` as the orchestrator gate
    that distinguishes a cloud Sunday cron run (which writes a marker)
    from a local manual run (which does not)."""
    from pipeline.orchestrator import CLOUD_CRON_MODE_ENV

    assert CLOUD_CRON_MODE_ENV == "CLOUD_CRON_MODE"


def test_maybe_write_cron_complete_marker_respects_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``_maybe_write_cron_complete_marker`` only writes when
    ``CLOUD_CRON_MODE=1``; any other value (unset, "0", "true", "") is a
    local manual run and must NOT produce a marker."""
    import logging

    from pipeline.orchestrator import (
        CLOUD_CRON_MODE_ENV,
        _maybe_write_cron_complete_marker,
    )

    monkeypatch.chdir(tmp_path)
    log = logging.getLogger("test")
    log.info = lambda *a, **k: None  # type: ignore[assignment]
    log.warning = lambda *a, **k: None  # type: ignore[assignment]

    for non_cloud in ("", "0", "true", "yes", "false"):
        monkeypatch.setenv(CLOUD_CRON_MODE_ENV, non_cloud)
        _maybe_write_cron_complete_marker("2026-W21", log)
        assert not (tmp_path / "markers" / "cron-complete-2026-W21.json").exists(), (
            f"Marker must not be written when {CLOUD_CRON_MODE_ENV}={non_cloud!r}"
        )

    monkeypatch.setenv(CLOUD_CRON_MODE_ENV, "1")
    _maybe_write_cron_complete_marker("2026-W21", log)
    assert (tmp_path / "markers" / "cron-complete-2026-W21.json").exists(), (
        f"Marker must be written when {CLOUD_CRON_MODE_ENV}=1"
    )
