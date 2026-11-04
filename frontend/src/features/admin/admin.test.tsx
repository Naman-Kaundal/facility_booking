import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "../../auth/AuthContext";
import { RequireRole } from "../../auth/RequireRole";
import { meBody, mockApi } from "../../test/mockApi";
import type { StaffRoleRow } from "../../types/admin";
import { AdminPage } from "./AdminPage";

afterEach(() => vi.unstubAllGlobals());

const SETTINGS = {
  gst_pct: 18,
  cleaning_pct: 10,
  security_deposit: 5000,
  electricity_advance_pct: 80,
  payment_url: null,
  updated_at: null,
  updated_by: null,
};
const ADMIN = meBody({ email: "admin@iitrpr.ac.in", roles: ["ADMIN"] });

function renderAdmin(tab = "settings") {
  return render(
    <MemoryRouter initialEntries={[`/admin?tab=${tab}`]}>
      <AuthProvider>
        <Routes>
          <Route
            path="/admin"
            element={
              <RequireRole roles={["ADMIN"]}>
                <AdminPage />
              </RequireRole>
            }
          />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("AdminPage", () => {
  it("is staff only", async () => {
    mockApi({ "GET /users/me": { body: meBody({ roles: ["FACILITY"] }) } });
    renderAdmin();
    expect(await screen.findByText("Staff only")).toBeInTheDocument();
  });

  it("validates and saves the cost settings and payment link", async () => {
    const fetchMock = mockApi({
      "GET /users/me": { body: ADMIN },
      "GET /admin/settings": { body: SETTINGS },
      "PATCH /admin/settings": (init) => ({
        body: { ...SETTINGS, ...JSON.parse(String(init.body)), updated_by: "admin@iitrpr.ac.in" },
      }),
    });
    renderAdmin();
    const gst = await screen.findByLabelText(/GST/);
    expect(gst).toHaveValue(18);

    await userEvent.clear(gst);
    await userEvent.type(gst, "120");
    await userEvent.type(screen.getByLabelText("Institute payment page"), "not-a-link");
    await userEvent.click(screen.getByRole("button", { name: "Save settings" }));
    expect(screen.getByText("GST can't be more than 100%.")).toBeInTheDocument();
    expect(screen.getByText(/starting with https/)).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === "PATCH")).toBe(false);

    await userEvent.clear(gst);
    await userEvent.type(gst, "12.5");
    await userEvent.clear(screen.getByLabelText("Institute payment page"));
    await userEvent.type(screen.getByLabelText("Institute payment page"), "https://pay.example.org");
    await userEvent.click(screen.getByRole("button", { name: "Save settings" }));
    expect(await screen.findByText("Settings saved.")).toBeInTheDocument();
    const patch = fetchMock.mock.calls.find(([, init]) => init?.method === "PATCH");
    expect(JSON.parse(String(patch?.[1]?.body))).toEqual({
      gst_pct: 12.5,
      cleaning_pct: 10,
      security_deposit: 5000,
      electricity_advance_pct: 80,
      payment_url: "https://pay.example.org",
    });
  });

  it("gives a staff role and won't let admins remove their own admin role", async () => {
    let rows: StaffRoleRow[] = [
      { id: 1, email: "admin@iitrpr.ac.in", role: "ADMIN", active: true, assigned_at: "2026-11-01T10:00:00Z", assigned_by: null },
    ];
    const fetchMock = mockApi({
      "GET /users/me": { body: ADMIN },
      "GET /admin/staff-roles": () => ({ body: rows }),
      "POST /admin/staff-roles": (init) => {
        const { email, role } = JSON.parse(String(init.body));
        const row: StaffRoleRow = {
          id: 2,
          email,
          role,
          active: true,
          assigned_at: "2026-11-03T10:00:00Z",
          assigned_by: "admin@iitrpr.ac.in",
        };
        rows = [...rows, row];
        return { status: 201, body: row };
      },
    });
    renderAdmin("roles");
    const mine = await screen.findByRole("button", { name: /Remove Admin role for admin@iitrpr.ac.in/ });
    expect(mine).toBeDisabled();

    await userEvent.type(screen.getByLabelText("Email"), "estate@iitrpr.ac.in");
    await userEvent.selectOptions(screen.getByLabelText("Role"), "ESTATE");
    await userEvent.click(screen.getByRole("button", { name: "Give role" }));
    const row = (await screen.findByText("estate@iitrpr.ac.in")).closest("tr")!;
    expect(within(row).getByText("Estate")).toBeInTheDocument();
    const post = fetchMock.mock.calls.find(([, init]) => init?.method === "POST");
    expect(JSON.parse(String(post?.[1]?.body))).toEqual({ email: "estate@iitrpr.ac.in", role: "ESTATE" });
  });

  it("lists failed emails and retries them", async () => {
    let failed = true;
    mockApi({
      "GET /users/me": { body: ADMIN },
      "GET /admin/emails": () => ({
        body: {
          max_attempts: 3,
          total: 1,
          items: [
            {
              id: 5, request_id: 9, event: "REQUEST_SUBMITTED", recipient: "events@company.com",
              subject: "[Facility Booking] Request FB-2026-004 received", status: failed ? "FAILED" : "SENT",
              attempt_count: failed ? 1 : 2, last_error: failed ? "ConnectionError: SMTP down" : null,
              created_at: "2026-11-03T10:00:00Z", last_attempt_at: "2026-11-03T10:00:00Z", sent_at: null,
            },
          ],
        },
      }),
      "POST /admin/emails/retry": () => {
        failed = false;
        return { body: { sent: 1, failed: 0, skipped: 0 } };
      },
    });
    renderAdmin("emails");
    expect(await screen.findByText("ConnectionError: SMTP down")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Retry failed emails" }));
    expect(await screen.findByText("Retried: 1 sent, 0 still failing.")).toBeInTheDocument();
    expect(await screen.findByText("2 tries")).toBeInTheDocument();
  });
});
