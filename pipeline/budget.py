"""Weekly LLM spend governance (D-59, D-60, D-61, D-B9).

Reservation accounting keeps $0.10 of the cap for meta stages (categorize,
rank, rollup) so per-item summarize cannot consume the full weekly budget.

Phase 5 (D-B9 + 05-CONTEXT) extends this module to a **cross-run** weekly
spend counter: cumulative cost flows back into ``WeekBudget`` from the
``pipeline_runs`` table so the Sunday cron and the Mon–Sat daily-retry
workflow share one bucket. When the $1/week hard cap fires, the
orchestrator marks unprocessed canonical items with
``summary_status='deferred_budget'`` and still publishes a partial
digest (OPS-05). ``HARD_CAP_USD`` env override (CI default 1.0) lets CI
run the same code path without editing ``config/digest.yaml``.
"""
from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass, field

from pipeline.config import load_digest_config
from pipeline.week import prior_week_id

DEFAULT_BASELINE_PER_ITEM_USD = 0.001
DEFAULT_META_PREFLIGHT_USD = 0.01
META_STAGE_ESTIMATE_USD = 0.005

# Env-var override for the hard cap (D-B9). CI sets this to drive the
# same gate as production without committing yaml edits. Any value that
# cannot be parsed as a positive float is silently ignored so a typo
# never escalates to a runtime crash.
HARD_CAP_USD_ENV = "HARD_CAP_USD"


@dataclass
class WeekBudget:
    """Tracks cap, reservation, and spend with stage-aware afford checks.

    Phase 5 additions (D-B9):
    - ``spent_usd`` is seeded from the cross-run cumulative spend for the
      active week so cron + daily-retry share one counter.
    - ``deferred_items`` records canonical item_ids whose summaries were
      skipped because the cap halted summarize. The list lives on the
      budget object so the orchestrator's mark-and-publish path can both
      append at halt time and read at finalize/report time without a
      second SQL aggregate.
    """

    cap_usd: float
    reserved_meta_usd: float
    spent_usd: float = 0.0
    halted: bool = False
    halted_at_stage: str | None = None
    pre_flight_estimate_usd: float = 0.0
    baseline_per_item_usd: float = DEFAULT_BASELINE_PER_ITEM_USD
    deferred_items: list[str] = field(default_factory=list)
    _spent_on_summarize: float = field(default=0.0, repr=False)

    @classmethod
    def from_config(
        cls,
        *,
        cap_override: float | None = None,
        conn: sqlite3.Connection | None = None,
        week_id: str | None = None,
    ) -> WeekBudget:
        """Load cap and reservation from ``config/digest.yaml`` (D-59).

        Cap-resolution precedence (highest wins):
            1. ``cap_override`` (CLI ``--max-cost-usd``)
            2. ``HARD_CAP_USD`` env var — CI/operator runtime knob (D-B9)
            3. ``config/digest.yaml`` ``pipeline.hard_stop_usd``

        When ``conn`` and ``week_id`` are provided, the per-item baseline
        comes from prior-week actuals and the spend counter is seeded
        from the cumulative cross-run aggregate so this week's daily
        retries don't race past the Sunday cron's spend.
        """
        cfg = load_digest_config()
        if cap_override is not None:
            cap = cap_override
        else:
            env_cap = _hard_cap_from_env()
            cap = env_cap if env_cap is not None else cfg.pipeline.hard_stop_usd
        baseline = DEFAULT_BASELINE_PER_ITEM_USD
        spent = 0.0
        if conn is not None and week_id is not None:
            baseline = baseline_per_item_from_runs(conn, week_id)
            spent = get_cumulative_week_spend_usd(conn, week_id)
        return cls(
            cap_usd=cap,
            reserved_meta_usd=cfg.pipeline.meta_reservation_usd,
            baseline_per_item_usd=baseline,
            spent_usd=round(spent, 6),
            _spent_on_summarize=round(spent, 6),
        )

    @staticmethod
    def load_weekly_spend(
        conn: sqlite3.Connection, week_id: str
    ) -> float:
        """Cross-run weekly spend loader (D-B4 + D-B9 shared counter).

        Thin instance-free wrapper around
        :func:`get_cumulative_week_spend_usd` so callers (tests, ad-hoc
        scripts, the daily-retry workflow's pre-flight log) can ask
        "how much have we spent so far this week?" without instantiating
        a full ``WeekBudget``.
        """
        return get_cumulative_week_spend_usd(conn, week_id)

    def mark_deferred_budget(self, item_id: str) -> None:
        """Record that ``item_id`` was skipped by the cap halt.

        The orchestrator calls this once per canonical item it could not
        summarize. The reporter consumes :attr:`deferred_items` (count
        only — item ids are not surfaced to readers per D-24).
        """
        if item_id not in self.deferred_items:
            self.deferred_items.append(item_id)

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


def _hard_cap_from_env() -> float | None:
    """Parse ``HARD_CAP_USD`` env var or return ``None`` if absent/invalid."""
    raw = os.environ.get(HARD_CAP_USD_ENV)
    if raw is None or raw.strip() == "":
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if value <= 0:
        return None
    return value


def get_cumulative_week_spend_usd(
    conn: sqlite3.Connection, week_id: str
) -> float:
    """Cross-run weekly spend (D-B4 + D-B9 shared counter).

    Returns the SUM of ``pipeline_runs.cost_usd_estimate`` for the active
    week across **all** terminal-status rows that represent real LLM
    work — ``success``, ``partial``, and ``failed``. ``failed`` is
    included because partial spend before a crash still hit the wallet
    and must count against the next run's cap budget.

    Phase-scoped rows are excluded (only ``phase='all'`` runs and
    ``phase='summarize'`` retries are aggregated) so an isolated
    ``run_render`` invocation does not double-count cost it already
    recorded on the original ``run_all``.
    """
    row = conn.execute(
        """
        SELECT COALESCE(SUM(cost_usd_estimate), 0.0) AS total
          FROM pipeline_runs
         WHERE week_id = ?
           AND status IN ('success', 'partial', 'failed')
           AND phase IN ('all', 'summarize')
        """,
        (week_id,),
    ).fetchone()
    if row is None:
        return 0.0
    return float(row["total"] or 0.0)


def baseline_per_item_from_runs(conn: sqlite3.Connection, week_id: str) -> float:
    """Prior-week per-item cost from completed ``pipeline_runs`` or conservative fallback.

    Looks up the ISO week before ``week_id`` so first-run-of-week pre-flight estimates
    use last week's actual spend-per-item ratio (D-59 / WR-02).
    """
    lookup_week = prior_week_id(week_id)
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
        (lookup_week,),
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
    "HARD_CAP_USD_ENV",
    "META_STAGE_ESTIMATE_USD",
    "WeekBudget",
    "baseline_per_item_from_runs",
    "get_cumulative_week_spend_usd",
]
