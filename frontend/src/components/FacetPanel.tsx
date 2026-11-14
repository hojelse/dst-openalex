import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useEffect, useId, useState } from "react";
import { facetValues, filterParams } from "../api";
import { countryName, flag, formatNumber, oaLabel, typeLabel } from "../lib/format";
import type { FacetName, FacetValue, SearchState } from "../types";

interface FacetConfig {
  name: FacetName;
  label: string;
  plural: string;
  /** Show a text box to find values beyond the top few. */
  searchable: boolean;
  format?: (value: string) => string;
}

const FACET_CONFIG: FacetConfig[] = [
  { name: "country", label: "Country", plural: "countries", searchable: true, format: (v) => `${flag(v)} ${countryName(v)}`.trim() },
  { name: "institution", label: "Institution", plural: "institutions", searchable: true },
  { name: "author", label: "Author", plural: "authors", searchable: true },
  { name: "concept", label: "Concept", plural: "concepts", searchable: true },
  { name: "type", label: "Publication type", plural: "types", searchable: false, format: typeLabel },
  { name: "oa_status", label: "Open access", plural: "statuses", searchable: false, format: oaLabel },
];

const COLLAPSED = 6;

interface Props {
  state: SearchState;
  facets: Record<FacetName, FacetValue[]> | undefined;
  onToggle: (facet: FacetName, value: string) => void;
  onDates: (from: string, to: string) => void;
}

export function FacetPanel({ state, facets, onToggle, onDates }: Props) {
  return (
    <div className="facet-panel">
      {FACET_CONFIG.map((cfg) => (
        <FacetGroup
          key={cfg.name}
          config={cfg}
          state={state}
          values={facets?.[cfg.name] ?? []}
          selected={state.filters[cfg.name]}
          onToggle={(v) => onToggle(cfg.name, v)}
        />
      ))}
      <DateRange from={state.dateFrom} to={state.dateTo} onChange={onDates} />
    </div>
  );
}

function FacetGroup({
  config,
  state,
  values,
  selected,
  onToggle,
}: {
  config: FacetConfig;
  state: SearchState;
  values: FacetValue[];
  selected: string[];
  onToggle: (value: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [filterText, setFilterText] = useState("");
  const contains = useDebounced(filterText, 250);
  const listId = useId();
  const format = config.format ?? ((v: string) => v);

  // Expanded view: fetch more values (and search them server-side). Countries are
  // stored as codes, so their names are filtered client-side instead.
  const serverContains = config.name === "country" ? "" : contains;
  const more = useQuery({
    queryKey: ["facet", config.name, filterParams(state).toString(), serverContains],
    queryFn: ({ signal }) => facetValues(state, config.name, serverContains, config.name === "country" ? 200 : 50, signal),
    enabled: expanded,
    placeholderData: keepPreviousData,
  });

  let shown: FacetValue[] = expanded ? (more.data?.values ?? values) : values.slice(0, COLLAPSED);
  if (expanded && config.name === "country" && contains) {
    const needle = contains.toLowerCase();
    shown = shown.filter((v) => countryName(v.value).toLowerCase().includes(needle) || v.value.toLowerCase() === needle);
  }
  // Selected values always stay visible (checked), even when outside the current top list.
  const missing = selected.filter((s) => !shown.some((v) => v.value === s));
  const options = [...missing.map((value) => ({ value, count: null as number | null })), ...shown];

  if (values.length === 0 && selected.length === 0) {
    return (
      <fieldset className="facet">
        <legend className="facet-title">{config.label}</legend>
        <p className="facet-empty">No values for the current results.</p>
      </fieldset>
    );
  }

  return (
    <fieldset className="facet">
      <legend className="facet-title">
        {config.label}
        {selected.length > 0 && <span className="facet-selected-count"> · {selected.length} selected</span>}
      </legend>
      {expanded && config.searchable && (
        <div className="facet-search">
          <label htmlFor={`${listId}-q`} className="visually-hidden">
            Find {config.label.toLowerCase()}
          </label>
          <input
            id={`${listId}-q`}
            type="search"
            placeholder={`Find ${config.label.toLowerCase()}…`}
            value={filterText}
            onChange={(e) => setFilterText(e.target.value)}
            autoComplete="off"
          />
        </div>
      )}
      <ul id={listId} className={`facet-options${expanded ? " facet-options-expanded" : ""}`} aria-busy={more.isFetching}>
        {options.map((opt) => {
          const checked = selected.includes(opt.value);
          return (
            <li key={opt.value}>
              <label className="facet-option">
                <input type="checkbox" checked={checked} onChange={() => onToggle(opt.value)} />
                <span className="facet-label">{format(opt.value)}</span>
                {opt.count !== null && <span className="facet-count">{formatNumber(opt.count)}</span>}
              </label>
            </li>
          );
        })}
        {expanded && options.length === 0 && !more.isFetching && <li className="facet-empty">No matches.</li>}
      </ul>
      {more.isError && <p className="facet-empty">Could not load more values.</p>}
      {(values.length > COLLAPSED || expanded) && (
        <button
          type="button"
          className="link-button facet-more"
          aria-expanded={expanded}
          aria-controls={listId}
          onClick={() => {
            setExpanded((e) => !e);
            setFilterText("");
          }}
        >
          {expanded ? "Show fewer" : config.searchable ? `Show more / search ${config.plural}` : "Show all"}
        </button>
      )}
    </fieldset>
  );
}

function DateRange({ from, to, onChange }: { from: string; to: string; onChange: (from: string, to: string) => void }) {
  return (
    <fieldset className="facet">
      <legend className="facet-title">Publication date</legend>
      <div className="date-range">
        <label>
          <span>From</span>
          <input type="date" min="2025-01-01" max="2025-12-31" value={from} onChange={(e) => onChange(e.target.value, to)} />
        </label>
        <label>
          <span>To</span>
          <input type="date" min="2025-01-01" max="2025-12-31" value={to} onChange={(e) => onChange(from, e.target.value)} />
        </label>
      </div>
    </fieldset>
  );
}

function useDebounced<T>(value: T, ms: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return debounced;
}
