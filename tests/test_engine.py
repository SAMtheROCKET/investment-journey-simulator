"""Engine tests covering every branch of the month loop."""

from __future__ import annotations

from datetime import date

import pytest

from conftest import (
    DEFAULT_START_DATE,
    build_test_fund,
    build_test_settings,
)
from investment_journey_simulator.constants import (
    EXEMPTION_LEVEL_PORTFOLIO_STR,
    PAUSE_SCOPE_BOTH_STR,
    PAUSE_SCOPE_SIP_STR,
    PAUSE_SCOPE_WITHDRAWAL_STR,
    REBALANCE_METHOD_FULL_STR,
    REBALANCE_METHOD_PARTIAL_STR,
    REBALANCE_TARGET_COLUMN_STR,
    REBALANCE_TARGET_SIP_SPLIT_STR,
    REBALANCE_TRIGGER_BAND_STR,
    REBALANCE_TRIGGER_BOTH_STR,
    REBALANCE_TRIGGER_CALENDAR_STR,
    STEPUP_MODE_BOTH_STR,
    STEPUP_MODE_GLOBAL_STR,
    STEPUP_MODE_OFF_STR,
    STEPUP_MODE_PER_FUND_STR,
    TAX_FUNDING_OUTSIDE_STR,
    TAX_FUNDING_PORTFOLIO_STR,
    WITHDRAWAL_MODE_FIXED_STR,
    WITHDRAWAL_MODE_PERCENT_STR,
    WITHDRAWAL_MODE_SCHEDULE_STR,
)
from investment_journey_simulator.engine import (
    PortfolioSimulator,
    calculate_weight_dict,
)
from investment_journey_simulator.models import (
    InstalmentOverride,
    OneOffContribution,
    PauseRange,
    PauseSettings,
    RebalanceSettings,
    StepUpSettings,
    TaxSettings,
    WithdrawalSettings,
)
from investment_journey_simulator.money_weighted import (
    calculate_pre_tax_xirr_percent_float,
)
from reference_data import (
    STATUTORY_EQUITY_EXEMPTION_RUPEES_FLOAT,
)


def run_simulation(fund_list, settings):
    """Run one simulation and return its result.

    REFERENCE: harness only.
    """
    return PortfolioSimulator(fund_list, settings).run()


# ------------------------------------------------------------------
# Horizon and month grid
# ------------------------------------------------------------------
def test_zero_horizon_produces_an_empty_result() -> None:
    """A zero-year horizon must not crash and must be empty.

    REFERENCE: G4-SYNTHETIC. Degenerate boundary of the loop.
    """
    simulation_result = run_simulation(
        [build_test_fund()], build_test_settings(horizon_years_int=0)
    )
    assert simulation_result.monthly_snapshots_list == []
    assert simulation_result.ending_value_float == 0.0
    assert simulation_result.ending_invested_float == 0.0


def test_one_month_of_a_one_year_horizon_is_recorded() -> None:
    """A one-year horizon must record exactly twelve months.

    REFERENCE: G4-SYNTHETIC. Grid length invariant.
    """
    simulation_result = run_simulation(
        [build_test_fund()], build_test_settings(horizon_years_int=1)
    )
    assert len(simulation_result.monthly_snapshots_list) == 12
    assert simulation_result.monthly_snapshots_list[
        0
    ].month_date == DEFAULT_START_DATE


def test_month_grid_rolls_over_the_year_boundary() -> None:
    """Starting in December must roll into January correctly.

    REFERENCE: G4-SYNTHETIC. Calendar arithmetic edge case.
    """
    simulation_result = run_simulation(
        [build_test_fund(start_date=date(2026, 12, 1))],
        build_test_settings(
            horizon_years_int=1,
            portfolio_start_date=date(2026, 12, 1),
        ),
    )
    assert simulation_result.monthly_snapshots_list[
        1
    ].month_date == date(2027, 1, 1)


# ------------------------------------------------------------------
# Contributions and step-up
# ------------------------------------------------------------------
def test_fund_starting_later_contributes_nothing_early() -> None:
    """A staggered fund must stay empty until its start month.

    REFERENCE: G4-SYNTHETIC. 12 months of a 24-month run.
    """
    simulation_result = run_simulation(
        [
            build_test_fund(
                "Late", start_date=date(2027, 1, 1)
            )
        ],
        build_test_settings(horizon_years_int=2),
    )
    assert simulation_result.monthly_snapshots_list[
        11
    ].portfolio_value_float == 0.0
    assert simulation_result.ending_invested_float == pytest.approx(
        12000.0
    )


@pytest.mark.parametrize(
    "mode_str, expected_invested_float",
    [
        (STEPUP_MODE_OFF_STR, 24000.0),
        (STEPUP_MODE_GLOBAL_STR, 25200.0),
        (STEPUP_MODE_PER_FUND_STR, 26400.0),
        (STEPUP_MODE_BOTH_STR, 27840.0),
    ],
)
def test_every_stepup_mode_changes_the_principal(
    mode_str: str,
    expected_invested_float: float,
) -> None:
    """All four escalation modes must behave distinctly.

    REFERENCE: G4-SYNTHETIC. 1000 per month for two years.
    Global 10 percent gives 12000 + 13200. Per fund 20 percent
    gives 12000 + 14400. BOTH multiplies the factors, so year two
    is 12000 * 1.1 * 1.2 = 15840, totalling 27840.
    """
    simulation_result = run_simulation(
        [build_test_fund(stepup_percent_float=20.0)],
        build_test_settings(
            horizon_years_int=2,
            stepup=StepUpSettings(mode_str, 10.0),
        ),
    )
    assert simulation_result.ending_invested_float == pytest.approx(
        expected_invested_float
    )


def test_stepup_interval_of_six_months_doubles_the_steps() -> None:
    """Escalating twice a year must apply twice as many steps.

    REFERENCE: G4-SYNTHETIC. Year one pays 6*1000 + 6*1100.
    """
    simulation_result = run_simulation(
        [build_test_fund()],
        build_test_settings(
            horizon_years_int=1,
            stepup=StepUpSettings(
                STEPUP_MODE_GLOBAL_STR, 10.0, interval_months_int=6
            ),
        ),
    )
    assert simulation_result.ending_invested_float == pytest.approx(
        6000.0 + 6600.0
    )


def test_delayed_first_stepup_holds_the_instalment() -> None:
    """A delayed first step must keep the original instalment.

    REFERENCE: G4-SYNTHETIC. With the first step at month 18, a
    twelve-month run never escalates.
    """
    simulation_result = run_simulation(
        [build_test_fund()],
        build_test_settings(
            horizon_years_int=1,
            stepup=StepUpSettings(
                STEPUP_MODE_GLOBAL_STR,
                10.0,
                first_stepup_month_index_int=18,
            ),
        ),
    )
    assert simulation_result.ending_invested_float == pytest.approx(
        12000.0
    )


def test_fixed_rupee_increment_adds_a_flat_amount() -> None:
    """A fixed increment must add rupees, not a percentage.

    REFERENCE: G4-SYNTHETIC. Year one 12*1000, year two
    12*(1000+500) = 18000, total 30000.
    """
    simulation_result = run_simulation(
        [build_test_fund()],
        build_test_settings(
            horizon_years_int=2,
            stepup=StepUpSettings(
                STEPUP_MODE_OFF_STR,
                fixed_increment_amount_float=500.0,
            ),
        ),
    )
    assert simulation_result.ending_invested_float == pytest.approx(
        30000.0
    )


def test_zero_interval_disables_escalation_entirely() -> None:
    """A non-positive interval must switch escalation off.

    REFERENCE: G4-SYNTHETIC. Guard branch.
    """
    simulation_result = run_simulation(
        [build_test_fund()],
        build_test_settings(
            horizon_years_int=3,
            stepup=StepUpSettings(
                STEPUP_MODE_GLOBAL_STR, 10.0, interval_months_int=0
            ),
        ),
    )
    assert simulation_result.ending_invested_float == pytest.approx(
        36000.0
    )


# ------------------------------------------------------------------
# Pauses
# ------------------------------------------------------------------
def test_recurring_month_pause_skips_that_month_every_year() -> None:
    """Pausing one month a year must drop twelve instalments.

    REFERENCE: G4-SYNTHETIC. 12 years, one paused month each.
    """
    simulation_result = run_simulation(
        [build_test_fund()],
        build_test_settings(
            horizon_years_int=12,
            pauses=PauseSettings(sip_pause_months_list=[8]),
        ),
    )
    assert simulation_result.ending_invested_float == pytest.approx(
        132000.0
    )


def test_pause_range_scoped_to_withdrawals_spares_the_sip() -> None:
    """A withdrawal-scoped pause must not stop contributions.

    REFERENCE: G4-SYNTHETIC. Scope routing branch.
    """
    simulation_result = run_simulation(
        [build_test_fund()],
        build_test_settings(
            horizon_years_int=1,
            pauses=PauseSettings(
                pause_ranges_list=[
                    PauseRange(
                        date(2026, 1, 1),
                        date(2026, 12, 1),
                        PAUSE_SCOPE_WITHDRAWAL_STR,
                    )
                ]
            ),
        ),
    )
    assert simulation_result.ending_invested_float == pytest.approx(
        12000.0
    )


def test_both_scope_pause_stops_contributions_too() -> None:
    """A BOTH-scoped pause must stop the contribution as well.

    REFERENCE: G4-SYNTHETIC. Scope routing branch.
    """
    simulation_result = run_simulation(
        [build_test_fund()],
        build_test_settings(
            horizon_years_int=1,
            pauses=PauseSettings(
                pause_ranges_list=[
                    PauseRange(
                        date(2026, 1, 1),
                        date(2026, 6, 1),
                        PAUSE_SCOPE_BOTH_STR,
                    )
                ]
            ),
        ),
    )
    assert simulation_result.ending_invested_float == pytest.approx(
        6000.0
    )


def test_reversed_pause_range_never_matches() -> None:
    """An end date before the start date must pause nothing.

    REFERENCE: G4-SYNTHETIC. Defensive branch.
    """
    simulation_result = run_simulation(
        [build_test_fund()],
        build_test_settings(
            horizon_years_int=1,
            pauses=PauseSettings(
                pause_ranges_list=[
                    PauseRange(
                        date(2026, 12, 1),
                        date(2026, 1, 1),
                        PAUSE_SCOPE_SIP_STR,
                    )
                ]
            ),
        ),
    )
    assert simulation_result.ending_invested_float == pytest.approx(
        12000.0
    )


# ------------------------------------------------------------------
# Withdrawals
# ------------------------------------------------------------------
def test_withdrawal_before_start_month_is_not_paid() -> None:
    """Nothing may be withdrawn before the chosen start month.

    REFERENCE: G4-SYNTHETIC. Start guard branch.
    """
    simulation_result = run_simulation(
        [build_test_fund()],
        build_test_settings(
            horizon_years_int=2,
            withdrawal=WithdrawalSettings(
                is_enabled_bool=True,
                start_month_index_int=12,
                mode_str=WITHDRAWAL_MODE_FIXED_STR,
                fixed_amount_float=500.0,
            ),
        ),
    )
    assert simulation_result.monthly_snapshots_list[
        11
    ].monthly_withdrawal_float == 0.0
    assert simulation_result.ending_withdrawn_float > 0.0


def test_excess_withdrawal_is_capped_and_reported_unmet() -> None:
    """Asking for more than the corpus must record a shortfall.

    REFERENCE: G4-SYNTHETIC. Depletion branch. A 1000 monthly
    request against a 100 monthly SIP exhausts the fund.
    """
    simulation_result = run_simulation(
        [build_test_fund(monthly_sip_float=100.0)],
        build_test_settings(
            horizon_years_int=3,
            withdrawal=WithdrawalSettings(
                is_enabled_bool=True,
                mode_str=WITHDRAWAL_MODE_FIXED_STR,
                fixed_amount_float=1000.0,
            ),
        ),
    )
    assert simulation_result.total_unmet_withdrawal_float > 0.0
    assert simulation_result.depletion_month_date is not None
    assert simulation_result.ending_value_float >= 0.0


def test_percent_of_corpus_withdrawal_never_depletes() -> None:
    """Taking a share of the corpus must leave something behind.

    REFERENCE: G1-ANALYTIC. Geometric decay never reaches zero.
    """
    simulation_result = run_simulation(
        [
            build_test_fund(
                monthly_sip_float=0.0,
                initial_investment_float=1000000.0,
            )
        ],
        build_test_settings(
            horizon_years_int=30,
            withdrawal=WithdrawalSettings(
                is_enabled_bool=True,
                mode_str=WITHDRAWAL_MODE_PERCENT_STR,
                portfolio_percent_float=1.0,
            ),
        ),
    )
    assert simulation_result.ending_value_float > 0.0
    assert simulation_result.total_unmet_withdrawal_float == 0.0


def test_monthly_schedule_pays_only_the_listed_months() -> None:
    """A twelve-month schedule must pay exactly its entries.

    REFERENCE: G4-SYNTHETIC. Only January carries an amount, so
    one year pays exactly one withdrawal.
    """
    schedule_list = [0.0] * 12
    schedule_list[0] = 5000.0
    simulation_result = run_simulation(
        [build_test_fund(monthly_sip_float=10000.0)],
        build_test_settings(
            horizon_years_int=1,
            withdrawal=WithdrawalSettings(
                is_enabled_bool=True,
                mode_str=WITHDRAWAL_MODE_SCHEDULE_STR,
                monthly_schedule_list=schedule_list,
            ),
        ),
    )
    paid_month_count_int = sum(
        1
        for snapshot in simulation_result.monthly_snapshots_list
        if snapshot.monthly_withdrawal_float > 0.0
    )
    assert paid_month_count_int == 1


def test_short_schedule_pays_nothing(
) -> None:
    """A schedule with fewer than twelve entries must pay zero.

    REFERENCE: G4-SYNTHETIC. Defensive branch.
    """
    simulation_result = run_simulation(
        [build_test_fund()],
        build_test_settings(
            horizon_years_int=1,
            withdrawal=WithdrawalSettings(
                is_enabled_bool=True,
                mode_str=WITHDRAWAL_MODE_SCHEDULE_STR,
                monthly_schedule_list=[1000.0, 2000.0],
            ),
        ),
    )
    assert simulation_result.ending_withdrawn_float == 0.0


def test_withdrawal_escalates_by_the_annual_change() -> None:
    """A yearly increase must lift later withdrawals.

    REFERENCE: G4-SYNTHETIC. 1000 in year one, 1100 in year two.
    """
    simulation_result = run_simulation(
        [build_test_fund(monthly_sip_float=50000.0)],
        build_test_settings(
            horizon_years_int=2,
            withdrawal=WithdrawalSettings(
                is_enabled_bool=True,
                mode_str=WITHDRAWAL_MODE_FIXED_STR,
                fixed_amount_float=1000.0,
                annual_change_percent_float=10.0,
            ),
        ),
    )
    assert simulation_result.monthly_snapshots_list[
        12
    ].requested_withdrawal_float == pytest.approx(1100.0)


def test_withdrawal_is_split_by_current_weight() -> None:
    """Each fund must fund the exit in proportion to its value.

    REFERENCE: G4-SYNTHETIC. Two identical funds each provide
    half of the requested amount.
    """
    simulation_result = run_simulation(
        [
            build_test_fund("Fund-A", 1000.0, 10.0),
            build_test_fund("Fund-B", 1000.0, 10.0),
        ],
        build_test_settings(
            horizon_years_int=3,
            withdrawal=WithdrawalSettings(
                is_enabled_bool=True,
                start_month_index_int=12,
                mode_str=WITHDRAWAL_MODE_FIXED_STR,
                fixed_amount_float=1000.0,
            ),
        ),
    )
    first_float = simulation_result.fund_outcomes_list[
        0
    ].withdrawn_amount_float
    second_float = simulation_result.fund_outcomes_list[
        1
    ].withdrawn_amount_float
    assert first_float == pytest.approx(second_float)


# ------------------------------------------------------------------
# Rebalancing
# ------------------------------------------------------------------
def test_rebalancing_off_records_no_events_and_no_tax() -> None:
    """A passive run must never trade or realize tax.

    REFERENCE: G4-SYNTHETIC. Core promise of the off switch.
    """
    simulation_result = run_simulation(
        [
            build_test_fund("Fund-A", 1000.0, 14.0),
            build_test_fund("Fund-B", 1000.0, 8.0),
        ],
        build_test_settings(horizon_years_int=10),
    )
    assert simulation_result.rebalance_events_list == []
    assert simulation_result.ending_tax_paid_float == 0.0


def test_full_liquidation_lands_exactly_on_target() -> None:
    """An exact rebalance funded from outside must hit target.

    REFERENCE: G4-SYNTHETIC. Equal SIPs give a 50/50 target.
    """
    simulation_result = run_simulation(
        [
            build_test_fund("Fund-A", 1000.0, 14.0),
            build_test_fund("Fund-B", 1000.0, 8.0),
        ],
        build_test_settings(
            horizon_years_int=5,
            rebalance=RebalanceSettings(
                is_enabled_bool=True,
                interval_months_int=12,
                method_str=REBALANCE_METHOD_FULL_STR,
                target_mode_str=REBALANCE_TARGET_SIP_SPLIT_STR,
                tax_funding_str=TAX_FUNDING_OUTSIDE_STR,
            ),
        ),
    )
    last_event = simulation_result.rebalance_events_list[-1]
    for weight_float in last_event.weights_after_dict.values():
        assert weight_float == pytest.approx(50.0, abs=1e-6)


def test_partial_rebalance_realizes_less_tax_than_full() -> None:
    """Selling only the drift must cost less tax than selling all.

    REFERENCE: G4-SYNTHETIC and real-world reasoning: a partial
    trade realizes a fraction of the unrealized gain.
    """
    tax_by_method_dict = {}
    for method_str in (
        REBALANCE_METHOD_FULL_STR,
        REBALANCE_METHOD_PARTIAL_STR,
    ):
        simulation_result = run_simulation(
            [
                build_test_fund("Fund-A", 20000.0, 14.0),
                build_test_fund("Fund-B", 20000.0, 8.0),
            ],
            build_test_settings(
                horizon_years_int=15,
                rebalance=RebalanceSettings(
                    is_enabled_bool=True,
                    interval_months_int=12,
                    method_str=method_str,
                    target_mode_str=REBALANCE_TARGET_SIP_SPLIT_STR,
                    tax_funding_str=TAX_FUNDING_PORTFOLIO_STR,
                ),
            ),
        )
        tax_by_method_dict[method_str] = (
            simulation_result.ending_tax_paid_float
        )
    assert (
        tax_by_method_dict[REBALANCE_METHOD_PARTIAL_STR]
        < tax_by_method_dict[REBALANCE_METHOD_FULL_STR]
    )


def test_tax_funded_from_outside_leaves_a_larger_corpus() -> None:
    """Paying tax from the bank must not shrink the portfolio.

    REFERENCE: G4-SYNTHETIC, and real-world: resident equity
    redemptions carry no withholding, so the corpus is untouched.
    """
    value_by_funding_dict = {}
    for funding_str in (
        TAX_FUNDING_OUTSIDE_STR,
        TAX_FUNDING_PORTFOLIO_STR,
    ):
        simulation_result = run_simulation(
            [
                build_test_fund("Fund-A", 20000.0, 14.0),
                build_test_fund("Fund-B", 20000.0, 8.0),
            ],
            build_test_settings(
                horizon_years_int=12,
                rebalance=RebalanceSettings(
                    is_enabled_bool=True,
                    interval_months_int=12,
                    method_str=REBALANCE_METHOD_FULL_STR,
                    target_mode_str=REBALANCE_TARGET_SIP_SPLIT_STR,
                    tax_funding_str=funding_str,
                ),
            ),
        )
        value_by_funding_dict[funding_str] = (
            simulation_result.ending_value_float
        )
    assert (
        value_by_funding_dict[TAX_FUNDING_OUTSIDE_STR]
        > value_by_funding_dict[TAX_FUNDING_PORTFOLIO_STR]
    )


def test_event_cap_limits_the_number_of_trades() -> None:
    """A cap of one must produce exactly one rebalance.

    REFERENCE: G4-SYNTHETIC. Cap branch of the trigger.
    """
    simulation_result = run_simulation(
        [
            build_test_fund("Fund-A", 1000.0, 14.0),
            build_test_fund("Fund-B", 1000.0, 8.0),
        ],
        build_test_settings(
            horizon_years_int=10,
            rebalance=RebalanceSettings(
                is_enabled_bool=True,
                interval_months_int=12,
                method_str=REBALANCE_METHOD_FULL_STR,
                target_mode_str=REBALANCE_TARGET_SIP_SPLIT_STR,
                maximum_events_int=1,
            ),
        ),
    )
    assert len(simulation_result.rebalance_events_list) == 1


def test_zero_interval_calendar_trigger_never_fires() -> None:
    """A non-positive interval must never trade on the calendar.

    REFERENCE: G4-SYNTHETIC. Guard branch.
    """
    simulation_result = run_simulation(
        [build_test_fund()],
        build_test_settings(
            horizon_years_int=5,
            rebalance=RebalanceSettings(
                is_enabled_bool=True,
                interval_months_int=0,
                method_str=REBALANCE_METHOD_FULL_STR,
                target_mode_str=REBALANCE_TARGET_SIP_SPLIT_STR,
            ),
        ),
    )
    assert simulation_result.rebalance_events_list == []


def test_drift_band_trigger_fires_without_a_calendar() -> None:
    """A band trigger must trade purely on drift.

    REFERENCE: G4-SYNTHETIC. Two funds at 14 and 4 percent drift
    past five points well inside the horizon.
    """
    simulation_result = run_simulation(
        [
            build_test_fund("Fund-A", 1000.0, 14.0),
            build_test_fund("Fund-B", 1000.0, 4.0),
        ],
        build_test_settings(
            horizon_years_int=10,
            rebalance=RebalanceSettings(
                is_enabled_bool=True,
                interval_months_int=0,
                method_str=REBALANCE_METHOD_PARTIAL_STR,
                target_mode_str=REBALANCE_TARGET_SIP_SPLIT_STR,
                trigger_str=REBALANCE_TRIGGER_BAND_STR,
                drift_band_percent_float=5.0,
            ),
        ),
    )
    assert len(simulation_result.rebalance_events_list) > 0
    for rebalance_event in simulation_result.rebalance_events_list:
        assert (
            rebalance_event.trigger_reason_str
            == REBALANCE_TRIGGER_BAND_STR
        )


def test_zero_band_width_never_fires() -> None:
    """A band of zero must disable the band trigger.

    REFERENCE: G4-SYNTHETIC. Guard branch.
    """
    simulation_result = run_simulation(
        [
            build_test_fund("Fund-A", 1000.0, 14.0),
            build_test_fund("Fund-B", 1000.0, 4.0),
        ],
        build_test_settings(
            horizon_years_int=10,
            rebalance=RebalanceSettings(
                is_enabled_bool=True,
                interval_months_int=0,
                method_str=REBALANCE_METHOD_PARTIAL_STR,
                target_mode_str=REBALANCE_TARGET_SIP_SPLIT_STR,
                trigger_str=REBALANCE_TRIGGER_BAND_STR,
                drift_band_percent_float=0.0,
            ),
        ),
    )
    assert simulation_result.rebalance_events_list == []


def test_calendar_and_band_trades_less_than_calendar_alone(
) -> None:
    """Requiring both conditions must reduce the trade count.

    REFERENCE: G4-SYNTHETIC. Intersection of two conditions can
    never be larger than either one.
    """
    event_count_by_trigger_dict = {}
    for trigger_str in (
        REBALANCE_TRIGGER_CALENDAR_STR,
        REBALANCE_TRIGGER_BOTH_STR,
    ):
        simulation_result = run_simulation(
            [
                build_test_fund("Fund-A", 1000.0, 13.0),
                build_test_fund("Fund-B", 1000.0, 11.0),
            ],
            build_test_settings(
                horizon_years_int=10,
                rebalance=RebalanceSettings(
                    is_enabled_bool=True,
                    interval_months_int=12,
                    method_str=REBALANCE_METHOD_PARTIAL_STR,
                    target_mode_str=REBALANCE_TARGET_SIP_SPLIT_STR,
                    trigger_str=trigger_str,
                    drift_band_percent_float=5.0,
                ),
            ),
        )
        event_count_by_trigger_dict[trigger_str] = len(
            simulation_result.rebalance_events_list
        )
    assert (
        event_count_by_trigger_dict[REBALANCE_TRIGGER_BOTH_STR]
        <= event_count_by_trigger_dict[
            REBALANCE_TRIGGER_CALENDAR_STR
        ]
    )


def test_target_column_mode_uses_the_declared_weights() -> None:
    """Declared targets must override the instalment split.

    REFERENCE: G4-SYNTHETIC. A 70/30 declared target must appear
    in the post-trade weights.
    """
    simulation_result = run_simulation(
        [
            build_test_fund(
                "Fund-A", 1000.0, 14.0,
                target_allocation_percent_float=70.0,
            ),
            build_test_fund(
                "Fund-B", 1000.0, 8.0,
                target_allocation_percent_float=30.0,
            ),
        ],
        build_test_settings(
            horizon_years_int=5,
            rebalance=RebalanceSettings(
                is_enabled_bool=True,
                interval_months_int=12,
                method_str=REBALANCE_METHOD_FULL_STR,
                target_mode_str=REBALANCE_TARGET_COLUMN_STR,
                tax_funding_str=TAX_FUNDING_OUTSIDE_STR,
            ),
        ),
    )
    last_event = simulation_result.rebalance_events_list[-1]
    assert last_event.weights_after_dict["Fund-A"] == pytest.approx(
        70.0, abs=1e-6
    )


def test_contribution_steering_costs_no_tax() -> None:
    """Cash-flow rebalancing must never sell anything.

    REFERENCE: G4-SYNTHETIC, and real-world: directing new money
    is not a transfer, so no capital gain arises.
    """
    simulation_result = run_simulation(
        [
            build_test_fund("Fund-A", 1000.0, 14.0),
            build_test_fund("Fund-B", 1000.0, 4.0),
        ],
        build_test_settings(
            horizon_years_int=10,
            rebalance=RebalanceSettings(
                use_contribution_steering_bool=True,
                target_mode_str=REBALANCE_TARGET_SIP_SPLIT_STR,
            ),
        ),
    )
    assert simulation_result.ending_tax_paid_float == 0.0
    assert simulation_result.rebalance_events_list == []


def test_contribution_steering_reduces_drift() -> None:
    """Steering new money must keep weights closer to target.

    REFERENCE: G4-SYNTHETIC. Compares final drift with and
    without steering, same funds and horizon.
    """
    drift_by_mode_dict = {}
    for is_steering_bool in (False, True):
        simulation_result = run_simulation(
            [
                build_test_fund("Fund-A", 1000.0, 14.0),
                build_test_fund("Fund-B", 1000.0, 4.0),
            ],
            build_test_settings(
                horizon_years_int=10,
                rebalance=RebalanceSettings(
                    use_contribution_steering_bool=is_steering_bool,
                    target_mode_str=REBALANCE_TARGET_SIP_SPLIT_STR,
                ),
            ),
        )
        weight_dict = calculate_weight_dict(
            {
                fund_outcome.name_str: (
                    fund_outcome.ending_value_float
                )
                for fund_outcome in (
                    simulation_result.fund_outcomes_list
                )
            }
        )
        drift_by_mode_dict[is_steering_bool] = abs(
            weight_dict["Fund-A"] - 50.0
        )
    assert drift_by_mode_dict[True] < drift_by_mode_dict[False]


# ------------------------------------------------------------------
# Accounting invariants
# ------------------------------------------------------------------
def test_internal_transfers_never_raise_invested_principal(
) -> None:
    """Rebalancing must not inflate the money the investor paid.

    REFERENCE: G4-SYNTHETIC. 10 years of 1000 per month across
    two funds is exactly 240000 of external principal.
    """
    simulation_result = run_simulation(
        [
            build_test_fund("Fund-A", 1000.0, 14.0),
            build_test_fund("Fund-B", 1000.0, 8.0),
        ],
        build_test_settings(
            horizon_years_int=10,
            rebalance=RebalanceSettings(
                is_enabled_bool=True,
                interval_months_int=12,
                method_str=REBALANCE_METHOD_FULL_STR,
                target_mode_str=REBALANCE_TARGET_SIP_SPLIT_STR,
            ),
        ),
    )
    assert simulation_result.ending_invested_float == pytest.approx(
        240000.0
    )


def test_cost_basis_plus_unrealized_equals_value() -> None:
    """Value must split cleanly into basis and unrealized gain.

    REFERENCE: G1-ANALYTIC. Definition of unrealized gain.
    """
    simulation_result = run_simulation(
        [build_test_fund()],
        build_test_settings(horizon_years_int=8),
    )
    fund_outcome = simulation_result.fund_outcomes_list[0]
    assert (
        fund_outcome.cost_basis_float
        + fund_outcome.unrealized_gain_float
    ) == pytest.approx(fund_outcome.ending_value_float)


def test_final_liquidation_tax_reduces_the_spendable_corpus(
) -> None:
    """Post-tax value must be below the paper value.

    REFERENCE: G2-STATUTORY. Unrealized gains are taxable on exit.
    """
    simulation_result = run_simulation(
        [build_test_fund(monthly_sip_float=25000.0)],
        build_test_settings(
            horizon_years_int=20,
            tax=TaxSettings(
                exemption_level_str=EXEMPTION_LEVEL_PORTFOLIO_STR,
                portfolio_exemption_amount_float=(
                    STATUTORY_EQUITY_EXEMPTION_RUPEES_FLOAT
                ),
                apply_final_liquidation_tax_bool=True,
            ),
        ),
    )
    assert simulation_result.final_liquidation_tax_float > 0.0
    assert (
        simulation_result.post_tax_ending_value_float
        < simulation_result.ending_value_float
    )


def test_final_liquidation_tax_is_zero_when_disabled() -> None:
    """The exit tax must be reported only when it is requested.

    REFERENCE: G4-SYNTHETIC. Feature switch branch.
    """
    simulation_result = run_simulation(
        [build_test_fund(monthly_sip_float=25000.0)],
        build_test_settings(horizon_years_int=20),
    )
    assert simulation_result.final_liquidation_tax_float == 0.0
    assert (
        simulation_result.post_tax_ending_value_float
        == simulation_result.ending_value_float
    )


def test_monthly_flows_reconcile_with_cumulative_totals() -> None:
    """Summing monthly flows must equal the reported totals.

    REFERENCE: G1-ANALYTIC. Accounting identity across the run.
    """
    simulation_result = run_simulation(
        [
            build_test_fund("Fund-A", 5000.0, 12.0),
            build_test_fund("Fund-B", 3000.0, 9.0),
        ],
        build_test_settings(
            horizon_years_int=12,
            withdrawal=WithdrawalSettings(
                is_enabled_bool=True,
                start_month_index_int=60,
                mode_str=WITHDRAWAL_MODE_FIXED_STR,
                fixed_amount_float=4000.0,
            ),
        ),
    )
    contributed_total_float = sum(
        snapshot.monthly_sip_float
        for snapshot in simulation_result.monthly_snapshots_list
    )
    withdrawn_total_float = sum(
        snapshot.monthly_withdrawal_float
        for snapshot in simulation_result.monthly_snapshots_list
    )
    assert contributed_total_float == pytest.approx(
        simulation_result.ending_invested_float
    )
    assert withdrawn_total_float == pytest.approx(
        simulation_result.ending_withdrawn_float
    )


def test_weight_helper_handles_an_empty_portfolio() -> None:
    """Weights of an empty portfolio must be zero, not undefined.

    REFERENCE: G4-SYNTHETIC. Division-by-zero guard.
    """
    assert calculate_weight_dict({"A": 0.0, "B": 0.0}) == {
        "A": 0.0,
        "B": 0.0,
    }


# ------------------------------------------------------------------
# Dated one-off contributions
# ------------------------------------------------------------------
def build_one_off_result(
    month_index_int: int,
    amount_float: float = 100000.0,
    horizon_years_int: int = 10,
):
    """Run a pure one-off plan with no instalment and no tax.

    REFERENCE: harness only. Isolates the dated contribution so
    nothing else can move the ending value.
    """
    return PortfolioSimulator(
        [build_test_fund(monthly_sip_float=0.0)],
        build_test_settings(
            horizon_years_int=horizon_years_int,
            one_off_contributions_list=[
                OneOffContribution(month_index_int, amount_float)
            ],
        ),
    ).run()


def test_a_one_off_at_month_zero_equals_an_opening_lump_sum(
) -> None:
    """The new path must agree with the already-verified one.

    REFERENCE: G3-CROSSCHECK. A one-off dated to month zero and a
    fund's opening lump sum are the same event described two ways,
    so they must produce identical corpora to the paisa.
    """
    lump_sum_result = PortfolioSimulator(
        [
            build_test_fund(
                monthly_sip_float=0.0,
                initial_investment_float=100000.0,
            )
        ],
        build_test_settings(),
    ).run()
    one_off_result = build_one_off_result(0)
    assert (
        one_off_result.ending_value_float
        == pytest.approx(lump_sum_result.ending_value_float)
    )
    assert (
        one_off_result.ending_invested_float
        == pytest.approx(lump_sum_result.ending_invested_float)
    )


@pytest.mark.parametrize("month_index_int", [0, 1, 12, 60, 96, 119])
def test_a_one_off_compounds_only_from_the_month_it_arrived(
    month_index_int: int,
) -> None:
    """This is the whole point of dating a contribution.

    REFERENCE: G1-ANALYTIC. Money invested at month N has exactly
    N fewer months of growth than the same money invested at month
    zero, so the ratio of the two corpora is (1+m)^-N with m the
    effective monthly rate derived from the annual return.
    """
    monthly_rate_float = 1.12 ** (1 / 12) - 1
    at_start_float = build_one_off_result(0).ending_value_float
    dated_float = build_one_off_result(
        month_index_int
    ).ending_value_float
    assert dated_float == pytest.approx(
        at_start_float
        / (1.0 + monthly_rate_float) ** month_index_int
    )


def test_a_one_off_is_principal_not_gain() -> None:
    """A bonus you invest is money you paid in, not profit.

    REFERENCE: G4-SYNTHETIC. Misclassifying it would overstate the
    gain and corrupt every return figure derived from it.
    """
    result = build_one_off_result(24, amount_float=50000.0)
    assert result.ending_invested_float == pytest.approx(50000.0)
    assert result.ending_value_float > 50000.0


def test_several_one_offs_can_share_one_month() -> None:
    """Multiple events may land on the same point of a timeline.

    REFERENCE: G4-SYNTHETIC. Two 25,000 contributions in month 12
    must equal one 50,000 contribution in month 12.
    """
    split_result = PortfolioSimulator(
        [build_test_fund(monthly_sip_float=0.0)],
        build_test_settings(
            one_off_contributions_list=[
                OneOffContribution(12, 25000.0),
                OneOffContribution(12, 25000.0),
            ]
        ),
    ).run()
    single_result = build_one_off_result(12, amount_float=50000.0)
    assert split_result.ending_value_float == pytest.approx(
        single_result.ending_value_float
    )


def test_an_unnamed_one_off_splits_by_target_allocation() -> None:
    """Adding to "the portfolio" must respect the target weights.

    REFERENCE: G4-SYNTHETIC. A 75/25 portfolio receiving 100,000
    must book 75,000 and 25,000, so each fund's own principal
    reflects what it actually received.
    """
    result = PortfolioSimulator(
        [
            build_test_fund(
                name_str="Equity",
                monthly_sip_float=0.0,
                target_allocation_percent_float=75.0,
            ),
            build_test_fund(
                name_str="Debt",
                monthly_sip_float=0.0,
                target_allocation_percent_float=25.0,
            ),
        ],
        build_test_settings(
            one_off_contributions_list=[
                OneOffContribution(0, 100000.0)
            ]
        ),
    ).run()
    invested_dict = {
        outcome.name_str: outcome.invested_amount_float
        for outcome in result.fund_outcomes_list
    }
    assert invested_dict["Equity"] == pytest.approx(75000.0)
    assert invested_dict["Debt"] == pytest.approx(25000.0)


def test_a_named_one_off_goes_only_to_that_fund() -> None:
    """Naming a fund must override the allocation split.

    REFERENCE: G4-SYNTHETIC. "I put my bonus into the equity fund"
    is a different instruction from "I added it to my portfolio".
    """
    result = PortfolioSimulator(
        [
            build_test_fund(
                name_str="Equity",
                monthly_sip_float=0.0,
                target_allocation_percent_float=50.0,
            ),
            build_test_fund(
                name_str="Debt",
                monthly_sip_float=0.0,
                target_allocation_percent_float=50.0,
            ),
        ],
        build_test_settings(
            one_off_contributions_list=[
                OneOffContribution(0, 100000.0, "Equity")
            ]
        ),
    ).run()
    invested_dict = {
        outcome.name_str: outcome.invested_amount_float
        for outcome in result.fund_outcomes_list
    }
    assert invested_dict["Equity"] == pytest.approx(100000.0)
    assert invested_dict["Debt"] == pytest.approx(0.0)


def test_a_one_off_naming_an_unknown_fund_invests_nothing() -> None:
    """Money must never land somewhere the user did not name.

    REFERENCE: G4-SYNTHETIC. Silently redirecting it would be
    worse than doing nothing, because the total would still look
    right while the allocation was wrong.
    """
    result = PortfolioSimulator(
        [build_test_fund(monthly_sip_float=0.0)],
        build_test_settings(
            one_off_contributions_list=[
                OneOffContribution(0, 100000.0, "Nonexistent")
            ]
        ),
    ).run()
    assert result.ending_invested_float == pytest.approx(0.0)


def test_one_off_cash_flows_reach_the_money_weighted_return(
) -> None:
    """A contribution the XIRR cannot see would inflate the rate.

    REFERENCE: G4-SYNTHETIC. A plan funded only by a month-zero
    one-off is a plain lump sum, so its money-weighted return must
    come back as the fund's own net return of 12%.
    """
    result = build_one_off_result(0)
    assert calculate_pre_tax_xirr_percent_float(
        result, True
    ) == pytest.approx(12.0, abs=0.01)


# ------------------------------------------------------------------
# Dated instalment overrides
# ------------------------------------------------------------------
def run_override_plan(
    override_list: list,
    stepup: StepUpSettings = None,
    horizon_years_int: int = 10,
):
    """Run a plain 1,000 a month plan carrying overrides.

    REFERENCE: harness only. No tax, no pause, no withdrawal, so
    the invested total is a pure function of the instalments.
    """
    return PortfolioSimulator(
        [build_test_fund()],
        build_test_settings(
            horizon_years_int=horizon_years_int,
            stepup=stepup,
            instalment_override_list=override_list,
        ),
    ).run()


def test_an_override_at_month_zero_equals_a_plain_instalment(
) -> None:
    """Overriding from the first month is just a different SIP.

    REFERENCE: G3-CROSSCHECK. Anchors the new path against the
    already-verified plain instalment path.
    """
    override_result = run_override_plan(
        [InstalmentOverride(0, 2500.0)]
    )
    plain_result = PortfolioSimulator(
        [build_test_fund(monthly_sip_float=2500.0)],
        build_test_settings(),
    ).run()
    assert override_result.ending_value_float == pytest.approx(
        plain_result.ending_value_float
    )


def test_an_override_changes_the_instalment_from_its_month(
) -> None:
    """A raise in year six must not be backdated to year one.

    REFERENCE: G4-SYNTHETIC. Sixty months at 1,000 then sixty at
    2,000 is 60,000 + 120,000 = 180,000 of principal.
    """
    result = run_override_plan([InstalmentOverride(60, 2000.0)])
    assert result.ending_invested_float == pytest.approx(180000.0)


def test_an_override_to_zero_stops_contributions() -> None:
    """Setting the amount to nothing must stop the SIP.

    REFERENCE: G4-SYNTHETIC. Sixty months at 1,000 and nothing
    after leaves exactly 60,000 of principal.
    """
    result = run_override_plan([InstalmentOverride(60, 0.0)])
    assert result.ending_invested_float == pytest.approx(60000.0)


def test_the_latest_override_before_this_month_wins() -> None:
    """Several changes must apply in calendar order.

    REFERENCE: G4-SYNTHETIC. 1,000 for 24 months, 2,000 for the
    next 36, then 500 for the last 60: 24,000 + 72,000 + 30,000.
    """
    result = run_override_plan(
        [
            InstalmentOverride(60, 500.0),
            InstalmentOverride(24, 2000.0),
        ]
    )
    assert result.ending_invested_float == pytest.approx(126000.0)


def test_an_override_resets_the_step_up_clock() -> None:
    """Saying "my SIP is now X" must mean X, not X stepped up.

    REFERENCE: G4-SYNTHETIC. With a 10% yearly step-up running
    from the start, an override to 2,000 in month 60 must invest
    exactly 2,000 that month - not 2,000 x 1.1^5.
    """
    result = run_override_plan(
        [InstalmentOverride(60, 2000.0)],
        stepup=StepUpSettings(
            mode_str=STEPUP_MODE_GLOBAL_STR,
            global_stepup_percent_float=10.0,
        ),
    )
    assert result.monthly_snapshots_list[
        60
    ].monthly_sip_float == pytest.approx(2000.0)


def test_step_up_then_grows_from_the_overridden_amount() -> None:
    """Escalation must continue, starting from the new figure.

    REFERENCE: G4-SYNTHETIC. A year after the override the 10%
    step-up lifts 2,000 to 2,200.
    """
    result = run_override_plan(
        [InstalmentOverride(60, 2000.0)],
        stepup=StepUpSettings(
            mode_str=STEPUP_MODE_GLOBAL_STR,
            global_stepup_percent_float=10.0,
        ),
    )
    assert result.monthly_snapshots_list[
        72
    ].monthly_sip_float == pytest.approx(2200.0)


def test_an_override_can_name_a_single_fund() -> None:
    """Changing one fund's SIP must leave the others alone.

    REFERENCE: G4-SYNTHETIC. Fund-A doubles from month 60, Fund-B
    keeps its 1,000 throughout: 180,000 and 120,000 of principal.
    """
    result = PortfolioSimulator(
        [
            build_test_fund(name_str="Fund-A"),
            build_test_fund(name_str="Fund-B"),
        ],
        build_test_settings(
            instalment_override_list=[
                InstalmentOverride(60, 2000.0, "Fund-A")
            ]
        ),
    ).run()
    invested_dict = {
        outcome.name_str: outcome.invested_amount_float
        for outcome in result.fund_outcomes_list
    }
    assert invested_dict["Fund-A"] == pytest.approx(180000.0)
    assert invested_dict["Fund-B"] == pytest.approx(120000.0)


def test_a_pause_still_beats_an_override() -> None:
    """A paused month invests nothing whatever the amount says.

    REFERENCE: G4-SYNTHETIC. The pause is checked first, so an
    override inside a pause window cannot revive the instalment.
    """
    result = PortfolioSimulator(
        [build_test_fund()],
        build_test_settings(
            pauses=PauseSettings(
                pause_ranges_list=[
                    PauseRange(
                        date(2031, 1, 1),
                        date(2031, 12, 1),
                        PAUSE_SCOPE_SIP_STR,
                    )
                ]
            ),
            instalment_override_list=[
                InstalmentOverride(60, 9999.0)
            ],
        ),
    ).run()
    assert result.monthly_snapshots_list[
        60
    ].monthly_sip_float == pytest.approx(0.0)
