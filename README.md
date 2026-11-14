# Climate Research DK: search Danish climate research from OpenAlex

A small full-stack application that harvests 2025 climate-change publications with at least one Danish institution from the [OpenAlex API](https://docs.openalex.org), stores them in **PostgreSQL**, indexes them in **Elasticsearch**, and serves a **React** search interface through a **FastAPI** backend, plus an *Insights* page with the optional data analysis.

![Search page](docs/screenshots/search.png)

| Task | Where |
|---|---|
| 1. Data extraction & storage | `backend/app/openalex.py` (client), `backend/app/transform.py` (normalisation), `backend/app/schema.sql` (relational model), `python -m app.cli harvest` |
| 2. Search & filter interface (Option A, Elasticsearch) | `backend/app/es_index.py` (mapping/indexer), `backend/app/search.py` (queries), `backend/app/main.py` (API), `frontend/` (React app) |
| 3. Documentation | this README, [`PROMPTS.md`](PROMPTS.md) |
| 4. Extra investigation (optional) | [`ANALYSIS.md`](ANALYSIS.md), `backend/app/insights.py` (SQL), the **Insights** page |

---

## Architecture

```mermaid
flowchart LR
    OA[(OpenAlex API)] -- "cursor paging<br/>1000 works" --> H[Harvester<br/>python -m app.cli harvest]
    H -- "raw JSON + normalised rows" --> PG[(PostgreSQL<br/>system of record)]
    H -. "works.jsonl.gz snapshot" .-> S[(data/)]
    S -. "load-snapshot (no API key needed)" .-> PG
    PG -- "python -m app.cli index<br/>new index + alias swap" --> ES[(Elasticsearch<br/>search index)]
    subgraph Runtime
      W[nginx + React SPA] -- "/api/*" --> API[FastAPI]
      API -- "search, facets" --> ES
      API -- "detail, insights (SQL)" --> PG
    end
    U((Browser)) --> W
```

| Component | Tech | Responsibility |
|---|---|---|
| **Harvester / pipeline** | Python, httpx, psycopg | Pages through the OpenAlex query with a cursor, retries with backoff, re-fetches works whose author list was truncated, upserts into Postgres and writes a raw JSONL snapshot. `bootstrap` makes start-up idempotent. |
| **PostgreSQL** | Postgres 17 | System of record. Normalised tables (`works`, `authors`, `institutions`, `authorships`, `authorship_institutions`, `authorship_countries`, `concepts`, `work_concepts`, `topics`, `work_topics`, `harvest_runs`) plus the full raw API response in `works.raw` (JSONB). |
| **Indexer** | elasticsearch-py | Reads works from Postgres, builds denormalised documents, bulk-indexes into a new versioned index (`works_<timestamp>`) and atomically moves the `works` alias, so re-indexing has no downtime. |
| **Elasticsearch** | ES 9.2 | Full-text search (English stemming + accent folding, so `Soren` finds `Søren`), facets via aggregations, highlighting. |
| **API** | FastAPI | `GET /api/search`, `GET /api/facets/{facet}`, `GET /api/works/{id}`, `GET /api/insights`, `GET /api/health`. OpenAPI docs at `/api/docs`. |
| **Web** | React 19, TypeScript, Vite, TanStack Query, React Router; served by nginx | Search page, publication detail page, insights page. nginx serves the static build and proxies `/api` (same origin, so no CORS). |

### Key design decisions

- **Postgres and Elasticsearch, each for what it's good at.** Postgres holds the harvested data in a structured, de-duplicated form with referential integrity. That suits the analysis questions (e.g. "count each author once per country") in plain SQL, and lets the index be rebuilt without calling OpenAlex again. Elasticsearch is a derived read model optimised for search and faceting. The detail page reads from Postgres, the search page from Elasticsearch.
- **Raw + normalised storage.** Keeping the untouched API response (`works.raw`) means no information is lost if the schema needs another field later; the normalised tables make the important parts queryable.
- **Disjunctive faceting.** Filters are OR within a facet and AND across facets. Each facet's counts are computed with every *other* filter applied but not its own (`post_filter` + per-facet filter aggregations), so after picking *Sweden* you can still see and add *Norway*.
- **Search box.** `simple_query_string` with `AND` semantics across a field group chosen by the *Search in* selector (All fields / Title / Author / Country / Institution). It never errors on bad syntax and still supports `"phrases"`, `-exclusion`, `a | b` and `prefix*`. Country search matches names and ISO codes (`Kenya`, `KE`).
- **Safe highlighting.** Elasticsearch wraps matches in private-use Unicode markers rather than HTML; the UI turns them into `<mark>` elements, so no data is ever injected as HTML.
- **URL-driven UI state.** Query, filters, sort and page live in the URL: every search is shareable, and back/forward work.
- **Snapshot for reproducibility.** OpenAlex now requires an API key once a shared per-IP budget is used up. The harvested data is committed as `data/works.jsonl.gz` (OpenAlex data is CC0), so the stack starts with real data without a key; a live harvest is one command away.

### Data quality issues found and handled

- **Truncated author lists.** OpenAlex *list* responses cap `authorships` at 100. Six harvested papers had exactly 100 authors (really up to 310), so the harvester re-fetches those works from the single-work endpoint.
- **Authors without an OpenAlex ID** (~570 authorships). They are kept by name in the author list but can't be counted as distinct entities in the analysis.
- **Abstracts** come as an inverted index and are reconstructed. About 19% start with the literal heading "Abstract", which is stripped.
- **Titles** can contain inline HTML (`<i>`, `<sub>`), which is stripped for display and search.
- **1 January dates.** 108 works are dated 1 January because OpenAlex uses that date when only the year is known; this is flagged in the analysis.

---

## Running the application

### Quick start (Docker, recommended)

Prerequisites: Docker with Compose v2, about 2 GB of free RAM (Elasticsearch).

```bash
git clone <this repo> && cd dst-openalex
cp .env.example .env          # optional: add OPENALEX_API_KEY, change ports/passwords
docker compose up --build
```

Open **http://localhost:8080** (API docs at http://localhost:8080/api/docs).

What happens on start-up:

1. `postgres` and `elasticsearch` start and become healthy.
2. The one-shot `pipeline` service runs `python -m app.cli bootstrap`: it creates the schema; **if the database is empty** it loads the bundled snapshot (or harvests from OpenAlex if the snapshot is missing); **if the index alias doesn't exist** it builds the index. It is idempotent, so restarts don't redo work.
3. `api` starts once the pipeline has finished; `web` once the API is healthy.

Postgres (`5432`) and Elasticsearch (`9200`) are published on `127.0.0.1` only, for local inspection.

### Harvesting fresh data from OpenAlex

```bash
# OPENALEX_API_KEY must be set in .env (free key, see https://help.openalex.org/api/authentication/)
docker compose run --rm pipeline python -m app.cli harvest --index      # 1000 works -> Postgres -> new ES index
docker compose run --rm pipeline python -m app.cli harvest --limit 5000 --index
docker compose run --rm pipeline python -m app.cli analyze               # analysis report (Markdown)
```

The harvest upserts, so re-running it refreshes existing records. The API's insights cache expires after 5 minutes (or restart the `api` service).

### Local development (without Docker for the app code)

Run only the data stores in Docker, and the API and UI natively with hot reload:

```bash
docker compose up -d postgres elasticsearch

# Backend (Python 3.12+)
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
export SNAPSHOT_PATH=../data/works.jsonl.gz
python -m app.cli bootstrap --reindex     # schema + snapshot + index (other defaults point to localhost)
uvicorn app.main:app --reload             # http://localhost:8000/api/docs

# Frontend (Node 20+), in another shell
cd frontend
npm install
npm run dev                               # http://localhost:5173 (proxies /api to :8000)
```

### Tests and checks

```bash
cd backend
ruff check app tests
pytest -m "not integration"   # unit tests: transform, query builder, OpenAlex client (mocked HTTP)
pytest -m integration         # API end-to-end against running Postgres + Elasticsearch with data loaded

cd frontend
npm run typecheck && npm test && npm run build
```

GitHub Actions (`.github/workflows/ci.yml`) runs all of the above, with Postgres and Elasticsearch as service containers.

### Configuration

All backend settings are environment variables (see `backend/app/config.py`):

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `postgresql://openalex:openalex@localhost:5432/openalex` | Postgres connection |
| `ELASTICSEARCH_URL` | `http://localhost:9200` | Elasticsearch endpoint |
| `ES_INDEX_ALIAS` | `works` | Alias the API queries; indexes are `works_<timestamp>` |
| `OPENALEX_API_KEY` | – | Sent as `Authorization: Bearer …` to OpenAlex |
| `HARVEST_LIMIT` | `1000` | Works to harvest |
| `SNAPSHOT_PATH` | `data/works.jsonl.gz` | Snapshot written by `harvest`, read by `bootstrap` |
| `INSIGHTS_CACHE_SECONDS` | `300` | In-memory cache for `/api/insights` |

Compose additionally reads `WEB_PORT` (default `8080`) and `POSTGRES_PASSWORD` from `.env`.

---

## API

| Endpoint | Description |
|---|---|
| `GET /api/search` | `q`, `field` (`all\|title\|author\|country\|institution`), repeatable filters `author`, `institution`, `country` (ISO code), `concept`, `type`, `oa_status`, `date_from`, `date_to`, `sort` (`relevance\|newest\|oldest\|most_cited`), `page`, `size` (≤100). Returns hits (with highlights) and facet counts. |
| `GET /api/facets/{facet}` | Same filter parameters, plus `contains` (case-insensitive substring) and `limit`: used by "Show more / search …" in the filter panel. |
| `GET /api/works/{id}` | Full record from Postgres: abstract, every author with affiliations and countries, affiliation table, concepts, topics, citations, OA status, DOI and external links. |
| `GET /api/insights` | Aggregates for the Insights page (same SQL as `ANALYSIS.md`). |
| `GET /api/health` | 200 when Postgres and Elasticsearch are reachable (used by the container health check). |

---

## User interface

- **Search page:** search bar with a *Search in* selector; result cards with title, authors (query-matching authors highlighted, even author #45 of a consortium paper), date, type, venue, institutions (Danish first, with country flag and name), abstract snippet, concepts (click to filter), citations and OA status. The filter panel has facets for country, institution, author, concept, publication type and OA status (with counts and in-facet search), plus a publication date range. It also offers active filter chips, sorting, numbered pagination, and skeleton loading, empty and error states with retry.
- **Detail page:** abstract, the full author list with ORCID, corresponding author and affiliations with countries; an affiliation table (institution, country, number of authors, ROR link); citation count, percentile and FWCI; DOI and external links (publisher, PDF, OA copy, OpenAlex, other locations); concepts with scores, topics (domain › field › subfield), author countries, keywords and SDGs. Authors, institutions and concepts link to a filtered search.
- **Insights page:** key figures, the top 20 Danish authors, authors per country, the citation distribution, publications per month, top Danish institutions, research fields and OA status. Bars link into the search, and each chart has a table view.
- **Usability and accessibility:** responsive from phones (tested at 390 px) to desktop (filters collapse behind a button), light and dark mode, semantic landmarks and headings, a skip link, labelled controls, keyboard-operable everything, focus moved to the new content on navigation and paging, `aria-live` result counts, status shown with icon and text rather than colour alone, `prefers-reduced-motion` and `forced-colors` support.

| | | |
|---|---|---|
| ![Detail](docs/screenshots/detail.png) | ![Mobile](docs/screenshots/mobile.png) | ![Dark mode](docs/screenshots/search-dark.png) |

See also [the Insights page](docs/screenshots/insights.png).

---

## Deployment

The Compose file is the deployment unit; it runs unchanged on any single host with Docker.

**Single VM (e.g. a 2 vCPU / 4 GB VM on Azure, AWS, GCP or Hetzner):**

1. Install Docker; clone the repository; `cp .env.example .env` and set a strong `POSTGRES_PASSWORD` and the `OPENALEX_API_KEY`.
2. `docker compose up -d --build`.
3. **Manual step, TLS and domain:** point a DNS record at the VM and put a TLS-terminating reverse proxy in front of the `web` port (e.g. Caddy: `reverse_proxy localhost:8080` gets Let's Encrypt certificates automatically), or use the cloud load balancer. Firewall everything except 80/443.
4. **Manual step, Elasticsearch on Linux hosts:** set `vm.max_map_count=262144` (`sysctl -w vm.max_map_count=262144`, persisted in `/etc/sysctl.d/`), as Elastic recommends for production.
5. **Manual step, refresh schedule (optional):** a cron job / systemd timer running `docker compose run --rm pipeline python -m app.cli harvest --index` keeps the data current. The alias swap means users never see a half-built index.
6. **Backups:** `pg_dump` the `openalex` database (it is the source of truth; Elasticsearch can always be rebuilt with `python -m app.cli index`).

**Hardening before real production use:** enable Elasticsearch security (`xpack.security.enabled=true`, TLS, a dedicated user with read-only access for the API and write access for the indexer), remove the `127.0.0.1` port mappings for Postgres and Elasticsearch, use secrets management for passwords and the API key, add request rate-limiting at the proxy, and ship logs and metrics (`/api/health` is ready for uptime checks).

**Managed / container-platform alternative:** build and push the two images (`backend/`, `frontend/`) to a registry from CI, then run the API and web on a container platform (Azure Container Apps, Cloud Run, ECS), with managed PostgreSQL and Elastic Cloud (or OpenSearch Service, with minor client changes). Run the pipeline as a scheduled job on the same platform. Only configuration changes: `DATABASE_URL`, `ELASTICSEARCH_URL` (plus auth), and the nginx upstream for `/api`.

A public deployment was not set up as part of this exercise; the stack has been verified end-to-end locally with `docker compose up` from a clean state.

---

## Assumptions, limitations and ideas

**Assumptions**

- The assignment's query is used verbatim (`search=climate change`, `institutions.country_code:DK`, 2025). The first 1000 works in OpenAlex's relevance order are stored (5,048 matched at harvest time); `harvest_rank` preserves that order and is the tie-breaker for search ranking.
- "Concepts (topics)": OpenAlex has deprecated *concepts* in favour of *topics*. The UI shows and filters by concepts as the task specifies, and shows topics on the detail page. Concept tagging is noisy (e.g. "Event (particle physics)" on a climate-policy paper).
- "Danish author" (analysis) means an author linked to an institution whose `country_code` is `DK` on at least one harvested work. Authors are ranked by number of harvested works, ties broken by citations.
- Country of an affiliation comes from the institution's `country_code` (plus OpenAlex's per-authorship `countries`, which also covers unmatched affiliation strings).

**Limitations**

- Facets use display names (authors, institutions, concepts), so two different authors with the same name share a facet value. IDs are kept in both stores; an ID-keyed facet would fix this.
- The dataset is 1000 works, not the full 5,048; analysis numbers describe the harvested sample, which is biased towards the most relevant results.
- Re-harvesting upserts. If OpenAlex's ranking changes, works that drop out of the top 1000 stay in the database (there is no pruning yet).
- No authentication, rate-limiting or Elasticsearch security in the local setup (see Deployment).
- Citation counts are a snapshot from harvest time.

**Ideas**

- An author entity page (all their works, co-author network) and an institution page, keyed by OpenAlex IDs.
- Search-as-you-type suggestions (`search_as_you_type` / completion suggester) and "did you mean" spelling correction.
- Semantic search: embed title and abstract and use Elasticsearch kNN hybrid search for queries like "effects of warming on Arctic fish".
- A co-authorship map (countries collaborating with Denmark) and topic trends.
- Incremental harvests using `from_updated_date`, and pruning of works no longer in the result set.
- Playwright end-to-end tests in CI (the UI was verified with Playwright during development, but those scripts aren't committed as a suite).

---

## Repository layout

```
backend/            FastAPI app + data pipeline (one Python package, one Docker image)
  app/
    openalex.py     OpenAlex client (cursor paging, retries, truncated-author re-fetch)
    transform.py    raw work -> relational rows / search document (pure functions)
    schema.sql      Postgres schema
    db.py           schema + upserts
    es_index.py     Elasticsearch mapping, bulk indexing, alias swap
    search.py       query builder (facets, highlighting, sorting) + response shaping
    repository.py   detail-page SQL
    insights.py     analysis SQL (+ Markdown report)
    main.py         FastAPI routes
    cli.py          harvest | load-snapshot | index | bootstrap | analyze
  tests/            unit tests + API integration tests
frontend/           React + TypeScript (Vite), nginx config
data/works.jsonl.gz raw OpenAlex snapshot of the 1000 harvested works
docs/screenshots/   screenshots used in this README
ANALYSIS.md         generated analysis report
PROMPTS.md          record of AI-assisted development
docker-compose.yml  full stack
```
