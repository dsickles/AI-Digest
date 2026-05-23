"""YouTube channel-uploads adapter (INGEST-03).

D-27: New uploads are discovered through the public channel RSS endpoint
``https://www.youtube.com/feeds/videos.xml?channel_id={id}`` parsed by
``feedparser`` (same dependency as the RSS adapter). For each entry we run
a transcript fetch via ``youtube-transcript-api`` and record the outcome
on ``items.transcript_status`` per the D-23 lifecycle:

- ``ok``            — captions fetched; transcript becomes ``raw_content``.
- ``pending_local`` — cloud IP / request blocked, or transcripts disabled
                      on a cloud weekly run (catch-up may flip to ok later).
- ``missing``       — only set by the local catch-up path (plan 02-04) once
                      ``TranscriptsDisabled`` has been confirmed from a
                      residential IP. The standard weekly path never sets this.

Per-video transcript failures must not raise ``FetchError`` or abort the
channel ingest — channel RSS is the discovery layer; transcripts are a
per-item enrichment.
"""
from __future__ import annotations

import hashlib
import re
from typing import TYPE_CHECKING

import feedparser
import structlog

from pipeline.adapters.base import FetchError, IngestAdapter, is_youtube_short
from pipeline.adapters.rss import _extract_published, _fetch_bytes
from pipeline.models import NormalizedItem

if TYPE_CHECKING:
    from pipeline.config import YoutubeSource

logger = structlog.get_logger(__name__)

# D-38: feed-parse sanity cap to prevent OOM on a runaway feed. Channel RSS
# returns ~15 most recent uploads at v1 cadence so this is purely defensive.
MAX_FEED_ENTRIES = 1000

_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def _extract_video_id(entry: feedparser.FeedParserDict) -> str | None:
    """Resolve the 11-char video id from a channel-RSS entry.

    YouTube's channel feed exposes ``yt:videoId`` (preferred) and an Atom
    ``id`` of the form ``yt:video:{video_id}``. Fall back to parsing the
    canonical watch link's ``v=`` query param if both are missing.
    """
    video_id = entry.get("yt_videoid") or entry.get("yt_video_id")
    if video_id and _VIDEO_ID_RE.match(video_id):
        return video_id

    raw_id = entry.get("id") or ""
    if raw_id.startswith("yt:video:"):
        candidate = raw_id.split(":", 2)[-1]
        if _VIDEO_ID_RE.match(candidate):
            return candidate

    link = entry.get("link") or ""
    if "v=" in link:
        candidate = link.split("v=", 1)[1].split("&", 1)[0]
        if _VIDEO_ID_RE.match(candidate):
            return candidate

    return None


def _description(entry: feedparser.FeedParserDict) -> str:
    """Pull a best-effort description (media:group/media:description or summary)."""
    media_group = entry.get("media_group") or {}
    if isinstance(media_group, dict):
        desc = media_group.get("media_description")
        if isinstance(desc, str) and desc.strip():
            return desc
    media_desc = entry.get("media_description")
    if isinstance(media_desc, str) and media_desc.strip():
        return media_desc
    return entry.get("summary", "") or ""


def _transcript_text(
    video_id: str,
    *,
    languages: tuple[str, ...] = ("en",),
    fetch_kwargs: dict | None = None,
) -> str:
    """Fetch the English transcript via ``youtube-transcript-api`` and join snippets."""
    from youtube_transcript_api import YouTubeTranscriptApi

    api = YouTubeTranscriptApi()
    fetched = api.fetch(video_id, languages=list(languages), **(fetch_kwargs or {}))
    snippets = getattr(fetched, "snippets", None) or list(fetched)
    parts: list[str] = []
    for snippet in snippets:
        text = getattr(snippet, "text", None)
        if text is None and isinstance(snippet, dict):
            text = snippet.get("text")
        if text:
            parts.append(str(text).strip())
    return " ".join(p for p in parts if p)


_TRANSCRIPT_DISABLED_NAMES = frozenset(
    {"TranscriptsDisabled", "NoTranscriptFound", "TranscriptsNotFound"}
)


def _classify_transcript_error(exc: BaseException, *, catch_up: bool = False) -> str:
    """Map youtube-transcript-api exceptions to D-23 transcript_status values.

    Standard cloud-ingest path (``catch_up=False``): every recognised failure
    maps to ``pending_local`` so the residential catch-up flow can retry.

    Catch-up path (``catch_up=True``, plan 02-04): ``TranscriptsDisabled`` and
    related "no captions exist" signals confirmed from a residential IP
    advance to ``missing`` — those videos will never produce a transcript and
    should not be retried. Network/proxy errors stay ``pending_local`` so the
    next catch-up attempt sees them again.
    """
    name = type(exc).__name__
    if catch_up and name in _TRANSCRIPT_DISABLED_NAMES:
        return "missing"
    return "pending_local"


class YoutubeAdapter(IngestAdapter):
    """Fetch a channel's recent uploads + per-video transcripts (D-23, D-27)."""

    last_http_status: int | None = None

    def __init__(
        self,
        *,
        transcript_fetcher=None,
        max_entries: int = MAX_FEED_ENTRIES,
    ) -> None:
        # Injectable transcript fetcher so tests can monkeypatch without touching
        # youtube_transcript_api's classes. Defaults to the module-level
        # ``_transcript_text`` resolved at call time (so monkeypatching
        # ``pipeline.adapters.youtube._transcript_text`` works for callers that
        # instantiate the adapter without an explicit fetcher).
        if transcript_fetcher is None:
            import pipeline.adapters.youtube as _self_mod

            transcript_fetcher = _self_mod._transcript_text
        self._transcript_fetcher = transcript_fetcher
        self._max_entries = max_entries

    def fetch_transcript(
        self, video_id: str, *, catch_up: bool = False
    ) -> tuple[str | None, str]:
        """Catch-up entry point: returns ``(text_or_None, transcript_status)``.

        ``text`` is the joined transcript (non-empty string) when status is
        ``ok``; ``None`` otherwise. ``catch_up=True`` enables the D-23
        residential-IP retry semantics where ``TranscriptsDisabled`` advances
        to ``missing`` instead of being treated as a recoverable failure.
        """
        try:
            text = self._transcript_fetcher(video_id)
        except Exception as exc:
            return None, _classify_transcript_error(exc, catch_up=catch_up)
        if text and text.strip():
            return text, "ok"
        return None, "pending_local"

    def fetch(self, source: YoutubeSource) -> list[NormalizedItem]:
        log = logger.bind(source_id=source.id, channel_id=source.channel_id)
        log.info("youtube.fetch.start", url=source.feed_url)

        body, status_code = _fetch_bytes(source.feed_url)
        self.last_http_status = status_code
        if status_code == 304:
            log.info("youtube.fetch.not_modified", status=304)
            return []

        feed = feedparser.parse(body)
        if feed.bozo and not feed.entries:
            raise FetchError(
                f"feedparser failed to parse {source.feed_url}: "
                f"{feed.get('bozo_exception')!r}",
                category="parse_error",
                http_status=status_code,
            )

        entries = list(feed.entries)[: self._max_entries]
        items: list[NormalizedItem] = []
        skipped_no_video_id = 0
        skipped_no_date = 0
        skipped_youtube_short = 0
        transcript_outcomes: dict[str, int] = {"ok": 0, "pending_local": 0}

        for entry in entries:
            video_id = _extract_video_id(entry)
            if not video_id:
                skipped_no_video_id += 1
                log.warning(
                    "youtube.entry.skipped_no_video_id",
                    title=entry.get("title", "<no title>"),
                )
                continue

            published_at = _extract_published(entry)
            if published_at is None:
                skipped_no_date += 1
                log.warning(
                    "youtube.entry.skipped_no_date",
                    video_id=video_id,
                    title=entry.get("title", "<no title>"),
                )
                continue

            external_id = f"yt:video:{video_id}"
            canonical_url = entry.get("link") or f"https://www.youtube.com/watch?v={video_id}"
            title = entry.get("title") or "(untitled)"
            description = _description(entry)

            if is_youtube_short(canonical_url):
                skipped_youtube_short += 1
                log.info(
                    "youtube.entry.skipped_youtube_short",
                    video_id=video_id,
                    url=canonical_url,
                    title=title,
                )
                continue

            transcript_status: str
            raw_content_html: str
            try:
                transcript = self._transcript_fetcher(video_id)
            except Exception as exc:
                transcript_status = _classify_transcript_error(exc)
                raw_content_html = description
                log.info(
                    "youtube.transcript.unavailable",
                    video_id=video_id,
                    error=type(exc).__name__,
                    transcript_status=transcript_status,
                )
            else:
                if transcript and transcript.strip():
                    transcript_status = "ok"
                    raw_content_html = transcript
                    log.info(
                        "youtube.transcript.ok",
                        video_id=video_id,
                        char_len=len(transcript),
                    )
                else:
                    transcript_status = "pending_local"
                    raw_content_html = description
                    log.info(
                        "youtube.transcript.empty",
                        video_id=video_id,
                        transcript_status=transcript_status,
                    )

            transcript_outcomes[transcript_status] = (
                transcript_outcomes.get(transcript_status, 0) + 1
            )

            try:
                item = NormalizedItem.build(
                    source_id=source.id,
                    external_id=external_id,
                    canonical_url=canonical_url,
                    title=title,
                    publisher=source.display_name,
                    published_at=published_at,
                    raw_content_html=raw_content_html,
                    transcript_status=transcript_status,
                )
            except Exception as exc:
                log.warning(
                    "youtube.entry.invalid",
                    video_id=video_id,
                    error=str(exc),
                )
                continue

            items.append(item)

        log.info(
            "youtube.fetch.complete",
            entries_total=len(feed.entries),
            entries_kept=len(items),
            entries_skipped_no_video_id=skipped_no_video_id,
            entries_skipped_no_date=skipped_no_date,
            entries_skipped_youtube_short=skipped_youtube_short,
            transcript_ok=transcript_outcomes.get("ok", 0),
            transcript_pending_local=transcript_outcomes.get("pending_local", 0),
        )
        return items


def _video_id_hash_fallback(video_id: str) -> str:
    """Stable sha256 for `yt:video:{video_id}` external_id derivation (test helper)."""
    return hashlib.sha256(f"yt:video:{video_id}".encode()).hexdigest()


__all__ = ["MAX_FEED_ENTRIES", "YoutubeAdapter"]
