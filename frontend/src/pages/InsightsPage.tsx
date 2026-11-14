import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { getInsights } from "../api";
import { ColumnChart, HBarChart } from "../components/BarChart";
import { ErrorState, Spinner } from "../components/States";
import { countryName, flag, formatCompact, formatMonth, formatNumber, formatPercent, oaLabel } from "../lib/format";
import { useDocumentTitle } from "../lib/useDocumentTitle";
import type { Insights } from "../types";

const q = (key: string, value: string) => `/?${new URLSearchParams({ [key]: value })}`;

export function InsightsPage() {
  useDocumentTitle("Insights");
  const insights = useQuery({ queryKey: ["insights"], queryFn: ({ signal }) => getInsights(signal) });

  return (
    <div className="container insights">
      <header className="page-header">
        <h1>Insights</h1>
        <p className="lede">
          What the harvested publications reveal about who does Danish climate research and with whom. Computed with SQL over
          the Postgres database; details in <code>ANALYSIS.md</code>.
        </p>
      </header>
      {insights.isPending ? (
        <Spinner label="Loading insights" />
      ) : insights.isError ? (
        <ErrorState title="Could not load insights" error={insights.error} onRetry={() => insights.refetch()} />
      ) : (
        <InsightsView data={insights.data} />
      )}
    </div>
  );
}

function InsightsView({ data }: { data: Insights }) {
  const s = data.summary;
  const topCountries = data.author_countries.slice(0, 20);
  const otherCountries = data.author_countries.slice(20);

  return (
    <>
      <section aria-label="Key figures" className="stat-grid">
        <Stat label="Publications" value={formatNumber(s.works)} note={`${formatDate(s.first_date)} – ${formatDate(s.last_date)}`} />
        <Stat label="Authors" value={formatCompact(s.authors)} note={`${formatNumber(s.danish_authors)} with a Danish affiliation`} />
        <Stat label="Institutions" value={formatCompact(s.institutions)} note={`in ${s.countries} countries`} />
        <Stat label="Open access" value={formatPercent(s.oa_share)} note="of publications free to read" />
        <Stat
          label="International"
          value={formatPercent(data.international_collaboration.share)}
          note="have co-authors outside Denmark"
        />
        <Stat label="Citations" value={formatCompact(s.citations)} note={`median ${data.citations.median} per publication`} />
      </section>

      <section className="panel" aria-labelledby="top-authors-h">
        <h2 id="top-authors-h">Top 20 Danish authors</h2>
        <p className="panel-note">
          A Danish author has at least one affiliation with a Danish institution. Ranked by number of harvested publications,
          ties broken by citations. Affiliations show every institution linked to the author in this dataset, with publication counts.
        </p>
        <div className="table-wrap">
          <table className="data-table top-authors">
            <thead>
              <tr>
                <th scope="col" className="num">
                  #
                </th>
                <th scope="col">Author</th>
                <th scope="col" className="num">
                  Publications
                </th>
                <th scope="col" className="num">
                  Citations
                </th>
                <th scope="col">Affiliations</th>
              </tr>
            </thead>
            <tbody>
              {data.top_danish_authors.map((a, i) => (
                <tr key={a.id}>
                  <td className="num muted">{i + 1}</td>
                  <th scope="row">
                    <Link to={q("author", a.name)}>{a.name}</Link>
                    {a.orcid && (
                      <a className="ext-mini orcid" href={a.orcid} target="_blank" rel="noreferrer" aria-label={`ORCID profile of ${a.name} (opens in new tab)`}>
                        ORCID
                      </a>
                    )}
                  </th>
                  <td className="num">{a.works}</td>
                  <td className="num">{formatNumber(a.citations)}</td>
                  <td>
                    <ul className="aff-inline">
                      {(a.affiliations ?? []).map((aff) => (
                        <li key={aff.id} className={aff.is_danish ? "" : "muted"}>
                          <span aria-hidden="true">{flag(aff.country_code)} </span>
                          {aff.name} <span className="aff-count">({aff.works})</span>
                        </li>
                      ))}
                    </ul>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {data.top_danish_authors.length > 0 && (
          <p className="panel-note">
            {data.top_danish_authors.at(-1)!.tied_with} Danish authors have exactly {data.top_danish_authors.at(-1)!.works} publications, so the
            last places depend on the citation tie-breaker.
          </p>
        )}
      </section>

      <div className="panel-grid">
        <section className="panel" aria-labelledby="countries-h">
          <h2 id="countries-h">Authors by country of affiliation</h2>
          <p className="panel-note">
            Distinct authors per country; an author with affiliations in several countries counts once in each. Top 20 of{" "}
            {data.author_countries.length} countries
            {otherCountries.length > 0 &&
              ` (the other ${otherCountries.length} add ${formatNumber(otherCountries.reduce((n, c) => n + c.authors, 0))})`}
            ; {formatNumber(data.authors_without_country)} authors have no country.
          </p>
          <HBarChart
            data={topCountries.map((c) => ({
              key: c.code,
              label: `${flag(c.code)} ${countryName(c.code)}`,
              value: c.authors,
              to: q("country", c.code),
            }))}
            unit="authors"
            labelHeader="Country"
            caption="Number of distinct authors per country of affiliation, top 20 countries"
          />
        </section>

        <section className="panel" aria-labelledby="citations-h">
          <h2 id="citations-h">Citations per publication</h2>
          <p className="panel-note">
            Heavily skewed, as expected for papers published in 2025: {formatPercent(data.citations.uncited_share)} are not cited yet,
            the median is {data.citations.median}, the mean {data.citations.mean.toFixed(1)} and the most cited has{" "}
            {formatNumber(data.citations.max)}. Bins widen to the right.
          </p>
          <ColumnChart
            data={data.citations.histogram.map((b) => ({ key: b.bin, label: b.bin, value: b.works }))}
            unit="publications"
            labelHeader="Citations"
            caption="Number of publications by citation count"
          />
          <p className="panel-link">
            <Link to="/?sort=most_cited">See the most cited publications ›</Link>
          </p>
        </section>

        <section className="panel" aria-labelledby="month-h">
          <h2 id="month-h">Publications per month (2025)</h2>
          <p className="panel-note">
            January is inflated: OpenAlex dates records it only knows the year of as 1 January, which accounts for most of that
            month.
          </p>
          <ColumnChart
            data={data.works_by_month.map((m) => ({ key: m.month, label: formatMonth(m.month), value: m.works }))}
            unit="publications"
            labelHeader="Month"
            caption="Number of publications per publication month in 2025"
          />
        </section>

        <section className="panel" aria-labelledby="inst-h">
          <h2 id="inst-h">Most active Danish institutions</h2>
          <HBarChart
            data={data.top_danish_institutions.map((i) => ({ key: i.id, label: i.name, value: i.works, to: q("institution", i.name) }))}
            unit="publications"
            labelHeader="Institution"
            caption="Publications per Danish institution, top 15"
          />
        </section>

        <section className="panel" aria-labelledby="fields-h">
          <h2 id="fields-h">Research field (primary topic)</h2>
          <HBarChart
            data={data.top_fields.map((f) => ({ key: f.name, label: f.name, value: f.works }))}
            unit="publications"
            labelHeader="Field"
            caption="Publications per research field of their primary topic"
          />
        </section>

        <section className="panel" aria-labelledby="oa-h">
          <h2 id="oa-h">Open access status</h2>
          <HBarChart
            data={data.oa_status.map((o) => ({ key: o.status, label: oaLabel(o.status), value: o.works, to: q("oa_status", o.status) }))}
            unit="publications"
            labelHeader="Status"
            caption="Publications per open access status"
          />
        </section>
      </div>
    </>
  );
}

function Stat({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="stat">
      <p className="stat-label">{label}</p>
      <p className="stat-value">{value}</p>
      {note && <p className="stat-note">{note}</p>}
    </div>
  );
}

function formatDate(iso: string | null) {
  if (!iso) return "?";
  return new Date(`${iso}T00:00:00`).toLocaleDateString("en-GB", { day: "numeric", month: "short" });
}
