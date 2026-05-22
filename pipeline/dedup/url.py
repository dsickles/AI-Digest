"""Tier 0 URL canonicalization (D-43, DEDUP-01)."""
from __future__ import annotations

from urllib.parse import parse_qsl, urlparse, urlunparse

import httpx

TRACKING_KEYS = frozenset(
    {
        "gclid",
        "fbclid",
        "ref",
        "mc_cid",
        "mc_eid",
        "msclkid",
        "_ga",
        "_gl",
        "igshid",
        "mkt_tok",
        "vero_id",
        "wickedid",
        "oly_anon_id",
        "oly_enc_id",
        "pk_campaign",
        "pk_kwd",
        "spm",
    }
)


def _is_tracking_key(key: str) -> bool:
    lowered = key.lower()
    return lowered.startswith("utm_") or lowered in TRACKING_KEYS


def _normalize_host(host: str) -> str:
    host = host.lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def _strip_trailing_slash(path: str) -> str:
    if path != "/" and path.endswith("/"):
        return path.rstrip("/")
    return path


def canonicalize_url(url: str, *, client: httpx.Client | None = None) -> str:
    """Normalize URL for Tier 0 exact-match dedup.

    Strips tracking query params, lowercases host, removes ``www.``, drops
    fragments, and normalizes trailing slashes. Optional ``client`` is unused
    here — callers that need redirect resolution use :func:`resolve_final_url`.
    """
    del client  # reserved for API symmetry with resolve_final_url callers
    parsed = urlparse(url.strip())
    if not parsed.scheme:
        parsed = urlparse(f"https://{url.strip()}")

    host = _normalize_host(parsed.hostname or "")
    netloc = host
    if parsed.port:
        netloc = f"{host}:{parsed.port}"

    filtered_pairs = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if not _is_tracking_key(key)
    ]
    query = "&".join(f"{key}={value}" if value else key for key, value in filtered_pairs)

    path = _strip_trailing_slash(parsed.path or "")
    normalized = urlunparse(
        (
            parsed.scheme.lower(),
            netloc,
            path,
            parsed.params,
            query,
            "",  # strip fragment
        )
    )
    return normalized


def resolve_final_url(url: str, client: httpx.Client) -> str:
    """Follow redirects once (5s timeout) then canonicalize."""
    try:
        resp = client.get(url, follow_redirects=True, timeout=5.0)
        return canonicalize_url(str(resp.url))
    except httpx.HTTPError:
        return canonicalize_url(url)
