import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "../../auth/AuthContext";
import { RequireAuth } from "../../auth/RequireAuth";
import { meBody, mockApi, signedOut } from "../../test/mockApi";
import { CategoryPage } from "./CategoryPage";
import { LoginPage } from "./LoginPage";

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/profile/category"
            element={
              <RequireAuth allowMissingCategory>
                <CategoryPage />
              </RequireAuth>
            }
          />
          <Route
            path="/home"
            element={
              <RequireAuth>
                <p>Home page</p>
              </RequireAuth>
            }
          />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("LoginPage", () => {
  it("offers Google sign-in and hides the development form by default", async () => {
    mockApi({
      "GET /users/me": signedOut,
      "GET /auth/config": { body: { google_enabled: true, dev_login_enabled: false } },
    });
    renderAt("/login");
    const google = await screen.findByRole("link", { name: /continue with google/i });
    expect(google).toHaveAttribute("href", expect.stringMatching(/\/api\/v1\/auth\/google$/));
    await waitFor(() => expect(screen.queryByText(/development sign-in/i)).not.toBeInTheDocument());
  });

  it("explains an error returned from the sign-in callback", async () => {
    mockApi({
      "GET /users/me": signedOut,
      "GET /auth/config": { body: { google_enabled: true, dev_login_enabled: false } },
    });
    renderAt("/login?error=INVALID_STATE");
    expect(await screen.findByRole("alert")).toHaveTextContent(/expired or didn't match/i);
  });

  it("shows the development form only when the server enables it", async () => {
    mockApi({
      "GET /users/me": signedOut,
      "GET /auth/config": { body: { google_enabled: false, dev_login_enabled: true } },
    });
    renderAt("/login");
    expect(await screen.findByText(/development sign-in/i)).toBeInTheDocument();
    expect(screen.getByText(/isn't configured on this server/i)).toBeInTheDocument();
  });
});

describe("Route guards", () => {
  it("sends signed-out visitors to the login page", async () => {
    mockApi({
      "GET /users/me": signedOut,
      "GET /auth/config": { body: { google_enabled: true, dev_login_enabled: false } },
    });
    renderAt("/home");
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
  });

  it("sends external users without a category to the category page", async () => {
    mockApi({ "GET /users/me": { body: meBody({ rate_category: null, needs_category: true }) } });
    renderAt("/home");
    expect(await screen.findByRole("heading", { name: "Your organisation" })).toBeInTheDocument();
  });

  it("lets IIT users straight in", async () => {
    mockApi({ "GET /users/me": { body: meBody({ rate_category: "IIT", is_iit: true }) } });
    renderAt("/home");
    expect(await screen.findByText("Home page")).toBeInTheDocument();
  });
});

describe("CategoryPage", () => {
  it("saves the chosen category with the CSRF token and continues home", async () => {
    let me = meBody({ rate_category: null, needs_category: true });
    const fetchMock = mockApi({
      "GET /users/me": () => ({ body: me }),
      "PUT /users/me/rate-category": (init) => {
        me = meBody({ rate_category: JSON.parse(String(init.body)).rate_category });
        return { body: me };
      },
    });
    renderAt("/profile/category");

    await userEvent.click(await screen.findByLabelText(/Govt\. \/ Semi Govt\. \/ PSU/));
    await userEvent.click(screen.getByRole("button", { name: "Continue" }));

    expect(await screen.findByText("Home page")).toBeInTheDocument();
    const put = fetchMock.mock.calls.find(([, init]) => init?.method === "PUT");
    expect(put?.[1]?.body).toBe(JSON.stringify({ rate_category: "GOVT" }));
    expect((put?.[1]?.headers as Record<string, string>)["X-CSRF-Token"]).toBe("csrf-123");
  });

  it("asks for a choice before submitting", async () => {
    mockApi({ "GET /users/me": { body: meBody({ rate_category: null, needs_category: true }) } });
    renderAt("/profile/category");
    await userEvent.click(await screen.findByRole("button", { name: "Continue" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Choose one option.");
  });
});
