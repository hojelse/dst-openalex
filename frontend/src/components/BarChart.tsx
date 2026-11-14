import { Link } from "react-router";
import { formatNumber } from "../lib/format";

export interface Datum {
  key: string;
  label: string;
  value: number;
  /** Optional link (e.g. to a filtered search) for the label. */
  to?: string;
}

interface Props {
  data: Datum[];
  /** Unit for tooltips and the table header, e.g. "authors". */
  unit: string;
  /** Column header for the label column of the table view. */
  labelHeader: string;
  /** Accessible description of the chart. */
  caption: string;
}

/** Horizontal bars with labels and values printed: readable without hover or colour. */
export function HBarChart({ data, unit, labelHeader, caption }: Props) {
  const max = Math.max(1, ...data.map((d) => d.value));
  const total = data.reduce((s, d) => s + d.value, 0);
  return (
    <figure className="chart">
      <ul className="hbar-list" aria-label={caption}>
        {data.map((d) => (
          <li className="hbar-row" key={d.key}>
            <span className="hbar-label">{d.to ? <Link to={d.to}>{d.label}</Link> : d.label}</span>
            <span className="hbar-track" aria-hidden="true">
              <span className="hbar-bar" style={{ width: `${(d.value / max) * 100}%` }} />
            </span>
            <span className="hbar-value">
              {formatNumber(d.value)}
              <span className="visually-hidden"> {unit}</span>
            </span>
          </li>
        ))}
      </ul>
      <TableView data={data} unit={unit} labelHeader={labelHeader} caption={caption} total={total} />
    </figure>
  );
}

/** Columns with a hover/focus tooltip per mark; only the tallest column is labelled. */
export function ColumnChart({ data, unit, labelHeader, caption, height = 200 }: Props & { height?: number }) {
  const max = Math.max(1, ...data.map((d) => d.value));
  const ticks = niceTicks(max);
  const top = ticks[ticks.length - 1] ?? max;
  const total = data.reduce((s, d) => s + d.value, 0);
  const maxIndex = data.findIndex((d) => d.value === max);
  return (
    <figure className="chart">
      <div className="col-chart" style={{ height }} role="group" aria-label={caption}>
        <div className="col-grid" aria-hidden="true">
          {ticks.map((t) => (
            <div className="col-gridline" key={t} style={{ bottom: `${(t / top) * 100}%` }}>
              <span>{formatNumber(t)}</span>
            </div>
          ))}
        </div>
        <div className="col-plot">
          {data.map((d, i) => (
            <div
              className="col"
              key={d.key}
              tabIndex={0}
              aria-label={`${d.label}: ${formatNumber(d.value)} ${unit}`}
            >
              <span className="col-bar" style={{ height: `${(d.value / top) * 100}%` }}>
                {i === maxIndex && <span className="col-cap">{formatNumber(d.value)}</span>}
              </span>
              <span className="col-tip" aria-hidden="true">
                <strong>
                  {labelHeader}: {d.label}
                </strong>
                <br />
                {formatNumber(d.value)} {unit}
                {total > 0 && ` · ${((d.value / total) * 100).toFixed(1)}%`}
              </span>
            </div>
          ))}
        </div>
      </div>
      <div className="col-labels" aria-hidden="true">
        {data.map((d) => (
          <span key={d.key}>{d.label}</span>
        ))}
      </div>
      <TableView data={data} unit={unit} labelHeader={labelHeader} caption={caption} total={total} />
    </figure>
  );
}

function TableView({ data, unit, labelHeader, caption, total }: Props & { total: number }) {
  return (
    <details className="chart-table">
      <summary>View as table</summary>
      <table>
        <caption className="visually-hidden">{caption}</caption>
        <thead>
          <tr>
            <th scope="col">{labelHeader}</th>
            <th scope="col" className="num">
              {unit.charAt(0).toUpperCase() + unit.slice(1)}
            </th>
            <th scope="col" className="num">
              Share
            </th>
          </tr>
        </thead>
        <tbody>
          {data.map((d) => (
            <tr key={d.key}>
              <td>{d.label}</td>
              <td className="num">{formatNumber(d.value)}</td>
              <td className="num">{total ? `${((d.value / total) * 100).toFixed(1)}%` : "–"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  );
}

/** Clean axis ticks: 0 plus ~3 round steps covering `max`. */
export function niceTicks(max: number, count = 3): number[] {
  const raw = max / count;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? raw;
  const ticks = [];
  for (let t = 0; t < max + step; t += step) {
    ticks.push(Math.round(t));
    if (t >= max) break;
  }
  return ticks;
}
