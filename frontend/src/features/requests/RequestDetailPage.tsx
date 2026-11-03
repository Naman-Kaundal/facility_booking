import { useEffect, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { errorMessage } from "../../api/client";
import { deleteDraft, getEvents } from "../../api/requests";
import { DecisionBadge } from "../../components/DecisionBadge";
import { StatusBadge } from "../../components/StatusBadge";
import { ErrorState, LoadingState } from "../../components/States";
import { Timeline } from "../../components/Timeline";
import type { TimelineEvent } from "../../types/request";
import {
  CATEGORY_LABELS,
  SECTION_LABELS,
  STATUS_HELP,
  formatDate,
  formatDateTime,
  formatInr,
  formatTotal,
} from "../../utils/format";
import { useRequest } from "./useRequest";
import "../../styles/workflow.css";

export function RequestDetailPage() {
  const id = Number(useParams().id);
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const { request, error, reload } = useRequest(id);
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const submittedAt = request?.submitted_at;
  useEffect(() => {
    // Drafts have no history yet; load the timeline once the request has been submitted.
    if (!submittedAt) return;
    getEvents(id)
      .then(setEvents)
      .catch(() => setEvents([]));
  }, [id, submittedAt]);

  if (error) return <ErrorState title="Couldn't load the request" message={error} onRetry={reload} />;
  if (!request) return <LoadingState label="Loading request…" />;

  const { event, charges_preview: preview } = request;
  const isDraft = request.status === "DRAFT";
  const isReturned = request.status === "RETURNED";

  async function remove() {
    try {
      await deleteDraft(id);
      navigate("/requests", { replace: true });
    } catch (err) {
      setActionError(errorMessage(err));
    }
  }

  return (
    <section className="page" aria-labelledby="detail-heading">
      <div className="page__header">
        <div>
          <p className="eyebrow">{request.ref_no ?? "Draft request"}</p>
          <h1 id="detail-heading">{event.purpose}</h1>
          {STATUS_HELP[request.status] && <p className="status-help">{STATUS_HELP[request.status]}</p>}
        </div>
        <StatusBadge status={request.status} />
      </div>

      {params.get("submitted") && request.status === "SUBMITTED" && (
        <div className="alert alert--info" role="status">
          Submitted. Your reference number is <strong>{request.ref_no}</strong>. Facilities will review it next.
        </div>
      )}
      {isDraft && (
        <div className="alert alert--info">
          This request is a draft. It's saved, but Facilities can't see it until you submit it.
        </div>
      )}
      {isReturned && (
        <div className="alert alert--warning" role="alert">
          <strong>Returned for correction:</strong> {request.return_reason}
          {request.returned_at && <span className="muted"> ({formatDateTime(request.returned_at)})</span>}
          <br />
          Make the changes, then review and submit again. Your reference number stays the same.
        </div>
      )}
      {actionError && (
        <div className="alert alert--error" role="alert">
          {actionError}
        </div>
      )}

      <div className="detail-grid">
        <div className="panel">
          <div className="panel__header">
            <h2>Event details</h2>
            {request.editable && <Link to={`/requests/${id}/edit`}>Edit</Link>}
          </div>
          <dl className="details">
            <dt>Organisation</dt>
            <dd className="pre-line">{event.organisation_name_address}</dd>
            <dt>Booked by</dt>
            <dd>{event.applicant_name}</dd>
            <dt>Email</dt>
            <dd>{event.contact_email}</dd>
            <dt>Office contact</dt>
            <dd>{event.office_contact}</dd>
            <dt>Mobile</dt>
            <dd>{event.mobile}</dd>
            <dt>Participants</dt>
            <dd>{event.participants}</dd>
            {request.submitted_at && (
              <>
                <dt>Submitted</dt>
                <dd>{formatDateTime(request.submitted_at)}</dd>
              </>
            )}
            <dt>Last updated</dt>
            <dd>{formatDateTime(request.updated_at)}</dd>
          </dl>
        </div>

        <div className="panel">
          <div className="panel__header">
            <h2>Facilities ({request.lines.length})</h2>
            {request.editable && <Link to={`/requests/${id}/facilities`}>Add or change</Link>}
          </div>
          {request.lines.length === 0 ? (
            <p className="muted">No facilities added yet.</p>
          ) : (
            <ul className="line-list">
              {request.lines.map((line) => (
                <li key={line.id}>
                  <div>
                    <strong>{line.facility_name}</strong>
                    <span className="muted">
                      {formatDate(line.booking_date)} · {line.slot_label} · {SECTION_LABELS[line.section]}
                    </span>
                    {request.submitted_at && !request.editable && (
                      <span>
                        <DecisionBadge decision={line.decision} />
                        {line.decision_remark && <span className="decision-remark"> {line.decision_remark}</span>}
                      </span>
                    )}
                  </div>
                  <span className="num">{line.rate ? formatInr(line.rate.amount) : "—"}</span>
                </li>
              ))}
            </ul>
          )}
          <div className="subtotal">
            <span>
              Booking charges
              {preview.category && <span className="muted"> ({CATEGORY_LABELS[preview.category]} rate)</span>}
            </span>
            <strong>{formatTotal(preview.booking_subtotal)}</strong>
          </div>
          <p className="hint">{preview.note}</p>
        </div>
      </div>

      {request.submitted_at && (
        <div className="panel">
          <h2>Timeline</h2>
          <Timeline events={events} />
        </div>
      )}

      {request.editable && (
        <div className="form-actions form-actions--split">
          {isDraft &&
            (confirmDelete ? (
              <span className="confirm">
                Delete this draft permanently?{" "}
                <button type="button" className="button button--danger" onClick={() => void remove()}>
                  Yes, delete
                </button>{" "}
                <button type="button" className="button button--secondary" onClick={() => setConfirmDelete(false)}>
                  Keep it
                </button>
              </span>
            ) : (
              <button type="button" className="button button--secondary" onClick={() => setConfirmDelete(true)}>
                Delete draft
              </button>
            ))}
          <span className="form-actions">
            <Link to="/requests" className="button button--secondary">
              Back to my requests
            </Link>
            <Link
              to={`/requests/${id}/review`}
              className="button"
              aria-disabled={request.lines.length === 0}
              onClick={(e) => request.lines.length === 0 && e.preventDefault()}
            >
              {isReturned ? "Review and resubmit" : "Review and submit"}
            </Link>
          </span>
        </div>
      )}
    </section>
  );
}
