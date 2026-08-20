"""Events landing on the same month as each other.

The fuzz in `test_engine_fuzz.py` covers breadth. This covers the
collisions it would hit only by luck: two things happening in the
same month, in an order that has to be decided one way or the
other. Each test below states which way, so a future change that
reverses it fails here rather than silently moving somebody's
retirement figure.

Every case is checked against the reference simulator where tax is
off, and against an invariant where it is not.
"""

from __future__ import annotations

from datetime import date

import pytest

from conftest import build_test_fund, build_test_settings
from investment_journey_simulator.constants import (
    PAUSE_SCOPE_BOTH_STR,
    PAUSE_SCOPE_SIP_STR,
    PAUSE_SCOPE_WITHDRAWAL_STR,
    REBALANCE_METHOD_FULL_STR,
    REBALANCE_TARGET_COLUMN_STR,
    STEPUP_MODE_GLOBAL_STR,
    WITHDRAWAL_MODE_FIXED_STR,
    WITHDRAWAL_MODE_PERCENT_STR,
)
from investment_journey_simulator.engine import PortfolioSimulator
from investment_journey_simulator.models import (
    InstalmentOverride,
    OneOffContribution,
    PauseRange,
    PauseSettings,
    RebalanceSettings,
    StepUpSettings,
    WithdrawalSettings,
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


def assert_matches_reference(fund_list, settings) -> None:
    """The two implementations must produce the same figures."""
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
        ), f"{label_str}: engine {got_float} vs reference {want_float}"
    return engine_result


def build_sip_pause(
    start_date: date,
    end_date: date,
    scope_str: str = PAUSE_SCOPE_SIP_STR,
) -> PauseSettings:
    """One pause range, of one scope."""
    return PauseSettings(
        pause_ranges_list=[
            PauseRange(start_date, end_date, scope_str)
        ]
    )


def build_withdrawal(
    amount_float: float, start_month_int: int
) -> WithdrawalSettings:
    """A flat monthly withdrawal."""
    return WithdrawalSettings(
        is_enabled_bool=True,
        start_month_index_int=start_month_int,
        mode_str=WITHDRAWAL_MODE_FIXED_STR,
        fixed_amount_float=amount_float,
    )


def build_rebalance(interval_months_int: int = 12):
    """Calendar rebalancing to the declared target column."""
    return RebalanceSettings(
        is_enabled_bool=True,
        interval_months_int=interval_months_int,
        method_str=REBALANCE_METHOD_FULL_STR,
        target_mode_str=REBALANCE_TARGET_COLUMN_STR,
        tax_funding_str="OUTSIDE",
    )


# ------------------------------------------------------------------
# A withdrawal and a pause in the same month.
# ------------------------------------------------------------------
def test_a_withdrawal_starting_inside_a_withdrawal_pause_waits():
    """The pause wins: nothing comes out until it lifts.

    REFERENCE: G4-SYNTHETIC. The withdrawal is scheduled to begin
    in month 12, inside a pause that covers months 12 to 23, so the
    first payment must be month 24 and not month 12.
    """
    settings = build_test_settings(
        horizon_years_int=4,
        withdrawal=build_withdrawal(
            5000.0, MONTHS_IN_YEAR_INT
        ),
        pauses=build_sip_pause(
            date(2027, 1, 1),
            date(2027, 12, 1),
            PAUSE_SCOPE_WITHDRAWAL_STR,
        ),
    )
    fund_list = [build_free_fund("Solo", 20000.0, 10.0)]
    engine_result = assert_matches_reference(fund_list, settings)
    snapshot_list = engine_result.monthly_snapshots_list
    paying_list = [
        index_int
        for index_int, snapshot in enumerate(snapshot_list)
        if snapshot.monthly_withdrawal_float > 0.0
    ]
    assert paying_list[0] == 2 * MONTHS_IN_YEAR_INT


def test_a_pause_scoped_to_both_stops_money_going_each_way():
    """One range, two flows, same months.

    REFERENCE: G4-SYNTHETIC.
    """
    settings = build_test_settings(
        horizon_years_int=5,
        withdrawal=build_withdrawal(3000.0, 0),
        pauses=build_sip_pause(
            date(2028, 1, 1),
            date(2028, 12, 1),
            PAUSE_SCOPE_BOTH_STR,
        ),
    )
    fund_list = [build_free_fund("Solo", 15000.0, 9.0)]
    engine_result = assert_matches_reference(fund_list, settings)
    for month_index_int in range(
        2 * MONTHS_IN_YEAR_INT, 3 * MONTHS_IN_YEAR_INT
    ):
        snapshot = engine_result.monthly_snapshots_list[
            month_index_int
        ]
        assert snapshot.monthly_sip_float == 0.0
        assert snapshot.monthly_withdrawal_float == 0.0


def test_a_pause_covering_the_whole_horizon_invests_nothing():
    """The degenerate case, which must not divide by anything.

    REFERENCE: G4-SYNTHETIC.
    """
    settings = build_test_settings(
        horizon_years_int=3,
        pauses=build_sip_pause(
            date(2026, 1, 1), date(2029, 12, 1)
        ),
    )
    fund_list = [build_free_fund("Solo", 10000.0, 12.0)]
    engine_result = assert_matches_reference(fund_list, settings)
    assert engine_result.ending_invested_float == 0.0
    assert engine_result.ending_value_float == 0.0


# ------------------------------------------------------------------
# A pause and a step-up in the same stretch.
# ------------------------------------------------------------------
def test_a_step_up_lands_during_a_pause_and_still_counts():
    """The escalation clock does not stop when the money does.

    REFERENCE: G4-SYNTHETIC. The pause covers the whole of plan
    year two, which contains an anniversary. On resuming in year
    three the instalment must be the twice-escalated one.
    """
    monthly_float, stepup_percent_float = 10000.0, 10.0
    settings = build_test_settings(
        horizon_years_int=4,
        stepup=StepUpSettings(
            STEPUP_MODE_GLOBAL_STR, stepup_percent_float
        ),
        pauses=build_sip_pause(
            date(2027, 1, 1), date(2027, 12, 1)
        ),
    )
    fund_list = [build_free_fund("Solo", monthly_float, 10.0)]
    engine_result = assert_matches_reference(fund_list, settings)
    resume_snapshot = engine_result.monthly_snapshots_list[
        2 * MONTHS_IN_YEAR_INT
    ]
    assert resume_snapshot.monthly_sip_float == pytest.approx(
        monthly_float * 1.1**2
    )


# ------------------------------------------------------------------
# Instalment changes colliding with each other and with events.
# ------------------------------------------------------------------
def test_two_instalment_changes_on_one_month_take_the_later_one():
    """Both apply in order, so the last one written wins.

    REFERENCE: G4-SYNTHETIC. A tie on the month index is broken by
    list order, which is the order the reader added them in.
    """
    settings = build_test_settings(
        horizon_years_int=2,
        instalment_override_list=[
            InstalmentOverride(0, 5000.0, ""),
            InstalmentOverride(0, 9000.0, ""),
        ],
    )
    fund_list = [build_free_fund("Solo", 1000.0, 8.0)]
    engine_result = assert_matches_reference(fund_list, settings)
    assert engine_result.ending_invested_float == pytest.approx(
        9000.0 * 2 * MONTHS_IN_YEAR_INT
    )


def test_an_instalment_change_restarts_the_escalation_clock():
    """Changing the amount resets when the next step-up is due.

    REFERENCE: G4-SYNTHETIC. The override lands at month 6, so the
    first escalation after it falls at month 18, not month 12.
    """
    settings = build_test_settings(
        horizon_years_int=3,
        stepup=StepUpSettings(STEPUP_MODE_GLOBAL_STR, 10.0),
        instalment_override_list=[
            InstalmentOverride(6, 20000.0, "")
        ],
    )
    fund_list = [build_free_fund("Solo", 1000.0, 8.0)]
    engine_result = assert_matches_reference(fund_list, settings)
    snapshot_list = engine_result.monthly_snapshots_list
    assert snapshot_list[17].monthly_sip_float == pytest.approx(
        20000.0
    )
    assert snapshot_list[18].monthly_sip_float == pytest.approx(
        20000.0 * 1.1
    )


def test_an_instalment_change_inside_a_pause_applies_on_resuming():
    """The change is remembered even though no money moved.

    REFERENCE: G4-SYNTHETIC.
    """
    settings = build_test_settings(
        horizon_years_int=3,
        pauses=build_sip_pause(
            date(2026, 7, 1), date(2026, 12, 1)
        ),
        instalment_override_list=[
            InstalmentOverride(8, 30000.0, "")
        ],
    )
    fund_list = [build_free_fund("Solo", 4000.0, 8.0)]
    engine_result = assert_matches_reference(fund_list, settings)
    snapshot_list = engine_result.monthly_snapshots_list
    assert snapshot_list[8].monthly_sip_float == 0.0
    assert snapshot_list[
        MONTHS_IN_YEAR_INT
    ].monthly_sip_float == pytest.approx(30000.0)


def test_an_instalment_of_zero_stops_the_plan_without_a_pause():
    """Setting the amount to nothing is a legitimate way to stop.

    REFERENCE: G4-SYNTHETIC.
    """
    settings = build_test_settings(
        horizon_years_int=3,
        instalment_override_list=[
            InstalmentOverride(MONTHS_IN_YEAR_INT, 0.0, "")
        ],
    )
    fund_list = [build_free_fund("Solo", 8000.0, 11.0)]
    engine_result = assert_matches_reference(fund_list, settings)
    assert engine_result.ending_invested_float == pytest.approx(
        8000.0 * MONTHS_IN_YEAR_INT
    )


# ------------------------------------------------------------------
# A rebalance colliding with the other flows of its month.
# ------------------------------------------------------------------
def test_a_rebalance_and_a_withdrawal_in_the_same_month():
    """The withdrawal is taken first, then the weights are fixed.

    REFERENCE: G4-SYNTHETIC. Rebalancing after the withdrawal is
    what makes the target weights hold on the corpus the investor
    is actually left with. Month 11 is both the twelfth month of
    the rebalancing interval and a withdrawal month.
    """
    settings = build_test_settings(
        horizon_years_int=6,
        withdrawal=build_withdrawal(4000.0, 0),
        rebalance=build_rebalance(MONTHS_IN_YEAR_INT),
    )
    fund_list = [
        build_free_fund(
            "Equity",
            10000.0,
            16.0,
            target_allocation_percent_float=60.0,
        ),
        build_free_fund(
            "Debt",
            10000.0,
            5.0,
            target_allocation_percent_float=40.0,
        ),
    ]
    engine_result = assert_matches_reference(fund_list, settings)
    event = engine_result.rebalance_events_list[0]
    assert event.weights_after_dict["Equity"] == pytest.approx(
        60.0, abs=1e-6
    )


def test_a_rebalance_in_a_month_whose_contributions_are_paused():
    """Nothing to invest, but plenty to realign.

    REFERENCE: G4-SYNTHETIC.
    """
    settings = build_test_settings(
        horizon_years_int=4,
        rebalance=build_rebalance(MONTHS_IN_YEAR_INT),
        pauses=build_sip_pause(
            date(2026, 12, 1), date(2026, 12, 1)
        ),
    )
    fund_list = [
        build_free_fund(
            "Equity",
            10000.0,
            18.0,
            target_allocation_percent_float=50.0,
        ),
        build_free_fund(
            "Debt",
            10000.0,
            4.0,
            target_allocation_percent_float=50.0,
        ),
    ]
    engine_result = assert_matches_reference(fund_list, settings)
    assert engine_result.rebalance_events_list
    assert engine_result.monthly_snapshots_list[
        MONTHS_IN_YEAR_INT - 1
    ].monthly_sip_float == 0.0


def test_an_end_of_month_instalment_is_not_rebalanced_that_month():
    """Money that arrives after the trade is not part of it.

    REFERENCE: G4-SYNTHETIC. This is the convention: contributions
    paid at month end land after the rebalance, so the weights read
    just after a rebalance include them and are not exactly on
    target. Stated here so a change to the order is visible.
    """
    settings = build_test_settings(
        horizon_years_int=3,
        sip_at_month_start_bool=False,
        rebalance=build_rebalance(MONTHS_IN_YEAR_INT),
    )
    fund_list = [
        build_free_fund(
            "Equity",
            10000.0,
            18.0,
            target_allocation_percent_float=50.0,
        ),
        build_free_fund(
            "Debt",
            2000.0,
            4.0,
            target_allocation_percent_float=50.0,
        ),
    ]
    engine_result = assert_matches_reference(fund_list, settings)
    snapshot = engine_result.monthly_snapshots_list[
        MONTHS_IN_YEAR_INT - 1
    ]
    value_list = [
        state.value_float for state in snapshot.fund_states_list
    ]
    assert value_list[0] != pytest.approx(value_list[1])


# ------------------------------------------------------------------
# Money running out, and other degenerate corners.
# ------------------------------------------------------------------
def test_a_withdrawal_larger_than_the_corpus_empties_it_once():
    """It cannot take more than there is, and never goes negative.

    REFERENCE: G4-SYNTHETIC.
    """
    settings = build_test_settings(
        horizon_years_int=3,
        withdrawal=build_withdrawal(500000.0, 1),
    )
    fund_list = [build_free_fund("Solo", 5000.0, 10.0)]
    engine_result = assert_matches_reference(fund_list, settings)
    for snapshot in engine_result.monthly_snapshots_list:
        assert snapshot.portfolio_value_float >= -1e-9
    assert engine_result.total_unmet_withdrawal_float > 0.0


def test_a_percent_withdrawal_of_an_empty_portfolio_asks_nothing():
    """Nothing held means nothing requested, not a division error.

    REFERENCE: G4-SYNTHETIC.
    """
    settings = build_test_settings(
        horizon_years_int=2,
        withdrawal=WithdrawalSettings(
            is_enabled_bool=True,
            start_month_index_int=0,
            mode_str=WITHDRAWAL_MODE_PERCENT_STR,
            portfolio_percent_float=5.0,
        ),
    )
    fund_list = [build_free_fund("Solo", 0.0, 10.0)]
    engine_result = assert_matches_reference(fund_list, settings)
    assert engine_result.ending_withdrawn_float == 0.0
    assert engine_result.total_unmet_withdrawal_float == 0.0


def test_a_fund_that_starts_after_the_withdrawals_have_begun():
    """Joining a portfolio that is already paying out.

    REFERENCE: G4-SYNTHETIC.
    """
    settings = build_test_settings(
        horizon_years_int=6,
        withdrawal=build_withdrawal(2000.0, 0),
    )
    fund_list = [
        build_free_fund("Early", 10000.0, 11.0),
        build_free_fund(
            "Late",
            10000.0,
            11.0,
            start_date=date(2029, 1, 1),
        ),
    ]
    engine_result = assert_matches_reference(fund_list, settings)
    late_outcome = next(
        fund_outcome
        for fund_outcome in engine_result.fund_outcomes_list
        if fund_outcome.name_str == "Late"
    )
    assert late_outcome.invested_amount_float == pytest.approx(
        10000.0 * 3 * MONTHS_IN_YEAR_INT
    )


def test_a_one_off_landing_on_a_rebalancing_month():
    """A lump sum that arrives just as the weights are reset.

    REFERENCE: G4-SYNTHETIC. The one-off is paid in before the
    rebalance, so it is included in the trade rather than left
    sitting outside the target split.
    """
    settings = build_test_settings(
        horizon_years_int=3,
        rebalance=build_rebalance(MONTHS_IN_YEAR_INT),
        one_off_contributions_list=[
            OneOffContribution(
                MONTHS_IN_YEAR_INT - 1, 500000.0, "Equity"
            )
        ],
    )
    fund_list = [
        build_free_fund(
            "Equity",
            10000.0,
            14.0,
            target_allocation_percent_float=50.0,
        ),
        build_free_fund(
            "Debt",
            10000.0,
            6.0,
            target_allocation_percent_float=50.0,
        ),
    ]
    engine_result = assert_matches_reference(fund_list, settings)
    event = engine_result.rebalance_events_list[0]
    assert event.weights_after_dict["Equity"] == pytest.approx(
        50.0, abs=1e-6
    )


def test_a_negative_return_fund_shrinks_without_breaking_anything():
    """Losses are allowed, and must not produce negative holdings.

    REFERENCE: G4-SYNTHETIC.
    """
    settings = build_test_settings(
        horizon_years_int=8,
        withdrawal=build_withdrawal(1000.0, MONTHS_IN_YEAR_INT),
        rebalance=build_rebalance(MONTHS_IN_YEAR_INT),
    )
    fund_list = [
        build_free_fund(
            "Falling",
            5000.0,
            -6.0,
            target_allocation_percent_float=50.0,
        ),
        build_free_fund(
            "Rising",
            5000.0,
            9.0,
            target_allocation_percent_float=50.0,
        ),
    ]
    engine_result = assert_matches_reference(fund_list, settings)
    for snapshot in engine_result.monthly_snapshots_list:
        for state in snapshot.fund_states_list:
            assert state.value_float >= -1e-9


def build_everything_settings():
    """One plan carrying every event this engine has."""
    return build_test_settings(
        horizon_years_int=20,
        sip_at_month_start_bool=True,
        stepup=StepUpSettings(
            STEPUP_MODE_GLOBAL_STR,
            8.0,
            interval_months_int=MONTHS_IN_YEAR_INT,
            first_stepup_month_index_int=18,
        ),
        withdrawal=build_withdrawal(
            12000.0, 10 * MONTHS_IN_YEAR_INT
        ),
        pauses=PauseSettings(
            sip_pause_months_list=[4],
            withdrawal_pause_months_list=[9],
            pause_ranges_list=[
                PauseRange(
                    date(2031, 3, 1),
                    date(2032, 2, 1),
                    PAUSE_SCOPE_SIP_STR,
                ),
                PauseRange(
                    date(2038, 1, 1),
                    date(2038, 6, 1),
                    PAUSE_SCOPE_WITHDRAWAL_STR,
                ),
            ],
        ),
        rebalance=build_rebalance(MONTHS_IN_YEAR_INT),
        instalment_override_list=[
            InstalmentOverride(
                3 * MONTHS_IN_YEAR_INT, 30000.0, ""
            ),
            InstalmentOverride(
                9 * MONTHS_IN_YEAR_INT, 45000.0, ""
            ),
        ],
        one_off_contributions_list=[
            OneOffContribution(
                5 * MONTHS_IN_YEAR_INT, 400000.0, ""
            ),
            OneOffContribution(
                7 * MONTHS_IN_YEAR_INT + 3, 150000.0, "Gold"
            ),
        ],
    )


def build_everything_fund_list():
    """Three funds, one of which joins two years late."""
    return [
        build_free_fund(
            "Equity",
            15000.0,
            13.0,
            target_allocation_percent_float=55.0,
            initial_investment_float=200000.0,
        ),
        build_free_fund(
            "Debt",
            5000.0,
            6.5,
            target_allocation_percent_float=30.0,
        ),
        build_free_fund(
            "Gold",
            3000.0,
            9.0,
            target_allocation_percent_float=15.0,
            start_date=date(2027, 6, 1),
        ),
    ]


def test_everything_at_once_still_agrees_with_the_reference():
    """Every event this engine has, in one plan.

    REFERENCE: G3-CROSSCHECK. Staggered starts, a lump sum, a
    step-up, two instalment changes, a one-off, a contribution
    pause, a withdrawal pause, a withdrawal and annual rebalancing.
    """
    engine_result = assert_matches_reference(
        build_everything_fund_list(), build_everything_settings()
    )
    assert engine_result.ending_value_float > 0.0
    assert engine_result.rebalance_events_list
    assert engine_result.ending_withdrawn_float > 0.0
