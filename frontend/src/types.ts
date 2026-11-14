// Mirrors the JSON returned by the FastAPI backend (see backend/app/search.py,
// repository.py and insights.py).

export const FACETS = ["country", "institution", "author", "concept", "type", "oa_status"] as const;
export type FacetName = (typeof FACETS)[number];

export const SEARCH_FIELDS = ["all", "title", "author", "country", "institution"] as const;
export type SearchField = (typeof SEARCH_FIELDS)[number];

export const SORTS = ["relevance", "newest", "oldest", "most_cited"] as const;
export type SortOrder = (typeof SORTS)[number];

export interface SearchState {
  q: string;
  field: SearchField;
  filters: Record<FacetName, string[]>;
  dateFrom: string;
  dateTo: string;
  sort: SortOrder;
  page: number;
}

export interface FacetValue {
  value: string;
  count: number;
}

export interface ResultAuthor {
  id: string | null;
  name: string;
  position: number;
  matched: boolean;
}

export interface SearchResult {
  id: string;
  title: string | null;
  title_highlight: string | null;
  snippet: string | null;
  publication_date: string | null;
  type: string | null;
  source: string | null;
  doi: string | null;
  cited_by_count: number;
  is_oa: boolean;
  oa_status: string | null;
  author_count: number;
  authors: ResultAuthor[];
  institution_count: number;
  institutions: { name: string; country_code: string | null }[];
  countries: string[];
  concepts: string[];
}

export interface SearchResponse {
  total: number;
  page: number;
  size: number;
  pages: number;
  took_ms: number | null;
  results: SearchResult[];
  facets: Record<FacetName, FacetValue[]>;
}

export interface Institution {
  id: string;
  name: string;
  ror: string | null;
  country_code: string | null;
  country_name: string | null;
  type: string | null;
}

export interface WorkAuthor {
  position: number;
  id: string | null;
  name: string;
  orcid: string | null;
  role: string | null;
  is_corresponding: boolean;
  raw_affiliations: string[];
  institutions: Institution[];
  countries: { code: string; name: string }[];
}

export interface WorkDetail {
  id: string;
  openalex_url: string;
  doi: string | null;
  title: string | null;
  abstract: string | null;
  publication_date: string | null;
  publication_year: number | null;
  type: string | null;
  language: string | null;
  source: {
    name: string | null;
    type: string | null;
    landing_page_url: string | null;
    license: string | null;
    version: string | null;
  };
  biblio: { volume?: string | null; issue?: string | null; first_page?: string | null; last_page?: string | null } | null;
  cited_by_count: number;
  citation_percentile: number | null;
  is_top_10_percent: boolean | null;
  fwci: number | null;
  referenced_works_count: number | null;
  counts_by_year: { year: number; cited_by_count: number }[];
  open_access: { is_oa: boolean; status: string | null; url: string | null };
  authors: WorkAuthor[];
  affiliations: (Institution & { author_count: number })[];
  concepts: { id: string; name: string; level: number | null; wikidata: string | null; score: number | null }[];
  topics: {
    id: string;
    name: string;
    subfield: string | null;
    field: string | null;
    domain: string | null;
    score: number | null;
    is_primary: boolean;
  }[];
  keywords: string[];
  sdgs: string[];
  links: { label: string; url: string }[];
  locations: {
    source: string | null;
    url: string;
    pdf_url: string | null;
    is_oa: boolean;
    version: string | null;
    license: string | null;
  }[];
  harvested_at: string;
}

export interface Insights {
  summary: {
    works: number;
    authors: number;
    danish_authors: number;
    institutions: number;
    countries: number;
    citations: number;
    oa_share: number;
    first_date: string | null;
    last_date: string | null;
    harvested_at: string | null;
  };
  top_danish_authors: {
    id: string;
    name: string;
    orcid: string | null;
    works: number;
    citations: number;
    tied_with: number;
    affiliations: { id: string; name: string; country_code: string | null; is_danish: boolean; works: number }[];
  }[];
  author_countries: { code: string; name: string; authors: number }[];
  authors_without_country: number;
  citations: {
    histogram: { bin: string; works: number }[];
    mean: number;
    median: number;
    p90: number;
    max: number;
    uncited_share: number;
  };
  works_by_month: { month: string; works: number }[];
  oa_status: { status: string; works: number }[];
  top_danish_institutions: { id: string; name: string; works: number }[];
  international_collaboration: { international: number; total: number; share: number };
  top_fields: { name: string; works: number }[];
}
