import { apiGet } from "./client";
import type { Availability } from "../types/availability";

export const getAvailability = (facilityId: number, date: string) =>
  apiGet<Availability>(`/availability?facility_id=${facilityId}&date=${encodeURIComponent(date)}`);
