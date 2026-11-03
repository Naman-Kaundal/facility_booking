import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { errorMessage } from "../../api/client";
import { listMyRequests } from "../../api/requests";
import { StatusBadge } from "../../components/StatusBadge";
import { EmptyState, ErrorState, LoadingState } from "../../components/States";
import type { RequestSummary } from "../../types/request";
import { formatDate } from "../../utils/format";

export function MyRequestsPage() {
  const [items, setItems] = useState<RequestSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    setError(null);
    setItems(null);
    listMyRequests()
      .then((data) => setItems(data.items))
      .catch((err) => setError(errorMessage(err)));
  }, []);

  useEffect(load, [load]);

  return (
    <section className="page" aria-labelledby="my-requests-heading">
      <div className="page__header">
        <h1 id="my-requests-heading">My requests</h1>
        <Link to="/requests/new" className="button">
          New request
        </Link>
      </div>

      {error && <ErrorState title="Couldn't load your requests" message={error} onRetry={load} />}
      {!error && items === null && <LoadingState label="Loading your requests…" />}
      {items?.length === 0 && <EmptyState message="You haven't started any requests yet." />}
      {items && items.length > 0 && (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">Reference</th>
                <th scope="col">Event</th>
                <th scope="col">Facilities</th>
                <th scope="col">First date</th>
                <th scope="col">Status</th>
                <th scope="col">
                  <span className="visually-hidden">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id}>
                  <td>{item.ref_no ?? <span className="muted">Not submitted</span>}</td>
                  <td className="cell-wrap">{item.purpose}</td>
                  <td className="cell-wrap">{item.facility_summary}</td>
                  <td>{item.first_date ? formatDate(item.first_date) : "—"}</td>
                  <td>
                    <StatusBadge status={item.status} />
                  </td>
                  <td>
                    <Link to={`/requests/${item.id}`} aria-label={`View request: ${item.purpose}`}>
                      View
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
