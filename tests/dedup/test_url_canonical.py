"""Unit tests for Tier 0 URL canonicalization."""
from __future__ import annotations

import httpx
import pytest

from pipeline.dedup.url import canonicalize_url, resolve_final_url


def test_strips_utm_params(url_collision_pair: tuple[str, str]) -> None:
    dirty, clean = url_collision_pair
    assert canonicalize_url(dirty) == canonicalize_url(clean)


def test_strips_gclid() -> None:
    url = "https://example.com/article?gclid=abc123&topic=ai"
    assert canonicalize_url(url) == "https://example.com/article?topic=ai"


def test_trailing_slash_normalized() -> None:
    assert canonicalize_url("https://example.com/post/") == "https://example.com/post"
    assert canonicalize_url("https://example.com/") == "https://example.com/"


def test_strips_www() -> None:
    assert canonicalize_url("https://www.example.com/x") == "https://example.com/x"


def test_resolve_final_url_falls_back_on_http_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class BrokenClient:
        def get(self, url: str, **kwargs: object) -> httpx.Response:
            raise httpx.HTTPError("boom")

    result = resolve_final_url(
        "https://example.com/a?utm_source=x",
        BrokenClient(),  # type: ignore[arg-type]
    )
    assert result == "https://example.com/a"
