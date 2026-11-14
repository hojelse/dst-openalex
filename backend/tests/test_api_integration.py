"""End-to-end API tests against real Postgres + Elasticsearch with the harvested data.

Run with the stack up (e.g. `docker compose up -d`) and `pytest -m integration`.
They are skipped automatically when the services are not reachable.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        if c.get("/api/health").status_code != 200:
            pytest.skip("Postgres/Elasticsearch not available")
        yield c


def test_health(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["documents"] >= 1000


def test_search_everything(client):
    body = client.get("/api/search").json()
    assert body["total"] >= 1000
    assert len(body["results"]) == 20
    # every harvested work is linked to a Danish institution
    assert body["facets"]["country"][0] == {"value": "DK", "count": body["total"]}


def test_search_by_author_highlights_author(client):
    body = client.get("/api/search", params={"q": "Svenning", "field": "author"}).json()
    assert body["total"] > 0
    assert all(any(a["matched"] for a in r["authors"]) for r in body["results"])


def test_search_by_country_name(client):
    body = client.get("/api/search", params={"q": "Kenya", "field": "country"}).json()
    assert body["total"] > 0
    assert all("KE" in r["countries"] for r in body["results"])


def test_filters_are_anded_across_facets_and_ored_within(client):
    se = client.get("/api/search", params={"country": "SE"}).json()["total"]
    no = client.get("/api/search", params={"country": "NO"}).json()["total"]
    both = client.get("/api/search", params=[("country", "SE"), ("country", "NO")]).json()
    assert max(se, no) <= both["total"] <= se + no
    narrowed = client.get("/api/search", params={"country": "SE", "type": "article"}).json()
    assert narrowed["total"] <= se


def test_sort_most_cited(client):
    results = client.get("/api/search", params={"sort": "most_cited"}).json()["results"]
    counts = [r["cited_by_count"] for r in results]
    assert counts == sorted(counts, reverse=True)


def test_detail_round_trip(client):
    first = client.get("/api/search", params={"q": "greenland"}).json()["results"][0]
    detail = client.get(f"/api/works/{first['id']}").json()
    assert detail["title"] == first["title"]
    assert detail["authors"] and detail["authors"][0]["position"] == 1
    assert any(link["label"] == "OpenAlex record" for link in detail["links"])
    for aff in detail["affiliations"]:
        assert "country_name" in aff


def test_detail_not_found(client):
    assert client.get("/api/works/W1").status_code == 404
    assert client.get("/api/works/not-an-id").status_code == 404


def test_validation_errors(client):
    assert client.get("/api/search", params={"sort": "nope"}).status_code == 422
    assert client.get("/api/search", params={"size": 1000}).status_code == 422
    assert client.get("/api/facets/nope").status_code == 422


def test_insights(client):
    body = client.get("/api/insights").json()
    assert body["summary"]["works"] >= 1000
    assert len(body["top_danish_authors"]) == 20
    assert body["author_countries"][0]["code"] == "DK"
    assert sum(b["works"] for b in body["citations"]["histogram"]) == body["summary"]["works"]
