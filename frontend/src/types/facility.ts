export type RateCategory = "IIT" | "GOVT" | "PRIVATE";
export type SlotUnit = "FULL_DAY" | "HALF_DAY" | "PER_DAY" | "THREE_HOUR";
export type FacilityGroup = "LHC" | "AUDITORIUM" | "SPORTS";
export type Section = "ACADEMIC" | "SPORTS";

export interface Tariff {
  category: RateCategory;
  unit: SlotUnit;
  amount: number;
  display_label: string;
}

export interface SlotOption {
  slot_key: string;
  label: string;
  slot_type: SlotUnit;
  start: string | null;
  end: string | null;
}

export interface Facility {
  id: string;
  code: string;
  name: string;
  group: FacilityGroup;
  section: Section;
  capacity: number | null;
  slot_types: SlotUnit[];
  slot_options: SlotOption[];
  tariffs: Tariff[];
  notes: string | null;
  active: boolean;
}

export interface FacilityList {
  items: Facility[];
  total: number;
}

export interface Health {
  status: "ok" | "degraded";
  database: "ok" | "unreachable";
  environment: string;
}
