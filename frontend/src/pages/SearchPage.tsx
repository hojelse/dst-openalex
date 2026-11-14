import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router";
import { searchWorks } from "../api";
import { FacetPanel } from "../components/FacetPanel";
import { Pagination } from "../components/Pagination";
import { ResultCard } from "../components/ResultCard";
import { SearchBar } from "../components/SearchBar";
import { EmptyState, ErrorState, SkeletonResults } from "../components/States";
import { countryName, formatNumber, oaLabel, typeLabel } from "../lib/format";
import { activeFilterCount, emptyFilters, parseSearchState, toSearchParams } from "../lib/searchState";
import { useDocumentTitle } from "../lib/useDocumentTitle";
import { FACETS, type FacetName, type SearchField, type SearchState, type SortOrder } from "../types";

const PAGE_SIZE = 20;

const SORT_LABELS: Record<SortOrder, string> = {
  relevance: "Relevance",
  newest: "Newest first",
  oldest: "Oldest first",
  most_cited: "Most cited",
};

const FACET_LABELS: Record<FacetName, string> = {
  country: "Country",
  institution: "Institution",
  author: "Author",
  concept: "Concept",
  type: "Type",
  oa_status: "Access",
};

const EXAMPLES: { q: string; field: SearchField; label: string }[] = [
  { q: "sea level rise", field: "all", label: "sea level rise" },
  { q: "Svenning", field: "author", label: "Svenning (author)" },
  { q: "Kenya", field: "country", label: "Kenya (country)" },
  { q: '"heat stress"', field: "title", label: "“heat stress” (title)" },
];

export function SearchPage() {
  const [params, setParams] = useSearchParams();
  const state = useMemo(() => parseSearchState(params), [params]);
  const queryString = toSearchParams(state).toString();
  const [filtersOpen, setFiltersOpen] = useState(false);
  const resultsRef = useRef<HTMLHeadingElement>(null);

  useDocumentTitle(state.q ? `“${state.q}” – Search` : "Search");

  const search = useQuery({
    queryKey: ["search", queryString],
    queryFn: ({ signal }) => searchWorks(state, PAGE_SIZE, signal),
    placeholderData: keepPreviousData,
  });

  const update = (patch: Partial<SearchState>) => {
    // Any change other than paging starts again from page 1.
    setParams(toSearchParams({ ...state, page: 1, ...patch }));
  };
  const toggle = (facet: FacetName, value: string) => {
    const current = state.filters[facet];
    const next = current.includes(value) ? current.filter((v) => v !== value) : [...current, value];
    update({ filters: { ...state.filters, [facet]: next } });
  };
  const hrefFor = (page: number) => `?${toSearchParams({ ...state, page })}`;

  // Bring the top of the results into view when the page number changes.
  const lastPage = useRef(state.page);
  useEffect(() => {
    if (lastPage.current !== state.page) {
      resultsRef.current?.scrollIntoView({ block: "start" });
      resultsRef.current?.focus({ preventScroll: true });
    }
    lastPage.current = state.page;
  }, [state.page]);

  const data = search.data;
  const nFilters = activeFilterCount(state);
  const isUpdating = search.isFetching && search.isPlaceholderData;

  return (
    <div className="container">
      <section className="search-hero">
        <h1>Climate research from Danish institutions, 2025</h1>
        <p className="lede">
          Explore publications about climate change with at least one Danish affiliation, harvested from OpenAlex.
        </p>
        <SearchBar q={state.q} field={state.field} onSearch={(q, field) => update({ q, field })} />
        {!state.q && nFilters === 0 && (
          <p className="examples">
            Try:{" "}
            {EXAMPLES.map((ex, i) => (
              <span key={ex.label}>
                {i > 0 && " · "}
                <button type="button" className="link-button" onClick={() => update({ q: ex.q, field: ex.field })}>
                  {ex.label}
                </button>
              </span>
            ))}
          </p>
        )}
      </section>

      <div className="search-layout">
        <aside id="filters" className={`filters${filtersOpen ? " is-open" : ""}`} aria-label="Filters">
          <div className="filters-head">
            <h2>Filters</h2>
            {nFilters > 0 && (
              <button type="button" className="link-button" onClick={() => update({ filters: emptyFilters(), dateFrom: "", dateTo: "" })}>
                Clear all
              </button>
            )}
          </div>
          <FacetPanel
            state={state}
            facets={data?.facets}
            onToggle={toggle}
            onDates={(dateFrom, dateTo) => update({ dateFrom, dateTo })}
          />
        </aside>

        <section className="results" aria-labelledby="results-heading">
          <div className="results-toolbar">
            <h2 id="results-heading" ref={resultsRef} tabIndex={-1} aria-live="polite">
              {data ? (
                <>
                  {formatNumber(data.total)} {data.total === 1 ? "publication" : "publications"}
                  {data.total > 0 && data.pages > 1 && (
                    <span className="results-range">
                      {" "}
                      · page {formatNumber(data.page)} of {formatNumber(data.pages)}
                    </span>
                  )}
                </>
              ) : (
                "Publications"
              )}
            </h2>
            <div className="toolbar-controls">
              <button
                type="button"
                className="btn btn-secondary filters-toggle"
                aria-expanded={filtersOpen}
                aria-controls="filters"
                onClick={() => setFiltersOpen((o) => !o)}
              >
                Filters{nFilters > 0 && ` (${nFilters})`}
              </button>
              <label className="sort">
                <span>Sort by</span>
                <select value={state.sort} onChange={(e) => update({ sort: e.target.value as SortOrder })}>
                  {Object.entries(SORT_LABELS).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </div>

          <ActiveFilters state={state} onRemove={toggle} onClearDates={() => update({ dateFrom: "", dateTo: "" })} />

          {search.isError && !data ? (
            <ErrorState title="Search failed" error={search.error} onRetry={() => search.refetch()} />
          ) : !data ? (
            <SkeletonResults />
          ) : data.total === 0 ? (
            <EmptyState title="No publications match your search">
              <p className="state-text">Try fewer words, another field in “Search in”, or remove some filters.</p>
              {nFilters > 0 && (
                <button type="button" className="btn btn-secondary" onClick={() => update({ filters: emptyFilters(), dateFrom: "", dateTo: "" })}>
                  Clear all filters
                </button>
              )}
            </EmptyState>
          ) : (
            <>
              {search.isError && (
                <ErrorState title="Could not update results" error={search.error} onRetry={() => search.refetch()} />
              )}
              <ol className={`result-list${isUpdating ? " is-updating" : ""}`} aria-busy={isUpdating}>
                {data.results.map((r) => (
                  <ResultCard
                    key={r.id}
                    result={r}
                    from={queryString}
                    onConcept={(c) => !state.filters.concept.includes(c) && toggle("concept", c)}
                  />
                ))}
              </ol>
              <Pagination page={data.page} pages={data.pages} hrefFor={hrefFor} />
            </>
          )}
        </section>
      </div>
    </div>
  );
}

function ActiveFilters({
  state,
  onRemove,
  onClearDates,
}: {
  state: SearchState;
  onRemove: (facet: FacetName, value: string) => void;
  onClearDates: () => void;
}) {
  const label = (facet: FacetName, value: string) =>
    facet === "country" ? countryName(value) : facet === "type" ? typeLabel(value) : facet === "oa_status" ? oaLabel(value) : value;
  const chips = FACETS.flatMap((f) => state.filters[f].map((v) => ({ f, v })));
  if (chips.length === 0 && !state.dateFrom && !state.dateTo) return null;
  return (
    <ul className="active-filters" aria-label="Active filters">
      {chips.map(({ f, v }) => (
        <li key={`${f}:${v}`}>
          <button type="button" className="filter-chip" onClick={() => onRemove(f, v)} aria-label={`Remove filter ${FACET_LABELS[f]}: ${label(f, v)}`}>
            <span className="filter-chip-facet">{FACET_LABELS[f]}:</span> {label(f, v)} <span aria-hidden="true">×</span>
          </button>
        </li>
      ))}
      {(state.dateFrom || state.dateTo) && (
        <li>
          <button type="button" className="filter-chip" onClick={onClearDates} aria-label="Remove date filter">
            <span className="filter-chip-facet">Date:</span> {state.dateFrom || "…"} – {state.dateTo || "…"} <span aria-hidden="true">×</span>
          </button>
        </li>
      )}
    </ul>
  );
}
