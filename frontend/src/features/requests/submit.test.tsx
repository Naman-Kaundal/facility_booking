import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "../../auth/AuthContext";
import { meBody, mockApi } from "../../test/mockApi";
import type { BookingRequest } from "../../types/request";
import { RequestDetailPage } from "./RequestDetailPage";
import { ReviewSubmitPage } from "./ReviewSubmitPage";

afterEach(() => vi.unstubAllGlobals());

function draft(overrides: Partial<BookingRequest> = {}): BookingRequest {
  return {
    id: 5,
    ref_no: null,
    status: "DRAFT",
    editable: true,
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
        id: 11,
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
        decision: "PENDING",
        decision_remark: null,
        decided_by_name: null,
        decided_at: null,
      },
    ],
    charges_preview: { category: "PRIVATE", booking_subtotal: 15000, lines_without_rate: 0, is_final: false, note: "Indicative." },
    created_at: "2026-10-29T10:00:00Z",
    updated_at: "2026-10-29T10:00:00Z",
    submitted_at: null,
    rate_category_snapshot: null,
    terms_version: null,
    return_reason: null,
    returned_at: null,
    ...overrides,
  };
}

const TERMS = { version: "v1-placeholder", text: "1. Be nice.", is_placeholder: true };

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <Routes>
          <Route path="/requests/:id" element={<RequestDetailPage />} />
          <Route path="/requests/:id/review" element={<ReviewSubmitPage />} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("ReviewSubmitPage", () => {
  it("needs the terms accepted, then submits with the terms version", async () => {
    let current = draft();
    const fetchMock = mockApi({
      "GET /users/me": { body: meBody() },
      "GET /requests/terms": { body: TERMS },
      "GET /requests/5": () => ({ body: current }),
      "GET /requests/5/events": { body: [] },
      "POST /requests/5/submit": () => {
        current = draft({ status: "SUBMITTED", editable: false, ref_no: "FB-2026-001", submitted_at: "2026-10-29T10:05:00Z" });
        return { body: current };
      },
    });
    renderAt("/requests/5/review");

    const submit = await screen.findByRole("button", { name: "Submit to Facilities" });
    expect(submit).toBeDisabled();
    expect(screen.getByText("1. Be nice.")).toBeInTheDocument();

    await userEvent.click(screen.getByLabelText(/I have read and accept/));
    await userEvent.click(submit);

    expect(await screen.findByText(/Your reference number is/)).toHaveTextContent("FB-2026-001");
    const post = fetchMock.mock.calls.find(([, init]) => init?.method === "POST");
    expect(JSON.parse(String(post?.[1]?.body))).toEqual({ terms_accepted: true, terms_version: "v1-placeholder" });
  });

  it("shows the server's reason when submission is refused", async () => {
    mockApi({
      "GET /users/me": { body: meBody() },
      "GET /requests/terms": { body: TERMS },
      "GET /requests/5": { body: draft() },
      "POST /requests/5/submit": {
        status: 409,
        body: { error: { code: "SLOT_UNAVAILABLE", message: "LHC Classroom M5 is already booked.", details: {} } },
      },
    });
    renderAt("/requests/5/review");
    await userEvent.click(await screen.findByLabelText(/I have read and accept/));
    await userEvent.click(screen.getByRole("button", { name: "Submit to Facilities" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("already booked");
  });
});

describe("RequestDetailPage after submission", () => {
  it("shows the reference, each line's decision and the timeline", async () => {
    const submitted = draft({
      status: "WITH_SECTION",
      editable: false,
      ref_no: "FB-2026-007",
      submitted_at: "2026-10-29T10:05:00Z",
      rate_category_snapshot: "PRIVATE",
    });
    submitted.lines[0] = { ...submitted.lines[0], decision: "REJECTED", decision_remark: "Exams that week" };
    mockApi({
      "GET /users/me": { body: meBody() },
      "GET /requests/5": { body: submitted },
      "GET /requests/5/events": {
        body: [
          {
            id: 1, event_type: "SUBMITTED", label: "Request submitted", from_status: "DRAFT", to_status: "SUBMITTED",
            actor_name: "Asha Rao", actor_role: "REQUESTER", remark: null, line: null, created_at: "2026-10-29T10:05:00Z",
          },
        ],
      },
    });
    renderAt("/requests/5");
    expect(await screen.findByText("FB-2026-007")).toBeInTheDocument();
    expect(screen.getByText("Rejected")).toBeInTheDocument();
    expect(screen.getByText(/Exams that week/)).toBeInTheDocument();
    expect(await screen.findByText("Request submitted")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Review and submit/ })).not.toBeInTheDocument();
  });

  it("asks for corrections when Facilities returned the request", async () => {
    mockApi({
      "GET /users/me": { body: meBody() },
      "GET /requests/5": {
        body: draft({
          status: "RETURNED",
          ref_no: "FB-2026-003",
          submitted_at: "2026-10-29T10:05:00Z",
          return_reason: "Add the full address",
        }),
      },
      "GET /requests/5/events": { body: [] },
    });
    renderAt("/requests/5");
    expect(await screen.findByRole("alert")).toHaveTextContent("Add the full address");
    expect(screen.getByRole("link", { name: "Review and resubmit" })).toHaveAttribute("href", "/requests/5/review");
  });
});
