import type { Facility, RateCategory, SlotUnit } from "../../types/facility";
import { CATEGORY_LABELS, CATEGORY_SHORT, GROUP_LABELS, SECTION_LABELS, UNIT_LABELS, formatInr } from "../../utils/format";

const CATEGORIES: RateCategory[] = ["PRIVATE", "GOVT", "IIT"];

export function FacilityCard({ facility, highlight }: { facility: Facility; highlight?: RateCategory | null }) {
  const headingId = `facility-${facility.code}`;
  const units = facility.slot_types;

  const amountFor = (unit: SlotUnit, category: RateCategory) =>
    facility.tariffs.find((t) => t.unit === unit && t.category === category);

  return (
    <article className="card" aria-labelledby={headingId} data-testid="facility-card">
      <header className="card__header">
        <h2 id={headingId} className="card__title">
          {facility.name}
        </h2>
        <div className="tags">
          <span className={`tag tag--${facility.group.toLowerCase()}`}>{GROUP_LABELS[facility.group]}</span>
          <span className="tag tag--outline">{SECTION_LABELS[facility.section]}</span>
        </div>
      </header>

      <dl className="facts">
        <div>
          <dt>Capacity</dt>
          <dd>{facility.capacity ? `${facility.capacity} seats` : "—"}</dd>
        </div>
        <div>
          <dt>Booked as</dt>
          <dd>{units.map((u) => UNIT_LABELS[u]).join(" or ")}</dd>
        </div>
      </dl>

      {facility.slot_options.length > 1 && (
        <div className="slots">
          <span className="slots__label">Slots</span>
          <ul className="slots__list">
            {facility.slot_options.map((slot) => (
              <li key={slot.slot_key} className="slot-chip">
                {slot.label}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="table-wrap">
        <table className="tariff-table">
          <caption className="visually-hidden">Indicative tariff for {facility.name}</caption>
          <thead>
            <tr>
              <th scope="col">Rate</th>
              {CATEGORIES.map((c) => (
                <th key={c} scope="col" title={CATEGORY_LABELS[c]} className={c === highlight ? "is-mine" : undefined}>
                  {CATEGORY_SHORT[c]}
                  {c === highlight && <span className="visually-hidden"> (your rate)</span>}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {units.map((unit) => (
              <tr key={unit}>
                <th scope="row">{UNIT_LABELS[unit]}</th>
                {CATEGORIES.map((c) => {
                  const tariff = amountFor(unit, c);
                  return (
                    <td
                      key={c}
                      className={[tariff?.amount === 0 ? "is-free" : "", c === highlight ? "is-mine" : ""].join(" ").trim() || undefined}
                    >
                      {tariff ? formatInr(tariff.amount) : "—"}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {facility.notes && <p className="card__note">{facility.notes}</p>}
    </article>
  );
}
