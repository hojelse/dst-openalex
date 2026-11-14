import { useEffect } from "react";

export function useDocumentTitle(title: string | undefined) {
  useEffect(() => {
    document.title = title ? `${title} · Climate Research DK` : "Climate Research DK";
  }, [title]);
}
