"""FastAPI application: search (Elasticsearch), publication detail and insights (Postgres)."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date
from typing import Annotated, Any

import psycopg
from elastic_transport import ConnectionError as ESConnectionError
from elasticsearch import ApiError, Elasticsearch, NotFoundError
from fastapi import Depends, FastAPI, HTTPException, Path, Query, Request
from fastapi.responses import JSONResponse
from psycopg_pool import ConnectionPool

from . import insights, repository
from .config import Settings, get_settings
from .search import (
    FACET_FIELDS,
    SearchField,
    SearchParams,
    SortOrder,
    build_facet_body,
    build_search_body,
    facet_values,
    shape_search_response,
    valid_work_id,
)

log = logging.getLogger("api")


class Services:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.es = Elasticsearch(settings.elasticsearch_url, request_timeout=10, max_retries=1)
        # open=False + open(wait=False): the API starts even if Postgres is still booting.
        self.pg = ConnectionPool(settings.database_url, min_size=1, max_size=10, open=False)
        self._insights: tuple[float, dict[str, Any]] | None = None
        self._insights_lock = threading.Lock()

    def open(self) -> None:
        self.pg.open(wait=False)

    def close(self) -> None:
        self.pg.close()
        self.es.close()

    def insights(self) -> dict[str, Any]:
        """Insights only change when data is re-harvested, so cache them briefly."""
        with self._insights_lock:
            now = time.monotonic()
            if self._insights and now - self._insights[0] < self.settings.insights_cache_seconds:
                return self._insights[1]
            with self.pg.connection() as conn:
                report = insights.compute(conn)
            self._insights = (now, report)
            return report


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    services = Services(get_settings())
    services.open()
    app.state.services = services
    yield
    services.close()


app = FastAPI(
    title="OpenAlex Climate DK API",
    description="Search and explore 2025 climate-change publications from Danish institutions.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    redoc_url=None,
)


def services(request: Request) -> Services:
    return request.app.state.services


@app.exception_handler(ESConnectionError)
async def es_unavailable(_: Request, exc: ESConnectionError) -> JSONResponse:
    log.error("Elasticsearch unavailable: %s", exc)
    return JSONResponse(status_code=503, content={"detail": "Search service is unavailable."})


@app.exception_handler(psycopg.OperationalError)
async def pg_unavailable(_: Request, exc: psycopg.OperationalError) -> JSONResponse:
    log.error("Postgres unavailable: %s", exc)
    return JSONResponse(status_code=503, content={"detail": "Database is unavailable."})


@app.exception_handler(NotFoundError)
async def index_missing(_: Request, exc: NotFoundError) -> JSONResponse:
    log.error("Index missing: %s", exc)
    return JSONResponse(
        status_code=503,
        content={"detail": "Search index not found - run the indexer (python -m app.cli index)."},
    )


def search_params(
    q: Annotated[str, Query(max_length=500, description="Free-text query")] = "",
    field: Annotated[SearchField, Query(description="Restrict the text search")] = "all",
    author: Annotated[list[str], Query(description="Author name (repeatable)")] = [],  # noqa: B006
    institution: Annotated[list[str], Query()] = [],  # noqa: B006
    country: Annotated[list[str], Query(description="ISO 3166-1 alpha-2 code")] = [],  # noqa: B006
    concept: Annotated[list[str], Query()] = [],  # noqa: B006
    type: Annotated[list[str], Query(description="Publication type")] = [],  # noqa: B006, A002
    oa_status: Annotated[list[str], Query(description="Open access status")] = [],  # noqa: B006
    date_from: date | None = None,
    date_to: date | None = None,
    sort: SortOrder = "relevance",
    page: Annotated[int, Query(ge=1, le=500)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> SearchParams:
    if page * size > 10_000:
        raise HTTPException(400, "Cannot page beyond 10,000 results")
    return SearchParams(
        q=q,
        field=field,
        filters={
            "author": author,
            "institution": institution,
            "country": [c.upper() for c in country],
            "concept": concept,
            "type": type,
            "oa_status": oa_status,
        },
        date_from=date_from,
        date_to=date_to,
        sort=sort,
        page=page,
        size=size,
    )


Params = Annotated[SearchParams, Depends(search_params)]
Svc = Annotated[Services, Depends(services)]


@app.get("/api/search", summary="Search publications with facets")
def search(params: Params, svc: Svc) -> dict[str, Any]:
    resp = svc.es.search(index=svc.settings.es_index_alias, **build_search_body(params))
    return shape_search_response(resp.body, params)


@app.get("/api/facets/{facet}", summary="Values of one facet, optionally filtered by substring")
def facet(
    facet: Annotated[str, Path(pattern="^(" + "|".join(FACET_FIELDS) + ")$")],
    params: Params,
    svc: Svc,
    contains: Annotated[str, Query(max_length=100)] = "",
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    body = build_facet_body(params, facet, contains, limit)
    resp = svc.es.search(index=svc.settings.es_index_alias, **body)
    return {"facet": facet, "values": facet_values(resp.body.get("aggregations", {}), facet)}


@app.get("/api/works/{work_id}", summary="Full publication record")
def work_detail(work_id: str, svc: Svc) -> dict[str, Any]:
    if not valid_work_id(work_id):
        raise HTTPException(404, "Publication not found")
    with svc.pg.connection() as conn:
        detail = repository.get_work_detail(conn, work_id)
    if detail is None:
        raise HTTPException(404, "Publication not found")
    return detail


@app.get("/api/insights", summary="Aggregate analysis of the harvested data")
def get_insights(svc: Svc) -> dict[str, Any]:
    return svc.insights()


@app.get("/api/health", summary="Liveness/readiness of the API and its backing services")
def health(svc: Svc) -> JSONResponse:
    status: dict[str, Any] = {}
    try:
        status["documents"] = svc.es.count(index=svc.settings.es_index_alias)["count"]
        status["elasticsearch"] = "ok"
    except (ESConnectionError, ApiError) as exc:
        status["elasticsearch"] = f"error: {exc.__class__.__name__}"
    try:
        with svc.pg.connection(timeout=3) as conn:
            conn.execute("SELECT 1")
        status["postgres"] = "ok"
    except Exception as exc:  # noqa: BLE001
        status["postgres"] = f"error: {exc.__class__.__name__}"
    healthy = status["elasticsearch"] == "ok" and status["postgres"] == "ok"
    status["status"] = "ok" if healthy else "degraded"
    return JSONResponse(status_code=200 if healthy else 503, content=status)
