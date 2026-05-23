"""YouTube Shorts ingest filter (UAT-FOLLOWUP-01).

Shorts URLs (`youtube.com/shorts/<id>` and variants) must be dropped at the
adapter boundary so they never reach summarize/categorize/rank/rollup or the
"Also seen this week" footer.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from pipeline.adapters.base import is_youtube_short
from pipeline.adapters.rss import RssAdapter
from pipeline.adapters.youtube import YoutubeAdapter
from pipeline.config import RssSource, YoutubeSource

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "feeds"


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/shorts/qevGU6MR1rk",
        "https://youtube.com/shorts/abc123",
        "https://m.youtube.com/shorts/xyz789",
        "https://youtu.be/shorts/short_id",
        "http://www.youtube.com/shorts/HTTPID",
        "https://www.youtube.com/shorts/qevGU6MR1rk?si=tracking",
        "  https://www.youtube.com/shorts/qevGU6MR1rk  ",
    ],
)
def test_is_youtube_short_positive(url: str) -> None:
    assert is_youtube_short(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtu.be/dQw4w9WgXcQ",
        "https://www.youtube.com/channel/UCsomething/shorts",  # path doesn't start with /shorts
        "https://example.com/youtube.com/shorts/spoof",
        "https://www.example.com/shorts/whatever",
        "https://simonwillison.net/2026/May/18/test/",
        "",
        None,
        "not-a-url",
    ],
)
def test_is_youtube_short_negative(url) -> None:
    assert not is_youtube_short(url)


# --- RSS adapter wiring ---


def _rss_source() -> RssSource:
    return RssSource(
        id="fixture-rss",
        type="rss",
        url="https://example.com/feed",
        display_name="Fixture RSS",
        tag="technical",
        enabled=True,
    )


_RSS_FEED_WITH_SHORT = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
<title>Mixed Feed</title>
<item>
  <title>Regular Article</title>
  <link>https://simonwillison.net/2026/May/22/post/</link>
  <guid isPermaLink="false">tag:test,2026:post-1</guid>
  <pubDate>Fri, 22 May 2026 12:00:00 GMT</pubDate>
  <description>Body.</description>
</item>
<item>
  <title>YouTube Short Embed</title>
  <link>https://www.youtube.com/shorts/qevGU6MR1rk</link>
  <guid isPermaLink="false">tag:test,2026:short-1</guid>
  <pubDate>Fri, 22 May 2026 12:30:00 GMT</pubDate>
  <description>A short video summary.</description>
</item>
<item>
  <title>Regular YouTube Watch</title>
  <link>https://www.youtube.com/watch?v=dQw4w9WgXcQ</link>
  <guid isPermaLink="false">tag:test,2026:watch-1</guid>
  <pubDate>Fri, 22 May 2026 13:00:00 GMT</pubDate>
  <description>Long-form.</description>
</item>
</channel></rss>
"""


def test_rss_adapter_drops_youtube_shorts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "pipeline.adapters.rss._fetch_bytes",
        lambda _url: (_RSS_FEED_WITH_SHORT, 200),
    )
    items = RssAdapter().fetch(_rss_source())

    urls = [item.canonical_url for item in items]
    assert "https://simonwillison.net/2026/May/22/post/" in urls
    assert "https://www.youtube.com/watch?v=dQw4w9WgXcQ" in urls
    assert not any("/shorts/" in url for url in urls)
    assert len(items) == 2


# --- YouTube channel adapter wiring ---


def _youtube_source() -> YoutubeSource:
    return YoutubeSource(
        id="fixture-channel",
        type="youtube",
        channel_id="UCFIXTURE00000000000000Z",
        display_name="Fixture Channel",
        tag="technical",
        enabled=True,
    )


_YT_CHANNEL_WITH_SHORT = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015"
      xmlns:media="http://search.yahoo.com/mrss/"
      xmlns="http://www.w3.org/2005/Atom">
  <title>Fixture Channel</title>
  <entry>
    <id>yt:video:dQw4w9WgXcQ</id>
    <yt:videoId>dQw4w9WgXcQ</yt:videoId>
    <title>Long-form upload</title>
    <link rel="alternate" href="https://www.youtube.com/watch?v=dQw4w9WgXcQ"/>
    <published>2026-05-22T12:00:00+00:00</published>
  </entry>
  <entry>
    <id>yt:video:qevGU6MR1rk</id>
    <yt:videoId>qevGU6MR1rk</yt:videoId>
    <title>Short upload</title>
    <link rel="alternate" href="https://www.youtube.com/shorts/qevGU6MR1rk"/>
    <published>2026-05-22T13:00:00+00:00</published>
  </entry>
</feed>
"""


def test_youtube_adapter_drops_shorts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "pipeline.adapters.youtube._fetch_bytes",
        lambda _url: (_YT_CHANNEL_WITH_SHORT, 200),
    )
    adapter = YoutubeAdapter(transcript_fetcher=lambda _vid: "transcript text here")
    items = adapter.fetch(_youtube_source())

    assert len(items) == 1
    assert items[0].canonical_url == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert all("/shorts/" not in item.canonical_url for item in items)
