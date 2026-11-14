import { useEffect, useState } from "react";
import type { SearchField } from "../types";

const FIELD_LABELS: Record<SearchField, string> = {
  all: "All fields",
  title: "Title",
  author: "Author",
  country: "Country",
  institution: "Institution",
};

const PLACEHOLDERS: Record<SearchField, string> = {
  all: "Search titles, abstracts, authors, institutions, countries…",
  title: "Words in the title, e.g. sea level rise",
  author: "Author name, e.g. Svenning",
  country: "Country name or code, e.g. Kenya or KE",
  institution: "Institution, e.g. Aarhus University",
};

interface Props {
  q: string;
  field: SearchField;
  onSearch: (q: string, field: SearchField) => void;
}

export function SearchBar({ q, field, onSearch }: Props) {
  const [text, setText] = useState(q);
  // Keep the input in sync when the URL changes (back button, chip removal, examples).
  useEffect(() => setText(q), [q]);

  return (
    <form
      className="search-bar"
      role="search"
      onSubmit={(e) => {
        e.preventDefault();
        onSearch(text.trim(), field);
      }}
    >
      <label htmlFor="search-field" className="visually-hidden">
        Search in
      </label>
      <select
        id="search-field"
        className="search-field"
        value={field}
        onChange={(e) => onSearch(text.trim(), e.target.value as SearchField)}
      >
        {Object.entries(FIELD_LABELS).map(([value, label]) => (
          <option key={value} value={value}>
            {label}
          </option>
        ))}
      </select>
      <div className="search-input-wrap">
        <label htmlFor="search-input" className="visually-hidden">
          Search publications
        </label>
        <input
          id="search-input"
          className="search-input"
          type="search"
          value={text}
          placeholder={PLACEHOLDERS[field]}
          onChange={(e) => setText(e.target.value)}
          autoComplete="off"
          spellCheck={false}
        />
        {text && (
          <button
            type="button"
            className="search-clear"
            aria-label="Clear search text"
            onClick={() => {
              setText("");
              onSearch("", field);
            }}
          >
            ×
          </button>
        )}
      </div>
      <button type="submit" className="btn btn-primary search-submit">
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="10.5" cy="10.5" r="6.5" />
          <path d="M15.5 15.5 21 21" />
        </svg>
        <span>Search</span>
      </button>
    </form>
  );
}
