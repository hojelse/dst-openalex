"""Pure functions that turn raw OpenAlex work JSON into database rows and search documents.

Keeping these free of I/O makes them easy to unit test against recorded API responses.
"""

from __future__ import annotations

import html
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from .countries import country_name

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
# Many publishers' abstracts start with the literal heading "Abstract" (~19% of records).
_ABSTRACT_LABEL_RE = re.compile(r"^abstract\b[\s:.\-–—]*", re.IGNORECASE)


def short_id(url: str | None) -> str | None:
    """'https://openalex.org/W123' -> 'W123' (also works for already-short ids)."""
    if not url:
        return None
    return url.rstrip("/").rsplit("/", 1)[-1]


def bare_doi(doi: str | None) -> str | None:
    """'https://doi.org/10.1/abc' -> '10.1/abc'."""
    if not doi:
        return None
    return re.sub(r"^https?://(dx\.)?doi\.org/", "", doi, flags=re.IGNORECASE)


def clean_text(value: str | None) -> str | None:
    """Strip inline markup (OpenAlex titles contain <i>, <sub>, ...) and normalise whitespace."""
    if value is None:
        return None
    text = html.unescape(_TAG_RE.sub("", value))
    text = _WS_RE.sub(" ", text).strip()
    return text or None


def reconstruct_abstract(inverted_index: dict[str, list[int]] | None) -> str | None:
    """OpenAlex ships abstracts as an inverted index {word: [positions]}; rebuild the text."""
    if not inverted_index:
        return None
    positions: dict[int, str] = {}
    for word, idxs in inverted_index.items():
        for i in idxs:
            positions[i] = word
    if not positions:
        return None
    text = clean_text(" ".join(positions[i] for i in sorted(positions)))
    if text is None:
        return None
    return _ABSTRACT_LABEL_RE.sub("", text) or None


@dataclass
class NormalizedWork:
    """A work split into the rows of the relational schema (see schema.sql)."""

    work: dict[str, Any]
    authors: list[dict[str, Any]] = field(default_factory=list)
    institutions: list[dict[str, Any]] = field(default_factory=list)
    authorships: list[dict[str, Any]] = field(default_factory=list)
    authorship_institutions: list[dict[str, Any]] = field(default_factory=list)
    authorship_countries: list[dict[str, Any]] = field(default_factory=list)
    concepts: list[dict[str, Any]] = field(default_factory=list)
    work_concepts: list[dict[str, Any]] = field(default_factory=list)
    topics: list[dict[str, Any]] = field(default_factory=list)
    work_topics: list[dict[str, Any]] = field(default_factory=list)


def normalize_work(raw: dict[str, Any], *, rank: int | None = None) -> NormalizedWork:
    work_id = short_id(raw["id"])
    oa = raw.get("open_access") or {}
    primary = raw.get("primary_location") or {}
    source = primary.get("source") or {}

    nw = NormalizedWork(
        work={
            "id": work_id,
            "doi": bare_doi(raw.get("doi")),
            "title": clean_text(raw.get("title") or raw.get("display_name")),
            "abstract": reconstruct_abstract(raw.get("abstract_inverted_index")),
            "publication_date": raw.get("publication_date"),
            "publication_year": raw.get("publication_year"),
            "type": raw.get("type"),
            "language": raw.get("language"),
            "cited_by_count": raw.get("cited_by_count") or 0,
            "fwci": raw.get("fwci"),
            "is_oa": oa.get("is_oa"),
            "oa_status": oa.get("oa_status"),
            "oa_url": oa.get("oa_url"),
            "source_name": source.get("display_name"),
            "landing_page_url": primary.get("landing_page_url"),
            "harvest_rank": rank,
        }
    )

    seen_authors: set[str] = set()
    seen_institutions: set[str] = set()
    for pos, authorship in enumerate(raw.get("authorships") or []):
        author = authorship.get("author") or {}
        author_id = short_id(author.get("id"))
        if author_id and author_id not in seen_authors:
            seen_authors.add(author_id)
            nw.authors.append(
                {
                    "id": author_id,
                    "display_name": author.get("display_name")
                    or authorship.get("raw_author_name")
                    or author_id,
                    "orcid": author.get("orcid"),
                }
            )
        nw.authorships.append(
            {
                "work_id": work_id,
                "author_position": pos,
                "author_id": author_id,
                "author_role": authorship.get("author_position"),
                "raw_author_name": authorship.get("raw_author_name"),
                "is_corresponding": bool(authorship.get("is_corresponding")),
                "raw_affiliations": authorship.get("raw_affiliation_strings") or [],
            }
        )
        authorship_insts: set[str] = set()
        for inst in authorship.get("institutions") or []:
            inst_id = short_id(inst.get("id"))
            if not inst_id or inst_id in authorship_insts:
                continue
            authorship_insts.add(inst_id)
            if inst_id not in seen_institutions:
                seen_institutions.add(inst_id)
                nw.institutions.append(
                    {
                        "id": inst_id,
                        "display_name": inst.get("display_name") or inst_id,
                        "ror": inst.get("ror"),
                        "country_code": inst.get("country_code"),
                        "type": inst.get("type"),
                    }
                )
            nw.authorship_institutions.append(
                {"work_id": work_id, "author_position": pos, "institution_id": inst_id}
            )
        for code in sorted(set(authorship.get("countries") or [])):
            nw.authorship_countries.append(
                {"work_id": work_id, "author_position": pos, "country_code": code}
            )

    for concept in raw.get("concepts") or []:
        cid = short_id(concept.get("id"))
        if not cid:
            continue
        nw.concepts.append(
            {
                "id": cid,
                "display_name": concept.get("display_name"),
                "level": concept.get("level"),
                "wikidata": concept.get("wikidata"),
            }
        )
        nw.work_concepts.append(
            {"work_id": work_id, "concept_id": cid, "score": concept.get("score")}
        )

    primary_topic_id = short_id((raw.get("primary_topic") or {}).get("id"))
    for topic in raw.get("topics") or []:
        tid = short_id(topic.get("id"))
        if not tid:
            continue
        nw.topics.append(
            {
                "id": tid,
                "display_name": topic.get("display_name"),
                "subfield": (topic.get("subfield") or {}).get("display_name"),
                "field": (topic.get("field") or {}).get("display_name"),
                "domain": (topic.get("domain") or {}).get("display_name"),
            }
        )
        nw.work_topics.append(
            {
                "work_id": work_id,
                "topic_id": tid,
                "score": topic.get("score"),
                "is_primary": tid == primary_topic_id,
            }
        )
    return nw


def to_search_doc(raw: dict[str, Any], *, rank: int | None = None) -> dict[str, Any]:
    """Build the denormalised Elasticsearch document for one work."""
    nw = normalize_work(raw, rank=rank)
    w = nw.work
    inst_by_id = {i["id"]: i for i in nw.institutions}

    insts_by_pos: dict[int, list[str]] = defaultdict(list)
    for ai in nw.authorship_institutions:
        insts_by_pos[ai["author_position"]].append(ai["institution_id"])
    countries_by_pos: dict[int, list[str]] = defaultdict(list)
    for ac in nw.authorship_countries:
        countries_by_pos[ac["author_position"]].append(ac["country_code"])
    names = {a["id"]: a["display_name"] for a in nw.authors}

    authors = []
    countries: list[str] = []
    for authorship in nw.authorships:
        pos = authorship["author_position"]
        countries.extend(countries_by_pos[pos])
        authors.append(
            {
                "id": authorship["author_id"],
                "name": names.get(authorship["author_id"]) or authorship["raw_author_name"],
                "institutions": [inst_by_id[i]["display_name"] for i in insts_by_pos[pos]],
                "countries": countries_by_pos[pos],
            }
        )
    # Institution countries also count (an authorship's "countries" normally includes them).
    countries.extend(i["country_code"] for i in nw.institutions if i["country_code"])
    country_codes = sorted(set(countries))

    concept_scores = {wc["concept_id"]: wc["score"] for wc in nw.work_concepts}
    concepts = sorted(nw.concepts, key=lambda c: -(concept_scores.get(c["id"]) or 0))

    return {
        "id": w["id"],
        "doi": w["doi"],
        "title": w["title"],
        "abstract": w["abstract"],
        "publication_date": w["publication_date"],
        "publication_year": w["publication_year"],
        "type": w["type"],
        "language": w["language"],
        "cited_by_count": w["cited_by_count"],
        "fwci": w["fwci"],
        "is_oa": bool(w["is_oa"]),
        "oa_status": w["oa_status"] or "unknown",
        "source": w["source_name"],
        "harvest_rank": rank,
        "author_count": len(authors),
        "authors": authors,
        "institutions": [
            {
                "id": i["id"],
                "name": i["display_name"],
                "country_code": i["country_code"],
                "type": i["type"],
            }
            for i in nw.institutions
        ],
        "countries": country_codes,
        "country_names": [country_name(c) for c in country_codes],
        "concepts": [
            {
                "id": c["id"],
                "name": c["display_name"],
                "level": c["level"],
                "score": concept_scores.get(c["id"]),
            }
            for c in concepts
        ],
        "topics": [
            {
                "id": t["id"],
                "name": t["display_name"],
                "subfield": t["subfield"],
                "field": t["field"],
                "domain": t["domain"],
            }
            for t in nw.topics
        ],
        "keywords": [k.get("display_name") for k in raw.get("keywords") or []],
    }
