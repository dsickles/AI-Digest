"""CLI entry point — ``python -m pipeline.run all`` (D-19).

Subcommands: ``ingest``, ``summarize``, ``render``, ``all``. Bare invocation
(with no subcommand) aliases ``all``. ``--week YYYY-Www`` overrides the ISO
week for backfill / replay (D-11, D-12).

Loaded ONLY at the CLI boundary:
  - python-dotenv for ``.env`` (D-21)
  - structlog stdout configuration
  - truststore for OS-native TLS trust

Adapter / store / renderer modules must remain import-free of these
to keep tests fast and unit-testable.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import truststore
from dotenv import load_dotenv

from pipeline.logging_config import configure_structlog

# Use the OS native trust store (macOS keychain, Windows certstore,
# system OpenSSL on Linux) so corporate-MITM and per-user-installed
# CAs are honored without copying bundles. Must run before any
# TLS-using import. Safe + cross-platform.
truststore.inject_into_ssl()

_WEEK_HELP = (
    "ISO week id YYYY-Www (e.g. 2026-W19) for backfill / replay; "
    "defaults to the current UTC ISO week."
)


_PENDING_TRANSCRIPTS_HELP = (
    "Re-fetch YouTube transcripts for items left in 'pending_local' from a "
    "previous run (typical case: cloud weekly run was blocked by YouTube). "
    "Skips RSS sources entirely. Intended to be run from a residential "
    "network where the YouTube transcript API works without a proxy."
)


def _add_week_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--week",
        dest="week_id",
        default=None,
        metavar="YYYY-Www",
        help=_WEEK_HELP,
    )


def _add_only_pending_transcripts_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--only-pending-transcripts",
        dest="only_pending_transcripts",
        action="store_true",
        default=False,
        help=_PENDING_TRANSCRIPTS_HELP,
    )


def _add_phase3_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--top-n",
        dest="top_n_briefing",
        type=int,
        default=None,
        metavar="N",
        help="Override config/digest.yaml top_n_briefing for Briefing section size.",
    )
    parser.add_argument(
        "--max-cost-usd",
        dest="max_cost_usd",
        type=float,
        default=None,
        metavar="USD",
        help="Override pipeline.hard_stop_usd weekly LLM spend cap (default 2.0).",
    )
    parser.add_argument(
        "--rebuild-clusters",
        dest="force_rebuild_clusters",
        action="store_true",
        default=False,
        help="Force dedup and downstream cascade for the target week.",
    )
    parser.add_argument(
        "--rebuild-rollup",
        dest="force_rebuild_rollup",
        action="store_true",
        default=False,
        help="Force rollup stages to re-run (category minis + weekly synthesis).",
    )


def _add_render_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--no-html-preview",
        dest="no_html_preview",
        action="store_true",
        default=False,
        help=(
            "Skip deprecated out/digest-{week}.html dev preview; "
            "emit digest JSON archive only."
        ),
    )
    parser.add_argument(
        "--web-out",
        dest="web_out_dir",
        type=Path,
        default=None,
        metavar="PATH",
        help="Override web/src/content/digests output directory for digest JSON.",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m pipeline.run",
        description=(
            "AI Digest pipeline — RSS → SQLite → Gemini → HTML. "
            "Use --week to backfill or replay a past ISO week (UTC)."
        ),
    )
    _add_week_arg(parser)
    _add_only_pending_transcripts_arg(parser)
    _add_phase3_flags(parser)

    sub = parser.add_subparsers(dest="command")

    ingest_cmd = sub.add_parser(
        "ingest",
        help="Fetch enabled sources and upsert into SQLite (network only).",
    )
    _add_week_arg(ingest_cmd)
    _add_only_pending_transcripts_arg(ingest_cmd)

    dedup_cmd = sub.add_parser(
        "dedup",
        help="Cluster same-story items for the week (deterministic).",
    )
    _add_week_arg(dedup_cmd)
    _add_phase3_flags(dedup_cmd)

    categorize_cmd = sub.add_parser(
        "categorize",
        help="Classify story clusters into edtech|business|technical.",
    )
    _add_week_arg(categorize_cmd)
    _add_phase3_flags(categorize_cmd)

    rank_cmd = sub.add_parser(
        "rank",
        help="Rank story clusters for the week Briefing Top N (LLM).",
    )
    _add_week_arg(rank_cmd)
    _add_phase3_flags(rank_cmd)

    rollup_cmd = sub.add_parser(
        "rollup",
        help="Generate category mini rollups and weekly synthesis (LLM).",
    )
    _add_week_arg(rollup_cmd)
    _add_phase3_flags(rollup_cmd)

    all_cmd = sub.add_parser(
        "all",
        help="Run ingest → dedup → summarize → categorize → rank → rollup → render (default).",
    )
    _add_week_arg(all_cmd)
    _add_only_pending_transcripts_arg(all_cmd)
    _add_phase3_flags(all_cmd)

    summarize_cmd = sub.add_parser(
        "summarize",
        help="Summarize items in the week window missing a TL;DR (LLM).",
    )
    _add_week_arg(summarize_cmd)
    _add_phase3_flags(summarize_cmd)

    render_cmd = sub.add_parser(
        "render",
        help="Render HTML digest from SQLite (no network, no LLM).",
    )
    _add_week_arg(render_cmd)
    _add_phase3_flags(render_cmd)
    _add_render_flags(render_cmd)

    return parser


def _resolve_week_id(args: argparse.Namespace) -> str:
    from pipeline.week import current_week_id, parse_week_id

    week_id = args.week_id or current_week_id()
    parse_week_id(week_id)
    return week_id


def _print_stats(stats, *, command: str) -> None:
    sys.stdout.write(f"\nPipeline {command} complete.\n")
    sys.stdout.write(f"  week_id:           {stats.week_id}\n")
    sys.stdout.write(f"  items_fetched:     {stats.items_fetched}\n")
    sys.stdout.write(f"  summaries_written: {stats.summaries_written}\n")
    sys.stdout.write(f"  items_degraded:    {stats.items_degraded}\n")
    sys.stdout.write(f"  cost_usd_estimate: ${stats.cost_usd_estimate:.6f}\n")
    sys.stdout.write(f"  errors:            {len(stats.errors)}\n")
    if stats.out_path is not None:
        sys.stdout.write(f"  digest:            {stats.out_path}\n")
    if getattr(stats, "digest_json_path", None) is not None:
        sys.stdout.write(f"  digest_json:       {stats.digest_json_path}\n")


def _phase3_kwargs(args: argparse.Namespace) -> dict:
    """Extract optional Phase 3 CLI overrides for orchestrator entry points."""
    return {
        "top_n_briefing": getattr(args, "top_n_briefing", None),
        "max_cost_usd": getattr(args, "max_cost_usd", None),
        "force_rebuild_clusters": getattr(args, "force_rebuild_clusters", False),
        "force_rebuild_rollup": getattr(args, "force_rebuild_rollup", False),
    }


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    configure_structlog()
    parser = _build_parser()
    args = parser.parse_args(argv)

    command = args.command or "all"
    week_id = _resolve_week_id(args)

    only_pending = getattr(args, "only_pending_transcripts", False)
    if only_pending and command not in {"ingest", "all"}:
        parser.error(
            "--only-pending-transcripts is only valid with `ingest` or `all`"
        )

    p3 = _phase3_kwargs(args)

    try:
        if command == "ingest":
            from pipeline.orchestrator import run_ingest

            stats = run_ingest(week_id, only_pending_transcripts=only_pending)
        elif command == "summarize":
            from pipeline.orchestrator import run_summarize

            stats = run_summarize(week_id, max_cost_usd=p3["max_cost_usd"])
        elif command == "render":
            from pipeline.orchestrator import run_render

            stats = run_render(
                week_id,
                top_n_briefing=p3["top_n_briefing"],
                no_html_preview=getattr(args, "no_html_preview", False),
                web_out_dir=getattr(args, "web_out_dir", None),
            )
        elif command == "dedup":
            from pipeline.orchestrator import run_dedup

            stats = run_dedup(
                week_id,
                force_rebuild_clusters=p3["force_rebuild_clusters"],
            )
        elif command == "categorize":
            from pipeline.orchestrator import run_categorize

            stats = run_categorize(week_id, max_cost_usd=p3["max_cost_usd"])
        elif command == "rank":
            from pipeline.orchestrator import run_rank

            stats = run_rank(week_id, max_cost_usd=p3["max_cost_usd"])
        elif command == "rollup":
            from pipeline.orchestrator import run_rollup

            stats = run_rollup(
                week_id,
                max_cost_usd=p3["max_cost_usd"],
                force_rebuild_rollup=p3["force_rebuild_rollup"],
            )
        elif command == "all":
            from pipeline.orchestrator import run_all

            stats = run_all(
                week_id,
                only_pending_transcripts=only_pending,
                **p3,
            )
        else:
            parser.error(f"unknown command: {command}")
            return 2
    except Exception as exc:
        sys.stderr.write(f"pipeline failed: {type(exc).__name__}: {exc}\n")
        return 1

    _print_stats(stats, command=command)
    return 0 if not stats.errors else 0  # partial success still returns 0


if __name__ == "__main__":
    raise SystemExit(main())
