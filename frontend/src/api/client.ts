/**
 * Thin, typed HTTP client for the GridDefence backend.
 *
 * Every module's own API hooks (src/modules/<name>/api.ts, once that module
 * exists) call through this client rather than each inventing its own fetch
 * wrapper — keeping the base URL, error shape, and credentials handling in
 * one place.
 */

const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly detail?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/**
 * Supplies the current bearer token for authenticated requests. Set by
 * modules/iam's AuthContext once a session exists; read here so the shared
 * client stays the single place requests are issued from (no per-module
 * fetch wrappers).
 */
let authTokenProvider: (() => string | null) | null = null;

export function setAuthTokenProvider(provider: (() => string | null) | null): void {
  authTokenProvider = provider;
}

async function request<TResponse>(path: string, init?: RequestInit): Promise<TResponse> {
  const token = authTokenProvider?.() ?? null;
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init?.headers,
    },
  });

  if (!response.ok) {
    let detail: unknown;
    try {
      detail = await response.json();
    } catch {
      detail = undefined;
    }
    throw new ApiError(`Request to ${path} failed with status ${response.status}`, response.status, detail);
  }

  if (response.status === 204) {
    return undefined as TResponse;
  }

  return (await response.json()) as TResponse;
}

export const apiClient = {
  baseUrl: API_BASE_URL,
  get: <TResponse>(path: string) => request<TResponse>(path, { method: "GET" }),
  post: <TResponse>(path: string, body?: unknown) =>
    request<TResponse>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
  delete: <TResponse>(path: string) => request<TResponse>(path, { method: "DELETE" }),
};

export interface HealthResponse {
  status: string;
  environment: string;
}

/** Unversioned health check — not under /api/v1 (backend main.py mirrors this). */
export function getHealth(): Promise<HealthResponse> {
  return apiClient.get<HealthResponse>("/health");
}
