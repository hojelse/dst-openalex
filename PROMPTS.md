# AI usage record

This solution was developed with **Claude Code** (Anthropic's agentic coding tool) running in a cloud session with this repository checked out. Claude Code read the assignment PDF, made the technical decisions, wrote the code, ran it against real services (Postgres, Elasticsearch and the live OpenAlex API in Docker), and verified the result with automated tests and browser screenshots.

## Prompts

The session was driven by very few prompts. Everything else was the agent working autonomously from the assignment text.

1. **The assignment itself:** the `Test Case - Fullstack position.pdf` file was attached with no additional instructions. Claude Code took the PDF's task list as the specification.
2. **Network and credentials:** the first OpenAlex request was blocked by the sandbox network policy. Claude Code proposed a cloud environment allowing `api.openalex.org` and the Docker/Elastic registries, which was approved. OpenAlex then returned *"Rate limit exceeded – insufficient budget… use your own key"*, so Claude Code asked for an OpenAlex API key through the session's secure credential form (the key is never visible to the model; the network proxy injects it). The first credential form was declined; the follow-up prompt was:
   > please reprompt for token

## What was delegated to the AI

Everything: requirements analysis, architecture, the harvester, database schema, Elasticsearch mapping and queries, API, React UI, Docker setup, tests, the analysis and the documentation. In the agent's planning:

- **Technology choices.** Elasticsearch, the preferred Option A. PostgreSQL as the system of record, chosen over SQLite so the analysis SQL and the deployment story are realistic. FastAPI and React with TypeScript as suggested. Hand-built accessible HTML/CSS bar charts instead of a chart library, to control mark styling, dark mode and table fallbacks.
- **Scope management.** The 2–3 hour guideline was treated as "keep it small but production-minded": one Python package and one image for both API and pipeline; no auth; a committed data snapshot so reviewers don't need an API key.

## How the output was evaluated, tested and verified

The agent did not trust its own code; each layer was run against real data before moving on:

| Check | What it caught or confirmed |
|---|---|
| Harvested 1000 real works, then queried Postgres for row counts and the maximum number of authors per work | **Every large paper had exactly 100 authors**, an OpenAlex list-endpoint truncation. Confirmed against the single-work endpoint (209 authors) and fixed by re-fetching those works (6 papers, up to 310 authors). |
| Looked at authorships with a `NULL` author ID | 569 unresolved authors; the decision was to keep them by name and exclude them from distinct-author counts (documented). |
| Ran the analysis SQL and read the output | Plausible results (Svenning, Sovacool, Jeppesen at the top; DK > US > GB > DE in author countries). Added a tie-count note, since 17 authors share 5 publications. |
| Exercised every API endpoint with `curl`/Python, including edge cases | Accent folding (`Soren` → `Søren`), country by name and code, disjunctive facet counts, phrase queries, malformed query syntax (no 500), invalid sort/page/facet (422), unknown and malicious IDs (404). Caught a Python bug where a dataclass field named `field` shadowed `dataclasses.field`. |
| **33 pytest tests:** unit tests for transforms, the query builder and the OpenAlex client (mocked HTTP: paging, retries, budget exhaustion, truncated-author re-fetch); 10 integration tests against live Postgres + Elasticsearch | All passing; `ruff` clean. |
| **7 Vitest tests** (URL-state round-trip, pagination, axis ticks) + `tsc --strict` | All passing. |
| **Playwright screenshots** of every page at desktop, mobile (390 px) and dark mode, inspected visually | The **mobile search bar collapsed the input to zero width** (flex-basis-0 item wrapping onto the select's row); fixed with a grid. Abstracts beginning with a literal **"Abstract"** heading (190 records); stripped in the transform. **"search countrys"** plural typo. A **"100th" percentile** rounding display. The y-axis label crowding a chart heading. A **January spike** traced to OpenAlex's 1 January placeholder dates (108 works); now explained in the UI and the analysis. |
| **Playwright click-through flows** (search → detail → back → facet → chip removal → pagination → skip link) | Found that in development the **skip link was skipped**: React StrictMode runs effects twice, which defeated a "first render" guard and moved focus to `<main>` on load. Fixed by comparing paths instead. Also confirmed focus moves to the results heading on page change. |
| `docker compose up` from an empty state, then the integration tests and screenshots against the nginx-served production build | Whole stack healthy; bootstrap seeds and indexes once and is idempotent on restart; SPA deep links work through nginx. (Inside the sandbox, image builds needed the proxy's CA certificate. That was handled with throwaway Dockerfile copies outside the repo, so the committed Dockerfiles are standard.) |

## Parts modified or developed by hand

None: all code and text in the repository was generated by the AI agent in this session and then iterated on by the agent based on the test and screenshot findings above. The candidate's role was to supply the assignment and credentials, approve the network/environment changes, and review the result.
