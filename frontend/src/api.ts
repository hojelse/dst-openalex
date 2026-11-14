import { FACETS, type FacetName, type FacetValue, type Insights, type SearchResponse, type SearchState, type WorkDetail } from "./types";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  let resp: Response;
  try {
    resp = await fetch(path, { signal, headers: { Accept: "application/json" } });
  } catch (err) {
    if ((err as Error).name === "AbortError") throw err;
    throw new ApiError("Could not reach the server. Check your connection and try again.", 0);
  }
  if (!resp.ok) {
    let detail = `Request failed (${resp.status})`;
    try {
      const body = await resp.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(detail, resp.status);
  }
  return resp.json() as Promise<T>;
}

/** Query string shared by /api/search and /api/facets (everything except page/sort). */
export function filterParams(state: SearchState): URLSearchParams {
  const p = new URLSearchParams();
  if (state.q.trim()) p.set("q", state.q.trim());
  if (state.field !== "all") p.set("field", state.field);
  for (const facet of FACETS) for (const v of state.filters[facet]) p.append(facet, v);
  if (state.dateFrom) p.set("date_from", state.dateFrom);
  if (state.dateTo) p.set("date_to", state.dateTo);
  return p;
}

export function searchWorks(state: SearchState, pageSize: number, signal?: AbortSignal) {
  const p = filterParams(state);
  p.set("sort", state.sort);
  p.set("page", String(state.page));
  p.set("size", String(pageSize));
  return getJson<SearchResponse>(`/api/search?${p}`, signal);
}

export function facetValues(state: SearchState, facet: FacetName, contains: string, limit: number, signal?: AbortSignal) {
  const p = filterParams(state);
  if (contains.trim()) p.set("contains", contains.trim());
  p.set("limit", String(limit));
  return getJson<{ facet: FacetName; values: FacetValue[] }>(`/api/facets/${facet}?${p}`, signal);
}

export function getWork(id: string, signal?: AbortSignal) {
  return getJson<WorkDetail>(`/api/works/${encodeURIComponent(id)}`, signal);
}

export function getInsights(signal?: AbortSignal) {
  return getJson<Insights>("/api/insights", signal);
}
