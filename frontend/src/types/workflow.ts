import type { BookingRequest, TimelineEvent } from "./request";
import type { Section } from "./facility";

export type Desk = "FACILITY" | "ACADEMIC" | "SPORTS";

export interface QueueItem {
  id: number;
  ref_no: string | null;
  status: string;
  purpose: string;
  applicant_name: string;
  organisation: string;
  requester_email: string;
  rate_category: string | null;
  submitted_at: string | null;
  line_count: number;
  /** Lines this desk still has to decide (Academic/Sports); 0 on the Facilities desk. */
  pending_lines: number;
  sections: Section[];
  first_date: string | null;
}

export interface Queue {
  desk: Desk;
  items: QueueItem[];
  total: number;
}

export interface StaffRequest {
  request: BookingRequest;
  requester_name: string;
  requester_email: string;
  timeline: TimelineEvent[];
  /** What this staff member may do now. Only for showing buttons; the server re-checks every action. */
  can_forward: boolean;
  can_return: boolean;
  decidable_line_ids: number[];
}

export interface DecisionInput {
  line_id: number;
  decision: "CONFIRMED" | "REJECTED";
  remark?: string;
}
