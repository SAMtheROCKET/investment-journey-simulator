"""Rate conversion tests, benchmarked against closed-form math."""

from __future__ import annotations

import pytest

from investment_journey_simulator.constants import (
    EXPENSE_MODEL_ACCRUED_STR,
    EXPENSE_MODEL_SIMPLE_STR,
    MINIMUM_ANNUAL_RETURN_PERCENT_FLOAT,
)
from investment_journey_simulator.returns import (
    apply_annual_growth_factor_float,
    calculate_growth_factor_float,
    calculate_monthly_rate_after_expense_float,
    calculate_net_return_percent_float,
    clamp_annual_return_percent_float,
    clamp_expense_percent_float,
    convert_annual_to_monthly_rate_float,
    convert_monthly_to_annual_percent_float,
    convert_nominal_to_real_percent_float,
)

TOLERANCE_FLOAT: float = 1e-12


@pytest.mark.parametrize(
    "annual_percent_float",
    [0.0, 6.0, 8.0, 12.0, 14.0, 25.0, -5.0],
)
def test_monthly_rate_compounds_back_to_annual(
    annual_percent_float: float,
) -> None:
    """Twelve monthly steps must reproduce the annual return.

    REFERENCE: G1-ANALYTIC. Definition of an effective rate:
    (1 + i_monthly)^12 - 1 == R_annual.
    """
    monthly_rate_float = convert_annual_to_monthly_rate_float(
        annual_percent_float
    )
    rebuilt_annual_float = (
        (1.0 + monthly_rate_float) ** 12 - 1.0
    ) * 100.0
    assert rebuilt_annual_float == pytest.approx(
        annual_percent_float, abs=1e-10
    )


def test_zero_return_gives_zero_monthly_rate() -> None:
    """A zero return must not move money at all.

    REFERENCE: G1-ANALYTIC. Edge case at the identity element.
    """
    assert convert_annual_to_monthly_rate_float(0.0) == 0.0


def test_monthly_and_annual_conversions_are_inverses() -> None:
    """Annualising a monthly rate must return the input.

    REFERENCE: G1-ANALYTIC. Round-trip inverse property.
    """
    original_percent_float = 12.0
    monthly_rate_float = convert_annual_to_monthly_rate_float(
        original_percent_float
    )
    assert convert_monthly_to_annual_percent_float(
        monthly_rate_float
    ) == pytest.approx(original_percent_float, abs=1e-10)


@pytest.mark.parametrize(
    "requested_float, expected_float",
    [
        (12.0, 12.0),
        (0.0, 0.0),
        (-50.0, -50.0),
        (-100.0, MINIMUM_ANNUAL_RETURN_PERCENT_FLOAT),
        (-250.0, MINIMUM_ANNUAL_RETURN_PERCENT_FLOAT),
    ],
)
def test_return_clamp_covers_every_branch(
    requested_float: float,
    expected_float: float,
) -> None:
    """Returns at or below total loss must be clamped.

    REFERENCE: G4-SYNTHETIC. A rate of -100% makes the twelfth
    root of (1 + r) undefined for further compounding.
    """
    assert clamp_annual_return_percent_float(
        requested_float
    ) == pytest.approx(expected_float)


def test_catastrophic_return_does_not_raise() -> None:
    """A -100% input must degrade gracefully, not crash.

    REFERENCE: G4-SYNTHETIC. Robustness against user input.
    """
    monthly_rate_float = convert_annual_to_monthly_rate_float(-100.0)
    assert monthly_rate_float < 0.0
    assert monthly_rate_float > -1.0


@pytest.mark.parametrize(
    "requested_float, expected_float",
    [(0.5, 0.5), (-1.0, 0.0), (0.0, 0.0), (150.0, 99.99)],
)
def test_expense_clamp_covers_every_branch(
    requested_float: float,
    expected_float: float,
) -> None:
    """Expense ratios must stay within a physical range.

    REFERENCE: G4-SYNTHETIC. Negative expenses would create money.
    """
    assert clamp_expense_percent_float(
        requested_float
    ) == pytest.approx(expected_float)


def test_simple_expense_model_subtracts_the_ratio() -> None:
    """The simple model is gross minus expense, by definition.

    REFERENCE: G4-SYNTHETIC. 12.0 - 0.5 = 11.5 percent.
    """
    assert calculate_net_return_percent_float(
        12.0, 0.5
    ) == pytest.approx(11.5)


def test_accrual_model_charges_more_than_simple() -> None:
    """Charging expense on the asset value costs slightly more.

    REFERENCE: G1-ANALYTIC. (1+g)(1-e) < 1 + g - e whenever both
    g and e are positive, because the cross term g*e is lost.
    """
    simple_rate_float = calculate_monthly_rate_after_expense_float(
        12.0, 1.0, EXPENSE_MODEL_SIMPLE_STR
    )
    accrued_rate_float = calculate_monthly_rate_after_expense_float(
        12.0, 1.0, EXPENSE_MODEL_ACCRUED_STR
    )
    assert accrued_rate_float < simple_rate_float


def test_accrual_model_matches_its_definition() -> None:
    """The accrual monthly factor must equal its formula.

    REFERENCE: G1-ANALYTIC. factor = (1+R)^(1/12) * (1-e)^(1/12).
    """
    expected_factor_float = (1.12) ** (1 / 12) * (0.995) ** (1 / 12)
    actual_rate_float = calculate_monthly_rate_after_expense_float(
        12.0, 0.5, EXPENSE_MODEL_ACCRUED_STR
    )
    assert actual_rate_float == pytest.approx(
        expected_factor_float - 1.0, abs=TOLERANCE_FLOAT
    )


def test_zero_expense_makes_both_models_agree() -> None:
    """With no expense the two models must be identical.

    REFERENCE: G1-ANALYTIC. Both reduce to the gross rate.
    """
    simple_rate_float = calculate_monthly_rate_after_expense_float(
        12.0, 0.0, EXPENSE_MODEL_SIMPLE_STR
    )
    accrued_rate_float = calculate_monthly_rate_after_expense_float(
        12.0, 0.0, EXPENSE_MODEL_ACCRUED_STR
    )
    assert simple_rate_float == pytest.approx(
        accrued_rate_float, abs=TOLERANCE_FLOAT
    )


def test_real_return_uses_the_fisher_relation() -> None:
    """Real return must satisfy (1+n) = (1+r)(1+pi).

    REFERENCE: G1-ANALYTIC. Fisher equation, exact form.
    """
    real_percent_float = convert_nominal_to_real_percent_float(
        12.0, 6.0
    )
    rebuilt_nominal_float = (
        (1 + real_percent_float / 100.0) * 1.06 - 1
    ) * 100.0
    assert rebuilt_nominal_float == pytest.approx(12.0, abs=1e-10)


def test_real_return_matches_hand_computed_value() -> None:
    """1.12 / 1.06 - 1 is 5.660377... percent.

    REFERENCE: G4-SYNTHETIC, hand derivation shown above.
    """
    assert convert_nominal_to_real_percent_float(
        12.0, 6.0
    ) == pytest.approx(5.6603773584905, abs=1e-10)


def test_impossible_inflation_returns_nominal_unchanged() -> None:
    """Inflation at -100% must not divide by zero.

    REFERENCE: G4-SYNTHETIC. Guard branch of the Fisher relation.
    """
    assert convert_nominal_to_real_percent_float(
        12.0, -100.0
    ) == pytest.approx(12.0)


@pytest.mark.parametrize(
    "months_held_int, expected_factor_float",
    [(-5, 1.0), (0, 1.0), (1, 1.01), (2, 1.0201)],
)
def test_growth_factor_covers_negative_zero_and_positive(
    months_held_int: int,
    expected_factor_float: float,
) -> None:
    """Holding periods at or below zero must not compound.

    REFERENCE: G4-SYNTHETIC. 1.01^n for n = 0, 1, 2.
    """
    assert calculate_growth_factor_float(
        0.01, months_held_int
    ) == pytest.approx(expected_factor_float)


@pytest.mark.parametrize(
    "elapsed_years_int, expected_float",
    [(0, 1000.0), (1, 1100.0), (2, 1210.0), (-3, 1000.0)],
)
def test_annual_growth_factor_covers_every_branch(
    elapsed_years_int: int,
    expected_float: float,
) -> None:
    """Escalation must compound yearly and ignore negatives.

    REFERENCE: G4-SYNTHETIC. 1000 * 1.1^n.
    """
    assert apply_annual_growth_factor_float(
        1000.0, 10.0, elapsed_years_int
    ) == pytest.approx(expected_float)


def test_negative_escalation_shrinks_the_amount() -> None:
    """A negative change rate must reduce the instalment.

    REFERENCE: G4-SYNTHETIC. 1000 * 0.9^2 = 810.
    """
    assert apply_annual_growth_factor_float(
        1000.0, -10.0, 2
    ) == pytest.approx(810.0)


def test_escalation_never_returns_a_negative_amount() -> None:
    """Escalation must clamp at zero, never pay the fund.

    REFERENCE: G4-SYNTHETIC. Physical impossibility guard.
    """
    assert apply_annual_growth_factor_float(-500.0, 10.0, 3) == 0.0
