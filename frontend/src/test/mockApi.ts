import { vi } from "vitest";

type Handler = (init: RequestInit) => { status?: number; body?: unknown };

/**
 * Replace fetch with a router keyed by "METHOD /path" (path after /api/v1, query ignored).
 * Returns the mock so tests can inspect calls.
 */
export function mockApi(routes: Record<string, Handler | { status?: number; body?: unknown }>) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const url = new URL(String(input));
    const path = url.pathname.replace(/^\/api\/v1/, "");
    const key = `${(init.method ?? "GET").toUpperCase()} ${path}`;
    const route = routes[key];
    if (!route) {
      return new Response(JSON.stringify({ error: { code: "NOT_MOCKED", message: key } }), { status: 599 });
    }
    const { status = 200, body } = typeof route === "function" ? route(init) : route;
    if (status === 204) return new Response(null, { status });
    return new Response(JSON.stringify(body ?? null), { status, headers: { "Content-Type": "application/json" } });
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

export const signedOut = { status: 401, body: { error: { code: "UNAUTHENTICATED", message: "Please sign in." } } };

export function meBody(overrides: Record<string, unknown> = {}) {
  return {
    id: 1,
    email: "events@company.com",
    name: "Asha Rao",
    rate_category: "PRIVATE",
    is_iit: false,
    needs_category: false,
    csrf_token: "csrf-123",
    roles: [],
    ...overrides,
  };
}
