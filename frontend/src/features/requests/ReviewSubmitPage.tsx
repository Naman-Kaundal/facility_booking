import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { errorMessage } from "../../api/client";
import { getTerms, submitRequest } from "../../api/requests";
import { StepIndicator } from "../../components/StepIndicator";
import { ErrorState, LoadingState } from "../../components/States";
import type { Terms } from "../../types/request";
import { CATEGORY_LABELS, SECTION_LABELS, formatDate, formatInr, formatTotal } from "../../utils/format";
import { useRequest } from "./useRequest";
import "../../styles/workflow.css";

/** Step 3: check everything, read and accept the terms, submit to Facilities. */
export function ReviewSubmitPage() {
  const id = Number(useParams().id);
  const navigate = useNavigate();
  const { request, error, reload } = useRequest(id);
  const [terms, setTerms] = useState<Terms | null>(null);
  const [accepted, setAccepted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  useEffect(() => {
    getTerms()
      .then(setTerms)
      .catch((err) => setSubmitError(errorMessage(err)));
  }, []);

  if (error) return <ErrorState title="Couldn't load the request" message={error} onRetry={reload} />;
  if (!request || !terms) return <LoadingState label="Loading…" />;
  if (!request.editable)
    return <ErrorState title="Already submitted" message="This request has already been submitted." />;

  const { event, lines, charges_preview: preview } = request;
  const resubmitting = request.status === "RETURNED";

  async function submit() {
    if (!accepted || !terms) {
      setSubmitError("Please read and accept the terms and conditions.");
      return;
    }
    setBusy(true);
    setSubmitError(null);
    try {
      await submitRequest(id, terms.version);
      navigate(`/requests/${id}?submitted=1`, { replace: true });
    } catch (err) {
      setSubmitError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="page page--form" aria-labelledby="review-heading">
      <StepIndicator current={3} />
      <h1 id="review-heading">{resubmitting ? "Review and resubmit" : "Review and submit"}</h1>

      {resubmitting && request.return_reason && (
        <div className="alert alert--warning">
          <strong>Facilities asked for:</strong> {request.return_reason}
        </div>
      )}

      <div className="panel">
        <div className="panel__header">
          <h2>Event</h2>
          <Link to={`/requests/${id}/edit`}>Edit</Link>
        </div>
        <dl className="details">
          <dt>Purpose</dt>
          <dd>{event.purpose}</dd>
          <dt>Organisation</dt>
          <dd className="pre-line">{event.organisation_name_address}</dd>
          <dt>Booked by</dt>
          <dd>
            {event.applicant_name} ({event.contact_email})
          </dd>
          <dt>Contacts</dt>
          <dd>
            Office {event.office_contact} · Mobile {event.mobile}
          </dd>
          <dt>Participants</dt>
          <dd>{event.participants}</dd>
        </dl>
      </div>

      <div className="panel">
        <div className="panel__header">
          <h2>Facilities ({lines.length})</h2>
          <Link to={`/requests/${id}/facilities`}>Change</Link>
        </div>
        {lines.length === 0 ? (
          <p className="alert alert--error">Add at least one facility before submitting.</p>
        ) : (
          <ul className="line-list">
            {lines.map((line) => (
              <li key={line.id}>
                <div>
                  <strong>{line.facility_name}</strong>
                  <span className="muted">
                    {formatDate(line.booking_date)} · {line.slot_label} · {SECTION_LABELS[line.section]}
                  </span>
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

      <div className="panel">
        <h2 id="terms-heading">Terms and conditions</h2>
        {terms.is_placeholder && (
          <p className="hint">These are placeholder terms until the Facilities Section supplies the approved text.</p>
        )}
        <div className="terms-box" tabIndex={0} role="region" aria-labelledby="terms-heading">
          {terms.text}
        </div>
        <label className="accept">
          <input type="checkbox" checked={accepted} onChange={(e) => setAccepted(e.target.checked)} />
          <span>I have read and accept the terms and conditions (version {terms.version}).</span>
        </label>
      </div>

      {submitError && (
        <div className="alert alert--error" role="alert">
          {submitError}
        </div>
      )}
      <div className="form-actions">
        <Link to={`/requests/${id}`} className="button button--secondary">
          Back
        </Link>
        <button
          type="button"
          className="button"
          onClick={() => void submit()}
          disabled={busy || lines.length === 0 || !accepted}
        >
          {busy ? "Submitting…" : resubmitting ? "Resubmit to Facilities" : "Submit to Facilities"}
        </button>
      </div>
    </section>
  );
}
