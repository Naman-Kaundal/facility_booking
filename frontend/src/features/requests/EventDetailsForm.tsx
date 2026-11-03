import { useState, type FormEvent, type ReactElement } from "react";
import { ApiError } from "../../api/client";
import type { EventDetailsInput } from "../../types/request";

type Values = Record<keyof EventDetailsInput, string>;

const EMPTY: Values = {
  organisation_name_address: "",
  applicant_name: "",
  office_contact: "",
  mobile: "",
  purpose: "",
  participants: "",
};

const PHONE = /^\+?[0-9 ()-]{6,20}$/;

/** Mirrors the backend rules so users see problems before submitting. The backend re-checks everything. */
export function validateEvent(values: Values): Partial<Values> {
  const errors: Partial<Values> = {};
  const required: (keyof Values)[] = ["organisation_name_address", "applicant_name", "office_contact", "mobile", "purpose"];
  for (const field of required) if (!values[field].trim()) errors[field] = "This field is required.";
  for (const field of ["office_contact", "mobile"] as const) {
    const v = values[field].trim();
    if (v && (!PHONE.test(v) || v.replace(/\D/g, "").length < 6)) errors[field] = "Enter a valid phone number.";
  }
  const n = Number(values.participants);
  if (!values.participants.trim()) errors.participants = "This field is required.";
  else if (!Number.isInteger(n) || n <= 0) errors.participants = "Enter a whole number greater than 0.";
  return errors;
}

interface Props {
  initial?: Partial<EventDetailsInput>;
  contactEmail: string;
  submitLabel: string;
  onSubmit: (values: EventDetailsInput) => Promise<void>;
  onCancel?: () => void;
}

export function EventDetailsForm({ initial, contactEmail, submitLabel, onSubmit, onCancel }: Props) {
  const [values, setValues] = useState<Values>(() => {
    const start = { ...EMPTY };
    for (const [key, value] of Object.entries(initial ?? {})) {
      if (value !== undefined && value !== null) start[key as keyof Values] = String(value);
    }
    return start;
  });
  const [errors, setErrors] = useState<Partial<Values>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const set = (field: keyof Values) => (e: { target: { value: string } }) =>
    setValues((v) => ({ ...v, [field]: e.target.value }));

  async function submit(event: FormEvent) {
    event.preventDefault();
    const found = validateEvent(values);
    setErrors(found);
    setFormError(null);
    if (Object.keys(found).length > 0) return;
    setBusy(true);
    try {
      await onSubmit({
        organisation_name_address: values.organisation_name_address.trim(),
        applicant_name: values.applicant_name.trim(),
        office_contact: values.office_contact.trim(),
        mobile: values.mobile.trim(),
        purpose: values.purpose.trim(),
        participants: Number(values.participants),
      });
    } catch (err) {
      if (err instanceof ApiError) {
        setErrors(err.fieldErrors() as Partial<Values>);
        setFormError(err.message);
      } else {
        setFormError("Something went wrong. Please try again.");
      }
    } finally {
      setBusy(false);
    }
  }

  const field = (name: keyof Values, label: string, input: ReactElement, hint?: string) => (
    <div className={`field${errors[name] ? " field--invalid" : ""}`}>
      <label htmlFor={name}>{label}</label>
      {input}
      {hint && <p className="hint">{hint}</p>}
      {errors[name] && (
        <p className="field-error" id={`${name}-error`}>
          {errors[name]}
        </p>
      )}
    </div>
  );

  const aria = (name: keyof Values) => ({
    id: name,
    name,
    "aria-invalid": Boolean(errors[name]),
    "aria-describedby": errors[name] ? `${name}-error` : undefined,
  });

  return (
    <form className="form" onSubmit={submit} noValidate>
      {formError && (
        <div className="alert alert--error" role="alert">
          {formError}
        </div>
      )}
      {field(
        "organisation_name_address",
        "Organisation name and address",
        <textarea {...aria("organisation_name_address")} rows={3} value={values.organisation_name_address} onChange={set("organisation_name_address")} />,
      )}
      <div className="form-grid">
        {field(
          "applicant_name",
          "Name of person booking",
          <input {...aria("applicant_name")} type="text" autoComplete="name" value={values.applicant_name} onChange={set("applicant_name")} />,
        )}
        <div className="field">
          <label htmlFor="contact_email">Email</label>
          <input id="contact_email" type="email" value={contactEmail} readOnly aria-readonly="true" />
          <p className="hint">From your Google account.</p>
        </div>
        {field(
          "office_contact",
          "Office contact",
          <input {...aria("office_contact")} type="tel" value={values.office_contact} onChange={set("office_contact")} />,
        )}
        {field(
          "mobile",
          "Mobile",
          <input {...aria("mobile")} type="tel" autoComplete="tel" value={values.mobile} onChange={set("mobile")} />,
        )}
      </div>
      {field(
        "purpose",
        "Purpose / details of the event",
        <textarea {...aria("purpose")} rows={4} value={values.purpose} onChange={set("purpose")} />,
      )}
      {field(
        "participants",
        "Number of participants",
        <input {...aria("participants")} type="number" min={1} step={1} inputMode="numeric" value={values.participants} onChange={set("participants")} />,
      )}
      <div className="form-actions">
        {onCancel && (
          <button type="button" className="button button--secondary" onClick={onCancel}>
            Cancel
          </button>
        )}
        <button type="submit" className="button" disabled={busy}>
          {busy ? "Saving…" : submitLabel}
        </button>
      </div>
    </form>
  );
}
