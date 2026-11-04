import { useEffect, useState } from "react";
import { errorMessage } from "../../api/client";
import { listAdminAudit } from "../../api/admin";
import { ErrorState, LoadingState } from "../../components/States";
import type { AdminAuditRow } from "../../types/admin";
import { formatDateTime } from "../../utils/format";

function describe(details: string | null): string {
  if (!details) return "";
  try {
    const parsed = JSON.parse(details) as Record<string, unknown>;
    return Object.entries(parsed)
      .map(([key, value]) => {
        if (value && typeof value === "object" && "to" in value) {
          const change = value as { from: unknown; to: unknown };
          return `${key}: ${String(change.from ?? "—")} → ${String(change.to ?? "—")}`;
        }
        return `${key}: ${String(value)}`;
      })
      .join("; ");
  } catch {
    return details;
  }
}

/** Who changed which setting, role, facility, rate or slot, and when. */
export function AuditPanel() {
  const [rows, setRows] = useState<AdminAuditRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = () => {
    listAdminAudit()
      .then(setRows)
      .catch((err) => setError(errorMessage(err)));
  };
  useEffect(load, []);

  if (error) return <ErrorState title="Couldn't load the change log" message={error} onRetry={load} />;
  if (!rows) return <LoadingState label="Loading…" />;
  return (
    <div className="panel">
      <h2>Change log</h2>
      {rows.length === 0 ? (
        <p className="muted">No admin changes yet.</p>
      ) : (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">When</th>
                <th scope="col">Who</th>
                <th scope="col">What</th>
                <th scope="col">Details</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id}>
                  <td>{formatDateTime(r.created_at)}</td>
                  <td>{r.actor_email}</td>
                  <td>
                    {r.action.replace(/_/g, " ").toLowerCase()}
                    {r.entity_id && <span className="desk-sub">{`${r.entity} ${r.entity_id}`}</span>}
                  </td>
                  <td className="cell-wrap">{describe(r.details)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
