import type { LineDecision } from "../types/request";
import { DECISION_LABELS } from "../utils/format";
import "../styles/workflow.css";

/** A line's section decision, shown as text (never colour alone). */
export function DecisionBadge({ decision }: { decision: LineDecision }) {
  return <span className={`decision decision--${decision.toLowerCase()}`}>{DECISION_LABELS[decision]}</span>;
}
