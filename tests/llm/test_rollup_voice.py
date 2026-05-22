"""Rollup voice ban-list assertions (D-57, 03-VALIDATION)."""
from __future__ import annotations

from unittest.mock import MagicMock

from pipeline.llm.rollup import (
    CATEGORY_PROMPT_VERSION,
    WEEKLY_PROMPT_VERSION,
    ClusterRollupInput,
    rollup_category,
    rollup_weekly,
)
from store.db import connect, init_db, insert_weekly_rollup

BAN_SUBSTRINGS = (
    "game-changer",
    "landscape",
    "delve",
    "it's worth noting",
    "significant implications",
    "paradigm shift",
)

# Mock output uses clean editorial prose (no ban-list words).
CLEAN_CATEGORY_NARRATIVE = (
    "OpenAI shipped GPT-6 on Tuesday; pricing is half of GPT-5 and context "
    "jumped to 2M tokens. Anthropic matched inference pricing the same day."
)

CLEAN_WEEKLY_NARRATIVE = (
    "OpenAI and Anthropic both cut inference prices mid-week while EU "
    "regulators finalized disclosure rules for general-purpose models.\n\n"
    "Classroom pilots and design tooling updates filled out a busy secondary lane."
)


def _mock_response(text: str) -> MagicMock:
    response = MagicMock()
    response.text = text
    usage = MagicMock()
    usage.prompt_token_count = 300
    usage.candidates_token_count = 100
    response.usage_metadata = usage
    return response


def test_category_rollup_narrative_excludes_ban_list(tmp_path) -> None:
    db_path = tmp_path / "voice-test.db"
    init_db(db_path)

    client = MagicMock()
    client.models.generate_content.return_value = _mock_response(
        CLEAN_CATEGORY_NARRATIVE
    )
    result = rollup_category(
        week_id="2026-W21",
        category="technical",
        clusters=[
            ClusterRollupInput(
                cluster_id="c-1",
                title="GPT-6 launch",
                summary_text="OpenAI announced GPT-6.",
                rank_position=1,
            )
        ],
        client=client,
    )
    assert result.rollup_status == "ok"
    assert result.narrative_md is not None
    lowered = result.narrative_md.lower()
    for banned in BAN_SUBSTRINGS:
        assert banned not in lowered

    with connect(db_path) as conn:
        insert_weekly_rollup(
            conn,
            week_id="2026-W21",
            scope="category:technical",
            narrative_md=result.narrative_md,
            rollup_status="ok",
            prompt_version=CATEGORY_PROMPT_VERSION,
            model_id="gemini-2.5-flash",
        )
        conn.commit()
        row = conn.execute(
            "SELECT narrative_md FROM weekly_rollups WHERE scope = 'category:technical'"
        ).fetchone()
    assert row is not None
    stored = row["narrative_md"].lower()
    assert "game-changer" not in stored
    assert "delve" not in stored


def test_weekly_rollup_narrative_excludes_ban_list() -> None:
    client = MagicMock()
    client.models.generate_content.return_value = _mock_response(CLEAN_WEEKLY_NARRATIVE)
    result = rollup_weekly(
        week_id="2026-W21",
        mini_paragraphs={
            "edtech": "Districts piloted classroom copilots.",
            "business": "Enterprise spend shifted to inference.",
            "technical": CLEAN_CATEGORY_NARRATIVE,
            "design": "Design tools added agent panels.",
        },
        client=client,
    )
    assert result.rollup_status == "ok"
    assert result.narrative_md is not None
    lowered = result.narrative_md.lower()
    for banned in BAN_SUBSTRINGS:
        assert banned not in lowered


def test_rollup_prompts_contain_ban_list_and_weekly_mini_only_input() -> None:
    from pathlib import Path

    category_path = (
        Path(__file__).resolve().parents[2]
        / "pipeline"
        / "llm"
        / "prompts"
        / "rollup_category_v1.md"
    )
    weekly_path = (
        Path(__file__).resolve().parents[2]
        / "pipeline"
        / "llm"
        / "prompts"
        / "rollup_weekly_v1.md"
    )
    category_text = category_path.read_text(encoding="utf-8")
    weekly_text = weekly_path.read_text(encoding="utf-8")
    assert "landscape" in category_text
    assert "four category mini-rollups" in weekly_text.lower()
    assert "{{mini_edtech}}" in weekly_text
    assert "{{ranked_clusters}}" in category_text
