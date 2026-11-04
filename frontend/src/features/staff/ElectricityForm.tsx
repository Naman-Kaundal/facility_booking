import { useState, type FormEvent } from "react";
import type { ElectricityInput } from "../../types/workflow";
import "../../styles/costs.css";

/**
 * Estate enters only the approximate electricity charge. The server calculates GST, cleaning,
 * the deposit, the total and the advance from the settings and the frozen rates.
 */
export function ElectricityForm({
  initial,
  revising,
  busy,
  onSubmit,
}: {
  initial?: number;
  revising: boolean;
  busy: boolean;
  onSubmit: (input: ElectricityInput) => Promise<void>;
}) {
  const [amount, setAmount] = useState(initial !== undefined ? String(initial) : "");
  const [remark, setRemark] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    const value = Number(amount);
    if (amount.trim() === "" || !Number.isFinite(value) || value < 0) {
      setError("Enter the estimate in rupees (0 or more).");
      return;
    }
    if (Math.round(value * 100) !== value * 100) {
      setError("Use at most two decimal places.");
      return;
    }
    setError(null);
    await onSubmit({ electricity_estimate: value, remark: remark.trim() || undefined });
  }

  return (
    <form className="panel" onSubmit={submit} noValidate aria-labelledby="estimate-heading">
      <h2 id="estimate-heading">{revising ? "Revise the electricity estimate" : "Electricity estimate"}</h2>
      <p className="muted">
        Enter the approximate electricity charge for the confirmed facilities. The costs are calculated automatically.
      </p>
      <div className="estimate-form">
        <div className={`field${error ? " field--invalid" : ""}`}>
          <label htmlFor="estimate">Amount (₹)</label>
          <input
            id="estimate"
            type="number"
            inputMode="decimal"
            min={0}
            step="0.01"
            value={amount}
            aria-invalid={Boolean(error)}
            aria-describedby={error ? "estimate-error" : undefined}
            onChange={(e) => setAmount(e.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="estimate-remark">Note (optional)</label>
          <input
            id="estimate-remark"
            value={remark}
            maxLength={1000}
            placeholder="e.g. AC for 8 hours"
            onChange={(e) => setRemark(e.target.value)}
          />
        </div>
      </div>
      {error && (
        <p className="field-error" id="estimate-error" role="alert">
          {error}
        </p>
      )}
      <div className="form-actions form-actions--start">
        <button type="submit" className="button" disabled={busy}>
          {busy ? "Saving…" : revising ? "Recalculate costs" : "Submit estimate"}
        </button>
      </div>
    </form>
  );
}
