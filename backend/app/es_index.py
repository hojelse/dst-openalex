"""Elasticsearch index definition and (re)indexing from Postgres."""

from __future__ import annotations

import logging
from collections.abc import Iterable, Iterator
from datetime import UTC, datetime
from typing import Any

from elasticsearch import Elasticsearch, helpers

from .transform import to_search_doc

log = logging.getLogger(__name__)

_KEYWORD = {"type": "keyword", "ignore_above": 512}


def _text_with_keyword(analyzer: str = "folded") -> dict[str, Any]:
    """Full-text field plus a `.keyword` sub-field used for facets and exact filters."""
    return {"type": "text", "analyzer": analyzer, "fields": {"keyword": _KEYWORD}}


INDEX_SETTINGS: dict[str, Any] = {
    "number_of_shards": 1,
    "number_of_replicas": 0,
    "analysis": {
        "filter": {
            "english_stemmer": {"type": "stemmer", "language": "english"},
            "english_possessive": {"type": "stemmer", "language": "possessive_english"},
        },
        "analyzer": {
            # Names, places, institutions: no stemming, but accent-insensitive so that
            # "Soren Norgaard" finds "Søren Nørgaard" and "Kobenhavn" finds "København".
            "folded": {
                "type": "custom",
                "tokenizer": "standard",
                "filter": ["lowercase", "asciifolding"],
            },
            # Prose (titles, abstracts): accent folding + English stemming.
            "english_folded": {
                "type": "custom",
                "tokenizer": "standard",
                "filter": ["english_possessive", "lowercase", "asciifolding", "english_stemmer"],
            },
        },
    },
}

INDEX_MAPPINGS: dict[str, Any] = {
    # Only mapped fields are indexed; anything else stays in _source for display.
    "dynamic": False,
    "properties": {
        "id": {"type": "keyword"},
        "doi": {"type": "keyword"},
        "title": {
            "type": "text",
            "analyzer": "english_folded",
            "fields": {"exact": {"type": "text", "analyzer": "folded"}},
        },
        "abstract": {"type": "text", "analyzer": "english_folded"},
        "publication_date": {"type": "date"},
        "publication_year": {"type": "integer"},
        "type": {"type": "keyword"},
        "language": {"type": "keyword"},
        "cited_by_count": {"type": "integer"},
        "fwci": {"type": "float"},
        "is_oa": {"type": "boolean"},
        "oa_status": {"type": "keyword"},
        "source": _text_with_keyword(),
        "harvest_rank": {"type": "integer"},
        "author_count": {"type": "integer"},
        # Plain object arrays (not nested): we filter/facet on single values, never on
        # combinations like "author X *at* institution Y", so nested isn't needed.
        "authors": {
            "properties": {
                "id": {"type": "keyword"},
                "name": _text_with_keyword(),
                "institutions": {"type": "text", "analyzer": "folded"},
                "countries": {"type": "keyword"},
            }
        },
        "institutions": {
            "properties": {
                "id": {"type": "keyword"},
                "name": _text_with_keyword(),
                "country_code": {"type": "keyword"},
                "type": {"type": "keyword"},
            }
        },
        # ISO codes; the .text sub-field lets "dk" / "de" match in the search box.
        "countries": {
            "type": "keyword",
            "fields": {"text": {"type": "text", "analyzer": "folded"}},
        },
        "country_names": _text_with_keyword(),
        "concepts": {
            "properties": {
                "id": {"type": "keyword"},
                "name": _text_with_keyword(),
                "level": {"type": "integer"},
                "score": {"type": "float"},
            }
        },
        "topics": {
            "properties": {
                "id": {"type": "keyword"},
                "name": _text_with_keyword(),
                "field": {"type": "keyword"},
                "domain": {"type": "keyword"},
            }
        },
        "keywords": {"type": "text", "analyzer": "english_folded"},
    },
}


def create_index(es: Elasticsearch, alias: str) -> str:
    name = f"{alias}_{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"
    es.indices.create(index=name, settings=INDEX_SETTINGS, mappings=INDEX_MAPPINGS)
    return name


def _actions(index: str, works: Iterable[tuple[dict[str, Any], int | None]]) -> Iterator[dict]:
    for raw, rank in works:
        doc = to_search_doc(raw, rank=rank)
        yield {"_op_type": "index", "_index": index, "_id": doc["id"], "_source": doc}


def swap_alias(es: Elasticsearch, alias: str, new_index: str, *, keep: int = 1) -> None:
    """Point `alias` at `new_index` atomically and delete older versions beyond `keep`."""
    existing = []
    if es.indices.exists_alias(name=alias):
        existing = list(es.indices.get_alias(name=alias).keys())
    actions: list[dict[str, Any]] = [{"remove": {"index": i, "alias": alias}} for i in existing]
    actions.append({"add": {"index": new_index, "alias": alias}})
    es.indices.update_aliases(actions=actions)

    versions = sorted(
        (i for i in es.indices.get(index=f"{alias}_*") if i != new_index), reverse=True
    )
    for old in versions[keep:]:
        log.info("Deleting old index %s", old)
        es.indices.delete(index=old)


def reindex(
    es: Elasticsearch, alias: str, works: Iterable[tuple[dict[str, Any], int | None]]
) -> tuple[str, int]:
    """Build a fresh index from `works`, then swap the alias to it (zero-downtime reindex)."""
    index = create_index(es, alias)
    ok, errors = helpers.bulk(es, _actions(index, works), chunk_size=200, raise_on_error=False)
    if errors:
        es.indices.delete(index=index)
        raise RuntimeError(f"{len(errors)} documents failed to index, first: {errors[0]}")
    es.indices.refresh(index=index)
    swap_alias(es, alias, index)
    log.info("Indexed %d documents into %s (alias %s)", ok, index, alias)
    return index, ok


def alias_exists(es: Elasticsearch, alias: str) -> bool:
    return bool(es.indices.exists_alias(name=alias))
