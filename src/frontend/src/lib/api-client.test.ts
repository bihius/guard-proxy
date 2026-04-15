import { afterEach, describe, expect, it, vi } from "vitest";

import { InvalidResponseError, apiRequest } from "./api-client";

describe("apiRequest", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("passes ReadableStream bodies through without JSON serialization", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response("ok", {
          status: 200,
          headers: { "content-type": "text/plain" },
        }),
      );
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(new Uint8Array([1, 2, 3]));
        controller.close();
      },
    });

    await apiRequest("/stream", {
      method: "POST",
      body: stream,
      responseType: "text",
    });

    const init = fetchMock.mock.calls[0]?.[1];
    const headers = new Headers(init?.headers);

    expect(init?.body).toBe(stream);
    expect(headers.has("Content-Type")).toBe(false);
    expect(headers.get("Accept")).toBe("text/plain");
  });

  it("sets JSON headers and stringifies plain object bodies", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response("{}", {
          status: 200,
          headers: { "content-type": "application/json" },
        }),
      );

    await apiRequest("/json", {
      method: "POST",
      body: { hello: "world" },
    });

    const init = fetchMock.mock.calls[0]?.[1];
    const headers = new Headers(init?.headers);

    expect(init?.body).toBe(JSON.stringify({ hello: "world" }));
    expect(headers.get("Content-Type")).toBe("application/json");
    expect(headers.get("Accept")).toBe("application/json");
  });

  it("parses JSON responses", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify({ status: "ok" }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );

    await expect(apiRequest<{ status: string }>("/health")).resolves.toEqual({
      status: "ok",
    });
  });

  it("supports empty responses", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(null, { status: 204 }),
    );

    await expect(
      apiRequest<void>("/auth/logout", {
        method: "POST",
        responseType: "empty",
      }),
    ).resolves.toBeUndefined();
  });

  it("fails clearly on unexpected success content type", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response("plain text", {
        status: 200,
        headers: { "content-type": "text/plain" },
      }),
    );

    await expect(apiRequest("/health")).rejects.toBeInstanceOf(
      InvalidResponseError,
    );
  });

  it("uses text fallback for non-json errors", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response("Backend exploded", {
        status: 500,
        headers: { "content-type": "text/plain" },
      }),
    );

    await expect(apiRequest("/health")).rejects.toMatchObject({
      detail: "Backend exploded",
      status: 500,
    });
  });
});
