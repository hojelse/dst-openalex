import { Link } from "react-router";
import { EmptyState } from "../components/States";
import { useDocumentTitle } from "../lib/useDocumentTitle";

export function NotFoundPage() {
  useDocumentTitle("Page not found");
  return (
    <div className="container page-header">
      <h1>Page not found</h1>
      <EmptyState title="There is nothing at this address.">
        <p className="state-text">
          <Link to="/">Go to the search page</Link>
        </p>
      </EmptyState>
    </div>
  );
}
