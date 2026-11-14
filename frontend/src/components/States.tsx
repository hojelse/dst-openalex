import type { ReactNode } from "react";

export function ErrorState({ title = "Something went wrong", error, onRetry }: { title?: string; error: unknown; onRetry?: () => void }) {
  const message = error instanceof Error ? error.message : "Unexpected error.";
  return (
    <div className="state state-error" role="alert">
      <svg viewBox="0 0 24 24" className="state-icon" aria-hidden="true">
        <circle cx="12" cy="12" r="10" />
        <path d="M12 7v6M12 16.5v.5" />
      </svg>
      <div>
        <p className="state-title">{title}</p>
        <p className="state-text">{message}</p>
        {onRetry && (
          <button type="button" className="btn btn-secondary" onClick={onRetry}>
            Try again
          </button>
        )}
      </div>
    </div>
  );
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="state">
      <svg viewBox="0 0 24 24" className="state-icon" aria-hidden="true">
        <circle cx="10.5" cy="10.5" r="6.5" />
        <path d="M15.5 15.5 21 21" />
      </svg>
      <div>
        <p className="state-title">{title}</p>
        {children}
      </div>
    </div>
  );
}

export function Spinner({ label = "Loading" }: { label?: string }) {
  return (
    <div className="spinner-wrap" role="status">
      <span className="spinner" aria-hidden="true" />
      <span className="visually-hidden">{label}…</span>
    </div>
  );
}

export function SkeletonResults({ count = 5 }: { count?: number }) {
  return (
    <div role="status" aria-label="Loading results">
      {Array.from({ length: count }, (_, i) => (
        <div className="result skeleton" key={i} aria-hidden="true">
          <div className="sk sk-title" />
          <div className="sk sk-line" style={{ width: "40%" }} />
          <div className="sk sk-line" style={{ width: "75%" }} />
          <div className="sk sk-line" style={{ width: "60%" }} />
        </div>
      ))}
    </div>
  );
}
