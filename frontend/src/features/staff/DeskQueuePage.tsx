import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { errorMessage } from "../../api/client";
import { getQueue } from "../../api/workflow";
import { ErrorState, LoadingState } from "../../components/States";
import type { Desk, Queue } from "../../types/workflow";
import { SECTION_LABELS, formatDate, formatDateTime } from "../../utils/format";
import { DESKS } from "./desks";
import "../../styles/staff.css";

/** The list of requests waiting for one desk. */
export function DeskQueuePage({ desk }: { desk: Desk }) {
  const info = DESKS.find((d) => d.desk === desk)!;
  const [queue, setQueue] = useState<Queue | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    setError(null);
    getQueue(desk)
      .then(setQueue)
      .catch((err) => setError(errorMessage(err)));
  }, [desk]);
  useEffect(load, [load]);

  if (error) return <ErrorState title="Couldn't load the queue" message={error} onRetry={load} />;
  if (!queue) return <LoadingState label="Loading queue…" />;

  const sectionDesk = desk !== "FACILITY";

  return (
    <section className="page" aria-labelledby="desk-heading">
      <div className="page__header">
        <div>
          <p className="eyebrow">Staff</p>
          <h1 id="desk-heading">{info.title}</h1>
          <p className="muted">{info.description}</p>
        </div>
        <button type="button" className="button button--secondary" onClick={load}>
          Refresh
        </button>
      </div>

      {queue.items.length === 0 ? (
        <div className="panel desk-empty">
          <strong>Nothing waiting.</strong>
          <p className="muted">New requests for this desk will appear here.</p>
        </div>
      ) : (
        <div className="table-wrap">
          <table className="data-table">
            <caption className="visually-hidden">{queue.total} requests waiting</caption>
            <thead>
              <tr>
                <th scope="col">Reference</th>
                <th scope="col">Event</th>
                <th scope="col">Requester</th>
                <th scope="col">First date</th>
                <th scope="col">{sectionDesk ? "To decide" : "Sections"}</th>
                <th scope="col">Submitted</th>
              </tr>
            </thead>
            <tbody>
              {queue.items.map((item) => (
                <tr key={item.id}>
                  <td>
                    <Link to={`/desk/requests/${item.id}?desk=${desk}`}>{item.ref_no ?? `#${item.id}`}</Link>
                  </td>
                  <td>{item.purpose}</td>
                  <td>
                    {item.applicant_name}
                    <span className="desk-sub">{item.organisation}</span>
                  </td>
                  <td>{item.first_date ? formatDate(item.first_date) : "—"}</td>
                  <td>
                    {sectionDesk
                      ? `${item.pending_lines} of ${item.line_count} lines`
                      : item.sections.map((s) => SECTION_LABELS[s]).join(", ")}
                  </td>
                  <td>{item.submitted_at ? formatDateTime(item.submitted_at) : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
