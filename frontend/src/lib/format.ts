const regionNames = new Intl.DisplayNames(["en"], { type: "region" });

export function countryName(code: string | null | undefined): string {
  if (!code) return "Unknown";
  try {
    return regionNames.of(code.toUpperCase()) ?? code;
  } catch {
    return code;
  }
}

/** "DK" -> 🇩🇰 (regional indicator symbols). Decorative only: always paired with the name. */
export function flag(code: string | null | undefined): string {
  if (!code || !/^[A-Za-z]{2}$/.test(code)) return "";
  return String.fromCodePoint(...[...code.toUpperCase()].map((c) => 0x1f1e6 + c.charCodeAt(0) - 65));
}

const dateFmt = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric" });

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "Unknown date";
  const d = new Date(`${iso.slice(0, 10)}T00:00:00`);
  return Number.isNaN(d.getTime()) ? iso : dateFmt.format(d);
}

const monthFmt = new Intl.DateTimeFormat("en-GB", { month: "short" });
export function formatMonth(yyyyMm: string): string {
  const d = new Date(`${yyyyMm}-01T00:00:00`);
  return Number.isNaN(d.getTime()) ? yyyyMm : monthFmt.format(d);
}

const numFmt = new Intl.NumberFormat("en-US");
export const formatNumber = (n: number) => numFmt.format(n);

const compactFmt = new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 });
export const formatCompact = (n: number) => (n < 10_000 ? numFmt.format(n) : compactFmt.format(n));

export const formatPercent = (share: number, digits = 0) => `${(share * 100).toFixed(digits)}%`;

export function plural(n: number, one: string, many = `${one}s`) {
  return `${formatNumber(n)} ${n === 1 ? one : many}`;
}

const TYPE_LABELS: Record<string, string> = {
  article: "Article",
  review: "Review",
  preprint: "Preprint",
  "book-chapter": "Book chapter",
  book: "Book",
  dissertation: "Dissertation",
  dataset: "Dataset",
  "conference-abstract": "Conference abstract",
  "software-paper": "Software paper",
  letter: "Letter",
  editorial: "Editorial",
  report: "Report",
  other: "Other",
};

export function typeLabel(type: string | null | undefined): string {
  if (!type) return "Unknown type";
  return TYPE_LABELS[type] ?? type.charAt(0).toUpperCase() + type.slice(1).replace(/-/g, " ");
}

const OA_LABELS: Record<string, string> = {
  gold: "Gold OA",
  diamond: "Diamond OA",
  green: "Green OA",
  hybrid: "Hybrid OA",
  bronze: "Bronze OA",
  closed: "Closed access",
  unknown: "Unknown access",
};

export const oaLabel = (status: string | null | undefined) => OA_LABELS[status ?? "unknown"] ?? status ?? "Unknown";

export const OA_DESCRIPTIONS: Record<string, string> = {
  gold: "Published open access in an open-access journal",
  diamond: "Open-access journal with no author charges",
  green: "Free copy available in a repository",
  hybrid: "Open access in a subscription journal",
  bronze: "Free to read on the publisher site, without an open licence",
  closed: "No free copy found",
};

const languageNames = new Intl.DisplayNames(["en"], { type: "language" });
export function languageName(code: string | null | undefined): string | null {
  if (!code) return null;
  try {
    return languageNames.of(code) ?? code;
  } catch {
    return code;
  }
}
