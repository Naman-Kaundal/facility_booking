import { useEffect, useState, type FormEvent } from "react";
import { Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { devLogin, fetchAuthConfig, GOOGLE_SIGN_IN_URL } from "../../api/auth";
import { errorMessage } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import { LoadingState } from "../../components/States";
import type { AuthConfig } from "../../types/user";

const ERRORS: Record<string, string> = {
  GOOGLE_CANCELLED: "Sign-in was cancelled at Google.",
  INVALID_STATE: "That sign-in link expired or didn't match. Please try again.",
  EMAIL_NOT_VERIFIED: "Your Google account's email address isn't verified.",
  INVALID_ID_TOKEN: "Google's sign-in couldn't be verified. Please try again.",
  GOOGLE_CODE_REJECTED: "Google rejected the sign-in. Please try again.",
  GOOGLE_UNREACHABLE: "Couldn't reach Google. Check your internet connection and try again.",
  GOOGLE_NOT_CONFIGURED: "Google sign-in isn't set up on this server yet (missing client ID/secret).",
};

export function LoginPage() {
  const { status, user, refresh } = useAuth();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [config, setConfig] = useState<AuthConfig | null>(null);
  const [devEmail, setDevEmail] = useState("");
  const [devError, setDevError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    fetchAuthConfig()
      .then(setConfig)
      .catch(() => setConfig({ google_enabled: true, dev_login_enabled: false }));
  }, []);

  if (status === "loading") return <LoadingState label="Checking your sign-in…" />;
  if (status === "signedIn" && user) return <Navigate to={user.needs_category ? "/profile/category" : params.get("next") || "/home"} replace />;

  const errorCode = params.get("error");

  async function submitDevLogin(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setDevError(null);
    try {
      await devLogin(devEmail.trim(), "");
      const me = await refresh();
      navigate(me?.needs_category ? "/profile/category" : "/home", { replace: true });
    } catch (err) {
      setDevError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="page page--narrow" aria-labelledby="login-heading">
      <div className="panel">
        <h1 id="login-heading">Sign in</h1>
        <p className="muted">
          Book IIT Ropar lecture halls, the auditorium and sports grounds. Sign in with your Google account. IIT Ropar
          (@iitrpr.ac.in) accounts get institute rates automatically.
        </p>

        {errorCode && (
          <div className="alert alert--error" role="alert">
            {ERRORS[errorCode] ?? "Sign-in failed. Please try again."}
          </div>
        )}

        <a className="button button--google" href={GOOGLE_SIGN_IN_URL}>
          <span className="google-mark" aria-hidden="true">
            G
          </span>
          Continue with Google
        </a>
        {config && !config.google_enabled && (
          <p className="hint">Google sign-in isn't configured on this server yet.</p>
        )}

        {config?.dev_login_enabled && (
          <form className="dev-login" onSubmit={submitDevLogin}>
            <h2>Development sign-in</h2>
            <p className="hint">
              For local testing only. This is switched off unless the server runs with DEV_LOGIN_ENABLED=true in
              development.
            </p>
            <label htmlFor="dev-email">Email</label>
            <div className="inline-field">
              <input
                id="dev-email"
                type="email"
                required
                value={devEmail}
                onChange={(e) => setDevEmail(e.target.value)}
                placeholder="name@iitrpr.ac.in"
              />
              <button type="submit" className="button button--secondary" disabled={busy}>
                Sign in
              </button>
            </div>
            {devError && (
              <p className="field-error" role="alert">
                {devError}
              </p>
            )}
          </form>
        )}
      </div>
    </section>
  );
}
