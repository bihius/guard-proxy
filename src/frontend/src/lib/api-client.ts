const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";

export type ApiResponseType = "json" | "text" | "empty";

export type ApiClientOptions = {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
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

function getApiBaseUrl() {
  return import.meta.env.VITE_API_BASE_URL ?? DEFAULT_API_BASE_URL;
}

function isJsonContentType(contentType: string | null) {
  if (!contentType) {
    return false;
  }

  return (
    contentType.includes("application/json") || contentType.includes("+json")
  );
}

function buildBody(body: ApiClientOptions["body"]) {
  if (body == null) {
    return undefined;
  }

  if (
    body instanceof FormData ||
    body instanceof URLSearchParams ||
    body instanceof Blob ||
    ArrayBuffer.isView(body) ||
    body instanceof ArrayBuffer ||
    typeof body === "string"
  ) {
    return body;
  }

  return JSON.stringify(body);
}

export async function apiRequest<T>(
  path: string,
  options: ApiClientOptions = {}
): Promise<T> {
  const headers = new Headers(options.headers);

  if (
    options.body != null &&
    !(options.body instanceof FormData) &&
    !(options.body instanceof URLSearchParams) &&
    !(options.body instanceof Blob) &&
    !(ArrayBuffer.isView(options.body)) &&
    !(options.body instanceof ArrayBuffer) &&
    typeof options.body !== "string"
  ) {
    headers.set("Content-Type", "application/json");
  }

  if (options.token) {
    headers.set("Authorization", `Bearer ${options.token}`);
  }

  if (options.responseType !== "empty" && !headers.has("Accept")) {
    headers.set("Accept", "application/json");
  }

  const response = await fetch(new URL(path, getApiBaseUrl()).toString(), {
    method: options.method ?? "GET",
    headers,
    body: buildBody(options.body),
    credentials: options.credentials,
    signal: options.signal,
  });

  if (!response.ok) {
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
