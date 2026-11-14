import { OA_DESCRIPTIONS, formatNumber, oaLabel } from "../lib/format";

/** Open-access status: icon + text, never colour alone. */
export function OaBadge({ status, isOa }: { status: string | null; isOa: boolean }) {
  return (
    <span className={`badge ${isOa ? "badge-oa" : "badge-closed"}`} title={OA_DESCRIPTIONS[status ?? ""] ?? undefined}>
      <svg viewBox="0 0 16 16" aria-hidden="true">
        {isOa ? (
          <path d="M5 7V5a3 3 0 0 1 5.8-1M4 7h8v6H4z" />
        ) : (
          <path d="M5 7V5a3 3 0 0 1 6 0v2M4 7h8v6H4z" />
        )}
      </svg>
      {oaLabel(isOa ? status : "closed")}
    </span>
  );
}

export function CitationCount({ count }: { count: number }) {
  return (
    <span className="citations" title="Times cited (OpenAlex)">
      <svg viewBox="0 0 16 16" aria-hidden="true">
        <path d="M3 4h4v4H5c0 2 1 3 2 3.5M9 4h4v4h-2c0 2 1 3 2 3.5" />
      </svg>
      <span>
        <strong>{formatNumber(count)}</strong> {count === 1 ? "citation" : "citations"}
      </span>
    </span>
  );
}
