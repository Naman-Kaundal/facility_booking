import { useCallback, useEffect, useState } from "react";
import { errorMessage } from "../../api/client";
import { listEmails, retryEmails } from "../../api/admin";
import { ErrorState, LoadingState } from "../../components/States";
import type { EmailLogList, EmailStatus } from "../../types/admin";
import { formatDateTime } from "../../utils/format";

const FILTERS: { value: EmailStatus | ""; label: string }[] = [
  { value: "", label: "All" },
  { value: "FAILED", label: "Failed" },
  { value: "PENDING", label: "Waiting" },
  { value: "SENT", label: "Sent" },
];
const STATUS_TEXT: Record<EmailStatus, string> = { SENT: "Sent", FAILED: "Failed", PENDING: "Waiting" };

/** Every notification email and what happened to it; failed ones can be retried. */
export function EmailLogPanel() {
  const [filter, setFilter] = useState<EmailStatus | "">("");
  const [log, setLog] = useState<EmailLogList | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    setError(null);
    listEmails(filter || undefined)
      .then(setLog)
      .catch((err) => setError(errorMessage(err)));
  }, [filter]);
  useEffect(load, [load]);

  async function retry() {
    setBusy(true);
    setNotice(null);
    try {
      const r = await retryEmails();
      setNotice(`Retried: ${r.sent} sent, ${r.failed} still failing.`);
      load();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  if (error && !log) return <ErrorState title="Couldn't load the email log" message={error} onRetry={load} />;
  if (!log) return <LoadingState label="Loading emails…" />;

  return (
    <div className="panel">
      <div className="panel__header">
        <h2>Email log</h2>
        <button type="button" className="button button--secondary" disabled={busy} onClick={() => void retry()}>
          Retry failed emails
        </button>
      </div>
      <p className="muted">
        Each email is tried up to {log.max_attempts} times. Retrying never sends an email that was already sent.
      </p>
      <div className="filters" role="group" aria-label="Show">
        {FILTERS.map((f) => (
          <button
            key={f.label}
            type="button"
            className={`filter${filter === f.value ? " filter--active" : ""}`}
            aria-pressed={filter === f.value}
            onClick={() => setFilter(f.value)}
          >
            {f.label}
          </button>
        ))}
      </div>
      {notice && (
        <div className="alert alert--info" role="status">
          {notice}
        </div>
      )}
      {log.items.length === 0 ? (
        <p className="muted">No emails here.</p>
      ) : (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">When</th>
                <th scope="col">To</th>
                <th scope="col">Subject</th>
                <th scope="col">Status</th>
              </tr>
            </thead>
            <tbody>
              {log.items.map((e) => (
                <tr key={e.id}>
                  <td>{formatDateTime(e.created_at)}</td>
                  <td>{e.recipient}</td>
                  <td>{e.subject}</td>
                  <td>
                    <span className={`email-status email-status--${e.status.toLowerCase()}`}>{STATUS_TEXT[e.status]}</span>
                    <span className="desk-sub">
                      {e.attempt_count} {e.attempt_count === 1 ? "try" : "tries"}
                    </span>
                    {e.last_error && <span className="desk-sub">{e.last_error}</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
