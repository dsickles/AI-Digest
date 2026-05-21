"""RSS / Atom adapter (INGEST-02).

Uses feedparser for parsing and httpx for the HTTP fetch so we can set a
sane User-Agent (some feeds 403 the default Python UA). External-id
derivation follows RESEARCH §1: prefer stable GUID, fall back to a
sha256(canonical_url + published_day) hash so re-ingest stays idempotent
even when GUIDs are missing.
"""
from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime

import feedparser
import httpx
import structlog

from pipeline.adapters.base import FetchError, IngestAdapter
from pipeline.config import SourceConfig
from pipeline.models import NormalizedItem

logger = structlog.get_logger(__name__)

USER_AGENT = "aidigest/0.1 (+https://github.com/dan-sickles/aidigest)"
HTTP_TIMEOUT_SECONDS = 20.0


def _extract_published(entry: feedparser.FeedParserDict) -> datetime | None:
    """Resolve the best timestamp; tz-aware UTC or None.

    Order per RESEARCH §1: published → updated → created. Bozo entries with
    all-None date fields are excluded by the caller.
    """
    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        struct = entry.get(key)
        if struct:
            return datetime(*struct[:6], tzinfo=UTC)
    return None


def _extract_body(entry: feedparser.FeedParserDict) -> str:
    """Atom ``content[0].value`` if present, else RSS ``summary``, else empty."""
    content = entry.get("content")
    if content:
        try:
            return content[0].get("value", "") or ""
        except (IndexError, AttributeError, TypeError):
            return ""
    return entry.get("summary", "") or ""


def _derive_external_id(
    entry: feedparser.FeedParserDict,
    canonical_url: str,
    published_day: str,
) -> str:
    """Stable per-item ID — see plan key_links (upsert idempotence)."""
    guid = entry.get("id") or entry.get("guid")
    if guid:
        guid = guid.strip()
        if entry.get("guidislink", True) or guid.startswith("http"):
            return guid
    return hashlib.sha256(f"{canonical_url}|{published_day}".encode()).hexdigest()


def _fetch_bytes(url: str) -> tuple[bytes, int]:
    """HTTP GET with explicit UA + redirect following.

    Returns ``(body, status_code)``. Status 304 yields an empty body — caller
    treats not-modified as success with zero new items.
    """
    accept_header = (
        "application/atom+xml,application/rss+xml,application/xml,*/*"
    )
    try:
        with httpx.Client(
            headers={"User-Agent": USER_AGENT, "Accept": accept_header},
            timeout=HTTP_TIMEOUT_SECONDS,
            follow_redirects=True,
        ) as client:
            response = client.get(url)
            if response.status_code == 304:
                return b"", 304
            response.raise_for_status()
            return response.content, response.status_code
    except httpx.HTTPError as exc:
        raise FetchError(f"http error fetching {url}: {exc}") from exc


class RssAdapter(IngestAdapter):
    """Fetch + normalize an RSS or Atom feed into ``NormalizedItem``s."""

    def fetch(self, source: SourceConfig) -> list[NormalizedItem]:
        log = logger.bind(source_id=source.id, url=source.url)
        log.info("rss.fetch.start")

        body, status_code = _fetch_bytes(source.url)
        if status_code == 304:
            log.info("rss.fetch.not_modified", status=304)
            return []

        feed = feedparser.parse(body)

        if feed.bozo and not feed.entries:
            raise FetchError(
                f"feedparser failed to parse {source.url}: {feed.get('bozo_exception')!r}"
            )

        feed_title = source.display_name
        if hasattr(feed, "feed"):
            feed_title = feed.feed.get("title", source.display_name)

        items: list[NormalizedItem] = []
        skipped_no_date = 0
        for entry in feed.entries:
            published_at = _extract_published(entry)
            if published_at is None:
                skipped_no_date += 1
                log.warning("rss.entry.skipped_no_date", title=entry.get("title", "<no title>"))
                continue

            canonical_url = entry.get("link") or ""
            if not canonical_url:
                log.warning("rss.entry.skipped_no_link", title=entry.get("title", "<no title>"))
                continue

            title = entry.get("title") or "(untitled)"
            published_day = published_at.strftime("%Y-%m-%d")
            external_id = _derive_external_id(entry, canonical_url, published_day)
            body_html = _extract_body(entry)

            try:
                item = NormalizedItem.build(
                    source_id=source.id,
                    external_id=external_id,
                    canonical_url=canonical_url,
                    title=title,
                    publisher=feed_title or source.display_name,
                    published_at=published_at,
                    raw_content_html=body_html,
                )
            except Exception as exc:
                log.warning("rss.entry.invalid", error=str(exc), title=title)
                continue

            items.append(item)

        log.info(
            "rss.fetch.complete",
            entries_total=len(feed.entries),
            entries_kept=len(items),
            entries_skipped_no_date=skipped_no_date,
            bozo=bool(feed.bozo),
            status=feed.get("status"),
        )
        return items


def _quiet_feedparser_logging() -> None:
    """feedparser is chatty on bozo; bump it to WARNING for the CLI."""
    logging.getLogger("feedparser").setLevel(logging.WARNING)


_quiet_feedparser_logging()


__all__ = ["RssAdapter"]
