import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { ErrorState, LoadingState } from "../components/States";
import { useAuth } from "./AuthContext";

/**
 * Shows its children only to signed-in users. External users who haven't chosen their
 * organisation category yet are sent to /profile/category first.
 *
 * This only decides what to *show*; the backend checks the session on every request.
 */
export function RequireAuth({ children, allowMissingCategory = false }: { children: ReactNode; allowMissingCategory?: boolean }) {
  const { status, user, refresh } = useAuth();
  const location = useLocation();

  if (status === "loading") return <LoadingState label="Checking your sign-in…" />;
  if (status === "error")
    return <ErrorState title="Couldn't reach the server" message="Please check the backend is running." onRetry={() => void refresh()} />;
  if (status === "signedOut" || !user) {
    return <Navigate to={`/login?next=${encodeURIComponent(location.pathname)}`} replace />;
  }
  if (user.needs_category && !allowMissingCategory) return <Navigate to="/profile/category" replace />;
  return <>{children}</>;
}
