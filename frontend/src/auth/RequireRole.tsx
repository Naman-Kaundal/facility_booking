import type { ReactNode } from "react";
import { ErrorState } from "../components/States";
import type { StaffRole } from "../types/user";
import { RequireAuth } from "./RequireAuth";
import { useAuth } from "./AuthContext";

/**
 * Shows its children only to signed-in staff holding one of `roles`.
 * This only hides pages; every staff endpoint checks the role again on the server.
 */
export function RequireRole({ roles, children }: { roles: StaffRole[]; children: ReactNode }) {
  return (
    <RequireAuth>
      <RoleGate roles={roles}>{children}</RoleGate>
    </RequireAuth>
  );
}

function RoleGate({ roles, children }: { roles: StaffRole[]; children: ReactNode }) {
  const { user } = useAuth();
  if (!user?.roles?.some((r) => roles.includes(r)))
    return <ErrorState title="Staff only" message="Your account doesn't have access to this desk." />;
  return <>{children}</>;
}
