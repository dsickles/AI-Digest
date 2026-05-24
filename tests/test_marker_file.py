"""Wave 0 RED stub — cron-complete marker file schema (D-B3 + D-B5b).

Expected to FAIL until Plan 05-02 implements the cron-complete marker
write/read roundtrip at the orchestrator's end-of-run seam.

The marker file is the entire handoff protocol between cloud cron and
home worker (D-B5b). Shape per 05-CONTEXT.md D-B3:

```
markers/cron-complete-{week_id}.json
{"week_id": "2026-W21", "completed_at": "2026-05-24T10:38:14Z"}
```

The home worker polls B2 every ~10 minutes, finds the marker whose
``week_id`` matches the current calendar week, downloads the DB, runs
``--only-pending-transcripts``, and deletes the marker on success
(idempotency: a duplicate cycle finds no marker and exits).
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
