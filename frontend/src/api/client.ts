export const API_BASE_URL: string =
  (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "") || "http://localhost:8000/api/v1";

/** Error thrown for non-2xx responses, carrying the backend's `{error: {code, message, details}}` payload. */
export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
    public readonly details: Record<string, unknown> = {},
  ) {
    super(message);
    this.name = "ApiError";
  }

  /** Field-level messages from a 422 VALIDATION_ERROR, keyed by field name. */
  fieldErrors(): Record<string, string> {
    const out: Record<string, string> = {};
    const fields = (this.details.fields as { loc?: unknown[]; msg?: string }[] | undefined) ?? [];
    for (const f of fields) {
      const name = String(f.loc?.[f.loc.length - 1] ?? "");
      if (name && !out[name]) out[name] = (f.msg ?? "Invalid value").replace(/^Value error, /, "");
    }
    if (typeof this.details.field === "string" && !out[this.details.field]) out[this.details.field] = this.message;
    return out;
  }
}

// The CSRF token comes from GET /users/me and must accompany every state-changing request.
let csrfToken: string | null = null;
export function setCsrfToken(token: string | null) {
  csrfToken = token;
}

type Method = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

export async function apiRequest<T>(method: Method, path: string, body?: unknown, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (method !== "GET" && csrfToken) headers["X-CSRF-Token"] = csrfToken;

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      method,
      headers: { ...headers, ...((init?.headers as Record<string, string>) ?? {}) },
      body: body === undefined ? undefined : JSON.stringify(body),
      credentials: "include", // send the session cookie
    });
  } catch {
    throw new ApiError(0, "NETWORK_ERROR", "Could not reach the booking server. Is the backend running?");
  }

  if (response.status === 204) return undefined as T;
  const data: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const err = (data as { error?: { code?: string; message?: string; details?: Record<string, unknown> } } | null)
      ?.error;
    throw new ApiError(
      response.status,
      err?.code ?? "HTTP_ERROR",
      err?.message ?? `Request failed with status ${response.status}.`,
      err?.details ?? {},
    );
  }
  return data as T;
}

export function apiGet<T>(path: string, init?: RequestInit): Promise<T> {
  return apiRequest<T>("GET", path, undefined, init);
}

export function errorMessage(err: unknown, fallback = "Something went wrong. Please try again."): string {
  return err instanceof ApiError ? err.message : fallback;
}
