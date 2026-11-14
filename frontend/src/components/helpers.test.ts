import { describe, expect, it } from "vitest";
import { niceTicks } from "./BarChart";
import { pageItems } from "./Pagination";

describe("pageItems", () => {
  it("shows all pages when few", () => {
    expect(pageItems(1, 3)).toEqual([1, 2, 3]);
  });
  it("collapses distant pages into ellipses", () => {
    expect(pageItems(6, 50)).toEqual([1, "…", 5, 6, 7, "…", 50]);
  });
  it("fills a single-page gap instead of an ellipsis", () => {
    expect(pageItems(4, 10)).toEqual([1, 2, 3, 4, 5, "…", 10]);
  });
});

describe("niceTicks", () => {
  it("covers the maximum with round steps", () => {
    expect(niceTicks(472)).toEqual([0, 200, 400, 600]);
    expect(niceTicks(95)).toEqual([0, 50, 100]);
    const t = niceTicks(1408);
    expect(t[0]).toBe(0);
    expect(t.at(-1)!).toBeGreaterThanOrEqual(1408);
  });
});
