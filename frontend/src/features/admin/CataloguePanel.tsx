import { useEffect, useState, type FormEvent } from "react";
import { errorMessage } from "../../api/client";
import { addTariff, listAdminFacilities, setTariffActive, updateFacility, updateSlot } from "../../api/admin";
import { ErrorState, LoadingState } from "../../components/States";
import type { AdminFacility, AdminSlot } from "../../types/admin";
import type { RateCategory, SlotUnit } from "../../types/facility";
import { CATEGORY_SHORT, SECTION_LABELS, UNIT_LABELS, formatInr, todayInIndia } from "../../utils/format";

const CATEGORIES: RateCategory[] = ["PRIVATE", "GOVT", "IIT"];

function dateOnly(iso: string): string {
  return new Intl.DateTimeFormat("en-IN", { dateStyle: "medium", timeZone: "Asia/Kolkata" }).format(new Date(iso));
}

/** Facilities, their rates and slot times. Changes apply to new bookings only. */
export function CataloguePanel() {
  const [facilities, setFacilities] = useState<AdminFacility[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = () => {
    listAdminFacilities()
      .then((items) => {
        setFacilities(items);
        setSelectedId((id) => id ?? items[0]?.id ?? null);
      })
      .catch((err) => setLoadError(errorMessage(err)));
  };
  useEffect(load, []);

  if (loadError) return <ErrorState title="Couldn't load the catalogue" message={loadError} onRetry={load} />;
  if (!facilities) return <LoadingState label="Loading facilities…" />;
  const facility = facilities.find((f) => f.id === selectedId) ?? null;

  async function run(action: () => Promise<AdminFacility>, done: string) {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const updated = await action();
      setFacilities((list) => list?.map((f) => (f.id === updated.id ? updated : f)) ?? null);
      setNotice(done);
      return true;
    } catch (err) {
      setError(errorMessage(err));
      return false;
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="admin-catalogue">
      <nav className="panel admin-catalogue__list" aria-label="Facilities">
        <h2>Facilities</h2>
        <ul>
          {facilities.map((f) => (
            <li key={f.id}>
              <button
                type="button"
                className={`admin-catalogue__item${f.id === selectedId ? " is-selected" : ""}`}
                aria-current={f.id === selectedId ? "true" : undefined}
                onClick={() => {
                  setSelectedId(f.id);
                  setError(null);
                  setNotice(null);
                }}
              >
                {f.name}
                {!f.active && <span className="tag tag--outline">Inactive</span>}
              </button>
            </li>
          ))}
        </ul>
      </nav>

      {facility && (
        <div className="admin-catalogue__detail">
          {error && (
            <div className="alert alert--error" role="alert">
              {error}
            </div>
          )}
          {notice && (
            <div className="alert alert--info" role="status">
              {notice}
            </div>
          )}
          <FacilityForm key={`f-${facility.id}`} facility={facility} busy={busy} run={run} />
          <TariffSection key={`t-${facility.id}`} facility={facility} busy={busy} run={run} />
          <SlotSection key={`s-${facility.id}`} facility={facility} busy={busy} run={run} />
        </div>
      )}
    </div>
  );
}

type Run = (action: () => Promise<AdminFacility>, done: string) => Promise<boolean>;

function FacilityForm({ facility, busy, run }: { facility: AdminFacility; busy: boolean; run: Run }) {
  const [name, setName] = useState(facility.name);
  const [capacity, setCapacity] = useState(facility.capacity ? String(facility.capacity) : "");

  function save(e: FormEvent) {
    e.preventDefault();
    const cap = capacity.trim() === "" ? null : Number(capacity);
    void run(() => updateFacility(facility.id, { name: name.trim(), capacity: cap }), "Facility saved.");
  }

  return (
    <form className="panel" onSubmit={save} aria-labelledby="facility-heading">
      <div className="panel__header">
        <h2 id="facility-heading">{facility.name}</h2>
        <span className="muted">
          {facility.code} · {SECTION_LABELS[facility.section]}
        </span>
      </div>
      <div className="form-grid">
        <div className="field">
          <label htmlFor="facility-name">Name</label>
          <input id="facility-name" value={name} maxLength={200} onChange={(e) => setName(e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="facility-capacity">Capacity (seats)</label>
          <input
            id="facility-capacity"
            type="number"
            min={1}
            value={capacity}
            onChange={(e) => setCapacity(e.target.value)}
          />
        </div>
      </div>
      <div className="form-actions form-actions--split">
        <button
          type="button"
          className={`button ${facility.active ? "button--danger" : "button--secondary"}`}
          disabled={busy}
          onClick={() =>
            void run(
              () => updateFacility(facility.id, { active: !facility.active }),
              facility.active ? "Facility hidden from new bookings." : "Facility can be booked again.",
            )
          }
        >
          {facility.active ? "Stop new bookings" : "Allow bookings again"}
        </button>
        <button type="submit" className="button" disabled={busy || !name.trim()}>
          Save
        </button>
      </div>
    </form>
  );
}

function TariffSection({ facility, busy, run }: { facility: AdminFacility; busy: boolean; run: Run }) {
  const [category, setCategory] = useState<RateCategory>("PRIVATE");
  const [unit, setUnit] = useState<SlotUnit>(facility.slot_types[0]);
  const [amount, setAmount] = useState("");
  const [from, setFrom] = useState(todayInIndia());
  const [formError, setFormError] = useState<string | null>(null);

  async function add(e: FormEvent) {
    e.preventDefault();
    const value = Number(amount);
    if (amount.trim() === "" || !Number.isInteger(value) || value < 0) {
      setFormError("Enter the rate in whole rupees (0 means no charges).");
      return;
    }
    setFormError(null);
    const ok = await run(
      () => addTariff({ facility_id: facility.id, category, unit, amount: value, effective_from: from }),
      "New rate added. Requests already submitted keep their old rate.",
    );
    if (ok) setAmount("");
  }

  return (
    <div className="panel">
      <h2>Rates</h2>
      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th scope="col">Category</th>
              <th scope="col">Unit</th>
              <th scope="col" className="num">
                Rate
              </th>
              <th scope="col">From</th>
              <th scope="col">Until</th>
              <th scope="col">Status</th>
              <th scope="col">
                <span className="visually-hidden">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {facility.tariffs.map((t) => (
              <tr key={t.id} className={t.active ? undefined : "is-inactive"}>
                <td>{CATEGORY_SHORT[t.category]}</td>
                <td>{UNIT_LABELS[t.unit]}</td>
                <td className="num">{formatInr(t.amount)}</td>
                <td>{dateOnly(t.effective_from)}</td>
                <td>{t.effective_to ? dateOnly(t.effective_to) : "—"}</td>
                <td>{!t.active ? "Off" : t.current ? "In effect" : new Date(t.effective_from) > new Date() ? "Scheduled" : "Ended"}</td>
                <td className="row-actions">
                  <button
                    type="button"
                    className="link-button"
                    disabled={busy}
                    onClick={() => void run(() => setTariffActive(t.id, !t.active), t.active ? "Rate switched off." : "Rate switched on.")}
                  >
                    {t.active ? "Switch off" : "Switch on"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <form className="admin-inline-form" onSubmit={add} noValidate aria-label="Add a new rate">
        <div className="field">
          <label htmlFor="tariff-category">Category</label>
          <select id="tariff-category" value={category} onChange={(e) => setCategory(e.target.value as RateCategory)}>
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {CATEGORY_SHORT[c]}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="tariff-unit">Unit</label>
          <select id="tariff-unit" value={unit} onChange={(e) => setUnit(e.target.value as SlotUnit)}>
            {facility.slot_types.map((u) => (
              <option key={u} value={u}>
                {UNIT_LABELS[u]}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="tariff-amount">New rate (₹)</label>
          <input
            id="tariff-amount"
            type="number"
            min={0}
            step={1}
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="tariff-from">Starts on</label>
          <input id="tariff-from" type="date" min={todayInIndia()} value={from} onChange={(e) => setFrom(e.target.value)} />
        </div>
        <button type="submit" className="button" disabled={busy}>
          Add rate
        </button>
      </form>
      {formError && (
        <p className="field-error" role="alert">
          {formError}
        </p>
      )}
      <p className="hint">The current rate for that category ends the day the new one starts.</p>
    </div>
  );
}

function SlotSection({ facility, busy, run }: { facility: AdminFacility; busy: boolean; run: Run }) {
  return (
    <div className="panel">
      <h2>Slots</h2>
      <ul className="admin-slots">
        {facility.slots.map((slot) => (
          <SlotRow key={slot.id} slot={slot} busy={busy} run={run} />
        ))}
      </ul>
      <p className="hint">Changing times affects new bookings. Bookings already confirmed keep the times they reserved.</p>
    </div>
  );
}

function SlotRow({ slot, busy, run }: { slot: AdminSlot; busy: boolean; run: Run }) {
  const [start, setStart] = useState(slot.start ?? "");
  const [end, setEnd] = useState(slot.end ?? "");
  const [label, setLabel] = useState(slot.label);
  const timed = slot.start !== null;

  function save(e: FormEvent) {
    e.preventDefault();
    const patch = timed ? { label: label.trim(), start, end } : { label: label.trim() };
    void run(() => updateSlot(slot.id, patch), "Slot saved.");
  }

  return (
    <li className={slot.active ? undefined : "is-inactive"}>
      <form className="admin-inline-form" onSubmit={save} aria-label={`Slot ${slot.label}`}>
        <div className="field">
          <label htmlFor={`slot-label-${slot.id}`}>Label</label>
          <input id={`slot-label-${slot.id}`} value={label} maxLength={100} onChange={(e) => setLabel(e.target.value)} />
        </div>
        {timed && (
          <>
            <div className="field">
              <label htmlFor={`slot-start-${slot.id}`}>Start</label>
              <input id={`slot-start-${slot.id}`} type="time" value={start} onChange={(e) => setStart(e.target.value)} />
            </div>
            <div className="field">
              <label htmlFor={`slot-end-${slot.id}`}>End</label>
              <input id={`slot-end-${slot.id}`} type="time" value={end} onChange={(e) => setEnd(e.target.value)} />
            </div>
          </>
        )}
        <button type="submit" className="button button--secondary" disabled={busy || !label.trim()}>
          Save
        </button>
        <button
          type="button"
          className="link-button"
          disabled={busy}
          onClick={() => void run(() => updateSlot(slot.id, { active: !slot.active }), slot.active ? "Slot switched off." : "Slot switched on.")}
        >
          {slot.active ? "Switch off" : "Switch on"}
        </button>
      </form>
    </li>
  );
}
