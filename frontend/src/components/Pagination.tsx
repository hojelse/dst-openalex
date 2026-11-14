import { Link } from "react-router";

interface Props {
  page: number;
  pages: number;
  hrefFor: (page: number) => string;
}

/** Page numbers with ellipses: 1 … 4 5 [6] 7 8 … 50. Real links, so they can be opened in new tabs. */
export function Pagination({ page, pages, hrefFor }: Props) {
  if (pages <= 1) return null;
  const items = pageItems(page, pages);
  return (
    <nav className="pagination" aria-label="Pagination">
      {page > 1 ? (
        <Link className="page-link page-step" to={hrefFor(page - 1)} rel="prev">
          ‹ Previous
        </Link>
      ) : (
        <span className="page-link page-step" aria-disabled="true">
          ‹ Previous
        </span>
      )}
      <ul>
        {items.map((it, i) =>
          it === "…" ? (
            <li key={`gap-${i}`} className="page-gap" aria-hidden="true">
              …
            </li>
          ) : (
            <li key={it}>
              <Link
                className="page-link"
                to={hrefFor(it)}
                aria-current={it === page ? "page" : undefined}
                aria-label={`Page ${it}`}
              >
                {it}
              </Link>
            </li>
          ),
        )}
      </ul>
      {page < pages ? (
        <Link className="page-link page-step" to={hrefFor(page + 1)} rel="next">
          Next ›
        </Link>
      ) : (
        <span className="page-link page-step" aria-disabled="true">
          Next ›
        </span>
      )}
    </nav>
  );
}

export function pageItems(page: number, pages: number): (number | "…")[] {
  const set = new Set([1, pages, page - 1, page, page + 1].filter((p) => p >= 1 && p <= pages));
  const sorted = [...set].sort((a, b) => a - b);
  const out: (number | "…")[] = [];
  sorted.forEach((p, i) => {
    const prev = sorted[i - 1];
    if (prev !== undefined && p - prev === 2) out.push(prev + 1);
    else if (prev !== undefined && p - prev > 2) out.push("…");
    out.push(p);
  });
  return out;
}
