"""CLI entry point — ``python -m pipeline.run all`` (D-19).

Plan 01-04 splits this into ``ingest``/``summarize``/``render``/``all``
subcommands. Skeleton ships only ``all``; an unrecognized subcommand
exits with usage and a non-zero status.

Loaded ONLY at the CLI boundary:
  - python-dotenv for ``.env`` (D-21)
  - structlog stdout configuration

Adapter / store / renderer modules must remain import-free of these
to keep tests fast and unit-testable.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys

import structlog
import truststore
from dotenv import load_dotenv

# Use the OS native trust store (macOS keychain, Windows certstore,
# system OpenSSL on Linux) so corporate-MITM and per-user-installed
# CAs are honored without copying bundles. Must run before any
# TLS-using import. Safe + cross-platform.
truststore.inject_into_ssl()


def _configure_logging() -> None:
    """structlog → stdout, info level by default; LOG_LEVEL env override.

    Plan 01-05 hardens this with json + last_run.md mirror; skeleton
    keeps it human-readable.
    """
    log_level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_name, logging.INFO)
    logging.basicConfig(level=log_level, format="%(message)s", stream=sys.stdout)
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.dev.ConsoleRenderer(colors=False),
        ],
        cache_logger_on_first_use=True,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m pipeline.run",
        description="AI Digest pipeline — RSS → SQLite → Gemini → HTML.",
    )
    sub = parser.add_subparsers(dest="command")

    all_cmd = sub.add_parser(
        "all",
        help="Run ingest → summarize → render in one pass (default).",
    )
    all_cmd.add_argument(
        "--week",
        dest="week_id",
        default=None,
        help="ISO week id YYYY-Www (e.g. 2026-W19); defaults to current UTC week.",
    )
    all_cmd.set_defaults(command="all")

    return parser


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    _configure_logging()
    parser = _build_parser()
    args = parser.parse_args(argv)

    command = getattr(args, "command", None) or "all"
    if command != "all":
        parser.error(f"unknown command: {command}")
        return 2

    from pipeline.orchestrator import run_all

    week_id = getattr(args, "week_id", None)
    try:
        stats = run_all(week_id=week_id)
    except Exception as exc:
        sys.stderr.write(f"pipeline failed: {type(exc).__name__}: {exc}\n")
        return 1

    sys.stdout.write(
        f"\nDigest written: {stats.out_path}\n"
        f"  week_id:           {stats.week_id}\n"
        f"  items_fetched:     {stats.items_fetched}\n"
        f"  summaries_written: {stats.summaries_written}\n"
        f"  items_degraded:    {stats.items_degraded}\n"
        f"  cost_usd_estimate: ${stats.cost_usd_estimate:.6f}\n"
        f"  errors:            {len(stats.errors)}\n"
    )
    return 0 if not stats.errors else 0  # partial success still returns 0


if __name__ == "__main__":
    raise SystemExit(main())
