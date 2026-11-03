import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { getAvailability } from "../../api/availability";
import { errorMessage } from "../../api/client";
import { fetchFacilities } from "../../api/facilities";
import { addLine, deleteLine, updateLine } from "../../api/requests";
import { useAuth } from "../../auth/AuthContext";
import { StepIndicator } from "../../components/StepIndicator";
import { ErrorState, LoadingState } from "../../components/States";
import type { Facility, FacilityGroup } from "../../types/facility";
import type { SlotAvailability } from "../../types/availability";
import type { RequestLine } from "../../types/request";
import { CATEGORY_SHORT, GROUP_LABELS, SECTION_LABELS, formatDate, formatInr, formatTotal, todayInIndia } from "../../utils/format";
import { useRequest } from "./useRequest";

const GROUP_ORDER: FacilityGroup[] = ["LHC", "AUDITORIUM", "SPORTS"];

interface LineForm {
  facilityId: string;
  date: string;
  slotKey: string;
}

const EMPTY_FORM: LineForm = { facilityId: "", date: "", slotKey: "" };

/** Step 2: add one or more facilities, each with its own date and slot. */
export function FacilityLinesPage() {
  const id = Number(useParams().id);
  const navigate = useNavigate();
  const { user } = useAuth();
  const { request, setRequest, error, reload } = useRequest(id);
  const [facilities, setFacilities] = useState<Facility[] | null>(null);
  const [catalogueError, setCatalogueError] = useState<string | null>(null);
  const [form, setForm] = useState<LineForm>(EMPTY_FORM);
  const [editingLineId, setEditingLineId] = useState<number | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  // Week 3: which slots are already booked (confirmed) for the chosen facility and date.
  const [availability, setAvailability] = useState<Record<string, SlotAvailability>>({});

  useEffect(() => {
    if (!form.facilityId || !form.date) {
      setAvailability({});
      return;
    }
    let cancelled = false;
    getAvailability(Number(form.facilityId), form.date)
      .then((data) => {
        if (!cancelled) setAvailability(Object.fromEntries(data.slots.map((s) => [s.slot_key, s])));
      })
      .catch(() => {
        if (!cancelled) setAvailability({}); // availability is a hint; the server re-checks on submit
      });
    return () => {
      cancelled = true;
    };
  }, [form.facilityId, form.date]);

  useEffect(() => {
    fetchFacilities()
      .then((data) => setFacilities(data.items))
      .catch((err) => setCatalogueError(errorMessage(err)));
  }, []);

  const facility = useMemo(
    () => facilities?.find((f) => String(f.id) === form.facilityId) ?? null,
    [facilities, form.facilityId],
  );
  const slot = facility?.slot_options.find((s) => s.slot_key === form.slotKey) ?? null;
  const rate =
    facility && slot && user?.rate_category
      ? facility.tariffs.find((t) => t.unit === slot.slot_type && t.category === user.rate_category)
      : undefined;

  if (error || catalogueError)
    return <ErrorState title="Couldn't load this page" message={error ?? catalogueError ?? ""} onRetry={reload} />;
  if (!request || !facilities) return <LoadingState label="Loading…" />;
  if (!request.editable)
    return <ErrorState title="Can't edit this request" message="Only draft requests can be changed." />;

  const today = todayInIndia();

  function startEdit(line: RequestLine) {
    setEditingLineId(line.id);
    setForm({ facilityId: String(line.facility_id), date: line.booking_date, slotKey: line.slot_key });
    setFormError(null);
  }

  function resetForm() {
    setEditingLineId(null);
    setForm(EMPTY_FORM);
    setFormError(null);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!form.facilityId || !form.date || !form.slotKey) {
      setFormError("Choose a facility, a date and a slot.");
      return;
    }
    if (form.date < today) {
      setFormError("The date can't be in the past.");
      return;
    }
    setBusy(true);
    setFormError(null);
    const line = { facility_id: Number(form.facilityId), booking_date: form.date, slot_key: form.slotKey };
    try {
      const updated = editingLineId ? await updateLine(id, editingLineId, line) : await addLine(id, line);
      setRequest(updated);
      resetForm();
    } catch (err) {
      setFormError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function remove(line: RequestLine) {
    setBusy(true);
    try {
      setRequest(await deleteLine(id, line.id));
      if (editingLineId === line.id) resetForm();
    } catch (err) {
      setFormError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  const preview = request.charges_preview;

  return (
    <section className="page page--form" aria-labelledby="lines-heading">
      <StepIndicator current={2} />
      <h1 id="lines-heading">Facilities and dates</h1>
      <p className="muted">
        For: <strong>{request.event.purpose}</strong> · <Link to={`/requests/${id}/edit`}>Edit event details</Link>
      </p>

      <form className="panel line-form" onSubmit={submit} noValidate aria-labelledby="line-form-heading">
        <h2 id="line-form-heading">{editingLineId ? "Edit facility" : "Add a facility"}</h2>
        <div className="form-grid form-grid--3">
          <div className="field">
            <label htmlFor="facility">Facility</label>
            <select
              id="facility"
              value={form.facilityId}
              onChange={(e) => setForm({ facilityId: e.target.value, date: form.date, slotKey: "" })}
            >
              <option value="">Choose a facility…</option>
              {GROUP_ORDER.map((group) => (
                <optgroup key={group} label={GROUP_LABELS[group]}>
                  {facilities
                    .filter((f) => f.group === group)
                    .map((f) => (
                      <option key={f.id} value={f.id}>
                        {f.name}
                        {f.capacity ? ` (${f.capacity} seats)` : ""}
                      </option>
                    ))}
                </optgroup>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="date">Date</label>
            <input
              id="date"
              type="date"
              min={today}
              value={form.date}
              onChange={(e) => setForm({ ...form, date: e.target.value })}
            />
          </div>
          <div className="field">
            <label htmlFor="slot">Slot</label>
            <select
              id="slot"
              value={form.slotKey}
              disabled={!facility}
              onChange={(e) => setForm({ ...form, slotKey: e.target.value })}
            >
              <option value="">{facility ? "Choose a slot…" : "Choose a facility first"}</option>
              {facility?.slot_options.map((s) => {
                const taken = availability[s.slot_key]?.available === false;
                return (
                  <option key={s.slot_key} value={s.slot_key} disabled={taken}>
                    {s.slot_type === "HALF_DAY" ? `Half day: ${s.label}` : s.label}
                    {taken ? " (already booked)" : ""}
                  </option>
                );
              })}
            </select>
          </div>
        </div>

        {facility && (
          <p className="line-form__info" aria-live="polite">
            {SECTION_LABELS[facility.section]} will review this facility.
            {rate && user?.rate_category && (
              <>
                {" "}
                Rate ({CATEGORY_SHORT[user.rate_category]}): <strong>{formatInr(rate.amount)}</strong>
              </>
            )}
          </p>
        )}
        {formError && (
          <p className="field-error" role="alert">
            {formError}
          </p>
        )}
        <div className="form-actions">
          {editingLineId && (
            <button type="button" className="button button--secondary" onClick={resetForm}>
              Cancel edit
            </button>
          )}
          <button type="submit" className="button" disabled={busy}>
            {editingLineId ? "Save facility" : "Add facility"}
          </button>
        </div>
      </form>

      <h2>Added facilities ({request.lines.length})</h2>
      {request.lines.length === 0 ? (
        <p className="muted">No facilities yet. Add at least one above.</p>
      ) : (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">Facility</th>
                <th scope="col">Section</th>
                <th scope="col">Date</th>
                <th scope="col">Slot</th>
                <th scope="col" className="num">
                  Rate
                </th>
                <th scope="col">
                  <span className="visually-hidden">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {request.lines.map((line) => (
                <tr key={line.id} className={line.id === editingLineId ? "is-editing" : undefined}>
                  <td>{line.facility_name}</td>
                  <td>{SECTION_LABELS[line.section]}</td>
                  <td>{formatDate(line.booking_date)}</td>
                  <td>{line.slot_label}</td>
                  <td className="num">{line.rate ? formatInr(line.rate.amount) : "—"}</td>
                  <td className="row-actions">
                    <button type="button" className="link-button" onClick={() => startEdit(line)} disabled={busy}>
                      Edit
                    </button>
                    <button
                      type="button"
                      className="link-button link-button--danger"
                      onClick={() => void remove(line)}
                      disabled={busy}
                      aria-label={`Remove ${line.facility_name} on ${formatDate(line.booking_date)}`}
                    >
                      Remove
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr>
                <th scope="row" colSpan={4}>
                  Booking charges subtotal
                </th>
                <td className="num">
                  <strong>{formatTotal(preview.booking_subtotal)}</strong>
                </td>
                <td />
              </tr>
            </tfoot>
          </table>
        </div>
      )}
      <p className="hint">{preview.note}</p>

      <div className="form-actions">
        <button type="button" className="button button--secondary" onClick={() => navigate(`/requests/${id}`)}>
          Save and finish later
        </button>
        <button
          type="button"
          className="button"
          disabled={request.lines.length === 0}
          onClick={() => navigate(`/requests/${id}/review`)}
        >
          Continue to review
        </button>
      </div>
    </section>
  );
}
