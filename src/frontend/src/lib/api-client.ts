
export type ApiResponseType = "json" | "text" | "empty";

export type ApiClientOptions = {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: BodyInit | Record<string, unknown> | null;
  token?: string | null;
  headers?: HeadersInit;
  credentials?: RequestCredentials;
  responseType?: ApiResponseType;
  signal?: AbortSignal;
};

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

export class InvalidResponseError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "InvalidResponseError";
  }
}

/**
 * Called when an authenticated request gets a 401. Should attempt a session
 * refresh and return the new access token, or null when the session is gone
 * (in which case auth state is expected to be cleared by the handler).
 */
type UnauthorizedHandler = () => Promise<string | null>;

let unauthorizedHandler: UnauthorizedHandler | null = null;
let pendingTokenRefresh: Promise<string | null> | null = null;

export function setUnauthorizedHandler(handler: UnauthorizedHandler | null) {
  unauthorizedHandler = handler;
  pendingTokenRefresh = null;
}

function refreshAccessToken(): Promise<string | null> {
  if (!unauthorizedHandler) {
    return Promise.resolve(null);
  }

  // Deduplicate concurrent 401s into a single refresh attempt.
  pendingTokenRefresh ??= unauthorizedHandler()
    .catch(() => null)
    .finally(() => {
      pendingTokenRefresh = null;
    });

  return pendingTokenRefresh;
}

function getApiBaseUrl() {
  const envUrl = import.meta.env.VITE_API_BASE_URL;
  if (envUrl && envUrl.trim() !== "") {
    return envUrl;
  }
  return "/api/v1";
}

function isJsonContentType(contentType: string | null) {
  if (!contentType) {
    return false;
  }

  return (
    contentType.includes("application/json") || contentType.includes("+json")
  );
}

function isReadableStreamBody(value: unknown): value is ReadableStream<unknown> {
  return typeof ReadableStream !== "undefined" && value instanceof ReadableStream;
}

function isBodyInit(value: unknown): value is BodyInit {
  return (
    (typeof FormData !== "undefined" && value instanceof FormData) ||
    (typeof URLSearchParams !== "undefined" &&
      value instanceof URLSearchParams) ||
    (typeof Blob !== "undefined" && value instanceof Blob) ||
    ArrayBuffer.isView(value) ||
    value instanceof ArrayBuffer ||
    typeof value === "string" ||
    isReadableStreamBody(value)
  );
}

function buildBody(body: ApiClientOptions["body"]) {
  if (body == null) {
    return undefined;
  }

  if (isBodyInit(body)) {
    return body;
  }

  return JSON.stringify(body);
}

export function apiRequest<T>(
  path: string,
  options: ApiClientOptions = {}
): Promise<T> {
  return executeRequest<T>(path, options, false);
}

async function executeRequest<T>(
  path: string,
  options: ApiClientOptions,
  isRetry: boolean
): Promise<T> {
  const headers = new Headers(options.headers);

  if (options.body != null && !isBodyInit(options.body)) {
    headers.set("Content-Type", "application/json");
  }

  if (options.token) {
    headers.set("Authorization", `Bearer ${options.token}`);
  }

  if (!headers.has("Accept")) {
    if (options.responseType === "text") {
      headers.set("Accept", "text/plain");
    } else if (options.responseType !== "empty") {
      headers.set("Accept", "application/json");
    }
  }

  const base = getApiBaseUrl();
  const cleanBase = base.endsWith("/") ? base.slice(0, -1) : base;
  const cleanPath = path.startsWith("/") ? path : `/${path}`;
  const url = `${cleanBase}${cleanPath}`;

  const response = await fetch(url, {
    method: options.method ?? "GET",
    headers,
    body: buildBody(options.body),
    credentials: options.credentials,
    signal: options.signal,
  });

  if (!response.ok) {
    if (response.status === 401 && options.token && !isRetry) {
      const newToken = await refreshAccessToken();
      if (newToken) {
        return executeRequest<T>(path, { ...options, token: newToken }, true);
      }
    }

    let detail = "Request failed";

    try {
      if (isJsonContentType(response.headers.get("content-type"))) {
        const data = (await response.json()) as { detail?: string };
        detail = data.detail ?? detail;
      } else {
        const text = await response.text();
        detail = text || response.statusText || detail;
      }
    } catch {
      detail = response.statusText || detail;
    }

    throw new ApiError(response.status, detail);
  }

  if (options.responseType === "empty" || response.status === 204) {
    return undefined as T;
  }

  if (options.responseType === "text") {
    return (await response.text()) as T;
  }

  const contentType = response.headers.get("content-type");
  if (!isJsonContentType(contentType)) {
    throw new InvalidResponseError(
      `Expected JSON response from ${path}, got ${contentType ?? "no content type"}`
    );
  }

  return (await response.json()) as T;
}
