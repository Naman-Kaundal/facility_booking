import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AuthProvider } from "../../auth/AuthContext";
import { RequireRole } from "../../auth/RequireRole";
import { meBody, mockApi } from "../../test/mockApi";
import type { BookingRequest, RequestLine } from "../../types/request";
import type { StaffRequest } from "../../types/workflow";
import { DeskQueuePage } from "./DeskQueuePage";
import { StaffRequestPage } from "./StaffRequestPage";

afterEach(() => vi.unstubAllGlobals());

function line(overrides: Partial<RequestLine>): RequestLine {
  return {
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
    decision: "PENDING",
    decision_remark: null,
    decided_by_name: null,
    decided_at: null,
    ...overrides,
  };
}

function staffView(overrides: Partial<StaffRequest> = {}, req: Partial<BookingRequest> = {}): StaffRequest {
  return {
    request: {
      id: 9,
      ref_no: "FB-2026-004",
      status: "SUBMITTED",
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
      lines: [line({ id: 1 }), line({ id: 2, facility_name: "Cricket ground", section: "SPORTS" })],
      charges_preview: { category: "PRIVATE", booking_subtotal: 30000, lines_without_rate: 0, is_final: false, note: "" },
      created_at: "2026-10-29T10:00:00Z",
      updated_at: "2026-10-29T10:00:00Z",
      submitted_at: "2026-10-29T10:05:00Z",
      rate_category_snapshot: "PRIVATE",
      terms_version: "v1-placeholder",
      return_reason: null,
      returned_at: null,
      ...req,
    },
    requester_name: "Asha Rao",
    requester_email: "events@company.com",
    timeline: [],
    can_forward: true,
    can_return: true,
    decidable_line_ids: [],
    ...overrides,
  };
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <Routes>
          <Route
            path="/desk/facilities"
            element={
              <RequireRole roles={["FACILITY"]}>
                <DeskQueuePage desk="FACILITY" />
              </RequireRole>
            }
          />
          <Route
            path="/desk/requests/:id"
            element={
              <RequireRole roles={["FACILITY", "ACADEMIC", "SPORTS"]}>
                <StaffRequestPage />
              </RequireRole>
            }
          />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe("staff desks", () => {
  it("hides a desk from people without the role", async () => {
    mockApi({ "GET /users/me": { body: meBody({ roles: [] }) } });
    renderAt("/desk/facilities");
    expect(await screen.findByText("Staff only")).toBeInTheDocument();
  });

  it("lists submitted requests on the Facilities desk", async () => {
    mockApi({
      "GET /users/me": { body: meBody({ roles: ["FACILITY"] }) },
      "GET /workflow/queue": {
        body: {
          desk: "FACILITY",
          total: 1,
          items: [
            {
              id: 9, ref_no: "FB-2026-004", status: "SUBMITTED", purpose: "Annual conference", applicant_name: "R. Mehta",
              organisation: "North Zone", requester_email: "events@company.com", rate_category: "PRIVATE",
              submitted_at: "2026-10-29T10:05:00Z", line_count: 2, pending_lines: 0, sections: ["ACADEMIC", "SPORTS"],
              first_date: "2026-11-20",
            },
          ],
        },
      },
    });
    renderAt("/desk/facilities");
    const link = await screen.findByRole("link", { name: "FB-2026-004" });
    expect(link).toHaveAttribute("href", "/desk/requests/9?desk=FACILITY");
    expect(screen.getByText("Academic section, Sports section")).toBeInTheDocument();
  });

  it("returns a request with a reason", async () => {
    const fetchMock = mockApi({
      "GET /users/me": { body: meBody({ roles: ["FACILITY"] }) },
      "GET /workflow/requests/9": { body: staffView() },
      "POST /requests/9/return": {
        body: staffView({ can_forward: false, can_return: false }, { status: "RETURNED", return_reason: "Add address" }),
      },
    });
    renderAt("/desk/requests/9");
    await userEvent.click(await screen.findByRole("button", { name: "Return for correction" }));
    await userEvent.click(screen.getByRole("button", { name: "Confirm return" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Say what the requester needs to correct");

    await userEvent.type(screen.getByLabelText("What needs correcting"), "Add address");
    await userEvent.click(screen.getByRole("button", { name: "Confirm return" }));
    expect(await screen.findByText("Returned to the requester.")).toBeInTheDocument();
    const post = fetchMock.mock.calls.find(([, init]) => init?.method === "POST");
    expect(JSON.parse(String(post?.[1]?.body))).toEqual({ reason: "Add address" });
    expect(screen.queryByRole("button", { name: "Forward to sections" })).not.toBeInTheDocument();
  });

  it("lets a section decide only its own lines and needs a remark to reject", async () => {
    const fetchMock = mockApi({
      "GET /users/me": { body: meBody({ roles: ["ACADEMIC"] }) },
      "GET /workflow/requests/9": {
        body: staffView({ can_forward: false, can_return: false, decidable_line_ids: [1] }, { status: "WITH_SECTION" }),
      },
      "POST /requests/9/decision": {
        body: staffView(
          { can_forward: false, can_return: false },
          {
            status: "WITH_SECTION",
            lines: [
              line({ id: 1, decision: "REJECTED", decision_remark: "Exams", decided_by_name: "Dr. Singh" }),
              line({ id: 2, facility_name: "Cricket ground", section: "SPORTS" }),
            ],
          },
        ),
      },
    });
    renderAt("/desk/requests/9");
    const forms = await screen.findAllByRole("form");
    expect(forms).toHaveLength(1); // only the Academic line, not the Sports one
    const form = within(forms[0]);
    expect(forms[0]).toHaveAccessibleName(/^Decision for LHC Classroom M5 on /);

    await userEvent.click(form.getByRole("button", { name: "Reject" }));
    expect(form.getByRole("alert")).toHaveTextContent("Give a reason");

    await userEvent.type(form.getByLabelText("Remark"), "Exams");
    await userEvent.click(form.getByRole("button", { name: "Reject" }));
    expect(await screen.findByText("Line rejected.")).toBeInTheDocument();
    expect(screen.getByText("Rejected")).toBeInTheDocument();
    const post = fetchMock.mock.calls.find(([, init]) => init?.method === "POST");
    expect(JSON.parse(String(post?.[1]?.body))).toEqual({ line_id: 1, decision: "REJECTED", remark: "Exams" });
  });
});
