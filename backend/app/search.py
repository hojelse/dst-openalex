"""Elasticsearch query construction and response shaping (pure functions, unit tested)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from dataclasses import field as dc_field
from datetime import date
from typing import Any, Literal

SearchField = Literal["all", "title", "author", "country", "institution"]
SortOrder = Literal["relevance", "newest", "oldest", "most_cited"]

# Facet name (used in the API / URL) -> keyword field in the index.
FACET_FIELDS: dict[str, str] = {
    "country": "countries",
    "institution": "institutions.name.keyword",
    "author": "authors.name.keyword",
    "concept": "concepts.name.keyword",
    "type": "type",
    "oa_status": "oa_status",
}

# Which fields the search box searches, per "search in" option.
SEARCH_FIELDS: dict[str, list[str]] = {
    "all": [
        "title^3",
        "title.exact^3",
        "authors.name^2",
        "country_names^2",
        "countries.text^2",
        "institutions.name^1.5",
        "concepts.name^1.5",
        "topics.name",
        "keywords",
        "abstract",
        "source",
    ],
    "title": ["title", "title.exact^2"],
    "author": ["authors.name"],
    "country": ["country_names", "countries.text"],
    "institution": ["institutions.name", "authors.institutions"],
}

SORTS: dict[str, list[Any]] = {
    # harvest_rank = position in OpenAlex's own relevance ranking: a good tie-breaker
    # (and the whole ordering when there is no query text).
    "relevance": ["_score", {"harvest_rank": "asc"}],
    "newest": [{"publication_date": "desc"}, "_score", {"harvest_rank": "asc"}],
    "oldest": [{"publication_date": "asc"}, "_score", {"harvest_rank": "asc"}],
    "most_cited": [{"cited_by_count": "desc"}, "_score", {"harvest_rank": "asc"}],
}

# Private-use code points as highlight markers: the UI splits on them and renders <mark>
# elements, so no HTML from the data is ever injected into the page.
HL_PRE, HL_POST = "", ""

LIST_AUTHORS = 8
LIST_INSTITUTIONS = 4
LIST_CONCEPTS = 5


@dataclass
class SearchParams:
    q: str = ""
    field: SearchField = "all"
    filters: dict[str, list[str]] = dc_field(default_factory=dict)
    date_from: date | None = None
    date_to: date | None = None
    sort: SortOrder = "relevance"
    page: int = 1
    size: int = 20
    facet_size: int = 10


def text_query(q: str, search_field: str) -> dict[str, Any]:
    q = q.strip()
    if not q:
        return {"match_all": {}}
    return {
        # simple_query_string never throws on bad syntax and still supports
        # "exact phrases", -exclusions, OR (|) and prefix* for power users.
        "simple_query_string": {
            "query": q,
            "fields": SEARCH_FIELDS[search_field],
            "default_operator": "and",
        }
    }


def filter_clauses(params: SearchParams) -> dict[str, dict[str, Any]]:
    """One terms clause per active facet (values within a facet are OR-ed)."""
    return {
        name: {"terms": {FACET_FIELDS[name]: values}}
        for name, values in params.filters.items()
        if name in FACET_FIELDS and values
    }


def base_query(params: SearchParams) -> dict[str, Any]:
    """Text query + non-facet filters (date range). Facet filters go in post_filter."""
    filters: list[dict[str, Any]] = []
    if params.date_from or params.date_to:
        rng: dict[str, str] = {}
        if params.date_from:
            rng["gte"] = params.date_from.isoformat()
        if params.date_to:
            rng["lte"] = params.date_to.isoformat()
        filters.append({"range": {"publication_date": rng}})
    return {"bool": {"must": [text_query(params.q, params.field)], "filter": filters}}


def _facet_agg(
    name: str, clauses: dict[str, dict[str, Any]], size: int, include: str | None = None
) -> dict[str, Any]:
    # Disjunctive faceting: a facet's counts honour every *other* active filter but not
    # its own, so users can still see (and add) alternative values in the same facet.
    others = [c for n, c in clauses.items() if n != name]
    terms: dict[str, Any] = {"field": FACET_FIELDS[name], "size": size}
    if include:
        terms["include"] = include
    return {
        "filter": {"bool": {"filter": others}} if others else {"match_all": {}},
        "aggs": {"values": {"terms": terms}},
    }


def build_search_body(params: SearchParams) -> dict[str, Any]:
    clauses = filter_clauses(params)
    body: dict[str, Any] = {
        "query": base_query(params),
        "aggs": {name: _facet_agg(name, clauses, params.facet_size) for name in FACET_FIELDS},
        "sort": SORTS[params.sort],
        "from": (params.page - 1) * params.size,
        "size": params.size,
        "track_total_hits": True,
        "_source": {"excludes": ["abstract", "keywords", "topics"]},
        "highlight": {
            "pre_tags": [HL_PRE],
            "post_tags": [HL_POST],
            "fields": {
                "title": {"number_of_fragments": 0},
                "title.exact": {"number_of_fragments": 0},
                "authors.name": {"number_of_fragments": 0},
                "abstract": {"fragment_size": 240, "number_of_fragments": 1, "no_match_size": 240},
            },
        },
    }
    if clauses:
        body["post_filter"] = {"bool": {"filter": list(clauses.values())}}
    return body


def contains_regex(text: str) -> str:
    """Case-insensitive 'contains' pattern for a terms-aggregation `include` (Lucene regex)."""
    parts = []
    for ch in text.strip():
        if ch.isalpha() and ch.lower() != ch.upper():
            parts.append(f"[{ch.lower()}{ch.upper()}]")
        elif ch.isalnum() or ch == " ":
            parts.append(ch)
        else:
            parts.append("\\" + ch)
    return ".*" + "".join(parts) + ".*"


def build_facet_body(params: SearchParams, facet: str, contains: str, size: int) -> dict[str, Any]:
    """Values of one facet (optionally filtered by substring) under the current search."""
    clauses = filter_clauses(params)
    include = contains_regex(contains) if contains.strip() else None
    return {
        "query": base_query(params),
        "size": 0,
        "aggs": {facet: _facet_agg(facet, clauses, size, include)},
    }


# --------------------------------------------------------------------------- responses


def _strip_markers(text: str) -> str:
    return text.replace(HL_PRE, "").replace(HL_POST, "")


def facet_values(aggs: dict[str, Any], name: str) -> list[dict[str, Any]]:
    buckets = aggs.get(name, {}).get("values", {}).get("buckets", [])
    return [{"value": b["key"], "count": b["doc_count"]} for b in buckets]


def shape_hit(hit: dict[str, Any]) -> dict[str, Any]:
    src = hit["_source"]
    hl = hit.get("highlight", {})

    title_hl = (hl.get("title") or hl.get("title.exact") or [None])[0]
    matched_authors = {_strip_markers(n) for n in hl.get("authors.name", [])}

    # Show the leading authors, but always include the ones the query matched
    # (e.g. author #45 of a consortium paper), keeping the original order.
    authors = src.get("authors") or []
    keep = {i for i, a in enumerate(authors) if a.get("name") in matched_authors}
    keep = set(sorted(keep)[:LIST_AUTHORS])
    for i in range(len(authors)):
        if len(keep) >= LIST_AUTHORS:
            break
        keep.add(i)

    institutions = src.get("institutions") or []
    # Danish institutions first: that is the scope of the collection.
    institutions = sorted(institutions, key=lambda i: i.get("country_code") != "DK")

    return {
        "id": src["id"],
        "title": src.get("title"),
        "title_highlight": title_hl,
        "snippet": (hl.get("abstract") or [None])[0],
        "publication_date": src.get("publication_date"),
        "type": src.get("type"),
        "source": src.get("source"),
        "doi": src.get("doi"),
        "cited_by_count": src.get("cited_by_count", 0),
        "is_oa": src.get("is_oa", False),
        "oa_status": src.get("oa_status"),
        "author_count": src.get("author_count", len(authors)),
        "authors": [
            {
                "id": authors[i].get("id"),
                "name": authors[i].get("name"),
                "position": i + 1,
                "matched": authors[i].get("name") in matched_authors,
            }
            for i in sorted(keep)
        ],
        "institution_count": len(institutions),
        "institutions": [
            {"name": i["name"], "country_code": i.get("country_code")}
            for i in institutions[:LIST_INSTITUTIONS]
        ],
        "countries": src.get("countries") or [],
        "concepts": [c["name"] for c in (src.get("concepts") or [])[:LIST_CONCEPTS]],
        "score": hit.get("_score"),
    }


def shape_search_response(resp: dict[str, Any], params: SearchParams) -> dict[str, Any]:
    total = resp["hits"]["total"]["value"]
    aggs = resp.get("aggregations", {})
    return {
        "total": total,
        "page": params.page,
        "size": params.size,
        "pages": max(1, -(-total // params.size)),
        "took_ms": resp.get("took"),
        "results": [shape_hit(h) for h in resp["hits"]["hits"]],
        "facets": {name: facet_values(aggs, name) for name in FACET_FIELDS},
    }


_ID_RE = re.compile(r"^W\d{1,12}$")


def valid_work_id(work_id: str) -> bool:
    return bool(_ID_RE.match(work_id))
