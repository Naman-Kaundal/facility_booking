"""Costing engine (LLD §9.2, §17.4): formula, rounding, settings and validation."""

from decimal import Decimal

import pytest

from app.services import settings_service
from app.services.costing_service import calculate, money


def test_presentation_example():
    """₹18,000 of bookings, ₹2,500 electricity, default settings (18% GST, 10% cleaning, ₹5,000, 80%)."""
    b = calculate(
        18000, gst_pct=18, cleaning_pct=10, security_deposit=5000, electricity_estimate=2500,
        electricity_advance_pct=80,
    )
    assert b.gst_amount == Decimal("3240.00")
    assert b.cleaning_amount == Decimal("1800.00")
    assert b.electricity_advance == Decimal("2000.00")
    assert b.total_estimated_cost == Decimal("30540.00")  # 18000 + 3240 + 1800 + 5000 + 2500
    assert b.advance_amount == Decimal("30040.00")  # same, but only 80% of electricity


def test_no_charges_lines_cost_only_the_deposit_and_electricity():
    """IIT sports grounds are "No charges": GST and cleaning on ₹0 are ₹0."""
    b = calculate(0, gst_pct=18, cleaning_pct=10, security_deposit=5000, electricity_estimate=0,
                  electricity_advance_pct=80)
    assert (b.gst_amount, b.cleaning_amount) == (Decimal("0.00"), Decimal("0.00"))
    assert b.advance_amount == b.total_estimated_cost == Decimal("5000.00")


def test_rounding_is_half_up_to_the_paisa():
    b = calculate(
        3333, gst_pct=Decimal("12.5"), cleaning_pct=Decimal("7.25"), security_deposit=0,
        electricity_estimate=Decimal("10.01"), electricity_advance_pct=50,
    )
    assert b.gst_amount == Decimal("416.63")  # 416.625 -> 416.63
    assert b.cleaning_amount == Decimal("241.64")  # 241.6425
    assert b.electricity_advance == Decimal("5.01")  # 5.005 -> 5.01
    assert money("0.005") == Decimal("0.01")


@pytest.mark.parametrize(
    "overrides",
    [
        {"electricity_estimate": -1},
        {"security_deposit": -5},
        {"gst_pct": 101},
        {"cleaning_pct": -1},
        {"electricity_advance_pct": 150},
    ],
)
def test_invalid_inputs_are_refused(overrides):
    values = {"gst_pct": 18, "cleaning_pct": 10, "security_deposit": 5000, "electricity_estimate": 100,
              "electricity_advance_pct": 80}
    with pytest.raises(ValueError):
        calculate(1000, **{**values, **overrides})


def test_settings_default_to_the_presentation_values(db):
    s = settings_service.get(db)
    assert (s.gst_pct, s.cleaning_pct, s.security_deposit, s.electricity_advance_pct) == (18, 10, 5000, 80)
    assert s.payment_url is None  # never invented; an admin must enter it
