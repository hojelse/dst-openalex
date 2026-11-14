from app.search import (
    FACET_FIELDS,
    HL_POST,
    HL_PRE,
    SearchParams,
    build_facet_body,
    build_search_body,
    contains_regex,
    shape_hit,
    shape_search_response,
    text_query,
    valid_work_id,
)


def test_empty_query_matches_all():
    assert text_query("  ", "all") == {"match_all": {}}


def test_text_query_uses_field_group():
    q = text_query("svenning", "author")["simple_query_string"]
    assert q["fields"] == ["authors.name"]
    assert q["default_operator"] == "and"


def test_disjunctive_facets():
    params = SearchParams(filters={"country": ["SE", "NO"], "type": ["article"]})
    body = build_search_body(params)

    # Hits are filtered by every facet...
    post = body["post_filter"]["bool"]["filter"]
    assert {"terms": {"countries": ["SE", "NO"]}} in post
    assert {"terms": {"type": ["article"]}} in post

    # ...but each facet's counts ignore its own selection.
    country_filter = body["aggs"]["country"]["filter"]["bool"]["filter"]
    assert country_filter == [{"terms": {"type": ["article"]}}]
    type_filter = body["aggs"]["type"]["filter"]["bool"]["filter"]
    assert type_filter == [{"terms": {"countries": ["SE", "NO"]}}]
    author_filter = body["aggs"]["author"]["filter"]["bool"]["filter"]
    assert len(author_filter) == 2
    assert set(body["aggs"]) == set(FACET_FIELDS)


def test_no_post_filter_without_filters():
    body = build_search_body(SearchParams())
    assert "post_filter" not in body
    assert body["aggs"]["country"]["filter"] == {"match_all": {}}


def test_unknown_filter_names_are_ignored():
    body = build_search_body(SearchParams(filters={"bogus": ["x"], "country": []}))
    assert "post_filter" not in body


def test_pagination_sort_and_dates():
    from datetime import date

    params = SearchParams(
        page=3, size=25, sort="most_cited", date_from=date(2025, 6, 1), date_to=date(2025, 6, 30)
    )
    body = build_search_body(params)
    assert body["from"] == 50 and body["size"] == 25
    assert body["sort"][0] == {"cited_by_count": "desc"}
    assert body["query"]["bool"]["filter"] == [
        {"range": {"publication_date": {"gte": "2025-06-01", "lte": "2025-06-30"}}}
    ]


def test_contains_regex_is_case_insensitive_and_escaped():
    assert contains_regex("Jens") == ".*[jJ][eE][nN][sS].*"
    assert contains_regex("a.b(") == ".*[aA]\\.[bB]\\(.*"
    assert contains_regex("kø") == ".*[kK][øØ].*"


def test_facet_body_applies_include():
    body = build_facet_body(SearchParams(filters={"author": ["X"]}), "author", "jen", 20)
    agg = body["aggs"]["author"]
    assert body["size"] == 0
    assert agg["aggs"]["values"]["terms"]["include"] == ".*[jJ][eE][nN].*"
    assert agg["aggs"]["values"]["terms"]["size"] == 20
    assert agg["filter"] == {"match_all": {}}  # own selection is not applied


def _hit(n_authors=12, matched="Author 11"):
    return {
        "_score": 1.0,
        "_source": {
            "id": "W1",
            "title": "T",
            "authors": [{"id": f"A{i}", "name": f"Author {i}"} for i in range(n_authors)],
            "institutions": [
                {"name": "Oxford", "country_code": "GB"},
                {"name": "DTU", "country_code": "DK"},
            ],
            "concepts": [{"name": f"C{i}"} for i in range(9)],
            "countries": ["DK", "GB"],
        },
        "highlight": {"authors.name": [f"{HL_PRE}{matched}{HL_POST}"]},
    }


def test_shape_hit_keeps_matched_author_and_order():
    hit = shape_hit(_hit())
    names = [a["name"] for a in hit["authors"]]
    assert len(names) == 8
    assert names[-1] == "Author 11"  # the matched author is included even though it's #12
    assert names[:7] == [f"Author {i}" for i in range(7)]
    assert hit["authors"][-1]["matched"] is True
    assert hit["authors"][-1]["position"] == 12
    assert hit["author_count"] == 12


def test_shape_hit_danish_institutions_first_and_concepts_capped():
    hit = shape_hit(_hit())
    assert hit["institutions"][0]["name"] == "DTU"
    assert len(hit["concepts"]) == 5


def test_shape_search_response_pages():
    resp = {"took": 3, "hits": {"total": {"value": 41}, "hits": [_hit()]}, "aggregations": {}}
    out = shape_search_response(resp, SearchParams(size=20))
    assert out["pages"] == 3
    assert out["facets"]["country"] == []


def test_valid_work_id():
    assert valid_work_id("W4413844203")
    assert not valid_work_id("A123")
    assert not valid_work_id("W1; DROP TABLE works")
