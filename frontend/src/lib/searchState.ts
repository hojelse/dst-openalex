import { FACETS, SEARCH_FIELDS, SORTS, type FacetName, type SearchField, type SearchState, type SortOrder } from "../types";

/**
 * The search state lives in the URL, so every search is linkable/bookmarkable and the
 * browser back button works. These two functions are the only place that knows the
 * mapping between URL parameters and the state object.
 */
export function parseSearchState(params: URLSearchParams): SearchState {
  const field = params.get("field") as SearchField | null;
  const sort = params.get("sort") as SortOrder | null;
  const page = Number.parseInt(params.get("page") ?? "1", 10);
  const filters = Object.fromEntries(FACETS.map((f) => [f, params.getAll(f)])) as Record<FacetName, string[]>;
  return {
    q: params.get("q") ?? "",
    field: field && SEARCH_FIELDS.includes(field) ? field : "all",
    filters,
    dateFrom: params.get("date_from") ?? "",
    dateTo: params.get("date_to") ?? "",
    sort: sort && SORTS.includes(sort) ? sort : "relevance",
    page: Number.isFinite(page) && page > 0 ? page : 1,
  };
}

export function toSearchParams(state: SearchState): URLSearchParams {
  const p = new URLSearchParams();
  if (state.q) p.set("q", state.q);
  if (state.field !== "all") p.set("field", state.field);
  for (const f of FACETS) for (const v of state.filters[f]) p.append(f, v);
  if (state.dateFrom) p.set("date_from", state.dateFrom);
  if (state.dateTo) p.set("date_to", state.dateTo);
  if (state.sort !== "relevance") p.set("sort", state.sort);
  if (state.page > 1) p.set("page", String(state.page));
  return p;
}

export function activeFilterCount(state: SearchState): number {
  return FACETS.reduce((n, f) => n + state.filters[f].length, 0) + (state.dateFrom ? 1 : 0) + (state.dateTo ? 1 : 0);
}

export const emptyFilters = (): Record<FacetName, string[]> =>
  Object.fromEntries(FACETS.map((f) => [f, []])) as unknown as Record<FacetName, string[]>;
