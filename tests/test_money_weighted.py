"""Money-weighted return tests."""

from __future__ import annotations

from datetime import date

import pytest

from conftest import build_test_fund, build_test_settings
from investment_journey_simulator.engine import PortfolioSimulator
from investment_journey_simulator.models import TaxSettings, WithdrawalSettings
from investment_journey_simulator.money_weighted import (
    CashFlow,
    build_post_tax_cash_flow_list,
    build_pre_tax_cash_flow_list,
    calculate_post_tax_xirr_percent_float,
    calculate_pre_tax_xirr_percent_float,
    calculate_present_value_float,
    calculate_xirr_percent_float,
)

EXCEL_DOCUMENTED_FLOW_LIST: list[CashFlow] = [
    CashFlow(date(2008, 1, 1), -10000.0),
    CashFlow(date(2008, 3, 1), 2750.0),
    CashFlow(date(2008, 10, 30), 4250.0),
    CashFlow(date(2009, 2, 15), 3250.0),
    CashFlow(date(2009, 4, 1), 2750.0),
]
EXCEL_DOCUMENTED_RESULT_FLOAT: float = 37.336


def test_solver_matches_the_documented_spreadsheet_example() -> None:
    """XIRR reproduces the worked example shipped with Excel.

    REFERENCE: G1-ANALYTIC and G3-CROSSCHECK. The flows and the
    expected 37.336% come from the spreadsheet vendor's own
    documentation of XIRR(), an implementation entirely
    independent of this package.
    """
    solved_percent_float = calculate_xirr_percent_float(
        EXCEL_DOCUMENTED_FLOW_LIST
    )
    assert solved_percent_float is not None
    assert solved_percent_float == pytest.approx(
        EXCEL_DOCUMENTED_RESULT_FLOAT, abs=0.001
    )


def test_single_period_return_is_exact() -> None:
    """One rupee out and 1.12 back a year later is twelve percent.

    REFERENCE: G1-ANALYTIC. Closed form; the day count over a
    non-leap year is exactly 365.
    """
    solved_percent_float = calculate_xirr_percent_float(
        [
            CashFlow(date(2026, 1, 1), -100.0),
            CashFlow(date(2027, 1, 1), 112.0),
        ]
    )
    assert solved_percent_float == pytest.approx(12.0, abs=1e-6)


def test_present_value_at_the_solved_rate_is_zero() -> None:
    """The solved rate is a root of the present value function.

    REFERENCE: G1-ANALYTIC. Definition of an internal rate of
    return; this is the property the solver claims to find.
    """
    solved_percent_float = calculate_xirr_percent_float(
        EXCEL_DOCUMENTED_FLOW_LIST
    )
    assert solved_percent_float is not None
    residual_float = calculate_present_value_float(
        EXCEL_DOCUMENTED_FLOW_LIST, solved_percent_float / 100.0
    )
    assert residual_float == pytest.approx(0.0, abs=1e-4)


@pytest.mark.parametrize(
    "flow_list",
    [
        [],
        [CashFlow(date(2026, 1, 1), -100.0)],
        [
            CashFlow(date(2026, 1, 1), -100.0),
            CashFlow(date(2027, 1, 1), -50.0),
        ],
        [
            CashFlow(date(2026, 1, 1), 100.0),
            CashFlow(date(2027, 1, 1), 50.0),
        ],
    ],
)
def test_degenerate_series_have_no_rate(
    flow_list: list[CashFlow],
) -> None:
    """A series without a sign change reports no rate at all.

    REFERENCE: G4-SYNTHETIC. An internal rate of return exists
    only where the present value function crosses zero; returning
    zero percent instead would be a fabricated number.
    """
    assert calculate_xirr_percent_float(flow_list) is None


@pytest.mark.parametrize("annual_return_percent_float", [8.0, 12.0])
@pytest.mark.parametrize("horizon_years_int", [5, 10, 25])
@pytest.mark.parametrize("sip_at_month_start_bool", [True, False])
def test_untaxed_plan_recovers_its_own_growth_rate(
    annual_return_percent_float: float,
    horizon_years_int: int,
    sip_at_month_start_bool: bool,
) -> None:
    """A plan with no levies earns the rate its funds compound at.

    REFERENCE: G1-ANALYTIC. With no tax, no charges and no
    withdrawals the money-weighted return must equal the fund's
    own rate. The tolerance absorbs the difference between the
    engine's idealised twelfth-of-a-year month and the actual/365
    day count XIRR uses, which is at most a few basis points.
    """
    fund_list = [
        build_test_fund(
            "Fund-A",
            10000.0,
            annual_return_percent_float,
            0.0,
            date(2026, 1, 1),
        )
    ]
    settings = build_test_settings(
        horizon_years_int=horizon_years_int,
        sip_at_month_start_bool=sip_at_month_start_bool,
    )
    result = PortfolioSimulator(fund_list, settings).run()
    solved_percent_float = calculate_pre_tax_xirr_percent_float(
        result, sip_at_month_start_bool
    )
    assert solved_percent_float == pytest.approx(
        annual_return_percent_float, abs=0.05
    )


def test_exit_tax_lowers_the_money_weighted_return() -> None:
    """Tax on exit must reduce the rate the investor keeps.

    REFERENCE: G4-SYNTHETIC. The post-tax series subtracts the
    liquidation tax from the terminal corpus, so its rate cannot
    exceed the pre-tax rate on the same plan.
    """
    fund_list = [
        build_test_fund(
            "Fund-A", 10000.0, 12.0, 0.0, date(2026, 1, 1)
        )
    ]
    settings = build_test_settings(
        horizon_years_int=10,
        tax=TaxSettings(
            apply_final_liquidation_tax_bool=True,
            cess_percent_float=4.0,
        ),
    )
    result = PortfolioSimulator(fund_list, settings).run()
    pre_tax_float = calculate_pre_tax_xirr_percent_float(result)
    post_tax_float = calculate_post_tax_xirr_percent_float(result)
    assert pre_tax_float is not None
    assert post_tax_float is not None
    assert post_tax_float < pre_tax_float


def test_without_levies_both_series_agree() -> None:
    """With no tax and no charges the two rates coincide.

    REFERENCE: G4-SYNTHETIC. The post-tax series differs from the
    pre-tax one only by the levies, so a levy-free plan must give
    the same answer twice.
    """
    fund_list = [
        build_test_fund(
            "Fund-A", 5000.0, 10.0, 0.0, date(2026, 1, 1)
        )
    ]
    settings = build_test_settings(horizon_years_int=7)
    result = PortfolioSimulator(fund_list, settings).run()
    assert calculate_post_tax_xirr_percent_float(
        result
    ) == pytest.approx(
        calculate_pre_tax_xirr_percent_float(result), abs=1e-9
    )


def test_terminal_corpus_settles_after_the_last_instalment() -> None:
    """The closing corpus is dated at the close of the last month.

    REFERENCE: G4-SYNTHETIC. The engine values a month after
    growing it, so dating the corpus at the month start would
    compress the elapsed time and inflate the solved rate.
    """
    fund_list = [
        build_test_fund(
            "Fund-A", 1000.0, 12.0, 0.0, date(2026, 1, 1)
        )
    ]
    settings = build_test_settings(horizon_years_int=1)
    result = PortfolioSimulator(fund_list, settings).run()
    flow_list = build_pre_tax_cash_flow_list(result, True)
    assert flow_list[-1].flow_date == date(2027, 1, 1)
    assert flow_list[0].flow_date == date(2026, 1, 1)


def test_withdrawals_appear_as_inflows() -> None:
    """Money taken out is a positive flow to the investor.

    REFERENCE: G4-SYNTHETIC. Sign convention check; a withdrawal
    booked as an outflow would silently invert the rate.
    """
    fund_list = [
        build_test_fund(
            "Fund-A",
            5000.0,
            10.0,
            0.0,
            date(2026, 1, 1),
            initial_investment_float=500000.0,
        )
    ]
    settings = build_test_settings(
        horizon_years_int=3,
        withdrawal=WithdrawalSettings(
            is_enabled_bool=True,
            fixed_amount_float=2000.0,
            start_month_index_int=0,
        ),
    )
    result = PortfolioSimulator(fund_list, settings).run()
    flow_list = build_post_tax_cash_flow_list(result)
    assert any(
        flow.amount_float > 0.0 for flow in flow_list[:-1]
    )
