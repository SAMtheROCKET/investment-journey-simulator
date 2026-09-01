"""Engine benchmarks against closed-form and notebook results.

Every test here compares the full simulation engine against an
independent source of truth rather than against itself.
"""

from __future__ import annotations

from datetime import date

import pytest

from conftest import (
    DEFAULT_START_DATE,
    build_test_fund,
    build_test_settings,
)
from investment_journey_simulator.constants import (
    PAUSE_SCOPE_SIP_STR,
    STEPUP_MODE_GLOBAL_STR,
    WITHDRAWAL_MODE_FIXED_STR,
)
from investment_journey_simulator.engine import PortfolioSimulator
from investment_journey_simulator.models import (
    PauseRange,
    PauseSettings,
    StepUpSettings,
    WithdrawalSettings,
)
from reference_data import (
    NOTEBOOK_LUMPSUM_EXPECTED_DICT,
    NOTEBOOK_SIP_EXPECTED_DICT,
    NOTEBOOK_SIP_GAP_EXPECTED_DICT,
    NOTEBOOK_STEPUP_EXPECTED_DICT,
    NOTEBOOK_THREE_FUND_FIFTEEN_YEAR_DICT,
    reference_sip_future_value_float,
    reference_swp_remaining_corpus_float,
)

NOTEBOOK_ROUNDING_TOLERANCE_FLOAT: float = 5e-4


@pytest.mark.parametrize(
    "horizon_years_int", sorted(NOTEBOOK_SIP_EXPECTED_DICT)
)
def test_engine_matches_notebook_sip_values(
    horizon_years_int: int,
) -> None:
    """The engine must reproduce the notebook's SIP table.

    REFERENCE: G3-CROSSCHECK against the earlier notebook, and
    G1-ANALYTIC because those values are the annuity-due formula.
    Inputs: 100 per month at 12 percent, start of month.
    """
    expected_dict = NOTEBOOK_SIP_EXPECTED_DICT[horizon_years_int]
    simulation_result = PortfolioSimulator(
        [build_test_fund(monthly_sip_float=100.0)],
        build_test_settings(horizon_years_int=horizon_years_int),
    ).run()
    assert simulation_result.ending_value_float == pytest.approx(
        expected_dict["future_value"],
        abs=NOTEBOOK_ROUNDING_TOLERANCE_FLOAT,
    )
    assert simulation_result.ending_invested_float == pytest.approx(
        expected_dict["invested"]
    )


@pytest.mark.parametrize(
    "horizon_years_int", sorted(NOTEBOOK_STEPUP_EXPECTED_DICT)
)
def test_engine_matches_notebook_stepup_values(
    horizon_years_int: int,
) -> None:
    """The engine must reproduce the notebook's step-up table.

    REFERENCE: G3-CROSSCHECK against the earlier notebook.
    Inputs: 100 per month at 12 percent, 10 percent yearly
    step-up applied on every twelfth month, start of month.
    """
    expected_dict = NOTEBOOK_STEPUP_EXPECTED_DICT[horizon_years_int]
    simulation_result = PortfolioSimulator(
        [build_test_fund(monthly_sip_float=100.0)],
        build_test_settings(
            horizon_years_int=horizon_years_int,
            stepup=StepUpSettings(STEPUP_MODE_GLOBAL_STR, 10.0),
        ),
    ).run()
    assert simulation_result.ending_value_float == pytest.approx(
        expected_dict["future_value"],
        abs=NOTEBOOK_ROUNDING_TOLERANCE_FLOAT,
    )
    assert simulation_result.ending_invested_float == pytest.approx(
        expected_dict["invested"], abs=1e-3
    )


@pytest.mark.parametrize(
    "horizon_years_int", sorted(NOTEBOOK_LUMPSUM_EXPECTED_DICT)
)
def test_engine_matches_notebook_lumpsum_values(
    horizon_years_int: int,
) -> None:
    """A pure lump sum must compound like the notebook's formula.

    REFERENCE: G3-CROSSCHECK and G1-ANALYTIC. 100 at 12 percent
    compounded annually equals 100 * 1.12^n, which the monthly
    engine reproduces because its monthly rate is the twelfth
    root of the annual rate.
    """
    expected_float = NOTEBOOK_LUMPSUM_EXPECTED_DICT[
        horizon_years_int
    ]
    simulation_result = PortfolioSimulator(
        [
            build_test_fund(
                monthly_sip_float=0.0,
                initial_investment_float=100.0,
            )
        ],
        build_test_settings(horizon_years_int=horizon_years_int),
    ).run()
    assert simulation_result.ending_value_float == pytest.approx(
        expected_float, abs=NOTEBOOK_ROUNDING_TOLERANCE_FLOAT
    )
    assert simulation_result.ending_invested_float == pytest.approx(
        100.0
    )


@pytest.mark.parametrize(
    "annual_return_percent_float, expected_value_float",
    sorted(NOTEBOOK_THREE_FUND_FIFTEEN_YEAR_DICT.items()),
)
def test_engine_matches_notebook_three_fund_table(
    annual_return_percent_float: float,
    expected_value_float: float,
) -> None:
    """Reproduce the notebook's three-fund fifteen-year table.

    REFERENCE: G3-CROSSCHECK against the earlier notebook.
    Inputs: 3000 per month for 15 years at 10, 12 and 14 percent.
    """
    simulation_result = PortfolioSimulator(
        [
            build_test_fund(
                monthly_sip_float=3000.0,
                gross_return_percent_float=(
                    annual_return_percent_float
                ),
            )
        ],
        build_test_settings(horizon_years_int=15),
    ).run()
    assert simulation_result.ending_value_float == pytest.approx(
        expected_value_float, abs=0.01
    )


@pytest.mark.parametrize(
    "gap_start_year_int", sorted(NOTEBOOK_SIP_GAP_EXPECTED_DICT)
)
def test_engine_matches_notebook_paused_sip(
    gap_start_year_int: int,
) -> None:
    """Pausing two whole years must match the notebook exactly.

    REFERENCE: G3-CROSSCHECK against the earlier notebook.
    Inputs: 1000 per month at 10 percent for 8 years, with two
    paused years starting at the given year.
    """
    expected_float = NOTEBOOK_SIP_GAP_EXPECTED_DICT[
        gap_start_year_int
    ]
    pause_start_date = date(
        DEFAULT_START_DATE.year + gap_start_year_int - 1, 1, 1
    )
    pause_end_date = date(
        DEFAULT_START_DATE.year + gap_start_year_int, 12, 1
    )
    simulation_result = PortfolioSimulator(
        [
            build_test_fund(
                monthly_sip_float=1000.0,
                gross_return_percent_float=10.0,
            )
        ],
        build_test_settings(
            horizon_years_int=8,
            pauses=PauseSettings(
                pause_ranges_list=[
                    PauseRange(
                        pause_start_date,
                        pause_end_date,
                        PAUSE_SCOPE_SIP_STR,
                    )
                ]
            ),
        ),
    ).run()
    assert simulation_result.ending_value_float == pytest.approx(
        expected_float, abs=NOTEBOOK_ROUNDING_TOLERANCE_FLOAT
    )
    assert simulation_result.ending_invested_float == pytest.approx(
        72000.0
    )


@pytest.mark.parametrize("horizon_years_int", [1, 2, 3, 5])
def test_engine_matches_reference_withdrawal_plan(
    horizon_years_int: int,
) -> None:
    """Withdrawals from a lump sum must match the reference loop.

    REFERENCE: G3-CROSSCHECK. The engine values the corpus at the
    end of the month and then pays the withdrawal, which is the
    reference function's ordinary-annuity convention.
    Inputs: 25,000 opening corpus at 12 percent, 500 per month.
    """
    expected_float = reference_swp_remaining_corpus_float(
        25000.0, 12.0, horizon_years_int, 500.0, False
    )
    simulation_result = PortfolioSimulator(
        [
            build_test_fund(
                monthly_sip_float=0.0,
                initial_investment_float=25000.0,
            )
        ],
        build_test_settings(
            horizon_years_int=horizon_years_int,
            withdrawal=WithdrawalSettings(
                is_enabled_bool=True,
                mode_str=WITHDRAWAL_MODE_FIXED_STR,
                fixed_amount_float=500.0,
            ),
        ),
    ).run()
    assert simulation_result.ending_value_float == pytest.approx(
        expected_float, abs=1e-6
    )


@pytest.mark.parametrize(
    "monthly_amount_float, annual_percent_float, years_int",
    [
        (5000.0, 12.0, 20),
        (25000.0, 11.0, 30),
        (1500.0, 8.0, 7),
        (100000.0, 13.5, 15),
    ],
)
def test_engine_matches_closed_form_for_realistic_plans(
    monthly_amount_float: float,
    annual_percent_float: float,
    years_int: int,
) -> None:
    """Realistic Indian SIP sizes must match the annuity formula.

    REFERENCE: G1-ANALYTIC closed form, with G5-PLAUSIBILITY
    inputs at magnitudes real investors actually use.
    """
    expected_float = reference_sip_future_value_float(
        monthly_amount_float, annual_percent_float, years_int, True
    )
    simulation_result = PortfolioSimulator(
        [
            build_test_fund(
                monthly_sip_float=monthly_amount_float,
                gross_return_percent_float=annual_percent_float,
            )
        ],
        build_test_settings(horizon_years_int=years_int),
    ).run()
    assert simulation_result.ending_value_float == pytest.approx(
        expected_float, rel=1e-12
    )


def test_end_of_month_timing_matches_ordinary_annuity() -> None:
    """End-of-month instalments must lose exactly one month.

    REFERENCE: G1-ANALYTIC. An annuity due equals an ordinary
    annuity multiplied by (1 + i).
    """
    ordinary_float = reference_sip_future_value_float(
        5000.0, 12.0, 10, False
    )
    simulation_result = PortfolioSimulator(
        [build_test_fund(monthly_sip_float=5000.0)],
        build_test_settings(
            horizon_years_int=10, sip_at_month_start_bool=False
        ),
    ).run()
    assert simulation_result.ending_value_float == pytest.approx(
        ordinary_float, rel=1e-12
    )


def test_two_equal_funds_split_exactly_in_half() -> None:
    """Identical funds must end with identical values.

    REFERENCE: G1-ANALYTIC. Symmetry: identical inputs must
    produce identical outputs.
    """
    simulation_result = PortfolioSimulator(
        [
            build_test_fund("Fund-A", 2000.0, 12.0),
            build_test_fund("Fund-B", 2000.0, 12.0),
        ],
        build_test_settings(horizon_years_int=12),
    ).run()
    first_value_float = simulation_result.fund_outcomes_list[
        0
    ].ending_value_float
    second_value_float = simulation_result.fund_outcomes_list[
        1
    ].ending_value_float
    assert first_value_float == pytest.approx(second_value_float)


def test_portfolio_equals_sum_of_independent_runs() -> None:
    """A multi-fund run must equal separate single-fund runs.

    REFERENCE: G1-ANALYTIC. Linearity: with no rebalancing and no
    withdrawals the funds never interact.
    """
    combined_result = PortfolioSimulator(
        [
            build_test_fund("Fund-A", 3000.0, 10.0),
            build_test_fund("Fund-B", 7000.0, 12.0),
        ],
        build_test_settings(horizon_years_int=18),
    ).run()
    separate_total_float = 0.0
    for name_str, amount_float, return_float in (
        ("Fund-A", 3000.0, 10.0),
        ("Fund-B", 7000.0, 12.0),
    ):
        separate_total_float += PortfolioSimulator(
            [build_test_fund(name_str, amount_float, return_float)],
            build_test_settings(horizon_years_int=18),
        ).run().ending_value_float
    assert combined_result.ending_value_float == pytest.approx(
        separate_total_float, rel=1e-12
    )


def test_zero_return_returns_exactly_the_principal() -> None:
    """With no growth the corpus must equal what was paid in.

    REFERENCE: G1-ANALYTIC. Degenerate case i = 0.
    """
    simulation_result = PortfolioSimulator(
        [
            build_test_fund(
                monthly_sip_float=5000.0,
                gross_return_percent_float=0.0,
            )
        ],
        build_test_settings(horizon_years_int=10),
    ).run()
    assert simulation_result.ending_value_float == pytest.approx(
        600000.0
    )
    assert simulation_result.ending_tax_paid_float == 0.0
