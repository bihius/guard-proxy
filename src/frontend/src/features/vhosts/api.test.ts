import { afterEach, describe, expect, it, vi } from "vitest";

import { listAllPolicies, listAllVHosts } from "./api";

function jsonResponse(body: unknown) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}

describe("vhosts API pagination helpers", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllEnvs();
  });

  it("loads every vhost page for complete relationship checks", async () => {
    vi.stubEnv("VITE_API_BASE_URL", "");
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        jsonResponse({
          items: [{ id: 1, domain: "first.example.com" }],
          total: 2,
          page: 1,
          per_page: 500,
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          items: [{ id: 501, domain: "late.example.com" }],
          total: 2,
          page: 2,
          per_page: 500,
        }),
      );

    const vhosts = await listAllVHosts("token");

    expect(vhosts.map((vhost) => vhost.domain)).toEqual([
      "first.example.com",
      "late.example.com",
    ]);
    expect(fetchMock.mock.calls.map((call) => call[0])).toEqual([
      "/api/v1/vhosts?page=1&per_page=500",
      "/api/v1/vhosts?page=2&per_page=500",
    ]);
  });

  it("loads every policy page for vhost assignment selectors", async () => {
    vi.stubEnv("VITE_API_BASE_URL", "");
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        jsonResponse({
          items: [{ id: 1, name: "First policy" }],
          total: 2,
          page: 1,
          per_page: 500,
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          items: [{ id: 501, name: "Late policy" }],
          total: 2,
          page: 2,
          per_page: 500,
        }),
      );

    const policies = await listAllPolicies("token");

    expect(policies.map((policy) => policy.name)).toEqual([
      "First policy",
      "Late policy",
    ]);
    expect(fetchMock.mock.calls.map((call) => call[0])).toEqual([
      "/api/v1/policies?page=1&per_page=500",
      "/api/v1/policies?page=2&per_page=500",
    ]);
  });
});
