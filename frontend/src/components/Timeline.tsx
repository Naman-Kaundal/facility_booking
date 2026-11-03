import type { TimelineEvent } from "../types/request";
import { formatDateTime } from "../utils/format";
import "../styles/workflow.css";

/** Audit timeline: who did what, and when (newest last). */
export function Timeline({ events }: { events: TimelineEvent[] }) {
  if (events.length === 0) return <p className="muted">Nothing has happened yet.</p>;
  return (
    <ol className="timeline" aria-label="Request timeline">
      {events.map((e) => (
        <li key={e.id} className={`timeline__item timeline__item--${e.event_type.toLowerCase()}`}>
          <div className="timeline__head">
            <strong>{e.label}</strong>
            <time dateTime={e.created_at}>{formatDateTime(e.created_at)}</time>
          </div>
          <div className="timeline__meta">
            {e.actor_name}
            {e.actor_role && e.actor_role !== "SYSTEM" && <span className="muted"> · {e.actor_role.toLowerCase()}</span>}
            {e.to_status && e.from_status !== e.to_status && (
              <span className="muted"> · status: {e.to_status.replace(/_/g, " ").toLowerCase()}</span>
            )}
          </div>
          {e.line && <div className="timeline__line">{e.line}</div>}
          {e.remark && <div className="timeline__remark">“{e.remark}”</div>}
        </li>
      ))}
    </ol>
  );
}
