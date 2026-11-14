import { Fragment } from "react";

// The API marks highlighted terms with private-use characters (see backend search.py)
// instead of HTML, so we can render <mark> elements without dangerouslySetInnerHTML.
const PRE = "";
const POST = "";

export function Highlight({ text }: { text: string }) {
  const parts: React.ReactNode[] = [];
  let rest = text;
  let key = 0;
  while (rest.length) {
    const start = rest.indexOf(PRE);
    if (start === -1) {
      parts.push(<Fragment key={key++}>{rest}</Fragment>);
      break;
    }
    const end = rest.indexOf(POST, start);
    if (start > 0) parts.push(<Fragment key={key++}>{rest.slice(0, start)}</Fragment>);
    if (end === -1) {
      parts.push(<Fragment key={key++}>{rest.slice(start + 1)}</Fragment>);
      break;
    }
    parts.push(<mark key={key++}>{rest.slice(start + 1, end)}</mark>);
    rest = rest.slice(end + 1);
  }
  return <>{parts}</>;
}

export const stripMarkers = (text: string) => text.replaceAll(PRE, "").replaceAll(POST, "");
