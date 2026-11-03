import { useId, useState, type FormEvent } from "react";
import type { DecisionInput } from "../../types/workflow";

/** Confirm or reject one line. Rejection needs a remark (the server enforces this too). */
export function DecisionForm({
  lineId,
  label,
  busy,
  onDecide,
}: {
  lineId: number;
  label: string;
  busy: boolean;
  onDecide: (input: DecisionInput) => Promise<void>;
}) {
  const [remark, setRemark] = useState("");
  const [error, setError] = useState<string | null>(null);
  const remarkId = useId();

  async function decide(decision: DecisionInput["decision"]) {
    if (decision === "REJECTED" && !remark.trim()) {
      setError("Give a reason for rejecting this line.");
      return;
    }
    setError(null);
    await onDecide({ line_id: lineId, decision, remark: remark.trim() || undefined });
  }

  return (
    <form
      className="decision-form"
      aria-label={`Decision for ${label}`}
      onSubmit={(e: FormEvent) => {
        e.preventDefault();
        void decide("CONFIRMED");
      }}
    >
      <label htmlFor={remarkId}>Remark</label>
      <input
        id={remarkId}
        value={remark}
        maxLength={1000}
        placeholder="Required when rejecting"
        onChange={(e) => setRemark(e.target.value)}
        aria-invalid={Boolean(error)}
      />
      {error && (
        <p className="field-error" role="alert">
          {error}
        </p>
      )}
      <div className="decision-form__buttons">
        <button type="submit" className="button" disabled={busy}>
          Confirm
        </button>
        <button type="button" className="button button--danger" disabled={busy} onClick={() => void decide("REJECTED")}>
          Reject
        </button>
      </div>
    </form>
  );
}
