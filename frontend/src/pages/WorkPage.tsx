import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router";
import { ApiError, getWork } from "../api";
import { CitationCount, OaBadge } from "../components/Badges";
import { ErrorState, Spinner } from "../components/States";
import { OA_DESCRIPTIONS, countryName, flag, formatDate, formatNumber, languageName, typeLabel } from "../lib/format";
import { useDocumentTitle } from "../lib/useDocumentTitle";
import type { WorkAuthor, WorkDetail } from "../types";

const AUTHORS_COLLAPSED = 25;

export function WorkPage() {
  const { id = "" } = useParams();
  const work = useQuery({ queryKey: ["work", id], queryFn: ({ signal }) => getWork(id, signal) });
  useDocumentTitle(work.data?.title ?? (work.isError ? "Publication not found" : "Publication"));

  return (
    <div className="container detail">
      <BackLink />
      {work.isPending ? (
        <Spinner label="Loading publication" />
      ) : work.isError ? (
        work.error instanceof ApiError && work.error.status === 404 ? (
          <ErrorState title="Publication not found" error={new Error(`There is no publication with id “${id}” in this collection.`)} />
        ) : (
          <ErrorState title="Could not load this publication" error={work.error} onRetry={() => work.refetch()} />
        )
      ) : (
        <WorkView work={work.data} />
      )}
    </div>
  );
}

function BackLink() {
  const location = useLocation();
  const navigate = useNavigate();
  const from = (location.state as { from?: string } | null)?.from;
  if (from !== undefined) {
    return (
      <a
        className="back-link"
        href={`/?${from}`}
        onClick={(e) => {
          e.preventDefault();
          navigate(-1); // real history back: keeps the results and their scroll position
        }}
      >
        ‹ Back to results
      </a>
    );
  }
  return (
    <Link className="back-link" to="/">
      ‹ Search all publications
    </Link>
  );
}

function WorkView({ work: w }: { work: WorkDetail }) {
  const biblio = [
    w.biblio?.volume && `Vol. ${w.biblio.volume}`,
    w.biblio?.issue && `Issue ${w.biblio.issue}`,
    w.biblio?.first_page && `pp. ${w.biblio.first_page}${w.biblio.last_page ? `–${w.biblio.last_page}` : ""}`,
  ].filter(Boolean);
  const countries = countryCounts(w.authors);

  return (
    <article className="work" aria-labelledby="work-title">
      <header className="work-header">
        <p className="eyebrow">
          {typeLabel(w.type)}
          {w.source.name && <> · {w.source.name}</>}
        </p>
        <h1 id="work-title">{w.title ?? "Untitled"}</h1>
        <p className="work-meta">
          Published <time dateTime={w.publication_date ?? undefined}>{formatDate(w.publication_date)}</time>
          {languageName(w.language) && <> · {languageName(w.language)}</>}
          {biblio.length > 0 && <> · {biblio.join(", ")}</>}
        </p>
        <div className="work-badges">
          <OaBadge status={w.open_access.status} isOa={w.open_access.is_oa} />
          <CitationCount count={w.cited_by_count} />
          {w.is_top_10_percent && <span className="badge badge-neutral">Top 10% cited (field &amp; year)</span>}
        </div>
      </header>

      <div className="work-grid">
        <div className="work-main">
          <section aria-labelledby="abstract-h" className="work-section">
            <h2 id="abstract-h">Abstract</h2>
            {w.abstract ? <p className="abstract">{w.abstract}</p> : <p className="muted">No abstract is available in OpenAlex for this publication.</p>}
          </section>

          <AuthorsSection authors={w.authors} />

          <section aria-labelledby="aff-h" className="work-section">
            <h2 id="aff-h">
              Affiliations <span className="count">({formatNumber(w.affiliations.length)})</span>
            </h2>
            {w.affiliations.length === 0 ? (
              <p className="muted">No institutions were matched for the authors of this publication.</p>
            ) : (
              <div className="table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th scope="col">Institution</th>
                      <th scope="col">Country</th>
                      <th scope="col" className="num">
                        Authors
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {w.affiliations.map((a) => (
                      <tr key={a.id}>
                        <td>
                          <Link to={`/?institution=${encodeURIComponent(a.name)}`}>{a.name}</Link>
                          {a.ror && (
                            <a className="ext-mini" href={a.ror} target="_blank" rel="noreferrer" aria-label={`${a.name} in the ROR registry (opens in new tab)`}>
                              ROR
                            </a>
                          )}
                        </td>
                        <td>
                          <span aria-hidden="true">{flag(a.country_code)} </span>
                          {a.country_name ?? countryName(a.country_code)}
                        </td>
                        <td className="num">{a.author_count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </div>

        <aside className="work-side" aria-label="Publication facts">
          <section className="card" aria-labelledby="links-h">
            <h2 id="links-h">Access &amp; links</h2>
            <p className="oa-line">
              <OaBadge status={w.open_access.status} isOa={w.open_access.is_oa} />
            </p>
            {w.open_access.status && OA_DESCRIPTIONS[w.open_access.status] && (
              <p className="muted small">{OA_DESCRIPTIONS[w.open_access.status]}.</p>
            )}
            {w.doi && (
              <p className="doi">
                <span className="label">DOI</span>{" "}
                <a href={`https://doi.org/${w.doi}`} target="_blank" rel="noreferrer">
                  {w.doi}
                </a>
              </p>
            )}
            <ul className="link-list">
              {w.links.map((l) => (
                <li key={l.url}>
                  <a href={l.url} target="_blank" rel="noreferrer">
                    {l.label}
                    <span className="visually-hidden"> (opens in new tab)</span>
                    <svg viewBox="0 0 16 16" aria-hidden="true" className="ext-icon">
                      <path d="M9 3h4v4M13 3 7 9M11 9v4H3V5h4" />
                    </svg>
                  </a>
                </li>
              ))}
            </ul>
            {w.locations.length > 1 && (
              <details className="locations">
                <summary>Also available at {w.locations.length - 1} other locations</summary>
                <ul>
                  {w.locations.slice(1).map((loc) => (
                    <li key={loc.url}>
                      <a href={loc.url} target="_blank" rel="noreferrer">
                        {loc.source ?? new URL(loc.url).hostname}
                      </a>
                      {loc.is_oa && <span className="muted small"> · free to read</span>}
                    </li>
                  ))}
                </ul>
              </details>
            )}
          </section>

          <section className="card" aria-labelledby="cite-h">
            <h2 id="cite-h">Citations</h2>
            <p className="big-number">{formatNumber(w.cited_by_count)}</p>
            <dl className="facts">
              {w.citation_percentile !== null && (
                <>
                  <dt>Percentile (same field &amp; year)</dt>
                  <dd>{ordinal(Math.min(99, Math.floor(w.citation_percentile * 100)))}</dd>
                </>
              )}
              {w.fwci !== null && (
                <>
                  <dt title="Field-weighted citation impact: 1.0 = world average">FWCI</dt>
                  <dd>{w.fwci.toFixed(2)}</dd>
                </>
              )}
              {w.referenced_works_count !== null && (
                <>
                  <dt>References</dt>
                  <dd>{formatNumber(w.referenced_works_count)}</dd>
                </>
              )}
            </dl>
            {w.counts_by_year.length > 0 && (
              <p className="muted small">
                By year: {w.counts_by_year.map((c) => `${c.year}: ${formatNumber(c.cited_by_count)}`).join(" · ")}
              </p>
            )}
          </section>

          <section className="card" aria-labelledby="concepts-h">
            <h2 id="concepts-h">Concepts</h2>
            {w.concepts.length === 0 ? (
              <p className="muted">None assigned.</p>
            ) : (
              <ul className="concept-list">
                {w.concepts.map((c) => (
                  <li key={c.id}>
                    <Link to={`/?concept=${encodeURIComponent(c.name)}`}>{c.name}</Link>
                    {c.score !== null && (
                      <span className="score" aria-label={`relevance score ${Math.round(c.score * 100)} percent`}>
                        <span className="score-bar" aria-hidden="true">
                          <span style={{ width: `${Math.round(c.score * 100)}%` }} />
                        </span>
                        <span aria-hidden="true">{Math.round(c.score * 100)}</span>
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </section>

          {w.topics.length > 0 && (
            <section className="card" aria-labelledby="topics-h">
              <h2 id="topics-h">Topics</h2>
              <ul className="topic-list">
                {w.topics.map((t) => (
                  <li key={t.id}>
                    <span className="topic-name">
                      {t.name}
                      {t.is_primary && <span className="badge badge-neutral small-badge">Primary</span>}
                    </span>
                    <span className="muted small">
                      {[t.domain, t.field, t.subfield].filter(Boolean).join(" › ")}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {countries.length > 0 && (
            <section className="card" aria-labelledby="countries-h">
              <h2 id="countries-h">Author countries</h2>
              <ul className="country-list">
                {countries.map((c) => (
                  <li key={c.code}>
                    <span aria-hidden="true">{flag(c.code)}</span> {c.name}
                    <span className="muted"> · {c.count} {c.count === 1 ? "author" : "authors"}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {(w.keywords.length > 0 || w.sdgs.length > 0) && (
            <section className="card" aria-labelledby="kw-h">
              <h2 id="kw-h">Keywords &amp; SDGs</h2>
              <ul className="chips">
                {w.keywords.map((k) => (
                  <li key={k}>
                    <span className="chip chip-static">{k}</span>
                  </li>
                ))}
                {w.sdgs.map((s) => (
                  <li key={s}>
                    <span className="chip chip-static chip-sdg">SDG: {s}</span>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </aside>
      </div>
    </article>
  );
}

function AuthorsSection({ authors }: { authors: WorkAuthor[] }) {
  const [showAll, setShowAll] = useState(false);
  const shown = showAll ? authors : authors.slice(0, AUTHORS_COLLAPSED);
  return (
    <section aria-labelledby="authors-h" className="work-section">
      <h2 id="authors-h">
        Authors <span className="count">({formatNumber(authors.length)})</span>
      </h2>
      <ol className="author-list">
        {shown.map((a) => (
          <li key={a.position} className="author">
            <div className="author-name">
              <span className="author-pos" aria-hidden="true">
                {a.position}
              </span>
              <Link to={`/?author=${encodeURIComponent(a.name)}`} title={`Search publications by ${a.name}`}>
                {a.name}
              </Link>
              {a.orcid && (
                <a className="ext-mini orcid" href={a.orcid} target="_blank" rel="noreferrer" aria-label={`ORCID profile of ${a.name} (opens in new tab)`}>
                  ORCID
                </a>
              )}
              {a.is_corresponding && <span className="badge badge-neutral small-badge">Corresponding</span>}
            </div>
            {a.institutions.length > 0 ? (
              <ul className="author-affs">
                {a.institutions.map((i) => (
                  <li key={i.id}>
                    {i.name}
                    <span className="muted">
                      {" "}
                      · <span aria-hidden="true">{flag(i.country_code)} </span>
                      {i.country_name ?? countryName(i.country_code)}
                    </span>
                  </li>
                ))}
              </ul>
            ) : a.raw_affiliations.length > 0 ? (
              <ul className="author-affs">
                {a.raw_affiliations.map((r) => (
                  <li key={r}>
                    {r} <span className="muted small">(unmatched affiliation text)</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="author-affs muted small">No affiliation recorded</p>
            )}
          </li>
        ))}
      </ol>
      {authors.length > AUTHORS_COLLAPSED && (
        <button type="button" className="btn btn-secondary" onClick={() => setShowAll((s) => !s)} aria-expanded={showAll}>
          {showAll ? "Show fewer authors" : `Show all ${formatNumber(authors.length)} authors`}
        </button>
      )}
    </section>
  );
}

function ordinal(n: number) {
  const suffix = n % 100 >= 11 && n % 100 <= 13 ? "th" : ({ 1: "st", 2: "nd", 3: "rd" } as Record<number, string>)[n % 10] ?? "th";
  return `${n}${suffix}`;
}

function countryCounts(authors: WorkAuthor[]) {
  const counts = new Map<string, { code: string; name: string; count: number }>();
  for (const a of authors) {
    for (const c of a.countries) {
      const entry = counts.get(c.code) ?? { code: c.code, name: c.name, count: 0 };
      entry.count += 1;
      counts.set(c.code, entry);
    }
  }
  return [...counts.values()].sort((a, b) => b.count - a.count || a.name.localeCompare(b.name));
}
