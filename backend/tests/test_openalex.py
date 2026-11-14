import httpx
import pytest

from app import openalex
from app.openalex import OpenAlexClient, OpenAlexError


def _page(ids, next_cursor, n_authors=1):
    return {
        "meta": {"count": 5048, "next_cursor": next_cursor},
        "results": [
            {"id": f"https://openalex.org/{i}", "authorships": [{}] * n_authors} for i in ids
        ],
    }


def make_client(handler, **kw):
    return OpenAlexClient(
        "https://api.test", api_key="k", transport=httpx.MockTransport(handler), **kw
    )


def test_cursor_pagination_and_limit(monkeypatch):
    monkeypatch.setattr(openalex, "MAX_PER_PAGE", 2)
    seen = []

    def handler(req: httpx.Request):
        seen.append(dict(req.url.params))
        assert req.headers["Authorization"] == "Bearer k"
        cursor = req.url.params["cursor"]
        if cursor == "*":
            return httpx.Response(200, json=_page(["W1", "W2"], "c2"))
        if cursor == "c2":
            return httpx.Response(200, json=_page(["W3", "W4"], "c3"))
        raise AssertionError("fetched past the limit")

    with make_client(handler) as client:
        works = [w["id"].rsplit("/", 1)[-1] for w, _ in client.iter_works(3)]

    assert works == ["W1", "W2", "W3"]
    assert [p["cursor"] for p in seen] == ["*", "c2"]
    assert seen[0]["filter"] == openalex.FILTER
    assert seen[0]["search"] == "climate change"


def test_stops_when_results_run_out():
    def handler(req):
        if req.url.params["cursor"] == "*":
            return httpx.Response(200, json=_page(["W1"], None))
        raise AssertionError

    with make_client(handler) as client:
        assert len(list(client.iter_works(1000))) == 1


def test_retries_transient_errors(monkeypatch):
    monkeypatch.setattr(openalex.time, "sleep", lambda s: None)
    calls = {"n": 0}

    def handler(req):
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(503)
        return httpx.Response(200, json=_page(["W1"], None))

    with make_client(handler) as client:
        assert len(list(client.iter_works(1))) == 1
    assert calls["n"] == 3


def test_exhausted_budget_fails_fast(monkeypatch):
    monkeypatch.setattr(openalex.time, "sleep", lambda s: pytest.fail("should not wait hours"))

    def handler(req):
        return httpx.Response(429, json={"error": "Rate limit exceeded", "retryAfter": 43991})

    with make_client(handler) as client, pytest.raises(OpenAlexError, match="OPENALEX_API_KEY"):
        list(client.iter_works(1))


def test_refetches_works_with_truncated_author_lists():
    def handler(req):
        if req.url.path == "/works":
            return httpx.Response(200, json=_page(["W1"], None, n_authors=100))
        assert req.url.path == "/works/W1"
        return httpx.Response(
            200, json={"id": "https://openalex.org/W1", "authorships": [{}] * 250}
        )

    with make_client(handler) as client:
        [(work, _)] = list(client.iter_works(1))
    assert len(work["authorships"]) == 250
