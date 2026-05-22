"""Determinism tests for weekly rank ordering (mocked LLM)."""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

from pipeline.llm.rank import (
    MODEL_ID,
    PROMPT_VERSION,
    ClusterRankInput,
    RankResponse,
    RankScoreEntry,
    rank_week_clusters,
)


def _fixed_clusters() -> list[ClusterRankInput]:
    return [
        ClusterRankInput(
            cluster_id="cluster-alpha",
            category="technical",
            title="Alpha model release",
            summary_text="A lab shipped a new model with lower pricing.",
            published_at=datetime(2026, 5, 19, 12, 0, tzinfo=UTC),
        ),
        ClusterRankInput(
            cluster_id="cluster-beta",
            category="business",
            title="Beta acquisition",
            summary_text="A major vendor acquired a startup in the AI tooling space.",
            published_at=datetime(2026, 5, 21, 9, 0, tzinfo=UTC),
        ),
        ClusterRankInput(
            cluster_id="cluster-gamma",
            category="design",
            title="Gamma design system",
            summary_text="A product team published an updated design system for AI apps.",
            published_at=datetime(2026, 5, 20, 15, 0, tzinfo=UTC),
        ),
    ]


def _mock_client() -> MagicMock:
    response = MagicMock()
    response.parsed = RankResponse(
        rankings=[
            RankScoreEntry(cluster_id="cluster-alpha", rank_score=72.0),
            RankScoreEntry(cluster_id="cluster-beta", rank_score=91.5),
            RankScoreEntry(cluster_id="cluster-gamma", rank_score=55.0),
        ]
    )
    usage = MagicMock()
    usage.prompt_token_count = 350
    usage.candidates_token_count = 120
    response.usage_metadata = usage
    client = MagicMock()
    client.models.generate_content.return_value = response
    return client


def test_rank_position_ordering_stable_across_runs() -> None:
    """Fixed fixture → identical rank_position ordering with locked versioning."""
    clusters = _fixed_clusters()
    client = _mock_client()

    first = rank_week_clusters(week_id="2026-W21", clusters=clusters, client=client)
    second = rank_week_clusters(week_id="2026-W21", clusters=clusters, client=client)

    first_positions = [r.rank_position for r in first]
    second_positions = [r.rank_position for r in second]
    assert first_positions == second_positions == [1, 2, 3]

    for result in first:
        assert result.prompt_version == PROMPT_VERSION
        assert result.model_id == MODEL_ID

    by_cluster = {r.cluster_id: r for r in first}
    assert by_cluster["cluster-beta"].rank_position == 1
    assert by_cluster["cluster-alpha"].rank_position == 2
    assert by_cluster["cluster-gamma"].rank_position == 3
