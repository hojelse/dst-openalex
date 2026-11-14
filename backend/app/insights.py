"""Analysis of the harvested data (optional task 4), computed with SQL in Postgres.

Shared by the `/api/insights` endpoint (charts in the UI) and `python -m app.cli analyze`
(Markdown report committed as ANALYSIS.md).
"""

from __future__ import annotations

from typing import Any

import psycopg
from psycopg.rows import dict_row

from .countries import country_name

SUMMARY_SQL = """
SELECT
    (SELECT count(*) FROM works)                                        AS works,
    (SELECT count(DISTINCT author_id) FROM authorships)                 AS authors,
    (SELECT count(DISTINCT institution_id) FROM authorship_institutions) AS institutions,
    (SELECT count(DISTINCT country_code) FROM authorship_countries)     AS countries,
    (SELECT coalesce(sum(cited_by_count), 0) FROM works)                AS citations,
    (SELECT round(avg(is_oa::int)::numeric, 4) FROM works)              AS oa_share,
    (SELECT min(publication_date) FROM works)                           AS first_date,
    (SELECT max(publication_date) FROM works)                           AS last_date,
    (SELECT max(finished_at) FROM harvest_runs)                         AS harvested_at,
    -- OpenAlex uses 1 January when only the publication year is known.
    (SELECT count(*) FROM works
     WHERE publication_date = make_date(publication_year, 1, 1))        AS jan_first_dates
"""

# "Danish author" = at least one affiliation (on any harvested work) with a Danish
# institution. Ranked by number of harvested works, ties broken by citations.
TOP_DANISH_AUTHORS_SQL = """
WITH danish_authors AS (
    SELECT DISTINCT au.author_id
    FROM authorships au
    JOIN authorship_institutions ai USING (work_id, author_position)
    JOIN institutions i ON i.id = ai.institution_id
    WHERE i.country_code = 'DK' AND au.author_id IS NOT NULL
),
author_work AS (       -- distinct, so a duplicated author slot never double counts
    SELECT DISTINCT au.author_id, au.work_id
    FROM authorships au
    JOIN danish_authors USING (author_id)
),
stats AS (
    SELECT aw.author_id, count(*) AS works, sum(w.cited_by_count) AS citations
    FROM author_work aw
    JOIN works w ON w.id = aw.work_id
    GROUP BY aw.author_id
)
SELECT
    s.author_id AS id, a.display_name AS name, a.orcid, s.works, s.citations,
    (SELECT json_agg(x ORDER BY x.is_danish DESC, x.works DESC, x.name)
     FROM (SELECT i.id, i.display_name AS name, i.country_code,
                  i.country_code = 'DK' AS is_danish,
                  count(DISTINCT ai.work_id) AS works
           FROM authorships au
           JOIN authorship_institutions ai USING (work_id, author_position)
           JOIN institutions i ON i.id = ai.institution_id
           WHERE au.author_id = s.author_id
           GROUP BY i.id, i.display_name, i.country_code) x) AS affiliations,
    (SELECT count(*) FROM stats s2 WHERE s2.works = s.works) AS tied_with
FROM stats s
JOIN authors a ON a.id = s.author_id
ORDER BY s.works DESC, s.citations DESC, s.author_id
LIMIT %(limit)s
"""

DANISH_AUTHOR_COUNT_SQL = """
SELECT count(DISTINCT au.author_id)
FROM authorships au
JOIN authorship_institutions ai USING (work_id, author_position)
JOIN institutions i ON i.id = ai.institution_id
WHERE i.country_code = 'DK'
"""

# Each author entity is counted once per country, however many works/affiliations
# link them to it. Countries come from OpenAlex's per-authorship country list plus
# the countries of the linked institutions.
AUTHOR_COUNTRIES_SQL = """
WITH author_country AS (
    SELECT au.author_id, ac.country_code
    FROM authorships au
    JOIN authorship_countries ac USING (work_id, author_position)
    WHERE au.author_id IS NOT NULL
    UNION
    SELECT au.author_id, i.country_code
    FROM authorships au
    JOIN authorship_institutions ai USING (work_id, author_position)
    JOIN institutions i ON i.id = ai.institution_id
    WHERE au.author_id IS NOT NULL AND i.country_code IS NOT NULL
)
SELECT country_code AS code, count(DISTINCT author_id) AS authors
FROM author_country
GROUP BY country_code
ORDER BY authors DESC, code
"""

AUTHORS_WITHOUT_COUNTRY_SQL = """
SELECT count(DISTINCT au.author_id)
FROM authorships au
WHERE au.author_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM authorships au2
      JOIN authorship_countries ac USING (work_id, author_position)
      WHERE au2.author_id = au.author_id)
  AND NOT EXISTS (
      SELECT 1 FROM authorships au3
      JOIN authorship_institutions ai USING (work_id, author_position)
      WHERE au3.author_id = au.author_id)
"""

CITATION_BINS: list[tuple[str, int, int | None]] = [
    ("0", 0, 0),
    ("1", 1, 1),
    ("2", 2, 2),
    ("3–4", 3, 4),
    ("5–9", 5, 9),
    ("10–19", 10, 19),
    ("20–49", 20, 49),
    ("50–99", 50, 99),
    ("100+", 100, None),
]

CITATION_STATS_SQL = """
SELECT
    round(avg(cited_by_count)::numeric, 2)                                   AS mean,
    percentile_cont(0.5) WITHIN GROUP (ORDER BY cited_by_count)              AS median,
    percentile_cont(0.9) WITHIN GROUP (ORDER BY cited_by_count)              AS p90,
    max(cited_by_count)                                                      AS max,
    round(avg((cited_by_count = 0)::int)::numeric, 4)                        AS uncited_share
FROM works
"""

BY_MONTH_SQL = """
SELECT to_char(date_trunc('month', publication_date), 'YYYY-MM') AS month, count(*) AS works
FROM works
WHERE publication_date IS NOT NULL
GROUP BY 1
ORDER BY 1
"""

OA_STATUS_SQL = """
SELECT coalesce(oa_status, 'unknown') AS status, count(*) AS works
FROM works GROUP BY 1 ORDER BY 2 DESC
"""

TOP_DK_INSTITUTIONS_SQL = """
SELECT i.id, i.display_name AS name, count(DISTINCT ai.work_id) AS works
FROM authorship_institutions ai
JOIN institutions i ON i.id = ai.institution_id
WHERE i.country_code = 'DK'
GROUP BY i.id, i.display_name
ORDER BY works DESC, name
LIMIT 15
"""

INTERNATIONAL_SQL = """
SELECT
    count(*) FILTER (WHERE EXISTS (
        SELECT 1 FROM authorship_countries ac
        WHERE ac.work_id = w.id AND ac.country_code <> 'DK')) AS international,
    count(*) AS total
FROM works w
"""

TOP_FIELDS_SQL = """
SELECT t.field AS name, count(*) AS works
FROM work_topics wt
JOIN topics t ON t.id = wt.topic_id
WHERE wt.is_primary
GROUP BY t.field
ORDER BY works DESC, name
LIMIT 12
"""


def compute(conn: psycopg.Connection, *, top_n: int = 20) -> dict[str, Any]:
    with conn.cursor(row_factory=dict_row) as cur:
        summary = cur.execute(SUMMARY_SQL).fetchone()
        top_authors = cur.execute(TOP_DANISH_AUTHORS_SQL, {"limit": top_n}).fetchall()
        danish_authors = cur.execute(DANISH_AUTHOR_COUNT_SQL).fetchone()["count"]
        countries = cur.execute(AUTHOR_COUNTRIES_SQL).fetchall()
        no_country = cur.execute(AUTHORS_WITHOUT_COUNTRY_SQL).fetchone()["count"]
        stats = cur.execute(CITATION_STATS_SQL).fetchone()
        counts = [
            r["cited_by_count"] for r in cur.execute("SELECT cited_by_count FROM works").fetchall()
        ]
        by_month = cur.execute(BY_MONTH_SQL).fetchall()
        oa_status = cur.execute(OA_STATUS_SQL).fetchall()
        dk_institutions = cur.execute(TOP_DK_INSTITUTIONS_SQL).fetchall()
        international = cur.execute(INTERNATIONAL_SQL).fetchone()
        fields = cur.execute(TOP_FIELDS_SQL).fetchall()

    histogram = [
        {
            "bin": label,
            "works": sum(1 for c in counts if c >= lo and (hi is None or c <= hi)),
        }
        for label, lo, hi in CITATION_BINS
    ]
    for c in countries:
        c["name"] = country_name(c["code"])

    return {
        "summary": {
            **{k: v for k, v in summary.items() if k not in {"first_date", "last_date"}},
            "oa_share": float(summary["oa_share"] or 0),
            "first_date": summary["first_date"].isoformat() if summary["first_date"] else None,
            "last_date": summary["last_date"].isoformat() if summary["last_date"] else None,
            "harvested_at": summary["harvested_at"].isoformat()
            if summary["harvested_at"]
            else None,
            "danish_authors": danish_authors,
        },
        "top_danish_authors": top_authors,
        "author_countries": countries,
        "authors_without_country": no_country,
        "citations": {
            "histogram": histogram,
            "mean": float(stats["mean"] or 0),
            "median": float(stats["median"] or 0),
            "p90": float(stats["p90"] or 0),
            "max": stats["max"] or 0,
            "uncited_share": float(stats["uncited_share"] or 0),
        },
        "works_by_month": by_month,
        "oa_status": oa_status,
        "top_danish_institutions": dk_institutions,
        "international_collaboration": {
            "international": international["international"],
            "total": international["total"],
            "share": international["international"] / international["total"]
            if international["total"]
            else 0,
        },
        "top_fields": fields,
    }


def to_markdown(report: dict[str, Any]) -> str:
    s = report["summary"]
    out: list[str] = []
    w = out.append
    w("# Analysis of the harvested OpenAlex data\n")
    w(
        "Generated by `python -m app.cli analyze` from the Postgres database "
        f"(data loaded {(s['harvested_at'] or 'n/a')[:10]}). The SQL lives in "
        "[`backend/app/insights.py`](backend/app/insights.py); the same numbers are "
        "charted on the **Insights** page of the app.\n"
    )
    w("## Dataset\n")
    w("| Metric | Value |\n|---|---:|")
    w(f"| Works | {s['works']:,} |")
    w(f"| Publication dates | {s['first_date']} – {s['last_date']} |")
    w(f"| Distinct authors | {s['authors']:,} |")
    w(f"| …of which Danish (≥1 Danish affiliation) | {s['danish_authors']:,} |")
    w(f"| Distinct institutions | {s['institutions']:,} |")
    w(f"| Distinct countries | {s['countries']:,} |")
    w(f"| Total citations | {s['citations']:,} |")
    w(f"| Open access share | {s['oa_share']:.1%} |")
    ic = report["international_collaboration"]
    w(
        f"| Works with a non-Danish co-author country | {ic['international']:,} "
        f"({ic['share']:.1%}) |\n"
    )

    w("## Top 20 Danish authors\n")
    w(
        "A *Danish author* has at least one affiliation with a Danish institution "
        "(institution `country_code = DK`) on any harvested work. Authors are ranked by the "
        "number of harvested works, ties broken by total citations of those works. "
        "Affiliations list every institution the author is linked to in the dataset "
        "(Danish ones first) with the number of works.\n"
    )
    w("| # | Author | Works | Citations | Affiliations (works) |\n|---:|---|---:|---:|---|")
    for i, a in enumerate(report["top_danish_authors"], 1):
        affs = "; ".join(
            f"{x['name']}{' 🇩🇰' if x['is_danish'] else ''} ({x['works']})"
            for x in a["affiliations"] or []
        )
        w(f"| {i} | {a['name']} | {a['works']} | {a['citations']:,} | {affs} |")
    if report["top_danish_authors"]:
        last = report["top_danish_authors"][-1]
        w(
            f"\nNote: {last['tied_with']} Danish authors have exactly {last['works']} works, "
            "so the bottom of the list is decided by the citation tie-breaker.\n"
        )

    w("## Authors per country\n")
    w(
        "Each author entity is counted once per country it is affiliated with (via the "
        "authorship's countries or its institutions' countries), regardless of how many works "
        f"link them. {report['authors_without_country']:,} authors have no country information."
        "\n"
    )
    w("| Country | Authors |\n|---|---:|")
    for c in report["author_countries"][:25]:
        w(f"| {c['name']} ({c['code']}) | {c['authors']:,} |")
    rest = report["author_countries"][25:]
    if rest:
        w(f"| *{len(rest)} other countries* | {sum(c['authors'] for c in rest):,} |")
    w("")

    cit = report["citations"]
    w("## Citations per publication\n")
    w(
        f"Mean {cit['mean']:.2f}, median {cit['median']:.0f}, 90th percentile {cit['p90']:.0f}, "
        f"max {cit['max']:,}; {cit['uncited_share']:.1%} of works are not cited yet "
        "(unsurprising for 2025 publications).\n"
    )
    w("| Citations | Works |\n|---|---:|")
    for b in cit["histogram"]:
        w(f"| {b['bin']} | {b['works']:,} |")
    w("")

    w("## Other observations\n")
    w("**Top Danish institutions by number of works**\n")
    w("| Institution | Works |\n|---|---:|")
    for i in report["top_danish_institutions"]:
        w(f"| {i['name']} | {i['works']:,} |")
    w("\n**Open access status**\n")
    w("| Status | Works |\n|---|---:|")
    for o in report["oa_status"]:
        w(f"| {o['status']} | {o['works']:,} |")
    w("\n**Research field of the primary topic**\n")
    w("| Field | Works |\n|---|---:|")
    for f in report["top_fields"]:
        w(f"| {f['name']} | {f['works']:,} |")
    w("\n**Works per publication month**\n")
    w(
        f"January is inflated: {s['jan_first_dates']} works are dated exactly 1 January, which "
        "OpenAlex uses when only the publication year is known.\n"
    )
    w("| Month | Works |\n|---|---:|")
    for m in report["works_by_month"]:
        w(f"| {m['month']} | {m['works']:,} |")
    w("")
    return "\n".join(out)
