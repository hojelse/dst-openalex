import { Fragment } from "react";
import { Link } from "react-router";
import { countryName, flag, formatDate, typeLabel } from "../lib/format";
import { Highlight } from "../lib/highlight";
import type { SearchResult } from "../types";
import { CitationCount, OaBadge } from "./Badges";

interface Props {
  result: SearchResult;
  /** Current search query string, so the detail page can link back to these results. */
  from: string;
  onConcept: (concept: string) => void;
}

export function ResultCard({ result: r, from, onConcept }: Props) {
  const titleId = `title-${r.id}`;
  const moreAuthors = r.author_count - r.authors.length;
  const moreInstitutions = r.institution_count - r.institutions.length;

  return (
    <li className="result">
      <article aria-labelledby={titleId}>
        <h3 className="result-title" id={titleId}>
          <Link to={`/works/${r.id}`} state={{ from }}>
            {r.title_highlight ? <Highlight text={r.title_highlight} /> : (r.title ?? "Untitled")}
          </Link>
        </h3>

        <p className="result-meta">
          <time dateTime={r.publication_date ?? undefined}>{formatDate(r.publication_date)}</time>
          <span aria-hidden="true"> · </span>
          <span>{typeLabel(r.type)}</span>
          {r.source && (
            <>
              <span aria-hidden="true"> · </span>
              <span className="result-source">{r.source}</span>
            </>
          )}
        </p>

        {r.authors.length > 0 && (
          <p className="result-authors">
            <span className="visually-hidden">Authors: </span>
            {r.authors.map((a, i) => {
              const prev = r.authors[i - 1];
              const gap = prev && a.position - prev.position > 1;
              return (
                <Fragment key={`${a.position}`}>
                  {i > 0 && (gap ? " … " : ", ")}
                  {a.matched ? <mark>{a.name}</mark> : a.name}
                </Fragment>
              );
            })}
            {moreAuthors > 0 && <span className="muted"> +{moreAuthors} more</span>}
          </p>
        )}

        {r.institutions.length > 0 && (
          <p className="result-institutions">
            <span className="visually-hidden">Institutions: </span>
            {r.institutions.map((inst, i) => (
              <Fragment key={inst.name}>
                {i > 0 && "; "}
                <span>
                  {inst.name}
                  {inst.country_code && (
                    <span className="country-inline" title={countryName(inst.country_code)}>
                      {" "}
                      <span aria-hidden="true">{flag(inst.country_code)}</span>
                      <span className="visually-hidden">({countryName(inst.country_code)})</span>
                    </span>
                  )}
                </span>
              </Fragment>
            ))}
            {moreInstitutions > 0 && <span className="muted"> +{moreInstitutions} more</span>}
          </p>
        )}

        {r.snippet && (
          <p className="result-snippet">
            <Highlight text={r.snippet} />…
          </p>
        )}

        <div className="result-footer">
          {r.concepts.length > 0 && (
            <ul className="chips" aria-label="Concepts">
              {r.concepts.map((c) => (
                <li key={c}>
                  <button type="button" className="chip" onClick={() => onConcept(c)} title={`Filter by concept: ${c}`}>
                    {c}
                  </button>
                </li>
              ))}
            </ul>
          )}
          <div className="result-stats">
            <CitationCount count={r.cited_by_count} />
            <OaBadge status={r.oa_status} isOa={r.is_oa} />
          </div>
        </div>
      </article>
    </li>
  );
}
