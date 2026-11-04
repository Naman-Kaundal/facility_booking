import type { DecisionInput, Desk, ElectricityInput, Queue, StaffRequest } from "../types/workflow";
import { apiGet, apiRequest } from "./client";

export const getQueue = (desk: Desk) => apiGet<Queue>(`/workflow/queue?desk=${desk}`);
export const getStaffRequest = (id: number) => apiGet<StaffRequest>(`/workflow/requests/${id}`);
export const forwardRequest = (id: number, remark?: string) =>
  apiRequest<StaffRequest>("POST", `/requests/${id}/forward`, { remark: remark || null });
export const returnRequest = (id: number, reason: string) =>
  apiRequest<StaffRequest>("POST", `/requests/${id}/return`, { reason });
export const decideLine = (id: number, input: DecisionInput) =>
  apiRequest<StaffRequest>("POST", `/requests/${id}/decision`, { ...input, remark: input.remark || null });
export const submitElectricity = (id: number, input: ElectricityInput) =>
  apiRequest<StaffRequest>("POST", `/requests/${id}/electricity`, { ...input, remark: input.remark || null });
export const intimateAdvance = (id: number, remark?: string) =>
  apiRequest<StaffRequest>("POST", `/requests/${id}/intimate`, { remark: remark || null });
