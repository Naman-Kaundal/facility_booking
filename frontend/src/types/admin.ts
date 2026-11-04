import type { FacilityGroup, RateCategory, Section, SlotUnit } from "./facility";
import type { StaffRole } from "./user";

export interface AdminSettings {
  gst_pct: number;
  cleaning_pct: number;
  security_deposit: number;
  electricity_advance_pct: number;
  payment_url: string | null;
  updated_at: string | null;
  updated_by: string | null;
}

export type SettingsPatch = Partial<Omit<AdminSettings, "updated_at" | "updated_by">>;

export interface StaffRoleRow {
  id: number;
  email: string;
  role: StaffRole;
  active: boolean;
  assigned_at: string;
  assigned_by: string | null;
}

export interface AdminTariff {
  id: number;
  category: RateCategory;
  unit: SlotUnit;
  amount: number;
  display_label: string;
  version: string;
  effective_from: string;
  effective_to: string | null;
  active: boolean;
  current: boolean;
}

export interface AdminSlot {
  id: number;
  slot_key: string;
  slot_type: SlotUnit;
  label: string;
  start: string | null;
  end: string | null;
  active: boolean;
}

export interface AdminFacility {
  id: number;
  code: string;
  name: string;
  group: FacilityGroup;
  section: Section;
  capacity: number | null;
  notes: string | null;
  active: boolean;
  sort_order: number;
  slot_types: SlotUnit[];
  slots: AdminSlot[];
  tariffs: AdminTariff[];
}

export interface TariffInput {
  facility_id: number;
  category: RateCategory;
  unit: SlotUnit;
  amount: number;
  effective_from: string;
}

export interface SlotPatch {
  label?: string;
  start?: string;
  end?: string;
  active?: boolean;
}

export type EmailStatus = "PENDING" | "SENT" | "FAILED";

export interface EmailLogRow {
  id: number;
  request_id: number | null;
  event: string;
  recipient: string;
  subject: string;
  status: EmailStatus;
  attempt_count: number;
  last_error: string | null;
  created_at: string;
  last_attempt_at: string | null;
  sent_at: string | null;
}

export interface EmailLogList {
  items: EmailLogRow[];
  total: number;
  max_attempts: number;
}

export interface AdminAuditRow {
  id: number;
  actor_email: string;
  action: string;
  entity: string;
  entity_id: string | null;
  details: string | null;
  created_at: string;
}
