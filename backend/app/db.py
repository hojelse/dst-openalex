"""Postgres access for the pipeline (sync psycopg) – schema, upserts and reads."""

from __future__ import annotations

import logging
from collections.abc import Iterable, Iterator
from datetime import datetime
from importlib import resources
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from .transform import NormalizedWork, normalize_work

log = logging.getLogger(__name__)


def connect(database_url: str) -> psycopg.Connection:
    return psycopg.connect(database_url)


def apply_schema(conn: psycopg.Connection) -> None:
    sql = resources.files("app").joinpath("schema.sql").read_text()
    with conn.transaction():
        conn.execute(sql)


def _upsert(table: str, rows: list[dict[str, Any]], key: tuple[str, ...]) -> tuple[str, list]:
    cols = list(rows[0].keys())
    updates = [c for c in cols if c not in key]
    conflict = (
        "DO UPDATE SET " + ", ".join(f"{c} = EXCLUDED.{c}" for c in updates)
        if updates
        else "DO NOTHING"
    )
    sql = (
        f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('%s' for _ in cols)}) "
        f"ON CONFLICT ({', '.join(key)}) {conflict}"
    )
    return sql, [tuple(r[c] for c in cols) for r in rows]


def _write(cur: psycopg.Cursor, table: str, rows: list[dict[str, Any]], key: tuple[str, ...]):
    if not rows:
        return
    sql, params = _upsert(table, rows, key)
    cur.executemany(sql, params)


def store_work(cur: psycopg.Cursor, raw: dict[str, Any], rank: int | None) -> NormalizedWork:
    """Upsert one work and replace its child rows, so re-harvesting refreshes cleanly."""
    nw = normalize_work(raw, rank=rank)
    work = dict(nw.work, raw=Jsonb(raw), harvested_at=datetime.now().astimezone())
    _write(cur, "works", [work], ("id",))
    # Child rows are owned by the work: delete + insert is simpler than diffing.
    for table in ("authorships", "work_concepts", "work_topics"):
        cur.execute(f"DELETE FROM {table} WHERE work_id = %s", (nw.work["id"],))

    _write(cur, "authors", nw.authors, ("id",))
    _write(cur, "institutions", nw.institutions, ("id",))
    _write(cur, "concepts", nw.concepts, ("id",))
    _write(cur, "topics", nw.topics, ("id",))
    _write(cur, "authorships", nw.authorships, ("work_id", "author_position"))
    _write(
        cur,
        "authorship_institutions",
        nw.authorship_institutions,
        ("work_id", "author_position", "institution_id"),
    )
    _write(
        cur,
        "authorship_countries",
        nw.authorship_countries,
        ("work_id", "author_position", "country_code"),
    )
    _write(cur, "work_concepts", nw.work_concepts, ("work_id", "concept_id"))
    _write(cur, "work_topics", nw.work_topics, ("work_id", "topic_id"))
    return nw


def store_works(
    conn: psycopg.Connection,
    works: Iterable[dict[str, Any]],
    *,
    batch_size: int = 100,
) -> int:
    """Store works in batches (one transaction per batch). Returns the number stored."""
    count = 0
    batch: list[dict[str, Any]] = []

    def flush() -> None:
        nonlocal count
        with conn.transaction(), conn.cursor() as cur:
            for raw in batch:
                count += 1
                store_work(cur, raw, rank=count)
        log.info("Stored %d works", count)
        batch.clear()

    for raw in works:
        batch.append(raw)
        if len(batch) >= batch_size:
            flush()
    if batch:
        flush()
    return count


def record_run(
    conn: psycopg.Connection,
    *,
    source: str,
    query: str | None,
    openalex_total: int | None,
    works_stored: int,
    started_at: datetime,
) -> None:
    with conn.transaction():
        conn.execute(
            "INSERT INTO harvest_runs (source, query, openalex_total, works_stored, started_at) "
            "VALUES (%s, %s, %s, %s, %s)",
            (source, query, openalex_total, works_stored, started_at),
        )


def count_works(conn: psycopg.Connection) -> int:
    return conn.execute("SELECT count(*) FROM works").fetchone()[0]


def iter_raw_works(conn: psycopg.Connection) -> Iterator[tuple[dict[str, Any], int | None]]:
    """Stream (raw_json, harvest_rank) for every stored work using a server-side cursor."""
    with conn.cursor(name="iter_works") as cur:
        cur.itersize = 200
        cur.execute("SELECT raw, harvest_rank FROM works ORDER BY harvest_rank NULLS LAST, id")
        yield from cur
