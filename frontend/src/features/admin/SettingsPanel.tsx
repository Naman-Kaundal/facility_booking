import { useEffect, useState, type FormEvent } from "react";
import { ApiError, errorMessage } from "../../api/client";
import { getSettings, updateSettings } from "../../api/admin";
import { ErrorState, LoadingState } from "../../components/States";
import type { AdminSettings } from "../../types/admin";
import { formatDateTime } from "../../utils/format";

type Form = Record<"gst_pct" | "cleaning_pct" | "security_deposit" | "electricity_advance_pct" | "payment_url", string>;

function toForm(s: AdminSettings): Form {
  return {
    gst_pct: String(s.gst_pct),
    cleaning_pct: String(s.cleaning_pct),
    security_deposit: String(s.security_deposit),
    electricity_advance_pct: String(s.electricity_advance_pct),
    payment_url: s.payment_url ?? "",
  };
}

const FIELDS: { key: keyof Form; label: string; hint: string; suffix?: string }[] = [
  { key: "gst_pct", label: "GST", hint: "Percentage of the booking charges (indicative).", suffix: "%" },
  { key: "cleaning_pct", label: "Cleaning", hint: "Percentage of the booking charges.", suffix: "%" },
  { key: "security_deposit", label: "Security deposit", hint: "Whole rupees, once per request (refundable).", suffix: "₹" },
  {
    key: "electricity_advance_pct",
    label: "Electricity in the advance",
    hint: "Share of Estate's estimate collected in advance.",
    suffix: "%",
  },
];

/** Cost settings and payment link. Changes apply to requests costed from now on. */
export function SettingsPanel() {
  const [settings, setSettings] = useState<AdminSettings | null>(null);
  const [form, setForm] = useState<Form | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = () => {
    setLoadError(null);
    getSettings()
      .then((s) => {
        setSettings(s);
        setForm(toForm(s));
      })
      .catch((err) => setLoadError(errorMessage(err)));
  };
  useEffect(load, []);

  if (loadError) return <ErrorState title="Couldn't load the settings" message={loadError} onRetry={load} />;
  if (!settings || !form) return <LoadingState label="Loading settings…" />;

  async function save(e: FormEvent) {
    e.preventDefault();
    if (!form) return;
    const next: Record<string, string> = {};
    for (const { key, label } of FIELDS) {
      const n = Number(form[key]);
      if (form[key].trim() === "" || !Number.isFinite(n) || n < 0) next[key] = `${label} must be a number, 0 or more.`;
      else if (key !== "security_deposit" && n > 100) next[key] = `${label} can't be more than 100%.`;
      else if (key === "security_deposit" && !Number.isInteger(n)) next[key] = "Use whole rupees.";
    }
    if (form.payment_url && !/^https?:\/\/\S+$/.test(form.payment_url.trim()))
      next.payment_url = "Enter a full web address starting with https://";
    setErrors(next);
    setSaved(false);
    if (Object.keys(next).length) return;
    setBusy(true);
    setFormError(null);
    try {
      const updated = await updateSettings({
        gst_pct: Number(form.gst_pct),
        cleaning_pct: Number(form.cleaning_pct),
        security_deposit: Number(form.security_deposit),
        electricity_advance_pct: Number(form.electricity_advance_pct),
        payment_url: form.payment_url.trim(),
      });
      setSettings(updated);
      setForm(toForm(updated));
      setSaved(true);
    } catch (err) {
      if (err instanceof ApiError) setErrors(err.fieldErrors());
      setFormError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="panel" onSubmit={save} noValidate aria-labelledby="settings-heading">
      <h2 id="settings-heading">Cost settings and payment link</h2>
      <p className="muted">
        Used when Estate's estimate is entered. Requests that are already costed keep the values they were costed with.
      </p>
      <div className="form-grid">
        {FIELDS.map(({ key, label, hint, suffix }) => (
          <div key={key} className={`field${errors[key] ? " field--invalid" : ""}`}>
            <label htmlFor={`setting-${key}`}>
              {label} {suffix && <span className="muted">({suffix})</span>}
            </label>
            <input
              id={`setting-${key}`}
              type="number"
              inputMode="decimal"
              min={0}
              step={key === "security_deposit" ? 1 : 0.01}
              value={form[key]}
              aria-invalid={Boolean(errors[key])}
              onChange={(e) => setForm({ ...form, [key]: e.target.value })}
            />
            <span className="hint">{hint}</span>
            {errors[key] && <span className="field-error">{errors[key]}</span>}
          </div>
        ))}
      </div>
      <div className={`field${errors.payment_url ? " field--invalid" : ""}`}>
        <label htmlFor="setting-payment_url">Institute payment page</label>
        <input
          id="setting-payment_url"
          type="url"
          placeholder="https://…"
          value={form.payment_url}
          aria-invalid={Boolean(errors.payment_url)}
          onChange={(e) => setForm({ ...form, payment_url: e.target.value })}
        />
        <span className="hint">
          The official link requesters use to pay. Enter only a link the Facilities Section has confirmed. Leave it empty
          to block advance intimations.
        </span>
        {errors.payment_url && <span className="field-error">{errors.payment_url}</span>}
      </div>
      {formError && (
        <div className="alert alert--error" role="alert">
          {formError}
        </div>
      )}
      {saved && (
        <div className="alert alert--info" role="status">
          Settings saved.
        </div>
      )}
      <div className="form-actions form-actions--split">
        <span className="hint">
          {settings.updated_by
            ? `Last changed by ${settings.updated_by}${settings.updated_at ? `, ${formatDateTime(settings.updated_at)}` : ""}`
            : "Using the default values."}
        </span>
        <button type="submit" className="button" disabled={busy}>
          {busy ? "Saving…" : "Save settings"}
        </button>
      </div>
    </form>
  );
}
