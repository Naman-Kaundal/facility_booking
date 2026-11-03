import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { FacilityCatalogue } from "./FacilityCatalogue";
import type { Facility } from "../../types/facility";

const facilities: Facility[] = [
  {
    id: "1",
    code: "M5",
    name: "LHC Classroom M5",
    group: "LHC",
    section: "ACADEMIC",
    capacity: 150,
    slot_types: ["FULL_DAY"],
    slot_options: [{ slot_key: "FULL_DAY", label: "Full day", slot_type: "FULL_DAY", start: null, end: null }],
    tariffs: [
      { category: "PRIVATE", unit: "FULL_DAY", amount: 15000, display_label: "₹15,000 / full day" },
      { category: "GOVT", unit: "FULL_DAY", amount: 10000, display_label: "₹10,000 / full day" },
      { category: "IIT", unit: "FULL_DAY", amount: 7000, display_label: "₹7,000 / full day" },
    ],
    notes: null,
    active: true,
  },
  {
    id: "2",
    code: "FOOTBALL",
    name: "Football Ground",
    group: "SPORTS",
    section: "SPORTS",
    capacity: null,
    slot_types: ["THREE_HOUR"],
    slot_options: [
      { slot_key: "09:00-12:00", label: "09:00–12:00", slot_type: "THREE_HOUR", start: "09:00", end: "12:00" },
      { slot_key: "12:00-15:00", label: "12:00–15:00", slot_type: "THREE_HOUR", start: "12:00", end: "15:00" },
    ],
    tariffs: [
      { category: "PRIVATE", unit: "THREE_HOUR", amount: 3000, display_label: "₹3,000 / 3 hours" },
      { category: "GOVT", unit: "THREE_HOUR", amount: 2500, display_label: "₹2,500 / 3 hours" },
      { category: "IIT", unit: "THREE_HOUR", amount: 0, display_label: "No charges" },
    ],
    notes: null,
    active: true,
  },
];

function mockFetchOnce(status: number, body: unknown) {
  vi.mocked(globalThis.fetch).mockResolvedValueOnce(
    new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } }),
  );
}

describe("FacilityCatalogue", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders facilities loaded from the API", async () => {
    mockFetchOnce(200, { items: facilities, total: 2 });
    render(<FacilityCatalogue />);

    expect(screen.getByRole("status")).toHaveTextContent("Loading facilities");
    const cards = await screen.findAllByTestId("facility-card");
    expect(cards).toHaveLength(2);

    const m5 = within(cards[0]);
    expect(m5.getByRole("heading", { name: "LHC Classroom M5" })).toBeInTheDocument();
    expect(m5.getByText("150 seats")).toBeInTheDocument();
    expect(m5.getByText("₹15,000")).toBeInTheDocument();

    const football = within(cards[1]);
    expect(football.getByText("No charges")).toBeInTheDocument();
    expect(football.getByText("09:00–12:00")).toBeInTheDocument();

    expect(globalThis.fetch).toHaveBeenCalledWith(
      expect.stringContaining("/facilities?active=true"),
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("filters by facility group", async () => {
    mockFetchOnce(200, { items: facilities, total: 2 });
    render(<FacilityCatalogue />);
    await screen.findAllByTestId("facility-card");

    await userEvent.click(screen.getByRole("button", { name: "Sports grounds" }));
    const cards = screen.getAllByTestId("facility-card");
    expect(cards).toHaveLength(1);
    expect(within(cards[0]).getByRole("heading")).toHaveTextContent("Football Ground");
    expect(screen.getByRole("button", { name: "Sports grounds" })).toHaveAttribute("aria-pressed", "true");
  });

  it("shows the backend error message and retries", async () => {
    mockFetchOnce(503, { error: { code: "DB_DOWN", message: "Database unavailable.", details: {} } });
    render(<FacilityCatalogue />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Database unavailable.");

    mockFetchOnce(200, { items: facilities, total: 2 });
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findAllByTestId("facility-card")).toHaveLength(2);
  });

  it("shows an empty state when there are no facilities", async () => {
    mockFetchOnce(200, { items: [], total: 0 });
    render(<FacilityCatalogue />);
    expect(await screen.findByText(/No facilities are available/)).toBeInTheDocument();
  });
});
