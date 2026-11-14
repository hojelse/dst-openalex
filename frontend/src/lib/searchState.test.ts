import { describe, expect, it } from "vitest";
import { activeFilterCount, parseSearchState, toSearchParams } from "./searchState";

describe("search state <-> URL", () => {
  it("round-trips every field", () => {
    const qs = "q=sea+ice&field=title&country=SE&country=NO&author=Jens&date_from=2025-02-01&sort=newest&page=3";
    const state = parseSearchState(new URLSearchParams(qs));
    expect(state.q).toBe("sea ice");
    expect(state.field).toBe("title");
    expect(state.filters.country).toEqual(["SE", "NO"]);
    expect(state.filters.author).toEqual(["Jens"]);
    expect(state.filters.concept).toEqual([]);
    expect(state.page).toBe(3);
    expect(activeFilterCount(state)).toBe(4);
    expect(parseSearchState(toSearchParams(state))).toEqual(state);
  });

  it("falls back to defaults for invalid values", () => {
    const state = parseSearchState(new URLSearchParams("field=bogus&sort=nope&page=-4"));
    expect(state.field).toBe("all");
    expect(state.sort).toBe("relevance");
    expect(state.page).toBe(1);
  });

  it("omits defaults from the URL", () => {
    const state = parseSearchState(new URLSearchParams(""));
    expect(toSearchParams(state).toString()).toBe("");
  });
});
