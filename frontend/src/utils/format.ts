import type { FacilityGroup, RateCategory, Section, SlotUnit } from "../types/facility";
import type { LineDecision, RequestStatus } from "../types/request";

const inr = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });

export function formatInr(amount: number): string {
  return amount === 0 ? "No charges" : inr.format(amount);
}

const inrPaise = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

/** Calculated amounts (GST, advance…) with paise: ₹30,040.00 */
export function formatMoney(amount: number): string {
  return inrPaise.format(amount);
}

/** "18" or "12.5" for percentages. */
export function formatPct(value: number): string {
  return `${Number(value.toFixed(2))}%`;
}

/** Money total, where 0 should read as ₹0 rather than "No charges". */
export function formatTotal(amount: number): string {
  return inr.format(amount);
}

/** "2026-11-05" -> "Thu, 5 Nov 2026" (dates are calendar dates, so no timezone shifting). */
export function formatDate(isoDate: string): string {
  const [y, m, d] = isoDate.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("en-IN", {
    weekday: "short",
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Kolkata" });
}

/** Today's date in India as YYYY-MM-DD (for <input type="date" min=…>). */
export function todayInIndia(): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata" }).format(new Date());
}

export const CATEGORY_LABELS: Record<RateCategory, string> = {
  PRIVATE: "Private / outside agencies",
  GOVT: "Govt. / Semi Govt. / PSU",
  IIT: "IIT Ropar",
};

export const CATEGORY_SHORT: Record<RateCategory, string> = {
  PRIVATE: "Private",
  GOVT: "Govt / PSU",
  IIT: "IIT Ropar",
};

export const UNIT_LABELS: Record<SlotUnit, string> = {
  FULL_DAY: "Full day",
  HALF_DAY: "Half day",
  PER_DAY: "Per day",
  THREE_HOUR: "3-hour slot",
};

export const GROUP_LABELS: Record<FacilityGroup, string> = {
  LHC: "Lecture Hall Complex",
  AUDITORIUM: "Auditorium",
  SPORTS: "Sports grounds",
};

export const SECTION_LABELS: Record<Section, string> = {
  ACADEMIC: "Academic section",
  SPORTS: "Sports section",
};

export const STATUS_LABELS: Record<RequestStatus, string> = {
  DRAFT: "Draft",
  SUBMITTED: "Submitted",
  RETURNED: "Returned for correction",
  WITH_SECTION: "With section",
  REJECTED: "Rejected",
  WITH_ESTATE: "With Estate",
  COSTED: "Costed",
  ADVANCE_INTIMATED: "Advance intimated",
};

export const DECISION_LABELS: Record<LineDecision, string> = {
  PENDING: "Awaiting decision",
  CONFIRMED: "Confirmed",
  REJECTED: "Rejected",
};

/** What each status means for the requester, in plain words. */
export const STATUS_HELP: Partial<Record<RequestStatus, string>> = {
  SUBMITTED: "Facilities is checking your request.",
  RETURNED: "Facilities has sent this back for correction. Edit it and submit again.",
  WITH_SECTION: "The Academic and/or Sports section is deciding on each facility.",
  REJECTED: "None of the facilities could be approved.",
  WITH_ESTATE: "All sections have decided. Next, Estate adds the electricity estimate and Facilities works out the costs.",
  COSTED: "The costs have been calculated. Facilities will send you the advance to pay.",
  ADVANCE_INTIMATED: "Pay the advance below through the institute payment page to complete the booking.",
};
