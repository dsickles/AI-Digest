"""Digest JSON schema contract tests (D-A2c, schema_version 1)."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from pipeline.render.digest_json import DigestDocument, emit_digest_json
from pipeline.render.partition import DigestCard


def _card(
    *,
    tldr: str | None,
    summary_status: str | None,
    title: str = "Story",
    rank_position: int | None = None,
) -> DigestCard:
    return DigestCard(
        title=title,
        publisher="Example Publisher",
        canonical_url="https://example.com/post",
        published_at=datetime(2026, 5, 20, tzinfo=UTC),
        tldr=tldr,
        summary_confidence="unavailable" if not tldr else "high",
        summary_status=summary_status,
        rank_position=rank_position,
    )


def test_emitted_json_has_schema_version_one_and_validates(tmp_path: Path) -> None:
    cards = [_card(tldr="Summary text.", summary_status="ok")]
    out_path = emit_digest_json(
        week_id="2026-W21",
        week_start=datetime(2026, 5, 18, tzinfo=UTC),
        week_end=datetime(2026, 5, 24, 23, 59, 59, tzinfo=UTC),
        cards=cards,
        out_dir=tmp_path,
        rollups_by_scope={},
        partial_publish=False,
        top_n_briefing=5,
        pipeline_report=None,
        conn=None,
    )
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    doc = DigestDocument.model_validate(payload)
    assert doc.week_id == "2026-W21"
    assert doc.main_feed[0].title == "Story"
    assert doc.generated_at.endswith("Z")
    assert doc.week_range.start.endswith("Z")
    assert doc.week_range.end.endswith("Z")


def test_emitter_source_has_no_gemini_string() -> None:
    source_path = Path("pipeline/render/digest_json.py")
    text = source_path.read_text(encoding="utf-8")
    assert "GEMINI" not in text
