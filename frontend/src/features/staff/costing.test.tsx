import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "../../auth/AuthContext";
import { RequireRole } from "../../auth/RequireRole";
import { meBody, mockApi } from "../../test/mockApi";
import type { CostBreakdown } from "../../types/costs";
import type { BookingRequest, RequestStatus } from "../../types/request";
import type { StaffRequest } from "../../types/workflow";
import { RequestDetailPage } from "../requests/RequestDetailPage";
import { StaffRequestPage } from "./StaffRequestPage";

afterEach(() => vi.unstubAllGlobals());

const COSTS: CostBreakdown = {
  items: [{ line_id: 1, facility_name: "LHC Classroom M5", booking_date: "2026-11-20", slot_label: "Full day", amount: 15000 }],
  booking_subtotal: 15000,
  gst_pct: 18,
  gst_amount: 2700,
  cleaning_pct: 10,
  cleaning_amount: 1500,
  security_deposit: 5000,
  electricity_estimate: 2500,
  electricity_advance_pct: 80,
  electricity_advance: 2000,
  total_estimated_cost: 26700,
  advance_amount: 26200,
  estimate_remark: "AC for 8 hours",
  calculated_at: "2026-11-03T10:00:00Z",
  calculated_by_name: "Estate Desk",
  intimated_at: null,
  payment_url: null,
  is_final: false,
};

function request(status: RequestStatus, costs: CostBreakdown | null): BookingRequest {
  return {
    id: 9,
    ref_no: "FB-2026-004",
    status,
    editable: false,
    event: {
      organisation_name_address: "North Zone Education Society",
      applicant_name: "R. Mehta",
      contact_email: "events@company.com",
      office_contact: "0172-2345678",
      mobile: "+91 98765 43210",
      purpose: "Annual conference",
      participants: 180,
    },
    lines: [
      {
        id: 1,
        facility_id: 3,
        facility_code: "M5",
        facility_name: "LHC Classroom M5",
        section: "ACADEMIC",
        booking_date: "2026-11-20",
        slot_key: "FULL_DAY",
        slot_label: "Full day",
        slot_type: "FULL_DAY",
        start: null,
        end: null,
        rate: { category: "PRIVATE", unit: "FULL_DAY", amount: 15000, display_label: "₹15,000 / full day" },
        decision: "CONFIRMED",
        decision_remark: null,
        decided_by_name: "Academic Desk",
        decided_at: "2026-11-02T10:00:00Z",
      },
    ],
    charges_preview: { category: "PRIVATE", booking_subtotal: 15000, lines_without_rate: 0, is_final: false, note: "" },
    created_at: "2026-11-01T10:00:00Z",
    updated_at: "2026-11-03T10:00:00Z",
    submitted_at: "2026-11-01T10:05:00Z",
    rate_category_snapshot: "PRIVATE",
    terms_version: "v1-placeholder",
    return_reason: null,
    returned_at: null,
    costs,
  };
}

function staffView(status: RequestStatus, costs: CostBreakdown | null, extra: Partial<StaffRequest> = {}): StaffRequest {
  return {
    request: request(status, costs),
    requester_name: "Asha Rao",
    requester_email: "events@company.com",
    timeline: [],
    can_forward: false,
    can_return: false,
    decidable_line_ids: [],
    can_enter_electricity: false,
    can_intimate: false,
    payment_url_configured: false,
    ...extra,
  };
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <Routes>
          <Route path="/requests/:id" element={<RequestDetailPage />} />
          <Route
            path="/desk/requests/:id"
            element={
              <RequireRole roles={["FACILITY", "ESTATE"]}>
                <StaffRequestPage />
              </RequireRole>
            }
          />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("Estate desk", () => {
  it("sends only the electricity estimate and shows the server's breakdown", async () => {
    const fetchMock = mockApi({
      "GET /users/me": { body: meBody({ roles: ["ESTATE"] }) },
      "GET /workflow/requests/9": { body: staffView("WITH_ESTATE", null, { can_enter_electricity: true }) },
      "POST /requests/9/electricity": { body: staffView("COSTED", COSTS, { can_enter_electricity: true }) },
    });
    renderAt("/desk/requests/9");

    const amount = await screen.findByLabelText("Amount (₹)");
    await userEvent.click(screen.getByRole("button", { name: "Submit estimate" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Enter the estimate");

    await userEvent.type(amount, "2500");
    await userEvent.type(screen.getByLabelText("Note (optional)"), "AC for 8 hours");
    await userEvent.click(screen.getByRole("button", { name: "Submit estimate" }));

    expect(await screen.findByText(/costs have been calculated/)).toBeInTheDocument();
    const post = fetchMock.mock.calls.find(([, init]) => init?.method === "POST");
    // No GST, deposit or advance in the request: the server calculates them.
    expect(JSON.parse(String(post?.[1]?.body))).toEqual({ electricity_estimate: 2500, remark: "AC for 8 hours" });
    expect(screen.getByText("₹26,200.00")).toBeInTheDocument(); // advance
    expect(screen.getByText("₹2,700.00")).toBeInTheDocument(); // GST
    expect(screen.getByRole("button", { name: "Recalculate costs" })).toBeInTheDocument();
    // Estate never sees the Facilities intimation controls.
    expect(screen.queryByRole("button", { name: /advance intimation/ })).not.toBeInTheDocument();
  });
});

describe("Facilities advance intimation", () => {
  it("warns when the payment link isn't configured", async () => {
    mockApi({
      "GET /users/me": { body: meBody({ roles: ["FACILITY"] }) },
      "GET /workflow/requests/9": { body: staffView("COSTED", COSTS) },
    });
    renderAt("/desk/requests/9");
    expect(await screen.findByText(/payment link isn't set yet/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Send advance intimation" })).not.toBeInTheDocument();
  });

  it("confirms, then sends the intimation", async () => {
    const sent = { ...COSTS, intimated_at: "2026-11-03T11:00:00Z", payment_url: "https://pay.example.org", is_final: true };
    const fetchMock = mockApi({
      "GET /users/me": { body: meBody({ roles: ["FACILITY"] }) },
      "GET /workflow/requests/9": {
        body: staffView("COSTED", COSTS, { can_intimate: true, payment_url_configured: true }),
      },
      "POST /requests/9/intimate": { body: staffView("ADVANCE_INTIMATED", sent, { payment_url_configured: true }) },
    });
    renderAt("/desk/requests/9");
    await userEvent.click(await screen.findByRole("button", { name: "Send advance intimation" }));
    await userEvent.type(screen.getByLabelText(/Message to the requester/), "Pay within 7 days");
    await userEvent.click(screen.getByRole("button", { name: "Send ₹26,200.00 advance intimation" }));

    expect(await screen.findByText("Advance intimation sent to the requester.")).toBeInTheDocument();
    const post = fetchMock.mock.calls.find(([, init]) => init?.method === "POST");
    expect(JSON.parse(String(post?.[1]?.body))).toEqual({ remark: "Pay within 7 days" });
    expect(screen.getByRole("link", { name: "https://pay.example.org" })).toBeInTheDocument();
  });
});

describe("Requester after the advance intimation", () => {
  it("shows the final breakdown and the payment link", async () => {
    const final = { ...COSTS, intimated_at: "2026-11-03T11:00:00Z", payment_url: "https://pay.example.org", is_final: true };
    mockApi({
      "GET /users/me": { body: meBody() },
      "GET /requests/9": { body: request("ADVANCE_INTIMATED", final) },
      "GET /requests/9/events": { body: [] },
    });
    renderAt("/requests/9");
    const link = await screen.findByRole("link", { name: "Open the institute payment page" });
    expect(link).toHaveAttribute("href", "https://pay.example.org");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
    expect(screen.getByText("Final cost breakdown")).toBeInTheDocument();
    expect(screen.getAllByText("₹26,200.00").length).toBeGreaterThan(0);
  });

  it("shows no costs before then", async () => {
    mockApi({
      "GET /users/me": { body: meBody() },
      "GET /requests/9": { body: request("COSTED", null) },
      "GET /requests/9/events": { body: [] },
    });
    renderAt("/requests/9");
    expect(await screen.findByText(/Facilities will send you the advance/)).toBeInTheDocument();
    expect(screen.queryByText("Final cost breakdown")).not.toBeInTheDocument();
  });
});
