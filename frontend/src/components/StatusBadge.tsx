import type { RequestStatus } from "../types/request";
import { STATUS_LABELS } from "../utils/format";

/** Status shown as text (never colour alone). */
export function StatusBadge({ status }: { status: RequestStatus }) {
  return <span className={`status status--${status.toLowerCase()}`}>{STATUS_LABELS[status] ?? status}</span>;
}
