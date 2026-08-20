"""Inverse solver tests."""

from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest

from conftest import build_test_fund, build_test_settings
from investment_journey_simulator.engine import PortfolioSimulator
from investment_journey_simulator.goal_seek import (
    solve_required_horizon_years_int,
    solve_required_monthly_sip_float,
    solve_required_return_percent_float,
)
from investment_journey_simulator.models import TaxSettings

START_DATE: date = date(2026, 1, 1)
TARGET_CORPUS_FLOAT: float = 20_000_000.0


def build_single_fund_list(monthly_sip_float: float = 10000.0):
    """Build a one-fund portfolio at twelve percent.

    REFERENCE: harness only.
    """
    return [
        build_test_fund(
            "Fund-A", monthly_sip_float, 12.0, 0.0, START_DATE
        )
    ]


def test_solved_instalment_reaches_the_target() -> None:
    """The solved instalment must actually meet the goal.

    REFERENCE: G1-ANALYTIC. Replaying the solved instalment
    through the engine is the definition of a correct answer, so
    the check is the round trip rather than a pinned number.
    """
    fund_list = build_single_fund_list()
    settings = build_test_settings(horizon_years_int=15)
    solved_float = solve_required_monthly_sip_float(
        fund_list, settings, TARGET_CORPUS_FLOAT
    )
    assert solved_float is not None
    achieved_float = PortfolioSimulator(
        [replace(fund_list[0], monthly_sip_float=solved_float)],
        settings,
    ).run().ending_value_float
    assert achieved_float == pytest.approx(
        TARGET_CORPUS_FLOAT, rel=1e-6
    )


def test_solved_instalment_matches_the_closed_form() -> None:
    """For a plain SIP the answer has a closed form to check.

    REFERENCE: G1-ANALYTIC. Target divided by the annuity-due
    factor of one rupee a month, using the same effective monthly
    rate the engine compounds at.
    """
    settings = build_test_settings(horizon_years_int=15)
    monthly_rate_float = 1.12 ** (1 / 12) - 1
    annuity_factor_float = (
        ((1 + monthly_rate_float) ** 180 - 1) / monthly_rate_float
    ) * (1 + monthly_rate_float)
    expected_float = TARGET_CORPUS_FLOAT / annuity_factor_float
    solved_float = solve_required_monthly_sip_float(
        build_single_fund_list(), settings, TARGET_CORPUS_FLOAT
    )
    assert solved_float == pytest.approx(expected_float, rel=1e-6)


def test_solved_return_reaches_the_target() -> None:
    """The solved return shift must meet the goal.

    REFERENCE: G1-ANALYTIC. Round trip through the engine.
    """
    fund_list = build_single_fund_list()
    settings = build_test_settings(horizon_years_int=15)
    shift_float = solve_required_return_percent_float(
        fund_list, settings, TARGET_CORPUS_FLOAT
    )
    assert shift_float is not None
    achieved_float = PortfolioSimulator(
        [
            replace(
                fund_list[0],
                gross_return_percent_float=(
                    fund_list[0].gross_return_percent_float
                    + shift_float
                ),
            )
        ],
        settings,
    ).run().ending_value_float
    assert achieved_float >= TARGET_CORPUS_FLOAT


def test_solved_horizon_is_the_first_year_that_reaches() -> None:
    """The horizon must be minimal, not merely sufficient.

    REFERENCE: G4-SYNTHETIC. The year before the solution must
    fall short, or the solver overshot.
    """
    fund_list = build_single_fund_list()
    settings = build_test_settings(horizon_years_int=15)
    solved_int = solve_required_horizon_years_int(
        fund_list, settings, TARGET_CORPUS_FLOAT
    )
    assert solved_int is not None
    reached_float = PortfolioSimulator(
        fund_list, replace(settings, horizon_years_int=solved_int)
    ).run().ending_value_float
    short_float = PortfolioSimulator(
        fund_list,
        replace(settings, horizon_years_int=solved_int - 1),
    ).run().ending_value_float
    assert reached_float >= TARGET_CORPUS_FLOAT
    assert short_float < TARGET_CORPUS_FLOAT


def test_unreachable_goal_reports_no_answer() -> None:
    """An impossible target must not return a search bound.

    REFERENCE: G4-SYNTHETIC. Returning the upper bound would look
    like a real answer and silently understate what is required.
    """
    fund_list = build_single_fund_list()
    settings = build_test_settings(horizon_years_int=1)
    assert (
        solve_required_monthly_sip_float(
            fund_list, settings, 1e18
        )
        is None
    )
    assert (
        solve_required_return_percent_float(
            fund_list, settings, 1e18
        )
        is None
    )
    assert (
        solve_required_horizon_years_int(fund_list, settings, 1e18)
        is None
    )


def test_a_portfolio_with_no_instalment_cannot_be_scaled() -> None:
    """Scaling zero by any factor is still zero.

    REFERENCE: G4-SYNTHETIC. Guard branch; there is no
    contribution mix to preserve.
    """
    fund_list = build_single_fund_list(0.0)
    settings = build_test_settings(horizon_years_int=15)
    assert (
        solve_required_monthly_sip_float(
            fund_list, settings, TARGET_CORPUS_FLOAT
        )
        is None
    )


def test_an_already_met_goal_needs_no_instalment() -> None:
    """A target already reached returns the lower bound.

    REFERENCE: G4-SYNTHETIC. Boundary branch where even a zero
    instalment clears the goal, because a lump sum already did.
    """
    fund_list = [
        build_test_fund(
            "Fund-A",
            10000.0,
            12.0,
            0.0,
            START_DATE,
            initial_investment_float=TARGET_CORPUS_FLOAT,
        )
    ]
    settings = build_test_settings(horizon_years_int=15)
    assert solve_required_monthly_sip_float(
        fund_list, settings, 1000.0
    ) == pytest.approx(0.0)


def test_post_tax_goal_needs_a_larger_instalment() -> None:
    """Targeting the spendable corpus costs more every month.

    REFERENCE: G4-SYNTHETIC. Exit tax reduces what is left, so a
    post-tax goal must demand a strictly larger instalment than
    the same goal measured before tax.
    """
    fund_list = build_single_fund_list()
    settings = build_test_settings(
        horizon_years_int=15,
        tax=TaxSettings(
            apply_final_liquidation_tax_bool=True,
            cess_percent_float=4.0,
        ),
    )
    pre_tax_float = solve_required_monthly_sip_float(
        fund_list, settings, TARGET_CORPUS_FLOAT, False
    )
    post_tax_float = solve_required_monthly_sip_float(
        fund_list, settings, TARGET_CORPUS_FLOAT, True
    )
    assert pre_tax_float is not None
    assert post_tax_float is not None
    assert post_tax_float > pre_tax_float
