"""Write ``out/last_run.md`` — human-readable run report (D-08).

Overwritten on every pipeline subcommand completion. Never writes API keys
or full article bodies (T-01-01).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

DEFAULT_OUT_PATH = Path("out") / "last_run.md"


@dataclass
class RunSummary:
    """Aggregate metrics for one pipeline subcommand run."""

    week_id: str
    phase: str
    started_at: datetime | None
    finished_at: datetime | None
    status: str
    items_fetched: int = 0
    summaries_written: int = 0
    items_degraded: int = 0
    llm_calls: int = 0
    cost_usd_estimate: float = 0.0
    per_source: list[tuple[str, int, list[str]]] = field(default_factory=list)
    errors: list[dict[str, str]] = field(default_factory=list)
    out_path: Path | None = None


def _fmt_ts(dt: datetime | None) -> str:
    if dt is None:
        return "—"
    return dt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _error_line(err: dict[str, str]) -> str:
    parts = [err.get("phase", "unknown")]
    if err.get("source_id"):
        parts.append(err["source_id"])
    if err.get("item_id"):
        parts.append(err["item_id"][:8])
    parts.append(err.get("error", "unknown error"))
    return " · ".join(parts)


def write_last_run_md(
    run_summary: RunSummary,
    *,
    out_path: Path | None = None,
) -> Path:
    """Write markdown run report; returns the path written."""
    target = out_path or DEFAULT_OUT_PATH
    target.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = [
        "# Last pipeline run",
        "",
        "## Run metadata",
        "",
        f"- **week_id:** `{run_summary.week_id}`",
        f"- **phase:** `{run_summary.phase}`",
        f"- **status:** `{run_summary.status}`",
        f"- **started:** {_fmt_ts(run_summary.started_at)}",
        f"- **finished:** {_fmt_ts(run_summary.finished_at)}",
    ]
    if run_summary.out_path is not None:
        lines.append(f"- **digest:** `{run_summary.out_path}`")

    lines.extend(["", "## Per-source", ""])
    if run_summary.per_source:
        lines.append("| source_id | items_fetched | errors |")
        lines.append("|-----------|---------------|--------|")
        for source_id, count, src_errors in run_summary.per_source:
            err_cell = "; ".join(src_errors) if src_errors else "—"
            lines.append(f"| `{source_id}` | {count} | {err_cell} |")
    else:
        lines.append("_No source breakdown (render-only or no ingest)._")

    lines.extend(
        [
            "",
            "## Totals",
            "",
            f"- **items_fetched:** {run_summary.items_fetched}",
            f"- **summaries_written:** {run_summary.summaries_written}",
            f"- **items_degraded:** {run_summary.items_degraded}",
            "",
            "## LLM",
            "",
            f"- **llm_calls:** {run_summary.llm_calls}",
            f"- **cost_usd_estimate:** ${run_summary.cost_usd_estimate:.6f}",
            "",
            "## Errors",
            "",
        ]
    )
    if run_summary.errors:
        for err in run_summary.errors:
            lines.append(f"- {_error_line(err)}")
    else:
        lines.append("_None._")

    lines.append("")
    target.write_text("\n".join(lines), encoding="utf-8")
    return target


__all__ = ["RunSummary", "write_last_run_md"]
