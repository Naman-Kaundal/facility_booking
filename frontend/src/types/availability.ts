import type { SlotUnit } from "./facility";

export interface SlotAvailability {
  slot_key: string;
  label: string;
  slot_type: SlotUnit;
  start: string | null;
  end: string | null;
  available: boolean;
  unavailable_reason: string | null;
}

export interface Availability {
  facility_id: number;
  date: string;
  slots: SlotAvailability[];
}
