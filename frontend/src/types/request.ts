import type { RateCategory, Section, SlotUnit } from "./facility";

export type RequestStatus =
  | "DRAFT"
  | "SUBMITTED"
  | "RETURNED"
  | "WITH_SECTION"
  | "REJECTED"
  | "WITH_ESTATE"
  | "COSTED"
  | "ADVANCE_INTIMATED";

export interface EventDetailsInput {
  organisation_name_address: string;
  applicant_name: string;
  office_contact: string;
  mobile: string;
  purpose: string;
  participants: number;
}

export interface EventDetails extends EventDetailsInput {
  contact_email: string;
}

export interface RatePreview {
  category: RateCategory;
  unit: SlotUnit;
  amount: number;
  display_label: string;
}

export type LineDecision = "PENDING" | "CONFIRMED" | "REJECTED";

export interface RequestLine {
  id: number;
  facility_id: number;
  facility_code: string;
  facility_name: string;
  section: Section;
  booking_date: string; // YYYY-MM-DD
  slot_key: string;
  slot_label: string;
  slot_type: SlotUnit;
  start: string | null;
  end: string | null;
  rate: RatePreview | null;
  decision: LineDecision;
  decision_remark: string | null;
  decided_by_name: string | null;
  decided_at: string | null;
}

export interface ChargesPreview {
  category: RateCategory | null;
  booking_subtotal: number;
  lines_without_rate: number;
  is_final: boolean;
  note: string;
}

export interface BookingRequest {
  id: number;
  ref_no: string | null;
  status: RequestStatus;
  editable: boolean;
  event: EventDetails;
  lines: RequestLine[];
  charges_preview: ChargesPreview;
  created_at: string;
  updated_at: string;
  submitted_at: string | null;
  rate_category_snapshot: RateCategory | null;
  terms_version: string | null;
  return_reason: string | null;
  returned_at: string | null;
}

export interface RequestSummary {
  id: number;
  ref_no: string | null;
  status: RequestStatus;
  purpose: string;
  facility_summary: string;
  line_count: number;
  first_date: string | null;
  created_at: string;
  updated_at: string;
}

export interface RequestList {
  items: RequestSummary[];
  total: number;
}

export interface LineInput {
  facility_id: number;
  booking_date: string;
  slot_key: string;
}

export interface Terms {
  version: string;
  text: string;
  is_placeholder: boolean;
}

export interface TimelineEvent {
  id: number;
  event_type: string;
  label: string;
  from_status: string | null;
  to_status: string | null;
  actor_name: string;
  actor_role: string | null;
  remark: string | null;
  line: string | null;
  created_at: string;
}
