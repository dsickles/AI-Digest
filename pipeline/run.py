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

    sub = parser.add_subparsers(dest="command")

    ingest_cmd = sub.add_parser(
        "ingest",
        help="Fetch enabled sources and upsert into SQLite (network only).",
    )
    _add_week_arg(ingest_cmd)
    _add_only_pending_transcripts_arg(ingest_cmd)

    summarize_cmd = sub.add_parser(
        "summarize",
        help="Summarize items in the week window missing a TL;DR (LLM).",
    )
    _add_week_arg(summarize_cmd)

    render_cmd = sub.add_parser(
        "render",
        help="Render HTML digest from SQLite (no network, no LLM).",
    )
    _add_week_arg(render_cmd)

    dedup_cmd = sub.add_parser(
        "dedup",
        help="Cluster same-story items for the week (deterministic).",
    )
    _add_week_arg(dedup_cmd)

    categorize_cmd = sub.add_parser(
        "categorize",
        help="Classify story clusters into edtech|business|technical|design.",
    )
    _add_week_arg(categorize_cmd)

    all_cmd = sub.add_parser(
        "all",
        help="Run ingest → dedup → summarize → categorize → render (default).",
    )
    _add_week_arg(all_cmd)
    _add_only_pending_transcripts_arg(all_cmd)

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

    try:
        if command == "ingest":
            from pipeline.orchestrator import run_ingest

            stats = run_ingest(week_id, only_pending_transcripts=only_pending)
        elif command == "summarize":
            from pipeline.orchestrator import run_summarize

            stats = run_summarize(week_id)
        elif command == "render":
            from pipeline.orchestrator import run_render

            stats = run_render(week_id)
        elif command == "dedup":
            from pipeline.orchestrator import run_dedup

            stats = run_dedup(week_id)
        elif command == "categorize":
            from pipeline.orchestrator import run_categorize

            stats = run_categorize(week_id)
        elif command == "all":
            from pipeline.orchestrator import run_all

            stats = run_all(week_id, only_pending_transcripts=only_pending)
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
