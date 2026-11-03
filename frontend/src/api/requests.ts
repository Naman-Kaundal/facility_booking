import { apiGet, apiRequest } from "./client";
import type { BookingRequest, EventDetailsInput, LineInput, RequestList, Terms, TimelineEvent } from "../types/request";

export const listMyRequests = () => apiGet<RequestList>("/requests");
export const getRequest = (id: number) => apiGet<BookingRequest>(`/requests/${id}`);
export const createDraft = (event: EventDetailsInput) => apiRequest<BookingRequest>("POST", "/requests", event);
export const updateEvent = (id: number, event: Partial<EventDetailsInput>) =>
  apiRequest<BookingRequest>("PATCH", `/requests/${id}`, event);
export const deleteDraft = (id: number) => apiRequest<void>("DELETE", `/requests/${id}`);
export const addLine = (id: number, line: LineInput) =>
  apiRequest<BookingRequest>("POST", `/requests/${id}/lines`, line);
export const updateLine = (id: number, lineId: number, line: Partial<LineInput>) =>
  apiRequest<BookingRequest>("PATCH", `/requests/${id}/lines/${lineId}`, line);
export const deleteLine = (id: number, lineId: number) =>
  apiRequest<BookingRequest>("DELETE", `/requests/${id}/lines/${lineId}`);
export const getTerms = () => apiGet<Terms>("/requests/terms");
export const submitRequest = (id: number, terms_version: string) =>
  apiRequest<BookingRequest>("POST", `/requests/${id}/submit`, { terms_accepted: true, terms_version });
export const getEvents = (id: number) => apiGet<TimelineEvent[]>(`/requests/${id}/events`);
