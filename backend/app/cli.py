"""Command-line entry point for the data pipeline.

python -m app.cli harvest          # OpenAlex API -> Postgres (+ JSONL snapshot)
python -m app.cli load-snapshot    # JSONL snapshot -> Postgres (no API key needed)
python -m app.cli index            # Postgres -> Elasticsearch (new index + alias swap)
python -m app.cli bootstrap        # schema, seed if empty, index if missing (used by compose)
python -m app.cli analyze          # print the analysis report (Markdown)
"""

from __future__ import annotations

import argparse
import gzip
import json
import logging
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

import psycopg
from elasticsearch import Elasticsearch

from . import db, es_index, insights
from .config import Settings, get_settings
from .openalex import FILTER, SEARCH, OpenAlexClient, OpenAlexError

log = logging.getLogger("pipeline")


# --------------------------------------------------------------------------- helpers


def wait_for_services(settings: Settings, timeout: float = 120) -> None:
    deadline = time.monotonic() + timeout
    while True:
        try:
            with db.connect(settings.database_url):
                pass
            es = Elasticsearch(settings.elasticsearch_url)
            es.cluster.health(wait_for_status="yellow", timeout="5s")
            return
        except Exception as exc:  # noqa: BLE001 - any failure means "not ready yet"
            if time.monotonic() > deadline:
                raise SystemExit(f"Services not ready after {timeout:.0f}s: {exc}") from exc
            log.info("Waiting for Postgres/Elasticsearch: %s", exc)
            time.sleep(3)


@contextmanager
def _snapshot_writer(path: str | None):
    if not path:
        yield None
        return
    p = Path(path)
    tmp = p.with_suffix(p.suffix + ".tmp")
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        fh = gzip.open(tmp, "wt", encoding="utf-8")  # noqa: SIM115 - closed below
    except OSError as exc:  # e.g. read-only volume: the database is what matters
        log.warning("Cannot write snapshot to %s (%s) - continuing without it", path, exc)
        yield None
        return
    with fh:
        yield fh
    tmp.replace(p)  # only replace the previous snapshot once the new one is complete


def read_snapshot(path: str) -> Iterator[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                yield json.loads(line)


# --------------------------------------------------------------------------- commands


def cmd_harvest(settings: Settings, limit: int, snapshot: str | None) -> int:
    started = datetime.now().astimezone()
    total: int | None = None
    with db.connect(settings.database_url) as conn:
        db.apply_schema(conn)
        with (
            OpenAlexClient(settings.openalex_base_url, settings.openalex_api_key) as client,
            _snapshot_writer(snapshot) as out,
        ):

            def works() -> Iterator[dict[str, Any]]:
                nonlocal total
                for work, meta in client.iter_works(limit):
                    total = meta.get("count", total)
                    if out:
                        out.write(json.dumps(work, ensure_ascii=False) + "\n")
                    yield work

            stored = db.store_works(conn, works())
        db.record_run(
            conn,
            source="api",
            query=f"search={SEARCH}&filter={FILTER}",
            openalex_total=total,
            works_stored=stored,
            started_at=started,
        )
    log.info("Harvested %d works (of %s matching in OpenAlex)", stored, total)
    return stored


def cmd_load_snapshot(settings: Settings, path: str) -> int:
    started = datetime.now().astimezone()
    with db.connect(settings.database_url) as conn:
        db.apply_schema(conn)
        stored = db.store_works(conn, read_snapshot(path))
        db.record_run(
            conn,
            source="snapshot",
            query=path,
            openalex_total=None,
            works_stored=stored,
            started_at=started,
        )
    log.info("Loaded %d works from %s", stored, path)
    return stored


def cmd_index(settings: Settings) -> int:
    es = Elasticsearch(settings.elasticsearch_url, request_timeout=60)
    with db.connect(settings.database_url) as conn:
        _, count = es_index.reindex(es, settings.es_index_alias, db.iter_raw_works(conn))
    return count


def cmd_bootstrap(settings: Settings, reindex: bool) -> None:
    """Idempotent start-up job: make sure there is data in Postgres and an index in ES."""
    wait_for_services(settings)
    with db.connect(settings.database_url) as conn:
        db.apply_schema(conn)
        existing = db.count_works(conn)
    if existing == 0:
        if Path(settings.snapshot_path).exists():
            log.info("Database empty - seeding from snapshot %s", settings.snapshot_path)
            cmd_load_snapshot(settings, settings.snapshot_path)
        else:
            log.info("Database empty and no snapshot - harvesting from OpenAlex")
            cmd_harvest(settings, settings.harvest_limit, settings.snapshot_path)
        reindex = True
    es = Elasticsearch(settings.elasticsearch_url)
    if reindex or not es_index.alias_exists(es, settings.es_index_alias):
        cmd_index(settings)
    else:
        log.info("Index alias '%s' already present - skipping reindex", settings.es_index_alias)


def cmd_analyze(settings: Settings) -> None:
    with psycopg.connect(settings.database_url) as conn:
        report = insights.compute(conn)
    sys.stdout.write(insights.to_markdown(report))


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("elastic_transport").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    settings = get_settings()

    parser = argparse.ArgumentParser(
        prog="python -m app.cli",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("harvest", help="fetch works from OpenAlex into Postgres")
    p.add_argument("--limit", type=int, default=settings.harvest_limit)
    p.add_argument(
        "--snapshot", default=settings.snapshot_path, help="write raw JSONL.gz here ('' to disable)"
    )
    p.add_argument("--index", action="store_true", help="re-index Elasticsearch afterwards")

    p = sub.add_parser("load-snapshot", help="load a JSONL.gz snapshot into Postgres")
    p.add_argument("path", nargs="?", default=settings.snapshot_path)
    p.add_argument("--index", action="store_true", help="re-index Elasticsearch afterwards")

    sub.add_parser("index", help="(re)build the Elasticsearch index from Postgres")

    p = sub.add_parser("bootstrap", help="seed + index if needed (idempotent)")
    p.add_argument("--reindex", action="store_true", help="always rebuild the index")

    sub.add_parser("analyze", help="print the analysis report as Markdown")

    args = parser.parse_args(argv)
    try:
        if args.command == "harvest":
            cmd_harvest(settings, args.limit, args.snapshot or None)
            if args.index:
                cmd_index(settings)
        elif args.command == "load-snapshot":
            cmd_load_snapshot(settings, args.path)
            if args.index:
                cmd_index(settings)
        elif args.command == "index":
            cmd_index(settings)
        elif args.command == "bootstrap":
            cmd_bootstrap(settings, args.reindex)
        elif args.command == "analyze":
            cmd_analyze(settings)
    except OpenAlexError as exc:
        raise SystemExit(f"Harvest failed: {exc}") from exc


if __name__ == "__main__":
    main()
