"""Read model for the publication detail page, served from Postgres (the system of record)."""

from __future__ import annotations

from typing import Any

import psycopg
from psycopg.rows import dict_row

from .countries import country_name

WORK_SQL = """
SELECT id, doi, title, abstract, publication_date, publication_year, type, language,
       cited_by_count, fwci, is_oa, oa_status, oa_url, source_name, landing_page_url,
       harvested_at,
       raw->'primary_location'                  AS primary_location,
       raw->'locations'                         AS locations,
       raw->'keywords'                          AS keywords,
       raw->'sustainable_development_goals'     AS sdgs,
       raw->'counts_by_year'                    AS counts_by_year,
       raw->'citation_normalized_percentile'    AS citation_percentile,
       raw->'biblio'                            AS biblio,
       (raw->>'referenced_works_count')::int    AS referenced_works_count
FROM works WHERE id = %s
"""

AUTHORS_SQL = """
SELECT au.author_position + 1 AS position,
       au.author_id AS id,
       coalesce(a.display_name, au.raw_author_name) AS name,
       a.orcid, au.author_role AS role, au.is_corresponding, au.raw_affiliations,
       coalesce((
           SELECT json_agg(json_build_object(
                      'id', i.id, 'name', i.display_name, 'ror', i.ror,
                      'country_code', i.country_code, 'type', i.type)
                  ORDER BY i.display_name)
           FROM authorship_institutions ai
           JOIN institutions i ON i.id = ai.institution_id
           WHERE ai.work_id = au.work_id AND ai.author_position = au.author_position
       ), '[]'::json) AS institutions,
       coalesce((
           SELECT array_agg(ac.country_code ORDER BY ac.country_code)
           FROM authorship_countries ac
           WHERE ac.work_id = au.work_id AND ac.author_position = au.author_position
       ), '{}') AS countries
FROM authorships au
LEFT JOIN authors a ON a.id = au.author_id
WHERE au.work_id = %s
ORDER BY au.author_position
"""

AFFILIATIONS_SQL = """
SELECT i.id, i.display_name AS name, i.ror, i.country_code, i.type,
       count(*) AS author_count
FROM authorship_institutions ai
JOIN institutions i ON i.id = ai.institution_id
WHERE ai.work_id = %s
GROUP BY i.id, i.display_name, i.ror, i.country_code, i.type
ORDER BY author_count DESC, name
"""

CONCEPTS_SQL = """
SELECT c.id, c.display_name AS name, c.level, c.wikidata, wc.score
FROM work_concepts wc JOIN concepts c ON c.id = wc.concept_id
WHERE wc.work_id = %s
ORDER BY wc.score DESC NULLS LAST, name
"""

TOPICS_SQL = """
SELECT t.id, t.display_name AS name, t.subfield, t.field, t.domain, wt.score, wt.is_primary
FROM work_topics wt JOIN topics t ON t.id = wt.topic_id
WHERE wt.work_id = %s
ORDER BY wt.is_primary DESC, wt.score DESC NULLS LAST
"""


def _with_country(inst: dict[str, Any]) -> dict[str, Any]:
    return {**inst, "country_name": country_name(inst.get("country_code"))}


def _links(work: dict[str, Any]) -> list[dict[str, str]]:
    links: list[dict[str, str]] = []
    seen: set[str] = set()

    def add(label: str, url: str | None) -> None:
        if url and url not in seen:
            seen.add(url)
            links.append({"label": label, "url": url})

    if work["doi"]:
        add("DOI", f"https://doi.org/{work['doi']}")
    primary = work.get("primary_location") or {}
    add("Publisher page", primary.get("landing_page_url"))
    add("PDF", primary.get("pdf_url"))
    add("Open access copy", work.get("oa_url"))
    add("OpenAlex record", f"https://openalex.org/{work['id']}")
    return links


def _locations(raw_locations: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    out = []
    for loc in raw_locations or []:
        url = loc.get("landing_page_url") or loc.get("pdf_url")
        if not url:
            continue
        out.append(
            {
                "source": (loc.get("source") or {}).get("display_name")
                or loc.get("raw_source_name"),
                "url": url,
                "pdf_url": loc.get("pdf_url"),
                "is_oa": bool(loc.get("is_oa")),
                "version": loc.get("version"),
                "license": loc.get("license"),
            }
        )
    return out


def get_work_detail(conn: psycopg.Connection, work_id: str) -> dict[str, Any] | None:
    with conn.cursor(row_factory=dict_row) as cur:
        work = cur.execute(WORK_SQL, (work_id,)).fetchone()
        if work is None:
            return None
        authors = cur.execute(AUTHORS_SQL, (work_id,)).fetchall()
        affiliations = cur.execute(AFFILIATIONS_SQL, (work_id,)).fetchall()
        concepts = cur.execute(CONCEPTS_SQL, (work_id,)).fetchall()
        topics = cur.execute(TOPICS_SQL, (work_id,)).fetchall()

    for a in authors:
        a["institutions"] = [_with_country(i) for i in a["institutions"]]
        a["countries"] = [{"code": c, "name": country_name(c)} for c in a["countries"]]

    primary = work.get("primary_location") or {}
    percentile = work.get("citation_percentile") or {}
    return {
        "id": work["id"],
        "openalex_url": f"https://openalex.org/{work['id']}",
        "doi": work["doi"],
        "title": work["title"],
        "abstract": work["abstract"],
        "publication_date": work["publication_date"],
        "publication_year": work["publication_year"],
        "type": work["type"],
        "language": work["language"],
        "source": {
            "name": work["source_name"],
            "type": (primary.get("source") or {}).get("type"),
            "landing_page_url": work["landing_page_url"],
            "license": primary.get("license"),
            "version": primary.get("version"),
        },
        "biblio": work.get("biblio"),
        "cited_by_count": work["cited_by_count"],
        "citation_percentile": percentile.get("value"),
        "is_top_10_percent": percentile.get("is_in_top_10_percent"),
        "fwci": work["fwci"],
        "referenced_works_count": work["referenced_works_count"],
        "counts_by_year": sorted(work.get("counts_by_year") or [], key=lambda c: c["year"]),
        "open_access": {
            "is_oa": bool(work["is_oa"]),
            "status": work["oa_status"],
            "url": work["oa_url"],
        },
        "authors": authors,
        "affiliations": [_with_country(a) for a in affiliations],
        "concepts": concepts,
        "topics": topics,
        "keywords": [k.get("display_name") for k in work.get("keywords") or []],
        "sdgs": [s.get("display_name") for s in work.get("sdgs") or []],
        "links": _links(work),
        "locations": _locations(work.get("locations")),
        "harvested_at": work["harvested_at"],
    }
