import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { fetchMe, logout } from "../api/auth";
import { ApiError, setCsrfToken } from "../api/client";
import type { Me } from "../types/user";

type AuthStatus = "loading" | "signedOut" | "signedIn" | "error";

interface AuthValue {
  status: AuthStatus;
  user: Me | null;
  /** Re-read the signed-in user from the server (after sign-in or a profile change). */
  refresh: () => Promise<Me | null>;
  signOut: () => Promise<void>;
}

// The default lets components that only *read* auth (e.g. the public catalogue) render without a provider.
const AuthContext = createContext<AuthValue>({
  status: "signedOut",
  user: null,
  refresh: async () => null,
  signOut: async () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [user, setUser] = useState<Me | null>(null);

  const apply = useCallback((me: Me | null, next: AuthStatus) => {
    setCsrfToken(me?.csrf_token ?? null);
    setUser(me);
    setStatus(next);
  }, []);

  const refresh = useCallback(async () => {
    try {
      const me = await fetchMe();
      apply(me, "signedIn");
      return me;
    } catch (err) {
      apply(null, err instanceof ApiError && err.status === 401 ? "signedOut" : "error");
      return null;
    }
  }, [apply]);

  const signOut = useCallback(async () => {
    try {
      await logout();
    } finally {
      apply(null, "signedOut");
    }
  }, [apply]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const value = useMemo(() => ({ status, user, refresh, signOut }), [status, user, refresh, signOut]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  return useContext(AuthContext);
}
