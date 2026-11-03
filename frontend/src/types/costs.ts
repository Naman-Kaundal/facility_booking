export interface CostItem {
  line_id: number;
  facility_name: string;
  booking_date: string;
  slot_label: string;
  amount: number;
}

/** Calculated by the backend only (never in the browser). */
export interface CostBreakdown {
  items: CostItem[];
  booking_subtotal: number;
  gst_pct: number;
  gst_amount: number;
  cleaning_pct: number;
  cleaning_amount: number;
  security_deposit: number;
  electricity_estimate: number;
  electricity_advance_pct: number;
  electricity_advance: number;
  total_estimated_cost: number;
  advance_amount: number;
  estimate_remark: string | null;
  calculated_at: string;
  calculated_by_name: string | null;
  intimated_at: string | null;
  /** Only set once Facilities has sent the advance intimation. */
  payment_url: string | null;
  is_final: boolean;
}
