import { useEffect, useState, type FormEvent } from "react";
import { errorMessage } from "../../api/client";
import { grantStaffRole, listStaffRoles, setStaffRoleActive } from "../../api/admin";
import { useAuth } from "../../auth/AuthContext";
import { ErrorState, LoadingState } from "../../components/States";
import type { StaffRoleRow } from "../../types/admin";
import type { StaffRole } from "../../types/user";
import { formatDateTime } from "../../utils/format";

const ROLES: { role: StaffRole; label: string }[] = [
  { role: "FACILITY", label: "Facilities" },
  { role: "ACADEMIC", label: "Academic section" },
  { role: "SPORTS", label: "Sports section" },
  { role: "ESTATE", label: "Estate" },
  { role: "ADMIN", label: "Admin" },
];
const ROLE_LABEL = Object.fromEntries(ROLES.map((r) => [r.role, r.label])) as Record<StaffRole, string>;

/** Who can use which desk. Roles belong to an email, so they can be given before the first sign-in. */
export function StaffRolesPanel() {
  const { user } = useAuth();
  const [rows, setRows] = useState<StaffRoleRow[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<StaffRole>("FACILITY");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = () => {
    listStaffRoles()
      .then(setRows)
      .catch((err) => setLoadError(errorMessage(err)));
  };
  useEffect(load, []);

  if (loadError) return <ErrorState title="Couldn't load staff roles" message={loadError} onRetry={load} />;
  if (!rows) return <LoadingState label="Loading staff roles…" />;

  async function run(action: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await action();
      setRows(await listStaffRoles());
      return true;
    } catch (err) {
      setError(errorMessage(err));
      return false;
    } finally {
      setBusy(false);
    }
  }

  async function grant(e: FormEvent) {
    e.preventDefault();
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email.trim())) {
      setError("Enter the person's Google email address.");
      return;
    }
    if (await run(() => grantStaffRole(email.trim(), role))) setEmail("");
  }

  return (
    <div className="panel">
      <h2>Staff roles</h2>
      <form className="admin-inline-form" onSubmit={grant} noValidate aria-label="Give a role">
        <div className="field">
          <label htmlFor="role-email">Email</label>
          <input
            id="role-email"
            type="email"
            value={email}
            placeholder="name@iitrpr.ac.in"
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="role-role">Role</label>
          <select id="role-role" value={role} onChange={(e) => setRole(e.target.value as StaffRole)}>
            {ROLES.map((r) => (
              <option key={r.role} value={r.role}>
                {r.label}
              </option>
            ))}
          </select>
        </div>
        <button type="submit" className="button" disabled={busy}>
          Give role
        </button>
      </form>
      {error && (
        <p className="field-error" role="alert">
          {error}
        </p>
      )}

      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th scope="col">Email</th>
              <th scope="col">Role</th>
              <th scope="col">Status</th>
              <th scope="col">Given</th>
              <th scope="col">
                <span className="visually-hidden">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const isMyAdmin = r.role === "ADMIN" && r.email === user?.email;
              return (
                <tr key={r.id} className={r.active ? undefined : "is-inactive"}>
                  <td>{r.email}</td>
                  <td>{ROLE_LABEL[r.role] ?? r.role}</td>
                  <td>{r.active ? "Active" : "Removed"}</td>
                  <td>
                    {formatDateTime(r.assigned_at)}
                    {r.assigned_by && <span className="desk-sub">by {r.assigned_by}</span>}
                  </td>
                  <td className="row-actions">
                    <button
                      type="button"
                      className={`link-button${r.active ? " link-button--danger" : ""}`}
                      disabled={busy || (r.active && isMyAdmin)}
                      title={r.active && isMyAdmin ? "You can't remove your own admin role" : undefined}
                      aria-label={`${r.active ? "Remove" : "Restore"} ${ROLE_LABEL[r.role]} role for ${r.email}`}
                      onClick={() => void run(() => setStaffRoleActive(r.id, !r.active))}
                    >
                      {r.active ? "Remove" : "Restore"}
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
