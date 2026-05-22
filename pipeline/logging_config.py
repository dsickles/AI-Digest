"""structlog configuration for the AI Digest CLI (D-07).

Invoked once from ``pipeline.run`` before any subcommand. TTY stdout gets
human-readable key=value lines; non-TTY (CI, pipes) gets JSON lines.
"""
from __future__ import annotations

import logging
import os
import sys

import structlog


def configure_structlog() -> None:
    """Configure structlog → stdout with ISO UTC timestamps."""
    log_level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_name, logging.INFO)
    logging.basicConfig(level=log_level, format="%(message)s", stream=sys.stdout)

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]

    if sys.stdout.isatty():
        renderer: structlog.types.Processor = structlog.dev.ConsoleRenderer(
            colors=False
        )
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        processors=[*shared_processors, renderer],
        cache_logger_on_first_use=True,
    )


__all__ = ["configure_structlog"]
