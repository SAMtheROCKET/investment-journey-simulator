"""Inflation adjustment tests against closed-form deflation."""

from __future__ import annotations

import pytest

from conftest import build_test_fund, build_test_settings
from investment_journey_simulator.constants import WITHDRAWAL_MODE_FIXED_STR
from investment_journey_simulator.engine import PortfolioSimulator
from investment_journey_simulator.inflation import (
    build_real_result,
    calculate_deflation_factor_float,
    calculate_varying_deflation_factor_float,
    deflate_amount_float,
)
from investment_journey_simulator.models import WithdrawalSettings
from reference_data import PLAUSIBLE_INFLATION_PERCENT_FLOAT


def test_deflation_factor_is_one_at_the_start_date() -> None:
    """No time elapsed means no loss of purchasing power.

    REFERENCE: G1-ANALYTIC. (1 + pi)^0 = 1.
    """
    assert calculate_deflation_factor_float(6.0, 0) == 1.0


@pytest.mark.parametrize(
    "elapsed_months_int, expected_factor_float",
    [(12, 1.06), (24, 1.1236), (6, 1.06 ** 0.5)],
)
def test_deflation_factor_matches_the_price_level_formula(
    elapsed_months_int: int,
    expected_factor_float: float,
) -> None:
    """The factor must equal (1 + pi) raised to elapsed years.

    REFERENCE: G1-ANALYTIC. Compound price level definition.
    """
    assert calculate_deflation_factor_float(
        6.0, elapsed_months_int
    ) == pytest.approx(expected_factor_float, abs=1e-12)


def test_negative_elapsed_months_are_clamped() -> None:
    """Time cannot run backwards; the factor must stay at one.

    REFERENCE: G4-SYNTHETIC. Defensive branch.
    """
    assert calculate_deflation_factor_float(6.0, -12) == 1.0


def test_impossible_inflation_is_clamped() -> None:
    """Inflation of -100 percent must not break the power.

    REFERENCE: G4-SYNTHETIC. Guard branch.
    """
    assert calculate_deflation_factor_float(-100.0, 12) > 0.0


def test_deflating_one_amount_matches_the_formula() -> None:
    """One lakh in twelve years at six percent is 49,696.94.

    REFERENCE: G1-ANALYTIC. 100000 / 1.06^12, hand-checkable.
    """
    assert deflate_amount_float(
        100000.0, 6.0, 144
    ) == pytest.approx(100000.0 / (1.06 ** 12), abs=1e-9)


def test_zero_inflation_leaves_the_run_unchanged() -> None:
    """With no inflation the real run must equal the nominal run.

    REFERENCE: G1-ANALYTIC. Identity element of deflation.
    """
    nominal_result = PortfolioSimulator(
        [build_test_fund(monthly_sip_float=5000.0)],
        build_test_settings(horizon_years_int=10),
    ).run()
    real_result = build_real_result(nominal_result, 0.0)
    assert real_result.ending_value_float == pytest.approx(
        nominal_result.ending_value_float
    )
    assert real_result.ending_invested_float == pytest.approx(
        nominal_result.ending_invested_float
    )


def test_real_ending_value_equals_nominal_over_price_level(
) -> None:
    """The closing corpus must deflate by the horizon factor.

    REFERENCE: G1-ANALYTIC. A stock at the horizon deflates once,
    at the price level of that date.
    """
    horizon_years_int = 15
    nominal_result = PortfolioSimulator(
        [build_test_fund(monthly_sip_float=10000.0)],
        build_test_settings(horizon_years_int=horizon_years_int),
    ).run()
    real_result = build_real_result(
        nominal_result, PLAUSIBLE_INFLATION_PERCENT_FLOAT
    )
    expected_float = nominal_result.ending_value_float / (
        1.06 ** horizon_years_int
    )
    assert real_result.ending_value_float == pytest.approx(
        expected_float, rel=1e-12
    )


def test_real_principal_deflates_each_instalment_separately(
) -> None:
    """Principal must accumulate individually deflated flows.

    REFERENCE: G1-ANALYTIC. Sum over m of 1000 / (1.06)^(m/12)
    for the twelve instalments of a one-year plan. Deflating the
    total by the final factor would give a different, wrong
    answer, which this test also asserts.
    """
    nominal_result = PortfolioSimulator(
        [build_test_fund(monthly_sip_float=1000.0)],
        build_test_settings(horizon_years_int=1),
    ).run()
    real_result = build_real_result(nominal_result, 6.0)
    expected_float = sum(
        1000.0 / (1.06 ** ((month_index_int + 1) / 12.0))
        for month_index_int in range(12)
    )
    assert real_result.ending_invested_float == pytest.approx(
        expected_float, rel=1e-12
    )
    naive_wrong_float = 12000.0 / 1.06
    assert real_result.ending_invested_float != pytest.approx(
        naive_wrong_float
    )


def test_real_values_are_lower_than_nominal_under_inflation(
) -> None:
    """Positive inflation must reduce every real figure.

    REFERENCE: G1-ANALYTIC. Monotonicity of deflation.
    """
    nominal_result = PortfolioSimulator(
        [build_test_fund(monthly_sip_float=5000.0)],
        build_test_settings(horizon_years_int=20),
    ).run()
    real_result = build_real_result(nominal_result, 6.0)
    assert (
        real_result.ending_value_float
        < nominal_result.ending_value_float
    )
    assert (
        real_result.ending_invested_float
        < nominal_result.ending_invested_float
    )


def test_gain_classification_stays_nominal() -> None:
    """Short and long term gains are legal, not economic, figures.

    REFERENCE: G2-STATUTORY. Tax law measures gains in nominal
    rupees, so the classification must not be deflated.
    """
    nominal_result = PortfolioSimulator(
        [build_test_fund(monthly_sip_float=25000.0)],
        build_test_settings(
            horizon_years_int=12,
            withdrawal=WithdrawalSettings(
                is_enabled_bool=True,
                start_month_index_int=60,
                mode_str=WITHDRAWAL_MODE_FIXED_STR,
                fixed_amount_float=10000.0,
            ),
        ),
    ).run()
    real_result = build_real_result(nominal_result, 6.0)
    for nominal_outcome, real_outcome in zip(
        nominal_result.fund_outcomes_list,
        real_result.fund_outcomes_list,
        strict=True,
    ):
        assert (
            real_outcome.long_term_gain_float
            == nominal_outcome.long_term_gain_float
        )
        assert (
            real_outcome.short_term_gain_float
            == nominal_outcome.short_term_gain_float
        )


def test_real_tax_is_lower_than_nominal_tax() -> None:
    """Tax paid in future rupees is worth less today.

    REFERENCE: G1-ANALYTIC. Each tax payment deflates at its own
    date, so the real total must be smaller.
    """
    nominal_result = PortfolioSimulator(
        [build_test_fund(monthly_sip_float=50000.0)],
        build_test_settings(
            horizon_years_int=15,
            withdrawal=WithdrawalSettings(
                is_enabled_bool=True,
                start_month_index_int=24,
                mode_str=WITHDRAWAL_MODE_FIXED_STR,
                fixed_amount_float=20000.0,
            ),
        ),
    ).run()
    real_result = build_real_result(nominal_result, 6.0)
    assert nominal_result.ending_tax_paid_float > 0.0
    assert (
        real_result.ending_tax_paid_float
        < nominal_result.ending_tax_paid_float
    )


def test_monthly_series_lengths_are_preserved() -> None:
    """Deflation must not add or drop any month.

    REFERENCE: G4-SYNTHETIC. Structural invariant.
    """
    nominal_result = PortfolioSimulator(
        [build_test_fund()], build_test_settings(horizon_years_int=7)
    ).run()
    real_result = build_real_result(nominal_result, 6.0)
    assert len(real_result.monthly_snapshots_list) == len(
        nominal_result.monthly_snapshots_list
    )
    assert len(
        real_result.monthly_snapshots_list[0].fund_states_list
    ) == 1


# ------------------------------------------------------------------
# Inflation that changes over time
# ------------------------------------------------------------------
@pytest.mark.parametrize("elapsed_months_int", [0, 1, 12, 60, 240])
def test_an_empty_schedule_matches_the_flat_rate_exactly(
    elapsed_months_int: int,
) -> None:
    """The varying form must generalise the flat one, not replace it.

    REFERENCE: G1-ANALYTIC. With no rate changes the two functions
    are the same function, so every existing real-terms figure is
    unaffected by the new machinery.
    """
    assert calculate_varying_deflation_factor_float(
        (), elapsed_months_int, 6.0
    ) == pytest.approx(
        calculate_deflation_factor_float(6.0, elapsed_months_int)
    )


def test_each_stretch_compounds_at_the_rate_then_in_force(
) -> None:
    """A spike in one decade must not reprice the others.

    REFERENCE: G1-ANALYTIC. Five years at 4% followed by five at
    10% must equal 1.04^5 x 1.10^5, not 1.07^10 or 1.10^10.
    """
    assert calculate_varying_deflation_factor_float(
        ((60, 10.0),), 120, 4.0
    ) == pytest.approx(1.04**5 * 1.10**5)


def test_a_change_dated_after_the_month_asked_about_is_ignored(
) -> None:
    """A future spike must never reprice the present.

    REFERENCE: G4-SYNTHETIC. Guard branch. At month 24 a change
    scheduled for month 60 has not happened yet.
    """
    assert calculate_varying_deflation_factor_float(
        ((60, 20.0),), 24, 5.0
    ) == pytest.approx(1.05**2)


def test_rate_changes_apply_in_calendar_order_however_given(
) -> None:
    """Events arrive from a rail in any order and must still sort.

    REFERENCE: G4-SYNTHETIC. The same three stretches, listed
    backwards, must produce the same price level.
    """
    forward_float = calculate_varying_deflation_factor_float(
        ((12, 8.0), (24, 3.0)), 36, 5.0
    )
    reversed_float = calculate_varying_deflation_factor_float(
        ((24, 3.0), (12, 8.0)), 36, 5.0
    )
    assert forward_float == pytest.approx(reversed_float)
    assert forward_float == pytest.approx(1.05 * 1.08 * 1.03)


def test_a_change_at_month_zero_replaces_the_opening_rate() -> None:
    """Declaring inflation at the start must not double count.

    REFERENCE: G4-SYNTHETIC. Boundary; the opening stretch has
    zero length, so only the declared rate applies.
    """
    assert calculate_varying_deflation_factor_float(
        ((0, 9.0),), 12, 5.0
    ) == pytest.approx(1.09)


def test_deflation_never_divides_by_zero() -> None:
    """A rate at or below minus a hundred percent must be clamped.

    REFERENCE: G4-SYNTHETIC. Guard branch inherited from the flat
    form; the factor must stay strictly positive.
    """
    assert (
        calculate_varying_deflation_factor_float(
            ((12, -150.0),), 60, 5.0
        )
        > 0.0
    )
