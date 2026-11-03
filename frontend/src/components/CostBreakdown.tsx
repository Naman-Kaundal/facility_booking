import type { CostBreakdown as Costs } from "../types/costs";
import { formatDate, formatDateTime, formatMoney, formatPct } from "../utils/format";
import "../styles/costs.css";

/**
 * The cost and advance breakdown (LLD §9). Every number comes from the backend; the browser
 * never calculates or sends amounts.
 */
export function CostBreakdown({ costs, title = "Cost breakdown" }: { costs: Costs; title?: string }) {
  return (
    <section className="costs" aria-labelledby="costs-heading">
      <h2 id="costs-heading">{title}</h2>
      {costs.items.length > 0 && (
        <table className="costs__items">
          <caption className="visually-hidden">Confirmed facilities</caption>
          <tbody>
            {costs.items.map((item) => (
              <tr key={item.line_id}>
                <th scope="row">
                  {item.facility_name}
                  <span className="muted">
                    {" "}
                    · {formatDate(item.booking_date)} · {item.slot_label}
                  </span>
                </th>
                <td className="num">{formatMoney(item.amount)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <table className="costs__table">
        <caption className="visually-hidden">Charges</caption>
        <tbody>
          <tr>
            <th scope="row">Booking charges (confirmed facilities)</th>
            <td className="num">{formatMoney(costs.booking_subtotal)}</td>
          </tr>
          <tr>
            <th scope="row">GST ({formatPct(costs.gst_pct)}, indicative)</th>
            <td className="num">{formatMoney(costs.gst_amount)}</td>
          </tr>
          <tr>
            <th scope="row">Cleaning ({formatPct(costs.cleaning_pct)})</th>
            <td className="num">{formatMoney(costs.cleaning_amount)}</td>
          </tr>
          <tr>
            <th scope="row">Security deposit (refundable)</th>
            <td className="num">{formatMoney(costs.security_deposit)}</td>
          </tr>
          <tr>
            <th scope="row">
              Electricity (approximate, from Estate)
              {costs.estimate_remark && <span className="costs__remark">“{costs.estimate_remark}”</span>}
            </th>
            <td className="num">{formatMoney(costs.electricity_estimate)}</td>
          </tr>
          <tr className="costs__total">
            <th scope="row">Total estimated cost</th>
            <td className="num">{formatMoney(costs.total_estimated_cost)}</td>
          </tr>
        </tbody>
      </table>

      <div className="costs__advance" role="group" aria-label="Advance to pay">
        <div>
          <strong>Advance to pay</strong>
          <span className="muted">
            Booking charges + GST + cleaning + deposit + {formatPct(costs.electricity_advance_pct)} of electricity (
            {formatMoney(costs.electricity_advance)})
          </span>
        </div>
        <strong className="costs__advance-amount">{formatMoney(costs.advance_amount)}</strong>
      </div>

      <p className="hint">
        Calculated {formatDateTime(costs.calculated_at)}
        {costs.calculated_by_name && ` after ${costs.calculated_by_name}'s electricity estimate`}.
        {costs.intimated_at && ` Advance intimated ${formatDateTime(costs.intimated_at)}.`}
      </p>
    </section>
  );
}

/** The requester's payment instructions: only a link to the institute page, no payment in this app. */
export function PaymentInstructions({ costs, refNo }: { costs: Costs; refNo: string | null }) {
  if (!costs.payment_url) return null;
  return (
    <div className="payment" role="region" aria-label="How to pay">
      <h2>Pay the advance</h2>
      <p>
        Pay <strong>{formatMoney(costs.advance_amount)}</strong> on the institute payment page and quote your reference
        number <strong>{refNo}</strong>. This app doesn't take payments itself.
      </p>
      <a className="button" href={costs.payment_url} target="_blank" rel="noopener noreferrer">
        Open the institute payment page
      </a>
    </div>
  );
}
