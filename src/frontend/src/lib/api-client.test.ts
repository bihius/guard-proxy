import { afterEach, describe, expect, it, vi } from "vitest";

import { apiRequest } from "./api-client";

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
});
