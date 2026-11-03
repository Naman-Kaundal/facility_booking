import { useState, type FormEvent } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { setRateCategory } from "../../api/auth";
import { errorMessage } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import { CATEGORY_LABELS } from "../../utils/format";

type External = "GOVT" | "PRIVATE";

const OPTIONS: { value: External; hint: string }[] = [
  { value: "GOVT", hint: "Central/State government departments, semi-government bodies and public sector undertakings." },
  { value: "PRIVATE", hint: "Companies, private institutions, societies and other outside agencies." },
];

/** External users pick their organisation category once. IIT accounts never see this page. */
export function CategoryPage() {
  const { user, refresh } = useAuth();
  const navigate = useNavigate();
  const [choice, setChoice] = useState<External | "">(
    user?.rate_category === "GOVT" || user?.rate_category === "PRIVATE" ? user.rate_category : "",
  );
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (user?.is_iit) return <Navigate to="/home" replace />;

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!choice) {
      setError("Choose one option.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await setRateCategory(choice);
      await refresh();
      navigate("/home", { replace: true });
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="page page--narrow" aria-labelledby="category-heading">
      <form className="panel" onSubmit={submit} noValidate>
        <h1 id="category-heading">Your organisation</h1>
        <p className="muted">
          Facility charges depend on the type of organisation booking. Signed in as <strong>{user?.email}</strong>.
        </p>
        <fieldset className="choice-list">
          <legend>Organisation category</legend>
          {OPTIONS.map((option) => (
            <label key={option.value} className={`choice${choice === option.value ? " choice--selected" : ""}`}>
              <input
                type="radio"
                name="category"
                value={option.value}
                checked={choice === option.value}
                onChange={() => setChoice(option.value)}
              />
              <span>
                <strong>{CATEGORY_LABELS[option.value]}</strong>
                <span className="hint">{option.hint}</span>
              </span>
            </label>
          ))}
        </fieldset>
        {error && (
          <p className="field-error" role="alert">
            {error}
          </p>
        )}
        <button type="submit" className="button" disabled={busy}>
          {busy ? "Saving…" : "Continue"}
        </button>
      </form>
    </section>
  );
}
