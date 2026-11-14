import { useEffect, useRef } from "react";
import { Link, NavLink, Route, Routes, useLocation, useNavigationType } from "react-router";
import { InsightsPage } from "./pages/InsightsPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { SearchPage } from "./pages/SearchPage";
import { WorkPage } from "./pages/WorkPage";

export default function App() {
  const { pathname } = useLocation();
  const navType = useNavigationType();
  const mainRef = useRef<HTMLElement>(null);
  const previousPath = useRef(pathname);

  // On client-side page changes: start at the top and move focus to the new content so
  // screen-reader and keyboard users aren't left on the link they activated.
  // (Comparing paths rather than a "first render" flag keeps this StrictMode-safe.)
  useEffect(() => {
    if (previousPath.current === pathname) return;
    previousPath.current = pathname;
    if (navType !== "POP") window.scrollTo(0, 0);
    mainRef.current?.focus({ preventScroll: true });
  }, [pathname, navType]);

  return (
    <>
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <header className="site-header">
        <div className="container site-header-inner">
          <Link to="/" className="brand" aria-label="Climate Research DK, home">
            <svg className="brand-mark" viewBox="0 0 32 32" aria-hidden="true">
              <circle cx="16" cy="16" r="14" />
              <path d="M6 19c4-5 8 3 12-2s6-3 8-1" />
            </svg>
            <span>
              <span className="brand-name">Climate Research DK</span>
              <span className="brand-tag">2025 publications · Danish institutions · OpenAlex</span>
            </span>
          </Link>
          <nav aria-label="Main" className="main-nav">
            <NavLink to="/" end>
              Search
            </NavLink>
            <NavLink to="/insights">Insights</NavLink>
          </nav>
        </div>
      </header>

      <main id="main" ref={mainRef} tabIndex={-1}>
        <Routes>
          <Route path="/" element={<SearchPage />} />
          <Route path="/works/:id" element={<WorkPage />} />
          <Route path="/insights" element={<InsightsPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </main>

      <footer className="site-footer">
        <div className="container">
          Data from{" "}
          <a href="https://openalex.org" target="_blank" rel="noreferrer">
            OpenAlex
          </a>{" "}
          (CC0): works matching “climate change” with at least one Danish institution, published in 2025.
        </div>
      </footer>
    </>
  );
}
