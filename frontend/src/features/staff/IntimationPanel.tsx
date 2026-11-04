import { useState } from "react";
import { formatMoney } from "../../utils/format";

/** Facilities reviews the server's breakdown and sends the advance and payment link to the requester. */
export function IntimationPanel({
  advance,
  paymentConfigured,
  canIntimate,
  busy,
  onSend,
}: {
  advance: number;
  paymentConfigured: boolean;
  canIntimate: boolean;
  busy: boolean;
  onSend: (remark?: string) => Promise<void>;
}) {
  const [confirming, setConfirming] = useState(false);
  const [remark, setRemark] = useState("");

  return (
    <div className="panel staff-actions">
      <h2>Advance intimation</h2>
      {!paymentConfigured ? (
        <div className="alert alert--warning" role="alert">
          The institute payment link isn't set yet. Ask an admin to add it under <strong>Admin → Settings</strong>, then
          send the intimation.
        </div>
      ) : !confirming ? (
        <>
          <p>
            Check the breakdown, then send the requester the advance of <strong>{formatMoney(advance)}</strong> with
            the payment link.
          </p>
          <div className="form-actions form-actions--start">
            <button type="button" className="button" disabled={!canIntimate} onClick={() => setConfirming(true)}>
              Send advance intimation
            </button>
          </div>
        </>
      ) : (
        <div className="field">
          <label htmlFor="intimation-remark">Message to the requester (optional)</label>
          <textarea
            id="intimation-remark"
            rows={2}
            maxLength={1000}
            value={remark}
            placeholder="e.g. Please pay within 7 days"
            onChange={(e) => setRemark(e.target.value)}
          />
          <div className="form-actions form-actions--start">
            <button type="button" className="button" disabled={busy} onClick={() => void onSend(remark.trim())}>
              {busy ? "Sending…" : `Send ${formatMoney(advance)} advance intimation`}
            </button>
            <button type="button" className="button button--secondary" onClick={() => setConfirming(false)}>
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
