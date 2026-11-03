import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "../../auth/AuthContext";
import { meBody, mockApi } from "../../test/mockApi";
import { validateEvent } from "./EventDetailsForm";
import { MyRequestsPage } from "./MyRequestsPage";
import { NewRequestPage } from "./NewRequestPage";

afterEach(() => vi.unstubAllGlobals());

const VALID = {
  organisation_name_address: "North Zone Education Society",
  applicant_name: "R. Mehta",
  office_contact: "0172-2345678",
  mobile: "+91 98765 43210",
  purpose: "Annual conference",
  participants: "180",
};

describe("validateEvent", () => {
  it("accepts a complete form", () => {
    expect(validateEvent(VALID)).toEqual({});
  });

  it("flags blank fields, bad phone numbers and non-positive participants", () => {
    const errors = validateEvent({ ...VALID, applicant_name: "  ", mobile: "call me", participants: "0" });
    expect(Object.keys(errors).sort()).toEqual(["applicant_name", "mobile", "participants"]);
    expect(validateEvent({ ...VALID, participants: "2.5" }).participants).toMatch(/whole number/);
  });
});

function renderPage(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <Routes>
          <Route path="/requests" element={<MyRequestsPage />} />
          <Route path="/requests/new" element={<NewRequestPage />} />
          <Route path="/requests/:id/facilities" element={<p>Step 2 page</p>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("MyRequestsPage", () => {
  it("lists the user's requests", async () => {
    mockApi({
      "GET /users/me": { body: meBody() },
      "GET /requests": {
        body: {
          total: 1,
          items: [
            {
              id: 7,
              ref_no: null,
              status: "DRAFT",
              purpose: "Annual conference",
              facility_summary: "LHC Classroom M5, Football Ground",
              line_count: 2,
              first_date: "2026-11-05",
              created_at: "2026-10-26T10:00:00Z",
              updated_at: "2026-10-26T10:00:00Z",
            },
          ],
        },
      },
    });
    renderPage("/requests");
    const row = (await screen.findByText("Annual conference")).closest("tr")!;
    expect(within(row).getByText("Draft")).toBeInTheDocument();
    expect(within(row).getByText("Not submitted")).toBeInTheDocument();
    expect(within(row).getByText("LHC Classroom M5, Football Ground")).toBeInTheDocument();
    expect(within(row).getByRole("link", { name: /view request/i })).toHaveAttribute("href", "/requests/7");
  });

  it("shows an empty state", async () => {
    mockApi({ "GET /users/me": { body: meBody() }, "GET /requests": { body: { total: 0, items: [] } } });
    renderPage("/requests");
    expect(await screen.findByText(/haven't started any requests/i)).toBeInTheDocument();
  });
});

describe("NewRequestPage", () => {
  it("creates a draft and moves to the facilities step", async () => {
    const fetchMock = mockApi({
      "GET /users/me": { body: meBody() },
      "POST /requests": { status: 201, body: { id: 42 } },
    });
    renderPage("/requests/new");

    expect(await screen.findByLabelText("Name of person booking")).toHaveValue("Asha Rao");
    expect(screen.getByLabelText("Email")).toHaveValue("events@company.com");

    await userEvent.type(screen.getByLabelText("Organisation name and address"), VALID.organisation_name_address);
    await userEvent.type(screen.getByLabelText("Office contact"), VALID.office_contact);
    await userEvent.type(screen.getByLabelText("Mobile"), VALID.mobile);
    await userEvent.type(screen.getByLabelText("Purpose / details of the event"), VALID.purpose);
    await userEvent.type(screen.getByLabelText("Number of participants"), "180");
    await userEvent.click(screen.getByRole("button", { name: "Save and add facilities" }));

    expect(await screen.findByText("Step 2 page")).toBeInTheDocument();
    const post = fetchMock.mock.calls.find(([, init]) => init?.method === "POST");
    expect(JSON.parse(String(post?.[1]?.body))).toEqual({
      ...VALID,
      applicant_name: "Asha Rao",
      participants: 180,
    });
  });

  it("does not submit an incomplete form", async () => {
    const fetchMock = mockApi({ "GET /users/me": { body: meBody() } });
    renderPage("/requests/new");
    await userEvent.click(await screen.findByRole("button", { name: "Save and add facilities" }));
    expect(screen.getAllByText("This field is required.").length).toBeGreaterThan(0);
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === "POST")).toBe(false);
  });
});
