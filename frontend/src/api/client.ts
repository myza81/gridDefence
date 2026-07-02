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
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<TResponse>(path: string, init?: RequestInit): Promise<TResponse> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  if (!response.ok) {
    throw new ApiError(`Request to ${path} failed with status ${response.status}`, response.status);
  }

  return (await response.json()) as TResponse;
}

export const apiClient = {
  baseUrl: API_BASE_URL,
  get: <TResponse>(path: string) => request<TResponse>(path, { method: "GET" }),
  post: <TResponse>(path: string, body?: unknown) =>
    request<TResponse>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
};

export interface HealthResponse {
  status: string;
  environment: string;
}

/** Unversioned health check — not under /api/v1 (backend main.py mirrors this). */
export function getHealth(): Promise<HealthResponse> {
  return apiClient.get<HealthResponse>("/health");
}
