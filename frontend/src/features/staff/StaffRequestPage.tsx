import { useCallback, useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { errorMessage } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import {
  decideLine,
  forwardRequest,
  getStaffRequest,
  intimateAdvance,
  returnRequest,
  submitElectricity,
} from "../../api/workflow";
import { CostBreakdown } from "../../components/CostBreakdown";
import { DecisionBadge } from "../../components/DecisionBadge";
import { StatusBadge } from "../../components/StatusBadge";
import { ErrorState, LoadingState } from "../../components/States";
import { Timeline } from "../../components/Timeline";
import type { DecisionInput, ElectricityInput, StaffRequest } from "../../types/workflow";
import { CATEGORY_LABELS, SECTION_LABELS, formatDate, formatDateTime, formatInr, formatTotal } from "../../utils/format";
import { DecisionForm } from "./DecisionForm";
import { DESKS } from "./desks";
import { ElectricityForm } from "./ElectricityForm";
import { IntimationPanel } from "./IntimationPanel";
import "../../styles/staff.css";

/** One request as staff see it, with the actions this person may take. */
export function StaffRequestPage() {
  const id = Number(useParams().id);
  const { user } = useAuth();
  const [params] = useSearchParams();
  const back = DESKS.find((d) => d.desk === params.get("desk"));
  const [data, setData] = useState<StaffRequest | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [mode, setMode] = useState<"none" | "forward" | "return">("none");
  const [text, setText] = useState("");

  const load = useCallback(() => {
    setLoadError(null);
    getStaffRequest(id)
      .then(setData)
      .catch((err) => setLoadError(errorMessage(err)));
  }, [id]);
  useEffect(load, [load]);

  async function act(run: () => Promise<StaffRequest>, done: string) {
    setBusy(true);
    setActionError(null);
    setNotice(null);
    try {
      setData(await run());
      setNotice(done);
      setMode("none");
      setText("");
    } catch (err) {
      setActionError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  if (loadError) return <ErrorState title="Couldn't load the request" message={loadError} onRetry={load} />;
  if (!data) return <LoadingState label="Loading request…" />;

  const { request, timeline } = data;
  const { event } = request;
  const category = request.rate_category_snapshot ?? request.charges_preview.category;

  function confirmMode() {
    if (mode === "return" && !text.trim()) {
      setActionError("Say what the requester needs to correct.");
      return;
    }
    if (mode === "forward") void act(() => forwardRequest(id, text.trim()), "Forwarded to the sections.");
    if (mode === "return") void act(() => returnRequest(id, text.trim()), "Returned to the requester.");
  }

  const decide = (input: DecisionInput) =>
    act(() => decideLine(id, input), input.decision === "CONFIRMED" ? "Line confirmed." : "Line rejected.");

  const enterElectricity = (input: ElectricityInput) =>
    act(() => submitElectricity(id, input), "Estimate saved. The costs have been calculated.");

  const sendAdvance = (remark?: string) =>
    act(() => intimateAdvance(id, remark), "Advance intimation sent to the requester.");

  const costs = request.costs ?? null;
  // Only the Facilities desk sends the advance; the server checks the role again.
  const showIntimation = request.status === "COSTED" && costs !== null && Boolean(user?.roles?.includes("FACILITY"));

  return (
    <section className="page" aria-labelledby="staff-heading">
      {back && (
        <p>
          <Link to={back.path}>← Back to {back.title}</Link>
        </p>
      )}
      <div className="page__header">
        <div>
          <p className="eyebrow">{request.ref_no}</p>
          <h1 id="staff-heading">{event.purpose}</h1>
        </div>
        <StatusBadge status={request.status} />
      </div>

      {notice && (
        <div className="alert alert--info" role="status">
          {notice}
        </div>
      )}
      {actionError && (
        <div className="alert alert--error" role="alert">
          {actionError}
        </div>
      )}

      <div className="detail-grid">
        <div className="panel">
          <h2>Requester</h2>
          <dl className="details">
            <dt>Account</dt>
            <dd>
              {data.requester_name} ({data.requester_email})
            </dd>
            <dt>Rate category</dt>
            <dd>{category ? CATEGORY_LABELS[category] : "—"}</dd>
            <dt>Organisation</dt>
            <dd className="pre-line">{event.organisation_name_address}</dd>
            <dt>Booked by</dt>
            <dd>{event.applicant_name}</dd>
            <dt>Contacts</dt>
            <dd>
              {event.contact_email} · Office {event.office_contact} · Mobile {event.mobile}
            </dd>
            <dt>Participants</dt>
            <dd>{event.participants}</dd>
            {request.submitted_at && (
              <>
                <dt>Submitted</dt>
                <dd>{formatDateTime(request.submitted_at)}</dd>
              </>
            )}
            {request.terms_version && (
              <>
                <dt>Terms accepted</dt>
                <dd>{request.terms_version}</dd>
              </>
            )}
          </dl>
        </div>

        <div className="panel">
          <h2>Facilities ({request.lines.length})</h2>
          <ul className="line-list staff-lines">
            {request.lines.map((line) => {
              const label = `${line.facility_name} on ${formatDate(line.booking_date)}`;
              const decidable = data.decidable_line_ids.includes(line.id);
              return (
                <li key={line.id}>
                  <div className="staff-line">
                    <div className="staff-line__head">
                      <div>
                        <strong>{line.facility_name}</strong>
                        <span className="muted">
                          {formatDate(line.booking_date)} · {line.slot_label} · {SECTION_LABELS[line.section]}
                        </span>
                      </div>
                      <span className="num">{line.rate ? formatInr(line.rate.amount) : "—"}</span>
                    </div>
                    <div>
                      <DecisionBadge decision={line.decision} />
                      {line.decided_by_name && (
                        <span className="muted">
                          {" "}
                          by {line.decided_by_name}
                          {line.decided_at && `, ${formatDateTime(line.decided_at)}`}
                        </span>
                      )}
                      {line.decision_remark && <div className="decision-remark">“{line.decision_remark}”</div>}
                    </div>
                    {decidable && <DecisionForm lineId={line.id} label={label} busy={busy} onDecide={decide} />}
                  </div>
                </li>
              );
            })}
          </ul>
          <div className="subtotal">
            <span>Booking charges (confirmed and pending lines)</span>
            <strong>{formatTotal(request.charges_preview.booking_subtotal)}</strong>
          </div>
        </div>
      </div>

      {data.can_enter_electricity && (
        <ElectricityForm
          key={costs?.calculated_at ?? "new"}
          initial={costs?.electricity_estimate}
          revising={request.status === "COSTED"}
          busy={busy}
          onSubmit={enterElectricity}
        />
      )}

      {costs && (
        <div className="panel">
          <CostBreakdown costs={costs} />
          {costs.payment_url && (
            <p className="hint">
              Payment link sent:{" "}
              <a href={costs.payment_url} target="_blank" rel="noopener noreferrer">
                {costs.payment_url}
              </a>
            </p>
          )}
        </div>
      )}

      {showIntimation && costs && (
        <IntimationPanel
          advance={costs.advance_amount}
          paymentConfigured={data.payment_url_configured}
          canIntimate={data.can_intimate}
          busy={busy}
          onSend={sendAdvance}
        />
      )}

      {(data.can_forward || data.can_return) && (
        <div className="panel staff-actions">
          <h2>Facilities check</h2>
          {mode === "none" ? (
            <div className="form-actions form-actions--start">
              {data.can_forward && (
                <button type="button" className="button" onClick={() => setMode("forward")}>
                  Forward to sections
                </button>
              )}
              {data.can_return && (
                <button type="button" className="button button--secondary" onClick={() => setMode("return")}>
                  Return for correction
                </button>
              )}
            </div>
          ) : (
            <div className="field">
              <label htmlFor="staff-text">
                {mode === "forward" ? "Note for the sections (optional)" : "What needs correcting"}
              </label>
              <textarea id="staff-text" rows={3} maxLength={1000} value={text} onChange={(e) => setText(e.target.value)} />
              <div className="form-actions form-actions--start">
                <button type="button" className="button" disabled={busy} onClick={confirmMode}>
                  {mode === "forward" ? "Confirm forward" : "Confirm return"}
                </button>
                <button
                  type="button"
                  className="button button--secondary"
                  onClick={() => {
                    setMode("none");
                    setText("");
                    setActionError(null);
                  }}
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      <div className="panel">
        <h2>Timeline</h2>
        <Timeline events={timeline} />
      </div>
    </section>
  );
}
