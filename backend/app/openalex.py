"""Minimal OpenAlex API client used by the harvester."""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from typing import Any

import httpx

log = logging.getLogger(__name__)

# The starting query from the assignment: "climate change" works with at least one
# Danish institution, published in 2025.
SEARCH = "climate change"
FILTER = (
    "institutions.country_code:DK,from_publication_date:2025-01-01,to_publication_date:2025-12-31"
)

MAX_PER_PAGE = 200  # OpenAlex maximum
LIST_AUTHORSHIP_CAP = 100  # list responses truncate authorships at this many
RETRYABLE_STATUS = {429, 500, 502, 503, 504}
# If OpenAlex asks us to wait longer than this, the daily budget is gone: fail fast.
MAX_RETRY_AFTER_SECONDS = 120


class OpenAlexError(RuntimeError):
    pass


class OpenAlexClient:
    def __init__(
        self,
        base_url: str = "https://api.openalex.org",
        api_key: str | None = None,
        *,
        max_attempts: int = 5,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        headers = {"User-Agent": "openalex-climate-dk-harvester/1.0", "Accept": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self._client = httpx.Client(
            base_url=base_url, headers=headers, timeout=60.0, transport=transport
        )
        self._max_attempts = max_attempts

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> OpenAlexClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        """GET with exponential backoff on 429/5xx and transport errors."""
        delay = 1.0
        for attempt in range(1, self._max_attempts + 1):
            try:
                resp = self._client.get(path, params=params)
            except httpx.TransportError as exc:
                if attempt == self._max_attempts:
                    raise OpenAlexError(f"Network error talking to OpenAlex: {exc}") from exc
                log.warning("Transport error (%s), retrying in %.0fs", exc, delay)
                time.sleep(delay)
                delay *= 2
                continue

            if resp.status_code == 200:
                return resp.json()

            if resp.status_code in RETRYABLE_STATUS and attempt < self._max_attempts:
                wait = _retry_after(resp) or delay
                if wait > MAX_RETRY_AFTER_SECONDS:
                    raise OpenAlexError(_budget_message(resp))
                log.warning("OpenAlex returned %s, retrying in %.0fs", resp.status_code, wait)
                time.sleep(wait)
                delay *= 2
                continue

            if resp.status_code == 429:
                raise OpenAlexError(_budget_message(resp))
            raise OpenAlexError(f"OpenAlex returned {resp.status_code}: {resp.text[:500]}")
        raise OpenAlexError("Exhausted retries")  # pragma: no cover

    def iter_works(
        self,
        limit: int,
        *,
        search: str = SEARCH,
        filter_: str = FILTER,
    ) -> Iterator[tuple[dict[str, Any], dict[str, Any]]]:
        """Yield ``(work, meta)`` pairs using cursor pagination until ``limit`` works are read.

        Cursor paging (rather than ``page=N``) is what OpenAlex recommends for walking
        result sets and has no 10k-result ceiling, so the same code scales past 1000.
        """
        per_page = min(MAX_PER_PAGE, max(limit, 1))
        cursor: str | None = "*"
        seen = 0
        while cursor and seen < limit:
            data = self.get(
                "/works",
                {"search": search, "filter": filter_, "per-page": per_page, "cursor": cursor},
            )
            results = data.get("results") or []
            meta = data.get("meta") or {}
            if not results:
                break
            for work in results:
                if seen >= limit:
                    break
                seen += 1
                yield self._complete(work), meta
            cursor = meta.get("next_cursor")
            log.info("Fetched %d/%d works (OpenAlex total: %s)", seen, limit, meta.get("count"))

    def get_work(self, work_id: str) -> dict[str, Any]:
        return self.get(f"/works/{work_id.rsplit('/', 1)[-1]}", {})

    def _complete(self, work: dict[str, Any]) -> dict[str, Any]:
        """List endpoints cap `authorships` at 100 entries; the single-work endpoint does not.

        For large-consortium papers, re-fetch the full record so the detail page can show
        the complete author list (only a handful of works per 1000 need this).
        """
        if len(work.get("authorships") or []) >= LIST_AUTHORSHIP_CAP:
            full = self.get_work(work["id"])
            log.info(
                "Re-fetched %s: %d -> %d authorships",
                work["id"],
                len(work["authorships"]),
                len(full.get("authorships") or []),
            )
            # Keep the search relevance score from the list response.
            return {**full, "relevance_score": work.get("relevance_score")}
        return work


def _retry_after(resp: httpx.Response) -> float | None:
    header = resp.headers.get("Retry-After")
    if header:
        try:
            return float(header)
        except ValueError:
            pass
    try:
        body = resp.json()
    except ValueError:
        return None
    value = body.get("retryAfter") if isinstance(body, dict) else None
    return float(value) if isinstance(value, int | float) else None


def _budget_message(resp: httpx.Response) -> str:
    return (
        "OpenAlex rate limit / daily budget exhausted. Set OPENALEX_API_KEY "
        "(free, see https://help.openalex.org/api/authentication/) or load the bundled "
        "snapshot with `python -m app.cli load-snapshot`. Response: " + resp.text[:300]
    )
