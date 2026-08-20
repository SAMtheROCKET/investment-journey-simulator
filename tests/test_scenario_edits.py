"""Named edits to a scenario, shared by Quick and Guided.

These exist so two screens asking the same question in different
words produce the identical scenario. The tests are mostly about
that: idempotence, and not leaving contradictory events behind.
"""

from __future__ import annotations

from datetime import date

import pytest

from conftest import build_test_fund
from investment_journey_simulator.plan_scenario import (
    AMOUNTS_SOURCE_TIMELINE_STR,
    PlanScenario,
    compile_scenario,
)
from investment_journey_simulator.scenario_edits import (
    build_named_copy,
    read_expected_return_float,
    read_monthly_contribution_float,
    set_currency_code,
    set_expected_return,
    set_horizon_years,
    set_inflation_percent,
    set_monthly_contribution,
    set_scenario_name,
    set_start_date,
)
from investment_journey_simulator.timeline import (
    EVENT_CHANGE_SIP_STR,
    EVENT_SETS_INSTALMENT_TUPLE,
    EVENT_START_SIP_STR,
    TimelineEvent,
    TimelinePlan,
)

PLAN_START_DATE: date = date(2026, 1, 1)


def build_scenario(*event_tuple: TimelineEvent) -> PlanScenario:
    """Build a twenty-year scenario with one equity fund."""
    return PlanScenario(
        plan=TimelinePlan(
            start_date=PLAN_START_DATE,
            horizon_years_int=20,
            event_list=list(event_tuple),
        ),
        fund_list=[build_test_fund(name_str="Equity")],
    )


# --- The contribution, which two screens both ask about -----------


def test_setting_the_contribution_adds_one_opening_event():
    """A fresh plan gains exactly one instalment event."""
    updated = set_monthly_contribution(build_scenario(), 25000.0)
    opening_list = [
        event
        for event in updated.plan.event_list
        if event.event_type_str in EVENT_SETS_INSTALMENT_TUPLE
    ]
    assert len(opening_list) == 1
    assert opening_list[0].amount_float == 25000.0
    assert opening_list[0].event_date == PLAN_START_DATE


def test_setting_it_twice_does_not_leave_two_events():
    """Asking the same question twice must not contradict itself."""
    once = set_monthly_contribution(build_scenario(), 25000.0)
    twice = set_monthly_contribution(once, 30000.0)
    opening_list = [
        event
        for event in twice.plan.event_list
        if event.event_type_str in EVENT_SETS_INSTALMENT_TUPLE
    ]
    assert len(opening_list) == 1
    assert opening_list[0].amount_float == 30000.0


def test_setting_it_is_idempotent():
    """The same answer twice leaves the same plan."""
    once = set_monthly_contribution(build_scenario(), 25000.0)
    assert set_monthly_contribution(once, 25000.0) == once


def test_a_later_change_is_never_overwritten():
    """Quick must not delete a raise the reader added in Guided."""
    scenario = build_scenario(
        TimelineEvent(
            EVENT_CHANGE_SIP_STR, date(2031, 1, 1), 40000.0
        )
    )
    updated = set_monthly_contribution(scenario, 25000.0)
    later_list = [
        event
        for event in updated.plan.event_list
        if event.event_date > PLAN_START_DATE
    ]
    assert len(later_list) == 1
    assert later_list[0].amount_float == 40000.0


def test_reading_it_back_returns_what_was_set():
    """The reader sees the number they typed when they return."""
    updated = set_monthly_contribution(build_scenario(), 18500.0)
    assert read_monthly_contribution_float(updated) == 18500.0


def test_reading_it_reports_the_opening_amount_not_a_later_one():
    """A plan that changes later still opens where it opened."""
    scenario = set_monthly_contribution(
        build_scenario(
            TimelineEvent(
                EVENT_CHANGE_SIP_STR, date(2031, 1, 1), 40000.0
            )
        ),
        25000.0,
    )
    assert read_monthly_contribution_float(scenario) == 25000.0


def test_setting_it_hands_the_amounts_to_the_timeline():
    """Otherwise the fund's own instalment would double-count."""
    updated = set_monthly_contribution(build_scenario(), 25000.0)
    assert (
        updated.amounts_source_str == AMOUNTS_SOURCE_TIMELINE_STR
    )
    compiled = compile_scenario(updated)
    assert compiled.fund_list[0].monthly_sip_float == 0.0


def test_a_form_plan_reports_its_funds_instalment():
    """A dashboard-shaped plan answers the same question."""
    scenario = build_scenario()
    assert read_monthly_contribution_float(scenario) == (
        scenario.fund_list[0].monthly_sip_float
    )


# --- The rest of the small edits ----------------------------------


@pytest.mark.parametrize("years_int", [1, 20, 50])
def test_setting_the_horizon(years_int):
    """The horizon is whatever the reader said."""
    updated = set_horizon_years(build_scenario(), years_int)
    assert updated.plan.horizon_years_int == years_int


def test_a_zero_horizon_is_refused_rather_than_stored():
    """A plan running for no months is not a plan."""
    assert (
        set_horizon_years(build_scenario(), 0).plan
    ).horizon_years_int == 1


def test_the_start_date_is_anchored_to_a_month():
    """The engine works on a month grid, so days are meaningless."""
    updated = set_start_date(build_scenario(), date(2027, 6, 14))
    assert updated.plan.start_date == date(2027, 6, 1)


def test_moving_the_start_leaves_events_where_they_were():
    """A later start is not the same as shifting every event."""
    scenario = build_scenario(
        TimelineEvent(EVENT_START_SIP_STR, date(2029, 1, 1), 500.0)
    )
    updated = set_start_date(scenario, date(2027, 1, 1))
    assert updated.plan.event_list[0].event_date == date(
        2029, 1, 1
    )


def test_the_return_applies_to_every_fund():
    """A simple screen offers one return for one portfolio."""
    scenario = PlanScenario(
        plan=TimelinePlan(
            start_date=PLAN_START_DATE, horizon_years_int=20
        ),
        fund_list=[
            build_test_fund(name_str="Equity"),
            build_test_fund(name_str="Debt"),
        ],
    )
    updated = set_expected_return(scenario, 9.5)
    assert [
        fund.gross_return_percent_float
        for fund in updated.fund_list
    ] == [9.5, 9.5]
    assert read_expected_return_float(updated) == 9.5


def test_the_currency_changes_no_amount():
    """Presentation is presentation; nothing is converted."""
    scenario = set_monthly_contribution(build_scenario(), 25000.0)
    updated = set_currency_code(scenario, "USD")
    assert read_monthly_contribution_float(updated) == 25000.0
    assert updated.presentation.currency_code_str == "USD"


def test_the_currency_does_not_change_the_tax_regime():
    """A reader may hold a fund quoted in another country."""
    updated = set_currency_code(build_scenario(), "USD")
    assert updated.presentation.regime_code_str == (
        build_scenario().presentation.regime_code_str
    )


def test_setting_inflation_overrides_the_currency_default():
    """An explicit rate always wins."""
    updated = set_inflation_percent(build_scenario(), 4.25)
    assert updated.resolved_inflation_percent_float == 4.25


def test_naming_a_plan():
    """Comparisons and reports need something to call it."""
    updated = set_scenario_name(build_scenario(), "Retire at 50")
    assert updated.name_str == "Retire at 50"


def test_an_empty_name_keeps_the_old_one():
    """A blank box must not wipe the label."""
    named = set_scenario_name(build_scenario(), "Retire at 50")
    assert set_scenario_name(named, "").name_str == "Retire at 50"


def test_a_named_copy_is_independent():
    """Editing a comparison entry must not touch the original."""
    original = set_monthly_contribution(
        build_scenario(), 25000.0
    )
    copied = build_named_copy(original, "Paused for three years")
    assert copied.name_str == "Paused for three years"
    assert copied.plan.event_list is not original.plan.event_list
    assert copied.fund_list is not original.fund_list
    assert compile_scenario(copied) == compile_scenario(original)
