import { useSearchParams } from "react-router-dom";
import { AuditPanel } from "./AuditPanel";
import { CataloguePanel } from "./CataloguePanel";
import { EmailLogPanel } from "./EmailLogPanel";
import { SettingsPanel } from "./SettingsPanel";
import { StaffRolesPanel } from "./StaffRolesPanel";
import "../../styles/admin.css";

const TABS = [
  { key: "settings", label: "Settings", Panel: SettingsPanel },
  { key: "roles", label: "Staff roles", Panel: StaffRolesPanel },
  { key: "catalogue", label: "Facilities & rates", Panel: CataloguePanel },
  { key: "emails", label: "Email log", Panel: EmailLogPanel },
  { key: "audit", label: "Change log", Panel: AuditPanel },
] as const;

/** Admin area (ADMIN role only; the backend checks the role on every call). */
export function AdminPage() {
  const [params, setParams] = useSearchParams();
  const current = TABS.find((t) => t.key === params.get("tab")) ?? TABS[0];
  const { Panel } = current;

  return (
    <section className="page" aria-labelledby="admin-heading">
      <div className="page__header">
        <div>
          <p className="eyebrow">Admin</p>
          <h1 id="admin-heading">Administration</h1>
          <p className="muted">Changes here apply to new bookings and costings. Every change is logged.</p>
        </div>
      </div>
      <div className="tabs" role="tablist" aria-label="Admin sections">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            role="tab"
            id={`tab-${t.key}`}
            aria-selected={t.key === current.key}
            aria-controls="admin-panel"
            className={`tabs__tab${t.key === current.key ? " is-active" : ""}`}
            onClick={() => setParams({ tab: t.key })}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div role="tabpanel" id="admin-panel" aria-labelledby={`tab-${current.key}`}>
        <Panel />
      </div>
    </section>
  );
}
