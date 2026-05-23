"""OBS-01 pipeline_notes emitter tests (D-A4a, D-A4b, LOCKED-01)."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from pipeline.render.digest_json import _build_pipeline_notes, emit_digest_json
from pipeline.render.partition import PARTIAL_PUBLISH_COPY, DigestCard
from pipeline.week import prior_week_id


def _card(**kwargs: object) -> DigestCard:
    defaults = {
        "title": "Story",
        "publisher": "Example Publisher",
        "canonical_url": "https://example.com/post",
        "published_at": datetime(2026, 5, 20, tzinfo=UTC),
        "tldr": "Summary text.",
        "summary_confidence": "high",
        "summary_status": "ok",
    }
    defaults.update(kwargs)
    return DigestCard(**defaults)  # type: ignore[arg-type]


def test_zero_state_returns_none() -> None:
    notes = _build_pipeline_notes(
        cards=[_card()],
        pipeline_report={"summary_status": {"ok": 1}, "source_health": {}, "budget": {}},
        conn=None,
        week_id="2026-W21",
    )
    assert notes is None


def test_silent_source_requires_three_consecutive_empty_weeks(apply_schema) -> None:
    from store.db import connect

    from pipeline.week import week_bounds

    week_id = "2026-W21"
    source_id = "silent-feed"
    break_week = "2026-W18"
    break_start, _ = week_bounds(break_week)
    published_at = break_start.strftime("%Y-%m-%dT%H:%M:%SZ")

    with connect(apply_schema) as conn:
        conn.execute(
            """
            INSERT INTO sources (source_id, type, url, display_name, enabled)
            VALUES (?, 'rss', 'https://example.com/feed', 'Silent Publisher', 1)
            """,
            (source_id,),
        )
        conn.execute(
            """
            INSERT INTO items (
                item_id, source_id, external_id, canonical_url, title,
                publisher, published_at, content_hash, ingested_at
            ) VALUES (?, ?, 'ext-1', 'https://example.com/1', 'Break streak', ?, ?, 'hash', ?)
            """,
            (
                "item-break",
                source_id,
                source_id,
                published_at,
                published_at,
            ),
        )
        conn.commit()

    health = {
        source_id: {
            "last_error_category": "empty_feed",
            "items_this_week": 0,
        }
    }

    with connect(apply_schema) as conn, patch(
        "pipeline.render.digest_json._publisher_display_name",
        return_value="Silent Publisher",
    ):
        two_week_notes = _build_pipeline_notes(
            cards=[],
            pipeline_report={
                "summary_status": {},
                "source_health": health,
                "budget": {},
            },
            conn=conn,
            week_id=prior_week_id(week_id),
        )
        assert two_week_notes is None

        three_week_notes = _build_pipeline_notes(
            cards=[],
            pipeline_report={
                "summary_status": {},
                "source_health": health,
                "budget": {},
            },
            conn=conn,
            week_id=week_id,
        )
        assert three_week_notes is not None
        assert any(
            "third week in a row" in line for line in three_week_notes.details
        )
        assert any(
            "Silent Publisher didn't publish" in line
            for line in three_week_notes.details
        )


def test_fetch_failure_copy_in_details() -> None:
    with patch(
        "pipeline.render.digest_json._publisher_display_name",
        return_value="Ben's Bites",
    ):
        notes = _build_pipeline_notes(
            cards=[],
            pipeline_report={
                "summary_status": {},
                "source_health": {
                    "bens-bites": {"last_error_category": "fetch_timeout"}
                },
                "budget": {},
            },
            conn=None,
            week_id="2026-W21",
        )
        assert notes is not None
        assert notes.details == [
            "Ben's Bites couldn't be reached this Sunday morning. "
            "The next run will retry."
        ]


def test_budget_halt_includes_partial_publish_copy_in_details() -> None:
    notes = _build_pipeline_notes(
        cards=[],
        pipeline_report={
            "summary_status": {},
            "source_health": {},
            "budget": {"halted": True},
        },
        conn=None,
        week_id="2026-W21",
    )
    assert notes is not None
    assert PARTIAL_PUBLISH_COPY in notes.details


def test_emit_failure_notice_matches_ui_spec(tmp_path: Path) -> None:
    out_path = emit_digest_json(
        week_id="2026-W21",
        week_start=datetime(2026, 5, 18, tzinfo=UTC),
        week_end=datetime(2026, 5, 24, 23, 59, 59, tzinfo=UTC),
        cards=[_card()],
        out_dir=tmp_path,
        rollups_by_scope={},
        partial_publish=True,
        top_n_briefing=5,
        pipeline_report={"budget": {"halted": True}, "summary_status": {}, "source_health": {}},
        conn=None,
    )
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["failure_notice"] == {
        "kind": "partial_publish",
        "body": PARTIAL_PUBLISH_COPY,
    }


def test_pipeline_notes_builder_does_not_reference_thin_status() -> None:
    source = Path("pipeline/render/digest_json.py").read_text(encoding="utf-8")
    builder_start = source.index("def _build_pipeline_notes")
    builder_end = source.index("def emit_digest_json", builder_start)
    builder_source = source[builder_start:builder_end]
    assert "thin" not in builder_source

    notes = _build_pipeline_notes(
        cards=[_card(summary_status="thin", tldr=None, summary_confidence="unavailable")],
        pipeline_report={
            "summary_status": {"thin": 5},
            "source_health": {},
            "budget": {},
        },
        conn=None,
        week_id="2026-W21",
    )
    assert notes is None


def test_pending_local_summary_line(tmp_path: Path) -> None:
    notes = _build_pipeline_notes(
        cards=[
            _card(transcript_status="pending_local"),
            _card(transcript_status="pending_local"),
        ],
        pipeline_report={"summary_status": {}, "source_health": {}, "budget": {}},
        conn=None,
        week_id="2026-W21",
    )
    assert notes is not None
    assert notes.summary_line == "2 video summaries pending"
    assert any("2 video transcripts will fill in" in d for d in notes.details)
