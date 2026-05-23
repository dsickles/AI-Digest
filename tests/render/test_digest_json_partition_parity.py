"""LOCKED-01 partition parity between digest JSON lists and partition router."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from pipeline.render.digest_json import emit_digest_json
from pipeline.render.partition import (
    QUOTA_BODY_COPY,
    _IN_PLACE_TRANSIENT_STATUSES,
    DigestCard,
)


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


def _emit(cards: list[DigestCard], tmp_path: Path, *, top_n: int = 5) -> dict:
    out_path = emit_digest_json(
        week_id="2026-W21",
        week_start=datetime(2026, 5, 18, tzinfo=UTC),
        week_end=datetime(2026, 5, 24, 23, 59, 59, tzinfo=UTC),
        cards=cards,
        out_dir=tmp_path,
        rollups_by_scope={},
        partial_publish=False,
        top_n_briefing=top_n,
        pipeline_report=None,
        conn=None,
    )
    return json.loads(out_path.read_text(encoding="utf-8"))


def test_thin_status_only_in_footer_aside(tmp_path: Path) -> None:
    payload = _emit([_card(tldr=None, summary_status="thin", title="ThinRss")], tmp_path)
    footer_titles = [c["title"] for c in payload["footer_aside"]]
    main_titles = [c["title"] for c in payload["main_feed"]]
    assert "ThinRss" in footer_titles
    assert "ThinRss" not in main_titles


def test_quota_exhausted_in_main_feed_with_degraded_body(tmp_path: Path) -> None:
    payload = _emit(
        [_card(tldr=None, summary_status="quota_exhausted", title="Quota")], tmp_path
    )
    assert payload["footer_aside"] == []
    assert len(payload["main_feed"]) == 1
    assert payload["main_feed"][0]["degraded_body"] == QUOTA_BODY_COPY
    assert payload["main_feed"][0]["tldr"] is None


def test_all_in_place_transient_statuses_get_degraded_body(tmp_path: Path) -> None:
    cards = [
        _card(tldr=None, summary_status=status, title=f"InPlace {status}")
        for status in sorted(_IN_PLACE_TRANSIENT_STATUSES)
    ]
    payload = _emit(cards, tmp_path)
    assert payload["footer_aside"] == []
    assert len(payload["main_feed"]) == len(_IN_PLACE_TRANSIENT_STATUSES)
    for card in payload["main_feed"]:
        assert card["degraded_body"] == QUOTA_BODY_COPY


def test_briefing_top_n_capped_by_config(tmp_path: Path) -> None:
    cards = [
        _card(
            tldr=f"Summary {n}.",
            summary_status="ok",
            title=f"Ranked {n}",
            rank_position=n,
        )
        for n in range(1, 8)
    ]
    payload = _emit(cards, tmp_path, top_n=3)
    assert len(payload["briefing_top_n"]) == 3
    assert [c["rank_position"] for c in payload["briefing_top_n"]] == [1, 2, 3]
