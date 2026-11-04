import type {
  AdminAuditRow,
  AdminFacility,
  AdminSettings,
  EmailLogList,
  EmailStatus,
  SettingsPatch,
  SlotPatch,
  StaffRoleRow,
  TariffInput,
} from "../types/admin";
import type { StaffRole } from "../types/user";
import { apiGet, apiRequest } from "./client";

export const getSettings = () => apiGet<AdminSettings>("/admin/settings");
export const updateSettings = (patch: SettingsPatch) => apiRequest<AdminSettings>("PATCH", "/admin/settings", patch);

export const listStaffRoles = () => apiGet<StaffRoleRow[]>("/admin/staff-roles");
export const grantStaffRole = (email: string, role: StaffRole) =>
  apiRequest<StaffRoleRow>("POST", "/admin/staff-roles", { email, role });
export const setStaffRoleActive = (id: number, active: boolean) =>
  apiRequest<StaffRoleRow>("PATCH", `/admin/staff-roles/${id}`, { active });

export const listAdminFacilities = () => apiGet<AdminFacility[]>("/admin/facilities");
export const updateFacility = (id: number, patch: Partial<Pick<AdminFacility, "name" | "capacity" | "active">>) =>
  apiRequest<AdminFacility>("PATCH", `/admin/facilities/${id}`, patch);
export const addTariff = (input: TariffInput) => apiRequest<AdminFacility>("POST", "/admin/tariffs", input);
export const setTariffActive = (id: number, active: boolean) =>
  apiRequest<AdminFacility>("PATCH", `/admin/tariffs/${id}`, { active });
export const updateSlot = (id: number, patch: SlotPatch) =>
  apiRequest<AdminFacility>("PATCH", `/admin/slot-windows/${id}`, patch);

export const listEmails = (status?: EmailStatus) =>
  apiGet<EmailLogList>(status ? `/admin/emails?status=${status}` : "/admin/emails");
export const retryEmails = () => apiRequest<{ sent: number; failed: number; skipped: number }>("POST", "/admin/emails/retry");

export const listAdminAudit = () => apiGet<AdminAuditRow[]>("/admin/audit");
