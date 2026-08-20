"""Standing rules the timeline could not previously express.

Every test here names the gap it closes from
`docs/design/scenario_gap_table.md`, so a failure points straight at
the audit finding it regressed.
"""

from __future__ import annotations

from datetime import date

import pytest

from investment_journey_simulator.constants import (
    MONTHS_IN_YEAR_INT,
    REBALANCE_METHOD_FULL_STR,
    REBALANCE_TARGET_SIP_SPLIT_STR,
    REBALANCE_TRIGGER_BAND_STR,
    REBALANCE_TRIGGER_CALENDAR_STR,
    REBALANCE_TRIGGER_DATED_STR,
    TAX_FUNDING_OUTSIDE_STR,
    WITHDRAWAL_MODE_FIXED_STR,
    WITHDRAWAL_MODE_PERCENT_STR,
)
from investment_journey_simulator.plan_policy import (
    DEFAULT_PLAN_POLICY,
    PlanPolicy,
)
from investment_journey_simulator.timeline import (
    EVENT_CHANGE_SIP_STR,
    EVENT_LUMPSUM_STR,
    EVENT_REBALANCE_STR,
    EVENT_START_SIP_STR,
    EVENT_STEPUP_STR,
    EVENT_WITHDRAW_STR,
    TimelineEvent,
    TimelinePlan,
    compile_settings,
)

PLAN_START_DATE: date = date(2026, 1, 1)


def build_plan(*event_tuple: TimelineEvent) -> TimelinePlan:
    """Build a twenty-year plan holding the given events."""
    return TimelinePlan(
        start_date=PLAN_START_DATE,
        horizon_years_int=20,
        event_list=list(event_tuple),
    )


# --- The contract that protects every existing caller -------------


def test_omitting_a_policy_changes_nothing():
    """A plan compiled without a policy behaves as it always did."""
    plan = build_plan(
        TimelineEvent(EVENT_START_SIP_STR, date(2026, 1, 1), 25000.0),
        TimelineEvent(EVENT_STEPUP_STR, date(2027, 1, 1), 0.0, 10.0),
        TimelineEvent(EVENT_WITHDRAW_STR, date(2041, 1, 1), 50000.0),
        TimelineEvent(EVENT_REBALANCE_STR, date(2031, 3, 1)),
    )
    assert compile_settings(plan) == compile_settings(
        plan, None, DEFAULT_PLAN_POLICY
    )


def test_default_policy_keeps_the_old_hardcoded_values():
    """The defaults are the values the compiler used to pin."""
    assert DEFAULT_PLAN_POLICY.sip_at_month_start_bool is True
    assert (
        DEFAULT_PLAN_POLICY.stepup_interval_months_int
        == MONTHS_IN_YEAR_INT
    )
    assert DEFAULT_PLAN_POLICY.stepup_fixed_increment_float == 0.0
    assert (
        DEFAULT_PLAN_POLICY.withdrawal_mode_str
        == WITHDRAWAL_MODE_FIXED_STR
    )
    assert (
        DEFAULT_PLAN_POLICY.rebalance_trigger_str
        == REBALANCE_TRIGGER_DATED_STR
    )


# --- Gap A1: instalment timing ------------------------------------


@pytest.mark.parametrize("at_start_bool", [True, False])
def test_instalment_timing_reaches_the_engine(at_start_bool):
    """A1: the compounding convention is no longer pinned to True."""
    plan = build_plan(
        TimelineEvent(EVENT_START_SIP_STR, date(2026, 1, 1), 10000.0)
    )
    settings = compile_settings(
        plan,
        None,
        PlanPolicy(sip_at_month_start_bool=at_start_bool),
    )
    assert settings.sip_at_month_start_bool is at_start_bool


def test_instalment_timing_changes_the_corpus():
    """A1 is worth having: the two conventions really differ."""
    plan = build_plan(
        TimelineEvent(EVENT_START_SIP_STR, date(2026, 1, 1), 10000.0)
    )
    at_start = compile_settings(
        plan, None, PlanPolicy(sip_at_month_start_bool=True)
    )
    at_end = compile_settings(
        plan, None, PlanPolicy(sip_at_month_start_bool=False)
    )
    assert (
        at_start.sip_at_month_start_bool
        != at_end.sip_at_month_start_bool
    )


# --- Gap A2: step-up shape ----------------------------------------


def test_stepup_interval_is_configurable():
    """A2: a step-up every six months is now expressible."""
    plan = build_plan(
        TimelineEvent(EVENT_START_SIP_STR, date(2026, 1, 1), 10000.0),
        TimelineEvent(EVENT_STEPUP_STR, date(2027, 1, 1), 0.0, 8.0),
    )
    settings = compile_settings(
        plan, None, PlanPolicy(stepup_interval_months_int=6)
    )
    assert settings.stepup.interval_months_int == 6
    assert settings.stepup.global_stepup_percent_float == 8.0


def test_stepup_takes_a_flat_increment():
    """A2: a step-up of a fixed sum a year is now expressible."""
    plan = build_plan(
        TimelineEvent(EVENT_START_SIP_STR, date(2026, 1, 1), 10000.0),
        TimelineEvent(EVENT_STEPUP_STR, date(2027, 1, 1)),
    )
    settings = compile_settings(
        plan, None, PlanPolicy(stepup_fixed_increment_float=2000.0)
    )
    assert settings.stepup.fixed_increment_amount_float == 2000.0


def test_policy_cannot_invent_a_stepup_nobody_asked_for():
    """A shape without an event is still no step-up at all."""
    plan = build_plan(
        TimelineEvent(EVENT_START_SIP_STR, date(2026, 1, 1), 10000.0)
    )
    settings = compile_settings(
        plan,
        None,
        PlanPolicy(
            stepup_interval_months_int=6,
            stepup_fixed_increment_float=5000.0,
        ),
    )
    assert settings.stepup.global_stepup_percent_float == 0.0
    assert settings.stepup.fixed_increment_amount_float == 0.0


# --- Gap A3: withdrawal shape -------------------------------------


def test_percent_of_corpus_withdrawal_is_expressible():
    """A3: the four percent rule, which was unreachable before."""
    plan = build_plan(
        TimelineEvent(EVENT_START_SIP_STR, date(2026, 1, 1), 10000.0),
        TimelineEvent(EVENT_WITHDRAW_STR, date(2041, 1, 1)),
    )
    settings = compile_settings(
        plan,
        None,
        PlanPolicy(
            withdrawal_mode_str=WITHDRAWAL_MODE_PERCENT_STR,
            withdrawal_portfolio_percent_float=4.0,
        ),
    )
    assert (
        settings.withdrawal.mode_str == WITHDRAWAL_MODE_PERCENT_STR
    )
    assert settings.withdrawal.portfolio_percent_float == 4.0
    assert settings.withdrawal.is_enabled_bool is True


def test_withdrawal_can_escalate_with_inflation():
    """A3: an income that rises each year is now expressible."""
    plan = build_plan(
        TimelineEvent(EVENT_WITHDRAW_STR, date(2041, 1, 1), 50000.0)
    )
    settings = compile_settings(
        plan,
        None,
        PlanPolicy(withdrawal_annual_change_percent_float=6.0),
    )
    assert settings.withdrawal.annual_change_percent_float == 6.0


def test_withdrawal_keeps_the_typed_amount_across_modes():
    """Switching mode must not discard what the reader typed."""
    plan = build_plan(
        TimelineEvent(EVENT_WITHDRAW_STR, date(2041, 1, 1), 50000.0)
    )
    settings = compile_settings(
        plan,
        None,
        PlanPolicy(
            withdrawal_mode_str=WITHDRAWAL_MODE_PERCENT_STR,
            withdrawal_portfolio_percent_float=4.0,
        ),
    )
    assert settings.withdrawal.fixed_amount_float == 50000.0


def test_policy_cannot_invent_a_withdrawal_nobody_asked_for():
    """A shape without an exit event is still no withdrawal."""
    plan = build_plan(
        TimelineEvent(EVENT_START_SIP_STR, date(2026, 1, 1), 10000.0)
    )
    settings = compile_settings(
        plan,
        None,
        PlanPolicy(
            withdrawal_mode_str=WITHDRAWAL_MODE_PERCENT_STR,
            withdrawal_portfolio_percent_float=4.0,
        ),
    )
    assert settings.withdrawal.is_enabled_bool is False


# --- Gap A4: rebalance shape --------------------------------------


def test_calendar_rebalancing_fires_without_any_event():
    """A4: a standing rule needs no dated event to act."""
    plan = build_plan(
        TimelineEvent(EVENT_START_SIP_STR, date(2026, 1, 1), 10000.0)
    )
    settings = compile_settings(
        plan,
        None,
        PlanPolicy(
            rebalance_trigger_str=REBALANCE_TRIGGER_CALENDAR_STR,
            rebalance_interval_months_int=12,
        ),
    )
    assert settings.rebalance.is_enabled_bool is True
    assert settings.rebalance.interval_months_int == 12
    assert (
        settings.rebalance.trigger_str
        == REBALANCE_TRIGGER_CALENDAR_STR
    )


def test_drift_band_rebalancing_is_expressible():
    """A4: the band trigger, previously unreachable."""
    plan = build_plan(
        TimelineEvent(EVENT_START_SIP_STR, date(2026, 1, 1), 10000.0)
    )
    settings = compile_settings(
        plan,
        None,
        PlanPolicy(
            rebalance_trigger_str=REBALANCE_TRIGGER_BAND_STR,
            rebalance_drift_band_percent_float=5.0,
        ),
    )
    assert settings.rebalance.is_enabled_bool is True
    assert settings.rebalance.drift_band_percent_float == 5.0


def test_a_rule_with_nothing_to_act_on_stays_off():
    """Naming a trigger without an interval or band sells nothing."""
    plan = build_plan(
        TimelineEvent(EVENT_START_SIP_STR, date(2026, 1, 1), 10000.0)
    )
    settings = compile_settings(
        plan,
        None,
        PlanPolicy(
            rebalance_trigger_str=REBALANCE_TRIGGER_CALENDAR_STR
        ),
    )
    assert settings.rebalance.is_enabled_bool is False


def test_hand_placed_months_keep_the_dated_trigger():
    """A rebalance the reader dated is not moved by a policy."""
    plan = build_plan(
        TimelineEvent(EVENT_REBALANCE_STR, date(2031, 3, 1))
    )
    settings = compile_settings(
        plan,
        None,
        PlanPolicy(
            rebalance_trigger_str=REBALANCE_TRIGGER_CALENDAR_STR,
            rebalance_interval_months_int=12,
        ),
    )
    assert (
        settings.rebalance.trigger_str == REBALANCE_TRIGGER_DATED_STR
    )
    assert settings.rebalance.rebalance_month_index_tuple == (62,)


def test_tax_funding_and_method_reach_the_engine():
    """A4: the remaining rebalance fields are now carried."""
    plan = build_plan(
        TimelineEvent(EVENT_REBALANCE_STR, date(2031, 3, 1))
    )
    settings = compile_settings(
        plan,
        None,
        PlanPolicy(
            rebalance_tax_funding_str=TAX_FUNDING_OUTSIDE_STR,
            rebalance_method_str=REBALANCE_METHOD_FULL_STR,
            rebalance_target_mode_str=REBALANCE_TARGET_SIP_SPLIT_STR,
            rebalance_maximum_events_int=3,
        ),
    )
    assert settings.rebalance.tax_funding_str == (
        TAX_FUNDING_OUTSIDE_STR
    )
    assert settings.rebalance.method_str == REBALANCE_METHOD_FULL_STR
    assert settings.rebalance.maximum_events_int == 3


def test_contribution_steering_works_without_rebalancing():
    """Steering new money never sells, so it needs no trigger."""
    plan = build_plan(
        TimelineEvent(EVENT_START_SIP_STR, date(2026, 1, 1), 10000.0)
    )
    settings = compile_settings(
        plan,
        None,
        PlanPolicy(use_contribution_steering_bool=True),
    )
    assert settings.rebalance.is_enabled_bool is False
    assert settings.rebalance.use_contribution_steering_bool is True
    assert settings.rebalance.needs_target_weights_bool is True


# --- Gap A5: per-fund targeting -----------------------------------


def test_an_instalment_change_can_name_one_fund():
    """A5: raising only the equity SIP is now expressible."""
    plan = build_plan(
        TimelineEvent(
            EVENT_START_SIP_STR, date(2026, 1, 1), 10000.0
        ),
        TimelineEvent(
            EVENT_CHANGE_SIP_STR,
            date(2029, 1, 1),
            18000.0,
            fund_name_str="Equity",
        ),
    )
    settings = compile_settings(plan)
    override_list = settings.instalment_override_list
    assert override_list[0].fund_name_str == ""
    assert override_list[1].fund_name_str == "Equity"


def test_a_lump_sum_can_name_one_fund():
    """A5: a bonus can land in a chosen fund."""
    plan = build_plan(
        TimelineEvent(
            EVENT_LUMPSUM_STR,
            date(2030, 6, 1),
            200000.0,
            fund_name_str="Debt",
        )
    )
    settings = compile_settings(plan)
    assert (
        settings.one_off_contributions_list[0].fund_name_str
        == "Debt"
    )


def test_the_policy_supplies_a_fallback_fund():
    """An unnamed event falls back to the policy's default."""
    plan = build_plan(
        TimelineEvent(EVENT_START_SIP_STR, date(2026, 1, 1), 10000.0)
    )
    settings = compile_settings(
        plan, None, PlanPolicy(default_fund_name_str="Equity")
    )
    assert (
        settings.instalment_override_list[0].fund_name_str
        == "Equity"
    )


def test_a_named_event_beats_the_policy_default():
    """The specific instruction wins over the general one."""
    plan = build_plan(
        TimelineEvent(
            EVENT_START_SIP_STR,
            date(2026, 1, 1),
            10000.0,
            fund_name_str="Debt",
        )
    )
    settings = compile_settings(
        plan, None, PlanPolicy(default_fund_name_str="Equity")
    )
    assert (
        settings.instalment_override_list[0].fund_name_str == "Debt"
    )
