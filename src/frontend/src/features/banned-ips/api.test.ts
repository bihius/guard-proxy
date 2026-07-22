import { afterEach, describe, expect, it, vi } from "vitest";

import { listBannedIps, unbanIp } from "./api";

function jsonResponse(body: unknown) {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}

describe("banned-ips API", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllEnvs();
  });

  it("fetches the banned-ips list", async () => {
    vi.stubEnv("VITE_API_BASE_URL", "");
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      jsonResponse({
        items: [
          {
            ip: "203.0.113.10",
            vhost_id: 1,
            domain: "app.example.com",
            gpc0: 12,
            ban_threshold: 10,
            banned: true,
            expires_in_seconds: 120,
          },
        ],
        total: 1,
      }),
    );

    const response = await listBannedIps("token");

    expect(response.items[0]?.ip).toBe("203.0.113.10");
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/v1/security/banned-ips");
  });

  it("sends a DELETE request with the IP URI-encoded in the path", async () => {
    vi.stubEnv("VITE_API_BASE_URL", "");
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse({ ip: "203.0.113.10", cleared: 1 }));

    const response = await unbanIp("token", "203.0.113.10");

    expect(response).toEqual({ ip: "203.0.113.10", cleared: 1 });
    expect(fetchMock.mock.calls[0]?.[0]).toBe("/api/v1/security/banned-ips/203.0.113.10");
    expect(fetchMock.mock.calls[0]?.[1]?.method).toBe("DELETE");
  });

  it("URI-encodes IPv6 literals in the delete path", async () => {
    vi.stubEnv("VITE_API_BASE_URL", "");
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse({ ip: "2001:db8::1", cleared: 1 }));

    await unbanIp("token", "2001:db8::1");

    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      "/api/v1/security/banned-ips/2001%3Adb8%3A%3A1",
    );
  });
});
