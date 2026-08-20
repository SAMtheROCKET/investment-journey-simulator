"""The engine, checked against arithmetic done independently.

Most of this project's suite tests the engine against itself:
fixtures record what it produced, and a regression is a change from
that. This catches drift and cannot catch a figure that was wrong
the day it was first recorded.

So nothing here compares the engine to a stored number. Each test
either derives the answer in closed form or re-computes it with a
plain loop written from the definition, and then asks whether the
engine agrees. Where no closed form exists - rebalancing,
combinations - the test asserts an invariant that has to hold
whatever the arithmetic underneath is.

This module exists because a reader noticed that the invested split
and the ending split of a three-fund plan were identical, which is
impossible when the funds assume different returns. Chasing it found
two defects that the whole existing suite had missed:

  * a screen rewrote every fund's return to the first fund's simply
    by being opened, which is what flattened the split, and
  * a portfolio instalment was handed to every fund in full, so a
    two-fund plan invested twice what the reader asked for.

Both lived in the space between features, which is where the tests
below deliberately spend most of their time.
"""

from __future__ import annotations

from datetime import date

import pytest

from conftest import build_test_fund, build_test_settings
from investment_journey_simulator.constants import (
    PAUSE_SCOPE_SIP_STR,
    REBALANCE_METHOD_FULL_STR,
    REBALANCE_TARGET_COLUMN_STR,
    STEPUP_MODE_GLOBAL_STR,
    WITHDRAWAL_MODE_FIXED_STR,
)
from investment_journey_simulator.engine import PortfolioSimulator
from investment_journey_simulator.inflation import (
    deflate_amount_float,
)
from investment_journey_simulator.models import (
    InstalmentOverride,
    PauseRange,
    PauseSettings,
    RebalanceSettings,
    StepUpSettings,
    WithdrawalSettings,
)
from investment_journey_simulator.tables import (
    SUMMARY_ENDING_VALUE_STR,
    SUMMARY_INVESTED_STR,
    build_fund_summary_dataframe,
)

MONTHS_IN_YEAR_INT: int = 12

# A rupee is divisible to two places, so anything below this is
# floating-point noise rather than money. Comparing a residual
# against exactly zero fails on a plan that met every withdrawal
# to within a hundred-billionth of a rupee.
PAISA_TOLERANCE_FLOAT: float = 0.005


def run_engine(fund_list: list, settings):
    """One run of the engine."""
    return PortfolioSimulator(fund_list, settings).run()


def monthly_rate_float(annual_percent_float: float) -> float:
    """The compounding convention, written out from scratch.

    Twelve per cent a year is `1.12 ** (1/12) - 1` a month, not
    twelve divided by twelve. Spelled out here rather than imported
    so this file cannot agree with the engine by sharing its
    mistake.
    """
    return (1.0 + annual_percent_float / 100.0) ** (
        1.0 / MONTHS_IN_YEAR_INT
    ) - 1.0


def grow_by_hand_float(
    monthly_float: float,
    annual_percent_float: float,
    months_int: int,
) -> float:
    """A plain loop, from the definition of monthly compounding."""
    rate_float = monthly_rate_float(annual_percent_float)
    value_float = 0.0
    for _month_int in range(months_int):
        value_float += monthly_float
        value_float *= 1.0 + rate_float
    return value_float


def share_list(amount_list: list) -> list:
    """Each amount as a fraction of the total."""
    total_float = sum(amount_list)
    return [
        amount_float / total_float for amount_float in amount_list
    ]


def read_split_tuple(simulation_result) -> tuple:
    """The invested split and the ending split, as fractions."""
    frame = build_fund_summary_dataframe(simulation_result)
    return (
        share_list(frame[SUMMARY_INVESTED_STR].tolist()),
        share_list(frame[SUMMARY_ENDING_VALUE_STR].tolist()),
    )


# ------------------------------------------------------------------
# The reported symptom: two donuts showing the same percentages.
# ------------------------------------------------------------------
def test_funds_with_different_returns_end_in_different_shares():
    """The bug a reader spotted, written as an assertion.

    Three funds, three returns, fixed instalments. The ending split
    cannot equal the invested split unless the returns are equal -
    it is arithmetically impossible - so when it does, something
    upstream has flattened the returns.
    """
    fund_list = [
        build_test_fund("Equity", 3000.0, 14.0),
        build_test_fund("Debt", 2000.0, 6.0),
        build_test_fund("Gold", 7000.0, 10.0),
    ]
    invested_list, ending_list = read_split_tuple(
        run_engine(
            fund_list, build_test_settings(horizon_years_int=20)
        )
    )
    assert invested_list != pytest.approx(ending_list, abs=1e-3)
    # The best fund gains share; the worst loses it.
    assert ending_list[0] > invested_list[0]
    assert ending_list[1] < invested_list[1]


def test_the_ending_split_is_the_one_the_returns_imply():
    """Not merely different - different by the right amount.

    Each fund's ending value is computed here by hand, and the
    split those hand figures imply must be the split the summary
    table reports.
    """
    specification_tuple = (
        ("Equity", 3000.0, 14.0),
        ("Debt", 2000.0, 6.0),
        ("Gold", 7000.0, 10.0),
    )
    years_int = 20
    fund_list = [
        build_test_fund(name_str, monthly_float, return_float)
        for name_str, monthly_float, return_float in (
            specification_tuple
        )
    ]
    _invested_list, ending_list = read_split_tuple(
        run_engine(
            fund_list,
            build_test_settings(horizon_years_int=years_int),
        )
    )
    expected_list = share_list(
        [
            grow_by_hand_float(
                monthly_float,
                return_float,
                years_int * MONTHS_IN_YEAR_INT,
            )
            for _name_str, monthly_float, return_float in (
                specification_tuple
            )
        ]
    )
    assert ending_list == pytest.approx(expected_list, rel=1e-9)


@pytest.mark.parametrize("return_percent_float", (0.0, 6.0, 14.0))
def test_one_fund_ends_where_its_own_return_puts_it(
    return_percent_float,
):
    """The single-fund case, against the loop."""
    simulation_result = run_engine(
        [build_test_fund("Solo", 5000.0, return_percent_float)],
        build_test_settings(horizon_years_int=15),
    )
    assert simulation_result.ending_value_float == pytest.approx(
        grow_by_hand_float(
            5000.0,
            return_percent_float,
            15 * MONTHS_IN_YEAR_INT,
        ),
        rel=1e-9,
    )


# ------------------------------------------------------------------
# The portfolio instalment, which was being handed to every fund in
# full rather than divided between them.
# ------------------------------------------------------------------
@pytest.mark.parametrize("fund_count_int", (1, 2, 3, 5))
def test_a_portfolio_instalment_is_divided_not_duplicated(
    fund_count_int,
):
    """What the reader typed is what the plan invests.

    A rail instalment is a statement about the plan, not about each
    fund in it. Handing it to every fund in full made a two-fund
    plan invest double, and the error grew with the fund count -
    every figure downstream inherited it.
    """
    monthly_float, years_int = 12000.0, 10
    fund_list = [
        build_test_fund(
            f"Fund-{index_int}",
            0.0,
            10.0,
            target_allocation_percent_float=100.0 / fund_count_int,
        )
        for index_int in range(fund_count_int)
    ]
    simulation_result = run_engine(
        fund_list,
        build_test_settings(
            horizon_years_int=years_int,
            instalment_override_list=[
                InstalmentOverride(0, monthly_float, "")
            ],
        ),
    )
    assert simulation_result.ending_invested_float == pytest.approx(
        monthly_float * years_int * MONTHS_IN_YEAR_INT, rel=1e-9
    )


def test_a_portfolio_instalment_follows_the_target_weights():
    """Divided by intent, not evenly by accident."""
    fund_list = [
        build_test_fund(
            "Equity",
            0.0,
            10.0,
            target_allocation_percent_float=70.0,
        ),
        build_test_fund(
            "Debt",
            0.0,
            10.0,
            target_allocation_percent_float=30.0,
        ),
    ]
    invested_list, _ending_list = read_split_tuple(
        run_engine(
            fund_list,
            build_test_settings(
                horizon_years_int=5,
                instalment_override_list=[
                    InstalmentOverride(0, 10000.0, "")
                ],
            ),
        )
    )
    assert invested_list == pytest.approx([0.70, 0.30], abs=1e-9)


def test_a_fund_specific_instalment_is_still_taken_whole():
    """Naming a fund means that fund, not a share of the plan."""
    fund_list = [
        build_test_fund("Equity", 0.0, 10.0),
        build_test_fund("Debt", 0.0, 10.0),
    ]
    simulation_result = run_engine(
        fund_list,
        build_test_settings(
            horizon_years_int=5,
            instalment_override_list=[
                InstalmentOverride(0, 4000.0, "Equity")
            ],
        ),
    )
    assert simulation_result.ending_invested_float == pytest.approx(
        4000.0 * 5 * MONTHS_IN_YEAR_INT, rel=1e-9
    )


def test_funds_with_no_stated_weight_share_a_plan_instalment():
    """The fallback, which must not multiply the money either."""
    monthly_float, years_int = 9000.0, 3
    fund_list = [
        build_test_fund(
            name_str, 0.0, 10.0, target_allocation_percent_float=0.0
        )
        for name_str in ("Equity", "Debt", "Gold")
    ]
    simulation_result = run_engine(
        fund_list,
        build_test_settings(
            horizon_years_int=years_int,
            instalment_override_list=[
                InstalmentOverride(0, monthly_float, "")
            ],
        ),
    )
    assert simulation_result.ending_invested_float == pytest.approx(
        monthly_float * years_int * MONTHS_IN_YEAR_INT, rel=1e-9
    )


# ------------------------------------------------------------------
# One feature at a time, each against a hand calculation.
# ------------------------------------------------------------------
def test_the_compounding_convention_is_the_documented_one():
    """Twelve per cent a year is not one per cent a month."""
    simulation_result = run_engine(
        [build_test_fund("Solo", 1000.0, 12.0)],
        build_test_settings(horizon_years_int=1),
    )
    naive_float = 0.0
    for _month_int in range(MONTHS_IN_YEAR_INT):
        naive_float = (naive_float + 1000.0) * (1.0 + 0.12 / 12.0)
    assert simulation_result.ending_value_float == pytest.approx(
        grow_by_hand_float(1000.0, 12.0, MONTHS_IN_YEAR_INT),
        rel=1e-9,
    )
    assert simulation_result.ending_value_float != pytest.approx(
        naive_float, rel=1e-6
    )


def test_a_step_up_raises_the_instalment_once_a_year():
    """Invested equals the sum of an escalating series."""
    monthly_float, stepup_percent_float, years_int = (
        10000.0,
        10.0,
        5,
    )
    simulation_result = run_engine(
        [build_test_fund("Solo", monthly_float, 10.0)],
        build_test_settings(
            horizon_years_int=years_int,
            stepup=StepUpSettings(
                STEPUP_MODE_GLOBAL_STR, stepup_percent_float
            ),
        ),
    )
    expected_float = sum(
        monthly_float
        * (1.0 + stepup_percent_float / 100.0) ** year_int
        * MONTHS_IN_YEAR_INT
        for year_int in range(years_int)
    )
    assert simulation_result.ending_invested_float == pytest.approx(
        expected_float, rel=1e-9
    )


def test_a_step_down_lowers_it_by_the_same_rule():
    """A negative escalation is the same arithmetic, downwards."""
    monthly_float, stepup_percent_float, years_int = (
        10000.0,
        -20.0,
        4,
    )
    simulation_result = run_engine(
        [build_test_fund("Solo", monthly_float, 10.0)],
        build_test_settings(
            horizon_years_int=years_int,
            stepup=StepUpSettings(
                STEPUP_MODE_GLOBAL_STR, stepup_percent_float
            ),
        ),
    )
    expected_float = sum(
        monthly_float
        * (1.0 + stepup_percent_float / 100.0) ** year_int
        * MONTHS_IN_YEAR_INT
        for year_int in range(years_int)
    )
    assert simulation_result.ending_invested_float == pytest.approx(
        expected_float, rel=1e-9
    )
    assert simulation_result.ending_invested_float < (
        monthly_float * years_int * MONTHS_IN_YEAR_INT
    )


def test_a_stepped_up_plan_grows_by_the_hand_loop():
    """Escalation and compounding together, month by month."""
    monthly_float, stepup_percent_float, years_int = (
        10000.0,
        10.0,
        6,
    )
    return_percent_float = 12.0
    simulation_result = run_engine(
        [
            build_test_fund(
                "Solo", monthly_float, return_percent_float
            )
        ],
        build_test_settings(
            horizon_years_int=years_int,
            stepup=StepUpSettings(
                STEPUP_MODE_GLOBAL_STR, stepup_percent_float
            ),
        ),
    )
    rate_float = monthly_rate_float(return_percent_float)
    value_float = 0.0
    for month_int in range(years_int * MONTHS_IN_YEAR_INT):
        year_int = month_int // MONTHS_IN_YEAR_INT
        value_float += monthly_float * (
            (1.0 + stepup_percent_float / 100.0) ** year_int
        )
        value_float *= 1.0 + rate_float
    assert simulation_result.ending_value_float == pytest.approx(
        value_float, rel=1e-9
    )


def build_sip_pause_settings(
    start_date: date, end_date: date
) -> PauseSettings:
    """One contribution break, given as a date range."""
    return PauseSettings(
        pause_ranges_list=[
            PauseRange(start_date, end_date, PAUSE_SCOPE_SIP_STR)
        ]
    )


def test_a_pause_removes_exactly_the_months_it_covers():
    """The gap costs the instalments inside it, and no others."""
    monthly_float, years_int = 10000.0, 10
    simulation_result = run_engine(
        [build_test_fund("Solo", monthly_float, 10.0)],
        build_test_settings(
            horizon_years_int=years_int,
            pauses=build_sip_pause_settings(
                date(2029, 1, 1), date(2031, 12, 1)
            ),
        ),
    )
    paused_months_int = 3 * MONTHS_IN_YEAR_INT
    assert simulation_result.ending_invested_float == pytest.approx(
        monthly_float
        * (years_int * MONTHS_IN_YEAR_INT - paused_months_int),
        rel=1e-9,
    )


def test_money_already_invested_grows_through_a_pause():
    """The point about a break people most often get wrong.

    A pause stops the instalments. It does not stop the compounding
    of what is already in the fund, and the hand loop says exactly
    how much that leaves.
    """
    monthly_float, return_percent_float = 10000.0, 12.0
    paused_month_set = set(
        range(3 * MONTHS_IN_YEAR_INT, 6 * MONTHS_IN_YEAR_INT)
    )
    simulation_result = run_engine(
        [build_test_fund("Solo", monthly_float, return_percent_float)],
        build_test_settings(
            horizon_years_int=10,
            pauses=build_sip_pause_settings(
                date(2029, 1, 1), date(2031, 12, 1)
            ),
        ),
    )
    rate_float = monthly_rate_float(return_percent_float)
    value_float = 0.0
    for month_int in range(10 * MONTHS_IN_YEAR_INT):
        if month_int not in paused_month_set:
            value_float += monthly_float
        value_float *= 1.0 + rate_float
    assert simulation_result.ending_value_float == pytest.approx(
        value_float, rel=1e-9
    )


def build_withdrawal_settings(
    withdrawal_float: float, start_month_int: int
) -> WithdrawalSettings:
    """A fixed monthly withdrawal starting at one month."""
    return WithdrawalSettings(
        is_enabled_bool=True,
        start_month_index_int=start_month_int,
        mode_str=WITHDRAWAL_MODE_FIXED_STR,
        fixed_amount_float=withdrawal_float,
    )


def test_withdrawals_come_out_at_the_rate_asked_for():
    """Total withdrawn equals the schedule, not something near it."""
    withdrawal_float, years_int = 20000.0, 10
    start_month_int = 5 * MONTHS_IN_YEAR_INT
    simulation_result = run_engine(
        [build_test_fund("Solo", 30000.0, 12.0)],
        build_test_settings(
            horizon_years_int=years_int,
            withdrawal=build_withdrawal_settings(
                withdrawal_float, start_month_int
            ),
        ),
    )
    expected_months_int = (
        years_int * MONTHS_IN_YEAR_INT - start_month_int
    )
    assert (
        simulation_result.ending_withdrawn_float
        == pytest.approx(
            withdrawal_float * expected_months_int, rel=1e-6
        )
    )
    assert (
        simulation_result.total_unmet_withdrawal_float
        == pytest.approx(0.0, abs=PAISA_TOLERANCE_FLOAT)
    )


def test_nothing_is_withdrawn_before_the_start_month():
    """A gap before withdrawals begin is a real gap."""
    start_month_int = 5 * MONTHS_IN_YEAR_INT
    simulation_result = run_engine(
        [build_test_fund("Solo", 30000.0, 12.0)],
        build_test_settings(
            horizon_years_int=10,
            withdrawal=build_withdrawal_settings(
                20000.0, start_month_int
            ),
        ),
    )
    early_list = simulation_result.monthly_snapshots_list[
        :start_month_int
    ]
    assert all(
        snapshot.monthly_withdrawal_float == 0.0
        for snapshot in early_list
    )


def test_a_withdrawal_costs_more_than_the_cash_it_hands_over():
    """Money out is money that stops compounding.

    Withdrawing from a taxed fund has no closed form, so this
    checks the bound instead: the ending value has to fall by more
    than the cash taken, because the growth on it is lost too.
    """
    withdrawal_float = 20000.0
    start_month_int = 5 * MONTHS_IN_YEAR_INT
    months_int = 10 * MONTHS_IN_YEAR_INT
    fund_list = [build_test_fund("Solo", 30000.0, 12.0)]
    with_result = run_engine(
        fund_list,
        build_test_settings(
            horizon_years_int=10,
            withdrawal=build_withdrawal_settings(
                withdrawal_float, start_month_int
            ),
        ),
    )
    without_result = run_engine(
        fund_list, build_test_settings(horizon_years_int=10)
    )
    taken_float = withdrawal_float * (months_int - start_month_int)
    assert (
        without_result.ending_value_float
        - with_result.ending_value_float
    ) > taken_float


def build_rebalance_settings(
    interval_months_int: int = 12,
) -> RebalanceSettings:
    """Calendar rebalancing back to the target column."""
    return RebalanceSettings(
        is_enabled_bool=True,
        interval_months_int=interval_months_int,
        method_str=REBALANCE_METHOD_FULL_STR,
        target_mode_str=REBALANCE_TARGET_COLUMN_STR,
    )


def build_drifting_fund_list(
    equity_target_float: float = 60.0,
) -> list:
    """Two funds whose weights must come apart over time."""
    return [
        build_test_fund(
            "Equity",
            5000.0,
            16.0,
            target_allocation_percent_float=equity_target_float,
        ),
        build_test_fund(
            "Debt",
            5000.0,
            4.0,
            target_allocation_percent_float=(
                100.0 - equity_target_float
            ),
        ),
    ]


def test_rebalancing_puts_the_weights_back_on_target():
    """After a full rebalance the split is the target split."""
    simulation_result = run_engine(
        build_drifting_fund_list(60.0),
        build_test_settings(
            horizon_years_int=10,
            rebalance=build_rebalance_settings(),
        ),
    )
    assert simulation_result.rebalance_events_list
    weight_dict = simulation_result.rebalance_events_list[
        -1
    ].weights_after_dict
    assert weight_dict["Equity"] == pytest.approx(60.0, abs=1e-6)
    assert weight_dict["Debt"] == pytest.approx(40.0, abs=1e-6)


def test_without_rebalancing_the_weights_drift():
    """The comparison that makes rebalancing mean anything."""
    _invested_list, ending_list = read_split_tuple(
        run_engine(
            build_drifting_fund_list(50.0),
            build_test_settings(horizon_years_int=20),
        )
    )
    assert ending_list[0] > 0.60


def test_rebalancing_happens_on_the_interval_it_was_given():
    """Twice as often means twice as many events."""
    fund_list = build_drifting_fund_list(50.0)
    annual_result = run_engine(
        fund_list,
        build_test_settings(
            horizon_years_int=10,
            rebalance=build_rebalance_settings(12),
        ),
    )
    biannual_result = run_engine(
        fund_list,
        build_test_settings(
            horizon_years_int=10,
            rebalance=build_rebalance_settings(6),
        ),
    )
    assert len(annual_result.rebalance_events_list) > 0
    assert len(biannual_result.rebalance_events_list) == (
        2 * len(annual_result.rebalance_events_list)
    )


def test_the_inflation_adjustment_is_a_division_by_compounding():
    """Real value is nominal divided by (1 + i) ** years."""
    nominal_float, inflation_float, years_int = (
        10_000_000.0,
        6.0,
        20,
    )
    assert deflate_amount_float(
        nominal_float,
        inflation_float,
        years_int * MONTHS_IN_YEAR_INT,
    ) == pytest.approx(
        nominal_float
        / ((1.0 + inflation_float / 100.0) ** years_int),
        rel=1e-9,
    )


def test_a_higher_inflation_rate_lowers_the_real_value():
    """Monotonic, and zero inflation must change nothing."""
    nominal_float = 10_000_000.0
    months_int = 20 * MONTHS_IN_YEAR_INT
    real_list = [
        deflate_amount_float(nominal_float, rate_float, months_int)
        for rate_float in (0.0, 3.0, 6.0, 9.0)
    ]
    assert real_list == sorted(real_list, reverse=True)
    assert real_list[0] == pytest.approx(nominal_float)


def test_deflating_a_total_once_is_not_the_same_as_per_flow():
    """The mistake the inflation module warns about, measured.

    Every instalment is deflated at its own date, so the real
    invested total has to be larger than the whole nominal total
    deflated once at the final factor.
    """
    monthly_float, inflation_float, years_int = 10000.0, 6.0, 20
    months_int = years_int * MONTHS_IN_YEAR_INT
    per_flow_float = sum(
        deflate_amount_float(
            monthly_float, inflation_float, month_int
        )
        for month_int in range(months_int)
    )
    at_the_end_float = deflate_amount_float(
        monthly_float * months_int, inflation_float, months_int
    )
    assert per_flow_float > at_the_end_float


# ------------------------------------------------------------------
# Combinations. Each feature works alone; the question is whether it
# still does while the others are running.
# ------------------------------------------------------------------
def build_everything_settings(**override_dict):
    """A plan with a step-up, a pause, withdrawals, rebalancing."""
    field_dict = dict(
        horizon_years_int=25,
        stepup=StepUpSettings(STEPUP_MODE_GLOBAL_STR, 8.0),
        pauses=build_sip_pause_settings(
            date(2031, 1, 1), date(2032, 12, 1)
        ),
        withdrawal=build_withdrawal_settings(
            15000.0, 18 * MONTHS_IN_YEAR_INT
        ),
        rebalance=build_rebalance_settings(),
    )
    field_dict.update(override_dict)
    return build_test_settings(**field_dict)


def build_everything_fund_list() -> list:
    """Two funds that will genuinely drift apart."""
    return [
        build_test_fund(
            "Equity",
            15000.0,
            14.0,
            target_allocation_percent_float=65.0,
        ),
        build_test_fund(
            "Debt",
            5000.0,
            6.0,
            target_allocation_percent_float=35.0,
        ),
    ]


def test_every_feature_at_once_still_runs():
    """Step-up, pause, withdrawals and rebalancing together."""
    simulation_result = run_engine(
        build_everything_fund_list(), build_everything_settings()
    )
    assert simulation_result.ending_value_float > 0.0
    assert simulation_result.ending_invested_float > 0.0
    assert simulation_result.ending_withdrawn_float > 0.0
    assert simulation_result.rebalance_events_list


def test_the_running_totals_never_go_backwards():
    """Cumulative means cumulative, whatever else is running.

    An invariant rather than a figure. A combination that made a
    running total fall would be a month counted twice, or a reset
    one feature performed behind another's back.
    """
    simulation_result = run_engine(
        build_everything_fund_list(), build_everything_settings()
    )
    for field_str in (
        "invested_amount_float",
        "withdrawn_amount_float",
        "tax_paid_float",
    ):
        value_list = [
            getattr(snapshot, field_str)
            for snapshot in simulation_result.monthly_snapshots_list
        ]
        assert value_list == sorted(
            value_list
        ), f"{field_str} decreases somewhere in the run"


def test_the_invested_total_is_the_sum_of_its_own_months():
    """The cumulative column has to agree with the monthly one.

    Two numbers the engine reports separately; if a combination of
    features writes one without the other, they part company.
    """
    simulation_result = run_engine(
        build_everything_fund_list(), build_everything_settings()
    )
    monthly_total_float = sum(
        snapshot.monthly_sip_float
        for snapshot in simulation_result.monthly_snapshots_list
    )
    assert simulation_result.ending_invested_float == pytest.approx(
        monthly_total_float, rel=1e-9
    )


def test_the_withdrawn_total_is_the_sum_of_its_own_months():
    """The same agreement, on the way out."""
    simulation_result = run_engine(
        build_everything_fund_list(), build_everything_settings()
    )
    monthly_total_float = sum(
        snapshot.monthly_withdrawal_float
        for snapshot in simulation_result.monthly_snapshots_list
    )
    assert simulation_result.ending_withdrawn_float == (
        pytest.approx(monthly_total_float, rel=1e-9)
    )


def test_the_pause_still_bites_when_everything_else_runs():
    """A feature must not stop working because others are on.

    The same plan with and without its pause. The difference in
    what was invested has to be the instalments the pause covered,
    stepped up like every other instalment in that stretch - so it
    is derived here from the escalation series rather than assumed
    to be the plain instalment.
    """
    fund_list = build_everything_fund_list()
    paused_result = run_engine(
        fund_list, build_everything_settings()
    )
    full_result = run_engine(
        fund_list, build_everything_settings(pauses=PauseSettings())
    )
    monthly_float = sum(
        fund.monthly_sip_float for fund in fund_list
    )
    # The break covers 2031 and 2032: plan years five and six of a
    # plan that starts in January 2026.
    missing_float = sum(
        monthly_float * (1.08**year_int) * MONTHS_IN_YEAR_INT
        for year_int in (5, 6)
    )
    assert (
        full_result.ending_invested_float
        - paused_result.ending_invested_float
    ) == pytest.approx(missing_float, rel=1e-9)


def test_a_pause_inside_a_step_up_does_not_stop_the_escalation():
    """Resuming picks up the escalated instalment, not the old one.

    A step-up that paused along with the contributions would
    quietly reset the plan to a smaller instalment for the rest of
    its life.
    """
    fund_list = build_everything_fund_list()
    simulation_result = run_engine(
        fund_list, build_everything_settings()
    )
    monthly_float = sum(
        fund.monthly_sip_float for fund in fund_list
    )
    resume_month_int = 7 * MONTHS_IN_YEAR_INT
    snapshot = simulation_result.monthly_snapshots_list[
        resume_month_int
    ]
    assert snapshot.monthly_sip_float == pytest.approx(
        monthly_float * (1.08**7), rel=1e-9
    )


def test_withdrawals_reduce_the_ending_value_they_come_from():
    """Everything else held constant, only the withdrawal differs."""
    fund_list = build_everything_fund_list()
    with_result = run_engine(fund_list, build_everything_settings())
    without_result = run_engine(
        fund_list,
        build_everything_settings(
            withdrawal=WithdrawalSettings(is_enabled_bool=False)
        ),
    )
    assert (
        without_result.ending_value_float
        > with_result.ending_value_float
    )


def test_withdrawing_during_a_rebalancing_schedule_still_pays():
    """Two features that both move money, running together.

    A rebalance liquidates and re-buys; a withdrawal sells. Run at
    the same time, the withdrawal must still be met in full.
    """
    simulation_result = run_engine(
        build_everything_fund_list(), build_everything_settings()
    )
    assert (
        simulation_result.total_unmet_withdrawal_float
        == pytest.approx(0.0, abs=PAISA_TOLERANCE_FLOAT)
    )
    paying_list = [
        snapshot
        for snapshot in simulation_result.monthly_snapshots_list
        if snapshot.monthly_withdrawal_float > 0.0
    ]
    assert all(
        snapshot.monthly_withdrawal_float == pytest.approx(15000.0)
        for snapshot in paying_list
    )


def test_rebalancing_changes_the_answer_and_says_so():
    """The policy switch has to be visible in the outcome."""
    fund_list = build_everything_fund_list()
    on_result = run_engine(fund_list, build_everything_settings())
    off_result = run_engine(
        fund_list,
        build_everything_settings(
            rebalance=RebalanceSettings(is_enabled_bool=False)
        ),
    )
    assert on_result.ending_value_float != pytest.approx(
        off_result.ending_value_float, rel=1e-6
    )


def test_the_horizon_is_the_number_of_months_simulated():
    """An off-by-one in the month grid moves every figure."""
    for years_int in (1, 7, 25, 40):
        simulation_result = run_engine(
            [build_test_fund("Solo", 1000.0, 10.0)],
            build_test_settings(horizon_years_int=years_int),
        )
        assert len(simulation_result.monthly_snapshots_list) == (
            years_int * MONTHS_IN_YEAR_INT
        )


def test_a_zero_return_plan_returns_exactly_what_went_in():
    """The one case whose answer nobody can argue about."""
    monthly_float, years_int = 5000.0, 12
    simulation_result = run_engine(
        [build_test_fund("Solo", monthly_float, 0.0)],
        build_test_settings(horizon_years_int=years_int),
    )
    expected_float = monthly_float * years_int * MONTHS_IN_YEAR_INT
    assert simulation_result.ending_invested_float == (
        pytest.approx(expected_float)
    )
    assert simulation_result.ending_value_float == pytest.approx(
        expected_float, rel=1e-9
    )
