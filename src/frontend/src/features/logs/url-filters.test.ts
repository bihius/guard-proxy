import { describe, expect, it } from "vitest";

import { EMPTY_FILTERS } from "./types";
import { filtersFromSearchParams, hasAnyFilter } from "./url-filters";

function parse(query: string) {
  return filtersFromSearchParams(new URLSearchParams(query));
}

describe("filtersFromSearchParams", () => {
  it("hydrates the filters the dashboard deep-links with", () => {
    const filters = parse("action=deny&source_ip=203.0.113.5&rule_id=942100");

    expect(filters.action).toBe("deny");
    expect(filters.source_ip).toBe("203.0.113.5");
    expect(filters.rule_id).toBe(942100);
  });

  it("ignores values outside the allowed enums", () => {
    expect(parse("action=explode").action).toBe("");
    expect(parse("severity=catastrophic").severity).toBe("");
  });

  it("ignores a non-numeric rule id", () => {
    expect(parse("rule_id=abc").rule_id).toBeNull();
    expect(parse("rule_id=-3").rule_id).toBeNull();
  });

  it("returns empty filters for an unrelated query string", () => {
    expect(parse("page=2&sort=asc")).toEqual(EMPTY_FILTERS);
  });
});

describe("hasAnyFilter", () => {
  it("is false only when nothing is set", () => {
    expect(hasAnyFilter(EMPTY_FILTERS)).toBe(false);
    expect(hasAnyFilter({ ...EMPTY_FILTERS, vhost: "app.example.com" })).toBe(true);
    expect(hasAnyFilter({ ...EMPTY_FILTERS, rule_id: 1 })).toBe(true);
  });
});
