"""Weekly LLM spend governance (D-59, D-60, D-61).

Reservation accounting keeps $0.10 of the cap for meta stages (categorize,
rank, rollup) so per-item summarize cannot consume the full weekly budget.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

from pipeline.config import load_digest_config

DEFAULT_BASELINE_PER_ITEM_USD = 0.001
DEFAULT_META_PREFLIGHT_USD = 0.01
META_STAGE_ESTIMATE_USD = 0.005


@dataclass
class WeekBudget:
    """Tracks cap, reservation, and spend with stage-aware afford checks."""

    cap_usd: float
    reserved_meta_usd: float
    spent_usd: float = 0.0
    halted: bool = False
    halted_at_stage: str | None = None
    pre_flight_estimate_usd: float = 0.0
    baseline_per_item_usd: float = DEFAULT_BASELINE_PER_ITEM_USD
    _spent_on_summarize: float = field(default=0.0, repr=False)

    @classmethod
    def from_config(
        cls,
        *,
        cap_override: float | None = None,
        conn: sqlite3.Connection | None = None,
        week_id: str | None = None,
    ) -> WeekBudget:
        """Load cap and reservation from ``config/digest.yaml`` (D-59)."""
        cfg = load_digest_config()
        cap = cap_override if cap_override is not None else cfg.pipeline.hard_stop_usd
        baseline = DEFAULT_BASELINE_PER_ITEM_USD
        if conn is not None and week_id is not None:
            baseline = baseline_per_item_from_runs(conn, week_id)
        return cls(
            cap_usd=cap,
            reserved_meta_usd=cfg.pipeline.meta_reservation_usd,
            baseline_per_item_usd=baseline,
        )

    @property
    def effective_meta_reservation_usd(self) -> float:
        """Meta reservation, capped when ``cap_usd`` is below configured reservation."""
        if self.cap_usd >= self.reserved_meta_usd:
            return self.reserved_meta_usd
        return round(min(self.reserved_meta_usd, self.cap_usd * 0.5), 6)

    @property
    def summarize_pool_usd(self) -> float:
        """Per-item pool after meta reservation (D-60)."""
        return max(
            0.0,
            self.cap_usd
            - self.effective_meta_reservation_usd
            - self._spent_on_summarize,
        )

    def set_pre_flight(
        self,
        *,
        pending_summarize: int,
        pending_meta_calls: int = 5,
    ) -> None:
        """Estimate remaining work at run start (D-59)."""
        self.pre_flight_estimate_usd = round(
            pending_summarize * self.baseline_per_item_usd
            + pending_meta_calls * META_STAGE_ESTIMATE_USD,
            6,
        )

    def record_spend(self, amount: float, *, stage: str) -> None:
        if amount and amount > 0:
            self.spent_usd += amount
            if stage == "summarize":
                self._spent_on_summarize += amount

    def can_afford(self, estimated_usd: float, *, stage: str) -> bool:
        if self.halted and stage == "summarize":
            return False
        est = round(estimated_usd, 6)
        spent = round(self.spent_usd, 6)
        if stage in {"categorize", "rank", "rollup"}:
            return spent + est <= round(self.cap_usd, 6)
        summarize_cap = round(self.cap_usd - self.effective_meta_reservation_usd, 6)
        return round(self._spent_on_summarize, 6) + est <= summarize_cap

    def halt_if_over_cap(self, *, stage: str) -> None:
        if not self.halted:
            self.halted_at_stage = stage
        self.halted = True

    def meta_stages_allowed(self) -> bool:
        """D-60: meta stages may run when reservation is intact after summarize halt."""
        if not self.halted:
            return True
        return self.spent_usd <= self.cap_usd


def baseline_per_item_from_runs(conn: sqlite3.Connection, week_id: str) -> float:
    """Prior-week per-item cost from ``pipeline_runs`` or conservative fallback."""
    row = conn.execute(
        """
        SELECT cost_usd_estimate, summaries_written
          FROM pipeline_runs
         WHERE week_id = ?
           AND phase = 'all'
           AND status IN ('success', 'partial')
           AND summaries_written > 0
         ORDER BY finished_at DESC
         LIMIT 1
        """,
        (week_id,),
    ).fetchone()
    if row is None:
        return DEFAULT_BASELINE_PER_ITEM_USD
    cost = float(row["cost_usd_estimate"] or 0.0)
    count = int(row["summaries_written"] or 0)
    if count <= 0:
        return DEFAULT_BASELINE_PER_ITEM_USD
    return max(DEFAULT_BASELINE_PER_ITEM_USD, round(cost / count, 6))


__all__ = [
    "DEFAULT_BASELINE_PER_ITEM_USD",
    "META_STAGE_ESTIMATE_USD",
    "WeekBudget",
    "baseline_per_item_from_runs",
]
