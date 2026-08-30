"""Taking money out in a lump, and closing a plan for good.

The engine could always drip money out on a schedule. It could not
take a single amount out on a single month, and it could not be
told to stop: a reader who wanted to buy a car in year eight, or to
cash the whole thing in at retirement, had no way to say so.

These are the two events that fixed that, and this file holds them
to the same standard as everything else here - against arithmetic
worked separately, against the independently written simulators in
`reference_simulator.py` and `reference_tax.py`, and against the
laws that must hold whatever the arithmetic says.

The combinations matter more than the features. A lump withdrawal
on a rebalancing month, a closure in a month that also pays an
instalment, a plan closed and then started again years later: each
of those crosses two mechanisms that were written separately, and
that is precisely where the defects of the last month all lived.
"""

from __future__ import annotations

from datetime import date

import pytest

from conftest import build_test_fund, build_test_settings
from investment_journey_simulator.constants import (
    REBALANCE_METHOD_FULL_STR,
    REBALANCE_TARGET_COLUMN_STR,
    STEPUP_MODE_GLOBAL_STR,
    WITHDRAWAL_MODE_FIXED_STR,
)
from investment_journey_simulator.engine import PortfolioSimulator
from investment_journey_simulator.models import (
    OneOffWithdrawal,
    RebalanceSettings,
    StepUpSettings,
    WithdrawalSettings,
)
from investment_journey_simulator.plan_scenario import (
    PlanScenario,
    compile_scenario,
)
from investment_journey_simulator.timeline import (
    EVENT_LUMPSUM_WITHDRAW_STR,
    EVENT_START_SIP_STR,
    EVENT_WITHDRAW_ALL_STR,
    TimelineEvent,
    TimelinePlan,
)
from reference_simulator import run_reference

MONTHS_IN_YEAR_INT: int = 12
PAISA_TOLERANCE_FLOAT: float = 0.01
TAX_FREE_FIELD_DICT: dict = {
    "short_term_tax_percent_float": 0.0,
    "long_term_tax_percent_float": 0.0,
    "exemption_amount_float": 0.0,
}


def build_free_fund(
    name_str: str,
    monthly_float: float,
    return_percent_float: float,
    **override_field_dict,
):
    """A fund with no tax, so the reference can check it."""
    return build_test_fund(
        name_str,
        monthly_float,
        return_percent_float,
        **{**TAX_FREE_FIELD_DICT, **override_field_dict},
    )


def assert_matches_reference(fund_list, settings):
    """The two implementations must agree on every figure."""
    engine_result = PortfolioSimulator(fund_list, settings).run()
    reference_outcome = run_reference(fund_list, settings)
    for label_str, got_float, want_float in (
        (
            "value",
            engine_result.ending_value_float,
            reference_outcome.ending_value_float,
        ),
        (
            "invested",
            engine_result.ending_invested_float,
            reference_outcome.invested_float,
        ),
        (
            "withdrawn",
            engine_result.ending_withdrawn_float,
            reference_outcome.withdrawn_float,
        ),
    ):
        assert got_float == pytest.approx(
            want_float, rel=1e-9, abs=PAISA_TOLERANCE_FLOAT
        ), f"{label_str}: {got_float} vs {want_float}"
    return engine_result


# ------------------------------------------------------------------
# A lump sum out, against arithmetic done by hand.
# ------------------------------------------------------------------
def test_a_lump_withdrawal_removes_exactly_what_was_asked_for():
    """The corpus falls by the amount, and by its lost growth.

    REFERENCE: G1-ANALYTIC. With no tax and no charges, the gap
    between the plan with the withdrawal and the plan without is
    the amount taken, compounded for the months that remained
    after it.

    "After it" is the whole subtlety. The sale happens at the
    close of its own month, so that month's growth has already
    been earned and only the months following are lost: 119 of
    them here, not 120. An off-by-one lands within one per cent,
    which is exactly the size of error a test written to agree
    with the code would have enshrined.
    """
    monthly_rate_float = (1.0 + 0.12) ** (1.0 / 12.0) - 1.0
    taken_float = 200000.0
    taken_month_int = 60
    horizon_years_int = 15
    fund_list = [build_free_fund("Solo", 10000.0, 12.0)]
    without_result = PortfolioSimulator(
        fund_list,
        build_test_settings(horizon_years_int=horizon_years_int),
    ).run()
    with_result = PortfolioSimulator(
        fund_list,
        build_test_settings(
            horizon_years_int=horizon_years_int,
            one_off_withdrawals_list=[
                OneOffWithdrawal(taken_month_int, taken_float, "")
            ],
        ),
    ).run()
    remaining_months_int = (
        horizon_years_int * MONTHS_IN_YEAR_INT - taken_month_int - 1
    )
    expected_gap_float = taken_float * (
        (1.0 + monthly_rate_float) ** remaining_months_int
    )
    assert (
        without_result.ending_value_float
        - with_result.ending_value_float
    ) == pytest.approx(expected_gap_float, rel=1e-9)


def test_a_lump_withdrawal_is_reported_as_money_withdrawn():
    """It counts as money out, not as a smaller contribution."""
    result = PortfolioSimulator(
        [build_free_fund("Solo", 10000.0, 12.0)],
        build_test_settings(
            horizon_years_int=10,
            one_off_withdrawals_list=[
                OneOffWithdrawal(60, 150000.0, "")
            ],
        ),
    ).run()
    assert result.ending_withdrawn_float == pytest.approx(
        150000.0, abs=PAISA_TOLERANCE_FLOAT
    )
    assert result.ending_invested_float == pytest.approx(
        10000.0 * 10 * MONTHS_IN_YEAR_INT
    )


def test_a_lump_withdrawal_larger_than_the_corpus_is_capped():
    """It takes what is there and records the rest as unmet.

    REFERENCE: G4-SYNTHETIC. The alternative - a negative
    balance - would be arithmetic nobody could act on.
    """
    result = PortfolioSimulator(
        [build_free_fund("Solo", 10000.0, 12.0)],
        build_test_settings(
            horizon_years_int=10,
            one_off_withdrawals_list=[
                OneOffWithdrawal(12, 50_000_000.0, "")
            ],
        ),
    ).run()
    snapshot = result.monthly_snapshots_list[12]
    assert snapshot.portfolio_value_float >= 0.0
    assert snapshot.unmet_withdrawal_float > 0.0
    assert snapshot.monthly_withdrawal_float > 0.0
    for later_snapshot in result.monthly_snapshots_list:
        assert later_snapshot.portfolio_value_float >= -1e-9


def test_a_named_fund_pays_the_whole_lump_itself():
    """Naming a fund means that fund, not the portfolio.

    REFERENCE: G4-SYNTHETIC. Taking part of it from a fund the
    reader did not name would be worse than falling short.
    """
    fund_list = [
        build_free_fund("Equity", 10000.0, 12.0),
        build_free_fund("Debt", 10000.0, 6.0),
    ]
    result = PortfolioSimulator(
        fund_list,
        build_test_settings(
            horizon_years_int=10,
            one_off_withdrawals_list=[
                OneOffWithdrawal(60, 300000.0, "Debt")
            ],
        ),
    ).run()
    debt_outcome = next(
        outcome
        for outcome in result.fund_outcomes_list
        if outcome.name_str == "Debt"
    )
    equity_outcome = next(
        outcome
        for outcome in result.fund_outcomes_list
        if outcome.name_str == "Equity"
    )
    assert debt_outcome.withdrawn_amount_float == pytest.approx(
        300000.0, abs=PAISA_TOLERANCE_FLOAT
    )
    assert equity_outcome.withdrawn_amount_float == 0.0


def test_a_lump_withdrawal_matches_the_reference_simulator():
    """REFERENCE: G3-CROSSCHECK."""
    assert_matches_reference(
        [
            build_free_fund(
                "Equity",
                10000.0,
                14.0,
                target_allocation_percent_float=60.0,
            ),
            build_free_fund(
                "Debt",
                10000.0,
                6.0,
                target_allocation_percent_float=40.0,
            ),
        ],
        build_test_settings(
            horizon_years_int=15,
            one_off_withdrawals_list=[
                OneOffWithdrawal(60, 400000.0, ""),
                OneOffWithdrawal(120, 250000.0, "Equity"),
            ],
        ),
    )


# ------------------------------------------------------------------
# Closing the plan.
# ------------------------------------------------------------------
def test_closing_a_plan_leaves_exactly_nothing():
    """Not nearly nothing. Nothing.

    REFERENCE: G1-ANALYTIC. Selling the balance compares a running
    total against each lot in turn and can leave a fraction
    behind; selling everything empties the book. The difference is
    nine nano-rupees, and the difference between "empty" and
    "almost empty" is a kind, not a size.

    Only the liquidation month is asserted, because this settings
    object liquidates without stopping anything: the instalment
    keeps running and rebuilds the corpus from the next month.
    That is the honest reading of the two instructions given, and
    `test_a_closed_timeline_is_flat_at_zero_afterwards` covers the
    timeline event, which does stop it.
    """
    result = PortfolioSimulator(
        [build_free_fund("Solo", 10000.0, 12.0)],
        build_test_settings(
            horizon_years_int=20, liquidation_month_index_int=120
        ),
    ).run()
    assert result.monthly_snapshots_list[
        120
    ].portfolio_value_float == 0.0


def test_a_closed_plan_pays_out_what_it_held():
    """Everything that was there arrives, less the charges."""
    fund_list = [build_free_fund("Solo", 10000.0, 12.0)]
    open_result = PortfolioSimulator(
        fund_list, build_test_settings(horizon_years_int=10)
    ).run()
    closed_result = PortfolioSimulator(
        fund_list,
        build_test_settings(
            horizon_years_int=10,
            liquidation_month_index_int=119,
        ),
    ).run()
    assert closed_result.ending_withdrawn_float == pytest.approx(
        open_result.ending_value_float, rel=1e-9
    )
    assert closed_result.ending_value_float == 0.0


def test_a_closed_plan_matches_the_reference_simulator():
    """REFERENCE: G3-CROSSCHECK."""
    assert_matches_reference(
        [
            build_free_fund(
                "Equity",
                10000.0,
                14.0,
                target_allocation_percent_float=60.0,
            ),
            build_free_fund(
                "Debt",
                5000.0,
                6.0,
                target_allocation_percent_float=40.0,
            ),
        ],
        build_test_settings(
            horizon_years_int=20,
            liquidation_month_index_int=120,
            rebalance=RebalanceSettings(
                is_enabled_bool=True,
                interval_months_int=12,
                method_str=REBALANCE_METHOD_FULL_STR,
                target_mode_str=REBALANCE_TARGET_COLUMN_STR,
                tax_funding_str="OUTSIDE",
            ),
        ),
    )


# ------------------------------------------------------------------
# The timeline, which is where a reader actually meets these.
# ------------------------------------------------------------------
def build_timeline_result(event_list: list, years_int: int = 20):
    """Compile a timeline and run it, as the app does."""
    scenario = PlanScenario(
        plan=TimelinePlan(date(2026, 1, 1), years_int, event_list),
        fund_list=[build_free_fund("Solo", 0.0, 12.0)],
    )
    compiled = compile_scenario(scenario)
    return PortfolioSimulator(
        compiled.fund_list, compiled.settings
    ).run()


def test_a_closed_timeline_is_flat_at_zero_afterwards():
    """The reported symptom, as an assertion.

    REFERENCE: G4-SYNTHETIC. A plan closed in year ten holds
    nothing for the ten years that remain, and the chart draws
    those years rather than stopping short.
    """
    result = build_timeline_result(
        [
            TimelineEvent(
                EVENT_START_SIP_STR, date(2026, 1, 1), 25000.0
            ),
            TimelineEvent(
                EVENT_WITHDRAW_ALL_STR, date(2036, 1, 1)
            ),
        ]
    )
    close_index_int = 10 * MONTHS_IN_YEAR_INT
    assert len(result.monthly_snapshots_list) == (
        20 * MONTHS_IN_YEAR_INT
    )
    assert (
        result.monthly_snapshots_list[
            close_index_int - 1
        ].portfolio_value_float
        > 0.0
    )
    for snapshot in result.monthly_snapshots_list[
        close_index_int:
    ]:
        assert snapshot.portfolio_value_float == 0.0
    # The closing month pays its own instalment before it sells,
    # so the silence starts the month after.
    for snapshot in result.monthly_snapshots_list[
        close_index_int + 1 :
    ]:
        assert snapshot.monthly_sip_float == 0.0


def test_a_closed_timeline_can_be_started_again():
    """A life that stops and restarts is an ordinary life.

    REFERENCE: G4-SYNTHETIC. The corpus goes to zero, stays there
    while nothing is being paid in, and climbs again from the
    month the reader starts investing once more.
    """
    result = build_timeline_result(
        [
            TimelineEvent(
                EVENT_START_SIP_STR, date(2026, 1, 1), 25000.0
            ),
            TimelineEvent(
                EVENT_WITHDRAW_ALL_STR, date(2036, 1, 1)
            ),
            TimelineEvent(
                EVENT_START_SIP_STR, date(2039, 1, 1), 40000.0
            ),
        ]
    )
    snapshot_list = result.monthly_snapshots_list
    close_index_int = 10 * MONTHS_IN_YEAR_INT
    restart_index_int = 13 * MONTHS_IN_YEAR_INT
    for snapshot in snapshot_list[
        close_index_int:restart_index_int
    ]:
        assert snapshot.portfolio_value_float == 0.0
    assert snapshot_list[
        restart_index_int
    ].monthly_sip_float == pytest.approx(40000.0)
    assert (
        snapshot_list[restart_index_int].portfolio_value_float > 0.0
    )
    assert snapshot_list[-1].portfolio_value_float > 0.0


def test_the_closing_month_still_pays_its_instalment():
    """A plan that ends in June invests in June, then sells.

    REFERENCE: G4-SYNTHETIC. The convention is stated here so a
    change to the order of the month fails a test rather than
    quietly moving a figure.
    """
    result = build_timeline_result(
        [
            TimelineEvent(
                EVENT_START_SIP_STR, date(2026, 1, 1), 25000.0
            ),
            TimelineEvent(
                EVENT_WITHDRAW_ALL_STR, date(2036, 1, 1)
            ),
        ]
    )
    closing_snapshot = result.monthly_snapshots_list[
        10 * MONTHS_IN_YEAR_INT
    ]
    assert closing_snapshot.monthly_sip_float == pytest.approx(
        25000.0
    )
    assert closing_snapshot.portfolio_value_float == 0.0


def test_a_lump_withdrawal_on_the_timeline_reaches_the_engine():
    """The event compiles to a sale on the month it was placed."""
    result = build_timeline_result(
        [
            TimelineEvent(
                EVENT_START_SIP_STR, date(2026, 1, 1), 25000.0
            ),
            TimelineEvent(
                EVENT_LUMPSUM_WITHDRAW_STR,
                date(2031, 6, 1),
                300000.0,
            ),
        ]
    )
    month_index_int = 5 * MONTHS_IN_YEAR_INT + 5
    snapshot = result.monthly_snapshots_list[month_index_int]
    assert snapshot.monthly_withdrawal_float == pytest.approx(
        300000.0, abs=PAISA_TOLERANCE_FLOAT
    )


# ------------------------------------------------------------------
# Combinations, which is where the defects have always been.
# ------------------------------------------------------------------
def build_everything_settings(**override_dict):
    """Every money-moving feature at once."""
    field_dict = dict(
        horizon_years_int=25,
        stepup=StepUpSettings(STEPUP_MODE_GLOBAL_STR, 8.0),
        withdrawal=WithdrawalSettings(
            is_enabled_bool=True,
            start_month_index_int=15 * MONTHS_IN_YEAR_INT,
            mode_str=WITHDRAWAL_MODE_FIXED_STR,
            fixed_amount_float=12000.0,
        ),
        rebalance=RebalanceSettings(
            is_enabled_bool=True,
            interval_months_int=12,
            method_str=REBALANCE_METHOD_FULL_STR,
            target_mode_str=REBALANCE_TARGET_COLUMN_STR,
            tax_funding_str="OUTSIDE",
        ),
        one_off_withdrawals_list=[
            OneOffWithdrawal(60, 300000.0, ""),
            OneOffWithdrawal(
                12 * MONTHS_IN_YEAR_INT - 1, 500000.0, "Equity"
            ),
        ],
    )
    field_dict.update(override_dict)
    return build_test_settings(**field_dict)


def build_everything_fund_list() -> list:
    """Two funds that drift apart."""
    return [
        build_free_fund(
            "Equity",
            15000.0,
            14.0,
            target_allocation_percent_float=65.0,
        ),
        build_free_fund(
            "Debt",
            5000.0,
            6.0,
            target_allocation_percent_float=35.0,
        ),
    ]


def test_lump_withdrawals_alongside_everything_else():
    """Step-up, standing withdrawal, rebalance and two lumps out.

    REFERENCE: G3-CROSSCHECK. One of the lumps is dated to a
    rebalancing month on purpose: both sell, and both sell from
    the same corpus.
    """
    assert_matches_reference(
        build_everything_fund_list(), build_everything_settings()
    )


def test_a_closure_alongside_everything_else():
    """The same plan, ended part way through.

    REFERENCE: G3-CROSSCHECK.
    """
    assert_matches_reference(
        build_everything_fund_list(),
        build_everything_settings(
            liquidation_month_index_int=(
                18 * MONTHS_IN_YEAR_INT
            )
        ),
    )


def test_a_lump_out_in_the_same_month_as_the_closure():
    """Two sales in one month, one of which ends the plan.

    REFERENCE: G3-CROSSCHECK. The lump is met first and the
    closure takes whatever is left, so the two cannot between
    them raise more than the corpus held.
    """
    closure_month_int = 18 * MONTHS_IN_YEAR_INT
    engine_result = assert_matches_reference(
        build_everything_fund_list(),
        build_everything_settings(
            one_off_withdrawals_list=[
                OneOffWithdrawal(closure_month_int, 400000.0, "")
            ],
            liquidation_month_index_int=closure_month_int,
        ),
    )
    assert engine_result.monthly_snapshots_list[
        closure_month_int
    ].portfolio_value_float == 0.0


def test_the_running_totals_still_only_rise():
    """Money out is cumulative however it left.

    REFERENCE: G4-SYNTHETIC.
    """
    result = PortfolioSimulator(
        build_everything_fund_list(),
        build_everything_settings(
            liquidation_month_index_int=(
                18 * MONTHS_IN_YEAR_INT
            )
        ),
    ).run()
    for field_str in (
        "invested_amount_float",
        "withdrawn_amount_float",
    ):
        value_list = [
            getattr(snapshot, field_str)
            for snapshot in result.monthly_snapshots_list
        ]
        assert value_list == sorted(value_list), field_str
