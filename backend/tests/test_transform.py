from app.transform import (
    bare_doi,
    clean_text,
    normalize_work,
    reconstruct_abstract,
    short_id,
    to_search_doc,
)


def test_short_id_and_doi():
    assert short_id("https://openalex.org/W4413844203") == "W4413844203"
    assert short_id("W1") == "W1"
    assert short_id(None) is None
    assert bare_doi("https://doi.org/10.1/ABC") == "10.1/ABC"
    assert bare_doi("http://dx.doi.org/10.1/x") == "10.1/x"
    assert bare_doi(None) is None


def test_clean_text_strips_markup_and_entities():
    assert clean_text("CO<sub>2</sub> &amp; <i>Picea</i>  abies ") == "CO2 & Picea abies"
    assert clean_text("   ") is None
    assert clean_text(None) is None


def test_reconstruct_abstract_orders_by_position():
    inv = {"world": [1], "hello": [0, 2], "again": [3]}
    assert reconstruct_abstract(inv) == "hello world hello again"
    assert reconstruct_abstract(None) is None
    assert reconstruct_abstract({}) is None


def test_reconstruct_abstract_drops_heading_label():
    assert (
        reconstruct_abstract({"Abstract": [0], "Forests": [1], "matter.": [2]}) == "Forests matter."
    )
    assert reconstruct_abstract({"Abstract:": [0], "Text": [1]}) == "Text"
    assert reconstruct_abstract({"Abstracts": [0], "rock": [1]}) == "Abstracts rock"


def test_normalize_work_rows(raw_work):
    nw = normalize_work(raw_work, rank=7)

    assert nw.work["id"] == "W4413844203"
    assert nw.work["harvest_rank"] == 7
    assert nw.work["title"].startswith("Datafication of Climate Change")
    assert nw.work["abstract"] and len(nw.work["abstract"]) > 100
    assert nw.work["publication_date"] == raw_work["publication_date"]

    # 8 author slots, but the first author has no OpenAlex id -> only 7 author entities
    assert len(nw.authorships) == 8
    assert nw.authorships[0]["author_id"] is None
    assert nw.authorships[0]["raw_author_name"]
    assert len(nw.authors) == 7
    assert [a["author_position"] for a in nw.authorships] == list(range(8))

    # Institutions are de-duplicated across authors (Georgia Tech appears 3 times)
    names = [i["display_name"] for i in nw.institutions]
    assert len(names) == len(set(names))
    assert "Aarhus University" in names
    assert len(nw.authorship_institutions) == 8

    assert {c["country_code"] for c in nw.authorship_countries} == {"US", "CA", "DK"}

    assert nw.concepts and len(nw.concepts) == len(nw.work_concepts)
    primary = [t for t in nw.work_topics if t["is_primary"]]
    assert len(primary) == 1 and primary[0]["topic_id"] == "T10883"


def test_search_doc(raw_work):
    doc = to_search_doc(raw_work, rank=1)

    assert doc["id"] == "W4413844203"
    assert doc["author_count"] == 8
    assert doc["authors"][0]["name"] == "Anya Martin"  # unresolved author keeps its name
    assert doc["authors"][3]["institutions"] == ["Aarhus University"]
    assert doc["authors"][3]["countries"] == ["DK"]
    assert doc["countries"] == ["CA", "DK", "US"]
    assert doc["country_names"] == ["Canada", "Denmark", "United States"]
    scores = [c["score"] for c in doc["concepts"]]
    assert scores == sorted(scores, reverse=True)
    assert doc["concepts"][0]["name"] == "Climate change"
    assert doc["is_oa"] in (True, False)
    assert doc["oa_status"]
